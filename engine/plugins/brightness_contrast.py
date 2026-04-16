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
        
        # Le contraste standard est centré sur 1.0 (on convertit le slider -100/100 en approx 0.5/3.0)
        # alpha = (contrast + 100) / 100
        # beta = brightness
        contrast = float(params.get('contrast', 0))
        brightness = float(params.get('brightness', 0))
        
        alpha = (contrast + 100) / 100.0
        if alpha < 0: alpha = 0
        
        # convertScaleAbs applique : output = saturation_cast(alpha*input + beta)
        res = cv2.convertScaleAbs(img, alpha=alpha, beta=brightness)
        
        return {'main': res}
