from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='filter_noise_salt_pepper',
    label='Salt & Pepper Noise',
    category='noise',
    icon='Ghost',
    description="Adds random white and black pixels (impulse noise).",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'amount', 'min': 0, 'max': 100, 'step': 1, 'default': 5}
    ]
)
class NoiseSaltPepperNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        prob = float(params.get('amount', 5.0)) / 100.0
        
        rnd = np.random.rand(*img.shape[:2])
        out = img.copy()
        out[rnd < (prob / 2.0)] = 0
        out[rnd > 1.0 - (prob / 2.0)] = 255
        
        return {'main': out}
