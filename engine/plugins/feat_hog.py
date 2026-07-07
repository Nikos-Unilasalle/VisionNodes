"""
feat_hog.py — Histogram of Oriented Gradients descriptor + visualisation.

Splits the image into cells and, in each, builds a histogram of gradient
orientations weighted by magnitude — the classic pedestrian-detection signature
(ch17, local descriptors). Outputs the cell-orientation visualisation and a
compact global orientation histogram (the shape signature).
"""

import cv2
import numpy as np
from skimage.feature import hog
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='feat_hog',
    label='HOG Descriptor',
    category='measure',
    icon='Wind',
    description=(
        "Histogram of Oriented Gradients. Splits the image into cells and draws, "
        "in each, the dominant gradient orientations (perpendicular to edges). "
        "Outputs the HOG visualisation and a compact global orientation histogram "
        "(signature) that stays stable under small rotations — the basis of "
        "pedestrian detection."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',      'label': 'HOG Visual', 'color': 'image'},
        {'id': 'signature', 'label': 'Signature',  'color': 'list'},
        {'id': 'n_bins',    'label': 'Orientations', 'color': 'scalar'},
    ],
    params=[
        {'id': 'orientations', 'label': 'Orientations', 'type': 'int', 'default': 9, 'min': 4, 'max': 18},
        {'id': 'cell_px',      'label': 'Cell Size (px)', 'type': 'int', 'default': 16, 'min': 4, 'max': 64},
        {'id': 'overlay',      'label': 'Overlay on Image', 'type': 'bool', 'default': True},
    ]
)
class HOGNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'signature': [], 'n_bins': 0}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()

        n_bins  = int(params.get('orientations', 9))
        cell_px = int(params.get('cell_px', 16))
        overlay = bool(params.get('overlay', True))

        _, hog_img = hog(
            gray, orientations=n_bins,
            pixels_per_cell=(cell_px, cell_px),
            cells_per_block=(1, 1), visualize=True, feature_vector=False,
        )
        hog_u8 = cv2.normalize(hog_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        hog_vis = cv2.applyColorMap(hog_u8, cv2.COLORMAP_INFERNO)

        if overlay:
            base = img if img.ndim == 3 else cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            if base.shape[:2] != hog_vis.shape[:2]:
                base = cv2.resize(base, (hog_vis.shape[1], hog_vis.shape[0]))
            vis = cv2.addWeighted(base, 0.4, hog_vis, 0.9, 0)
        else:
            vis = hog_vis

        # Compact signature: global orientation histogram weighted by gradient
        # magnitude, folded to [0, 180) so opposite gradients share a bin.
        gx = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx ** 2 + gy ** 2)
        ang = (np.degrees(np.arctan2(gy, gx)) % 180.0)
        hist, _ = np.histogram(ang, bins=n_bins, range=(0, 180), weights=mag)
        total = float(hist.sum()) or 1.0
        signature = [round(float(h / total), 4) for h in hist]

        return {'main': vis, 'signature': signature, 'n_bins': n_bins}
