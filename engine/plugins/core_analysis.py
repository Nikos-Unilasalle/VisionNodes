import cv2
import numpy as np
import os
import urllib.request
from registry import vision_node, NodeProcessor

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

_FLOW_PRESETS = [
    {'pyr_scale': 0.5, 'levels': 3, 'winsize': 15, 'iterations': 3, 'poly_n': 5, 'poly_sigma': 1.2},   # 0: Standard
    {'pyr_scale': 0.5, 'levels': 5, 'winsize': 31, 'iterations': 7, 'poly_n': 7, 'poly_sigma': 1.5},   # 1: Précis / Lent
    {'pyr_scale': 0.5, 'levels': 2, 'winsize': 7, 'iterations': 3, 'poly_n': 5, 'poly_sigma': 1.1},    # 2: Rapide
    {'pyr_scale': 0.5, 'levels': 5, 'winsize': 25, 'iterations': 5, 'poly_n': 7, 'poly_sigma': 1.5},   # 3: Haute qualité
    {'pyr_scale': 0.5, 'levels': 2, 'winsize': 10, 'iterations': 2, 'poly_n': 5, 'poly_sigma': 1.1},   # 4: Performance
]

@vision_node(
    type_id="analysis_flow",
    label="Optical Flow",
    category='detect',
    icon="Wind",
    description="Analyzes movement between frames using Farneback algorithm.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "data", "color": "any"}
    ],
    params=[
        {"id": "preset", "label": "Preset", "type": "enum", "options": ['Standard', 'Précis / Lent', 'Rapide', 'Haute qualité', 'Performance', 'Personnalisé'], "default": 0},
        {"id": "pyr_scale", "label": "Pyramid Scale", "type": "float", "default": 0.5},
        {"id": "levels", "label": "Levels", "type": "int", "default": 3},
        {"id": "winsize", "label": "Win Size", "type": "int", "default": 15},
        {"id": "iterations", "label": "Iterations", "type": "int", "default": 3},
        {"id": "poly_n", "label": "Poly N", "type": "int", "default": 5},
        {"id": "poly_sigma", "label": "Poly Sigma", "type": "float", "default": 1.2}
    ]
)
class OpticalFlowNode(NodeProcessor):
    def __init__(self, engine=None):
        super().__init__()
        self.prev = None
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        preset_idx = int(params.get('preset', 0))
        if preset_idx < len(_FLOW_PRESETS):
            pv = _FLOW_PRESETS[preset_idx]
            pyr_scale = pv['pyr_scale']
            levels = pv['levels']
            winsize = pv['winsize']
            iterations = pv['iterations']
            poly_n = pv['poly_n']
            poly_sigma = pv['poly_sigma']
        else:
            pyr_scale = float(params.get('pyr_scale', 0.5))
            levels = int(params.get('levels', 3))
            winsize = int(params.get('winsize', 15))
            iterations = int(params.get('iterations', 3))
            poly_n = int(params.get('poly_n', 5))
            poly_sigma = float(params.get('poly_sigma', 1.2))
        flow = None
        if self.prev is not None and self.prev.shape == gray.shape:
            flow = cv2.calcOpticalFlowFarneback(
                self.prev, gray, None,
                pyr_scale, levels, winsize, iterations, poly_n, poly_sigma, 0
            )
        self.prev = gray
        return {"main": img, 'data': flow}

@vision_node(
    type_id="analysis_flow_viz",
    label="Flow Viz",
    category='visualize',
    icon="Eye",
    description="Colorized visualization of optical flow data.",
    inputs=[{"id": "data", "color": "any"}],
    outputs=[{"id": "main", "color": "image"}]
)
class FlowVizNode(NodeProcessor):
    def process(self, inputs, params):
        flow = inputs.get('data')
        if flow is None: return {"main": None}
        h, w = flow.shape[:2]
        hsv = np.zeros((h, w, 3), dtype=np.uint8)
        hsv[..., 1] = 255
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv[..., 0] = ang * 180 / np.pi / 2
        hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        return {"main": cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)}

