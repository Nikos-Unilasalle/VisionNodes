from registry import vision_node, NodeProcessor
import math
import numpy as np
import cv2

@vision_node(
    type_id='math_3d_to_screen',
    label='3D → Screen',
    category='math',
    icon='Box',
    description="Universal perspective projection of a 3D vector [x, y, z] to 2D screen coordinates [0..1].",
    inputs=[
        {'id': 'vector', 'color': 'dict', 'label': 'Vector (X, Y, Z)'},
        {'id': 'image',  'color': 'image', 'label': 'Background (opt)'},
    ],
    outputs=[
        {'id': 'main',  'color': 'image', 'label': 'Image Output'},
        {'id': 'x',     'color': 'scalar', 'label': 'Screen X'},
        {'id': 'y',     'color': 'scalar', 'label': 'Screen Y'},
        {'id': 'point', 'color': 'dict', 'label': 'Graphics Point'}
    ],
    params=[
        {'id': 'focal_length', 'label': 'Focal Length', 'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 5.0, 'step': 0.1},
        {'id': 'scale_x',      'label': 'Scale X',     'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 10.0, 'step': 0.05},
        {'id': 'scale_y',      'label': 'Scale Y',     'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 10.0, 'step': 0.05},
        {'id': 'offset_x',     'label': 'Offset X',    'type': 'float', 'default': 0.0,  'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'offset_y',     'label': 'Offset Y',    'type': 'float', 'default': 0.0,  'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'flip_x',       'label': 'Flip X',      'type': 'bool',  'default': False},
        {'id': 'flip_y',       'label': 'Flip Y',      'type': 'bool',  'default': False},
        {'id': 'clamp',        'label': 'Clamp [0..1]', 'type': 'bool',  'default': True},
    ]
)
class Vec3ToScreenNode(NodeProcessor):
    def process(self, inputs, params):
        vec = inputs.get('vector')
        img = inputs.get('image')

        if not isinstance(vec, dict):
            return {'main': img, 'x': None, 'y': None, 'point': None}

        # Extract components
        x = float(vec.get('x', vec.get('vec_x', 0.0)))
        y = float(vec.get('y', vec.get('vec_y', 0.0)))
        z = float(vec.get('z', vec.get('vec_z', 1.0)))

        # Perspective projection
        if abs(z) < 0.0001: z = 0.0001
        
        f = float(params.get('focal_length', 1.0))
        sx = float(params.get('scale_x', 1.0))
        sy = float(params.get('scale_y', 1.0))
        ox = float(params.get('offset_x', 0.0))
        oy = float(params.get('offset_y', 0.0))

        # Basic pinhole: x' = f * (x/z)
        raw_x = 0.5 + (f * (x / z) + ox) * sx
        raw_y = 0.5 - (f * (y / z) + oy) * sy

        if bool(params.get('flip_x', False)): raw_x = 1.0 - raw_x
        if bool(params.get('flip_y', False)): raw_y = 1.0 - raw_y

        if bool(params.get('clamp', True)):
            raw_x = max(0.0, min(1.0, raw_x))
            raw_y = max(0.0, min(1.0, raw_y))

        point = {
            '_type': 'graphics', 'shape': 'point',
            'pts': [[raw_x, raw_y]], 'relative': True,
            'color': (0, 255, 100), 'thickness': 10
        }

        # Visualization
        out_img = None
        if img is not None:
            out_img = img.copy()
            h, w = out_img.shape[:2]
            px, py = int(raw_x * w), int(raw_y * h)
            cv2.circle(out_img, (px, py), 12, (0, 255, 100), 2, cv2.LINE_AA)
            cv2.drawMarker(out_img, (px, py), (0, 255, 100), cv2.MARKER_CROSS, 20, 1)

        return {'main': out_img, 'x': raw_x, 'y': raw_y, 'point': point}
