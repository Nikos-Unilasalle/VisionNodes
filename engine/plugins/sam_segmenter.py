"""
SAM Segmenter — Interactive AI segmentation using SAM 2 (Meta).
Supports bounding box and point prompts for precise object segmentation.
Models are downloaded automatically from HuggingFace on first use.
"""
from registry import vision_node, NodeProcessor, send_notification, hf_ui_progress
import cv2
import numpy as np
import json
import threading
import os

SAM2_AVAILABLE = False
try:
    import torch
    import sam2
    SAM2_AVAILABLE = True
except ImportError:
    torch = None

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
    label='AI Segmenter (SAM)',
    category='segmentation',
    icon='Scan',
    description=(
        "Interactive AI segmentation powered by SAM 2 (Segment Anything Model 2, Meta). "
        "Draw a bounding box or place a point to segment any object with pixel-perfect precision. "
        "Supports four model sizes from Tiny (~40 MB) to Large (~900 MB). "
        "Models download automatically on first use."
    ),
    inputs=[
        {'id': 'image',  'color': 'image'},
        {'id': 'boxes',  'color': 'any',  'label': 'Boxes (single or list)'},
        {'id': 'points', 'color': 'list', 'label': 'Points List'},
    ],
    outputs=[
        {'id': 'main',      'color': 'image',  'label': 'Overlay'},
        {'id': 'mask',      'color': 'mask',   'label': 'Combined Mask'},
        {'id': 'count',     'color': 'scalar', 'label': 'Object Count'},
        {'id': 'areas',     'color': 'list',   'label': 'Areas (px²)'},
        {'id': 'centroids', 'color': 'list',   'label': 'Centroids'},
        {'id': 'contours',  'color': 'list',   'label': 'Contours List'},
    ],
    params=[
        # ── Authentication ──
        {'id': 'hf_token', 'label': 'Hugging Face Token (leave empty if saved)', 'type': 'string',
         'default': ''},

        # ── Model Selection ──
        {'id': 'model', 'label': 'Model', 'type': 'enum',
         'options': _MODEL_NAMES, 'default': 0},

        # ── Trigger ──
        {'id': 'segment', 'label': 'Segment', 'type': 'trigger', 'default': False},

        # ── Prompt Mode ──
        {'id': 'prompt_mode', 'label': 'Prompt Mode', 'type': 'enum',
         'options': ['Box (single)', 'Points List Input Port', 'Automatic (Grid)',
                     'Boxes List (all)'],
         'default': 0},

        # ── Automatic Mode Settings ──
        {'id': 'points_per_side', 'label': 'Points per side (Auto)', 'type': 'int',
         'default': 32, 'min': 8, 'max': 128, 'step': 8},
        {'id': 'pred_iou_thresh', 'label': 'IOU Threshold (Auto)', 'type': 'float',
         'default': 0.8, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'stability_score_thresh', 'label': 'Stability Threshold (Auto)', 'type': 'float',
         'default': 0.95, 'min': 0.0, 'max': 1.0, 'step': 0.05},

        # ── Mask Selection ──
        {'id': 'multimask', 'label': 'Multi-mask (3 candidates)',
         'type': 'boolean', 'default': True},
        {'id': 'mask_select', 'label': 'Candidate (if multi-mask)',
         'type': 'enum', 'options': ['Best (IOU auto)', 'Candidate 1', 'Candidate 2', 'Candidate 3'],
         'default': 0},
        # ── Visualization ──
        {'id': 'overlay_opacity', 'label': 'Overlay Opacity (%)', 'type': 'number',
         'default': 50, 'min': 0, 'max': 100, 'step': 5},
    ],
    colorable=True,
)
class SAMSegmenterNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.predictor = None
        self.generator = None
        self._gen_config = None
        self.current_model_name = ""
        self._loading = False
        self._failed = set()

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

            # Check and install sam2 if missing
            if not self.ensure_packages(['sam2'], pip_names=['git+https://github.com/facebookresearch/sam2.git'], notif_id=_NOTIF_ID):
                return

            # Dynamic imports and patching
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            from sam2.utils.transforms import SAM2Transforms

            def _patched_sam2_transforms_init(self, resolution, mask_threshold, max_hole_area=0.0, max_sprinkle_area=0.0):
                import torch.nn as nn
                from torchvision.transforms import Resize, Normalize, ToTensor
                nn.Module.__init__(self)
                self.resolution = resolution
                self.mask_threshold = mask_threshold
                self.max_hole_area = max_hole_area
                self.max_sprinkle_area = max_sprinkle_area
                self.mean = [0.485, 0.456, 0.406]
                self.std = [0.229, 0.224, 0.225]
                self.to_tensor = ToTensor()
                self.transforms = nn.Sequential(
                    Resize((self.resolution, self.resolution), antialias=True),
                    Normalize(self.mean, self.std),
                )
            SAM2Transforms.__init__ = _patched_sam2_transforms_init

            # --- Optimization: Limit CPU threads during heavy model loading ---
            # This prevents starving the main event loop / WebSocket server,
            # especially with large models like SAM 2 Large (~900 MB).
            old_threads = torch.get_num_threads()
            torch.set_num_threads(1)
            
            try:
                # Always load on CPU first (from_pretrained doesn't support MPS directly)
                from sam2.sam2_image_predictor import SAM2ImagePredictor
                with hf_ui_progress(_NOTIF_ID, prefix=f"Downloading {model_name}"):
                    predictor = SAM2ImagePredictor.from_pretrained(hf_id, device='cpu')
            finally:
                torch.set_num_threads(old_threads)

            # Move model to the target accelerator
            if self.device in ('mps', 'cuda'):
                predictor.model = predictor.model.to(self.device)

            self.predictor = predictor
            self.generator = None # Reset generator if model changes
            self._gen_config = None
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

    def _status_overlay(self, image, text, color=(255, 200, 50)):
        """Draw a status banner on a copy of the image."""
        if image is None:
            return None
        out = image.copy()
        cv2.rectangle(out, (0, 0), (out.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(out, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, color, 1, cv2.LINE_AA)
        return out

    def _normalize_box_inputs(self, inputs):
        """Smart unified 'boxes' port: accepts a single box dict (YOLO) or a
        boxes list (Grounding DINO). Returns (single_box_dict_or_None, boxes_list)."""
        raw = inputs.get('boxes')
        if raw is None:
            raw = inputs.get('box')  # back-compat for old 'box' handle
        if isinstance(raw, dict):
            return raw, [raw]
        if isinstance(raw, list):
            single = raw[0] if (raw and isinstance(raw[0], dict)) else None
            return single, raw
        return None, []

    def process(self, inputs, params):
        image = inputs.get('image')

        def empty(msg=None, color=(255, 200, 50)):
            main = self._status_overlay(image, msg, color) if msg and image is not None else image
            return {'main': main, 'mask': None, 'count': 0,
                    'areas': [], 'centroids': [], 'contours': []}

        if image is None:
            return empty()

        if not self.ensure_packages(['sam2'], pip_names=['git+https://github.com/facebookresearch/sam2.git'], notif_id=_NOTIF_ID):
            return empty()

        if torch is None:
            return empty('torch not available — install pytorch')

        hf_token = params.get('hf_token', '')

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
            if model_name in self._failed:
                return empty(f'SAM load failed: {model_name} — check HF token', color=(60, 60, 255))
            if not self._loading:
                self._loading = True
                self.predictor = None
                threading.Thread(
                    target=self._load_model_thread,
                    args=(model_name,),
                    daemon=True
                ).start()
            return empty(f'Loading {model_name}…  (first run downloads model)')

        if self.predictor is None:
            return empty(f'Loading {model_name}…')

        # ── Trigger gate ──
        triggered = bool(params.get('segment', False))
        if not triggered:
            if getattr(self, '_cache_result', None) is not None:
                return self._cache_result
            return empty('Press Segment to run')

        h, w = image.shape[:2]

        # ── 2. Determine prompt ──
        prompt_mode = int(params.get('prompt_mode', 0))

        # Build cache key from image + prompt params + inputs
        img_hash = hash(image[::8, ::8].tobytes())
        box_in, boxes_in = self._normalize_box_inputs(inputs)
        pts_in = inputs.get('points')

        box_hash = tuple(sorted(box_in.items())) if isinstance(box_in, dict) else None

        pts_hash   = str(pts_in)                 if isinstance(pts_in, list) else None
        boxes_hash = str(boxes_in)               if isinstance(boxes_in, list) else None

        prompt_key = (prompt_mode, box_hash, pts_hash, boxes_hash,
                      params.get('multimask'), params.get('mask_select', 0),
                      params.get('overlay_opacity', 50),
                      params.get('points_per_side', 32),
                      params.get('pred_iou_thresh', 0.8),
                      params.get('stability_score_thresh', 0.95))

        cache_key = (img_hash, prompt_key)
        if cache_key == getattr(self, '_cache_hash', None) and getattr(self, '_cache_result', None) is not None:
            return self._cache_result

        # ── 3. Set image embedding (cached) ──
        self.report_progress(0.2, 'SAM: Computing embedding…')

        try:
            if img_hash != self._embed_hash:
                # Convert BGR → RGB for SAM
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                with torch.inference_mode():
                    if self.device == 'cuda':
                        with torch.autocast(self.device, dtype=torch.bfloat16):
                            self.predictor.set_image(rgb)
                    else:
                        self.predictor.set_image(rgb)

                self._embed_hash = img_hash

            # ── 4. Run prediction ──
            multimask = bool(params.get('multimask', True))

            if prompt_mode == 2:
                # ── 4a. Automatic Mode (Grid) ──
                self.report_progress(0.6, 'SAM: Generating masks (Grid)…')
                
                pps = int(params.get('points_per_side', 32))
                iou_t = float(params.get('pred_iou_thresh', 0.8))
                stab_t = float(params.get('stability_score_thresh', 0.95))
                
                gen_config = (pps, iou_t, stab_t)
                if self.generator is None or self._gen_config != gen_config:
                    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
                    self.generator = SAM2AutomaticMaskGenerator(
                        model=self.predictor.model,
                        points_per_side=pps,
                        pred_iou_thresh=iou_t,
                        stability_score_thresh=stab_t
                    )
                    self._gen_config = gen_config

                # SAM 2 generator expects RGB
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                with torch.inference_mode():
                    masks_data = self.generator.generate(rgb)

                # Process results: combine into a colored label map
                overlay = image.copy()
                opacity = float(params.get('overlay_opacity', 50)) / 100.0
                
                label_map = np.zeros((h, w, 3), dtype=np.uint8)
                combined_mask = np.zeros((h, w), dtype=np.uint8)
                
                areas = []
                centroids = []
                all_contours = []

                for i, m in enumerate(masks_data):
                    mask = m['segmentation']
                    if hasattr(mask, 'cpu'):
                        mask = mask.detach().cpu().numpy()
                    mask = mask > 0

                    area = float(m.get('area', np.sum(mask)))
                    areas.append(area)

                    bbox = m.get('bbox', [0, 0, 0, 0])
                    centroids.append([float(bbox[0] + bbox[2] / 2), float(bbox[1] + bbox[3] / 2)])

                    m_u8 = mask.astype(np.uint8) * 255
                    cnts, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if cnts:
                        all_contours.append(cnts[0].reshape(-1, 2).tolist())
                        cv2.drawContours(overlay, cnts, -1, (255, 255, 255), 1)

                    color = [
                        int((i * 67  + 40) % 200 + 55),
                        int((i * 137 + 80) % 200 + 55),
                        int((i * 197 + 120) % 200 + 55),
                    ]
                    label_map[mask] = color
                    combined_mask[mask] = 255

                # Alpha blend only in masked regions
                blended = cv2.addWeighted(overlay, 1.0 - opacity, label_map, opacity, 0)
                region  = label_map.any(axis=2)
                overlay[region] = blended[region]

                self.report_progress(1.0, f'SAM: {len(masks_data)} objects found')
                result = {
                    'main': overlay,
                    'mask': combined_mask,
                    'count': float(len(masks_data)),
                    'areas': areas,
                    'centroids': centroids,
                    'contours': all_contours,
                }
                self._cache_hash = cache_key
                self._cache_result = result
                return result

            # ── 4b. Boxes List mode (Grounding DINO → SAM batch) ──
            if prompt_mode == 3:
                boxes_input = boxes_in
                if not isinstance(boxes_input, list) or len(boxes_input) == 0:
                    return empty('No boxes — connect a boxes list to the boxes port')

                pixel_boxes = []
                for b in boxes_input:
                    if not isinstance(b, dict):
                        continue
                    xmin = float(b.get('xmin', 0))
                    ymin = float(b.get('ymin', 0))
                    bw   = float(b.get('width',  0))
                    bh   = float(b.get('height', 0))
                    x1 = int(max(0, xmin * w))
                    y1 = int(max(0, ymin * h))
                    x2 = int(min(w, (xmin + bw) * w))
                    y2 = int(min(h, (ymin + bh) * h))
                    if x2 > x1 and y2 > y1:
                        pixel_boxes.append([x1, y1, x2, y2])

                if not pixel_boxes:
                    return empty('Boxes list empty or invalid format')

                n_boxes = len(pixel_boxes)
                self.report_progress(0.6, f'SAM: Segmenting {n_boxes} objects…')

                all_boxes_np = np.array(pixel_boxes)  # (N, 4) pixel xyxy

                # Chunk the batch: a single predict() on hundreds of boxes can
                # exhaust GPU memory (dense GDINO output → MPS/CUDA OOM).
                # The image embedding is cached, so per-chunk predict is cheap.
                CHUNK = 24
                mask_chunks = []
                for start in range(0, n_boxes, CHUNK):
                    box_chunk = all_boxes_np[start:start + CHUNK]
                    self.report_progress(
                        0.6 + 0.3 * start / max(n_boxes, 1),
                        f'SAM: Segmenting {start + len(box_chunk)}/{n_boxes}…'
                    )
                    with torch.inference_mode():
                        if self.device == 'cuda':
                            with torch.autocast(self.device, dtype=torch.bfloat16):
                                m, _, _ = self.predictor.predict(box=box_chunk, multimask_output=False)
                        else:
                            m, _, _ = self.predictor.predict(box=box_chunk, multimask_output=False)
                    if hasattr(m, 'cpu'):
                        m = m.detach().cpu().numpy()
                    if m.ndim == 4:
                        m = m[:, 0]            # (k, 1, H, W) → (k, H, W)
                    elif m.ndim == 2:
                        m = m[None, ...]       # single box → (1, H, W)
                    mask_chunks.append(m)

                masks = np.concatenate(mask_chunks, axis=0)  # (N, H, W)

                opacity = float(params.get('overlay_opacity', 50)) / 100.0
                label_map    = np.zeros((h, w, 3), dtype=np.uint8)
                combined_mask = np.zeros((h, w), dtype=np.uint8)
                areas, centroids, all_contours = [], [], []

                for i, mask in enumerate(masks):
                    mask_bool = mask > 0
                    color = [
                        int((i * 67  + 40) % 200 + 55),
                        int((i * 137 + 80) % 200 + 55),
                        int((i * 197 + 120) % 200 + 55),
                    ]
                    label_map[mask_bool] = color
                    combined_mask[mask_bool] = 255
                    areas.append(float(np.sum(mask_bool)))

                    m_u8 = mask_bool.astype(np.uint8) * 255
                    cnts, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if cnts:
                        M = cv2.moments(m_u8)
                        cx = float(M['m10'] / M['m00']) if M['m00'] != 0 else 0.0
                        cy = float(M['m01'] / M['m00']) if M['m00'] != 0 else 0.0
                        centroids.append([cx, cy])
                        all_contours.append(cnts[0].reshape(-1, 2).tolist())
                    else:
                        centroids.append([0.0, 0.0])
                        all_contours.append([])

                # Proper alpha blend ONLY in masked regions (not additive)
                overlay = image.copy()
                blended = cv2.addWeighted(image, 1.0 - opacity, label_map, opacity, 0)
                region  = label_map.any(axis=2)
                overlay[region] = blended[region]

                for i, mask in enumerate(masks):
                    m_u8 = (mask > 0).astype(np.uint8) * 255
                    cnts, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    cv2.drawContours(overlay, cnts, -1, (255, 255, 255), 1)
                    x1, y1, x2, y2 = pixel_boxes[i]
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 255), 1)

                self.report_progress(1.0, f'SAM: {n_boxes} objects segmented')
                result = {
                    'main': overlay, 'mask': combined_mask,
                    'count': float(n_boxes),
                    'areas': areas, 'centroids': centroids, 'contours': all_contours,
                }
                self._cache_hash = cache_key
                self._cache_result = result
                return result

            # ── 4c. Prompted Mode (Box / Points) ──
            self.report_progress(0.6, 'SAM: Segmenting…')

            predict_kwargs = {
                'multimask_output': multimask,
            }

            # Auto-detect mode if the selected input port is empty
            box_input  = box_in
            pts_input  = inputs.get('points')
            has_box    = isinstance(box_input, dict)
            has_points = isinstance(pts_input, list) and len(pts_input) > 0

            if prompt_mode == 0 and not has_box and has_points:
                prompt_mode = 1   # fall through to points
            elif prompt_mode == 1 and not has_points and has_box:
                prompt_mode = 0   # fall through to box

            if prompt_mode == 0:
                # Box from input port
                if not has_box:
                    self.report_progress(1.0, 'SAM: No box input connected')
                    return empty('No box connected — set Prompt Mode to Points')
                bbox = self._get_bbox_from_dict(box_input, h, w)
                if bbox is None:
                    return empty('Invalid box input')
                predict_kwargs['box'] = bbox[None, :]

            elif prompt_mode == 1:
                # Points List from input port
                pts_list = inputs.get('points')
                if not pts_list or not isinstance(pts_list, list):
                    self.report_progress(1.0, 'SAM: No points list connected')
                    return empty('No points connected — connect Manual Points → POINTS')

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

                if not coords:
                    return empty('Points list empty — click on Manual Points to add points')

                predict_kwargs['point_coords'] = np.array(coords)
                predict_kwargs['point_labels'] = np.array(labels)

            else:
                return empty('Unknown prompt mode')

            with torch.inference_mode():
                if self.device == 'cuda':
                    with torch.autocast(self.device, dtype=torch.bfloat16):
                        masks, scores, logits = self.predictor.predict(**predict_kwargs)
                else:
                    masks, scores, logits = self.predictor.predict(**predict_kwargs)

        except Exception as e:
            print(f'[SAM] Prediction error: {e}')
            send_notification(
                f'SAM error: {str(e)[:120]}',
                level='error', notif_id=_NOTIF_ID
            )
            self.report_progress(1.0, 'SAM: Error')
            return empty(f'SAM error: {str(e)[:80]}', color=(60, 60, 255))

        # ── 5. Select mask ──
        mask_select = int(params.get('mask_select', 0))
        if not multimask or mask_select == 0:
            best_idx = int(np.argmax(scores))
        else:
            best_idx = min(mask_select - 1, len(masks) - 1)

        selected_score = float(scores[best_idx])
        selected_mask = masks[best_idx]
        
        # CRITICAL: Convert torch tensor to numpy if needed
        if hasattr(selected_mask, 'cpu'):
            selected_mask = selected_mask.detach().cpu().numpy()

        # masks from SAM 2 are typically boolean or 0/1. Ensure it's uint8
        mask_bool = selected_mask > 0
        mask_uint8 = mask_bool.astype(np.uint8) * 255


        # ── 6. Build overlay visualization ──
        opacity = float(params.get('overlay_opacity', 50)) / 100.0
        
        # Original default green color
        mb, mg, mr = (0, 255, 0)

        overlay = image.copy()
        color_mask = np.zeros_like(image)
        color_mask[mask_bool] = [mb, mg, mr]

        # Proper alpha blend ONLY in the masked region (not additive)
        blended = cv2.addWeighted(overlay, 1.0 - opacity, color_mask, opacity, 0)
        overlay[mask_bool] = blended[mask_bool]

        # Draw contour on overlay for clarity
        contours, _ = cv2.findContours(
            mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours, -1, (mb, mg, mr), 2)

        # Draw the prompt indicator on the overlay
        if prompt_mode == 0:
            # Draw box from input
            box_input = box_in
            if isinstance(box_input, dict):
                bbox = self._get_bbox_from_dict(box_input, h, w)
                if bbox is not None:
                    cv2.rectangle(overlay, (bbox[0], bbox[1]),
                                  (bbox[2], bbox[3]), (0, 255, 255), 2)
        elif prompt_mode == 1:
            # Draw multi-points from input
            pts_list = inputs.get('points')
            if isinstance(pts_list, list):
                for p in pts_list:
                    if isinstance(p, dict) and 'x' in p and 'y' in p:
                        cx, cy = int(p['x'] * w), int(p['y'] * h)
                        is_fg = p.get('label', 1) == 1
                        color = (0, 220, 80) if is_fg else (60, 60, 255)
                        cv2.circle(overlay, (cx, cy), 5, color, -1)
                        cv2.circle(overlay, (cx, cy), 6, (255, 255, 255), 1)

        # Add score text
        cv2.putText(
            overlay, f"Score: {selected_score:.3f}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
            0.8, (255, 255, 255), 2
        )

        self.report_progress(1.0, 'SAM: Done')

        # Calculate metrics for the single mask
        area = float(np.sum(mask_bool))
        
        # Centroid
        M = cv2.moments(mask_uint8)
        if M["m00"] != 0:
            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])
        else:
            cx, cy = 0.0, 0.0
            
        # Contour list
        cnt_list = []
        if contours:
            cnt_list = [c.reshape(-1, 2).tolist() for c in contours]

        result = {
            'main': overlay,
            'mask': mask_uint8,
            'count': 1.0,
            'areas': [area],
            'centroids': [[cx, cy]],
            'contours': cnt_list,
        }

        # Cache result
        self._cache_hash = cache_key
        self._cache_result = result

        return result
