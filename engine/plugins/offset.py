from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_offset',
    label='Offset Shift',
    category='geom',
    icon='Move',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'x_offset', 'min': -1000, 'max': 1000, 'step': 5, 'default': 0},
        {'id': 'y_offset', 'min': -1000, 'max': 1000, 'step': 5, 'default': 0}
    ]
)
class OffsetNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        tx = float(params.get('x_offset', 0))
        ty = float(params.get('y_offset', 0))
        
        h, w = img.shape[:2]
        
        # Matrice de translation (Décalage spatial)
        M = np.float32([[1, 0, tx], [0, 1, ty]])
        shifted = cv2.warpAffine(img, M, (w, h))
        
        return {'main': shifted}
