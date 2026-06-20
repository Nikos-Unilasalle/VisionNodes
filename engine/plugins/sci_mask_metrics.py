import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_mask_metrics',
    label='Mask Metrics',
    category='measure',
    icon='Target',
    description=(
        "Compares a predicted binary mask to a ground-truth mask (ch4).\n\n"
        "Outputs IoU (Jaccard), Dice (F1-pixel), Precision, Recall, F1, "
        "and raw VP / FP / FN counts.\n\n"
        "Colored overlay: green=VP, red=FP, blue=FN — reveals immediately "
        "whether the error leans toward over- or under-segmentation.\n"
        "IoU = VP/(VP+FP+FN) — doubly penalises both over and under-segmentation.\n"
        "Dice = 2·VP/(2·VP+FP+FN) — always ≥ IoU; same ranking, more forgiving.\n"
        "Precision = VP/(VP+FP), Recall = VP/(VP+FN), F1 = harmonic mean."
    ),
    inputs=[
        {'id': 'pred',  'label': 'Prediction', 'color': 'mask'},
        {'id': 'truth', 'label': 'Ground Truth', 'color': 'mask'},
        {'id': 'image', 'label': 'BG Image (opt)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Overlay',   'color': 'image'},
        {'id': 'data', 'label': 'Metrics',   'color': 'dict'},
        {'id': 'iou',  'label': 'IoU',       'color': 'scalar'},
        {'id': 'dice', 'label': 'Dice',      'color': 'scalar'},
    ],
    params=[
        {'id': 'show_overlay', 'label': 'Show Overlay',      'type': 'bool', 'default': True},
        {'id': 'alpha',        'label': 'Overlay Alpha',     'type': 'float',
         'default': 0.45, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'iou_thresh',   'label': 'IoU Threshold (VP)', 'type': 'float',
         'default': 0.5, 'min': 0.0, 'max': 1.0, 'step': 0.05},
    ]
)
class MaskMetricsNode(NodeProcessor):

    @staticmethod
    def _to_binary(mask: np.ndarray) -> np.ndarray:
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        return (mask > 127).astype(bool)

    def process(self, inputs, params):
        pred  = inputs.get('pred')
        truth = inputs.get('truth')

        if pred is None or truth is None:
            return {'main': None, 'data': None, 'iou': 0.0, 'dice': 0.0}

        bin_pred  = self._to_binary(pred)
        bin_truth = self._to_binary(truth)

        # Align sizes
        if bin_pred.shape != bin_truth.shape:
            h = max(bin_pred.shape[0], bin_truth.shape[0])
            w = max(bin_pred.shape[1], bin_truth.shape[1])
            bin_pred  = cv2.resize(bin_pred.astype(np.uint8),  (w, h),
                                   interpolation=cv2.INTER_NEAREST).astype(bool)
            bin_truth = cv2.resize(bin_truth.astype(np.uint8), (w, h),
                                   interpolation=cv2.INTER_NEAREST).astype(bool)

        H, W = bin_pred.shape

        vp = int(np.sum(bin_pred  & bin_truth))
        fp = int(np.sum(bin_pred  & ~bin_truth))
        fn = int(np.sum(~bin_pred & bin_truth))

        iou       = vp / (vp + fp + fn) if (vp + fp + fn) > 0 else 0.0
        dice      = 2 * vp / (2 * vp + fp + fn) if (2 * vp + fp + fn) > 0 else 0.0
        precision = vp / (vp + fp) if (vp + fp) > 0 else 0.0
        recall    = vp / (vp + fn) if (vp + fn) > 0 else 0.0
        f1        = 2 * precision * recall / (precision + recall) \
                    if (precision + recall) > 0 else 0.0

        # ── Overlay ──────────────────────────────────────────────────────────
        show    = bool(params.get('show_overlay', True))
        alpha   = float(params.get('alpha', 0.45))
        bg_img  = inputs.get('image')

        if bg_img is not None and isinstance(bg_img, np.ndarray):
            base = bg_img.copy()
            if base.ndim == 2:
                base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
            if base.shape[:2] != (H, W):
                base = cv2.resize(base, (W, H))
        else:
            base = np.zeros((H, W, 3), dtype=np.uint8)

        overlay = base.copy()

        if show:
            color_layer = base.copy()
            # VP: green, FP: red, FN: blue
            color_layer[bin_pred  & bin_truth]  = (0,   200, 0)
            color_layer[bin_pred  & ~bin_truth] = (0,   0,   220)
            color_layer[~bin_pred & bin_truth]  = (200, 0,   0)
            overlay = cv2.addWeighted(base, 1 - alpha, color_layer, alpha, 0)

        # Draw text HUD
        lines = [
            f'IoU={iou:.3f}  Dice={dice:.3f}',
            f'P={precision:.3f}  R={recall:.3f}  F1={f1:.3f}',
            f'VP={vp}  FP={fp}  FN={fn}',
        ]
        for i, line in enumerate(lines):
            cv2.putText(overlay, line, (8, 22 + i * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # Legend
        cv2.putText(overlay, 'VP', (8,  H - 38), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (0, 200, 0),   1, cv2.LINE_AA)
        cv2.putText(overlay, 'FP', (32, H - 38), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (0, 0, 220),   1, cv2.LINE_AA)
        cv2.putText(overlay, 'FN', (56, H - 38), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (200, 0, 0),   1, cv2.LINE_AA)

        return {
            'main': overlay,
            'data': {
                'iou':       round(iou,       4),
                'dice':      round(dice,      4),
                'precision': round(precision, 4),
                'recall':    round(recall,    4),
                'f1':        round(f1,        4),
                'vp':        vp,
                'fp':        fp,
                'fn':        fn,
            },
            'iou':  round(iou,  4),
            'dice': round(dice, 4),
        }
