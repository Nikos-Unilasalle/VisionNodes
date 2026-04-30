import sys
import subprocess

def check_and_install_dependencies():
    # Map package names to import names
    deps = {
        "opencv-python": "cv2",
        "mediapipe": "mediapipe",
        "websockets": "websockets",
        "numpy": "numpy",
        "ultralytics": "ultralytics",
        "torch": "torch",
        "pytesseract": "pytesseract",
        "easyocr": "easyocr",
        "rasterio": "rasterio",
        "pyproj": "pyproj",
        "earthengine-api": "ee",
        "geopy": "geopy",
        "librosa": "librosa",
        "soundfile": "soundfile",
    }
    
    missing = []
    for pkg, import_name in deps.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
            
    if missing:
        print(f"\n📦 VISION NODES :: Missing dependencies: {missing}")
        print("🚀 For a clean experience, please run: npm run setup\n")
        print("Trying auto-installation... please wait.\n")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print("\n✅ Installation complete. Starting engine...\n")
        except Exception as e:
            print(f"\n❌ Auto-install failed: {e}")
            print("👉 Please run manually: npm run setup or pip install -r engine/requirements.txt\n")

# Run bootstrap before other imports
check_and_install_dependencies()

import asyncio
import json
import cv2
import base64
import numpy as np
import websockets
import time
import os
import urllib.request
try:
    from PIL import Image as _PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
from registry import (
    NODE_SCHEMAS, NODE_CLASS_REGISTRY,
    _notification_queue, send_notification,
    vision_node, NodeProcessor, topological_sort,
)

# Optimized for Linux/Arch, use CAP_ANY as primary to avoid V4L2 index errors
CAP_BACKEND = cv2.CAP_ANY

def list_available_cameras():
    index = 0
    arr = []
    while index < 8:
        # Try primary backend first, then CAP_V4L2 as fallback specifically for Linux
        cap = cv2.VideoCapture(index, CAP_BACKEND)
        if not cap.isOpened():
            cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
            
        if cap.isOpened():
            arr.append(index)
            cap.release()
        index += 1
    return arr

# --- AI Setup (MediaPipe) ---
MODEL_PATH = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

def download_model():
    if not os.path.exists(MODEL_PATH):
        try:
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        except Exception as e:
            print(f"[Engine] Failed to download face model: {e}")

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    download_model()
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    detector_options = vision.FaceLandmarkerOptions(base_options=base_options, num_faces=10)
    detector = vision.FaceLandmarker.create_from_options(detector_options)
    AI_AVAILABLE = True
except Exception as e:
    AI_AVAILABLE = False
    print(f"AI Error: {e}")

# --- Plugin System ---

