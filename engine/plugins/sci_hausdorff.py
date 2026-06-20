import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_hausdorff',
    label='Hausdorff Distance',
    category='measure',
    icon='ArrowLeftRight',
    description=(
        "Hausdorff distance between two binary masks (ch3 §3.6).\n\n"
        "H(A,B) = max(h(A→B), h(B→A)) — worst-case mismatch.\n"
        "h(A→B) = max_{a∈A} min_{b∈B} d(a,b) — directed Hausdorff.\n\n"
        "Percentile < 100 gives Modified Hausdorff / HD95 (robust to outliers).\n"
        "Uses distance transform (fast O(N)) instead of brute-force O(N²).\n"
        "Overlay: A=cyan, B=orange, worst-case pair connected by red line."
    ),
    inputs=[
        {'id': 'mask_a', 'label': 'Mask A', 'color': 'mask'},
        {'id': 'mask_b', 'label': 'Mask B', 'color': 'mask'},
        {'id': 'image',  'label': 'BG Image (opt)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',    'label': 'Overlay',    'color': 'image'},
        {'id': 'h_ab',    'label': 'H(A→B)',     'color': 'scalar'},
        {'id': 'h_ba',    'label': 'H(B→A)',     'color': 'scalar'},
        {'id': 'h_max',   'label': 'H max',      'color': 'scalar'},
    ],
    params=[
        {'id': 'percentile', 'label': 'Percentile (100=classic, 95=HD95)',
         'type': 'float', 'default': 100.0, 'min': 50.0, 'max': 100.0, 'step': 1.0},
        {'id': 'draw_arrow', 'label': 'Draw Worst-Case Arrow', 'type': 'bool',
         'default': True},
    ]
)
class HausdorffDistanceNode(NodeProcessor):

    @staticmethod
    def _to_binary(mask: np.ndarray) -> np.ndarray:
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        return (mask > 127).astype(np.uint8)

    @staticmethod
    def _directed_hausdorff(pts_from: np.ndarray, dist_transform: np.ndarray,
                             percentile: float):
        """For each point in pts_from, read its distance to set B via dist_transform."""
        if len(pts_from) == 0:
            return 0.0, None
        dists = dist_transform[pts_from[:, 0], pts_from[:, 1]]
        pct_dist = float(np.percentile(dists, percentile))
        # Worst-case point (for arrow overlay)
        worst_idx = int(np.argmin(np.abs(dists - pct_dist)))
        worst_pt = (pts_from[worst_idx, 1], pts_from[worst_idx, 0])  # (x, y)
        return pct_dist, worst_pt

    def process(self, inputs, params):
        mask_a = inputs.get('mask_a')
        mask_b = inputs.get('mask_b')
        if mask_a is None or mask_b is None:
            return {'main': None, 'h_ab': 0.0, 'h_ba': 0.0, 'h_max': 0.0}

        percentile = float(params.get('percentile', 100.0))
        draw_arrow = bool(params.get('draw_arrow', True))

        bin_a = self._to_binary(mask_a)
        bin_b = self._to_binary(mask_b)

        # Align sizes
        H = max(bin_a.shape[0], bin_b.shape[0])
        W = max(bin_a.shape[1], bin_b.shape[1])
        if bin_a.shape != (H, W):
            bin_a = cv2.resize(bin_a, (W, H), interpolation=cv2.INTER_NEAREST)
        if bin_b.shape != (H, W):
            bin_b = cv2.resize(bin_b, (W, H), interpolation=cv2.INTER_NEAREST)

        # Distance transforms
        not_b = (1 - bin_b).astype(np.uint8)
        not_a = (1 - bin_a).astype(np.uint8)
        dist_to_b = cv2.distanceTransform(not_b, cv2.DIST_L2, 5)
        dist_to_a = cv2.distanceTransform(not_a, cv2.DIST_L2, 5)

        pts_a = np.argwhere(bin_a > 0)  # rows (y,x) in numpy order
        pts_b = np.argwhere(bin_b > 0)

        h_ab, worst_a = self._directed_hausdorff(pts_a, dist_to_b, percentile)
        h_ba, worst_b = self._directed_hausdorff(pts_b, dist_to_a, percentile)
        h_max = max(h_ab, h_ba)

        # Overlay
        bg = inputs.get('image')
        if bg is not None and isinstance(bg, np.ndarray):
            overlay = bg.copy()
            if overlay.ndim == 2:
                overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2BGR)
            if overlay.shape[:2] != (H, W):
                overlay = cv2.resize(overlay, (W, H))
        else:
            overlay = np.zeros((H, W, 3), dtype=np.uint8)

        # Draw masks as colored contours
        cnts_a, _ = cv2.findContours(bin_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts_b, _ = cv2.findContours(bin_b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, cnts_a, -1, (200, 200, 0), 2)   # cyan-ish A
        cv2.drawContours(overlay, cnts_b, -1, (0, 140, 255), 2)   # orange B

        if draw_arrow and worst_a is not None and worst_b is not None:
            # Find nearest point in B to worst_a
            dist_val_a = dist_to_b[worst_a[1], worst_a[0]]
            # Find nearest B point by searching around worst_a
            y0, x0 = worst_a[1], worst_a[0]
            r = int(dist_val_a) + 2
            y1s = max(0, y0 - r)
            y2s = min(H, y0 + r + 1)
            x1s = max(0, x0 - r)
            x2s = min(W, x0 + r + 1)
            roi = bin_b[y1s:y2s, x1s:x2s]
            roi_pts = np.argwhere(roi > 0)
            if len(roi_pts) > 0:
                nearest = roi_pts[np.argmin(
                    np.sqrt((roi_pts[:, 0] - (y0 - y1s)) ** 2 +
                            (roi_pts[:, 1] - (x0 - x1s)) ** 2)
                )]
                nearest_xy = (nearest[1] + x1s, nearest[0] + y1s)
                cv2.arrowedLine(overlay, (x0, y0), nearest_xy, (0, 0, 220), 2,
                                cv2.LINE_AA, tipLength=0.15)

        label = f'H={h_max:.1f}px  A→B={h_ab:.1f}  B→A={h_ba:.1f}'
        if percentile < 100.0:
            label = f'HD{percentile:.0f}: ' + label
        cv2.putText(overlay, label, (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'A', (8, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 0), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'B', (22, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 255), 1, cv2.LINE_AA)

        return {
            'main':  overlay,
            'h_ab':  round(h_ab, 2),
            'h_ba':  round(h_ba, 2),
            'h_max': round(h_max, 2),
        }
