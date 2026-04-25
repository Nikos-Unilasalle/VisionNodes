from registry import vision_node, NodeProcessor
import math
import numpy as np
import cv2

@vision_node(
    type_id='math_vec_to_screen',
    label='Vec → Screen',
    category='math',
    icon='Monitor',
    description="Maps yaw/pitch to normalized screen coordinates [0..1]. Connect image for tan()-based projection and visual calibration feedback.",
    inputs=[
        {'id': '3Dvector', 'color': 'dict'},
        {'id': 'image',    'color': 'image'},
    ],
    outputs=[
        {'id': 'main',  'color': 'image'},
        {'id': 'x',     'color': 'scalar'},
        {'id': 'y',     'color': 'scalar'},
        {'id': 'point', 'color': 'dict'}
    ],
    params=[
        {'id': 'scale_x',  'label': 'Scale X',    'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 10.0, 'step': 0.05},
        {'id': 'scale_y',  'label': 'Scale Y',    'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 10.0, 'step': 0.05},
        {'id': 'offset_x', 'label': 'Offset X',   'type': 'float', 'default': 0.0,  'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'offset_y', 'label': 'Offset Y',   'type': 'float', 'default': 0.0,  'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'smooth',   'label': 'Smoothing',  'type': 'float', 'default': 0.7,  'min': 0.0,  'max': 0.99,'step': 0.01},
        {'id': 'clamp',    'label': 'Clamp',  'type': 'bool', 'default': True},
        {'id': 'flip_x',   'label': 'Flip X', 'type': 'bool', 'default': False},
        {'id': 'flip_y',   'label': 'Flip Y', 'type': 'bool', 'default': False},
    ]
)
class VecToScreenNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._sx = 0.5
        self._sy = 0.5

    def process(self, inputs, params):
        gaze  = inputs.get('3Dvector')
        image = inputs.get('image')

        empty_pt = {'_type': 'graphics', 'shape': 'point',
                    'pts': [[0.5, 0.5]], 'relative': True,
                    'r': 255, 'g': 80, 'b': 0, 'thickness': 12}

        if not isinstance(gaze, dict):
            return {'main': image, 'x': self._sx, 'y': self._sy, 'point': empty_pt}

        yaw   = float(gaze.get('yaw',   0.0))
        pitch = float(gaze.get('pitch', 0.0))

        scale_x  = float(params.get('scale_x',  1.0))
        scale_y  = float(params.get('scale_y',  1.0))
        offset_x = float(params.get('offset_x', 0.0))
        offset_y = float(params.get('offset_y', 0.0))
        smooth   = float(params.get('smooth',   0.7))
        do_clamp = int(params.get('clamp',  1))
        flip_x   = int(params.get('flip_x', 0))
        flip_y   = int(params.get('flip_y', 0))

        if image is not None:
            # Physically-motivated projection: use image FOV as natural scale
            # tan(angle) maps ±FOV/2 to ±0.5 around center
            # focal ≈ max(w,h) → half-FOV ≈ atan(0.5) ≈ 26°
            h_img, w_img = image.shape[:2]
            focal = float(max(w_img, h_img))
            raw_x = 0.5 + (math.tan(yaw   + offset_x) * focal / w_img) * scale_x
            raw_y = 0.5 - (math.tan(pitch + offset_y) * focal / h_img) * scale_y
        else:
            # Linear fallback (no image connected)
            raw_x = 0.5 + (yaw   + offset_x) * scale_x
            raw_y = 0.5 - (pitch + offset_y) * scale_y

        if flip_x: raw_x = 1.0 - raw_x
        if flip_y: raw_y = 1.0 - raw_y

        self._sx = smooth * self._sx + (1.0 - smooth) * raw_x
        self._sy = smooth * self._sy + (1.0 - smooth) * raw_y

        out_x = max(0.0, min(1.0, self._sx)) if do_clamp else self._sx
        out_y = max(0.0, min(1.0, self._sy)) if do_clamp else self._sy

        point = {
            '_type': 'graphics', 'shape': 'point',
            'pts': [[out_x, out_y]], 'relative': True,
            'r': 255, 'g': 80, 'b': 0, 'thickness': 14
        }

        # Draw calibration overlay on image
        out_img = None
        if image is not None:
            out_img = image.copy()
            h_img, w_img = out_img.shape[:2]
            px, py = int(out_x * w_img), int(out_y * h_img)
            # Crosshair + filled dot
            cv2.line(out_img, (px - 20, py), (px + 20, py), (0, 80, 255), 1)
            cv2.line(out_img, (px, py - 20), (px, py + 20), (0, 80, 255), 1)
            cv2.circle(out_img, (px, py), 8, (0, 80, 255), -1)
            cv2.circle(out_img, (px, py), 9, (255, 255, 255), 1)
            label = f'({out_x:.2f}, {out_y:.2f})'
            cv2.putText(out_img, label, (px + 12, py - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        return {'main': out_img, 'x': out_x, 'y': out_y, 'point': point}
