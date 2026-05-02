import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_COLORMAPS = [
    ('Viridis',  cv2.COLORMAP_VIRIDIS),
    ('Plasma',   cv2.COLORMAP_PLASMA),
    ('Inferno',  cv2.COLORMAP_INFERNO),
    ('Magma',    cv2.COLORMAP_MAGMA),
    ('Turbo',    cv2.COLORMAP_TURBO),
    ('Jet',      cv2.COLORMAP_JET),
    ('Hot',      cv2.COLORMAP_HOT),
    ('Cool',     cv2.COLORMAP_COOL),
    ('Parula',   cv2.COLORMAP_PARULA),
    ('Cividis',  cv2.COLORMAP_CIVIDIS),
    ('Rainbow',  cv2.COLORMAP_RAINBOW),
    ('Ocean',    cv2.COLORMAP_OCEAN),
]
_NAMES = [n for n, _ in _COLORMAPS]
_IDS   = [i for _, i in _COLORMAPS]

@vision_node(
    type_id='sci_colormap',
    label='Colormap / LUT',
    category=['visualize', 'scientific'],
    icon='Palette',
    description="Apply scientific colormap (LUT) to grayscale image. Converts intensity to false color for visualization.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'colormap',   'label': 'Colormap',   'type': 'enum',  'options': _NAMES, 'default': 0},
        {'id': 'auto_range', 'label': 'Auto Range',  'type': 'bool',  'default': True},
        {'id': 'in_min',     'label': 'Input Min',   'type': 'float', 'default': 0.0,   'min': 0.0, 'max': 65535.0},
        {'id': 'in_max',     'label': 'Input Max',   'type': 'float', 'default': 255.0, 'min': 0.0, 'max': 65535.0},
        {'id': 'invert',     'label': 'Invert LUT',  'type': 'bool',  'default': False},
    ]
)
class ColormapNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        cmap_id = _IDS[int(params.get('colormap', 0))]
        auto    = bool(params.get('auto_range', True))
        invert  = bool(params.get('invert', False))

        src = img.astype(np.float32)

        if len(src.shape) == 3 and src.shape[2] == 3:
            tmp = src.clip(0, 255).astype(np.uint8)
            gray = cv2.cvtColor(tmp, cv2.COLOR_BGR2GRAY).astype(np.float32)
        else:
            gray = src

        if auto:
            lo, hi = float(gray.min()), float(gray.max())
        else:
            lo = float(params.get('in_min', 0.0))
            hi = float(params.get('in_max', 255.0))

        if hi <= lo:
            hi = lo + 1.0

        norm = ((gray - lo) / (hi - lo) * 255).clip(0, 255).astype(np.uint8)
        if invert:
            norm = 255 - norm

        return {'main': cv2.applyColorMap(norm, cmap_id)}
