import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='filter_high_pass',
    label='Filter: High Pass',
    category='image',
    icon='Waves',
    description="Extracts fine details and edges by removing low frequencies. Useful for frequency separation.",
    
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
        {'id': 'kernel_size', 'label': 'Cutoff (Size)', 'type': 'int', 'min': 1, 'max': 51, 'default': 5},
        {'id': 'gain', 'label': 'Gain', 'type': 'float', 'min': 1.0, 'max': 5.0, 'default': 1.0},
        {'id': 'bias', 'label': 'Visual Bias (128)', 'type': 'bool', 'default': True}
    ]
)
class HighPassFilterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}
            
        # 1. Read parameters
        k_size = int(params.get('kernel_size', 5))
        gain = float(params.get('gain', 1.0))
        use_bias = bool(params.get('bias', True))
        
        # 2. Ensure kernel size is odd
        if k_size % 2 == 0:
            k_size += 1
        k_size = max(1, k_size)
        
        # 3. Create Low Pass version
        blur = cv2.GaussianBlur(img, (k_size, k_size), 0)
        
        # 4. Subtract Low Pass from Original (High Pass = Original - LowPass)
        # We work in float to avoid clipping during subtraction
        img_f = img.astype(np.float32)
        blur_f = blur.astype(np.float32)
        
        high_pass = (img_f - blur_f) * gain
        
        # 5. Apply Bias if requested (useful to see the result centered around gray)
        if use_bias:
            high_pass += 128
            
        # 6. Clip and convert back to uint8
        result = np.clip(high_pass, 0, 255).astype(np.uint8)
        
        return {'main': result}
