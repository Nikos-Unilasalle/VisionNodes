import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="bg_sub_mog2",
    label="MOG2 Subtractor",
    category=["cv", "analysis"],
    icon="Layers",
    description="Separates moving foreground objects from a static background (MOG2).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}],
    params=[
        {"id": "history", "label": "History", "type": "scalar", "min": 1, "max": 1000, "default": 500},
        {"id": "threshold", "label": "Threshold", "type": "scalar", "min": 0, "max": 100, "default": 16},
        {"id": "detect_shadows", "label": "Shadows", "type": "boolean", "default": True}
    ]
)
class MOG2SubtractorNode(NodeProcessor):
    def __init__(self):
        self.subtractor = None
        self.last_params = {}

    def process(self, inputs, params):
        img = inputs.get('image') if inputs.get('image') is not None else inputs.get('main')
        if img is None: return {"main": None, "mask": None}

        # Initialize or update subtractor if params change
        history = int(params.get('history', 500))
        threshold = float(params.get('threshold', 16))
        shadows = bool(params.get('detect_shadows', True))

        current_params = (history, threshold, shadows)
        if self.subtractor is None or current_params != self.last_params:
            self.subtractor = cv2.createBackgroundSubtractorMOG2(
                history=history, varThreshold=threshold, detectShadows=shadows
            )
            self.last_params = current_params

        mask = self.subtractor.apply(img)
        return {"main": mask, "mask": mask}

@vision_node(
    type_id="bg_sub_knn",
    label="KNN Subtractor",
    category=["cv", "analysis"],
    icon="Layers",
    description="Separates moving foreground objects using K-Nearest Neighbors approach.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}],
    params=[
        {"id": "history", "label": "History", "type": "scalar", "min": 1, "max": 1000, "default": 500},
        {"id": "threshold", "label": "Dist Thresh", "type": "scalar", "min": 0, "max": 1000, "default": 400},
        {"id": "detect_shadows", "label": "Shadows", "type": "boolean", "default": True}
    ]
)
class KNNSubtractorNode(NodeProcessor):
    def __init__(self):
        self.subtractor = None
        self.last_params = {}

    def process(self, inputs, params):
        img = inputs.get('image') if inputs.get('image') is not None else inputs.get('main')
        if img is None: return {"main": None, "mask": None}

        history = int(params.get('history', 500))
        threshold = float(params.get('threshold', 400))
        shadows = bool(params.get('detect_shadows', True))

        current_params = (history, threshold, shadows)
        if self.subtractor is None or current_params != self.last_params:
            self.subtractor = cv2.createBackgroundSubtractorKNN(
                history=history, dist2Threshold=threshold, detectShadows=shadows
            )
            self.last_params = current_params

        mask = self.subtractor.apply(img)
        return {"main": mask, "mask": mask}
