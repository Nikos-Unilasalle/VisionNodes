from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_brightness_contrast',
    label='Bright & Contrast',
    category='cv',
    icon='Zap',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'brightness', 'min': -100, 'max': 100, 'step': 1, 'default': 0},
        {'id': 'contrast', 'min': -100, 'max': 100, 'step': 1, 'default': 0}
    ]
)
class BrightnessContrastNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        brightness = int(params.get('brightness', 0))
        contrast = int(params.get('contrast', 0))

        if brightness != 0 or contrast != 0:
            if contrast != 0:
                f = 131 * (contrast + 127) / (127 * (131 - contrast))
                alpha_c = f
                gamma_c = 127 * (1 - f)
                img = cv2.addWeighted(img, alpha_c, img, 0, gamma_c)
            if brightness != 0:
                img = cv2.add(img, np.array([brightness]))
        
        return {'main': img}
