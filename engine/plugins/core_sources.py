import cv2
import numpy as np
import base64
import os
from registry import vision_node, NodeProcessor

def _load_image_robust(path):
    """Load any image file to uint8 BGR. Tries cv2 then PIL fallback."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    try:
        from PIL import Image as _PILImage
        _PIL_AVAILABLE = True
    except ImportError:
        _PIL_AVAILABLE = False
        
    if img is None and _PIL_AVAILABLE:
        try:
            pil = _PILImage.open(path)
            img = np.array(pil)
        except Exception:
            return None
    if img is None: return None
    if img.dtype != np.uint8:
        flat = img[:, :, 0] if img.ndim == 3 else img
        lo, hi = float(np.nanmin(flat)), float(np.nanmax(flat))
        span = hi - lo if hi != lo else 1.0
        img = np.clip((img.astype(np.float32) - lo) / span, 0.0, 1.0)
        img = (img * 255).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 1:
        img = cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

@vision_node(
    type_id="input_webcam",
    label="Webcam",
    category='input',
    icon="Camera",
    description="Captures live video feed from your system camera.",
    inputs=[],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "width", "color": "scalar"},
        {"id": "height", "color": "scalar"},
        {"id": "fps", "color": "scalar"}
    ],
    params=[
        {"id": "device_index", "label": "Device Index", "type": "int", "default": 0},
        {"id": "width", "label": "Width", "type": "int", "default": 0},
        {"id": "height", "label": "Height", "type": "int", "default": 0},
        {"id": "fps", "label": "FPS", "type": "int", "default": 0}
    ]
)
class WebcamInput(NodeProcessor):
    def __init__(self, engine=None):
        self.engine = engine
        self._applied = {}

    def process(self, inputs, params):
        idx = int(params.get('device_index', 0))
        if self.engine and self.engine.current_cap_index != idx:
            self.engine.switch_camera(idx)
            self._applied = {}
        cap = self.engine.cap if self.engine else None
        if cap:
            for prop, key in ((cv2.CAP_PROP_FRAME_WIDTH, 'width'), (cv2.CAP_PROP_FRAME_HEIGHT, 'height'), (cv2.CAP_PROP_FPS, 'fps')):
                val = int(params.get(key, 0))
                if val > 0 and self._applied.get(key) != val:
                    cap.set(prop, val)
                    self._applied[key] = val
            aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            af = cap.get(cv2.CAP_PROP_FPS)
            return {"main": inputs.get('raw_frame'), "width": aw, "height": ah, "fps": round(af, 1)}
        return {"main": None, "width": 0, "height": 0, "fps": 0}

@vision_node(
    type_id="input_image",
    label="Image File",
    category='input',
    icon="Image",
    description="Loads a static image from your local drive.",
    inputs=[],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "width", "color": "scalar"},
        {"id": "height", "color": "scalar"}
    ],
    params=[{"id": "path", "label": "File Path", "type": "string", "default": "samples/car.jpg"}]
)
class ImageInput(NodeProcessor):
    def __init__(self, engine=None):
        self.last_path = ""
        self.cached_img = None
    def process(self, inputs, params):
        path = params.get('path', '')
        if not path: return {"main": None}
        full_path = os.path.abspath(os.path.expanduser(path))
        if full_path != self.last_path:
            img = _load_image_robust(full_path)
            if img is not None:
                self.cached_img = img
                self.last_path = full_path
        if self.cached_img is not None:
             h, w = self.cached_img.shape[:2]
             out = {"main": self.cached_img, "width": w, "height": h}
             try:
                sc = 120 / h
                preview_img = cv2.resize(self.cached_img, (int(w * sc), 120))
                _, buf = cv2.imencode('.jpg', preview_img, [cv2.IMWRITE_JPEG_QUALITY, 50])
                out["preview"] = base64.b64encode(buf).decode('utf-8')
             except Exception: pass
             return out
        return {"main": None}

@vision_node(
    type_id="input_movie",
    label="Movie File",
    category='input',
    icon="Film",
    description="Plays a video file with playback and scrubbing controls.",
    inputs=[],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "frame", "color": "scalar"},
        {"id": "total_frames", "color": "scalar"}
    ],
    params=[
        {"id": "path", "label": "File Path", "type": "string", "default": "samples/face.mp4"},
        {"id": "playing", "label": "Playing", "type": "bool", "default": False},
        {"id": "scrub_index", "label": "Frame", "type": "int", "default": 0}
    ]
)
class MovieInput(NodeProcessor):
    def __init__(self, engine=None):
        self.last_path = ""
        self.cap = None
        self.total_frames = 0
    def process(self, inputs, params):
        path = params.get('path', '')
        if not path: return {"main": None}
        full_path = os.path.abspath(os.path.expanduser(path))
        if full_path != self.last_path:
            if self.cap: self.cap.release()
            self.cap = cv2.VideoCapture(full_path)
            if self.cap.isOpened():
                self.last_path = full_path
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not self.cap or not self.cap.isOpened(): return {"main": None}
        playing = params.get('playing', False)
        if playing:
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
        else:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(params.get('scrub_index', 0)))
            ret, frame = self.cap.read()
        cur = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        return {"main": frame if ret else None, "frame": cur, "total_frames": self.total_frames}

@vision_node(
    type_id="input_solid_color",
    label="Solid Color",
    category='input',
    icon="Palette",
    description="Generates an image of a custom solid color.",
    inputs=[],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "color", "label": "Color", "type": "color", "default": "#ff0000"},
        {"id": "width", "label": "Width", "type": "int", "default": 640},
        {"id": "height", "label": "Height", "type": "int", "default": 480}
    ]
)
class SolidColorNode(NodeProcessor):
    def process(self, inputs, params):
        hex_color = str(params.get('color', '#ff0000')).lstrip('#')
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except (ValueError, IndexError):
            r, g, b = 255, 0, 0
        w, h = int(params.get('width', 640)), int(params.get('height', 480))
        img = np.full((h, w, 3), (b, g, r), dtype=np.uint8)
        return {"main": img}
