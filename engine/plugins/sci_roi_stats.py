import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='sci_roi_stats',
    label='ROI Statistics',
    category=['analysis', 'scientific'],
    icon='Crosshair',
    description="Measure pixel statistics (mean, std, min, max) inside a rectangular region of interest.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main',  'color': 'image',  'label': 'Image + ROI'},
        {'id': 'mean',  'color': 'scalar'},
        {'id': 'std',   'color': 'scalar'},
        {'id': 'min',   'color': 'scalar'},
        {'id': 'max',   'color': 'scalar'},
        {'id': 'count', 'color': 'scalar', 'label': 'Pixel Count'},
    ],
    params=[
        {'id': 'x',          'label': 'X (%)',      'type': 'float', 'default': 25.0, 'min': 0.0, 'max': 99.0},
        {'id': 'y',          'label': 'Y (%)',      'type': 'float', 'default': 25.0, 'min': 0.0, 'max': 99.0},
        {'id': 'w',          'label': 'Width (%)',  'type': 'float', 'default': 50.0, 'min': 1.0, 'max': 100.0},
        {'id': 'h',          'label': 'Height (%)', 'type': 'float', 'default': 50.0, 'min': 1.0, 'max': 100.0},
        {'id': 'channel',    'label': 'Channel',    'type': 'enum',  'options': ['Luminance', 'Red', 'Green', 'Blue'], 'default': 0},
        {'id': 'color',      'label': 'Overlay Color', 'type': 'color', 'default': '#00FFA0'},
        {'id': 'show_stats', 'label': 'Show Stats', 'type': 'bool',  'default': True},
    ]
)
class ROIStatsNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        _none = {'main': None, 'mean': None, 'std': None, 'min': None, 'max': None, 'count': None}
        if img is None:
            return _none

        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)

        ih, iw = img.shape[:2]
        rx = int(float(params.get('x', 25.0)) / 100.0 * iw)
        ry = int(float(params.get('y', 25.0)) / 100.0 * ih)
        rw = max(1, int(float(params.get('w', 50.0)) / 100.0 * iw))
        rh = max(1, int(float(params.get('h', 50.0)) / 100.0 * ih))
        rx = min(rx, iw - 1);  ry = min(ry, ih - 1)
        rw = min(rw, iw - rx); rh = min(rh, ih - ry)

        chan = int(params.get('channel', 0))
        is_color = len(img.shape) == 3 and img.shape[2] == 3
        roi = img[ry:ry+rh, rx:rx+rw]

        if not is_color:
            data = roi.astype(np.float32)
        elif chan == 0:
            data = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        elif chan == 1:
            data = roi[:, :, 2].astype(np.float32)
        elif chan == 2:
            data = roi[:, :, 1].astype(np.float32)
        else:
            data = roi[:, :, 0].astype(np.float32)

        mean_v = float(np.mean(data))
        std_v  = float(np.std(data))
        min_v  = float(np.min(data))
        max_v  = float(np.max(data))
        count  = int(data.size)

        color_hex = str(params.get('color', '#00FFA0'))
        try:
            r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
            color_bgr = (b, g, r)
        except Exception:
            color_bgr = (0, 255, 160)

        out = img.copy()
        if len(out.shape) == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(out, (rx, ry), (rx + rw, ry + rh), color_bgr, 1)

        if bool(params.get('show_stats', True)):
            font  = cv2.FONT_HERSHEY_SIMPLEX
            lines = [f"mean={mean_v:.1f}", f"std={std_v:.1f}", f"[{min_v:.0f},{max_v:.0f}]"]
            for i, line in enumerate(lines):
                cv2.putText(out, line, (rx + 3, ry + 14 + i * 14), font, 0.38, color_bgr, 1, cv2.LINE_AA)

        return {'main': out, 'mean': mean_v, 'std': std_v, 'min': min_v, 'max': max_v, 'count': count}
