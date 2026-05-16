import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='filter_low_pass',
    label='Filter: Low Pass',
    category='image',
    icon='Waves',
    description="Applies a Gaussian low-pass filter to smooth the image and reduce noise.",
    
    # UI Flags
    resizable=False,
    colorable=True,
    
    # Port Definitions
    inputs=[
        {'id': 'image', 'label': 'Input', 'color': 'image'}
    ],
    outputs=[
        {'id': 'main', 'label': 'Output', 'color': 'image'}
    ],
    
    # Parameter Definitions
    params=[
        {'id': 'kernel_size', 'label': 'Smoothness', 'type': 'int', 'min': 1, 'max': 31, 'default': 5},
        {'id': 'sigma', 'label': 'Sigma (Spread)', 'type': 'float', 'min': 0.1, 'max': 10.0, 'default': 1.0}
    ]
)
class LowPassFilterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}
            
        # 1. Read parameters
        k_size = int(params.get('kernel_size', 5))
        sigma = float(params.get('sigma', 1.0))
        
        # 2. Ensure kernel size is odd and positive
        if k_size % 2 == 0:
            k_size += 1
        k_size = max(1, k_size)
        
        # 3. Apply Gaussian Blur (Low Pass)
        
        result = cv2.GaussianBlur(img, (k_size, k_size), sigma)
        
        return {'main': result}
