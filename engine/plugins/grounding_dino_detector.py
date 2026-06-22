"""
Grounding DINO Detector — Zero-shot object detection via text prompts.
Uses transformers GroundingDINO. Models auto-download from HuggingFace.
Connect boxes_list → SAM Segmenter (Boxes List mode) for precise per-object segmentation.

Tile mode: splits image into NxN patches, runs GDINO on each, merges with global NMS.
Essential for dense repeated objects (stones, cells, etc.) that a single pass misses.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import threading
import json
import os

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

_NOTIF_ID = 'grounding_dino'

_HF_MODELS = {
    'Tiny': 'IDEA-Research/grounding-dino-tiny',
    'Base': 'IDEA-Research/grounding-dino-base',
}
_MODEL_NAMES = list(_HF_MODELS.keys())
_TILE_OPTIONS = ['None (full image)', '2×2', '3×3', '4×4', '5×5']
_TILE_GRIDS   = [1, 2, 3, 4, 5]


@vision_node(
    type_id='grounding_dino_detector',
    label='Grounding DINO',
    category='analysis',
    icon='Search',
    description=(
        "Zero-shot object detection using Grounding DINO (IDEA Research). "
        "Detect any object by typing its name as a text prompt (e.g. 'stone'). "
        "Use Tile Mode for dense scenes (stones, cells…) — splits image into patches "
        "and merges detections. Connect boxes_list → SAM Segmenter for precise segmentation."
    ),
    inputs=[
        {'id': 'image',  'color': 'image'},
        {'id': 'prompt', 'color': 'string', 'label': 'Text Prompt (port)'},
    ],
    outputs=[
        {'id': 'main',       'color': 'image',  'label': 'Overlay'},
        {'id': 'boxes_list', 'color': 'list',   'label': 'Boxes List'},
        {'id': 'count',      'color': 'scalar', 'label': 'Count'},
        {'id': 'scores',     'color': 'list',   'label': 'Confidence Scores'},
    ],
    params=[
        {'id': 'hf_token',       'label': 'HuggingFace Token (leave empty if saved)', 'type': 'string',
         'default': ''},
        {'id': 'model',          'label': 'Model',          'type': 'enum',
         'options': _MODEL_NAMES, 'default': 0},
        {'id': 'text_prompt',    'label': 'Text Prompt',    'type': 'string',
         'default': 'stone'},
        {'id': 'detect',         'label': 'Detect', 'type': 'trigger', 'default': False},
        {'id': '_sec_detection', 'label': 'Detection', 'type': 'section'},
        {'id': 'tile_mode',      'label': 'Tile Mode',      'type': 'enum',
         'options': _TILE_OPTIONS, 'default': 0},
        {'id': 'tile_overlap',   'label': 'Tile Overlap px', 'type': 'int',
         'default': 64, 'min': 0, 'max': 256, 'step': 16},
        {'id': 'box_threshold',  'label': 'Box Threshold',  'type': 'float',
         'default': 0.20, 'min': 0.05, 'max': 0.95, 'step': 0.05},
        {'id': 'text_threshold', 'label': 'Text Threshold', 'type': 'float',
         'default': 0.15, 'min': 0.05, 'max': 0.95, 'step': 0.05},
        {'id': 'nms_threshold',  'label': 'NMS Threshold',  'type': 'float',
         'default': 0.5, 'min': 0.1, 'max': 1.0, 'step': 0.05},
        {'id': 'min_area',       'label': 'Min Area (% image)', 'type': 'float',
         'default': 0.0, 'min': 0.0, 'max': 100.0, 'step': 0.1},
        {'id': 'max_area',       'label': 'Max Area (% image)', 'type': 'float',
         'default': 50.0, 'min': 1.0, 'max': 100.0, 'step': 1.0},
        {'id': 'max_boxes',      'label': 'Max Boxes (0=all)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 1000},
        {'id': '_sec_display',   'label': 'Display', 'type': 'section'},
        {'id': 'label_mode',     'label': 'Label Mode',     'type': 'enum',
         'options': ['ID', 'ID + Score', 'Label + Score', 'None'], 'default': 0},
        {'id': 'label_pos',      'label': 'Label Position', 'type': 'enum',
         'options': ['Top-Left', 'Center'], 'default': 0},
    ],
    colorable=True,
)
class GroundingDINODetectorNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.processor = None
        self.model = None
        self.current_model_name = ''
        self._loading = False
        self._failed = set()
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

    def _load_model_thread(self, model_name: str) -> None:
        try:
            hf_id = _HF_MODELS[model_name]
            send_notification(f'GDINO: Downloading {model_name}…', progress=0.1, notif_id=_NOTIF_ID)

            if not self.ensure_packages(['transformers', 'timm'], notif_id=_NOTIF_ID):
                self._failed.add(model_name)
                return

            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

            proc = AutoProcessor.from_pretrained(hf_id)
            mdl  = AutoModelForZeroShotObjectDetection.from_pretrained(hf_id)
            mdl  = mdl.to(self.device)
            mdl.eval()

            self.processor = proc
            self.model = mdl
            self.current_model_name = model_name
            self._cache_result = None

            send_notification(f'GDINO: {model_name} ready ✓', progress=1.0, notif_id=_NOTIF_ID)
        except Exception as e:
            self._failed.add(model_name)
            print(f'[GDINO] Load FAILED: {e}')
            send_notification(f'GDINO error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
        finally:
            self._loading = False

    def _status_overlay(self, image: np.ndarray, text: str) -> np.ndarray:
        out = image.copy()
        cv2.rectangle(out, (0, 0), (out.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(out, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 200, 50), 1, cv2.LINE_AA)
        return out

    def _empty(self, image, msg: str = None) -> dict:
        main = self._status_overlay(image, msg) if (msg and image is not None) else image
        return {'main': main, 'boxes_list': [], 'count': 0.0, 'scores': []}

    def _infer_patch(self, pil_patch, text_prompt: str, box_thr: float, text_thr: float) -> tuple:
        """Run GDINO on one PIL patch. Returns (boxes_xyxy_px, scores, labels)."""
        ph, pw = pil_patch.size[1], pil_patch.size[0]
        inp = self.processor(images=pil_patch, text=text_prompt, return_tensors='pt')
        inp = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in inp.items()}
        with torch.no_grad():
            if self.device == 'cuda':
                with torch.autocast('cuda', dtype=torch.float16):
                    out = self.model(**inp)
            else:
                out = self.model(**inp)
        try:
            res = self.processor.post_process_grounded_object_detection(
                out, inp['input_ids'],
                box_threshold=box_thr, text_threshold=text_thr,
                target_sizes=[(ph, pw)],
            )
        except TypeError:
            res = self.processor.post_process_grounded_object_detection(
                out, inp['input_ids'],
                threshold=box_thr,
                target_sizes=[(ph, pw)],
            )
        r = res[0]
        boxes  = r['boxes'].cpu().numpy() if len(r['boxes']) else np.zeros((0, 4))
        scores = r['scores'].cpu().numpy() if len(r['scores']) else np.zeros(0)
        labels = r['labels']
        return boxes, scores, labels

    def process(self, inputs: dict, params: dict) -> dict:
        image = inputs.get('image')
        if image is None:
            return self._empty(None)

        # HF token — persist to ~/.vnstudio/secrets.json
        hf_token = params.get('hf_token', '')
        secrets_path = os.path.expanduser('~/.vnstudio/secrets.json')
        if hf_token:
            os.makedirs(os.path.dirname(secrets_path), exist_ok=True)
            secrets = {}
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path) as f:
                        secrets = json.load(f)
                except Exception:
                    pass
            secrets['hf_token'] = hf_token
            try:
                with open(secrets_path, 'w') as f:
                    json.dump(secrets, f)
            except Exception:
                pass
        else:
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path) as f:
                        hf_token = json.load(f).get('hf_token', '')
                except Exception:
                    pass
        if hf_token:
            os.environ['HF_TOKEN'] = hf_token

        # Model loading
        model_idx  = int(params.get('model', 0))
        model_name = _MODEL_NAMES[min(model_idx, len(_MODEL_NAMES) - 1)]

        if model_name != self.current_model_name:
            if model_name in self._failed:
                return self._empty(image, f'GDINO load failed: {model_name}')
            if not self._loading:
                self._loading = True
                self.model = None
                threading.Thread(target=self._load_model_thread, args=(model_name,), daemon=True).start()
            return self._empty(image, f'Loading {model_name}…')

        if self.model is None:
            return self._empty(image, f'Loading {model_name}…')

        # Normalize image to uint8 BGR (Blend Modes and other nodes can output float32)
        if image.dtype != np.uint8:
            if image.dtype in (np.float32, np.float64):
                scale = 255.0 if image.max() <= 1.0 else 1.0
                image = np.clip(image * scale, 0, 255).astype(np.uint8)
            else:
                image = np.clip(image, 0, 255).astype(np.uint8)

        # Trigger gate — only run on button press
        triggered = bool(params.get('detect', False))
        if not triggered:
            if self._cache_result is not None:
                return self._cache_result
            return self._empty(image, 'Press Detect to run')

        # Read params
        text_prompt = inputs.get('prompt') or params.get('text_prompt', 'stone')
        if not isinstance(text_prompt, str) or not text_prompt.strip():
            return self._empty(image, 'No text prompt — set param or connect string port')

        box_thr     = float(params.get('box_threshold',  0.20))
        text_thr    = float(params.get('text_threshold', 0.15))
        nms_thr     = float(params.get('nms_threshold',  0.5))
        label_mode  = int(params.get('label_mode', 0))
        label_pos   = int(params.get('label_pos', 0))   # 0=top-left, 1=center
        min_area    = float(params.get('min_area', 0.0)) / 100.0
        max_area    = float(params.get('max_area', 50.0)) / 100.0
        max_boxes   = int(params.get('max_boxes', 0))
        tile_idx    = int(params.get('tile_mode', 0))
        grid        = _TILE_GRIDS[min(tile_idx, len(_TILE_GRIDS) - 1)]
        overlap     = int(params.get('tile_overlap', 64))

        h, w = image.shape[:2]

        try:
            from PIL import Image as PILImage
            pil_img = PILImage.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

            if grid == 1:
                # ── Single pass ──
                self.report_progress(0.3, 'GDINO: detecting…')
                boxes_pixel, scores, labels = self._infer_patch(pil_img, text_prompt, box_thr, text_thr)

            else:
                # ── Tile mode: NxN patches with overlap ──
                tile_w = w // grid
                tile_h = h // grid
                all_boxes  = []
                all_scores = []
                all_labels = []
                n_tiles = grid * grid

                for idx, (row, col) in enumerate(
                    (r, c) for r in range(grid) for c in range(grid)
                ):
                    x0 = max(0, col * tile_w - overlap)
                    y0 = max(0, row * tile_h - overlap)
                    x1 = min(w, (col + 1) * tile_w + overlap)
                    y1 = min(h, (row + 1) * tile_h + overlap)

                    patch = pil_img.crop((x0, y0, x1, y1))
                    self.report_progress(
                        0.1 + 0.8 * idx / n_tiles,
                        f'GDINO tile {idx + 1}/{n_tiles}…'
                    )

                    p_boxes, p_scores, p_labels = self._infer_patch(
                        patch, text_prompt, box_thr, text_thr
                    )

                    # Remap from patch coords → full image coords
                    if len(p_boxes):
                        p_boxes[:, 0] += x0
                        p_boxes[:, 1] += y0
                        p_boxes[:, 2] += x0
                        p_boxes[:, 3] += y0
                        # Clamp to image bounds
                        p_boxes[:, [0, 2]] = np.clip(p_boxes[:, [0, 2]], 0, w)
                        p_boxes[:, [1, 3]] = np.clip(p_boxes[:, [1, 3]], 0, h)
                        all_boxes.append(p_boxes)
                        all_scores.extend(p_scores.tolist())
                        all_labels.extend(p_labels)

                if all_boxes:
                    boxes_pixel = np.vstack(all_boxes)
                    scores      = np.array(all_scores)
                    labels      = all_labels
                else:
                    boxes_pixel = np.zeros((0, 4))
                    scores      = np.zeros(0)
                    labels      = []

        except Exception as e:
            print(f'[GDINO] Inference error: {e}')
            send_notification(f'GDINO error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
            return self._empty(image, f'GDINO error: {str(e)[:60]}')

        # Global NMS (critical in tile mode — boxes from adjacent tiles overlap)
        if len(boxes_pixel) > 1:
            keep        = _nms(boxes_pixel, scores, nms_thr)
            boxes_pixel = boxes_pixel[keep]
            scores      = scores[keep]
            labels      = [labels[i] for i in keep]

        # Area filter: drop boxes outside [min_area, max_area] fraction of image.
        # Removes the common GDINO failure where one box engulfs the whole image.
        if len(boxes_pixel) > 0:
            img_area  = float(w * h)
            box_areas = ((boxes_pixel[:, 2] - boxes_pixel[:, 0]) *
                         (boxes_pixel[:, 3] - boxes_pixel[:, 1])) / img_area
            keep_area = np.where((box_areas >= min_area) & (box_areas <= max_area))[0]
            boxes_pixel = boxes_pixel[keep_area]
            scores      = scores[keep_area]
            labels      = [labels[i] for i in keep_area]

        if max_boxes > 0 and len(boxes_pixel) > max_boxes:
            top_idx     = np.argsort(scores)[::-1][:max_boxes]
            boxes_pixel = boxes_pixel[top_idx]
            scores      = scores[top_idx]
            labels      = [labels[i] for i in top_idx]

        # Build normalized YOLO-compatible output (matches SAM box port format)
        boxes_list = []
        for i, (box, score, label) in enumerate(zip(boxes_pixel, scores, labels)):
            x1, y1, x2, y2 = box
            xmin = float(x1) / w
            ymin = float(y1) / h
            bw   = float(x2 - x1) / w
            bh   = float(y2 - y1) / h
            boxes_list.append({
                'id':     i,
                'label':  label,
                'score':  float(score),
                'xmin':   xmin,
                'ymin':   ymin,
                'width':  bw,
                'height': bh,
                '_type':  'graphics',
                'shape':  'rect',
                'pts':    [[xmin, ymin], [xmin + bw, ymin + bh]],
                'r': 0, 'g': 220, 'b': 120, 'thickness': 2,
            })

        # Visualization
        overlay = image.copy()
        for i, (box, score, label) in enumerate(zip(boxes_pixel, scores, labels)):
            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            color = (
                int((i * 67  + 40) % 200 + 55),
                int((i * 137 + 80) % 200 + 55),
                int((i * 197 + 120) % 200 + 55),
            )
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            # label_mode: 0=ID, 1=ID+Score, 2=Label+Score, 3=None
            txt = None
            if label_mode == 0:
                txt = f'#{i}'
            elif label_mode == 1:
                txt = f'#{i} {score:.2f}'
            elif label_mode == 2:
                txt = f'{label} {score:.2f}'
            if txt:
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                if label_pos == 1:
                    # Center: place label box at the bbox centroid
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    bx, by = cx - tw // 2, cy + th // 2
                else:
                    # Top-Left: label box hugging the top edge
                    bx, by = x1 + 2, y1 - 4
                cv2.rectangle(overlay, (bx - 2, by - th - 4), (bx + tw + 2, by + 2), color, -1)
                cv2.putText(overlay, txt, (bx, by),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        n = len(boxes_list)
        tile_str = f' ({grid}×{grid} tiles)' if grid > 1 else ''
        self.report_progress(1.0, f'GDINO: {n} object{"s" if n != 1 else ""} detected{tile_str}')

        out = {
            'main':       overlay,
            'boxes_list': boxes_list,
            'count':      float(n),
            'scores':     [float(s) for s in scores],
        }
        self._cache_result = out
        return out


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list:
    """CPU NMS — returns list of kept indices sorted by descending score."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep  = []
    while len(order) > 0:
        i = int(order[0])
        keep.append(i)
        if len(order) == 1:
            break
        xx1  = np.maximum(x1[i], x1[order[1:]])
        yy1  = np.maximum(y1[i], y1[order[1:]])
        xx2  = np.minimum(x2[i], x2[order[1:]])
        yy2  = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou  = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou < iou_threshold]
    return keep
