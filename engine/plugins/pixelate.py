from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_pixelate',
    label='Pixelate Filter',
    category='cv',
    icon='Hash',
    description="Reduces the apparent resolution of the image to create a pixelated effect.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'blocks', 'min': 1, 'max': 50, 'step': 1, 'default': 10}
    ]
)
class PixelateNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        blocks = int(params.get('blocks', 10))
        h, w = img.shape[:2]
        
        # Resize down
        small = cv2.resize(img, (max(1, w // blocks), max(1, h // blocks)), interpolation=cv2.INTER_LINEAR)
        # Resize up
        pixelated = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        
        return {'main': pixelated}
