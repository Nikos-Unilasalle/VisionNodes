import cv2
import numpy as np
from registry import vision_node, NodeProcessor

OUTPUTS = ['Absolute (band energy)', 'Signed']
MIN_SIGMA = 0.3
MIN_RATIO = 1.05


@vision_node(
    type_id='filter_dog',
    label='Difference of Gaussians',
    category='image',
    icon='Waves',
    description=(
        "Band-pass filter: G(sigma) − G(sigma × ratio). Keeps structures whose size is "
        "roughly 2–4 × sigma (cells, grains, dots) and removes finer noise and slow "
        "illumination. Absolute output + a large blur = texture energy at that scale. "
        "Sigma can be driven by a Number node to adapt to image resolution."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'sigma', 'color': 'scalar', 'label': 'Sigma'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'raw', 'color': 'any', 'label': 'Raw (float)'},
    ],
    params=[
        {'id': 'sigma', 'label': 'Sigma (px)', 'type': 'float', 'default': 3.0, 'min': MIN_SIGMA, 'max': 50, 'step': 0.1},
        {'id': 'ratio', 'label': 'Ratio (k)', 'type': 'float', 'default': 2.0, 'min': MIN_RATIO, 'max': 8, 'step': 0.1},
        {'id': 'output', 'label': 'Output', 'type': 'enum', 'options': OUTPUTS, 'default': 0},
    ],
)
class DifferenceOfGaussiansNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'raw': None}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        gray = gray.astype(np.float32)
        sigma = max(MIN_SIGMA, float(params.get('sigma', 3.0)))
        ratio = max(MIN_RATIO, float(params.get('ratio', 2.0)))
        signed = int(params.get('output', 0)) == 1

        dog = cv2.GaussianBlur(gray, (0, 0), sigma) - cv2.GaussianBlur(gray, (0, 0), sigma * ratio)

        if signed:
            peak = float(np.abs(dog).max())
            scale = 127.0 / peak if peak > 0 else 0.0
            main = np.clip(dog * scale + 128, 0, 255).astype(np.uint8)
            return {'main': main, 'raw': dog}

        energy = np.abs(dog)
        main = cv2.normalize(energy, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return {'main': main, 'raw': energy}
