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
    type_id='analysis_pose_mp',
    label='Pose Tracker',
    category='track',
    icon='User',
    description="Analyzes and tracks human body posture (33 keypoints) via MediaPipe.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'pose_list', 'color': 'list'},
        {'id': 'data', 'color': 'dict'}
    ],
    params=[]
)
class PoseDetectionNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.detector = None
        self.model_path = "pose_landmarker.task"
        # Initialization is now lazy (moved to process)

    def _init_detector(self):
        if not AI_AVAILABLE: return
        
        if not os.path.exists(self.model_path):
            url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
            try: 
                print(f"Downloading Pose model...")
                urllib.request.urlretrieve(url, self.model_path)
            except Exception as e:
                print(f"Failed to download pose model: {e}")
                return

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None or not AI_AVAILABLE: 
            return {"main": image, "pose_list": [], "data": {}}
        
        if self.detector is None:
            self._init_detector()
            if self.detector is None: return {"main": image, "pose_list": [], "data": {}}

        # Convert to RGB for MediaPipe
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        
        pose_list = []
        main_pose = {}
        
        if results.pose_landmarks:
            for landmarks in results.pose_landmarks:
                lms = [{"x": lm.x, "y": lm.y, "z": lm.z, "visibility": lm.visibility} for lm in landmarks]
                
                # Bounding box estimate
                xs = [lm.x for lm in landmarks]
                ys = [lm.y for lm in landmarks]
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)
                
                pose_data = {
                    "xmin": xmin, "ymin": ymin,
                    "width": xmax - xmin, "height": ymax - ymin,
                    "landmarks": lms,
                    "_type": "graphics",
                    "shape": "polygon",
                    "pts": [[lm.x, lm.y] for lm in landmarks],
                    "r": 0, "g": 255, "b": 255, "thickness": 2
                }
                pose_list.append(pose_data)
                if not main_pose: main_pose = pose_data

        return {
            "main": image,
            "pose_list": pose_list,
            "data": main_pose
        }
