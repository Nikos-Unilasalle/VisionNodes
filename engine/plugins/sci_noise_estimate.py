"""
sci_noise_estimate.py — reference-free noise / SNR estimation (ch14 §14.1).

Estimates the Gaussian-noise standard deviation of an image WITHOUT a clean
reference, using Immerkaer's fast Laplacian estimator (robust to structure up
to second order), and fits the Poisson-Gauss affine variance law  Var(I)=a*I+b
by binning local mean vs local variance. Reports SNR too.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

# Immerkaer double-Laplacian mask: cancels smooth structure, leaves noise.
_IMMERKAER = np.array([[1, -2, 1],
                       [-2, 4, -2],
                       [1, -2, 1]], dtype=np.float32)


@vision_node(
    type_id='sci_noise_estimate',
    label='Noise Estimate',
    category='measure',
    icon='Activity',
    description=(
        "Reference-free noise and SNR estimation (ch14 §14.1).\n\n"
        "sigma: robust Gaussian-noise std via Immerkaer's Laplacian estimator "
        "(cancels image structure up to 2nd order, so it measures the random "
        "floor, not the edges).\n"
        "snr_db: 10*log10(mean^2 / sigma^2).\n"
        "gain_a, read_b: affine fit of the Poisson-Gauss variance law "
        "Var(I) = a*I + b, from local mean vs local variance — a is the "
        "photon-shot gain, b the electronic read floor.\n\n"
        "Linearise the image first (ch7): the affine law only holds in linear "
        "space. Saturated / clipped pixels are excluded from the fit."
    ),
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main',     'color': 'image',  'label': 'Overlay'},
        {'id': 'sigma',    'color': 'scalar', 'label': 'Sigma (noise)'},
        {'id': 'snr_db',   'color': 'scalar', 'label': 'SNR (dB)'},
        {'id': 'gain_a',   'color': 'scalar', 'label': 'Gain a'},
        {'id': 'read_b',   'color': 'scalar', 'label': 'Read floor b'},
        {'id': 'data',     'color': 'dict',   'label': 'Stats'},
    ],
    params=[
        {'id': 'window',   'label': 'Local Window (px)', 'type': 'int',
         'default': 7, 'min': 3, 'max': 31},
        {'id': 'exclude_sat', 'label': 'Exclude 0/255', 'type': 'bool', 'default': True},
        {'id': 'show_overlay', 'label': 'Show Overlay', 'type': 'bool', 'default': True},
    ],
)
class NoiseEstimateNode(NodeProcessor):

    @staticmethod
    def _to_gray(img):
        if img is None:
            return None
        if img.ndim == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return img.astype(np.float32)

    @staticmethod
    def _immerkaer_sigma(gray):
        """Robust Gaussian-noise std (Immerkaer 1996)."""
        h, w = gray.shape[:2]
        if h < 3 or w < 3:
            return 0.0
        conv = cv2.filter2D(gray, cv2.CV_32F, _IMMERKAER, borderType=cv2.BORDER_REPLICATE)
        s = float(np.sum(np.abs(conv)))
        sigma = s * np.sqrt(np.pi / 2.0) / (6.0 * (w - 2) * (h - 2))
        return float(sigma)

    def _affine_fit(self, gray, window, exclude_sat):
        """Fit Var(I) = a*I + b from local mean vs local variance."""
        k = int(window) | 1  # force odd
        mean = cv2.blur(gray, (k, k))
        mean_sq = cv2.blur(gray * gray, (k, k))
        var = np.clip(mean_sq - mean * mean, 0.0, None)

        m = mean.ravel()
        v = var.ravel()
        if exclude_sat:
            keep = (m > 1.0) & (m < 254.0)
            m, v = m[keep], v[keep]
        if m.size < 32:
            return 0.0, float(np.median(v)) if v.size else 0.0

        # Robust binning: median variance per intensity bin, then LS line.
        bins = np.linspace(float(m.min()), float(m.max()), 24)
        idx = np.digitize(m, bins)
        xs, ys = [], []
        for b in range(1, len(bins)):
            sel = idx == b
            if np.count_nonzero(sel) >= 8:
                xs.append(float(np.mean(m[sel])))
                ys.append(float(np.median(v[sel])))  # median var = robust to edges
        if len(xs) < 2:
            return 0.0, float(np.median(v))
        a, b = np.polyfit(np.array(xs), np.array(ys), 1)
        return float(a), float(b)

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'sigma': 0.0, 'snr_db': 0.0,
                    'gain_a': 0.0, 'read_b': 0.0, 'data': None}

        gray = self._to_gray(img)
        window = int(params.get('window', 7))
        exclude_sat = bool(params.get('exclude_sat', True))

        sigma = self._immerkaer_sigma(gray)
        mean_signal = float(np.mean(gray))
        snr_db = float(10.0 * np.log10((mean_signal ** 2) / (sigma ** 2))) if sigma > 1e-6 else 0.0
        gain_a, read_b = self._affine_fit(gray, window, exclude_sat)

        sigma = round(sigma, 3)
        snr_db = round(snr_db, 2)
        gain_a = round(gain_a, 4)
        read_b = round(read_b, 3)

        base = img.copy() if img.ndim == 3 else cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_GRAY2BGR)
        base = base.astype(np.uint8)
        if bool(params.get('show_overlay', True)):
            lines = [f"sigma={sigma}", f"SNR={snr_db} dB", f"a={gain_a}  b={read_b}"]
            y = 22
            for ln in lines:
                cv2.putText(base, ln, (8, y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (0, 255, 0), 2, cv2.LINE_AA)
                y += 24

        return {
            'main': base,
            'sigma': sigma,
            'snr_db': snr_db,
            'gain_a': gain_a,
            'read_b': read_b,
            'data': {'sigma': sigma, 'snr_db': snr_db, 'gain_a': gain_a,
                     'read_b': read_b, 'mean': round(mean_signal, 2)},
        }
