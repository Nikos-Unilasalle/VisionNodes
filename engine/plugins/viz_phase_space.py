"""
Phase Space visualization nodes.

- phase_space          : standalone 2D attractor / Lissajous plot for any pair of scalars
- imu_phase_dashboard  : 6-channel composite (Accel XY/XZ/YZ + Gyro XY/XZ/YZ)
                         designed for M5StickC Plus2 or any 6-DOF IMU
"""
from collections import deque

import cv2
import numpy as np

from registry import NodeProcessor, vision_node


# ─────────────────────────────────────────────────────────────────────────────
#  Shared cell renderer
# ─────────────────────────────────────────────────────────────────────────────

def _render_phase_cell(pts, w, h, bgr, title="", xl="X", yl="Y"):
    """Render one phase-space cell onto a (h, w, 3) uint8 image."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX

    if len(pts) < 2:
        cv2.putText(img, title, (8, 22), font, 0.46, (90, 90, 90), 1, cv2.LINE_AA)
        cv2.putText(img, "waiting…", (8, 44), font, 0.38, (60, 60, 60), 1, cv2.LINE_AA)
        return img

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    xpad = (xmax - xmin) * 0.12 or 0.05
    ypad = (ymax - ymin) * 0.12 or 0.05
    xmin -= xpad; xmax += xpad
    ymin -= ypad; ymax += ypad
    dx = xmax - xmin
    dy = ymax - ymin

    M = 30  # margin

    def to_px(xv, yv):
        px = M + int((xv - xmin) / dx * (w - 2 * M))
        py = h - M - int((yv - ymin) / dy * (h - 2 * M))
        return (max(0, min(w - 1, px)), max(0, min(h - 1, py)))

    # Grid
    for i in range(5):
        gx = M + int((w - 2 * M) * i / 4)
        gy = M + int((h - 2 * M) * i / 4)
        cv2.line(img, (gx, M), (gx, h - M), (20, 20, 20), 1)
        cv2.line(img, (M, gy), (w - M, gy), (20, 20, 20), 1)

    # Zero-axis highlights
    if xmin <= 0 <= xmax:
        zx, _ = to_px(0, ymin)
        cv2.line(img, (zx, M), (zx, h - M), (45, 45, 45), 1)
    if ymin <= 0 <= ymax:
        _, zy = to_px(xmin, 0)
        cv2.line(img, (M, zy), (w - M, zy), (45, 45, 45), 1)

    # Fading trail — nonlinear alpha: dim tail, bright head
    n = len(pts)
    for i in range(1, n):
        t = (i / n) ** 1.5
        col = tuple(int(c * t) for c in bgr)
        p1 = to_px(*pts[i - 1])
        p2 = to_px(*pts[i])
        thick = 2 if i > n - 5 else 1
        cv2.line(img, p1, p2, col, thick, cv2.LINE_AA)

    # Current-point glow + dot
    cx, cy = to_px(pts[-1][0], pts[-1][1])
    for rad, alp in ((10, 0.07), (7, 0.18), (4, 0.45)):
        cv2.circle(img, (cx, cy), rad, tuple(int(c * alp) for c in bgr), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 3, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 2, bgr, -1, cv2.LINE_AA)

    # Cell border (tinted)
    dim = tuple(int(c * 0.30) for c in bgr)
    cv2.rectangle(img, (M, M), (w - M, h - M), dim, 1)

    # Title
    lc = tuple(int(c * 0.72) for c in bgr)
    cv2.putText(img, title, (M, M - 7), font, 0.46, (195, 195, 195), 1, cv2.LINE_AA)

    # Axis labels
    cv2.putText(img, xl, (w // 2 - 6, h - 4), font, 0.36, lc, 1, cv2.LINE_AA)
    cv2.putText(img, yl, (2, h // 2 + 5), font, 0.36, lc, 1, cv2.LINE_AA)

    # Live value
    xv, yv = pts[-1]
    cv2.putText(img, f"({xv:.3f}, {yv:.3f})", (M + 3, h - M - 5),
                font, 0.31, (75, 75, 75), 1, cv2.LINE_AA)

    # Axis tick labels (min / max only)
    tc = (55, 55, 55)
    cv2.putText(img, f"{xmin:.2f}", (M, h - M + 13), font, 0.28, tc, 1, cv2.LINE_AA)
    cv2.putText(img, f"{xmax:.2f}", (w - M - 22, h - M + 13), font, 0.28, tc, 1, cv2.LINE_AA)
    cv2.putText(img, f"{ymax:.2f}", (1, M + 8), font, 0.28, tc, 1, cv2.LINE_AA)
    cv2.putText(img, f"{ymin:.2f}", (1, h - M - 1), font, 0.28, tc, 1, cv2.LINE_AA)

    return img


# ─────────────────────────────────────────────────────────────────────────────
#  Standalone Phase Space node
# ─────────────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='phase_space',
    label='Phase Space',
    category='visualize',
    icon='GitBranch',
    description="2D phase-space (Lissajous / attractor) plot for any pair of scalar signals. Fading colored trail.",
    inputs=[
        {'id': 'x', 'color': 'scalar'},
        {'id': 'y', 'color': 'scalar'},
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'title',       'label': 'Title',        'type': 'string', 'default': 'Phase Space'},
        {'id': 'x_label',     'label': 'X Label',      'type': 'string', 'default': 'X'},
        {'id': 'y_label',     'label': 'Y Label',      'type': 'string', 'default': 'Y'},
        {'id': 'trail_color', 'label': 'Trail Color',  'type': 'color',  'default': '#00ffcc'},
        {'id': 'trail_len',   'label': 'Trail Length', 'type': 'int',    'default': 300, 'min': 10, 'max': 2000},
        {'id': 'width',       'label': 'Width',        'type': 'int',    'default': 380, 'min': 150, 'max': 800},
        {'id': 'height',      'label': 'Height',       'type': 'int',    'default': 380, 'min': 150, 'max': 800},
    ]
)
class PhaseSpaceNode(NodeProcessor):
    def __init__(self):
        self._buf = deque()

    def process(self, inputs, params):
        w = int(params.get('width', 380))
        h = int(params.get('height', 380))

        xv = inputs.get('x')
        yv = inputs.get('y')
        if xv is None or yv is None:
            return {'main': np.zeros((h, w, 3), dtype=np.uint8)}
        try:
            xv, yv = float(xv), float(yv)
        except (TypeError, ValueError):
            return {'main': np.zeros((h, w, 3), dtype=np.uint8)}

        self._buf.append((xv, yv))
        trail_len = int(params.get('trail_len', 300))
        while len(self._buf) > trail_len:
            self._buf.popleft()

        hex_c = str(params.get('trail_color', '#00ffcc')).lstrip('#')
        try:
            r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
            bgr = (b, g, r)
        except Exception:
            bgr = (204, 255, 0)

        img = _render_phase_cell(
            list(self._buf), w, h, bgr,
            title=str(params.get('title', 'Phase Space')),
            xl=str(params.get('x_label', 'X')),
            yl=str(params.get('y_label', 'Y')),
        )
        return {'main': img}


# ─────────────────────────────────────────────────────────────────────────────
#  IMU Phase Dashboard — 6-channel composite (2 rows × 3 cols)
# ─────────────────────────────────────────────────────────────────────────────

# (input_x_id, input_y_id, title, x_label, y_label, bgr_color)
_IMU_PLOTS = [
    ('ax', 'ay', 'Accel  XY', 'ax', 'ay', (204, 255,   0)),   # #00ffcc
    ('ax', 'az', 'Accel  XZ', 'ax', 'az', (255, 170,   0)),   # #00aaff
    ('ay', 'az', 'Accel  YZ', 'ay', 'az', (255,  68, 170)),   # #aa44ff
    ('gx', 'gy', 'Gyro   XY', 'gx', 'gy', ( 68,  68, 255)),   # #ff4444
    ('gx', 'gz', 'Gyro   XZ', 'gx', 'gz', (  0, 136, 255)),   # #ff8800
    ('gy', 'gz', 'Gyro   YZ', 'gy', 'gz', (  0, 238, 255)),   # #ffee00
]


@vision_node(
    type_id='imu_phase_dashboard',
    label='IMU Phase Dashboard',
    category='visualize',
    icon='Activity',
    description="6-channel phase-space dashboard for IMU (2×3 grid): Accel XY/XZ/YZ + Gyro XY/XZ/YZ. For M5StickC Plus2.",
    inputs=[
        {'id': 'ax', 'color': 'scalar', 'label': 'Accel X'},
        {'id': 'ay', 'color': 'scalar', 'label': 'Accel Y'},
        {'id': 'az', 'color': 'scalar', 'label': 'Accel Z'},
        {'id': 'gx', 'color': 'scalar', 'label': 'Gyro X'},
        {'id': 'gy', 'color': 'scalar', 'label': 'Gyro Y'},
        {'id': 'gz', 'color': 'scalar', 'label': 'Gyro Z'},
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'trail_len',  'label': 'Trail Length',     'type': 'int',    'default': 300, 'min': 10, 'max': 2000},
        {'id': 'width',      'label': 'Width',            'type': 'int',    'default': 840, 'min': 450, 'max': 2400},
        {'id': 'height',     'label': 'Height',           'type': 'int',    'default': 597, 'min': 300, 'max': 1600},
        {'id': 'title',      'label': 'Dashboard Title',  'type': 'string', 'default': 'IMU Phase Space — M5StickC Plus2'},
    ]
)
class ImuPhaseDashboardNode(NodeProcessor):
    def __init__(self):
        self._bufs = {f"{p[0]}{p[1]}": deque() for p in _IMU_PLOTS}

    def process(self, inputs, params):
        trail_len = int(params.get('trail_len', 300))
        W = int(params.get('width', 840))
        H = int(params.get('height', 597))
        title = str(params.get('title', 'IMU Phase Space'))
        hdr_h = 36
        cell_w = W // 3
        cell_h = max(1, (H - hdr_h - 1) // 2)  # 1px separator

        vals = {}
        for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz'):
            try:
                vals[k] = float(inputs.get(k) or 0.0)
            except (TypeError, ValueError):
                vals[k] = 0.0

        for plot in _IMU_PLOTS:
            xk, yk = plot[0], plot[1]
            key = f"{xk}{yk}"
            self._bufs[key].append((vals[xk], vals[yk]))
            while len(self._bufs[key]) > trail_len:
                self._bufs[key].popleft()

        cells = []
        for plot in _IMU_PLOTS:
            xk, yk, ptitle, xl, yl, bgr = plot
            key = f"{xk}{yk}"
            cells.append(_render_phase_cell(list(self._bufs[key]), cell_w, cell_h, bgr, ptitle, xl, yl))

        # 2 × 3 grid
        row0 = np.hstack(cells[0:3])
        row1 = np.hstack(cells[3:6])

        # Header bar
        hdr = np.zeros((hdr_h, W, 3), dtype=np.uint8)
        cv2.line(hdr, (0, hdr_h - 1), (W, hdr_h - 1), (42, 42, 42), 1)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(hdr, title, (12, 24), font, 0.56, (215, 215, 215), 1, cv2.LINE_AA)

        # Row-separator (1px)
        sep = np.full((1, W, 3), 30, dtype=np.uint8)

        dashboard = np.vstack([hdr, row0, sep, row1])
        return {'main': dashboard}
