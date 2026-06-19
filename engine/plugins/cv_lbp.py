"""
Local Binary Pattern node for VNStudio.
Chapter 13 (texture).
Computes the LBP texture descriptor (skimage.feature.local_binary_pattern),
a colored LBP map, and a histogram of the codes.
"""

import cv2
import numpy as np
from skimage.feature import local_binary_pattern
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_lbp',
    label='Local Binary Pattern',
    category='measure',
    icon='Grid3x3',
    description="Local Binary Pattern texture descriptor. Encodes each pixel by "
                "thresholding its circular neighborhood, then outputs a colored map and histogram.",
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'LBP Map', 'color': 'image'},
        {'id': 'hist_image', 'label': 'Histogram', 'color': 'image'},
        {'id': 'data', 'label': 'Data', 'color': 'dict'},
    ],
    params=[
        {'id': 'points', 'label': 'Points (P)', 'type': 'int', 'min': 4, 'max': 24, 'default': 8},
        {'id': 'radius', 'label': 'Radius (R)', 'type': 'float', 'min': 1.0, 'max': 10.0, 'default': 1.0},
        {'id': 'method', 'label': 'Method', 'type': 'enum',
         'options': ['uniform', 'default', 'ror', 'var'], 'default': 'uniform'},
        {'id': 'show_histogram', 'label': 'Show Histogram', 'type': 'bool', 'default': True},
    ]
)
class LocalBinaryPatternNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'hist_image': None, 'data': None}

        points = int(params.get('points', 8))
        radius = float(params.get('radius', 1.0))
        method = params.get('method', 'uniform')
        if method not in ('uniform', 'default', 'ror', 'var'):
            method = 'uniform'
        show_histogram = bool(params.get('show_histogram', True))

        # Grayscale
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        # Compute LBP
        lbp = local_binary_pattern(gray, points, radius, method)
        lbp = np.nan_to_num(lbp, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float64)

        # Normalize the LBP map robustly to 0-255 (var/ror produce float ranges)
        lo = float(lbp.min())
        hi = float(lbp.max())
        if hi > lo:
            lbp_norm = ((lbp - lo) / (hi - lo) * 255.0).astype(np.uint8)
        else:
            lbp_norm = np.zeros_like(lbp, dtype=np.uint8)
        lbp_color = cv2.applyColorMap(lbp_norm, cv2.COLORMAP_JET)

        # Histogram of LBP codes
        if method in ('uniform', 'default', 'ror'):
            n_bins = int(lbp.max()) + 1
            n_bins = max(1, n_bins)
            hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(0, n_bins))
        else:
            # 'var' is continuous-valued; use a fixed bin count
            n_bins = 64
            hist, _ = np.histogram(lbp.ravel(), bins=n_bins, range=(lo, hi if hi > lo else lo + 1.0))

        hist = hist.astype(np.float64)
        total = hist.sum()
        if total > 0:
            hist = hist / total  # normalized histogram

        hist_bgr = None
        if show_histogram:
            hist_bgr = self._render_histogram(hist)

        return {
            'main': lbp_color,
            'hist_image': hist_bgr,
            'data': {'histogram': hist.tolist(), 'n_bins': int(n_bins)},
        }

    def _render_histogram(self, hist):
        """Render a normalized histogram as a BGR uint8 bar chart."""
        W, H = 512, 256
        margin = 20
        canvas = np.full((H, W, 3), 30, dtype=np.uint8)
        n = len(hist)
        if n == 0:
            return canvas

        plot_w = W - 2 * margin
        plot_h = H - 2 * margin
        max_val = float(hist.max()) if hist.max() > 0 else 1.0
        bar_w = max(1, plot_w // n)

        for i, v in enumerate(hist):
            bar_h = int((v / max_val) * plot_h)
            x0 = margin + i * bar_w
            x1 = x0 + max(1, bar_w - 1)
            y0 = H - margin
            y1 = y0 - bar_h
            cv2.rectangle(canvas, (x0, y1), (x1, y0), (0, 200, 255), -1)

        # Axis line
        cv2.line(canvas, (margin, H - margin), (W - margin, H - margin), (200, 200, 200), 1)
        return canvas
