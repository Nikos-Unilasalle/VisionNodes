from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='geom_cropper',
    label='Auto Cropper',
    category='geom',
    icon='Maximize',
    description="Crops a specific rectangular area from the image (cropping).",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'data', 'color': 'any'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'padding', 'min': 0, 'max': 100, 'default': 10}
    ]
)
class CropperNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        data = inputs.get('data')
        if img is None or data is None or 'xmin' not in data: return {"main": img}
        
        h, w = img.shape[:2]
        pad = float(params.get('padding', 10)) / 100.0
        
        x1 = max(0, int((data['xmin'] - pad/2) * w))
        y1 = max(0, int((data['ymin'] - pad/2) * h))
        x2 = min(w, int((data['xmin'] + data['width'] + pad/2) * w))
        y2 = min(h, int((data['ymin'] + data['height'] + pad/2) * h))
        
        if x2 > x1 and y2 > y1:
            return {"main": img[y1:y2, x1:x2]}
        return {"main": img}
