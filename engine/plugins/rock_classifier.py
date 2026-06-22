"""
Rock Classifier — EfficientNet-B0 + Spatial Attention rock-type classifier.

Architecture and weights from zhh-pixel/rock (Nature Sci. Reports 2025,
s41598-025-03706-0). 5-class rock image classifier. Weights auto-download
from GitHub on first use.

In the wall pipeline: connect SAM 'contours' → this node crops each stone,
classifies it, and outputs a {class_name: [stone_ids]} dict that plugs
straight into Stone Calepinage 'classes' — a deterministic, LLM-free
alternative to the Ollama classification step.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import os
import threading
import importlib.util

_NOTIF_ID = 'rock_classifier'
_WEIGHTS_URL = 'https://github.com/zhh-pixel/rock/raw/main/weights/model_aug_SA_lion.pth'
_WEIGHTS_DIR = os.path.expanduser('~/.vnstudio/models')
_WEIGHTS_PATH = os.path.join(_WEIGHTS_DIR, 'model_aug_SA_lion.pth')
_MODEL_SRC = os.path.join(os.path.dirname(__file__), 'rock_classifier_src', 'model_SA.py')

# ImageNet normalization (matches the repo's predict_test transforms)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_INPUT = 224

_NUM_CLASSES = 5
# The repo ships no class_indices.json — names are user-editable.
_DEFAULT_CLASSES = 'class_0,class_1,class_2,class_3,class_4'


def _load_model_def():
    """Import the vendored EfficientNet-SA definition (not a plugin → safe)."""
    spec = importlib.util.spec_from_file_location('rock_model_SA', _MODEL_SRC)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@vision_node(
    type_id='rock_classifier',
    label='Rock Classifier',
    category='analysis',
    icon='Gem',
    description=(
        "EfficientNet-B0 + Spatial Attention rock-type classifier "
        "(zhh-pixel/rock, Nature Sci. Reports 2025). Classifies each "
        "segmented stone into one of 5 rock classes. Connect SAM 'contours' "
        "→ outputs a {class: [ids]} dict that feeds Stone Calepinage directly "
        "(deterministic, no LLM). Weights auto-download on first use."
    ),
    inputs=[
        {'id': 'image',    'color': 'image', 'label': 'Source Image'},
        {'id': 'contours', 'color': 'list',  'label': 'Contours (SAM)'},
    ],
    outputs=[
        {'id': 'main',      'color': 'image',  'label': 'Overlay'},
        {'id': 'classes',   'color': 'dict',   'label': 'Classes {type:[ids]} → Calepinage'},
        {'id': 'labels',    'color': 'list',   'label': 'Per-stone [{id,class,conf}]'},
        {'id': 'top_class', 'color': 'string', 'label': 'Dominant Class'},
    ],
    params=[
        {'id': 'classify',    'label': 'Classify', 'type': 'trigger', 'default': False},
        {'id': '_sec_model', 'label': 'Model Config', 'type': 'section'},
        {'id': 'class_names', 'label': 'Class Names (comma-sep, 5)', 'type': 'string',
         'default': _DEFAULT_CLASSES},
        {'id': 'weights_path','label': 'Weights Path (empty = auto-download)', 'type': 'string',
         'default': ''},
        {'id': '_sec_detection', 'label': 'Detection', 'type': 'section'},
        {'id': 'min_crop',    'label': 'Min Crop Size (px)', 'type': 'int',
         'default': 12, 'min': 4, 'max': 128},
        {'id': 'pad',         'label': 'Crop Padding (px)', 'type': 'int',
         'default': 4, 'min': 0, 'max': 64},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'show_labels', 'label': 'Show Labels', 'type': 'bool', 'default': True},
        {'id': 'font_scale',  'label': 'Font Scale', 'type': 'float',
         'default': 0.45, 'min': 0.2, 'max': 2.0, 'step': 0.05},
    ],
    colorable=True,
    resizable=True,
)
class RockClassifierNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.model = None
        self._loading = False
        self._failed = False
        self._cache_result = None

        self.device = 'cpu'
        try:
            import torch
            if torch.backends.mps.is_available():
                self.device = 'mps'
            elif torch.cuda.is_available():
                self.device = 'cuda'
        except ImportError:
            pass

    def _ensure_weights(self, weights_path: str) -> str | None:
        """Return a valid weights path, downloading from GitHub if needed."""
        if weights_path and os.path.exists(weights_path):
            return weights_path
        if os.path.exists(_WEIGHTS_PATH):
            return _WEIGHTS_PATH
        # Download
        try:
            import requests
            os.makedirs(_WEIGHTS_DIR, exist_ok=True)
            send_notification('Rock: downloading weights (13 MB)…', progress=0.1, notif_id=_NOTIF_ID)
            with requests.get(_WEIGHTS_URL, stream=True, timeout=120) as r:
                r.raise_for_status()
                tmp = _WEIGHTS_PATH + '.part'
                with open(tmp, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        f.write(chunk)
                os.replace(tmp, _WEIGHTS_PATH)
            send_notification('Rock: weights ready ✓', progress=1.0, notif_id=_NOTIF_ID)
            return _WEIGHTS_PATH
        except Exception as e:
            print(f'[Rock] Weights download failed: {e}')
            send_notification(f'Rock: download failed — {str(e)[:80]}',
                              level='error', notif_id=_NOTIF_ID)
            return None

    def _load_model_thread(self, weights_path: str) -> None:
        try:
            import torch
            if not self.ensure_packages(['torch', 'torchvision'], notif_id=_NOTIF_ID):
                self._failed = True
                return
            path = self._ensure_weights(weights_path)
            if path is None:
                self._failed = True
                return
            mod = _load_model_def()
            net = mod.efficientnet_b0(num_classes=_NUM_CLASSES)
            sd  = torch.load(path, map_location='cpu', weights_only=False)
            if isinstance(sd, dict) and 'state_dict' in sd:
                sd = sd['state_dict']
            net.load_state_dict(sd, strict=False)
            net.eval().to(self.device)
            self.model = net
            send_notification('Rock: model ready ✓', progress=1.0, notif_id=_NOTIF_ID)
        except Exception as e:
            self._failed = True
            print(f'[Rock] Model load failed: {e}')
            send_notification(f'Rock error: {str(e)[:100]}', level='error', notif_id=_NOTIF_ID)
        finally:
            self._loading = False

    def _preprocess(self, crop_bgr: np.ndarray):
        """BGR crop → normalized CHW tensor (1,3,224,224)."""
        import torch
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        # Resize shorter side to 224 then center-crop (matches repo transforms)
        h, w = rgb.shape[:2]
        scale = _INPUT / min(h, w)
        rgb = cv2.resize(rgb, (max(_INPUT, int(w * scale)), max(_INPUT, int(h * scale))))
        h, w = rgb.shape[:2]
        y0 = (h - _INPUT) // 2
        x0 = (w - _INPUT) // 2
        rgb = rgb[y0:y0 + _INPUT, x0:x0 + _INPUT]
        arr = rgb.astype(np.float32) / 255.0
        arr = (arr - _MEAN) / _STD
        arr = np.transpose(arr, (2, 0, 1))
        return torch.from_numpy(arr).unsqueeze(0)

    def _empty(self, image, msg: str = None):
        main = image
        if msg is not None and image is not None:
            main = image.copy()
            cv2.rectangle(main, (0, 0), (main.shape[1], 36), (20, 20, 20), -1)
            cv2.putText(main, msg, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 200, 50), 1, cv2.LINE_AA)
        return {'main': main, 'classes': {}, 'labels': [], 'top_class': ''}

    def process(self, inputs: dict, params: dict) -> dict:
        import torch

        image    = inputs.get('image')
        contours = inputs.get('contours')
        if image is None:
            return self._empty(None)

        class_names = [s.strip() for s in str(params.get('class_names', _DEFAULT_CLASSES)).split(',') if s.strip()]
        if len(class_names) < _NUM_CLASSES:
            class_names += [f'class_{i}' for i in range(len(class_names), _NUM_CLASSES)]

        # Model loading (background)
        weights_path = (params.get('weights_path') or '').strip()
        if self.model is None:
            if self._failed:
                return self._empty(image, 'Rock: model load failed — check weights/network')
            if not self._loading:
                self._loading = True
                threading.Thread(target=self._load_model_thread,
                                 args=(weights_path,), daemon=True).start()
            return self._empty(image, 'Loading rock model… (first run downloads weights)')

        # Trigger gate
        if not bool(params.get('classify', False)):
            if self._cache_result is not None:
                return self._cache_result
            return self._empty(image, 'Press Classify to run')

        if not isinstance(contours, list) or len(contours) == 0:
            return self._empty(image, 'No contours — connect SAM contours port')

        min_crop = int(params.get('min_crop', 12))
        pad      = int(params.get('pad', 4))
        show_labels = bool(params.get('show_labels', True))
        font_scale  = float(params.get('font_scale', 0.45))
        h, w = image.shape[:2]

        classes_dict: dict = {}
        labels: list = []
        overlay = image.copy()
        class_count: dict = {}

        self.report_progress(0.1, 'Rock: classifying stones…')

        for sid, contour in enumerate(contours):
            if not isinstance(contour, (list, tuple)) or len(contour) < 3:
                continue
            pts = np.array(contour, dtype=np.int32)
            x, y, bw, bh = cv2.boundingRect(pts)
            if bw < min_crop or bh < min_crop:
                continue
            x0 = max(0, x - pad); y0 = max(0, y - pad)
            x1 = min(w, x + bw + pad); y1 = min(h, y + bh + pad)
            crop = image[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            try:
                tensor = self._preprocess(crop).to(self.device)
                with torch.inference_mode():
                    logits = self.model(tensor)
                    probs  = torch.softmax(logits, dim=1)[0]
                    cls_idx = int(torch.argmax(probs).item())
                    conf    = float(probs[cls_idx].item())
            except Exception as e:
                print(f'[Rock] inference error on stone {sid}: {e}')
                continue

            cls_name = class_names[cls_idx] if cls_idx < len(class_names) else f'class_{cls_idx}'
            classes_dict.setdefault(cls_name, []).append(sid)
            class_count[cls_name] = class_count.get(cls_name, 0) + 1
            labels.append({'id': sid, 'class': cls_name, 'conf': round(conf, 3)})

            # Overlay: outline + label at centroid
            M = cv2.moments(pts)
            cx = int(M['m10'] / M['m00']) if M['m00'] else x + bw // 2
            cy = int(M['m01'] / M['m00']) if M['m00'] else y + bh // 2
            color = (
                int((cls_idx * 67 + 40) % 200 + 55),
                int((cls_idx * 137 + 80) % 200 + 55),
                int((cls_idx * 197 + 120) % 200 + 55),
            )
            cv2.polylines(overlay, [pts.reshape(-1, 1, 2)], True, color, 2)
            if show_labels:
                txt = f'#{sid}:{cls_name}'
                cv2.putText(overlay, txt, (cx - 10, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

        top_class = max(class_count, key=class_count.get) if class_count else ''
        n = len(labels)
        self.report_progress(1.0, f'Rock: {n} stones classified')

        result = {
            'main': overlay,
            'classes': classes_dict,
            'labels': labels,
            'top_class': top_class,
        }
        self._cache_result = result
        return result
