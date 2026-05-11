"""
SAM Segmenter — Interactive AI segmentation using SAM 2 (Meta).
Supports bounding box and point prompts for precise object segmentation.
Models are downloaded automatically from HuggingFace on first use.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import json
import threading
import os

try:
    import torch
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False

_NOTIF_ID = 'sam_segmenter'

# HuggingFace model IDs for each variant
_HF_MODELS = {
    'SAM2 Tiny':  'facebook/sam2-hiera-tiny',
    'SAM2 Small': 'facebook/sam2-hiera-small',
    'SAM2 Base+': 'facebook/sam2-hiera-base-plus',
    'SAM2 Large': 'facebook/sam2-hiera-large',
}

_MODEL_NAMES = list(_HF_MODELS.keys())


@vision_node(
    type_id='sam_segmenter',
    label='SAM Segmenter',
    category='detect',
    icon='Scan',
    description=(
        "Interactive AI segmentation powered by SAM 2 (Segment Anything Model 2, Meta). "
        "Draw a bounding box or place a point to segment any object with pixel-perfect precision. "
        "Supports four model sizes from Tiny (~40 MB) to Large (~900 MB). "
        "Models download automatically on first use."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'box',   'color': 'dict', 'label': 'Box (from YOLO)'},
        {'id': 'points', 'color': 'list', 'label': 'Points List'},
    ],
    outputs=[
        {'id': 'main',  'color': 'image', 'label': 'Overlay'},
        {'id': 'mask',  'color': 'mask'},
        {'id': 'score', 'color': 'scalar'},
    ],
    params=[
        # ── Authentication ──
        {'id': 'hf_token', 'label': 'Hugging Face Token (laisser vide si sauvegardé)', 'type': 'string',
         'default': ''},

        # ── Model Selection ──
        {'id': 'model', 'label': 'Model', 'type': 'enum',
         'options': _MODEL_NAMES, 'default': 0},

        # ── Prompt Mode ──
        {'id': 'prompt_mode', 'label': 'Prompt Mode', 'type': 'enum',
         'options': ['Box Input Port', 'Points List Input Port'],
         'default': 0},

        # ── Mask Selection ──
        {'id': 'multimask', 'label': 'Multi-mask (3 candidates)',
         'type': 'boolean', 'default': True},
        {'id': 'mask_index', 'label': 'Mask Selection', 'type': 'number',
         'default': 0, 'min': 0, 'max': 2, 'step': 1},
        {'id': 'auto_best', 'label': 'Auto-select Best', 'type': 'boolean',
         'default': True},
        {'id': 'mask_threshold', 'label': 'Mask Threshold (Sensitivity)', 'type': 'number',
         'default': 0.0, 'min': -10.0, 'max': 10.0, 'step': 0.5},

        # ── Visualization ──
        {'id': 'overlay_opacity', 'label': 'Overlay Opacity (%)', 'type': 'number',
         'default': 50, 'min': 0, 'max': 100, 'step': 5},
        {'id': 'mask_color_index', 'label': 'Mask Color (Palette)', 'type': 'int',
         'default': 3, 'min': 0, 'max': 7},

        # ── Post-processing ──
        {'id': 'refine_pixels', 'label': 'Erode/Dilate (px)', 'type': 'int',
         'default': 0, 'min': -50, 'max': 50},
        {'id': 'smoothing', 'label': 'Smoothing (px)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 20},
        {'id': 'invert', 'label': 'Invert Mask', 'type': 'boolean',
         'default': False},
    ],
    colorable=True,
)
class SAMSegmenterNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.predictor = None
        self.current_model_name = ""
        self._loading = False
        self._failed = set()
        self.lock = threading.Lock()

        # Image embedding cache
        self._embed_hash = None

        # Result cache
        self._cache_hash = None
        self._cache_result = None

        # Device detection
        self.device = 'cpu'
        if SAM2_AVAILABLE:
            if torch.backends.mps.is_available():
                self.device = 'mps'
            elif torch.cuda.is_available():
                self.device = 'cuda'
            print(f"[SAM] Using device: {self.device}")

    def _load_model_thread(self, model_name):
        """Load SAM2 model in a background thread."""
        try:
            hf_id = _HF_MODELS.get(model_name)
            if not hf_id:
                send_notification(
                    f'SAM: Unknown model {model_name}',
                    level='error', notif_id=_NOTIF_ID
                )
                self._failed.add(model_name)
                return

            send_notification(
                f'SAM: Downloading {model_name}…',
                progress=0.1, notif_id=_NOTIF_ID
            )

            # Always load on CPU first (from_pretrained doesn't support MPS directly)
            predictor = SAM2ImagePredictor.from_pretrained(hf_id, device='cpu')

            # Move model to the target accelerator
            if self.device == 'mps':
                # Force float32 on MPS: internal operations like interpolate are unreliable in bfloat16
                predictor.model = predictor.model.to(self.device, dtype=torch.float32)
            elif self.device == 'cuda':
                # CUDA handles bfloat16/autocast well
                predictor.model = predictor.model.to(self.device)

            self.predictor = predictor
            self.current_model_name = model_name
            self._embed_hash = None  # Reset embedding cache

            send_notification(
                f'SAM: {model_name} ready ✓',
                progress=1.0, notif_id=_NOTIF_ID
            )

        except Exception as e:
            self._failed.add(model_name)
            print(f'[SAM] Model load FAILED: {e}')
            send_notification(
                f'SAM error: {str(e)[:120]}',
                level='error', notif_id=_NOTIF_ID
            )
        finally:
            self._loading = False

    def _get_bbox_from_dict(self, box_dict, h, w):
        """Convert a YOLO-style dict {xmin, ymin, width, height} (normalized) to pixel bbox."""
        if not isinstance(box_dict, dict):
            return None

        xmin = float(box_dict.get('xmin', 0))
        ymin = float(box_dict.get('ymin', 0))
        bw = float(box_dict.get('width', 1))
        bh = float(box_dict.get('height', 1))

        x_min = int(max(0, xmin * w))
        y_min = int(max(0, ymin * h))
        x_max = int(min(w, (xmin + bw) * w))
        y_max = int(min(h, (ymin + bh) * h))

        return np.array([x_min, y_min, x_max, y_max])

    def process(self, inputs, params):
        image = inputs.get('image')
        empty = {'main': image, 'mask': None, 'score': 0.0}

        if image is None:
            return empty

        if not SAM2_AVAILABLE:
            send_notification(
                'SAM: sam2 package not installed. Run: pip install git+https://github.com/facebookresearch/sam2.git',
                level='error', notif_id=_NOTIF_ID
            )
            return empty

        hf_token = params.get('hf_token', '')

        # Local persistence for HF token
        secrets_path = os.path.expanduser('~/.vnstudio/secrets.json')
        if hf_token:
            os.makedirs(os.path.dirname(secrets_path), exist_ok=True)
            secrets = {}
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path, 'r') as f:
                        secrets = json.load(f)
                except Exception: pass
            secrets['hf_token'] = hf_token
            try:
                with open(secrets_path, 'w') as f:
                    json.dump(secrets, f)
            except Exception: pass
        else:
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path, 'r') as f:
                        secrets = json.load(f)
                        if 'hf_token' in secrets:
                            hf_token = secrets['hf_token']
                except Exception: pass

        if hf_token:
            os.environ['HF_TOKEN'] = hf_token

        # ── 1. Model Loading ──
        model_idx = int(params.get('model', 0))
        model_name = _MODEL_NAMES[min(model_idx, len(_MODEL_NAMES) - 1)]

        # Check if we need a different model
        if model_name != self.current_model_name:
            if not self._loading and model_name not in self._failed:
                self._loading = True
                self.predictor = None
                threading.Thread(
                    target=self._load_model_thread,
                    args=(model_name,),
                    daemon=True
                ).start()
            return empty

        if self.predictor is None:
            return empty

        # Hotfix: Ensure float32 on MPS for stability (interpolate bug)
        if self.device == 'mps' and next(self.predictor.model.parameters()).dtype != torch.float32:
            self.predictor.model = self.predictor.model.to(dtype=torch.float32)

        h, w = image.shape[:2]

        # ── 2. Determine prompt ──
        prompt_mode = int(params.get('prompt_mode', 0))

        # Build cache key from image + prompt params + inputs
        img_hash = hash(image[::8, ::8].tobytes())
        box_in = inputs.get('box')
        pts_in = inputs.get('points')
        
        box_hash = tuple(sorted(box_in.items())) if isinstance(box_in, dict) else None
        pts_hash = str(pts_in) if isinstance(pts_in, list) else None

        prompt_key = (prompt_mode, box_hash, pts_hash, params.get('multimask'),
                      params.get('mask_index'), params.get('auto_best'))

        cache_key = (img_hash, prompt_key)
        if cache_key == getattr(self, '_cache_hash', None) and getattr(self, '_cache_result', None) is not None:
            return self._cache_result

        # ── 3. Execution (with non-blocking lock) ──
        if not self.lock.acquire(blocking=False):
            return empty  # Skip frame if busy

        try:
            if self.device == 'mps':
                torch.mps.empty_cache()

            if img_hash != self._embed_hash:
                self.report_progress(0.2, 'SAM: Encoding image…')
                
                # Convert BGR → RGB for SAM
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                with torch.no_grad():
                    if self.device == 'cuda':
                        with torch.autocast(self.device, dtype=torch.bfloat16):
                            self.predictor.set_image(rgb)
                    else:
                        self.predictor.set_image(rgb)

                self._embed_hash = img_hash

            self.report_progress(0.6, 'SAM: Segmenting…')

            multimask = bool(params.get('multimask', True))
            auto_best = bool(params.get('auto_best', True))
            mask_idx = int(params.get('mask_index', 0))

            predict_kwargs = {'multimask_output': multimask}

            if prompt_mode == 0:
                box_input = inputs.get('box')
                if box_input is None or not isinstance(box_input, dict):
                    self.report_progress(1.0, 'SAM: No box input')
                    return empty
                bbox = self._get_bbox_from_dict(box_input, h, w)
                if bbox is None: return empty
                predict_kwargs['box'] = bbox[None, :]

            elif prompt_mode == 1:
                pts_list = inputs.get('points')
                if not pts_list or not isinstance(pts_list, list):
                    self.report_progress(1.0, 'SAM: No points list')
                    return empty
                
                coords = []
                labels = []
                for p in pts_list:
                    if isinstance(p, dict) and 'x' in p and 'y' in p:
                        coords.append([p['x'] * w, p['y'] * h])
                        labels.append(p.get('label', 1))
                    elif isinstance(p, (list, tuple)) and len(p) >= 2:
                        if p[0] <= 1.0 and p[1] <= 1.0:
                            coords.append([p[0] * w, p[1] * h])
                        else:
                            coords.append([p[0], p[1]])
                        labels.append(1)
                
                if not coords: return empty
                predict_kwargs['point_coords'] = np.array(coords)
                predict_kwargs['point_labels'] = np.array(labels)
            
            else:
                return empty

            with torch.no_grad():
                if self.device == 'cuda':
                    with torch.autocast(self.device, dtype=torch.bfloat16):
                        masks, scores, logits = self.predictor.predict(**predict_kwargs)
                else:
                    masks, scores, logits = self.predictor.predict(**predict_kwargs)

            # Ensure CPU/Numpy
            if hasattr(masks, 'detach'): masks = masks.detach().cpu().numpy()
            if hasattr(scores, 'detach'): scores = scores.detach().cpu().numpy()
            if hasattr(logits, 'detach'): logits = logits.detach().cpu().numpy()

            # Select mask
            if multimask and auto_best:
                best_idx = int(np.argmax(scores))
            else:
                best_idx = min(mask_idx, len(masks) - 1)

            selected_score = float(scores[best_idx])
            selected_logits = logits[best_idx]

            thresh = float(params.get('mask_threshold', 0.0))
            mask_bool = selected_logits > thresh
            mask_uint8 = mask_bool.astype(np.uint8) * 255

            # Post-processing
            refine = int(params.get('refine_pixels', 0))
            smooth = int(params.get('smoothing', 0))
            invert = params.get('invert', False)

            if refine != 0:
                kernel = np.ones((abs(refine), abs(refine)), np.uint8)
                mask_uint8 = cv2.dilate(mask_uint8, kernel) if refine > 0 else cv2.erode(mask_uint8, kernel)
            
            if smooth > 0:
                ksize = smooth * 2 + 1
                mask_uint8 = cv2.GaussianBlur(mask_uint8, (ksize, ksize), 0)
                _, mask_uint8 = cv2.threshold(mask_uint8, 127, 255, cv2.THRESH_BINARY)

            if invert: mask_uint8 = 255 - mask_uint8
            mask_bool = mask_uint8 > 127

            # Visualization
            opacity = float(params.get('overlay_opacity', 50)) / 100.0
            palette = [
                (255, 144, 30), (80, 220, 0), (0, 200, 255), (60, 60, 255),
                (255, 80, 180), (200, 200, 200), (255, 255, 255), (20, 20, 20)
            ]
            c_idx = int(params.get('mask_color_index', 3))
            mb, mg, mr = palette[c_idx % len(palette)]

            overlay = image.copy()
            color_mask = np.zeros_like(image)
            color_mask[mask_bool] = [mb, mg, mr]
            overlay = cv2.addWeighted(overlay, 1.0, color_mask, opacity, 0)

            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, (mb, mg, mr), 2)

            # Draw prompts
            if prompt_mode == 0 and isinstance(box_in, dict):
                bbox = self._get_bbox_from_dict(box_in, h, w)
                if bbox is not None: cv2.rectangle(overlay, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 255), 2)
            elif prompt_mode == 1 and isinstance(pts_in, list):
                for p in pts_in:
                    if isinstance(p, dict) and 'x' in p and 'y' in p:
                        cx, cy = int(p['x'] * w), int(p['y'] * h)
                        color = (0, 220, 80) if p.get('label', 1) == 1 else (60, 60, 255)
                        cv2.circle(overlay, (cx, cy), 5, color, -1)
                        cv2.circle(overlay, (cx, cy), 6, (255, 255, 255), 1)

            cv2.putText(overlay, f"Score: {selected_score:.3f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            self.report_progress(1.0, 'SAM: Done')

            result = {'main': overlay, 'mask': mask_uint8, 'score': selected_score}
            self._cache_hash, self._cache_result = cache_key, result
            return result

        except Exception as e:
            print(f'[SAM] Error: {e}')
            send_notification(f'SAM error: {str(e)[:100]}', level='error', notif_id=_NOTIF_ID)
            self.report_progress(1.0, 'SAM: Error')
            return empty
        finally:
            self.lock.release()
