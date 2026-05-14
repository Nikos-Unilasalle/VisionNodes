"""
FastSAM Segmenter — Real-time AI segmentation using FastSAM (YOLOv8-seg).
10-50x faster than SAM2. Same output format as sam_segmenter — drop-in for sam_grain_stats.
Models auto-download on first use via ultralytics (pip install ultralytics).
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import threading

try:
    from ultralytics import FastSAM as _FastSAM
    FASTSAM_AVAILABLE = True
except ImportError:
    FASTSAM_AVAILABLE = False

_NOTIF_ID = 'fast_sam_segmenter'
_MODEL_FILES = ['FastSAM-s.pt', 'FastSAM-x.pt']
_MODEL_NAMES = ['FastSAM-s (23 MB — rapide)', 'FastSAM-x (138 MB — précis)']
_IMGSZ_OPTIONS = [512, 640, 1024, 1280]


@vision_node(
    type_id='fast_sam_segmenter',
    label='FastSAM Segmenter',
    category='geology',
    icon='Zap',
    description=(
        "Segmentation automatique temps-réel via FastSAM (YOLOv8-seg).\n"
        "10 à 50× plus rapide que SAM2. Sortie identique à SAM Segmenter.\n\n"
        "GUIDE:\n"
        "- Connecter 'Contours' à SAM Grain Stats pour les métriques morpho.\n"
        "- FastSAM-s : idéal pour les grandes images (< 1 s).\n"
        "- Augmenter la Conf. pour réduire le bruit, baisser l'IOU pour moins de chevauchement.\n"
        "- Requiert : pip install ultralytics"
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
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
        {'id': 'model', 'label': 'Model', 'type': 'enum',
         'options': _MODEL_NAMES, 'default': 0},
        {'id': 'imgsz', 'label': 'Résolution inférence', 'type': 'enum',
         'options': ['512 px', '640 px', '1024 px', '1280 px'], 'default': 1},
        {'id': 'conf', 'label': 'Confidence', 'type': 'float',
         'default': 0.4, 'min': 0.05, 'max': 0.95, 'step': 0.05},
        {'id': 'iou', 'label': 'IOU Threshold', 'type': 'float',
         'default': 0.9, 'min': 0.1, 'max': 0.99, 'step': 0.05},
        {'id': 'overlay_opacity', 'label': 'Overlay Opacity (%)', 'type': 'number',
         'default': 50, 'min': 0, 'max': 100, 'step': 5},
    ],
    colorable=True,
)
class FastSAMSegmenterNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.model = None
        self.current_model_file = ''
        self._loading = False
        self._failed = set()
        self._cache_hash = None
        self._cache_result = None
        self.device = _detect_device()

    def _load_model_thread(self, model_file):
        try:
            send_notification(
                f'FastSAM: Chargement {model_file}…',
                progress=0.1, notif_id=_NOTIF_ID
            )
            m = _FastSAM(model_file)
            self.model = m
            self.current_model_file = model_file
            send_notification(
                f'FastSAM: {model_file} prêt ✓',
                progress=1.0, notif_id=_NOTIF_ID
            )
        except Exception as e:
            self._failed.add(model_file)
            print(f'[FastSAM] Erreur chargement: {e}')
            send_notification(
                f'FastSAM erreur: {str(e)[:120]}',
                level='error', notif_id=_NOTIF_ID
            )
        finally:
            self._loading = False

    def process(self, inputs, params):
        image = inputs.get('image')
        empty = {
            'main': image, 'mask': None, 'count': 0.0,
            'areas': [], 'centroids': [], 'contours': [],
        }

        if image is None:
            return empty

        if not FASTSAM_AVAILABLE:
            send_notification(
                'FastSAM: ultralytics non installé. Exécuter : pip install ultralytics',
                level='error', notif_id=_NOTIF_ID
            )
            return empty

        model_idx = int(params.get('model', 0))
        model_file = _MODEL_FILES[min(model_idx, len(_MODEL_FILES) - 1)]

        if model_file != self.current_model_file:
            if not self._loading and model_file not in self._failed:
                self._loading = True
                self.model = None
                threading.Thread(
                    target=self._load_model_thread,
                    args=(model_file,),
                    daemon=True,
                ).start()
            return empty

        if self.model is None:
            return empty

        imgsz = _IMGSZ_OPTIONS[int(params.get('imgsz', 1))]
        conf = float(params.get('conf', 0.4))
        iou = float(params.get('iou', 0.9))
        opacity = float(params.get('overlay_opacity', 50)) / 100.0

        # Cache check
        img_hash = hash(image[::8, ::8].tobytes())
        cache_key = (img_hash, imgsz, conf, iou, opacity)
        if cache_key == self._cache_hash and self._cache_result is not None:
            return self._cache_result

        h, w = image.shape[:2]
        self.report_progress(0.2, 'FastSAM: Inférence…')

        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.model(
                rgb,
                device=self.device,
                retina_masks=True,
                imgsz=imgsz,
                conf=conf,
                iou=iou,
                verbose=False,
            )
        except Exception as e:
            print(f'[FastSAM] Erreur inférence: {e}')
            send_notification(
                f'FastSAM erreur: {str(e)[:120]}',
                level='error', notif_id=_NOTIF_ID
            )
            return empty

        self.report_progress(0.7, 'FastSAM: Extraction masques…')

        overlay, combined_mask, areas, centroids, all_contours = _process_masks(
            image, results[0], h, w, opacity
        )

        count = float(len(areas))
        cv2.putText(
            overlay, f'FastSAM: {int(count)} segments',
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
        )

        self.report_progress(1.0, f'FastSAM: {int(count)} segments détectés')

        result = {
            'main': overlay,
            'mask': combined_mask,
            'count': count,
            'areas': areas,
            'centroids': centroids,
            'contours': all_contours,
        }
        self._cache_hash = cache_key
        self._cache_result = result
        return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _detect_device():
    try:
        import torch
        if torch.backends.mps.is_available():
            return 'mps'
        if torch.cuda.is_available():
            return 'cuda'
    except Exception:
        pass
    return 'cpu'


def _process_masks(image, result_obj, h, w, opacity):
    overlay = image.copy()
    label_map = np.zeros((h, w, 3), dtype=np.uint8)
    combined_mask = np.zeros((h, w), dtype=np.uint8)
    areas, centroids, all_contours = [], [], []

    if result_obj.masks is None:
        return overlay, combined_mask, areas, centroids, all_contours

    masks_tensor = result_obj.masks.data
    if hasattr(masks_tensor, 'cpu'):
        masks_tensor = masks_tensor.detach().cpu().numpy()

    for i, mask in enumerate(masks_tensor):
        if mask.shape != (h, w):
            mask = cv2.resize(
                mask.astype(np.float32), (w, h),
                interpolation=cv2.INTER_NEAREST,
            )
        mask_bool = mask > 0.5
        area = float(np.sum(mask_bool))
        if area < 1:
            continue

        m_uint8 = mask_bool.astype(np.uint8) * 255
        M = cv2.moments(m_uint8)
        if M['m00'] > 0:
            cx = float(M['m10'] / M['m00'])
            cy = float(M['m01'] / M['m00'])
        else:
            cx, cy = float(w / 2), float(h / 2)

        cnts, _ = cv2.findContours(m_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            pts = cnts[0].reshape(-1, 2).tolist()
            all_contours.append(pts)

        color = [
            int((i * 67 + 40) % 200 + 55),
            int((i * 137 + 80) % 200 + 55),
            int((i * 197 + 120) % 200 + 55),
        ]
        label_map[mask_bool] = color
        combined_mask[mask_bool] = 255
        areas.append(area)
        centroids.append([cx, cy])

    overlay = cv2.addWeighted(overlay, 1.0, label_map, opacity, 0)

    for cnt_pts in all_contours:
        cnt_arr = np.array(cnt_pts, dtype=np.int32).reshape(-1, 1, 2)
        cv2.drawContours(overlay, [cnt_arr], -1, (255, 255, 255), 1)

    return overlay, combined_mask, areas, centroids, all_contours
