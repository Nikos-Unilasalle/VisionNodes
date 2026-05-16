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
    for lbl in range(1, int(labels_map.max()) + 1):
        c = _PALETTE[(lbl - 1) % len(_PALETTE)]
        out[labels_map == lbl] = c
    return out


def _get_dims(mask, image):
    for ref in (mask, image):
        if ref is not None:
            return ref.shape[:2]
    return 512, 512


def _stats_from_region(label_id: int, pixel_mask: np.ndarray) -> dict:
    """Compute stats for a single binary region."""
    area = int(np.count_nonzero(pixel_mask))
    ys, xs = np.nonzero(pixel_mask)
    cx = int(xs.mean()) if len(xs) else 0
    cy = int(ys.mean()) if len(ys) else 0
    diameter = float(2.0 * np.sqrt(area / np.pi)) if area > 0 else 0.0
    return {'id': label_id, 'area': area, 'cx': cx, 'cy': cy, 'diameter': round(diameter, 2)}


@vision_node(
    type_id='obj_extractor',
    label='Object Extractor',
    category='segmentation',
    icon='Package',
    description=(
        'Unified object extractor — normalises any segmentation output into '
        'a labeled map, count, and per-object statistics.\n\n'
        'When both Mask and Objects are connected, they are merged: '
        'objects (circles, polygons) are drawn first, then mask regions '
        'not already covered by an object are added — no double-counting.\n\n'
        'Object list format: Hough circles, polygon lists, YOLO detections.\n'
        'Stats output includes: id, area (px²), cx, cy, diameter (px).'
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
        objects  = inputs.get('objects')
        mask     = inputs.get('mask')
        image    = inputs.get('image')
        min_area = int(params.get('min_area', 0))

        h, w = _get_dims(mask, image)
        labels_map = np.zeros((h, w), dtype=np.int32)
        stats_list = []
        label_id = 0

        has_objects = isinstance(objects, list) and len(objects) > 0

        # ── 1. Draw objects (circles / polygons) ─────────────────────────
        if has_objects:
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                shape    = obj.get('shape', '')
                relative = obj.get('relative', False)
                pts_raw  = obj.get('pts', [])

                if shape == 'circle':
                    if not pts_raw:
                        continue
                    p  = pts_raw[0]
                    cx = int(p[0] * w) if relative else int(p[0])
                    cy = int(p[1] * h) if relative else int(p[1])
                    r  = int(obj.get('radius', 0))
                    if r <= 0:
                        continue
                    area = float(np.pi * r * r)
                    if area < min_area:
                        continue
                    label_id += 1
                    cv2.circle(labels_map, (cx, cy), r, label_id, -1)
                    stats_list.append({
                        'id': label_id, 'area': round(area, 1),
                        'cx': cx, 'cy': cy,
                        'diameter': round(2.0 * r, 2),
                    })

                elif len(pts_raw) >= 3:
                    if relative:
                        poly = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts_raw], np.int32)
                    else:
                        poly = np.array([[int(p[0]), int(p[1])] for p in pts_raw], np.int32)
                    area = float(cv2.contourArea(poly))
                    if area < min_area:
                        continue
                    label_id += 1
                    cv2.fillPoly(labels_map, [poly], label_id)
                    M  = cv2.moments(poly)
                    cx = int(M['m10'] / M['m00']) if M['m00'] > 0 else 0
                    cy = int(M['m01'] / M['m00']) if M['m00'] > 0 else 0
                    stats_list.append({
                        'id': label_id, 'area': round(area, 1),
                        'cx': cx, 'cy': cy,
                        'diameter': round(2.0 * np.sqrt(area / np.pi), 2),
                    })

        # ── 2. Add mask regions not already covered ───────────────────────
        if mask is not None:
            gray   = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask
            binary = (gray > 0).astype(np.uint8)
            if binary.shape[:2] != (h, w):
                binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)

            n_cc, cc_map, cv_stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
            for i in range(1, n_cc):
                area = int(cv_stats[i, cv2.CC_STAT_AREA])
                if area < max(min_area, 1):
                    continue
                region_pixels = (cc_map == i)
                # Skip if >50% of this region is already covered by an object
                if has_objects and np.count_nonzero(labels_map[region_pixels]) > area * 0.5:
                    continue
                label_id += 1
                labels_map[region_pixels] = label_id
                s = _stats_from_region(label_id, region_pixels)
                stats_list.append(s)

        count = len(stats_list)

        # ── 3. Aggregate size stats ────────────────────────────────────────
        areas     = [s['area']     for s in stats_list]
        diameters = [s['diameter'] for s in stats_list]
        mean_area  = float(np.mean(areas))     if areas else 0.0
        mean_diam  = float(np.mean(diameters)) if diameters else 0.0
        std_diam   = float(np.std(diameters))  if len(diameters) > 1 else 0.0
        cv_diam    = float(std_diam / mean_diam * 100) if mean_diam > 0 else 0.0  # anisocytosis %

        # ── 4. Preview ────────────────────────────────────────────────────
        preview = _colorize_labels(labels_map)
        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                ph  = min(360, preview.shape[0])
                pw  = int(ph * preview.shape[1] / preview.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview, (pw, ph)),
                                     [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'count':         int(count),
            'labels':        labels_map,
            'main':          preview,
            'main_preview':  self._last_preview,
            'stats': {
                'count':     int(count),
                'objects':   stats_list,
                'mean_area': round(mean_area, 1),
                'mean_diam': round(mean_diam, 2),
                'cv_diam':   round(cv_diam,   1),
            },
        }