def load_plugins():
    import importlib.util
    import glob
    import sys

    engine_dir = os.path.dirname(os.path.abspath(__file__))
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)

    if hasattr(sys, '_MEIPASS'):
        plugin_dir = os.path.join(sys._MEIPASS, "engine", "plugins")
    else:
        plugin_dir = os.path.join(engine_dir, "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    for file in glob.glob(os.path.join(plugin_dir, "*.py")):
        if os.path.basename(file) == "__init__.py": continue
        module_name = f"plugins.{os.path.basename(file)[:-3]}"
        spec = importlib.util.spec_from_file_location(module_name, file)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            print(f"[Plugins] Loaded: {module_name}")
        except Exception as e:
            print(f"[Plugins] Failed to load {module_name}: {e}")

# --- INPUT UNITS ---
@vision_node(
    type_id="input_webcam",
    label="Webcam",
    category="src",
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
        if self.engine.current_cap_index != idx:
            self.engine.switch_camera(idx)
            self._applied = {}
        cap = self.engine.cap
        for prop, key in ((cv2.CAP_PROP_FRAME_WIDTH, 'width'), (cv2.CAP_PROP_FRAME_HEIGHT, 'height'), (cv2.CAP_PROP_FPS, 'fps')):
            val = int(params.get(key, 0))
            if val > 0 and self._applied.get(key) != val:
                cap.set(prop, val)
                self._applied[key] = val
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        af = cap.get(cv2.CAP_PROP_FPS)
        return {"main": inputs.get('raw_frame'), "width": aw, "height": ah, "fps": round(af, 1)}

def _load_image_robust(path):
    """Load any image file to uint8 BGR. Tries cv2 then PIL fallback."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None and _PIL_AVAILABLE:
        try:
            pil = _PILImage.open(path)
            img = np.array(pil)
            print(f"[Engine] PIL loaded {path} mode={pil.mode} dtype={img.dtype}")
        except Exception as e:
            print(f"[Engine] PIL fallback failed: {e}")
            return None
    if img is None:
        return None
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
    type_id="input_image",
    label="Image File",
    category="src",
    icon="Image",
    description="Loads a static image from your local drive.",
    inputs=[],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "width", "color": "scalar"},
        {"id": "height", "color": "scalar"},
        {"id": "depth", "color": "string"}
    ],
    params=[
        {"id": "path", "label": "File Path", "type": "string", "default": "samples/car.jpg"}
    ]
)
class ImageInput(NodeProcessor):
    def __init__(self):
        self.last_path = ""
        self.cached_img = None
    def process(self, inputs, params):
        path = params.get('path', '')
        if not path: return {"main": None}

        # Absolute path resolution
        full_path = os.path.abspath(os.path.expanduser(path))

        if not os.path.exists(full_path):
            # Relative to project root (parent of engine dir)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt_root = os.path.join(project_root, path)
            if os.path.exists(alt_root):
                full_path = alt_root
            else:
                # Relative to cwd/public
                alt_public = os.path.abspath(os.path.join(os.getcwd(), "public", path))
                if os.path.exists(alt_public):
                    full_path = alt_public
        
        if full_path != self.last_path:
            print(f"[Engine] Loading Image: {full_path}")
            img = _load_image_robust(full_path)
            if img is not None:
                self.cached_img = img
                self.last_path = full_path
            else:
                print(f"[Error] Failed to load image at: {full_path}")
                return {"main": None}

        if self.cached_img is not None:
             h, w = self.cached_img.shape[:2]
             out = {"main": self.cached_img, "width": w, "height": h, "depth": "8-bit"}
             try:
                 sc = 120 / h
                 preview_w = int(w * sc)
                 if preview_w > 0:
                    preview_img = cv2.resize(self.cached_img, (preview_w, 120))
                    _, buf = cv2.imencode('.jpg', preview_img, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    out["preview"] = base64.b64encode(buf).decode('utf-8')
             except Exception as e:
                 print(f"[Warning] Preview generation failed: {e}")
             return out
        
        return {"main": None}

@vision_node(
    type_id="input_movie",
    label="Movie File",
    category="src",
    icon="Film",
    description="Plays a video file with playback and scrubbing controls.",
    inputs=[],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "frame", "color": "scalar"},
        {"id": "total_frames", "color": "scalar"},
        {"id": "fps", "color": "scalar"},
        {"id": "duration", "color": "scalar"}
    ],
    params=[
        {"id": "path", "label": "File Path", "type": "string", "default": "samples/face.mp4"},
        {"id": "playing", "label": "Playing", "type": "bool", "default": False},
        {"id": "scrub_index", "label": "Frame", "type": "int", "default": 0},
        {"id": "start_frame", "label": "Start", "type": "int", "default": 0},
        {"id": "end_frame", "label": "End", "type": "int", "default": 0}
    ]
)
class MovieInput(NodeProcessor):
    def __init__(self):
        self.last_path = ""
        self.cap = None
        self.total_frames = 0
        self.current_frame = 0

    def process(self, inputs, params):
        path = params.get('path', '')
        if not path: return {"main": None}
        
        full_path = os.path.abspath(os.path.expanduser(path))
        
        if full_path != self.last_path:
            if self.cap: self.cap.release()
            print(f"[Engine] Attempting to open video: {full_path}")
            cap = cv2.VideoCapture(full_path)
            if cap.isOpened():
                self.cap = cap
                self.last_path = full_path
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.current_frame = 0
                print(f"[Success] Video opened. Total frames: {self.total_frames}")
            else:
                print(f"[Error] OpenCV could not open video: {full_path}")
                return {"main": None}
            
        if not self.cap or not self.cap.isOpened(): return {"main": None}
        
        playing = params.get('playing', False)
        scrub_index = int(params.get('scrub_index', 0))
        
        start_f = int(params.get('start_frame', 0))
        end_f = int(params.get('end_frame', self.total_frames - 1))
        if end_f < start_f: end_f = self.total_frames - 1

        if playing:
            self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            if self.current_frame < start_f or self.current_frame > end_f:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
            
            ret, frame = self.cap.read()
            if not ret: 
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
                ret, frame = self.cap.read()
            self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        else:
            # Constrain scrubbing to the trim range
            scrub_clamped = max(start_f, min(scrub_index, end_f))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, scrub_clamped)
            ret, frame = self.cap.read()
            self.current_frame = scrub_clamped
            
        # Generate a small preview for the UI
        preview_b64 = None
        if ret and frame is not None:
            try:
                h, w = frame.shape[:2]
                sc = 120 / h
                preview_w = int(w * sc)
                if preview_w > 0:
                    preview_img = cv2.resize(frame, (preview_w, 120))
                    _, buf = cv2.imencode('.jpg', preview_img, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    preview_b64 = base64.b64encode(buf).decode('utf-8')
            except Exception as e:
                print(f"[Engine] Preview encode error: {e}")

        vw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        vh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        vfps = self.cap.get(cv2.CAP_PROP_FPS)
        dur = round(self.total_frames / vfps, 1) if vfps > 0 else 0
        return {
            "main": frame if ret else None,
            "frame": self.current_frame,
            "total_frames": self.total_frames,
            "current_frame": self.current_frame,
            "preview": preview_b64,
            "filename": os.path.basename(full_path),
            "width": vw, "height": vh,
            "fps": round(vfps, 1), "duration": dur,
        }

@vision_node(
    type_id="input_solid_color",
    label="Solid Color",
    category="src",
    icon="Palette",
    description="Generates an image of a custom solid color.",
    inputs=[],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "r", "label": "Red", "type": "int", "default": 255, "min": 0, "max": 255},
        {"id": "g", "label": "Green", "type": "int", "default": 0, "min": 0, "max": 255},
        {"id": "b", "label": "Blue", "type": "int", "default": 0, "min": 0, "max": 255},
        {"id": "width", "label": "Width", "type": "int", "default": 640},
        {"id": "height", "label": "Height", "type": "int", "default": 480}
    ]
)
class SolidColorNode(NodeProcessor):
    def process(self, inputs, params):
        r, g, b = int(params.get('r', 255)), int(params.get('g', 0)), int(params.get('b', 0))
        w, h = int(params.get('width', 640)), int(params.get('height', 480))
        img = np.full((h, w, 3), (b, g, r), dtype=np.uint8)
        return {"main": img}

# --- FILTER UNITS ---
@vision_node(
    type_id="filter_canny",
    label="Canny Edge",
    category="filter",
    icon="Waves",
    description="Detects edges using the Canny algorithm.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "low", "label": "Low Threshold", "type": "int", "default": 100, "min": 0, "max": 1000},
        {"id": "high", "label": "High Threshold", "type": "int", "default": 200, "min": 0, "max": 1000}
    ]
)
class CannyFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return {"main": cv2.Canny(gray, int(params.get('low', 100)), int(params.get('high', 200)))}

@vision_node(
    type_id="filter_blur",
    label="Gaussian Blur",
    category="filter",
    icon="Waves",
    description="Applies a Gaussian blur to smooth the image.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "size", "label": "Kernel Size", "type": "int", "default": 5, "min": 1, "max": 51}
    ]
)
class BlurFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        s = int(params.get('size', 5))
        if s % 2 == 0: s += 1
        return {"main": cv2.GaussianBlur(img, (s, s), 0)}

@vision_node(
    type_id="filter_gray",
    label="Grayscale",
    category="filter",
    icon="Waves",
    description="Converts the image to grayscale.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}]
)
class GrayFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        res = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return {"main": res}

@vision_node(
    type_id="filter_threshold",
    label="Threshold",
    category="filter",
    icon="Waves",
    description="Separates the image into black and white based on intensity.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "mask", "color": "mask"}
    ],
    params=[
        {"id": "threshold", "label": "Threshold Value", "type": "int", "default": 127, "min": 0, "max": 255}
    ]
)
class ThresholdFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None, "mask": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, res = cv2.threshold(gray, int(params.get('threshold', 127)), 255, cv2.THRESH_BINARY)
        return {"main": res, "mask": res}

@vision_node(
    type_id="geom_flip",
    label="Flip",
    category="geom",
    icon="Move",
    description="Inverts the image horizontally or vertically.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "flip_mode", "label": "Flip (-1=Both, 0=Vertical, 1=Horizontal)", "type": "int", "default": 1, "min": -1, "max": 1, "step": 1}
    ]
)
class FlipNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        return {"main": cv2.flip(img, int(params.get('flip_mode', 1)))}

@vision_node(
    type_id="geom_resize",
    label="Resize",
    category="geom",
    icon="Scaling",
    description="Changes the image resolution or scaling.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "width", "color": "scalar"},
        {"id": "height", "color": "scalar"}
    ],
    params=[
        {"id": "mode", "label": "Resize Mode", "type": "enum", "options": ["Scale", "Absolute"], "default": 0},
        {"id": "scale", "label": "Scale Factor", "type": "float", "default": 1.0, "min": 0.01, "max": 10.0},
        {"id": "target_width", "label": "Width (px)", "type": "int", "default": 640},
        {"id": "target_height", "label": "Height (px)", "type": "int", "default": 480},
        {"id": "interpolation", "label": "Interpolation", "type": "enum", "options": ["Nearest", "Linear", "Cubic", "Lanczos"], "default": 1}
    ]
)
class ResizeNode(NodeProcessor):
    INTERP = [cv2.INTER_LINEAR, cv2.INTER_NEAREST, cv2.INTER_LINEAR,
              cv2.INTER_CUBIC, cv2.INTER_LANCZOS4, cv2.INTER_AREA]

    def process(self, inputs, params):
        img = inputs.get('image') or inputs.get('main')
        if img is None: return {"main": None}

        ih, iw = img.shape[:2]
        mode    = int(params.get('mode', 0))
        interp_idx = int(params.get('interp', 0))

        if interp_idx == 0:  # Auto: AREA for downscale, LINEAR for upscale
            auto_interp = None
        else:
            auto_interp = self.INTERP[min(interp_idx, len(self.INTERP) - 1)]

        if mode == 0:  # Scale
            sc = max(0.01, float(params.get('scale', 1.0)))
            ow, oh = max(1, int(iw * sc)), max(1, int(ih * sc))
        elif mode == 1:  # Fit Width
            ow = max(1, int(params.get('width', iw)))
            oh = max(1, int(ih * ow / iw))
        elif mode == 2:  # Fit Height
            oh = max(1, int(params.get('height', ih)))
            ow = max(1, int(iw * oh / ih))
        else:  # Exact W×H
            ow = max(1, int(params.get('width', iw)))
            oh = max(1, int(params.get('height', ih)))

        if auto_interp is None:
            auto_interp = cv2.INTER_AREA if (ow * oh < iw * ih) else cv2.INTER_LINEAR

        out = cv2.resize(img, (ow, oh), interpolation=auto_interp)
        return {"main": out, "width": ow, "height": oh}

# --- ANALYSIS & FLOW ---
@vision_node(
    type_id="analysis_flow",
    label="Optical Flow",
    category=["track", "signal"],
    icon="Wind",
    description="Analyzes movement between frames using Farneback algorithm.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "data", "color": "any"}
    ],
    params=[
        {"id": "pyr_scale", "label": "Pyramid Scale", "type": "float", "default": 0.5},
        {"id": "levels", "label": "Levels", "type": "int", "default": 3},
        {"id": "winsize", "label": "Win Size", "type": "int", "default": 15},
        {"id": "iterations", "label": "Iterations", "type": "int", "default": 3},
        {"id": "poly_n", "label": "Poly N", "type": "int", "default": 5},
        {"id": "poly_sigma", "label": "Poly Sigma", "type": "float", "default": 1.2}
    ]
)
class OpticalFlowNode(NodeProcessor):
    def __init__(self): self.prev = None
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        flow = None
        if self.prev is not None and self.prev.shape == gray.shape:
            flow = cv2.calcOpticalFlowFarneback(
                self.prev, gray, None, 
                float(params.get('pyr_scale', 0.5)), int(params.get('levels', 3)), 
                int(params.get('winsize', 15)), int(params.get('iterations', 3)), 
                int(params.get('poly_n', 5)), float(params.get('poly_sigma', 1.2)), 0
            )
        self.prev = gray
        return {"main": img, "data": flow}

@vision_node(
    type_id="analysis_flow_viz",
    label="Flow Viz",
    category="visualize",
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
    category="analysis",
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
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Auto", "Flux (Motion)", "Area (Mask)", "Brightness", "Red Channel", "Green Channel", "Blue Channel", "Count (Elements)"], "default": 0},
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
        
        # 1. Determine Mode if Auto
        if mode == 0: # Auto
            if data is not None:
                if isinstance(data, np.ndarray):
                    if len(data.shape) == 3 and data.shape[2] == 2: mode = 1 # Flux
                    else: mode = 3 # Brightness (approx)
                elif isinstance(data, (list, tuple)): mode = 7 # Count
                elif isinstance(data, (int, float)): mode = 8 # Scalar
                else: mode = 3 
            elif mask is not None: mode = 2 # Area
            elif img is not None: mode = 3 # Brightness
        
        # 2. Execution
        if mode == 1: # Flux (Motion)
            flow = data if isinstance(data, np.ndarray) and len(data.shape) == 3 and data.shape[2] == 2 else None
            if flow is not None:
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                if mask is not None:
                    # Apply mask if provided
                    mask_res = cv2.resize(mask, (mag.shape[1], mag.shape[0]))
                    if len(mask_res.shape) == 3: mask_res = cv2.cvtColor(mask_res, cv2.COLOR_BGR2GRAY)
                    mag = mag[mask_res > 0]
                val = float(np.mean(mag)) if mag.size > 0 else 0.0
                unit = "flux"
        
        elif mode == 2: # Area (Mask)
            m = mask if mask is not None else data
            if m is not None and isinstance(m, np.ndarray):
                if len(m.shape) == 3: m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
                val = float(cv2.countNonZero(m))
                unit = "px"
        
        elif mode in [3, 4, 5, 6]: # Brightness or Color Channels
            im = img if img is not None else data
            if im is not None and isinstance(im, np.ndarray):
                if len(im.shape) == 2: # Grayscale
                    val = float(np.mean(im))
                else: # BGR
                    if mode == 3: val = float(np.mean(im)) # Global
                    elif mode == 4: val = float(np.mean(im[..., 2])) # R
                    elif mode == 5: val = float(np.mean(im[..., 1])) # G
                    elif mode == 6: val = float(np.mean(im[..., 0])) # B
                unit = "lvl"
        
        elif mode == 7: # Count (Elements)
            if isinstance(data, (list, tuple)):
                val = float(len(data))
            elif isinstance(data, dict):
                val = 1.0 # One object
            elif isinstance(data, (int, float)):
                val = float(data) # Treat scalar as its value
            else:
                val = 0.0
            unit = "items"
        
        elif mode == 8: # Scalar Value
            if isinstance(data, (int, float)):
                val = float(data)
            elif isinstance(data, str):
                try: val = float(data)
                except: val = 0.0
            unit = ""
            
        # 3. Post-process
        final_val = (val * scale) + offset
        
        return {
            "main": img if img is not None else mask,
            "scalar": final_val,
            "display_text": f"{final_val:.{precision}f} {unit}".strip()
        }

@vision_node(
    type_id="analysis_face_mp",
    label="Face Tracker",
    category="detect",
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
    def __init__(self):
        super().__init__()
        self.detector = None
        self.options = None
        # Lazy initialization
    def _lazy_init(self, max_faces=3):
        import os, urllib.request
        model_path = "face_landmarker.task"
        if not os.path.exists(model_path):
            try:
                urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", model_path)
            except Exception as e:
                print(f"[Engine] Failed to download face_landmarker: {e}")
                return
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.FaceLandmarkerOptions(base_options=base_options, num_faces=max_faces)
        self.detector = vision.FaceLandmarker.create_from_options(self.options)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"faces_list": [], "main": None}
        max_faces = int(params.get('max_faces', 3))
        if self.detector is None or (self.options and self.options.num_faces != max_faces):
            self._lazy_init(max_faces)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        faces_list = []
        if getattr(results, 'face_landmarks', None):
            for face_landmarks in results.face_landmarks:
                x_min, y_min = min([lm.x for lm in face_landmarks]), min([lm.y for lm in face_landmarks])
                x_max, y_max = max([lm.x for lm in face_landmarks]), max([lm.y for lm in face_landmarks])
                lms = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in face_landmarks]
                face_data = {
                    "xmin": max(0, x_min), "ymin": max(0, y_min), "width": min(1-x_min, x_max - x_min), "height": min(1-y_min, y_max - y_min),
                    "landmarks": lms, "label": "face", "_type": "graphics", "shape": "rect", "pts": [[max(0, x_min), max(0, y_min)], [min(1, x_max), min(1, y_max)]], "color": "#00ff00"
                }
                faces_list.append(face_data)
        out = {"faces_list": faces_list, "main": image}
        for i, face in enumerate(faces_list): out[f"face_{i}"] = face
        return out

@vision_node(
    type_id="analysis_hand_mp",
    label="Hand Tracker",
    category="detect",
    icon="Zap",
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
    def __init__(self):
        super().__init__()
        self.detector = None
        self.options = None
        # Lazy initialization
    def _lazy_init(self, max_hands=2):
        import os, urllib.request
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            try:
                urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task", model_path)
            except Exception as e:
                print(f"[Engine] Failed to download hand_landmarker: {e}")
                return
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=max_hands)
        self.detector = vision.HandLandmarker.create_from_options(self.options)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"hands_list": [], "main": None}
        max_hands = int(params.get('max_hands', 2))
        if self.detector is None or (self.options and self.options.num_hands != max_hands):
            self._lazy_init(max_hands)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        hands_list = []
        if getattr(results, 'hand_landmarks', None):
            for hand_landmarks in results.hand_landmarks:
                x_min, y_min = min([lm.x for lm in hand_landmarks]), min([lm.y for lm in hand_landmarks])
                x_max, y_max = max([lm.x for lm in hand_landmarks]), max([lm.y for lm in hand_landmarks])
                lms = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in hand_landmarks]
                hand_data = {
                    "xmin": max(0, x_min), "ymin": max(0, y_min), "width": min(1-x_min, x_max - x_min), "height": min(1-y_min, y_max - y_min),
                    "landmarks": lms, "label": "hand", "_type": "graphics", "shape": "polygon", "pts": [[lm.x, lm.y] for lm in hand_landmarks], "color": "#ff00ff"
                }
                hands_list.append(hand_data)
        out = {"hands_list": hands_list, "main": image}
        for i, hand in enumerate(hands_list): out[f"hand_{i}"] = hand
        return out

@vision_node(
    type_id="filter_color_mask",
    label="Color Mask",
    category="mask",
    icon="Layers",
    description="Creates a mask by isolating a range of colors (HSV or RGB distance).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["HSV Range", "RGB Distance"], "default": 0},
        {"id": "h_min", "label": "H Min", "type": "int", "default": 0, "min": 0, "max": 179},
        {"id": "h_max", "label": "H Max", "type": "int", "default": 179, "min": 0, "max": 179},
        {"id": "s_min", "label": "S Min", "type": "int", "default": 0, "min": 0, "max": 255},
        {"id": "s_max", "label": "S Max", "type": "int", "default": 255, "min": 0, "max": 255},
        {"id": "v_min", "label": "V Min", "type": "int", "default": 0, "min": 0, "max": 255},
        {"id": "v_max", "label": "V Max", "type": "int", "default": 255, "min": 0, "max": 255},
        {"id": "r", "label": "Target R", "type": "int", "default": 128},
        {"id": "g", "label": "Target G", "type": "int", "default": 128},
        {"id": "b", "label": "Target B", "type": "int", "default": 128},
        {"id": "threshold", "label": "RGB Threshold", "type": "int", "default": 30}
    ]
)
class ColorMaskNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"mask": None}
        if len(image.shape) == 2 or image.shape[2] == 1: image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        mode = int(params.get('mode', 0))
        if mode == 1:
            r = int(params.get('r', 128))
            g = int(params.get('g', 128))
            b = int(params.get('b', 128))
            thresh = int(params.get('threshold', 30))
            target = np.array([b, g, r], dtype=np.float32)
            diff = image.astype(np.float32) - target
            dist = np.sqrt(np.sum(diff ** 2, axis=2))
            mask = (dist <= thresh).astype(np.uint8) * 255
        else:
            h_min, h_max = params.get('h_min', 0), params.get('h_max', 179)
            s_min, s_max = params.get('s_min', 0), params.get('s_max', 255)
            v_min, v_max = params.get('v_min', 0), params.get('v_max', 255)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([h_max, s_max, v_max]))
        return {"mask": mask}

@vision_node(
    type_id="filter_morphology",
    label="Morphology",
    category="mask",
    icon="Layers",
    description="Dilation or erosion operations to clean up masks.",
    inputs=[{"id": "mask", "color": "mask"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "operation", "label": "Operation", "type": "enum", "options": ["Dilation", "Erosion"], "default": 0},
        {"id": "size", "label": "Kernel Size", "type": "int", "default": 5, "min": 1, "max": 51}
    ]
)
class MorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask', inputs.get('image'))
        if mask is None: return {"mask": None}
        op, size = params.get('operation', 0), int(params.get('size', 5))
        kernel = np.ones((size, size), np.uint8)
        res = cv2.dilate(mask, kernel, iterations=1) if op == 0 else cv2.erode(mask, kernel, iterations=1)
        return {"mask": res}

@vision_node(
    type_id='draw_overlay',
    label='Visual Overlay',
    category='draw',
    icon='PenTool',
    description="Draws graphical elements (from Draw Text, trackers, etc.) over an image. Connect graphics to the 'data' inputs.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'data', 'color': 'any'},
        {'id': 'data_2', 'color': 'any'},
        {'id': 'data_3', 'color': 'any'},
        {'id': 'data_4', 'color': 'any'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}]
)
class OverlayNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image', inputs.get('main', inputs.get('raw_frame')))
        if img is None: return {"main": None}
        res = img.copy()
        if len(res.shape) == 2: res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)
        h, w = res.shape[:2]
        col, thick = (0, 255, 0), 2
        
        # Scan ALL inputs for graphics or detection data
        for key, data in inputs.items():
            if data is None: continue
            if isinstance(data, dict):
                if data.get('_type') == 'graphics': 
                    self._draw_graphics(res, data, w, h, col, thick)
                elif 'xmin' in data: 
                    cv2.rectangle(res, (int(data['xmin']*w), int(data['ymin']*h)), (int((data['xmin']+data['width'])*w), int((data['ymin']+data['height'])*h)), col, thick)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if item.get('_type') == 'graphics': 
                            self._draw_graphics(res, item, w, h, col, thick)
                        elif 'xmin' in item: 
                            cv2.rectangle(res, (int(item['xmin']*w), int(item['ymin']*h)), (int((item['xmin']+item['width'])*w), int((item['ymin']+item['height'])*h)), col, thick)
            elif isinstance(data, (float, int)) and key != 'raw_frame': 
                cv2.putText(res, f"{key}: {data:.4f}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, col, thick)
        return {"main": res}
    def _draw_graphics(self, img, data, w, h, default_col, default_thick):
        shape, pts, rel = data.get('shape', 'point'), data.get('pts', []), data.get('relative', True)
        color = default_col
        if 'color' in data and data['color'].startswith('#'):
            hex_col = data['color'].lstrip('#')
            if len(hex_col) == 6:
                r, g, b = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
                color = (b, g, r)
        thick = int(data.get('thickness', default_thick))
        scaled_pts = [(int(p[0]*w), int(p[1]*h)) if rel else (int(p[0]), int(p[1])) for p in pts]
        if shape == 'point' and len(scaled_pts) > 0: cv2.circle(img, scaled_pts[0], max(1, thick), color, -1)
        elif shape == 'line' and len(scaled_pts) >= 2: cv2.line(img, scaled_pts[0], scaled_pts[1], color, max(1, thick))
        elif shape == 'rect' and len(scaled_pts) >= 2:
            cv2.rectangle(img, scaled_pts[0], scaled_pts[1], color, -1 if data.get('fill') else max(1, thick))
            if 'label' in data: cv2.putText(img, data['label'], (scaled_pts[0][0], scaled_pts[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif shape == 'polygon' and len(scaled_pts) > 2:
            pts_arr = np.array(scaled_pts, np.int32).reshape((-1, 1, 2))
            if data.get('fill'): cv2.fillPoly(img, [pts_arr], color)
            cv2.polylines(img, [pts_arr], True, color, max(1, thick))
            if 'label' in data: cv2.putText(img, data['label'], (scaled_pts[0][0], scaled_pts[0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif shape == 'circle' and len(scaled_pts) > 0:
            rad = int(data.get('radius', 0.1) * w) if rel else int(data.get('radius', 10))
            cv2.circle(img, scaled_pts[0], rad, color, max(1, thick))
            if 'label' in data: cv2.putText(img, data['label'], (scaled_pts[0][0] - rad, scaled_pts[0][1] - rad - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif shape == 'text' and len(scaled_pts) > 0:
            text = str(data.get('text', data.get('label', '')))
            scale = float(data.get('font_scale', 1.0))
            cv2.putText(img, text, scaled_pts[0], cv2.FONT_HERSHEY_SIMPLEX, scale, color, max(1, thick))

@vision_node(
    type_id="data_list_selector",
    label="List Selector",
    category="data",
    icon="Box",
    description="Extracts a specific item from a list of detections.",
    inputs=[{"id": "list_in", "color": "list"}],
    outputs=[{"id": "item_out", "color": "any"}],
    params=[
        {"id": "index", "label": "Index", "type": "int", "default": 0}
    ]
)
class ListSelectorNode(NodeProcessor):
    def process(self, inputs, params):
        d_list = inputs.get('list_in') or inputs.get('data')
        if not isinstance(d_list, list): return {"item_out": None}
        idx = int(params.get('index', 0))
        return {"item_out": d_list[idx] if 0 <= idx < len(d_list) else None}

@vision_node(
    type_id="data_coord_splitter",
    label="Coord Splitter",
    category="data",
    icon="Box",
    description="Splits a coordinate dictionary into 4 scalar values.",
    inputs=[{"id": "data", "color": "any"}],
    outputs=[
        {"id": "x", "color": "scalar"},
        {"id": "y", "color": "scalar"},
        {"id": "w", "color": "scalar"},
        {"id": "h", "color": "scalar"}
    ]
)
class CoordSplitterNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('data')
        if not isinstance(d, dict): return {"x": None, "y": None, "w": None, "h": None}
        return {"x": d.get("xmin"), "y": d.get("ymin"), "w": d.get("width"), "h": d.get("height")}

@vision_node(
    type_id="data_coord_combine",
    label="Coord Combine",
    category="data",
    icon="Box",
    description="Combines 4 scalar values into a coordinate dictionary.",
    inputs=[
        {"id": "x", "color": "scalar"},
        {"id": "y", "color": "scalar"},
        {"id": "w", "color": "scalar"},
        {"id": "h", "color": "scalar"}
    ],
    outputs=[{"id": "dict_out", "color": "any"}]
)
class CoordCombineNode(NodeProcessor):
    def process(self, inputs, params):
        return {"dict_out": {"xmin": float(inputs.get("x", 0.0) or 0.0), "ymin": float(inputs.get("y", 0.0) or 0.0), "width": float(inputs.get("w", 0.0) or 0.0), "height": float(inputs.get("h", 0.0) or 0.0)}}

@vision_node(
    type_id="util_coord_to_mask",
    label="Coord To Mask",
    category="mask",
    icon="Layers",
    description="Transforms detection coordinates into a white mask.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "data", "color": "any"}
    ],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "width", "label": "Width (if no img)", "type": "int", "default": 640},
        {"id": "height", "label": "Height (if no img)", "type": "int", "default": 480}
    ]
)
class CoordToMaskNode(NodeProcessor):
    def process(self, inputs, params):
        img_ref, data = inputs.get('image'), inputs.get('data')
        w, h = (img_ref.shape[1], img_ref.shape[0]) if img_ref is not None else (int(params.get('width', 640)), int(params.get('height', 480)))
        mask = np.zeros((h, w), dtype=np.uint8)
        
        items = data if isinstance(data, list) else [data] if data else []
        for item in items:
            if not isinstance(item, dict): continue
            
            # Case 1: Landmarks (MediaPipe format: list of {'x', 'y'})
            if 'landmarks' in item:
                lms = item['landmarks']
                pts = np.array([(int(lm['x'] * w), int(lm['y'] * h)) for lm in lms], np.int32)
                if len(pts) > 2:
                    hull = cv2.convexHull(pts)
                    cv2.fillPoly(mask, [hull], 255)
            
            # Case 2: Points (List of [x, y])
            elif 'pts' in item:
                pts = np.array([(int(p[0] * w), int(p[1] * h)) for p in item['pts']], np.int32)
                if len(pts) > 2:
                    cv2.fillPoly(mask, [pts], 255)
            
            # Case 3: Simple Box
            elif 'xmin' in item:
                cv2.rectangle(mask, 
                    (int(item['xmin']*w), int(item['ymin']*h)), 
                    (int((item['xmin']+item['width'])*w), int((item['ymin']+item['height'])*h)), 
                    255, -1)
                    
        return {"mask": mask}

@vision_node(
    type_id="util_mask_blend",
    label="Mask Blend",
    category="blend",
    icon="Box",
    description="Blends two images using a mask as an alpha layer.",
    inputs=[
        {"id": "image_a", "color": "image"},
        {"id": "image_b", "color": "image"},
        {"id": "mask", "color": "mask"}
    ],
    outputs=[{"id": "main", "color": "image"}]
)
class MaskBlendNode(NodeProcessor):
    def process(self, inputs, params):
        img_a, img_b, mask = inputs.get('image_a', inputs.get('image')), inputs.get('image_b'), inputs.get('mask')
        if img_a is None: return {"main": None}
        if img_b is None or mask is None: return {"main": img_a}
        if len(mask.shape) == 3: mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = cv2.resize(mask, (img_a.shape[1], img_a.shape[0]))
        mask_normalized = np.expand_dims(mask, axis=2) / 255.0
        if len(img_a.shape) == 2 or img_a.shape[2] == 1: img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)
        img_b_res = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        if len(img_b_res.shape) == 2 or img_b_res.shape[2] == 1: img_b_res = cv2.cvtColor(img_b_res, cv2.COLOR_GRAY2BGR)
        blended = (img_a * (1.0 - mask_normalized)) + (img_b_res * mask_normalized)
        return {"main": blended.astype(np.uint8)}

@vision_node(
    type_id="data_inspector",
    label="Inspect Unit",
    category="visualize",
    icon="Eye",
    description="Displays the raw data content flowing through a link.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "data", "color": "any"}
    ],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "data_out", "color": "any"}
    ]
)
class InspectorNode(NodeProcessor):
    def process(self, inputs, params): return {"main": inputs.get('image'), "data_out": inputs.get('data')}

@vision_node(
    type_id="canvas_note",
    label="Note",
    category="canvas",
    icon="Type",
    description="Annotation text block. Double-click to edit. Drag & resize freely.",
    inputs=[],
    outputs=[]
)
class NoteNode(NodeProcessor):
    def process(self, inputs, params): return {}

@vision_node(
    type_id="canvas_frame",
    label="Frame",
    category="canvas",
    icon="Box",
    description="Wraps and labels a group of nodes. Drag to encapsulate nodes.",
    inputs=[],
    outputs=[]
)
class FrameNode(NodeProcessor):
    def process(self, inputs, params): return {}

@vision_node(
    type_id="canvas_reroute",
    label="Reroute",
    category="canvas",
    icon="GitCommit",
    description="Pass-through node to organize wires.",
    inputs=[{"id": "in", "color": "any"}],
    outputs=[{"id": "out", "color": "any"}]
)
class RerouteNode(NodeProcessor):
    def process(self, inputs, params):
        out = {}
        for k, v in inputs.items():
            if k != 'raw_frame':
                out[k] = v
        # Ensure 'main', 'image', 'data' exist if any other exist, since we don't know the intent
        first_val = next(iter(out.values()), None) if out else None
        if 'main' not in out: out['main'] = first_val
        if 'image' not in out: out['image'] = first_val
        if 'data' not in out: out['data'] = first_val
        if 'out' not in out: out['out'] = first_val
        return out

@vision_node(
    type_id="output_display",
    label="Display",
    category="out",
    icon="Maximize",
    description="The output terminal displaying the final video stream.",
    inputs=[
        {"id": "main", "color": "image"},
        {"id": "mask_in", "color": "mask"},
        {"id": "flow_in", "color": "any"}
    ],
    outputs=[{"id": "main", "color": "image"}]
)
class DisplayOutput(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('main')
        mask = inputs.get('mask_in')
        flow = inputs.get('flow_in')
        
        # Determine base image
        res = img if img is not None else flow
        if res is None and mask is not None:
            # If only mask, show it as grayscale
            res = mask
            
        # Overlay mask if both exist
        if img is not None and mask is not None:
            # Resize mask to img if needed
            if mask.shape[:2] != img.shape[:2]:
                mask = cv2.resize(mask, (img.shape[1], img.shape[0]))
            
            # Create red overlay for mask
            overlay = img.copy()
            overlay[mask > 0] = [0, 0, 255] # Red BGR
            res = cv2.addWeighted(overlay, 0.4, img, 0.6, 0)
            
        return {"main": res}

# --- CORE ENGINE ---
def _is_serializable(v):
    """Reject numpy arrays, rasterio Affine, and any container holding them."""
    if isinstance(v, (str, int, float, bool, type(None))):
        return True
    if isinstance(v, np.ndarray):
        return False
    if isinstance(v, dict):
        return all(_is_serializable(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return all(_is_serializable(x) for x in v)
    return False  # Affine, bytes, unknown objects — skip

def flatten_groups(node_list, edge_list, prefix=''):
    """Recursively expand group_node types into flat nodes+edges."""
    flat_nodes = []
    flat_edges = []
    group_ids = {n['id'] for n in node_list if n.get('type') == 'group_node'}
    non_group_ids = {n['id'] for n in node_list if n.get('type') != 'group_node'}

    for node in node_list:
        if node.get('type') != 'group_node':
            flat_nodes.append({**node, 'id': prefix + node['id']})

    for e in edge_list:
        src, tgt = e.get('source', ''), e.get('target', '')
        if src in non_group_ids and tgt in non_group_ids:
            flat_edges.append({**e, 'source': prefix + src, 'target': prefix + tgt})

    for node in node_list:
        if node.get('type') != 'group_node':
            continue
        g_id = node['id']
        gprefix = prefix + g_id + '::'
        sub = node.get('data', {}).get('subGraph', {})
        sub_nodes = sub.get('nodes', [])
        sub_edges = sub.get('edges', [])

        gin = next((n for n in sub_nodes if n.get('type') == 'group_input'), None)
        gout = next((n for n in sub_nodes if n.get('type') == 'group_output'), None)
        gin_id = gin['id'] if gin else None
        gout_id = gout['id'] if gout else None

        inner_nodes = [n for n in sub_nodes if n.get('type') not in ('group_input', 'group_output')]
        inner_edges = [e for e in sub_edges
                       if e.get('source') not in (gin_id, gout_id)
                       and e.get('target') not in (gin_id, gout_id)]

        sub_flat_nodes, sub_flat_edges = flatten_groups(inner_nodes, inner_edges, prefix=gprefix)
        flat_nodes.extend(sub_flat_nodes)
        flat_edges.extend(sub_flat_edges)

        for outer_e in edge_list:
            if outer_e.get('target') != g_id or not gin_id:
                continue
            th = outer_e.get('targetHandle', '')
            for inner_e in sub_edges:
                if inner_e.get('source') != gin_id or inner_e.get('sourceHandle', '') != th:
                    continue
                flat_edges.append({
                    'id': f"f_{outer_e.get('id','')}_{inner_e.get('id','')}",
                    'source': prefix + outer_e['source'],
                    'sourceHandle': outer_e.get('sourceHandle', ''),
                    'target': gprefix + inner_e['target'],
                    'targetHandle': inner_e.get('targetHandle', ''),
                })

        for outer_e in edge_list:
            if outer_e.get('source') != g_id or not gout_id:
                continue
            sh = outer_e.get('sourceHandle', '')
            for inner_e in sub_edges:
                if inner_e.get('target') != gout_id or inner_e.get('targetHandle', '') != sh:
                    continue
                flat_edges.append({
                    'id': f"f_{inner_e.get('id','')}_{outer_e.get('id','')}",
                    'source': gprefix + inner_e['source'],
                    'sourceHandle': inner_e.get('sourceHandle', ''),
                    'target': prefix + outer_e['target'],
                    'targetHandle': outer_e.get('targetHandle', ''),
                })

    return flat_nodes, flat_edges


class VisionEngine:
    def __init__(self):
        self.current_cap_index = 0
        # Initialize with flexible backend detection
        self.cap = cv2.VideoCapture(self.current_cap_index, CAP_BACKEND)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.current_cap_index, cv2.CAP_V4L2)
        self.graph = {"nodes": [], "edges": []}
        self.sorted_nodes = []
        self.connected_clients = set()
        self.node_instances = {}
        self.registry = {}
        self.registry.update(NODE_CLASS_REGISTRY)
        self.pending_capture = None
        self.preview_node_id = None
        
        self.fallback_img = None
        img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img", "fallback.jpg")
        if os.path.exists(img_path):
            self.fallback_img = cv2.imread(img_path)

        self._run_event = asyncio.Event()  # set only when a live source is active

    def switch_camera(self, idx):
        target_idx = str(idx)
        current_idx = str(getattr(self, 'current_cap_index', -1))
        
        # If we are already on this index, don't try again (even if it's closed/failed)
        if current_idx == target_idx and self.cap is not None:
            return
            
        print(f"[Engine] Camera Switch Request: {current_idx} -> {target_idx}")
        
        if self.cap: 
            self.cap.release()
            self.cap = None
            
        # Try primary backend
        print(f"[Engine] Attempting to open cam {target_idx} (CAP_ANY)...")
        cap = cv2.VideoCapture(int(idx), CAP_BACKEND)
        
        if not cap.isOpened():
            print(f"[Engine] Fallback to CAP_V4L2 for cam {target_idx}...")
            cap = cv2.VideoCapture(int(idx), cv2.CAP_V4L2)
            
        self.cap = cap
        self.current_cap_index = int(idx)
        print(f"[Engine] Camera {target_idx} opened: {self.cap.isOpened()}")
        
        if not self.cap.isOpened():
            print(f"[Engine] CRITICAL: Camera {target_idx} failed to open. Stopping retry loop.")

    def _should_run(self):
        return len(self.sorted_nodes) > 0

    def update_graph(self, g):
        raw_edges = [e for e in g.get('edges', []) if e.get('source') and e.get('target')]
        flat_nodes, flat_edges = flatten_groups(g.get('nodes', []), raw_edges)
        self.graph = {'nodes': flat_nodes, 'edges': flat_edges}
        nodes_dict = {n['id']: n for n in flat_nodes}
        s_ids = topological_sort(flat_nodes, flat_edges)
        self.sorted_nodes = [nodes_dict[nid] for nid in s_ids if nid in nodes_dict]
        active_nids = set(nodes_dict.keys())
        self.node_instances = {nid: inst for nid, inst in self.node_instances.items() if nid in active_nids}
        if self._should_run():
            self._run_event.set()
        else:
            self._run_event.clear()

    async def _drain_notifs_loop(self):
        """Background task: flush notification queue to clients every 50 ms."""
        while True:
            await asyncio.sleep(0.05)
            while not _notification_queue.empty():
                try:
                    notif = _notification_queue.get_nowait()
                    notif_msg = json.dumps({"type": "notification", **notif})
                    if self.connected_clients:
                        await asyncio.gather(*[c.send(notif_msg) for c in list(self.connected_clients)], return_exceptions=True)
                except Exception as e:
                    print(f"[Engine] Notification drain error: {e}")

    async def run(self):
        while True:
            if not self._run_event.is_set():
                await self._run_event.wait()
                continue
            ret, frame = self.cap.read()
            if not ret:
                frame = None   # ← allow non-camera nodes (audio, geo…) to run anyway
                await asyncio.sleep(0.05)
            results, node_datas, final_img, commands = {}, {}, None, []
            for node in self.sorted_nodes:
                nid, ntype = node['id'], node['type']
                inputs = {"raw_frame": frame}
                for e in self.graph.get('edges', []):
                    if e['target'] == nid and e['source'] in results:
                        source_res = results[e['source']]
                        sh, th = e.get('sourceHandle', 'main').split('__')[-1], e.get('targetHandle', '').split('__')[-1]
                        val = source_res.get(sh)
                        if val is not None:
                            if th:
                                inputs[th] = val
                                if th in ['image', 'main'] and isinstance(val, np.ndarray):
                                    inputs['image'] = val
                                elif th == 'image':
                                    inputs.pop('image', None)  # val not ndarray — don't pollute image slot
                                if th == 'data': inputs['data'] = val
                            else:
                                if isinstance(val, np.ndarray): inputs['image'] = val
                                else: inputs['data'] = val
                # Get or create instance for this specific node
                if nid not in self.node_instances:
                    cls = self.registry.get(ntype)
                    if cls:
                        # Handle special cases if needed, or pass engine reference
                        try:
                            # Try passing self (engine) in case it's needed
                            self.node_instances[nid] = cls(self)
                        except TypeError:
                            # Fallback to no-args init
                            self.node_instances[nid] = cls()
                
                proc = self.node_instances.get(nid)
                if proc:
                    try:
                        out = await asyncio.to_thread(proc.process, inputs, node.get('data', {}).get('params', {}))
                        results[nid] = out
                        
                        # Handle On-Demand Capture
                        if self.pending_capture == nid and out.get('main') is not None:
                            try:
                                capture_img = out['main']
                                if len(capture_img.shape) == 2: capture_img = cv2.cvtColor(capture_img, cv2.COLOR_GRAY2BGR)
                                _, c_buf = cv2.imencode('.png', capture_img)
                                c_b64 = base64.b64encode(c_buf).decode('utf-8')
                                async def send_capture(b):
                                    msg = json.dumps({"type": "node_capture", "node_id": nid, "image": b})
                                    if self.connected_clients: await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)], return_exceptions=True)
                                asyncio.create_task(send_capture(c_b64))
                                self.pending_capture = None # Reset
                            except Exception as ce: print(f"Capture Error: {ce}")

                        for k, v in out.items():
                            if k == "_command" and v:
                                cmd = dict(v)
                                if cmd.get('node_id') == '__self__': cmd['node_id'] = nid
                                commands.append(cmd)
                            elif k != "main" and not isinstance(v, np.ndarray) and _is_serializable(v):
                                node_datas[f"{nid}:{k}"] = v
                        if self.preview_node_id and nid == self.preview_node_id:
                            preview_img = out.get('main')
                            if preview_img is None:
                                for _v in out.values():
                                    if isinstance(_v, np.ndarray) and len(_v.shape) >= 2:
                                        preview_img = _v; break
                            if preview_img is not None: final_img = preview_img
                        elif not self.preview_node_id and ntype == 'output_display' and out.get('main') is not None:
                            final_img = out['main']
                    except Exception as e: print(f"Error {nid}: {e}")
            if final_img is None:
                final_img = getattr(self, 'fallback_img', None)
                if final_img is None:
                    final_img = np.zeros((480, 640, 3), dtype=np.uint8)
            if final_img is not None:
                try:
                    if len(final_img.shape) == 2: final_img = cv2.cvtColor(final_img, cv2.COLOR_GRAY2BGR)
                    elif len(final_img.shape) == 3 and final_img.shape[2] == 2:
                        hsv = np.zeros((final_img.shape[0], final_img.shape[1], 3), dtype=np.uint8); hsv[..., 1] = 255
                        mag, ang = cv2.cartToPolar(final_img[..., 0], final_img[..., 1])
                        hsv[..., 0], hsv[..., 2] = ang * 180 / np.pi / 2, cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
                        final_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                    _, buf = cv2.imencode('.jpg', final_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    msg = json.dumps({
                        "type": "update", 
                        "image": base64.b64encode(buf).decode('utf-8'), 
                        "nodes_data": node_datas,
                        "commands": commands
                    })
                    if self.connected_clients: await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)], return_exceptions=True)
                except Exception as e: print(f"Encoding Error: {e}")

            await asyncio.sleep(1/30)

    async def hdl(self, ws):
        self.connected_clients.add(ws)
        if NODE_SCHEMAS:
            try:
                await ws.send(json.dumps({"type": "schema", "nodes": NODE_SCHEMAS}))
            except Exception as e:
                print(f"[Engine] Failed to send schema: {e}")
        try:
            async for m in ws:
                try:
                    d = json.loads(m)
                    if d.get('type') == 'update_graph':
                        self.update_graph(d.get('graph', {}))
                    elif d.get('type') == 'request_node_capture':
                        self.pending_capture = d.get('node_id')
                    elif d.get('type') == 'set_preview_node':
                        self.preview_node_id = d.get('node_id')
                except Exception as e:
                    print(f"[Engine] Message handler error: {e}")
        except Exception as e:
            print(f"[Engine] WebSocket closed: {e}")
        finally:
            self.connected_clients.remove(ws)

load_plugins()

async def main(engine_instance):
    try:
        async with websockets.serve(engine_instance.hdl, "localhost", 8765):
            await asyncio.gather(
                engine_instance.run(),
                engine_instance._drain_notifs_loop(),
            )
    except Exception as e:
        print(f"Server Error: {e}")

def free_port(port):
    import signal
    try:
        result = subprocess.run(['ss', '-tlnp', f'sport = :{port}'],
                                capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'pid=' in line:
                pid = int(line.split('pid=')[1].split(',')[0])
                if pid != os.getpid():
                    os.kill(pid, signal.SIGKILL)
        time.sleep(0.3)
    except Exception:
        pass

if __name__ == "__main__":
    print("[Engine] Starting OpenCV Sidecar...")
    free_port(8765)
    cameras = list_available_cameras()
    print(f"[Engine] Available cameras: {cameras}")

    engine = VisionEngine()
    try:
        asyncio.run(main(engine))
    except KeyboardInterrupt:
        print("\n[Engine] Stopped.")
