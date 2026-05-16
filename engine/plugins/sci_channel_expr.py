import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_DEFAULT_EXPR = 'B * 0.5 + R * 0.3 - G * 0.8'

_SAFE_NS = {
    'np': np,
    'abs': np.abs,
    'sqrt': np.sqrt,
    'clip': np.clip,
    'log': np.log,
    'exp': np.exp,
    'sin': np.sin,
    'cos': np.cos,
    'min': np.minimum,
    'max': np.maximum,
    'mean': np.mean,
    'std': np.std,
    'pi': np.pi,
}


@vision_node(
    type_id='sci_channel_expr',
    label='Channel Formula',
    category='color',
    icon='Calculator',
    description=(
        'Computes a per-pixel expression on image channels, outputting a float32 grayscale result.\n\n'
        'Available variables: R, G, B (0–255 float), H, S, V (HSV 0–255 float), '
        'L, A_lab, B_lab (LAB channels).\n\n'
        'Math: abs, sqrt, clip, log, exp, sin, cos, min, max, mean, std, np, pi.\n\n'
        'Examples:\n'
        '  B*0.5 + R*0.3 - G*0.8      (purple stain score)\n'
        '  (R - G) / (R + G + 1e-6)   (red vs green index)\n'
        '  clip(V - S*0.5, 0, 255)     (brightness minus saturation)'
    ),
    resizable=True,
    min_width=280,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'image', 'label': 'Image (BGR)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'result',    'label': 'Result (float)', 'color': 'any'},
        {'id': 'visualized','label': 'Visualized',     'color': 'image'},
    ],
    params=[
        {'id': 'expression','label': 'Expression',    'type': 'code',  'default': _DEFAULT_EXPR},
        {'id': 'normalize', 'label': 'Normalize 0-255','type': 'bool', 'default': True},
        {'id': 'colormap',  'label': 'Colormap',      'type': 'enum',
         'options': ['Gray', 'Viridis', 'Plasma', 'Hot', 'Jet', 'Turbo'], 'default': 0},
        {'id': 'clamp_min', 'label': 'Clamp Min',     'type': 'float', 'default': -1e9, 'min': -1e9, 'max': 0.0},
        {'id': 'clamp_max', 'label': 'Clamp Max',     'type': 'float', 'default':  1e9, 'min': 0.0,  'max': 1e9},
    ],
)
class ChannelExprNode(NodeProcessor):
    _CMAPS = [None, cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_PLASMA,
              cv2.COLORMAP_HOT, cv2.COLORMAP_JET, cv2.COLORMAP_TURBO]

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'result': None, 'visualized': None}

        src = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        f   = src.astype(np.float32)

        b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]  # noqa: E741

        hsv_f = cv2.cvtColor(src, cv2.COLOR_BGR2HSV).astype(np.float32)
        H, S, V = hsv_f[:, :, 0], hsv_f[:, :, 1], hsv_f[:, :, 2]

        lab_f = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
        L, A_lab, B_lab = lab_f[:, :, 0], lab_f[:, :, 1], lab_f[:, :, 2]

        # Uppercase aliases for usability
        ns = dict(_SAFE_NS)
        ns.update({'R': r, 'G': g, 'B': b,
                   'H': H, 'S': S, 'V': V,
                   'L': L, 'A_lab': A_lab, 'B_lab': B_lab})

        expr = str(params.get('expression', _DEFAULT_EXPR)).strip()
        try:
            result = eval(expr, {"__builtins__": {}}, ns)  # noqa: S307
            result = np.asarray(result, dtype=np.float32)
            if result.shape != src.shape[:2]:
                result = np.broadcast_to(result, src.shape[:2]).copy()
        except Exception as e:
            h_img, w_img = src.shape[:2]
            result = np.zeros((h_img, w_img), dtype=np.float32)
            cv2.putText(src.copy(), f'Expr error: {e}', (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 50, 230), 1)

        cmin = float(params.get('clamp_min', -1e9))
        cmax = float(params.get('clamp_max',  1e9))
        if cmin > -1e8 or cmax < 1e8:
            result = np.clip(result, cmin, cmax)

        do_norm  = bool(params.get('normalize', True))
        cmap_idx = int(params.get('colormap', 0))
        cmap_id  = self._CMAPS[cmap_idx] if 0 <= cmap_idx < len(self._CMAPS) else None

        if do_norm:
            lo, hi = float(result.min()), float(result.max())
            vis_u8 = ((result - lo) / (hi - lo + 1e-10) * 255).astype(np.uint8) if hi > lo else np.zeros_like(result, dtype=np.uint8)
        else:
            vis_u8 = np.clip(result, 0, 255).astype(np.uint8)

        if cmap_id is not None:
            visualized = cv2.applyColorMap(vis_u8, cmap_id)
        else:
            visualized = cv2.cvtColor(vis_u8, cv2.COLOR_GRAY2BGR)

        return {'result': result, 'visualized': visualized}
