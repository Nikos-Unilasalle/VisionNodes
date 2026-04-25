from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='filter_noise_gaussian',
    label='Gaussian Noise',
    category='noise',
    icon='Ghost',
    description="Adds Gaussian noise to simulate film grain or a noisy sensor.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'sigma', 'min': 0, 'max': 100, 'step': 1, 'default': 25}
    ]
)
class NoiseGaussianNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        sigma = float(params.get('sigma', 25.0))
        noise = np.random.randn(*img.shape) * sigma
        noisy_img = np.clip(img.astype(float) + noise, 0, 255).astype(np.uint8)
        return {'main': noisy_img}
