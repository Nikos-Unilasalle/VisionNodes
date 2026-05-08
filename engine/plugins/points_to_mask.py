import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='points_to_mask',
    label='Points to Mask',
    category='mask',
    icon='Target',
    description="Convert a list of points into a binary mask. Each point is drawn as a filled circle.",
    inputs=[
        {'id': 'points', 'color': 'list'},
        {'id': 'reference', 'color': 'image'}
    ],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'radius', 'label': 'Point Radius (px)', 'type': 'number', 'default': 5, 'min': 1, 'max': 500},
        {'id': 'width',  'label': 'Width (if no ref)', 'type': 'number', 'default': 640, 'min': 1, 'max': 8000},
        {'id': 'height', 'label': 'Height (if no ref)', 'type': 'number', 'default': 480, 'min': 1, 'max': 8000},
    ]
)
class PointsToMaskNode(NodeProcessor):
    def process(self, inputs, params):
        points = inputs.get('points')
        ref = inputs.get('reference')
        
        # Determine size
        if ref is not None:
            h, w = ref.shape[:2]
        else:
            w = int(params.get('width', 640))
            h = int(params.get('height', 480))
            
        mask = np.zeros((h, w), dtype=np.uint8)
        
        if not points or not isinstance(points, list):
            return {'mask': mask}
            
        radius = int(params.get('radius', 5))
        
        for p in points:
            x, y = None, None
            
            # Case 1: Dict with 'x' and 'y' (normalized or pixel)
            if isinstance(p, dict):
                x_val = p.get('x')
                y_val = p.get('y')
                if x_val is not None and y_val is not None:
                    # Check if normalized (0-1) or pixel
                    # MergePoints uses normalized, so we assume normalized if it looks like it
                    # or if we have a way to know. Here we'll guess based on range or just assume 
                    # based on the workflow context.
                    # Actually, let's check if 'relative' or similar exists.
                    # Or just assume 0-1 if both are <= 1.
                    if float(x_val) <= 1.0 and float(y_val) <= 1.0:
                        x = int(float(x_val) * w)
                        y = int(float(y_val) * h)
                    else:
                        x = int(float(x_val))
                        y = int(float(y_val))
            
            # Case 2: List/Tuple [x, y]
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                x_val, y_val = p[0], p[1]
                if float(x_val) <= 1.0 and float(y_val) <= 1.0:
                    x = int(float(x_val) * w)
                    y = int(float(y_val) * h)
                else:
                    x = int(float(x_val))
                    y = int(float(y_val))
            
            if x is not None and y is not None:
                cv2.circle(mask, (x, y), radius, 255, -1)
                
        return {'mask': mask}
