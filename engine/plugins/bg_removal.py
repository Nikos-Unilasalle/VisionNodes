from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='filter_bg_subtraction',
    label='BG Removal',
    category='filter',
    icon='Ghost',
    description="Subtracts the static background to isolate only moving objects.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'mask', 'color': 'mask'}
    ],
    params=[
        {'id': 'history', 'min': 1, 'max': 1000, 'default': 500},
        {'id': 'threshold', 'min': 1, 'max': 100, 'default': 16},
        {'id': 'detectShadows', 'label': 'Detect Shadows', 'type': 'bool', 'default': True}
    ]
)
class BackgroundSubtractionNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.subtractor = None
        self.last_params = {}

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"main": None, "mask": None}
        
        # Re-init if params changed
        hist = int(params.get('history', 500))
        thr = float(params.get('threshold', 16))
        shd = bool(params.get('detectShadows', True))
        
        if self.subtractor is None or \
           params.get('history') != self.last_params.get('history') or \
           params.get('threshold') != self.last_params.get('threshold'):
            self.subtractor = cv2.createBackgroundSubtractorMOG2(
                history=hist, varThreshold=thr, detectShadows=shd
            )
            self.last_params = params.copy()

        mask = self.subtractor.apply(image)
        
        # Clean up mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Apply mask to image
        res = cv2.bitwise_and(image, image, mask=mask)
        
        return {"main": res, "mask": mask}
