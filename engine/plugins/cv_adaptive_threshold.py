import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_adaptive_threshold',
    label='Adaptive Threshold',
    category='segmentation',
    icon='Layers',
    description=(
        "Local thresholding: computes a per-pixel threshold from the neighbourhood mean\n"
        "minus a constant C. Robust to uneven illumination (ch12 §12.2).\n\n"
        "Block Size must be odd; pixels darker than (local_mean − C) are set to 255."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Mask', 'color': 'mask'},
    ],
    params=[
        {'id': 'block_size',      'label': 'Block Size',       'type': 'int',  'default': 11, 'min': 3, 'max': 201},
        {'id': 'c',               'label': 'Constant (C)',      'type': 'int',  'default': 5,  'min': -50, 'max': 50},
        {'id': 'adaptive_method', 'label': 'Adaptive Method',  'type': 'enum',
         'options': ['Mean', 'Gaussian'], 'default': 1},
        {'id': 'invert',          'label': 'Invert',            'type': 'bool', 'default': False},
    ]
)
class AdaptiveThresholdNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()

        block = int(params.get('block_size', 11))
        if block < 3:
            block = 3
        if block % 2 == 0:
            block += 1  # must be odd

        c_val   = int(params.get('c', 5))
        method  = int(params.get('adaptive_method', 1))
        invert  = bool(params.get('invert', False))

        cv_method = cv2.ADAPTIVE_THRESH_GAUSSIAN_C if method == 1 else cv2.ADAPTIVE_THRESH_MEAN_C
        thresh_type = cv2.THRESH_BINARY_INV if not invert else cv2.THRESH_BINARY

        result = cv2.adaptiveThreshold(
            gray, 255, cv_method, thresh_type, block, c_val
        )

        return {'main': result}
