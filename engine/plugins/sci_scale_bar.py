import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_POSITIONS = ['Bottom Right', 'Bottom Left', 'Top Right', 'Top Left']

@vision_node(
    type_id='sci_scale_bar',
    label='Scale Bar',
    category=['visualize', 'scientific'],
    icon='Ruler',
    description="Overlay calibrated scale bar on image. Set Pixels/Unit to match your Unit Calibration node.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'pixels_per_unit', 'label': 'Pixels / Unit',      'type': 'float',  'default': 100.0, 'min': 0.1},
        {'id': 'bar_length',      'label': 'Bar Length (units)',  'type': 'float',  'default': 1.0,   'min': 0.01},
        {'id': 'unit_name',       'label': 'Unit Name',           'type': 'string', 'default': 'mm'},
        {'id': 'position',        'label': 'Position',            'type': 'enum',   'options': _POSITIONS, 'default': 0},
        {'id': 'color',           'label': 'Color',               'type': 'color',  'default': '#FFFFFF'},
        {'id': 'thickness',       'label': 'Thickness (px)',      'type': 'int',    'default': 3,  'min': 1, 'max': 10},
        {'id': 'margin',          'label': 'Margin (px)',         'type': 'int',    'default': 20, 'min': 5, 'max': 120},
    ]
)
class ScaleBarNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)

        out = img.copy()
        if len(out.shape) == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

        h, w = out.shape[:2]
        ppu        = max(float(params.get('pixels_per_unit', 100.0)), 0.001)
        bar_units  = float(params.get('bar_length', 1.0))
        bar_px     = int(ppu * bar_units)
        unit       = str(params.get('unit_name', 'mm'))
        pos_idx    = int(params.get('position', 0))
        thickness  = int(params.get('thickness', 3))
        margin     = int(params.get('margin', 20))

        color_hex = str(params.get('color') or '#FFFFFF').strip()
        if not color_hex.startswith('#'): color_hex = '#' + color_hex
        try:
            # Handle both #RRGGBB and #RGB formats
            if len(color_hex) == 7:
                r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
            elif len(color_hex) == 4:
                r, g, b = int(color_hex[1]*2, 16), int(color_hex[2]*2, 16), int(color_hex[3]*2, 16)
            else:
                raise ValueError("Invalid hex")
            color_bgr = (b, g, r)
        except Exception:
            color_bgr = (255, 255, 255)

        bar_px = max(10, min(bar_px, w - 2 * margin))
        label  = f"{bar_units:g} {unit}"
        font   = cv2.FONT_HERSHEY_SIMPLEX
        fscale = 0.5
        (tw, th), _ = cv2.getTextSize(label, font, fscale, 1)
        tick_h = thickness * 2

        if pos_idx == 0:   # Bottom Right
            x2 = w - margin;  y2 = h - margin;  x1 = x2 - bar_px
        elif pos_idx == 1: # Bottom Left
            x1 = margin;      y2 = h - margin;  x2 = x1 + bar_px
        elif pos_idx == 2: # Top Right
            x2 = w - margin;  y2 = margin + th + 10 + thickness;  x1 = x2 - bar_px
        else:              # Top Left
            x1 = margin;      y2 = margin + th + 10 + thickness;  x2 = x1 + bar_px

        cv2.line(out, (x1, y2), (x2, y2), color_bgr, thickness)
        cv2.line(out, (x1, y2 - tick_h), (x1, y2 + tick_h), color_bgr, thickness)
        cv2.line(out, (x2, y2 - tick_h), (x2, y2 + tick_h), color_bgr, thickness)

        tx = (x1 + x2) // 2 - tw // 2
        ty = y2 - tick_h - 4
        cv2.putText(out, label, (tx, ty), font, fscale, color_bgr, 1, cv2.LINE_AA)

        return {'main': out}
