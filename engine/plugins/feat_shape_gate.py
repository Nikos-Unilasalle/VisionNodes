import base64
import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _to_uint8_bgr(img) -> np.ndarray:
    if not isinstance(img, np.ndarray):
        return np.zeros((64, 64, 3), dtype=np.uint8)
    if img.dtype != np.uint8:
        if img.dtype in (np.float32, np.float64):
            img = (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8) if float(img.max()) <= 1.0 \
                  else np.clip(img, 0, 255).astype(np.uint8)
        else:
            img = np.clip(img, 0, 255).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


@vision_node(
    type_id='feat_shape_gate',
    label='Shape Gate',
    category='segmentation',
    icon='Circle',
    description=(
        'Filters connected regions by shape compactness.\n\n'
        'Aspect Ratio: min(w,h)/max(w,h) from bounding box — 1.0=square, '
        'low=elongated. Keeps round/compact blobs.\n\n'
        'Circularity: 4π·area/perimeter² — 1.0=perfect circle, '
        'low=irregular or hollow (rings, stars…). Independent of scale.\n\n'
        'Both filters are AND-combined. Disable either to use only one.\n'
        'Preview: natural colors=kept, dimmed=rejected, bounding box colored.'
    ),
    resizable=True,
    min_width=240,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'mask',  'label': 'Mask',  'color': 'mask'},
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'mask_kept', 'label': 'Kept Mask',     'color': 'mask'},
        {'id': 'mask_rej',  'label': 'Rejected Mask', 'color': 'mask'},
        {'id': 'main',      'label': 'Preview',       'color': 'image'},
        {'id': 'count',     'label': 'Count',         'color': 'scalar'},
    ],
    params=[
        {'id': 'use_aspect',      'label': 'Aspect Ratio Filter',  'type': 'bool',
         'default': True},
        {'id': 'min_aspect',      'label': 'Min Aspect (W/H)',     'type': 'float',
         'default': 0.6, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'use_circularity', 'label': 'Circularity Filter',   'type': 'bool',
         'default': True},
        {'id': 'min_circularity', 'label': 'Min Circularity',      'type': 'float',
         'default': 0.35, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'min_size',        'label': 'Min Size (px²)',        'type': 'int',
         'default': 20, 'min': 1, 'max': 50000},
    ],
)
class ShapeGateNode(NodeProcessor):
    def __init__(self):
        self._last_preview: str | None = None
        self._frame_count = 0

    def process(self, inputs, params):
        mask_in = inputs.get('mask')
        raw_img = inputs.get('image')
        img = raw_img if isinstance(raw_img, np.ndarray) else None

        def _passthrough():
            return {
                'mask_kept': None, 'mask_rej': None,
                'main': img, 'main_preview': self._last_preview, 'count': 0,
            }

        if mask_in is None:
            return _passthrough()

        if not isinstance(mask_in, np.ndarray):
            return _passthrough()

        # Ensure single-channel binary
        m = mask_in
        if m.ndim == 3:
            m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.shape[2] == 3 else m[..., 0]
        binary = (m > 0).astype(np.uint8)

        h, w = binary.shape[:2]

        # Params
        use_ar   = bool(params.get('use_aspect',      True))
        min_ar   = float(params.get('min_aspect',     0.6))
        use_circ = bool(params.get('use_circularity', True))
        min_circ = float(params.get('min_circularity', 0.35))
        min_size = int(params.get('min_size', 20))

        # Label components
        n_labels, labels = cv2.connectedComponents(binary, connectivity=8)

        mask_kept = np.zeros((h, w), dtype=np.uint8)
        mask_rej  = np.zeros((h, w), dtype=np.uint8)

        # Per-component info for preview bboxes
        component_info = []  # (x, y, bw, bh, kept, ar, circ)
        kept = 0

        for lbl in range(1, n_labels):
            comp = (labels == lbl).astype(np.uint8)
            area = float(np.sum(comp))
            if area < min_size:
                continue

            # Aspect ratio from bounding box
            x, y, bw, bh = cv2.boundingRect(comp)
            ar = min(bw, bh) / max(bw, bh, 1)

            # Circularity via outer contour
            cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            circ = 0.0
            if cnts:
                perim = cv2.arcLength(cnts[0], True)
                if perim > 0:
                    circ = min(1.0, (4.0 * np.pi * area) / (perim * perim))

            passes = (not use_ar or ar >= min_ar) and (not use_circ or circ >= min_circ)

            pixel_mask = comp.astype(bool)
            if passes:
                mask_kept[pixel_mask] = 255
                kept += 1
            else:
                mask_rej[pixel_mask] = 255

            component_info.append((x, y, bw, bh, passes, ar, circ))

        # ── Preview ──
        if img is not None:
            base = _to_uint8_bgr(img)
            if base.shape[:2] != (h, w):
                base = cv2.resize(base, (w, h))
        else:
            base = np.zeros((h, w, 3), dtype=np.uint8)
            base[mask_kept > 0] = (60, 200, 60)
            base[mask_rej  > 0] = (60,  60, 200)

        preview = base.copy()

        # Dim rejected pixels
        rej_px = mask_rej > 0
        if np.any(rej_px):
            preview[rej_px] = (preview[rej_px].astype(np.float32) * 0.25).clip(0, 255).astype(np.uint8)

        # Draw bounding boxes + metric labels
        for (x, y, bw, bh, passes, ar, circ) in component_info:
            color = (0, 220, 80) if passes else (60, 60, 255)
            cv2.rectangle(preview, (x, y), (x + bw, y + bh), color, 1)
            label_parts = []
            if use_ar:
                label_parts.append(f'ar={ar:.2f}')
            if use_circ:
                label_parts.append(f'c={circ:.2f}')
            if label_parts:
                cv2.putText(
                    preview, ' '.join(label_parts),
                    (x, max(y - 4, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA,
                )

        cv2.putText(
            preview, f'kept: {kept}',
            (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
        )

        # Periodic preview compression
        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                ph = min(360, preview.shape[0])
                pw = int(ph * preview.shape[1] / preview.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview, (pw, ph)),
                                     [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'mask_kept':    mask_kept,
            'mask_rej':     mask_rej,
            'main':         preview,
            'main_preview': self._last_preview,
            'count':        float(kept),
        }
