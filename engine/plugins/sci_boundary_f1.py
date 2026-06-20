import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_boundary_f1',
    label='Boundary F1',
    category='measure',
    icon='Scan',
    description=(
        "Boundary F1 score (BF) between two binary masks (ch4 §4.6).\n\n"
        "Extracts contour pixels from both masks and computes precision/recall "
        "with a pixel tolerance: a predicted boundary pixel counts as correct "
        "if a ground-truth boundary pixel exists within the tolerance radius.\n\n"
        "P_c = boundary pred pixels near truth  / total pred boundary\n"
        "R_c = boundary truth pixels near pred  / total truth boundary\n"
        "BF  = 2·P_c·R_c / (P_c + R_c)\n\n"
        "BF complements Hausdorff: BF is a bounded proportion, Hausdorff "
        "reports the single worst-case mismatch.\n"
        "Overlay: cyan=pred boundary, orange=truth boundary, green=matched."
    ),
    inputs=[
        {'id': 'pred',  'label': 'Prediction',   'color': 'mask'},
        {'id': 'truth', 'label': 'Ground Truth',  'color': 'mask'},
        {'id': 'image', 'label': 'BG Image (opt)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',       'label': 'Overlay', 'color': 'image'},
        {'id': 'boundary_f1', 'label': 'BF',     'color': 'scalar'},
        {'id': 'precision',  'label': 'Boundary Precision', 'color': 'scalar'},
        {'id': 'recall',     'label': 'Boundary Recall',    'color': 'scalar'},
    ],
    params=[
        {'id': 'tolerance', 'label': 'Tolerance (px)', 'type': 'int',
         'default': 2, 'min': 1, 'max': 20},
    ]
)
class BoundaryF1Node(NodeProcessor):

    @staticmethod
    def _to_binary(mask: np.ndarray) -> np.ndarray:
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        return (mask > 127).astype(np.uint8)

    @staticmethod
    def _boundary_pixels(binary: np.ndarray) -> np.ndarray:
        """Extract boundary pixels via morphological erosion."""
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        eroded = cv2.erode(binary, kernel, iterations=1)
        return binary - eroded  # ring of boundary pixels

    @staticmethod
    def _match_ratio(boundary_from: np.ndarray, boundary_to: np.ndarray,
                     tol: int) -> float:
        """Fraction of 'from' boundary pixels within tol of 'to' boundary."""
        n_from = int(np.sum(boundary_from > 0))
        if n_from == 0:
            return 1.0  # nothing to match → perfect vacuously
        # Dilate 'to' by tolerance to create acceptance zone
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1))
        dilated_to = cv2.dilate(boundary_to, kernel, iterations=1)
        matched = int(np.sum((boundary_from > 0) & (dilated_to > 0)))
        return matched / n_from

    def process(self, inputs, params):
        pred  = inputs.get('pred')
        truth = inputs.get('truth')
        if pred is None or truth is None:
            return {'main': None, 'boundary_f1': 0.0, 'precision': 0.0, 'recall': 0.0}

        tol = int(params.get('tolerance', 2))

        bin_pred  = self._to_binary(pred)
        bin_truth = self._to_binary(truth)

        # Align sizes
        if bin_pred.shape != bin_truth.shape:
            h = max(bin_pred.shape[0], bin_truth.shape[0])
            w = max(bin_pred.shape[1], bin_truth.shape[1])
            bin_pred  = cv2.resize(bin_pred,  (w, h), interpolation=cv2.INTER_NEAREST)
            bin_truth = cv2.resize(bin_truth, (w, h), interpolation=cv2.INTER_NEAREST)

        H, W = bin_pred.shape

        bnd_pred  = self._boundary_pixels(bin_pred)
        bnd_truth = self._boundary_pixels(bin_truth)

        p_c = self._match_ratio(bnd_pred, bnd_truth, tol)
        r_c = self._match_ratio(bnd_truth, bnd_pred, tol)

        bf = 2 * p_c * r_c / (p_c + r_c) if (p_c + r_c) > 0 else 0.0

        # ── Overlay ──────────────────────────────────────────────────────────
        bg_img = inputs.get('image')
        if bg_img is not None and isinstance(bg_img, np.ndarray):
            base = bg_img.copy()
            if base.ndim == 2:
                base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
            if base.shape[:2] != (H, W):
                base = cv2.resize(base, (W, H))
        else:
            base = np.zeros((H, W, 3), dtype=np.uint8)

        overlay = base.copy()

        # Dilate truth for acceptance zone (to show matching)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1))
        dilated_truth = cv2.dilate(bnd_truth, kernel)

        # Matched pred boundary: pred bnd within truth zone
        matched_pred = (bnd_pred > 0) & (dilated_truth > 0)

        # Draw layers: truth=orange, pred=cyan, matched=green
        overlay[bnd_truth > 0] = (0, 140, 255)         # orange truth
        overlay[bnd_pred  > 0] = (200, 200, 0)         # cyan pred
        overlay[matched_pred]   = (0, 200, 0)           # green matched

        label = f'BF={bf:.3f}  P_c={p_c:.3f}  R_c={r_c:.3f}  tol={tol}px'
        cv2.putText(overlay, label, (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'pred', (8, H - 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 0), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'truth', (42, H - 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 140, 255), 1, cv2.LINE_AA)
        cv2.putText(overlay, 'match', (82, H - 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 200, 0), 1, cv2.LINE_AA)

        return {
            'main':         overlay,
            'boundary_f1':  round(bf,  4),
            'precision':    round(p_c, 4),
            'recall':       round(r_c, 4),
        }
