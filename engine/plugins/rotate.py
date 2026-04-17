from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_rotate',
    label='Rotate Image',
    category='geom',
    icon='Move',
    description="Applies a custom rotation and scaling to the video stream.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'angle', 'min': 0, 'max': 360, 'step': 1, 'default': 0},
        {'id': 'scale', 'min': 0.1, 'max': 3.0, 'step': 0.1, 'default': 1.0}
    ]
)
class RotateNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        angle = float(params.get('angle', 0))
        scale = float(params.get('scale', 1.0))
        
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        
        # Matrix de rotation
        matrix = cv2.getRotationMatrix2D(center, angle, scale)
        rotated = cv2.warpAffine(img, matrix, (w, h))
        
        return {'main': rotated}
