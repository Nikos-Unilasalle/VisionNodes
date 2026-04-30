from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import torch
import threading
import os

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

@vision_node(
    type_id='object_detection_yolo',
    label='YOLO Detector',
    category='detect',
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
        self._cache_hash = None
        self._cache_params = None
        self._cache_result = None

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
            self._loading = True
            send_notification(f'YOLO: loading {name}…', progress=0.1, notif_id='yolo_load')
            try:
                self.model = YOLO(name)
                self.model.to(self.device)
                self.current_model_name = name
                send_notification(f'YOLO: ready ({name})', progress=1.0, notif_id='yolo_load')
            except Exception as e:
                send_notification(f'YOLO load error: {e}', level='error', notif_id='yolo_load')
                self.model = None
            self._loading = False

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None or not YOLO_AVAILABLE:
            return {"main": image, "objects_list": []}

        conf = float(params.get('confidence', 25)) / 100.0
        size_idx = int(params.get('model_size', 0))

        if self.model is None and not getattr(self, '_loading', False):
            threading.Thread(target=self._load_model, args=(size_idx,), daemon=True).start()
        elif self.model is not None:
            try:
                current_idx = ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt"].index(self.current_model_name)
                if size_idx != current_idx and not getattr(self, '_loading', False):
                    threading.Thread(target=self._load_model, args=(size_idx,), daemon=True).start()
            except ValueError:
                pass

        if self.model is None: return {"main": image, "objects_list": []}

        # Cache: skip inference if image + params unchanged
        img_hash = hash(image[::8, ::8].tobytes())
        params_key = (conf, size_idx)
        if img_hash == self._cache_hash and params_key == self._cache_params and self._cache_result is not None:
            return self._cache_result

        # Inference
        self.report_progress(0.2, 'YOLO: detecting…')
        results = self.model.predict(image, conf=conf, verbose=False, device=self.device)
        self.report_progress(1.0, 'YOLO: done')
        
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

        out = {"main": image, "objects_list": objects_list}
        for i in range(3):
            out[f"obj_{i}"] = objects_list[i] if i < len(objects_list) else None

        self._cache_hash = img_hash
        self._cache_params = params_key
        self._cache_result = out
        return out
