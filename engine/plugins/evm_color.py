from registry import vision_node, NodeProcessor
import cv2
import numpy as np

# Fixed internal processing resolution — prevents state resets when crop size changes
# (face moves → crop varies → without this fix the IIR never converges)
_INT_W, _INT_H = 160, 120

@vision_node(
    type_id='plugin_evm_color',
    label='EVM Color',
    category='fx',
    icon='Activity',
    description=(
        "Eulerian Video Magnification — color amplification (Wu et al. 2012). "
        "Amplifies subtle Cr/Cb variations (pulse, perfusion) via Gaussian pyramid + IIR bandpass. "
        "Optional mask input: restricts both analysis and amplification to masked pixels (skin ROI). "
        "Default params target resting pulse (50–60 BPM). "
        "Outputs: amplified video + scientific signal (mean bandpass Cr ×1000, oscillates at pulse rate)."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',         'color': 'image'},
        {'id': 'signal',       'color': 'scalar'},
        {'id': 'signal_cb',    'color': 'scalar'},
        {'id': 'filtered_vis', 'color': 'image'},
    ],
    params=[
        {'id': 'alpha',       'min': 0,   'max': 250, 'step': 1, 'default': 120},
        {'id': 'low_cutoff',  'min': 0,   'max': 5000,'step': 1, 'default': 830},
        {'id': 'high_cutoff', 'min': 0,   'max': 5000,'step': 1, 'default': 1000},
        {'id': 'fps',         'min': 10,  'max': 120, 'step': 1, 'default': 30},
        {'id': 'levels',      'min': 1,   'max': 5,   'step': 1, 'default': 3},
        {'id': 'attenuation', 'min': 1,   'max': 100, 'step': 1, 'default': 3},
    ]
)
class EVMColorNode(NodeProcessor):
    """
    low_cutoff / high_cutoff: mHz (830 = 0.83 Hz ≈ 50 BPM, 1000 = 1.0 Hz ≈ 60 BPM).
    attenuation: max |filtered| as % of [0,1] range before alpha multiply.
                 Guards against motion transients. 3% default.
    alpha: 120 matches Wu et al. 2012 Table 1 (face pulse).

    Mask workflow (when mask connected):
      1. Bounding-box crop → pyramid + IIR run on small patch only        (compute saving)
      2. Signal averaged on masked pixels only via pixel indexing          (better SNR)
      3. Amplification blended back with mask weight                       (no background artifacts)

    Processing always at fixed 160×120 grid → IIR state never resets on crop size variation.
    """

    def __init__(self):
        self.low1 = None
        self.low2 = None
        self._sig = None

    def _reset(self):
        self.low1 = None
        self.low2 = None

    def process(self, inputs, params):
        img  = inputs.get('image')
        mask = inputs.get('mask')
        if img is None:
            return {'main': None, 'signal': 0.0, 'signal_cb': 0.0, 'filtered_vis': None}

        alpha   = float(params.get('alpha', 120))
        low_hz  = float(params.get('low_cutoff',  830))  / 1000.0
        high_hz = float(params.get('high_cutoff', 1000)) / 1000.0
        fps     = max(1.0, float(params.get('fps', 30)))
        levels  = int(params.get('levels', 3))
        att     = float(params.get('attenuation', 3)) / 100.0

        sig = (low_hz, high_hz, fps, levels)
        if sig != self._sig:
            self._reset()
            self._sig = sig

        r_high = 1.0 - np.exp(-2.0 * np.pi * high_hz / fps)
        r_low  = 1.0 - np.exp(-2.0 * np.pi * low_hz  / fps)

        h, w = img.shape[:2]
        frame = img.astype(np.float32) / 255.0

        # --- Normalise mask → float weight map (H×W×1) ---
        has_mask = False
        mask_f   = None
        x1, y1, x2, y2 = 0, 0, w, h

        if mask is not None:
            m = mask if mask.ndim == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            m = cv2.resize(m, (w, h)) if m.shape[:2] != (h, w) else m
            if m.any():
                has_mask = True
                mask_f   = (m > 0).astype(np.float32)[:, :, np.newaxis]
                # Bounding box — IIR runs only on this patch (Strategy 1)
                bx, by, bw, bh = cv2.boundingRect((m > 0).astype(np.uint8))
                pad = 8  # small margin for pyramid context
                x1 = max(0, bx - pad);  y1 = max(0, by - pad)
                x2 = min(w, bx+bw+pad); y2 = min(h, by+bh+pad)

        roi = frame[y1:y2, x1:x2]

        # --- IIR bandpass at fixed internal resolution (on bbox ROI only) ---
        small    = cv2.resize(roi, (_INT_W, _INT_H))
        ycrcb_s  = cv2.cvtColor(small, cv2.COLOR_BGR2YCrCb)
        coarse   = ycrcb_s
        for _ in range(levels):
            coarse = cv2.pyrDown(coarse)

        if self.low1 is None:
            self.low1 = coarse.copy()
            self.low2 = coarse.copy()

        self.low1 = (1.0 - r_high) * self.low1 + r_high * coarse
        self.low2 = (1.0 - r_low)  * self.low2 + r_low  * coarse
        filtered  = self.low1 - self.low2

        # --- Signal: averaged on masked coarse pixels (Strategy 2) ---
        if has_mask:
            ch, cw = filtered.shape[:2]
            roi_mask_small = cv2.resize(
                (mask_f[:, :, 0] * 255).astype(np.uint8)[y1:y2, x1:x2],
                (cw, ch)) > 0
            if roi_mask_small.any():
                signal    = float(np.mean(filtered[:, :, 1][roi_mask_small])) * 1000.0
                signal_cb = float(np.mean(filtered[:, :, 2][roi_mask_small])) * 1000.0
            else:
                signal    = float(np.mean(filtered[:, :, 1])) * 1000.0
                signal_cb = float(np.mean(filtered[:, :, 2])) * 1000.0
        else:
            signal    = float(np.mean(filtered[:, :, 1])) * 1000.0
            signal_cb = float(np.mean(filtered[:, :, 2])) * 1000.0

        # --- Clamp + amplify ---
        amplified = np.clip(filtered, -att, att) * alpha

        for _ in range(levels):
            amplified = cv2.pyrUp(amplified)
        amplified = amplified[:_INT_H, :_INT_W]

        # Upsample to bbox ROI size
        roi_h, roi_w = y2 - y1, x2 - x1
        amplified_roi = cv2.resize(amplified, (roi_w, roi_h))

        # --- Apply to Cr/Cb channels of bbox ROI, then paste back ---
        roi_ycrcb = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
        if has_mask:
            roi_mask_f = mask_f[y1:y2, x1:x2]          # (roi_h, roi_w, 1)
            roi_ycrcb[:, :, 1:] += amplified_roi[:, :, 1:] * roi_mask_f
        else:
            roi_ycrcb[:, :, 1:] += amplified_roi[:, :, 1:]
        roi_ycrcb = np.clip(roi_ycrcb, 0.0, 1.0)
        roi_result = cv2.cvtColor(roi_ycrcb, cv2.COLOR_YCrCb2BGR)

        result = frame.copy()
        result[y1:y2, x1:x2] = roi_result

        # --- Delta visualisation ---
        amp_full = np.zeros((h, w, 3), dtype=np.float32)
        amp_full[y1:y2, x1:x2] = amplified_roi
        fv = np.zeros((h, w, 3), dtype=np.float32)
        fv[:, :, 2] = np.clip(0.5 + amp_full[:, :, 1] * 2.0, 0.0, 1.0)
        fv[:, :, 0] = np.clip(0.5 + amp_full[:, :, 2] * 2.0, 0.0, 1.0)
        filtered_vis = (fv * 255).astype(np.uint8)

        return {
            'main':         (result * 255).astype(np.uint8),
            'signal':       signal,
            'signal_cb':    signal_cb,
            'filtered_vis': filtered_vis,
        }
