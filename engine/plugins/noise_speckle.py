from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='filter_noise_speckle',
    label='Speckle Noise',
    category='filter',
    icon='Ghost',
    description="Adds multiplicative noise to simulate complex interference.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'intensity', 'min': 0, 'max': 100, 'step': 1, 'default': 10}
    ]
)
class NoiseSpeckleNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        intensity = float(params.get('intensity', 10.0)) / 100.0
        noise = np.random.randn(*img.shape) * intensity
        noisy_img = np.clip(img.astype(float) * (1 + noise), 0, 255).astype(np.uint8)
        return {'main': noisy_img}
