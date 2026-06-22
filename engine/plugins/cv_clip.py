"""
CLIP Embeddings & Zero-Shot Classification
OpenAI CLIP (ViT backbone) via HuggingFace transformers.

Two usage modes:
  1. Zero-shot classification: image + text labels → best label + probability scores.
  2. Embedding extraction: image → normalized 512/768-d vector for similarity / retrieval.
"""
import cv2
import numpy as np
import threading
import os
import json
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'cv_clip'

_MODELS = {
    'ViT-B/32 (fast, 512d)':     'openai/clip-vit-base-patch32',
    'ViT-L/14 (accurate, 768d)': 'openai/clip-vit-large-patch14',
}
_MODEL_NAMES = list(_MODELS.keys())


@vision_node(
    type_id='cv_clip',
    label='CLIP Embeddings',
    category='ml',
    icon='Search',
    description=(
        "OpenAI CLIP (ViT): encode images and text in a shared embedding space. "
        "Zero-shot classification: text labels port or comma-separated param → best label + score. "
        "Embedding output: use for semantic similarity, retrieval, or clustering with other nodes."
    ),
    inputs=[
        {'id': 'image',       'color': 'image', 'label': 'Image'},
        {'id': 'labels_list', 'color': 'list',  'label': 'Text labels (list)'},
    ],
    outputs=[
        {'id': 'label',     'color': 'string', 'label': 'Best label'},
        {'id': 'score',     'color': 'scalar', 'label': 'Confidence'},
        {'id': 'scores',    'color': 'list',   'label': 'All scores [{label, score}]'},
        {'id': 'embedding', 'color': 'any',    'label': 'Image embedding (vector)'},
        {'id': 'overlay',   'color': 'image',  'label': 'Image + top-K overlay'},
    ],
    params=[
        {'id': '_sec_model', 'label': 'Model Config', 'type': 'section'},
        {'id': 'hf_token',    'label': 'HuggingFace Token', 'type': 'string', 'default': ''},
        {'id': 'model',       'label': 'Model', 'type': 'enum',
         'options': _MODEL_NAMES, 'default': 0},
        {'id': 'download',    'label': 'Download Model', 'type': 'trigger', 'default': False},
        {'id': '_sec_inference', 'label': 'Inference', 'type': 'section'},
        {'id': 'text_labels', 'label': 'Labels (comma-separated)', 'type': 'string',
         'default': 'cat, dog, bird, car, building, water, forest, road'},
        {'id': 'normalize',   'label': 'Normalize embedding', 'type': 'bool', 'default': True},
        {'id': 'top_k',       'label': 'Top-K in overlay',   'type': 'int',
         'min': 1, 'max': 10, 'default': 3},
        {'id': 'temperature', 'label': 'Softmax temperature','type': 'float',
         'min': 1.0, 'max': 200.0, 'step': 5.0, 'default': 100.0},
    ],
    colorable=True,
)
class CLIPEmbeddingsNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.processor      = None
        self.model          = None
        self.current_model  = ''
        self._loading       = False
        self._failed: set   = set()
        self.device = 'cpu'
        try:
            import torch
            if torch.backends.mps.is_available():
                self.device = 'mps'
            elif torch.cuda.is_available():
                self.device = 'cuda'
        except ImportError:
            pass

    # ── Model loading ────────────────────────────────────────────────────────
    def _load_thread(self, model_name: str) -> None:
        try:
            hf_id = _MODELS[model_name]
            send_notification(f'CLIP: downloading {model_name}…', progress=0.1, notif_id=_NOTIF)

            if not self.ensure_packages(['transformers'], notif_id=_NOTIF):
                self._failed.add(model_name)
                return

            from transformers import CLIPProcessor, CLIPModel

            proc = CLIPProcessor.from_pretrained(hf_id)
            mdl  = CLIPModel.from_pretrained(hf_id).to(self.device)
            mdl.eval()

            self.processor     = proc
            self.model         = mdl
            self.current_model = model_name
            send_notification(f'CLIP: {model_name} ready ✓', progress=1.0, notif_id=_NOTIF)
        except Exception as e:
            self._failed.add(model_name)
            send_notification(f'CLIP error: {str(e)[:120]}', level='error', notif_id=_NOTIF)
        finally:
            self._loading = False

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _hf_token(self, params: dict) -> None:
        """Persist + inject HF token (same pattern as DINOv2)."""
        token        = params.get('hf_token', '')
        secrets_path = os.path.expanduser('~/.vnstudio/secrets.json')
        if token:
            os.makedirs(os.path.dirname(secrets_path), exist_ok=True)
            secrets = {}
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path) as f:
                        secrets = json.load(f)
                except Exception:
                    pass
            secrets['hf_token'] = token
            try:
                with open(secrets_path, 'w') as f:
                    json.dump(secrets, f)
            except Exception:
                pass
        elif os.path.exists(secrets_path):
            try:
                with open(secrets_path) as f:
                    token = json.load(f).get('hf_token', '')
            except Exception:
                pass
        if token:
            os.environ['HF_TOKEN'] = token

    @staticmethod
    def _as_feature_tensor(out):
        """get_image_features / get_text_features should return a tensor, but some
        transformers versions return a model-output object. Extract the tensor."""
        if hasattr(out, 'float') and hasattr(out, 'cpu'):
            return out  # already a tensor
        for attr in ('image_embeds', 'text_embeds', 'pooler_output', 'last_hidden_state'):
            v = getattr(out, attr, None)
            if v is not None:
                return v
        raise TypeError(f'Unexpected CLIP feature type: {type(out).__name__}')

    def _status_overlay(self, image: np.ndarray, msg: str) -> np.ndarray:
        out = image.copy()
        cv2.rectangle(out, (0, 0), (out.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(out, msg, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (200, 200, 50), 1, cv2.LINE_AA)
        return out

    def _empty(self, image, msg: str = '') -> dict:
        overlay = self._status_overlay(image, msg) if (image is not None and msg) else image
        return {'label': '', 'score': 0.0, 'scores': [], 'embedding': None, 'overlay': overlay}

    # ── Main ─────────────────────────────────────────────────────────────────
    def process(self, inputs: dict, params: dict) -> dict:
        import torch

        image = inputs.get('image')
        if image is None:
            return self._empty(None)

        self._hf_token(params)

        # Model loading
        model_idx  = int(params.get('model', 0))
        model_name = _MODEL_NAMES[min(model_idx, len(_MODEL_NAMES) - 1)]

        if model_name != self.current_model:
            download = bool(params.get('download', False))
            if self._loading:
                return self._empty(image, f'Loading {model_name}…')
            if model_name in self._failed and not download:
                return self._empty(image, f'CLIP load failed: {model_name} — press Download to retry')
            if download:
                self._loading = True
                self.model = None
                self._failed.discard(model_name)
                threading.Thread(target=self._load_thread, args=(model_name,), daemon=True).start()
                return self._empty(image, f'Downloading {model_name}…')
            return self._empty(image, 'Press "Download Model" to load')

        if self.model is None:
            return self._empty(image, 'Press "Download Model" to load')

        # Normalize to uint8 BGR
        if image.dtype != np.uint8:
            scale = 255.0 if image.max() <= 1.0 else 1.0
            image = np.clip(image * scale, 0, 255).astype(np.uint8)

        # Resolve text labels: port takes priority over param
        labels_port = inputs.get('labels_list')
        if isinstance(labels_port, list) and labels_port:
            text_labels = [str(l) for l in labels_port if l]
        else:
            raw = params.get('text_labels', 'cat, dog, bird')
            text_labels = [l.strip() for l in raw.split(',') if l.strip()]

        if not text_labels:
            return self._empty(image, 'CLIP: no text labels — check param or port')

        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        try:
            self.report_progress(0.3, 'CLIP: encoding…')

            # Image features
            img_in = self.processor(images=pil_img, return_tensors='pt')
            img_in = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in img_in.items()}
            with torch.no_grad():
                img_feats = self._as_feature_tensor(self.model.get_image_features(**img_in))

            feat_np = img_feats.float().cpu().numpy()[0]
            norm    = np.linalg.norm(feat_np)
            embedding = (feat_np / norm if norm > 0 else feat_np).astype(np.float32)

            if not bool(params.get('normalize', True)):
                embedding = feat_np.astype(np.float32)

            # Text features
            txt_in = self.processor(
                text=text_labels, return_tensors='pt', padding=True, truncation=True,
            )
            txt_in = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in txt_in.items()}
            with torch.no_grad():
                txt_feats = self._as_feature_tensor(self.model.get_text_features(**txt_in))

            txt_np = txt_feats.float().cpu().numpy()
            txt_norms = np.linalg.norm(txt_np, axis=1, keepdims=True)
            txt_norms[txt_norms == 0] = 1.0
            txt_normed = txt_np / txt_norms

            # Cosine similarity → softmax probabilities
            temp  = float(params.get('temperature', 100.0))
            sims  = txt_normed @ embedding        # (n_labels,)
            exp_s = np.exp(sims * temp)
            probs = exp_s / exp_s.sum()

            # Sort descending
            order  = np.argsort(-probs)
            scores = [{'label': text_labels[i], 'score': float(probs[i])} for i in order]

            best_label = scores[0]['label'] if scores else ''
            best_score = float(scores[0]['score']) if scores else 0.0
            top_k      = int(params.get('top_k', 3))

            # Build overlay
            overlay = image.copy()
            cv2.rectangle(overlay, (0, 0), (overlay.shape[1], 30), (18, 18, 18), -1)
            cv2.putText(overlay, f'{best_label}  {best_score:.1%}',
                        (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 220, 80), 1, cv2.LINE_AA)
            bar_max = max(overlay.shape[1] - 170, 60)
            for i, s in enumerate(scores[:top_k]):
                y = 36 + i * 20
                bar_w = int(s['score'] * bar_max)
                cv2.rectangle(overlay, (155, y + 1), (155 + bar_w, y + 15), (50, 110, 230), -1)
                cv2.putText(overlay, f"{s['label'][:18]:18} {s['score']:.1%}",
                            (4, y + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (190, 190, 190), 1, cv2.LINE_AA)

            self.report_progress(1.0, 'CLIP: done')
            return {
                'label':     best_label,
                'score':     best_score,
                'scores':    scores,
                'embedding': embedding,
                'overlay':   overlay,
            }

        except Exception as e:
            print(f'[CLIP] Error: {e}')
            send_notification(f'CLIP error: {str(e)[:120]}', level='error', notif_id=_NOTIF)
            return self._empty(image, f'CLIP error: {str(e)[:60]}')