@vision_node(
    type_id="analysis_monitor",
    label="Universal Monitor",
    category='detect',
    icon="Target",
    description="Universal measurement tool for flow, area, brightness, and counting objects.",
    inputs=[
        {"id": "data", "color": "data"},
        {"id": "image", "color": "image"},
        {"id": "mask", "color": "mask"}
    ],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "scalar", "color": "scalar"}
    ],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Auto", "Flux (Motion)", "Area (Mask)", "Brightness", "Red Channel", "Green Channel", "Blue Channel", "Count (Elements)", "Scalar Value"], "default": 0},
        {"id": "scale", "label": "Scale Factor", "type": "scalar", "min": 0, "max": 1000, "default": 1.0},
        {"id": "offset", "label": "Offset", "type": "scalar", "min": -1000, "max": 1000, "default": 0.0},
        {"id": "precision", "label": "Decimals", "type": "scalar", "min": 0, "max": 5, "default": 3}
    ]
)
class UniversalMonitorNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        img = inputs.get('image', inputs.get('main'))
        mask = inputs.get('mask')
        mode = int(params.get('mode', 0))
        scale = float(params.get('scale', 1.0))
        offset = float(params.get('offset', 0.0))
        precision = int(params.get('precision', 3))
        val = 0.0
        unit = ""
        if mode == 0:
            if data is not None:
                if isinstance(data, np.ndarray):
                    if len(data.shape) == 3 and data.shape[2] == 2: mode = 1
                    else: mode = 3
                elif isinstance(data, (list, tuple)): mode = 7
                elif isinstance(data, (int, float)): mode = 8
                else: mode = 3
            elif mask is not None: mode = 2
            elif img is not None: mode = 3
        if mode == 1:
            flow = data if isinstance(data, np.ndarray) and len(data.shape) == 3 and data.shape[2] == 2 else None
            if flow is not None:
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                if mask is not None:
                    mask_res = cv2.resize(mask, (mag.shape[1], mag.shape[0]))
                    if len(mask_res.shape) == 3: mask_res = cv2.cvtColor(mask_res, cv2.COLOR_BGR2GRAY)
                    mag = mag[mask_res > 0]
                val = float(np.mean(mag)) if mag.size > 0 else 0.0
                unit = "flux"
        elif mode == 2:
            m = mask if mask is not None else data
            if m is not None and isinstance(m, np.ndarray):
                if len(m.shape) == 3: m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
                val = float(cv2.countNonZero(m))
                unit = "px"
        elif mode in [3, 4, 5, 6]:
            im = img if img is not None else data
            if im is not None and isinstance(im, np.ndarray):
                if len(im.shape) == 2: val = float(np.mean(im))
                else:
                    if mode == 3: val = float(np.mean(im))
                    elif mode == 4: val = float(np.mean(im[..., 2]))
                    elif mode == 5: val = float(np.mean(im[..., 1]))
                    elif mode == 6: val = float(np.mean(im[..., 0]))
                unit = "lvl"
        elif mode == 7:
            if isinstance(data, (list, tuple)): val = float(len(data))
            elif isinstance(data, dict): val = 1.0
            elif isinstance(data, (int, float)): val = float(data)
            unit = "items"
        elif mode == 8:
            if isinstance(data, (int, float)): val = float(data)
            elif isinstance(data, str):
                try: val = float(data)
                except: val = 0.0
            unit = ""
        final_val = (val * scale) + offset
        txt = f"{final_val:.{precision}f} {unit}".strip()
        res = img if img is not None else mask
        if res is not None and len(res.shape) == 2: res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)
        if res is not None:
            cv2.putText(res, txt, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
        return {
            "main": res, 
            "scalar": final_val, 
            "data_out": final_val,
            "display_text": txt
        }

@vision_node(
    type_id="analysis_face_mp",
    label="Face Tracker",
    category='detect',
    icon="User",
    description="Detects and tracks faces and facial landmarks (MediaPipe).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "faces_list", "color": "list"},
        {"id": "main", "color": "image"}
    ],
    params=[
        {"id": "max_faces", "label": "Max Faces", "type": "int", "default": 3, "min": 1, "max": 10}
    ]
)
class FaceDetectionNode(NodeProcessor):
    def __init__(self, engine=None):
        super().__init__()
        self.detector = None
        self.options = None
    def _lazy_init(self, max_faces=3):
        model_path = "face_landmarker.task"
        if not os.path.exists(model_path):
            try:
                urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", model_path)
            except Exception: return
        if not AI_AVAILABLE: return
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.FaceLandmarkerOptions(base_options=base_options, num_faces=max_faces)
        self.detector = vision.FaceLandmarker.create_from_options(self.options)
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"faces_list": [], "main": None}
        if not AI_AVAILABLE: return {"faces_list": [], "main": image}
        max_faces = int(params.get('max_faces', 3))
        if self.detector is None or (self.options and self.options.num_faces != max_faces):
            self._lazy_init(max_faces)
        if self.detector is None: return {"faces_list": [], "main": image}
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        faces_list = []
        if getattr(results, 'face_landmarks', None):
            for face_landmarks in results.face_landmarks:
                x_min, y_min = min([lm.x for lm in face_landmarks]), min([lm.y for lm in face_landmarks])
                x_max, y_max = max([lm.x for lm in face_landmarks]), max([lm.y for lm in face_landmarks])
                lms = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in face_landmarks]
                face_data = {
                    "xmin": x_min, "ymin": y_min, "width": x_max - x_min, "height": y_max - y_min,
                    "landmarks": lms, "label": "face", "_type": "graphics", "shape": "rect", "pts": [[x_min, y_min], [x_max, y_max]], "color": "#00ff00"
                }
                faces_list.append(face_data)
        return {"faces_list": faces_list, "main": image}

