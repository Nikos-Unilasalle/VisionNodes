"""
sci_robust_bbox.py — bounding box fit, ordinary vs robust (Huber-like, MAD-based).

Fits a tight box around the foreground pixels of a mask. Ordinary mode takes the
literal min/max extent — a single stray blob (a sticker, a speck) stretches the
box to include it. Robust mode rejects pixels whose x or y coordinate is more
than `tolerance` scaled-MADs from the median coordinate before taking the
extent, the same trimming idea as Huber loss (ch15, robust losses in detection).
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_MAD_TO_STD = 1.4826  # scale factor so tolerance reads in std-equivalent units


@vision_node(
    type_id='sci_robust_bbox',
    label='Robust Box Fit',
    category='measure',
    icon='ScanLine',
    description=(
        "Fits a bounding box to a mask's foreground pixels, in two modes "
        "(ch15 §15.x, robust losses). Ordinary takes the literal min/max extent "
        "— a single outlier blob (a sticker next to the real object) stretches "
        "the box to swallow it. Robust rejects pixels whose x or y coordinate is "
        "more than `tolerance` scaled-MADs from the median before measuring the "
        "extent, the same idea Huber loss applies to regression. Both boxes are "
        "drawn for direct comparison; the chosen mode's box is also reported "
        "numerically."
    ),
    inputs=[
        {'id': 'mask',  'label': 'Mask',           'color': 'mask'},
        {'id': 'image', 'label': 'Image (opt, BG)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',    'label': 'Overlay', 'color': 'image'},
        {'id': 'box_x',   'label': 'Box X',   'color': 'scalar'},
        {'id': 'box_y',   'label': 'Box Y',   'color': 'scalar'},
        {'id': 'box_w',   'label': 'Box W',   'color': 'scalar'},
        {'id': 'box_h',   'label': 'Box H',   'color': 'scalar'},
        {'id': 'n_rejected', 'label': 'Rejected Px', 'color': 'scalar'},
    ],
    params=[
        {'id': 'mode',      'label': 'Mode', 'type': 'enum',
         'options': ['Ordinary', 'Robust (Huber)'], 'default': 1},
        {'id': 'tolerance', 'label': 'Tolerance (scaled MAD)', 'type': 'float',
         'default': 2.0, 'min': 0.5, 'max': 20.0, 'step': 0.1},
    ]
)
class RobustBBoxNode(NodeProcessor):

    @staticmethod
    def _ordinary_box(xs, ys):
        return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)

    @classmethod
    def _robust_box(cls, xs, ys, tol):
        mx, my = np.median(xs), np.median(ys)
        madx = np.median(np.abs(xs - mx)) or 1.0
        mady = np.median(np.abs(ys - my)) or 1.0
        keep = (np.abs(xs - mx) <= tol * _MAD_TO_STD * madx) & \
               (np.abs(ys - my) <= tol * _MAD_TO_STD * mady)
        if not keep.any():
            keep = np.ones_like(keep)
        kx, ky = xs[keep], ys[keep]
        box = cls._ordinary_box(kx, ky)
        return box, int((~keep).sum())

    def process(self, inputs, params):
        mask = inputs.get('mask')
        empty = {'main': None, 'box_x': 0, 'box_y': 0, 'box_w': 0, 'box_h': 0, 'n_rejected': 0}
        if mask is None:
            return empty

        gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask
        ys, xs = np.nonzero(gray > 127)
        if len(xs) == 0:
            return empty

        mode = int(params.get('mode', 1))
        tol  = float(params.get('tolerance', 3.0))

        ord_box = self._ordinary_box(xs, ys)
        rob_box, n_rejected = self._robust_box(xs, ys, tol)
        chosen = rob_box if mode == 1 else ord_box

        bg = inputs.get('image')
        H, W = gray.shape
        if bg is not None and isinstance(bg, np.ndarray):
            base = bg.copy()
            if base.ndim == 2:
                base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
            if base.shape[:2] != (H, W):
                base = cv2.resize(base, (W, H))
        else:
            base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        overlay = base.copy()
        ox, oy, ow, oh = ord_box
        cv2.rectangle(overlay, (ox, oy), (ox + ow, oy + oh), (0, 0, 255), 1, cv2.LINE_AA)  # red = ordinary
        rx, ry, rw, rh = rob_box
        cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (0, 220, 0), 2, cv2.LINE_AA)  # green = robust

        label = f'{["Ordinary","Robust"][mode]}  rejected={n_rejected}/{len(xs)}  tol={tol:.1f}'
        cv2.putText(overlay, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(overlay, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'red=ordinary', (8, H - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'green=robust', (8, H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 0), 1, cv2.LINE_AA)

        cx, cy, cw, ch = chosen
        return {
            'main': overlay,
            'box_x': cx, 'box_y': cy, 'box_w': cw, 'box_h': ch,
            'n_rejected': n_rejected,
        }
