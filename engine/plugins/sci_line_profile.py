import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='sci_line_profile',
    label='Line Profile',
    category=['analysis', 'scientific'],
    icon='Activity',
    description="Extract intensity profile along a line segment. Fundamental in microscopy, spectroscopy, and materials analysis.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main',    'color': 'image', 'label': 'Image + Line'},
        {'id': 'chart',   'color': 'image', 'label': 'Profile Chart'},
        {'id': 'profile', 'color': 'data',  'label': 'Profile Values'},
    ],
    params=[
        {'id': 'x1',         'label': 'X1 (%)',         'type': 'float', 'default': 10.0, 'min': 0.0, 'max': 100.0},
        {'id': 'y1',         'label': 'Y1 (%)',         'type': 'float', 'default': 50.0, 'min': 0.0, 'max': 100.0},
        {'id': 'x2',         'label': 'X2 (%)',         'type': 'float', 'default': 90.0, 'min': 0.0, 'max': 100.0},
        {'id': 'y2',         'label': 'Y2 (%)',         'type': 'float', 'default': 50.0, 'min': 0.0, 'max': 100.0},
        {'id': 'samples',    'label': 'Samples',        'type': 'int',   'default': 256,  'min': 16,  'max': 1024},
        {'id': 'line_width', 'label': 'Avg Width (px)', 'type': 'int',   'default': 1,    'min': 1,   'max': 21},
        {'id': 'channel',    'label': 'Channel',        'type': 'enum',  'options': ['Luminance', 'Red', 'Green', 'Blue'], 'default': 0},
    ],
    resizable=True, min_width=250, min_height=150
)
class LineProfileNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'chart': None, 'profile': None}

        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)

        ih, iw = img.shape[:2]
        px1 = int(float(params.get('x1', 10.0)) / 100.0 * iw)
        py1 = int(float(params.get('y1', 50.0)) / 100.0 * ih)
        px2 = int(float(params.get('x2', 90.0)) / 100.0 * iw)
        py2 = int(float(params.get('y2', 50.0)) / 100.0 * ih)

        n       = int(params.get('samples', 256))
        lw      = int(params.get('line_width', 1))
        chan    = int(params.get('channel', 0))

        is_color = len(img.shape) == 3 and img.shape[2] == 3
        if not is_color:
            gray = img
        elif chan == 0:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif chan == 1:
            gray = img[:, :, 2]
        elif chan == 2:
            gray = img[:, :, 1]
        else:
            gray = img[:, :, 0]

        xs = np.linspace(px1, px2, n, dtype=np.float32)
        ys = np.linspace(py1, py2, n, dtype=np.float32)

        gray_f = gray.astype(np.float32)

        if lw <= 1:
            map_x = xs.reshape(1, -1)
            map_y = ys.reshape(1, -1)
            profile = cv2.remap(gray_f, map_x, map_y, cv2.INTER_LINEAR)[0].astype(float)
        else:
            dx = float(px2 - px1)
            dy = float(py2 - py1)
            length = max(np.sqrt(dx**2 + dy**2), 1e-6)
            nx, ny = -dy / length, dx / length
            offsets = np.linspace(-(lw - 1) / 2.0, (lw - 1) / 2.0, lw)
            strips = []
            for off in offsets:
                mx = (xs + nx * off).reshape(1, -1).astype(np.float32)
                my = (ys + ny * off).reshape(1, -1).astype(np.float32)
                strips.append(cv2.remap(gray_f, mx, my, cv2.INTER_LINEAR)[0])
            profile = np.mean(strips, axis=0).astype(float)

        out = img.copy()
        if len(out.shape) == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        cv2.line(out, (px1, py1), (px2, py2), (0, 255, 100), 1, cv2.LINE_AA)
        cv2.circle(out, (px1, py1), 4, (0, 200, 255), -1)
        cv2.circle(out, (px2, py2), 4, (255, 100, 0), -1)

        cw = int(params.get('width', 400))
        ch = int(params.get('height', 200))
        chart = np.full((ch, cw, 3), 18, dtype=np.uint8)
        for i in range(1, 4):
            cv2.line(chart, (int(cw * i / 4), 0), (int(cw * i / 4), ch), (40, 40, 40), 1)
            cv2.line(chart, (0, int(ch * i / 4)), (cw, int(ch * i / 4)), (40, 40, 40), 1)

        p_min, p_max = float(profile.min()), float(profile.max())
        if p_max <= p_min:
            p_max = p_min + 1.0
        pad = 12
        norm_p = ((profile - p_min) / (p_max - p_min) * (ch - 2 * pad)).astype(int)
        pts = np.array([[int(i / len(norm_p) * cw), ch - pad - v] for i, v in enumerate(norm_p)], dtype=np.int32)
        cv2.polylines(chart, [pts], False, (0, 255, 100), 1, cv2.LINE_AA)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(chart, f"{p_max:.1f}", (4, 14),      font, 0.38, (160, 160, 160), 1)
        cv2.putText(chart, f"{p_min:.1f}", (4, ch - 4),  font, 0.38, (160, 160, 160), 1)

        return {'main': out, 'chart': chart, 'profile': profile.tolist()}