@vision_node(
    type_id="analysis_hand_mp",
    label="Hand Tracker",
    category='detect',
    icon="Hand",
    description="Detects and tracks hands and joints (MediaPipe).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "hands_list", "color": "list"},
        {"id": "main", "color": "image"}
    ],
    params=[
        {"id": "max_hands", "label": "Max Hands", "type": "int", "default": 2, "min": 1, "max": 10}
    ]
)
class HandDetectionNode(NodeProcessor):
    def __init__(self, engine=None):
        super().__init__()
        self.detector = None
        self.options = None
    def _lazy_init(self, max_hands=2):
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            try:
                urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task", model_path)
            except Exception: return
        if not AI_AVAILABLE: return
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=max_hands)
        self.detector = vision.HandLandmarker.create_from_options(self.options)
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"hands_list": [], "main": None}
        if not AI_AVAILABLE: return {"hands_list": [], "main": image}
        max_hands = int(params.get('max_hands', 2))
        if self.detector is None or (self.options and self.options.num_hands != max_hands):
            self._lazy_init(max_hands)
        if self.detector is None: return {"hands_list": [], "main": image}
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        hands_list = []
        if getattr(results, 'hand_landmarks', None):
            for hand_landmarks in results.hand_landmarks:
                x_min, y_min = min([lm.x for lm in hand_landmarks]), min([lm.y for lm in hand_landmarks])
                x_max, y_max = max([lm.x for lm in hand_landmarks]), max([lm.y for lm in hand_landmarks])
                lms = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in hand_landmarks]
                hand_data = {
                    "xmin": x_min, "ymin": y_min, "width": x_max - x_min, "height": y_max - y_min,
                    "landmarks": lms, "label": "hand", "_type": "graphics", "shape": "polygon", "pts": [[lm.x, lm.y] for lm in hand_landmarks], "color": "#ff00ff"
                }
                hands_list.append(hand_data)
        return {"hands_list": hands_list, "main": image}
