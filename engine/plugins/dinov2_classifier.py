"""
DINOv2 Classifier — Zero-shot image classification via k-NN over reference embeddings.
Uses Meta DINOv2 (facebook/dinov2-*) as a frozen feature extractor. No training, no head.

Pipeline:  Grounding DINO → boxes_list ─┐
                                        ├→ DINOv2 Classifier → labels_list + overlay
           Webcam → image ─────────────┘

References: point `ref_dir` at a folder using the ImageFolder convention:
    ref_dir/
        cat/   img1.jpg img2.jpg …
        dog/   img3.png …
Each subfolder name is a class. Press "Build Refs" to embed them (cached in memory).
Each detected crop is embedded and classified by weighted k-NN against the references.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import os
import threading

_NOTIF_ID = 'dinov2_classifier'

_HF_MODELS = {
    'Base (ViT-B/14, 768d)':  'facebook/dinov2-base',
    'Large (ViT-L/14, 1024d)': 'facebook/dinov2-large',
}
_MODEL_NAMES = list(_HF_MODELS.keys())
_IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff')


@vision_node(
    type_id='dinov2_classifier',
    label='DINOv2 Classifier',
    category='analysis',
    icon='Boxes',
    description=(
        "Zero-shot classification with DINOv2 (Meta). No training: classifies each "
        "input crop by weighted k-NN against reference embeddings. "
        "Point 'Reference Folder' at an ImageFolder dir (subfolders = classes), press "
        "'Build Refs', then connect boxes_list from Grounding DINO to classify each box."
    ),
    inputs=[
        {'id': 'image',      'color': 'image'},
        {'id': 'boxes_list', 'color': 'list', 'label': 'Boxes List'},
    ],
    outputs=[
        {'id': 'main',        'color': 'image',  'label': 'Overlay'},
        {'id': 'labels_list', 'color': 'list',   'label': 'Labels List'},
        {'id': 'classes',     'color': 'dict',   'label': 'Classes {type:[ids]}'},
        {'id': 'summary',     'color': 'dict',   'label': 'Summary (per-class)'},
        {'id': 'count',       'color': 'scalar', 'label': 'Count'},
    ],
    params=[
        {'id': 'hf_token',   'label': 'HuggingFace Token (leave empty if saved)', 'type': 'string',
         'default': ''},
        {'id': 'model',      'label': 'Model', 'type': 'enum',
         'options': _MODEL_NAMES, 'default': 0},
        {'id': 'ref_dir',    'label': 'Reference Folder (ImageFolder)', 'type': 'string',
         'default': ''},
        {'id': 'build_refs', 'label': 'Build Refs', 'type': 'trigger', 'default': False},
        {'id': 'k',          'label': 'k (neighbors)', 'type': 'int',
         'default': 5, 'min': 1, 'max': 50},
        {'id': 'metric',     'label': 'Metric', 'type': 'enum',
         'options': ['Cosine', 'Euclidean'], 'default': 0},
        {'id': 'min_score',  'label': 'Min Score (else "unknown")', 'type': 'float',
         'default': 0.0, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'crop_pad',   'label': 'Crop Padding %', 'type': 'float',
         'default': 0.0, 'min': 0.0, 'max': 50.0, 'step': 1.0},
        {'id': 'whole_frame', 'label': 'Classify Whole Frame (ignore boxes)', 'type': 'bool',
         'default': False},
        {'id': 'label_mode', 'label': 'Label Mode', 'type': 'enum',
         'options': ['Label + Score', 'Label', 'None'], 'default': 0},

        # ── Run gate ──
        {'id': 'classify', 'label': 'Classify', 'type': 'trigger', 'default': False},

        # ── Persistence ──
        {'id': 'save_path', 'label': 'Save File (.cls.json)', 'type': 'file_path',
         'default': '~/VNStudio/exports/classification.cls.json',
         'filters': [{'name': 'Classification', 'extensions': ['json']}]},
        {'id': 'save_classif', 'label': 'Save Classification', 'type': 'trigger', 'default': False},
    ],
    colorable=True,
)
class DINOv2ClassifierNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.processor = None
        self.model = None
        self.current_model_name = ''
        self._loading = False
        self._failed = set()

        # Reference embedding store
        self._ref_embeds = None      # np.ndarray (N, D), L2-normalized
        self._ref_labels = None      # list[str] length N
        self._ref_dir = ''
        self._ref_model = ''
        self._building = False

        # Result cache (so downstream stays fed without re-running the heavy model)
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

    # ── Model loading ──────────────────────────────────────────────────────
    def _load_model_thread(self, model_name: str) -> None:
        try:
            hf_id = _HF_MODELS[model_name]
            send_notification(f'DINOv2: Downloading {model_name}…', progress=0.1, notif_id=_NOTIF_ID)

            if not self.ensure_packages(['transformers', 'timm'], notif_id=_NOTIF_ID):
                self._failed.add(model_name)
                return

            from transformers import AutoImageProcessor, AutoModel

            proc = AutoImageProcessor.from_pretrained(hf_id)
            mdl  = AutoModel.from_pretrained(hf_id)
            mdl  = mdl.to(self.device)
            mdl.eval()

            self.processor = proc
            self.model = mdl
            self.current_model_name = model_name
            # New backbone → existing refs are stale
            self._ref_embeds = None
            self._ref_labels = None

            send_notification(f'DINOv2: {model_name} ready ✓', progress=1.0, notif_id=_NOTIF_ID)
        except Exception as e:
            self._failed.add(model_name)
            print(f'[DINOv2] Load FAILED: {e}')
            send_notification(f'DINOv2 error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
        finally:
            self._loading = False

    # ── Embedding ──────────────────────────────────────────────────────────
    def _embed_batch(self, pil_list: list, torch) -> np.ndarray:
        """Embed a list of PIL images → (N, D) L2-normalized CLS embeddings."""
        if not pil_list:
            return np.zeros((0, 1), dtype=np.float32)
        inp = self.processor(images=pil_list, return_tensors='pt')
        inp = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in inp.items()}
        with torch.no_grad():
            out = self.model(**inp)
        # DINOv2: pooler_output == CLS token; fall back to last_hidden_state[:,0]
        feats = getattr(out, 'pooler_output', None)
        if feats is None:
            feats = out.last_hidden_state[:, 0]
        feats = feats.float().cpu().numpy()
        norms = np.linalg.norm(feats, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (feats / norms).astype(np.float32)

    def _build_refs_thread(self, ref_dir: str, model_name: str, torch) -> None:
        try:
            from PIL import Image as PILImage
            classes = sorted(
                d for d in os.listdir(ref_dir)
                if os.path.isdir(os.path.join(ref_dir, d))
            )
            if not classes:
                send_notification('DINOv2: no class subfolders in ref dir', level='error', notif_id=_NOTIF_ID)
                return

            embeds_all = []
            labels_all = []
            for ci, cls in enumerate(classes):
                cls_path = os.path.join(ref_dir, cls)
                files = [f for f in os.listdir(cls_path) if f.lower().endswith(_IMG_EXTS)]
                pil_batch = []
                for f in files:
                    try:
                        pil_batch.append(PILImage.open(os.path.join(cls_path, f)).convert('RGB'))
                    except Exception as e:
                        print(f'[DINOv2] skip {f}: {e}')
                if not pil_batch:
                    continue
                send_notification(
                    f'DINOv2: embedding "{cls}" ({len(pil_batch)} imgs)…',
                    progress=0.1 + 0.85 * ci / len(classes), notif_id=_NOTIF_ID,
                )
                emb = self._embed_batch(pil_batch, torch)
                embeds_all.append(emb)
                labels_all.extend([cls] * len(pil_batch))

            if not embeds_all:
                send_notification('DINOv2: no reference images found', level='error', notif_id=_NOTIF_ID)
                return

            self._ref_embeds = np.vstack(embeds_all)
            self._ref_labels = labels_all
            self._ref_dir    = ref_dir
            self._ref_model  = model_name
            n_cls = len(set(labels_all))
            send_notification(
                f'DINOv2: refs ready ✓ {len(labels_all)} imgs / {n_cls} classes',
                progress=1.0, notif_id=_NOTIF_ID,
            )
        except Exception as e:
            print(f'[DINOv2] Build refs FAILED: {e}')
            send_notification(f'DINOv2 refs error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
        finally:
            self._building = False

    # ── k-NN ───────────────────────────────────────────────────────────────
    def _knn(self, query: np.ndarray, k: int, metric: int) -> tuple:
        """Weighted k-NN. query: (D,) L2-normed. Returns (label, score in [0,1])."""
        refs = self._ref_embeds
        if metric == 0:  # cosine (vectors are L2-normed → dot product)
            sims = refs @ query                          # higher = closer, in [-1,1]
        else:            # euclidean → convert distance to similarity
            d = np.linalg.norm(refs - query, axis=1)
            sims = 1.0 / (1.0 + d)
        kk = min(k, len(sims))
        idx = np.argpartition(-sims, kk - 1)[:kk]
        # Weighted vote: sum similarity per class
        votes = {}
        total = 0.0
        for i in idx:
            w = max(0.0, float(sims[i]))
            lbl = self._ref_labels[i]
            votes[lbl] = votes.get(lbl, 0.0) + w
            total += w
        if not votes or total <= 0:
            return 'unknown', 0.0
        best = max(votes, key=votes.get)
        return best, votes[best] / total

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _status_overlay(self, image: np.ndarray, text: str) -> np.ndarray:
        out = image.copy()
        cv2.rectangle(out, (0, 0), (out.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(out, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 200, 50), 1, cv2.LINE_AA)
        return out

    def _empty(self, image, msg: str = None) -> dict:
        main = self._status_overlay(image, msg) if (msg and image is not None) else image
        return {'main': main, 'labels_list': [], 'classes': {}, 'summary': {}, 'count': 0.0}

    def _save_classification(self, path: str, result: dict, h: int, w: int) -> tuple:
        """Serialize a classification result to .cls.json. Returns (ok, message)."""
        import json
        path = os.path.expanduser((path or '').strip())
        if not path:
            return False, 'No save path set'
        # Strip the overlay image; keep machine-usable data only.
        doc = {
            'version': 1,
            'source': 'dinov2_classifier',
            'image_size': {'w': int(w), 'h': int(h)},
            'count': int(result.get('count', 0) or 0),
            'labels_list': result.get('labels_list', []),
            'classes': result.get('classes', {}),
            'summary': result.get('summary', {}),
        }
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(doc, f, ensure_ascii=False)
            return True, f'Saved {doc["count"]} labels → {os.path.basename(path)}'
        except Exception as e:
            return False, f'Save failed: {str(e)[:100]}'

    def _crop(self, image: np.ndarray, box: dict, pad: float):
        """box has normalized xmin/ymin/width/height. Returns BGR crop or None."""
        h, w = image.shape[:2]
        x1 = box.get('xmin', 0.0) * w
        y1 = box.get('ymin', 0.0) * h
        bw = box.get('width', 0.0) * w
        bh = box.get('height', 0.0) * h
        px = bw * pad
        py = bh * pad
        x1i = int(max(0, x1 - px))
        y1i = int(max(0, y1 - py))
        x2i = int(min(w, x1 + bw + px))
        y2i = int(min(h, y1 + bh + py))
        if x2i <= x1i or y2i <= y1i:
            return None, (x1i, y1i, x2i, y2i)
        return image[y1i:y2i, x1i:x2i], (x1i, y1i, x2i, y2i)

    # ── Main ─────────────────────────────────────────────────────────────────
    def process(self, inputs: dict, params: dict) -> dict:
        import torch

        image = inputs.get('image')
        if image is None:
            return self._empty(None)

        # HF token — persist to ~/.vnstudio/secrets.json (same scheme as GDINO)
        import json
        hf_token     = params.get('hf_token', '')
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
        elif os.path.exists(secrets_path):
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
                return self._empty(image, f'DINOv2 load failed: {model_name}')
            if not self._loading:
                self._loading = True
                self.model = None
                threading.Thread(target=self._load_model_thread, args=(model_name,), daemon=True).start()
            return self._empty(image, f'Loading {model_name}…')

        if self.model is None:
            return self._empty(image, f'Loading {model_name}…')

        # Normalize image to uint8 BGR
        if image.dtype != np.uint8:
            if image.dtype in (np.float32, np.float64):
                scale = 255.0 if image.max() <= 1.0 else 1.0
                image = np.clip(image * scale, 0, 255).astype(np.uint8)
            else:
                image = np.clip(image, 0, 255).astype(np.uint8)

        # Build references (trigger)
        ref_dir = (params.get('ref_dir', '') or '').strip()
        if bool(params.get('build_refs', False)):
            if not ref_dir or not os.path.isdir(ref_dir):
                return self._empty(image, 'Set a valid Reference Folder')
            if not self._building:
                self._building = True
                threading.Thread(
                    target=self._build_refs_thread, args=(ref_dir, model_name, torch), daemon=True,
                ).start()
            return self._empty(image, 'Building references…')

        if self._building:
            return self._empty(image, 'Building references…')

        if self._ref_embeds is None or self._ref_model != model_name:
            return self._empty(image, 'Press "Build Refs" first')

        # ── Save gate (independent of Classify) ──
        if bool(params.get('save_classif', False)):
            hh, ww = image.shape[:2]
            if self._cache_result is not None:
                ok, msg = self._save_classification(params.get('save_path', ''),
                                                    self._cache_result, hh, ww)
                send_notification(msg, level='info' if ok else 'error', notif_id=_NOTIF_ID)
            else:
                send_notification('DINOv2: run Classify before saving',
                                  level='error', notif_id=_NOTIF_ID)
            return self._cache_result if self._cache_result is not None else self._empty(image, 'Press Classify to run')

        # ── Classify gate: heavy model only runs on explicit trigger ──
        if not bool(params.get('classify', False)):
            if self._cache_result is not None:
                return self._cache_result
            return self._empty(image, 'Press Classify to run')

        # Read params
        k          = int(params.get('k', 5))
        metric     = int(params.get('metric', 0))
        min_score  = float(params.get('min_score', 0.0))
        crop_pad   = float(params.get('crop_pad', 0.0)) / 100.0
        whole      = bool(params.get('whole_frame', False))
        label_mode = int(params.get('label_mode', 0))

        h, w = image.shape[:2]
        from PIL import Image as PILImage

        # Collect crops to classify (batch)
        crops_pil = []
        rects     = []
        src_boxes = []
        if whole:
            crops_pil.append(PILImage.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
            rects.append((0, 0, w, h))
            src_boxes.append(None)
        else:
            boxes = inputs.get('boxes_list') or []
            if not isinstance(boxes, list) or not boxes:
                return self._empty(image, 'No boxes — connect Grounding DINO boxes_list')
            for box in boxes:
                if not isinstance(box, dict):
                    continue
                crop, rect = self._crop(image, box, crop_pad)
                if crop is None or crop.size == 0:
                    continue
                crops_pil.append(PILImage.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
                rects.append(rect)
                src_boxes.append(box)

        if not crops_pil:
            return self._empty(image, 'No valid crops')

        # Embed all crops in one forward pass, then k-NN each
        try:
            self.report_progress(0.4, f'DINOv2: classifying {len(crops_pil)} crop(s)…')
            embeds = self._embed_batch(crops_pil, torch)
        except Exception as e:
            print(f'[DINOv2] Inference error: {e}')
            send_notification(f'DINOv2 error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
            return self._empty(image, f'DINOv2 error: {str(e)[:60]}')

        labels_list = []
        overlay = image.copy()
        for i, (q, rect, src) in enumerate(zip(embeds, rects, src_boxes)):
            label, score = self._knn(q, k, metric)
            if score < min_score:
                label = 'unknown'
            # Use the source box id so ids stay aligned with SAM contour order
            # (SAM indexes contours by position in the same boxes_list).
            stone_id = int(src['id']) if (isinstance(src, dict) and 'id' in src) else i
            labels_list.append({
                'id':    stone_id,
                'label': label,
                'score': float(score),
                'box':   src,
            })

            x1, y1, x2, y2 = rect
            color = (
                int((i * 67  + 40) % 200 + 55),
                int((i * 137 + 80) % 200 + 55),
                int((i * 197 + 120) % 200 + 55),
            )
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            txt = None
            if label_mode == 0:
                txt = f'{label} {score:.2f}'
            elif label_mode == 1:
                txt = label
            if txt:
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                bx, by = x1 + 2, y1 - 4 if y1 > 14 else y1 + th + 4
                cv2.rectangle(overlay, (bx - 2, by - th - 4), (bx + tw + 2, by + 2), color, -1)
                cv2.putText(overlay, txt, (bx, by),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        n = len(labels_list)

        # Aggregate per-class summary (for calepinage / reports / CSV)
        counts = {}
        score_sums = {}
        for item in labels_list:
            lbl = item['label']
            counts[lbl] = counts.get(lbl, 0) + 1
            score_sums[lbl] = score_sums.get(lbl, 0.0) + item['score']
        classes = [
            {
                'label':     lbl,
                'count':     counts[lbl],
                'fraction':  counts[lbl] / n if n else 0.0,
                'avg_score': score_sums[lbl] / counts[lbl] if counts[lbl] else 0.0,
            }
            for lbl in sorted(counts, key=lambda x: -counts[x])
        ]
        dominant = classes[0]['label'] if classes else None
        summary = {
            'total':       n,
            'num_classes': len([c for c in classes if c['label'] != 'unknown']),
            'dominant':    dominant,
            'counts':      counts,
            'classes':     classes,
        }

        # {type: [ids]} mapping — direct input for Stone Calepinage 'classes' port
        classes_map = {}
        for item in labels_list:
            classes_map.setdefault(item['label'], []).append(item['id'])

        self.report_progress(1.0, f'DINOv2: {n} classified')
        result = {
            'main':        overlay,
            'labels_list': labels_list,
            'classes':     classes_map,
            'summary':     summary,
            'count':       float(n),
        }
        self._cache_result = result
        return result
