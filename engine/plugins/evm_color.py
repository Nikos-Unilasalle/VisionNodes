from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

# Fixed internal processing resolution — prevents state resets when crop size changes
# (face moves → crop varies → without this fix the IIR never converges)
_INT_W, _INT_H = 160, 120

@vision_node(
    type_id='plugin_evm_color',
    label='EVM Color',
    category='cv',
    icon='Activity',
    description=(
        "Eulerian Video Magnification — color amplification (Wu et al. 2012). "
        "Amplifies subtle Cr/Cb variations (pulse, perfusion) via Gaussian pyramid + IIR bandpass. "
        "Default params target resting pulse (50–60 BPM). "
        "Outputs: amplified video + scientific signal (mean bandpass Cr ×1000, oscillates at pulse rate)."
    ),
    inputs=[{'id': 'image', 'color': 'image'}],
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
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'signal': 0.0, 'signal_cb': 0.0, 'filtered_vis': None}

        alpha    = float(params.get('alpha', 120))
        low_hz   = float(params.get('low_cutoff',  830))  / 1000.0
        high_hz  = float(params.get('high_cutoff', 1000)) / 1000.0
        fps      = max(1.0, float(params.get('fps', 30)))
        levels   = int(params.get('levels', 3))
        att      = float(params.get('attenuation', 3)) / 100.0

        sig = (low_hz, high_hz, fps, levels)
        if sig != self._sig:
            self._reset()
            self._sig = sig

        r_high = 1.0 - np.exp(-2.0 * np.pi * high_hz / fps)
        r_low  = 1.0 - np.exp(-2.0 * np.pi * low_hz  / fps)

        # Always work at fixed internal resolution — state shape is constant regardless of crop
        frame = img.astype(np.float32) / 255.0
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (_INT_W, _INT_H))
        ycrcb_s = cv2.cvtColor(small, cv2.COLOR_BGR2YCrCb)

        coarse = ycrcb_s
        for _ in range(levels):
            coarse = cv2.pyrDown(coarse)

        if self.low1 is None:
            self.low1 = coarse.copy()
            self.low2 = coarse.copy()

        self.low1 = (1.0 - r_high) * self.low1 + r_high * coarse
        self.low2 = (1.0 - r_low)  * self.low2 + r_low  * coarse
        filtered = self.low1 - self.low2

        # Scientific outputs: mean Cr / Cb bandpass (×1000 for readability)
        signal    = float(np.mean(filtered[:, :, 1])) * 1000.0
        signal_cb = float(np.mean(filtered[:, :, 2])) * 1000.0

        # Clamp then amplify (kills transients from residual motion)
        filtered_clamped = np.clip(filtered, -att, att)
        amplified = filtered_clamped * alpha

        # Upsample back to internal resolution then scale to actual frame size
        for _ in range(levels):
            amplified = cv2.pyrUp(amplified)
        amplified = amplified[:_INT_H, :_INT_W]
        amplified_full = cv2.resize(amplified, (w, h))

        # Apply to Cr/Cb channels only — preserves luminance
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        out = ycrcb.copy()
        out[:, :, 1:] += amplified_full[:, :, 1:]
        out = np.clip(out, 0.0, 1.0)
        result = cv2.cvtColor(out, cv2.COLOR_YCrCb2BGR)

        # Delta visualization: red = Cr amplification, blue = Cb amplification
        fv = np.zeros_like(frame)
        fv[:, :, 2] = np.clip(0.5 + amplified_full[:, :, 1] * 2.0, 0.0, 1.0)
        fv[:, :, 0] = np.clip(0.5 + amplified_full[:, :, 2] * 2.0, 0.0, 1.0)
        filtered_vis = (fv * 255).astype(np.uint8)

        return {
            'main':         (result * 255).astype(np.uint8),
            'signal':       signal,
            'signal_cb':    signal_cb,
            'filtered_vis': filtered_vis,
        }
