"""
feat_ransac_line.py — dominant line fitting on edge points (RANSAC vs L2).

Fits a single dominant straight line to the white pixels of an edge map
(e.g. Canny output). RANSAC finds the consensus line that the most points
agree on, ignoring outliers (false lines from clutter); the least-squares
mode fits every point and is easily dragged off by outliers — the contrast
is the whole point (ch16 §16.x, robust estimation).
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_MAX_POINTS = 4000  # subsample cap for speed


@vision_node(
    type_id='feat_ransac_line',
    label='RANSAC Line Fit',
    category='measure',
    icon='Slash',
    description=(
        "Fits one dominant line to the white pixels of an edge map. RANSAC keeps "
        "the consensus line supported by the most inliers (robust to false lines); "
        "Least Squares fits all points (dragged off by outliers). Reports the "
        "inlier count and the line angle, and overlays the fit."
    ),
    inputs=[
        {'id': 'image', 'label': 'Edges', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',    'label': 'Overlay', 'color': 'image'},
        {'id': 'inliers', 'label': 'Inliers', 'color': 'scalar'},
        {'id': 'angle',   'label': 'Angle (deg)', 'color': 'scalar'},
        {'id': 'n_points','label': 'Edge Points', 'color': 'scalar'},
    ],
    params=[
        {'id': 'mode',       'label': 'Mode', 'type': 'enum',
         'options': ['RANSAC', 'Least Squares'], 'default': 0},
        {'id': 'threshold',  'label': 'Inlier Dist (px)', 'type': 'float', 'default': 3.0, 'min': 0.5, 'max': 30.0, 'step': 0.5},
        {'id': 'iterations', 'label': 'Iterations',       'type': 'int',   'default': 200, 'min': 10, 'max': 5000},
    ]
)
class RansacLineNode(NodeProcessor):

    @staticmethod
    def _points(edges: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(edges, cv2.COLOR_BGR2GRAY) if edges.ndim == 3 else edges
        ys, xs = np.nonzero(gray > 127)
        pts = np.column_stack([xs, ys]).astype(np.float32)  # (N, 2) as (x, y)
        if len(pts) > _MAX_POINTS:
            idx = np.random.choice(len(pts), _MAX_POINTS, replace=False)
            pts = pts[idx]
        return pts

    @staticmethod
    def _fit_l2(pts: np.ndarray):
        vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        return float(vx), float(vy), float(x0), float(y0)

    @staticmethod
    def _dist_to_line(pts, vx, vy, x0, y0):
        # Perpendicular distance to line through (x0,y0) with unit dir (vx,vy):
        # |(p - p0) x dir|
        dx = pts[:, 0] - x0
        dy = pts[:, 1] - y0
        return np.abs(dx * vy - dy * vx)

    def _ransac(self, pts, thr, iters):
        n = len(pts)
        best_inliers = None
        best_count = -1
        rng = np.random.default_rng()
        for _ in range(iters):
            i, j = rng.integers(0, n, size=2)
            if i == j:
                continue
            p1, p2 = pts[i], pts[j]
            d = p2 - p1
            norm = np.hypot(d[0], d[1])
            if norm < 1e-6:
                continue
            vx, vy = d / norm
            dist = self._dist_to_line(pts, vx, vy, p1[0], p1[1])
            inl = dist < thr
            c = int(inl.sum())
            if c > best_count:
                best_count = c
                best_inliers = inl
        if best_inliers is None or best_count < 2:
            return self._fit_l2(pts) + (n,)
        vx, vy, x0, y0 = self._fit_l2(pts[best_inliers])  # refine on consensus
        return vx, vy, x0, y0, best_count

    def process(self, inputs, params):
        edges = inputs.get('image')
        if edges is None:
            return {'main': None, 'inliers': 0, 'angle': 0.0, 'n_points': 0}

        pts = self._points(edges)
        H, W = (edges.shape[:2])
        base = edges if edges.ndim == 3 else cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        overlay = base.copy()

        if len(pts) < 2:
            return {'main': overlay, 'inliers': 0, 'angle': 0.0, 'n_points': int(len(pts))}

        mode = int(params.get('mode', 0))
        thr  = float(params.get('threshold', 3.0))
        iters = int(params.get('iterations', 200))

        if mode == 0:
            vx, vy, x0, y0, inliers = self._ransac(pts, thr, iters)
        else:
            vx, vy, x0, y0 = self._fit_l2(pts)
            dist = self._dist_to_line(pts, vx, vy, x0, y0)
            inliers = int((dist < thr).sum())

        # Extend line across the image and draw it
        t = max(H, W)
        p_a = (int(round(x0 - vx * t)), int(round(y0 - vy * t)))
        p_b = (int(round(x0 + vx * t)), int(round(y0 + vy * t)))
        cv2.line(overlay, p_a, p_b, (0, 220, 0), 2, cv2.LINE_AA)

        angle = float(np.degrees(np.arctan2(vy, vx)))
        label = f'{["RANSAC","L2"][mode]}  inliers={inliers}/{len(pts)}  angle={angle:.1f}'
        cv2.putText(overlay, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(overlay, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1, cv2.LINE_AA)

        return {
            'main':     overlay,
            'inliers':  int(inliers),
            'angle':    round(angle, 2),
            'n_points': int(len(pts)),
        }
