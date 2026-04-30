from registry import vision_node, NodeProcessor
import cv2
import numpy as np

_INT_W, _INT_H = 320, 240  # fixed internal resolution for motion EVM

@vision_node(
    type_id='plugin_evm_motion',
    label='EVM Motion',
    category='detect',
    icon='Waves',
    description=(
        "Eulerian Video Magnification — motion amplification (Wu et al. 2012). "
        "Amplifies subtle spatial motions via Laplacian pyramid + IIR bandpass per level. "
        "Optional mask input: restricts both analysis and amplification to masked pixels. "
        "lambda_c attenuates fine spatial scales (paper: 80px for motion). "
        "motion_mag output = mean absolute motion amplitude per frame."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',       'color': 'image'},
        {'id': 'motion_mag', 'color': 'scalar'},
        {'id': 'motion_vis', 'color': 'image'},
    ],
    params=[
        {'id': 'alpha',       'min': 0,    'max': 200,  'step': 1, 'default': 20},
        {'id': 'low_cutoff',  'min': 0,    'max': 5000, 'step': 1, 'default': 40},
        {'id': 'high_cutoff', 'min': 0,    'max': 5000, 'step': 1, 'default': 300},
        {'id': 'fps',         'min': 10,   'max': 120,  'step': 1, 'default': 30},
        {'id': 'levels',      'min': 1,    'max': 6,    'step': 1, 'default': 4},
        {'id': 'lambda_c',   'min': 1,    'max': 1000, 'step': 1, 'default': 80},
    ]
)
class EVMMotionNode(NodeProcessor):
    """
    low_cutoff / high_cutoff: mHz.
    lambda_c: spatial wavelength cutoff (px). Level l has wavelength 2^(l+1)px.
              Levels below lambda_c get attenuated proportionally.

    Mask workflow (when mask connected):
      1. Bounding-box crop → Laplacian pyramid + IIR on small patch only  (compute saving)
      2. motion_mag averaged on masked pixels only                         (better SNR)
      3. Amplification blended back with mask weight                       (no background artifacts)

    Internal processing at 320×240 — stable state regardless of crop size variation.
    """

    def __init__(self):
        self.low1 = None
        self.low2 = None
        self._sig = None

    def _reset(self):
        self.low1 = None
        self.low2 = None

    @staticmethod
    def _build_laplacian_pyramid(img, levels):
        pyr = []
        current = img
        for _ in range(levels):
            down = cv2.pyrDown(current)
            up   = cv2.pyrUp(down, dstsize=(current.shape[1], current.shape[0]))
            pyr.append(current - up)
            current = down
        pyr.append(current)
        return pyr

    @staticmethod
    def _collapse_laplacian_pyramid(pyr):
        result = pyr[-1]
        for lap in reversed(pyr[:-1]):
            result = cv2.pyrUp(result, dstsize=(lap.shape[1], lap.shape[0]))
            result = result + lap
        return result

    def process(self, inputs, params):
        img  = inputs.get('image')
        mask = inputs.get('mask')
        if img is None:
            return {'main': None, 'motion_mag': 0.0, 'motion_vis': None}

        alpha    = float(params.get('alpha', 20))
        low_hz   = float(params.get('low_cutoff',  40))  / 1000.0
        high_hz  = float(params.get('high_cutoff', 300)) / 1000.0
        fps      = max(1.0, float(params.get('fps', 30)))
        levels   = int(params.get('levels', 4))
        lambda_c = max(1.0, float(params.get('lambda_c', 80)))

        sig = (low_hz, high_hz, fps, levels, lambda_c)
        if sig != self._sig:
            self._reset()
            self._sig = sig

        r_high = 1.0 - np.exp(-2.0 * np.pi * high_hz / fps)
        r_low  = 1.0 - np.exp(-2.0 * np.pi * low_hz  / fps)

        h, w = img.shape[:2]

        # --- Normalise mask → float weight map and bounding box ---
        has_mask = False
        mask_f   = None
        x1, y1, x2, y2 = 0, 0, w, h

        if mask is not None:
            m = mask if mask.ndim == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            m = cv2.resize(m, (w, h)) if m.shape[:2] != (h, w) else m
            if m.any():
                has_mask = True
                mask_f   = (m > 0).astype(np.float32)[:, :, np.newaxis]
                bx, by, bw, bh = cv2.boundingRect((m > 0).astype(np.uint8))
                pad = 8
                x1 = max(0, bx - pad);  y1 = max(0, by - pad)
                x2 = min(w, bx+bw+pad); y2 = min(h, by+bh+pad)

        roi = img[y1:y2, x1:x2]

        # Fixed internal resolution — prevents state resets on crop size changes
        frame_small = cv2.resize(roi, (_INT_W, _INT_H)).astype(np.float32) / 255.0

        pyr = self._build_laplacian_pyramid(frame_small, levels)

        if self.low1 is None:
            self.low1 = [lv.copy() for lv in pyr]
            self.low2 = [lv.copy() for lv in pyr]

        amp_pyr       = []
        motion_signal = 0.0

        for l, lv in enumerate(pyr):
            wavelength_l = float(2 ** (l + 1))
            alpha_eff = alpha * min(1.0, wavelength_l / lambda_c)

            self.low1[l] = (1.0 - r_high) * self.low1[l] + r_high * lv
            self.low2[l] = (1.0 - r_low)  * self.low2[l] + r_low  * lv
            filtered = self.low1[l] - self.low2[l]

            # Signal: masked pixels only if mask available (Strategy 2)
            if has_mask:
                lh, lw = filtered.shape[:2]
                roi_mask_lv = cv2.resize(
                    (mask_f[y1:y2, x1:x2, 0] * 255).astype(np.uint8),
                    (lw, lh)) > 0
                if roi_mask_lv.any():
                    motion_signal += float(np.mean(np.abs(filtered)[roi_mask_lv])) * alpha_eff
                else:
                    motion_signal += float(np.mean(np.abs(filtered))) * alpha_eff
            else:
                motion_signal += float(np.mean(np.abs(filtered))) * alpha_eff

            amp_pyr.append(lv + alpha_eff * filtered)

        reconstructed_small = self._collapse_laplacian_pyramid(amp_pyr)
        reconstructed_small = np.clip(reconstructed_small, 0.0, 1.0)

        # Scale back to roi size
        roi_h, roi_w = y2 - y1, x2 - x1
        reconstructed_roi = cv2.resize(reconstructed_small, (roi_w, roi_h))

        # Blend amplification with mask and paste into full frame (Strategy 1 + 3)
        result = img.astype(np.float32) / 255.0
        if has_mask:
            roi_mask_f = mask_f[y1:y2, x1:x2]
            orig_roi   = result[y1:y2, x1:x2]
            result[y1:y2, x1:x2] = orig_roi * (1.0 - roi_mask_f) + reconstructed_roi * roi_mask_f
        else:
            result[y1:y2, x1:x2] = reconstructed_roi
        result = (np.clip(result, 0.0, 1.0) * 255).astype(np.uint8)

        # Motion delta visualization
        orig_small = cv2.resize(roi.astype(np.float32) / 255.0, (_INT_W, _INT_H))
        delta_small = np.clip(0.5 + (reconstructed_small - orig_small) * 3.0, 0.0, 1.0)
        motion_vis_roi = (cv2.resize(delta_small, (roi_w, roi_h)) * 255).astype(np.uint8)
        motion_vis = np.full((h, w, 3), 128, dtype=np.uint8)
        motion_vis[y1:y2, x1:x2] = motion_vis_roi

        return {
            'main':       result,
            'motion_mag': motion_signal * 1000.0,
            'motion_vis': motion_vis,
        }
