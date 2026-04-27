from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import os
import base64
try:
    from PIL import Image as _PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

@vision_node(
    type_id='input_float_image',
    label='Float Image',
    category='src',
    icon='FileImage',
    description="Loads float32/uint16 scientific images (TIFF, NDVI, HDR, etc.) and normalizes to 8-bit for processing. Supports min-max stretch, percentile clipping, and fixed range.",
    inputs=[],
    outputs=[
        {'id': 'main',    'color': 'image'},
        {'id': 'raw',     'color': 'any'},
        {'id': 'width',   'color': 'scalar'},
        {'id': 'height',  'color': 'scalar'},
        {'id': 'raw_min', 'color': 'scalar'},
        {'id': 'raw_max', 'color': 'scalar'},
    ],
    params=[
        {'id': 'path',      'label': 'File Path',      'type': 'string', 'default': ''},
        {'id': 'normalize', 'label': 'Normalize',       'type': 'enum',
         'options': ['Min-Max', 'Percentile', 'Fixed Range'], 'default': 1},
        {'id': 'p_low',     'label': 'Percentile Low',  'type': 'float', 'default': 2.0},
        {'id': 'p_high',    'label': 'Percentile High', 'type': 'float', 'default': 98.0},
        {'id': 'fixed_min', 'label': 'Fixed Min',       'type': 'float', 'default': -1.0},
        {'id': 'fixed_max', 'label': 'Fixed Max',       'type': 'float', 'default':  1.0},
    ],
    colorable=True,
)
class FloatImageInputNode(NodeProcessor):
    def __init__(self):
        self.last_path = ''
        self.cached_raw = None

    def process(self, inputs, params):
        path = params.get('path', '')
        if not path:
            return {'main': None, 'width': 0, 'height': 0, 'raw_min': 0.0, 'raw_max': 0.0}

        full_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(full_path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt = os.path.join(project_root, path)
            if os.path.exists(alt):
                full_path = alt

        if full_path != self.last_path:
            raw = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
            if raw is None and _PIL_AVAILABLE:
                try:
                    pil = _PILImage.open(full_path)
                    raw = np.array(pil)
                    print(f"[FloatImageInput] PIL loaded {full_path} mode={pil.mode} dtype={raw.dtype} shape={raw.shape}")
                except Exception as e:
                    print(f"[FloatImageInput] PIL fallback failed: {e}")
            if raw is None:
                print(f"[FloatImageInput] Failed: {full_path}")
                return {'main': None, 'width': 0, 'height': 0, 'raw_min': 0.0, 'raw_max': 0.0}
            self.cached_raw = raw.astype(np.float32)
            self.last_path = full_path
            print(f"[FloatImageInput] Loaded {full_path} dtype={raw.dtype} shape={raw.shape}")

        if self.cached_raw is None:
            return {'main': None, 'width': 0, 'height': 0, 'raw_min': 0.0, 'raw_max': 0.0}

        raw = self.cached_raw
        # Flatten to single channel for stats (works for 2D and any 3D)
        flat = raw[:, :, 0] if raw.ndim == 3 else raw

        raw_min = float(np.nanmin(flat))
        raw_max = float(np.nanmax(flat))

        mode = int(params.get('normalize', 1))
        if mode == 0:    # Min-Max
            lo, hi = raw_min, raw_max
        elif mode == 1:  # Percentile
            p_low  = float(params.get('p_low',  2.0))
            p_high = float(params.get('p_high', 98.0))
            lo = float(np.nanpercentile(flat, p_low))
            hi = float(np.nanpercentile(flat, p_high))
        else:            # Fixed Range
            lo = float(params.get('fixed_min', -1.0))
            hi = float(params.get('fixed_max',  1.0))

        span = hi - lo if hi != lo else 1.0
        normalized = np.clip((raw - lo) / span, 0.0, 1.0)
        img8 = (normalized * 255).astype(np.uint8)

        # Ensure output is 3-channel BGR
        if img8.ndim == 2:
            img8 = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
        elif img8.shape[2] == 1:
            img8 = cv2.cvtColor(img8[:, :, 0], cv2.COLOR_GRAY2BGR)
        elif img8.shape[2] == 4:
            img8 = cv2.cvtColor(img8, cv2.COLOR_BGRA2BGR)

        h, w = img8.shape[:2]
        # raw: single-channel float32 for direct float thresholding
        raw_out = self.cached_raw[:, :, 0] if self.cached_raw.ndim == 3 else self.cached_raw
        out = {'main': img8, 'raw': raw_out, 'width': w, 'height': h, 'raw_min': raw_min, 'raw_max': raw_max}

        try:
            sc = 120 / h
            pw = int(w * sc)
            if pw > 0:
                prev = cv2.resize(img8, (pw, 120))
                _, buf = cv2.imencode('.jpg', prev, [cv2.IMWRITE_JPEG_QUALITY, 50])
                out['preview'] = base64.b64encode(buf).decode('utf-8')
        except Exception as e:
            print(f"[FloatImageInput] Preview error: {e}")

        return out
