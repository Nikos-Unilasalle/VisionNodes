from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import random

@vision_node(
    type_id='filter_glitch',
    label='Glitch FX',
    category='fx',
    icon='Zap',
    description="Applies random digital distortions for a 'glitch' effect.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'intensity', 'min': 0, 'max': 100, 'default': 20},
        {'id': 'shift', 'min': 0, 'max': 50, 'default': 10}
    ]
)
class GlitchNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"main": None}
        
        intensity = int(params.get('intensity', 20))
        shift = int(params.get('shift', 10))
        
        if intensity == 0: return {"main": image}
        
        res = image.copy()
        h, w = res.shape[:2]
        
        # Color shifting
        if random.random() < (intensity / 100):
            channel = random.randint(0, 2)
            s = random.randint(-shift, shift)
            res[:, :, channel] = np.roll(res[:, :, channel], s, axis=1)
            
        # Horizontal scanlines displacement
        for _ in range(int(intensity / 10)):
            if random.random() < 0.5:
                y = random.randint(0, h - 1)
                h_slice = random.randint(1, 10)
                s = random.randint(-shift * 2, shift * 2)
                res[y:y+h_slice, :] = np.roll(res[y:y+h_slice, :], s, axis=1)
        
        return {"main": res}
