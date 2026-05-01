from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='cv_levels',
    label='Image Levels',
    category='cv',
    icon='Sliders',
    description="Adjusts image intensity levels: black point, white point, gamma (midtones), and output range.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'in_black', 'label': 'In Black', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 0},
        {'id': 'in_white', 'label': 'In White', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255},
        {'id': 'gamma',    'label': 'Gamma',    'type': 'scalar', 'min': 0.1, 'max': 5.0, 'default': 1.0},
        {'id': 'out_black', 'label': 'Out Black', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 0},
        {'id': 'out_white', 'label': 'Out White', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255},
    ]
)
class LevelsNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        in_black = float(params.get('in_black', 0))
        in_white = float(params.get('in_white', 255))
        gamma = float(params.get('gamma', 1.0))
        out_black = float(params.get('out_black', 0))
        out_white = float(params.get('out_white', 255))
        
        # Prevent division by zero
        diff = in_white - in_black
        if diff == 0:
            diff = 0.001
            
        # Optimization: use a lookup table for 8-bit images
        # We'll calculate the mapping for all 256 possible values
        x = np.arange(256).astype(np.float32)
        
        # 1. Input remapping & clipping
        res = (x - in_black) / diff
        res = np.clip(res, 0, 1)
        
        # 2. Gamma correction
        if gamma != 1.0:
            # We use 1/gamma so that gamma > 1.0 brightens midtones (standard behavior)
            res = np.power(res, 1.0 / gamma)
            
        # 3. Output remapping & clipping
        res = res * (out_white - out_black) + out_black
        res = np.clip(res, 0, 255).astype(np.uint8)
        
        # Apply LUT
        return {'main': cv2.LUT(img, res)}
