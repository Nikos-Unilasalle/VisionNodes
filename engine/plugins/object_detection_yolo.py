from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np
import torch
import os

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

@vision_node(
    type_id='object_detection_yolo',
    label='YOLO Detector',
    category='track',
    icon='Zap',
    description="High-performance object detection (80 classes) using the YOLOv11 model.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'objects_list', 'color': 'list'},
        {'id': 'obj_0', 'color': 'dict'},
        {'id': 'obj_1', 'color': 'dict'},
        {'id': 'obj_2', 'color': 'dict'}
    ],
    params=[
        {'id': 'confidence', 'min': 0, 'max': 100, 'default': 25},
        {'id': 'model_size', 'min': 0, 'max': 2, 'default': 0} # 0=Nano, 1=Small, 2=Medium
    ]
)
class YoloDetectionNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.model = None
        self.device = 'cpu'
        self.current_model_name = ""
        
        if torch.backends.mps.is_available():
            self.device = 'mps'
        elif torch.cuda.is_available():
            self.device = 'cuda'
            
        print(f"[YOLO] Using device: {self.device}")

    def _load_model(self, size_idx):
        if not YOLO_AVAILABLE: return
        
        models = ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt"]
        name = models[int(size_idx)]
        
        if name != self.current_model_name:
            print(f"[YOLO] Loading model: {name}")
            self.model = YOLO(name)
            self.model.to(self.device)
            self.current_model_name = name

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None or not YOLO_AVAILABLE: 
            return {"main": image, "objects_list": []}
            
        conf = float(params.get('confidence', 25)) / 100.0
        size_idx = int(params.get('model_size', 0))

        if self.model is None:
            self._load_model(size_idx)
        else:
            try:
                current_idx = ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt"].index(self.current_model_name)
                if size_idx != current_idx:
                    self._load_model(size_idx)
            except ValueError:
                self._load_model(size_idx)
            
        if self.model is None: return {"main": image, "objects_list": []}

        # Inference
        results = self.model.predict(image, conf=conf, verbose=False, device=self.device)
        
        objects_list = []
        h, w = image.shape[:2]
        
        if len(results) > 0:
            result = results[0]
            boxes = result.boxes
            for box in boxes:
                # Get coordinates
                b = box.xywhn[0].cpu().numpy() # [x_center, y_center, w, h] normalized
                cls = int(box.cls[0].cpu().numpy())
                label = self.model.names[cls]
                score = float(box.conf[0].cpu().numpy())
                
                # Convert center-xywh to corner-xmin-ymin-width-height
                xmin = b[0] - b[2]/2
                ymin = b[1] - b[3]/2
                
                obj_data = {
                    "label": label,
                    "score": score,
                    "xmin": float(xmin),
                    "ymin": float(ymin),
                    "width": float(b[2]),
                    "height": float(b[3]),
                    "_type": "graphics",
                    "shape": "rect",
                    "pts": [
                        [float(xmin), float(ymin)],
                        [float(xmin + b[2]), float(ymin + b[3])]
                    ],
                    "r": 255, "g": 255, "b": 0, "thickness": 2
                }
                objects_list.append(obj_data)

        out = {
            "main": image,
            "objects_list": objects_list
        }
        # Populate individual object ports
        for i in range(3):
            out[f"obj_{i}"] = objects_list[i] if i < len(objects_list) else None
            
        return out
