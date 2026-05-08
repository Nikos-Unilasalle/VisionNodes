import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id='cv_colorspace',
    label='Color Space Convert',
    category='detect',
    icon='Palette',
    description="Convert RGB image to HSV or CIE Lab color space for advanced analysis and processing.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'hsv', 'color': 'image'},
        {'id': 'lab', 'color': 'image'}
    ],
    params=[
        {'id': 'bgr_input', 'label': 'Input is BGR (OpenCV)', 'type': 'boolean', 'default': True}
    ]
)
class ColorSpaceNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'hsv': None, 'lab': None}

        try:
            # Handle different image formats
            if not isinstance(img, np.ndarray):
                return {'main': None, 'hsv': None, 'lab': None}

            # Ensure 3-channel image
            if len(img.shape) != 3 or img.shape[2] != 3:
                return {'main': img, 'hsv': None, 'lab': None}

            # Handle BGR/RGB conversion
            is_bgr = bool(params.get('bgr_input', True))
            working_img = img
            if not is_bgr:
                # Frontend sends RGB, convert to BGR for OpenCV
                working_img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            # Convert to HSV and Lab
            hsv = cv2.cvtColor(working_img, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(working_img, cv2.COLOR_BGR2Lab)

            # Output selection
            output_mode = int(params.get('output_mode', 0))
            if output_mode == 0:  # HSV
                main = hsv
            elif output_mode == 1:  # Lab
                main = lab
            else:  # Original
                main = img

            return {
                'main': main,
                'hsv': hsv,
                'lab': lab
            }

        except Exception as e:
            return {'main': img, 'hsv': None, 'lab': None}
