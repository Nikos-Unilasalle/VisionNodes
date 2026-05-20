import base64
import json

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_DEFAULT_CLASSES = json.dumps([
    {"label": "Water",      "value": -0.50, "color": "#2196f3"},
    {"label": "Bare Soil",  "value":  0.10, "color": "#ff9800"},
    {"label": "Sparse Veg", "value":  0.40, "color": "#8bc34a"},
    {"label": "Dense Veg",  "value":  0.80, "color": "#2e7d32"},
    {"label": "Urban",      "value": -0.10, "color": "#9e9e9e"},
])

_COLORMAPS = [
    ('RdYlGn',  None),
    ('Viridis',  cv2.COLORMAP_VIRIDIS),
    ('Inferno',  cv2.COLORMAP_INFERNO),
    ('Plasma',   cv2.COLORMAP_PLASMA),
    ('Jet',      cv2.COLORMAP_JET),
    ('Turbo',    cv2.COLORMAP_TURBO),
    ('Gray',     -1),
]
_CM_NAMES = [c[0] for c in _COLORMAPS]


def _rdylgn_lut() -> np.ndarray:
    """Red-Yellow-Green LUT for NDVI-style maps."""
    lut = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        if t < 0.5:
            r, g, b = 220, int(440 * t), 30
        else:
            r, g, b = max(0, int(440 * (1.0 - t))), 200, 30
        lut[i] = [b, g, r]  # BGR
    return lut


_RDYLGN = _rdylgn_lut().reshape((256, 1, 3))


def _apply_colormap(gray8: np.ndarray, cmap_code) -> np.ndarray:
    if cmap_code is None:
        img3 = cv2.cvtColor(gray8, cv2.COLOR_GRAY2BGR)
        return cv2.LUT(img3, _RDYLGN)
    if cmap_code == -1:
        return cv2.cvtColor(gray8, cv2.COLOR_GRAY2BGR)
    return cv2.applyColorMap(gray8, cmap_code)


@vision_node(
    type_id='sci_index_painter',
    label='Index Painter',
    category='measure',
    icon='Palette',
    description=(
        "Interactive scientific index map painter. Draw regions on a blank canvas and assign "
        "a float scalar value to each class. Output is float32 compatible with sci_colormap, "
        "sci_roi_stats, and spectral index nodes. "
        "Default classes map to NDVI semantics (−1…+1). Use for ground truth generation, "
        "synthetic spectral maps, weight maps, and ROI seeding."
    ),
    inputs=[],
    outputs=[
        {'id': 'index',  'color': 'image', 'label': 'Index (float32)'},
        {'id': 'labels', 'color': 'markers', 'label': 'Labels (uint8)'},
    ],
    params=[
        {'id': 'classes',  'label': 'Classes',  'type': 'string', 'default': _DEFAULT_CLASSES},
        {'id': 'strokes',  'label': 'Strokes',  'type': 'string', 'default': '[]'},
        {'id': 'width',    'label': 'Width',    'type': 'int',    'default': 512, 'min': 64, 'max': 2048},
        {'id': 'height',   'label': 'Height',   'type': 'int',    'default': 512, 'min': 64, 'max': 2048},
        {'id': 'bg_value', 'label': 'BG Value', 'type': 'float',  'default': 0.0, 'min': -2.0, 'max': 2.0, 'step': 0.01},
        {'id': 'colormap', 'label': 'Colormap', 'type': 'enum',   'options': _CM_NAMES, 'default': 0},
    ]
)
class IndexPainterNode(NodeProcessor):
    def process(self, inputs, params):
        w  = int(params.get('width',    512))
        h  = int(params.get('height',   512))
        bg = float(params.get('bg_value', 0.0))

        try:
            classes = json.loads(params.get('classes', '[]') or '[]')
        except Exception:
            classes = []

        try:
            strokes = json.loads(params.get('strokes', '[]') or '[]')
        except Exception:
            strokes = []

        index  = np.full((h, w), bg, dtype=np.float32)
        labels = np.zeros((h, w), dtype=np.uint8)

        for stroke in strokes:
            class_idx = int(stroke.get('class_idx', 0))
            if class_idx >= len(classes):
                continue
            cls       = classes[class_idx]
            value     = float(cls.get('value', 0.0))
            radius    = max(1, int(float(stroke.get('radius', 0.03)) * min(w, h)))
            pts       = stroke.get('pts', [])
            label_val = class_idx + 1  # 0 = background

            for i, pt in enumerate(pts):
                cx = int(float(pt[0]) * w)
                cy = int(float(pt[1]) * h)
                cv2.circle(index,  (cx, cy), radius, float(value),     -1)
                cv2.circle(labels, (cx, cy), radius, int(label_val),   -1)
                if i > 0:
                    prev = pts[i - 1]
                    px = int(float(prev[0]) * w)
                    py = int(float(prev[1]) * h)
                    cv2.line(index,  (px, py), (cx, cy), float(value),   radius * 2)
                    cv2.line(labels, (px, py), (cx, cy), int(label_val), radius * 2)

        # Colormap preview
        idx_min, idx_max = float(index.min()), float(index.max())
        span = idx_max - idx_min
        if span > 0.0:
            norm8 = ((index - idx_min) / span * 255.0).clip(0, 255).astype(np.uint8)
        else:
            norm8 = np.zeros((h, w), dtype=np.uint8)

        cm_param = params.get('colormap', 0)
        if isinstance(cm_param, str):
            if cm_param in _CM_NAMES:
                cm_idx = _CM_NAMES.index(cm_param)
            else:
                try:
                    cm_idx = int(cm_param)
                except ValueError:
                    cm_idx = 0
        else:
            cm_idx = int(cm_param)
        cm_code = _COLORMAPS[cm_idx][1] if cm_idx < len(_COLORMAPS) else None
        preview = _apply_colormap(norm8, cm_code)

        _, buf = cv2.imencode('.jpg', preview, [cv2.IMWRITE_JPEG_QUALITY, 80])
        main_preview = base64.b64encode(buf).decode('utf-8')

        return {
            'index':        index,
            'labels':       labels,
            'main_preview': main_preview,
        }
