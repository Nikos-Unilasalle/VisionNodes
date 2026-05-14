"""
FastSAM Petro Segmenter — Port of GrainSight (fazzam/GrainSight on HuggingFace) into VNStudio.
Individual grain segmentation with colored overlay, contours, and per-grain measurements.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import threading
import os
import urllib.request

try:
    from ultralytics import FastSAM as _FastSAM
    FASTSAM_AVAILABLE = True
except ImportError:
    FASTSAM_AVAILABLE = False

_NOTIF_ID = 'fast_sam_segmenter'
_MODEL_URL = "https://huggingface.co/spaces/fazzam/GrainSight/resolve/main/src/model/FastSAM-x.pt"
_IMGSZ_OPTIONS = [512, 640, 1024, 1280]


@vision_node(
    type_id='fast_sam_segmenter',
    label='FastSAM Segmenter (Petro)',
    category='geology',
    icon='Zap',
    description=(
        "Grain segmentation via FastSAM fine-tuned for petrography (GrainSight pipeline).\n"
        "Outputs a colored overlay, mask image, contour list (→ SAM Grain Stats), and per-grain measurements.\n\n"
        "GUIDE:\n"
        "- scale: connect Calibration → Scale output for µm/px\n"
        "- better_quality: morphological cleanup (slower but cleaner contours)\n"
        "- grain_data: list of dicts {id, area, perimeter, roundness, aspect_ratio, feret_diameter}\n"
        "- Requires: pip install ultralytics"
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'scale', 'color': 'scalar', 'label': 'Scale (unit/px)'},
    ],
    outputs=[
        {'id': 'main',       'color': 'image', 'label': 'Overlay'},
        {'id': 'masks_img',  'color': 'image', 'label': 'Masks'},
        {'id': 'contours',   'color': 'list',  'label': 'Contours (→ SAM Grain Stats)'},
        {'id': 'grain_data', 'color': 'any',   'label': 'Grain Data'},
    ],
    params=[
        {'id': 'imgsz',            'label': 'Inference Size',    'type': 'enum',
         'options': ['512 px', '640 px', '1024 px', '1280 px'],  'default': 2},
        {'id': 'conf',             'label': 'Confidence',        'type': 'float',
         'default': 0.25, 'min': 0.05, 'max': 0.95, 'step': 0.05},
        {'id': 'iou',              'label': 'IOU Threshold',     'type': 'float',
         'default': 0.7,  'min': 0.1,  'max': 0.95, 'step': 0.05},
        {'id': 'max_det',          'label': 'Max Grains',        'type': 'int',
         'default': 500, 'min': 50, 'max': 5000, 'step': 50},
        {'id': 'scale_factor',     'label': 'Scale (unit/px)',   'type': 'float',
         'default': 1.0, 'min': 0.0001, 'max': 1000.0, 'step': 0.001},
        {'id': 'contour_thickness','label': 'Contour Thickness', 'type': 'int',
         'default': 1, 'min': 1, 'max': 5},
        {'id': 'better_quality',   'label': 'Better Quality',    'type': 'toggle',
         'default': False},
        {'id': 'show_ids',         'label': 'Show Grain IDs',    'type': 'toggle',
         'default': True},
        {'id': 'id_font_scale',    'label': 'ID Font Size',       'type': 'float',
         'default': 0.5, 'min': 0.2, 'max': 2.0, 'step': 0.1},
    ],
    colorable=True,
)
class FastSAMSegmenterNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.model = None
        self._loading = False
        self._failed = False
        self._cache_hash = None
        self._cache_result = None
        self.device = _detect_device()
        self.model_path = os.path.expanduser("~/.vnstudio/models/FastSAM_Petro.pt")

    def _load_model_thread(self):
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            if not os.path.exists(self.model_path):
                send_notification(
                    'FastSAM: Downloading Petro model (138MB)…',
                    progress=0.1, notif_id=_NOTIF_ID,
                )
                urllib.request.urlretrieve(_MODEL_URL, self.model_path)
            send_notification('FastSAM: Loading into memory…', progress=0.5, notif_id=_NOTIF_ID)
            self.model = _FastSAM(self.model_path)
            send_notification('FastSAM: Ready ✓', progress=1.0, notif_id=_NOTIF_ID)
        except Exception as e:
            self._failed = True
            print(f'[FastSAM] Load error: {e}')
            send_notification(f'FastSAM error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
        finally:
            self._loading = False

    def process(self, inputs, params):
        image = inputs.get('image')
        empty = {'main': image, 'masks_img': None, 'contours': [], 'grain_data': None}

        if image is None:
            return empty

        if not FASTSAM_AVAILABLE:
            send_notification(
                'FastSAM: ultralytics not installed. Run: pip install ultralytics',
                level='error', notif_id=_NOTIF_ID,
            )
            return empty

        if self.model is None:
            if not self._loading and not self._failed:
                self._loading = True
                threading.Thread(target=self._load_model_thread, daemon=True).start()
            return empty

        imgsz_idx      = int(params.get('imgsz', 2))
        imgsz          = _IMGSZ_OPTIONS[imgsz_idx]
        conf           = float(params.get('conf', 0.25))
        iou            = float(params.get('iou', 0.7))
        max_det        = int(params.get('max_det', 500))
        scale_input    = inputs.get('scale')
        scale_factor   = float(scale_input) if scale_input is not None else float(params.get('scale_factor', 1.0))
        contour_thick  = int(params.get('contour_thickness', 1))
        better_quality = bool(params.get('better_quality', False))
        show_ids       = bool(params.get('show_ids', True))
        id_font_scale  = float(params.get('id_font_scale', 0.5))

        img_hash  = hash(image[::8, ::8].tobytes())
        cache_key = (img_hash, imgsz, conf, iou, max_det, scale_factor, contour_thick, better_quality, show_ids, id_font_scale)
        if cache_key == self._cache_hash and self._cache_result is not None:
            c = self._cache_result
            return {
                'main':       c['main'].copy(),
                'masks_img':  c['masks_img'].copy() if c['masks_img'] is not None else None,
                'contours':   c['contours'],
                'grain_data': c['grain_data'],
            }

        h, w = image.shape[:2]
        self.report_progress(0.2, 'FastSAM: Inference…')

        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.model(
                rgb,
                device=self.device,
                retina_masks=True,
                imgsz=imgsz,
                conf=conf,
                iou=iou,
                max_det=max_det,
                verbose=False,
            )
        except Exception as e:
            print(f'[FastSAM] Inference error: {e}')
            send_notification(f'FastSAM error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
            return empty

        self.report_progress(0.5, 'FastSAM: Processing masks…')

        if results[0].masks is None:
            return {'main': image, 'masks_img': None, 'contours': [], 'grain_data': []}

        raw = results[0].masks.data
        if hasattr(raw, 'cpu'):
            # .copy() critical: .numpy() shares PyTorch memory; next inference
            # reclaims that buffer, corrupting cached arrays.
            raw = raw.detach().cpu().numpy().copy()
        else:
            raw = np.array(raw)

        masks = []
        for m in raw:
            if m.shape != (h, w):
                m = cv2.resize(m.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
            else:
                m = m.astype(np.float32)
            masks.append(m)

        if better_quality:
            k3, k8 = np.ones((3, 3), np.uint8), np.ones((8, 8), np.uint8)
            cleaned = []
            for m in masks:
                binary = (m > 0.5).astype(np.uint8)
                binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k3)
                binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k8)
                cleaned.append(binary.astype(np.float32))
            masks = cleaned

        self.report_progress(0.65, 'FastSAM: Coloring…')
        overlay   = _build_colored_overlay(image, masks)
        masks_img = _build_colored_overlay(np.zeros_like(image), masks, alpha=1.0)
        overlay   = _draw_contours(overlay, masks, thickness=contour_thick)

        self.report_progress(0.85, 'FastSAM: Computing grain params…')
        grain_data, contour_list = _process_masks(masks, image.shape, scale_factor)

        if show_ids and grain_data:
            overlay = _draw_ids(overlay, grain_data, contour_list, id_font_scale)

        self.report_progress(1.0, f'FastSAM: {len(grain_data)} grains detected')

        self._cache_hash = cache_key
        self._cache_result = {
            'main':       overlay.copy(),
            'masks_img':  masks_img.copy(),
            'contours':   contour_list,
            'grain_data': grain_data,
        }
        return {'main': overlay, 'masks_img': masks_img, 'contours': contour_list, 'grain_data': grain_data}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_colored_overlay(image, masks, alpha=0.6):
    """Assign random color per grain, blend onto image. Largest masks drawn first."""
    h, w = image.shape[:2]
    result = image.copy().astype(np.float32)
    color_layer = np.zeros((h, w, 3), dtype=np.float32)
    alpha_layer = np.zeros((h, w), dtype=np.float32)

    areas = [np.sum(m > 0.5) for m in masks]
    for idx in np.argsort(areas)[::-1]:
        binary = masks[idx] > 0.5
        color_layer[binary] = np.random.randint(50, 256, 3).astype(np.float32)
        alpha_layer[binary] = alpha

    for c in range(3):
        result[:, :, c] = result[:, :, c] * (1 - alpha_layer) + color_layer[:, :, c] * alpha_layer
    return result.astype(np.uint8)


def _draw_contours(image, masks, thickness=1):
    """Morpho-clean each mask then draw approx contours in white."""
    result = image.copy()
    kernel = np.ones((5, 5), np.uint8)
    for mask in masks:
        binary = (mask > 0.5).astype(np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.GaussianBlur(binary, (5, 5), 0)
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            eps = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            cv2.drawContours(result, [approx], -1, (255, 255, 255), thickness)
    return result


def _process_masks(masks, image_shape, scale_factor=1.0):
    """Compute grain params + extract contours (sam_grain_stats format) in one pass."""
    grains = []
    contour_list = []

    for i, mask in enumerate(masks):
        binary = (mask > 0.5).astype(np.uint8)
        area_px = int(np.sum(binary))
        if area_px < 5:
            continue

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            continue

        cnt = max(contours, key=cv2.contourArea)
        contour_list.append(cnt.reshape(-1, 2).tolist())

        area = area_px * (scale_factor ** 2)
        perimeter = cv2.arcLength(cnt, True) * scale_factor
        roundness = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0

        aspect_ratio = 0.0
        if len(cnt) >= 5:
            ellipse = cv2.fitEllipse(cnt)
            major, minor = ellipse[1]
            aspect_ratio = float(major / minor) if minor > 0 else 0.0

        hull_pts = cv2.convexHull(cnt)[:, 0, :]
        if len(hull_pts) > 1:
            diffs = hull_pts[:, np.newaxis, :] - hull_pts[np.newaxis, :, :]
            feret = float(np.max(np.linalg.norm(diffs, axis=2))) * scale_factor
        else:
            feret = 0.0

        grains.append({
            'id':             i,
            'area':           round(area, 3),
            'perimeter':      round(perimeter, 3),
            'roundness':      round(min(max(roundness, 0.0), 1.0), 4),
            'aspect_ratio':   round(aspect_ratio, 4),
            'feret_diameter': round(feret, 3),
        })

    valid_pairs = [(g, c) for g, c in zip(grains, contour_list)
                   if g['feret_diameter'] > 0 and 0 <= g['roundness'] <= 1]
    if not valid_pairs:
        return [], []
    valid_grains, valid_contours = zip(*valid_pairs)
    return list(valid_grains), list(valid_contours)


def _draw_ids(image, grain_data, contour_list, font_scale=0.5):
    """Draw grain IDs at contour centroids (white text on black pill)."""
    result = image.copy()
    font  = cv2.FONT_HERSHEY_SIMPLEX
    thick = max(1, int(font_scale * 2))
    pad   = max(2, int(font_scale * 4))
    for grain, cnt_pts in zip(grain_data, contour_list):
        pts = np.array(cnt_pts, dtype=np.int32).reshape(-1, 1, 2)
        M = cv2.moments(pts)
        if M['m00'] > 0:
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
        else:
            r = pts.reshape(-1, 2)
            cx, cy = int(r[:, 0].mean()), int(r[:, 1].mean())
        text = str(grain['id'])
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thick)
        cv2.rectangle(result,
                      (cx - tw // 2 - pad, cy - th - pad),
                      (cx + tw // 2 + pad, cy + pad),
                      (0, 0, 0), -1)
        cv2.putText(result, text, (cx - tw // 2, cy), font,
                    font_scale, (255, 255, 255), thick, cv2.LINE_AA)
    return result


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
