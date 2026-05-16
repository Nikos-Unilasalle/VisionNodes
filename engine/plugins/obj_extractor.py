import base64
import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_PALETTE = [
    (220,  60,  60), ( 60, 180,  75), ( 67, 133, 255), (255, 165,   0),
    (145,  30, 180), ( 70, 240, 240), (240,  50, 230), (210, 245,  60),
    (250, 190, 212), (  0, 128, 128), (220, 190, 255), (170, 110,  40),
    (128,   0,   0), (128, 128,   0), (  0,   0, 128), (128, 128, 128),
]


def _colorize_labels(labels_map: np.ndarray) -> np.ndarray:
    h, w = labels_map.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)
    max_label = int(labels_map.max())
    for lbl in range(1, max_label + 1):
        c = _PALETTE[(lbl - 1) % len(_PALETTE)]
        out[labels_map == lbl] = c
    return out


def _get_dims(mask, image):
    """Return (h, w) from first available reference."""
    for ref in (mask, image):
        if ref is not None:
            return ref.shape[:2]
    return 512, 512


@vision_node(
    type_id='obj_extractor',
    label='Object Extractor',
    category='segmentation',
    icon='Package',
    description=(
        'Unified object extractor — normalises any segmentation output into '
        'a labeled map, count, and per-object statistics.\n\n'
        'Input priority:\n'
        '  1. Objects list (circles, polygons, detections from Hough, SAM, YOLO…)\n'
        '  2. Binary mask (connected-components analysis)\n\n'
        'Connect Image or Mask so the node knows the frame dimensions when '
        'computing from relative-coordinate objects.'
    ),
    resizable=True,
    min_width=220,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'objects', 'label': 'Objects List', 'color': 'list'},
        {'id': 'mask',    'label': 'Mask',         'color': 'mask'},
        {'id': 'image',   'label': 'Image (dims)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'count',  'label': 'Count',      'color': 'scalar'},
        {'id': 'labels', 'label': 'Labels Map',  'color': 'markers'},
        {'id': 'main',   'label': 'Preview',     'color': 'image'},
        {'id': 'stats',  'label': 'Stats',       'color': 'dict'},
    ],
    params=[
        {'id': 'min_area', 'label': 'Min Area (px²)', 'type': 'int', 'default': 0, 'min': 0, 'max': 100000},
    ],
)
class ObjExtractorNode(NodeProcessor):
    def __init__(self):
        self._last_preview: str | None = None
        self._frame_count = 0

    def process(self, inputs, params):
        objects = inputs.get('objects')
        mask    = inputs.get('mask')
        image   = inputs.get('image')
        min_area = int(params.get('min_area', 0))

        h, w = _get_dims(mask, image)
        labels_map = np.zeros((h, w), dtype=np.int32)
        stats_list = []

        use_objects = isinstance(objects, list) and len(objects) > 0

        if use_objects:
            label_id = 0
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                shape = obj.get('shape', '')
                relative = obj.get('relative', False)
                pts_raw = obj.get('pts', [])

                if shape == 'circle':
                    if not pts_raw:
                        continue
                    p = pts_raw[0]
                    cx = int(p[0] * w) if relative else int(p[0])
                    cy = int(p[1] * h) if relative else int(p[1])
                    r  = int(obj.get('radius', 0))
                    area = float(np.pi * r * r)
                    if area < min_area:
                        continue
                    label_id += 1
                    cv2.circle(labels_map, (cx, cy), r, label_id, -1)
                    stats_list.append({
                        'id': label_id, 'area': round(area, 1),
                        'cx': cx, 'cy': cy, 'radius': r,
                    })

                elif len(pts_raw) >= 3:
                    if relative:
                        poly = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts_raw], dtype=np.int32)
                    else:
                        poly = np.array([[int(p[0]), int(p[1])] for p in pts_raw], dtype=np.int32)
                    area = float(cv2.contourArea(poly))
                    if area < min_area:
                        continue
                    label_id += 1
                    cv2.fillPoly(labels_map, [poly], label_id)
                    M = cv2.moments(poly)
                    cx = int(M['m10'] / M['m00']) if M['m00'] > 0 else 0
                    cy = int(M['m01'] / M['m00']) if M['m00'] > 0 else 0
                    stats_list.append({
                        'id': label_id, 'area': round(area, 1),
                        'cx': cx, 'cy': cy,
                    })

        elif mask is not None:
            gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask.copy()
            binary = (gray > 0).astype(np.uint8)
            n_labels, labels_map, cv_stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
            for i in range(1, n_labels):
                area = int(cv_stats[i, cv2.CC_STAT_AREA])
                if area < min_area:
                    continue
                stats_list.append({
                    'id': i,
                    'area': area,
                    'cx': int(centroids[i, 0]),
                    'cy': int(centroids[i, 1]),
                    'w':  int(cv_stats[i, cv2.CC_STAT_WIDTH]),
                    'h':  int(cv_stats[i, cv2.CC_STAT_HEIGHT]),
                })
            # Re-label removing filtered regions
            if min_area > 0:
                kept_ids = {s['id'] for s in stats_list}
                clean = np.zeros_like(labels_map)
                for new_id, old_id in enumerate(sorted(kept_ids), start=1):
                    clean[labels_map == old_id] = new_id
                    for s in stats_list:
                        if s['id'] == old_id:
                            s['id'] = new_id
                labels_map = clean

        count = len(stats_list)
        preview = _colorize_labels(labels_map)

        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                ph = min(360, preview.shape[0])
                pw = int(ph * preview.shape[1] / preview.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview, (pw, ph)),
                                     [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'count':  int(count),
            'labels': labels_map,
            'main':   preview,
            'main_preview': self._last_preview,
            'stats':  {'objects': stats_list, 'count': int(count)},
        }
