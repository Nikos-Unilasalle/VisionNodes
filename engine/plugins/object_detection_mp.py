from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np
import os
import urllib.request

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

@vision_node(
    type_id='analysis_object_mp',
    label='Object Detector',
    category='track',
    icon='Box',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'objects_list', 'color': 'list'},
        {'id': 'obj_0', 'color': 'dict'},
        {'id': 'obj_1', 'color': 'dict'},
        {'id': 'obj_2', 'color': 'dict'},
        {'id': 'obj_3', 'color': 'dict'},
        {'id': 'obj_4', 'color': 'dict'}
    ],
    params=[
        {'id': 'score_threshold', 'min': 0, 'max': 100, 'default': 50},
        {'id': 'max_results', 'min': 1, 'max': 20, 'default': 5}
    ]
)
class ObjectDetectionNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.detector = None
        self.model_path = "efficientdet.tflite"
        self.last_params = {}
        self._init_detector()

    def _init_detector(self, score=0.5, max_res=5):
        if not AI_AVAILABLE: return
        
        if not os.path.exists(self.model_path):
            url = "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite"
            try: 
                print(f"Downloading Object Detection model...")
                urllib.request.urlretrieve(url, self.model_path)
            except Exception as e:
                print(f"Failed to download object model: {e}")
                return

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.ObjectDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            score_threshold=score,
            max_results=max_res
        )
        self.detector = vision.ObjectDetector.create_from_options(options)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None or not AI_AVAILABLE: 
            return {"main": image, "objects_list": []}
        
        score = float(params.get('score_threshold', 50)) / 100.0
        max_res = int(params.get('max_results', 5))
        
        if self.detector is None or \
           score != self.last_params.get('score_threshold') or \
           max_res != self.last_params.get('max_results'):
            self._init_detector(score, max_res)
            self.last_params = params.copy()
            if self.detector is None: return {"main": image, "objects_list": []}

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        
        objects_list = []
        h, w = image.shape[:2]
        
        if results.detections:
            for detection in results.detections:
                bbox = detection.bounding_box
                category = detection.categories[0]
                
                obj_data = {
                    "label": category.category_name,
                    "score": category.score,
                    "xmin": bbox.origin_x / w,
                    "ymin": bbox.origin_y / h,
                    "width": bbox.width / w,
                    "height": bbox.height / h,
                    "_type": "graphics",
                    "shape": "rect",
                    "pts": [
                        [bbox.origin_x / w, bbox.origin_y / h],
                        [(bbox.origin_x + bbox.width) / w, (bbox.origin_y + bbox.height) / h]
                    ],
                    "r": 255, "g": 0, "b": 255, "thickness": 2
                }
                objects_list.append(obj_data)

        out = {
            "main": image,
            "objects_list": objects_list
        }
        # Populate individual object ports
        for i in range(5):
            out[f"obj_{i}"] = objects_list[i] if i < len(objects_list) else None
            
        return out
