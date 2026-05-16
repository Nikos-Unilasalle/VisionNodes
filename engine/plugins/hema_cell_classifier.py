import cv2
import numpy as np
from registry import vision_node, NodeProcessor


_SUBTYPE_BGR = {
    'Neutrophil': (255, 80, 30),
    'Lymphocyte': (255, 255, 60),
    'Monocyte': (40, 140, 240),
    'Eosinophil': (180, 105, 255),
    'Basophil': (220, 60, 220),
}

_BASIC_BGR = {
    'RBC': (60, 200, 80),
    'WBC': (40, 40, 220),
    'PLT': (0, 220, 240),
}


def _hex_to_bgr(h):
    try:
        s = h.lstrip('#')
        if len(s) != 6:
            return (68, 68, 239)
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (b, g, r)
    except Exception:
        return (68, 68, 239)


def _classify_region(area_px, circularity, b_mean, g_mean, r_mean,
                     plt_max, rbc_max):
    if area_px < plt_max:
        return 'PLT'
    if (area_px < rbc_max and circularity > 0.60
            and r_mean > g_mean and r_mean > b_mean):
        return 'RBC'
    return 'WBC'


def _classify_wbc_subtype(region_pixels_bgr, region_mask, purple_score_map,
                          circularity):
    total_px = int(region_mask.sum())
    if total_px <= 0:
        return 'Monocyte'

    region_scores = purple_score_map[region_mask > 0]
    if region_scores.size == 0:
        return 'Monocyte'

    nucleus_thresh = max(10.0, float(region_scores.mean()) + 5.0)
    nucleus_pixels = region_scores > nucleus_thresh
    nucleus_count = int(nucleus_pixels.sum())
    nucleus_ratio = nucleus_count / float(total_px)

    if nucleus_ratio > 0.75:
        return 'Lymphocyte'

    if circularity < 0.45:
        return 'Neutrophil'

    if nucleus_count > 0:
        nucleus_r = float(region_pixels_bgr[nucleus_pixels, 2].mean())
    else:
        nucleus_r = 0.0
    if nucleus_r > 150.0:
        return 'Eosinophil'

    mean_intensity = float(region_pixels_bgr.mean())
    if mean_intensity < 60.0:
        return 'Basophil'

    return 'Monocyte'


@vision_node(
    type_id='hema_cell_classifier',
    label='Blood Cell Classifier',
    category='hematology',
    icon='Microscope',
    description='Classifies segmented blood cells (RBC/WBC/PLT) with optional WBC differential on Giemsa/Wright-stained smears.',
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',      'label': 'Smear (BGR)', 'color': 'image'},
        {'id': 'labels_map', 'label': 'Labels',      'color': 'markers'},
        {'id': 'um_per_px',  'label': 'um/px',       'color': 'scalar'},
    ],
    outputs=[
        {'id': 'overlay',  'label': 'Overlay',  'color': 'image'},
        {'id': 'counts',   'label': 'Counts',   'color': 'dict'},
        {'id': 'wbc_diff', 'label': 'WBC Diff', 'color': 'dict'},
        {'id': 'regions',  'label': 'Regions',  'color': 'list'},
    ],
    params=[
        {'id': 'mode', 'label': 'Mode', 'type': 'enum',
         'options': ['Basic (RBC/WBC/PLT)', 'Differential (WBC subtypes)'],
         'default': 0},
        {'id': 'min_area_px',     'label': 'Min Area (px)', 'type': 'int',   'default': 30,  'min': 5,  'max': 500},
        {'id': 'rbc_max_area_px', 'label': 'RBC Max Area',  'type': 'int',   'default': 400, 'min': 50, 'max': 2000},
        {'id': 'plt_max_area_px', 'label': 'PLT Max Area',  'type': 'int',   'default': 60,  'min': 5,  'max': 200},
        {'id': 'show_labels',     'label': 'Show Labels',   'type': 'bool',  'default': True},
        {'id': 'accent_color',    'label': 'Accent',        'type': 'color', 'default': '#ef4444'},
    ],
)
class HemaCellClassifier(NodeProcessor):
    def process(self, inputs, params):
        img        = inputs.get('image')
        labels_map = inputs.get('labels_map')

        empty_counts = {'RBC': 0, 'WBC': 0, 'PLT': 0, 'total': 0}
        empty_diff   = {'Neutrophil': 0, 'Lymphocyte': 0, 'Monocyte': 0,
                        'Eosinophil': 0, 'Basophil': 0}

        if img is None or labels_map is None:
            return {
                'overlay': img.copy() if img is not None else None,
                'counts':   empty_counts,
                'wbc_diff': empty_diff,
                'regions':  [],
            }

        labels = labels_map.astype(np.int32, copy=True)
        if labels.ndim == 3:
            labels = labels[..., 0]
        if labels.shape[:2] != img.shape[:2]:
            labels = cv2.resize(labels, (img.shape[1], img.shape[0]),
                                interpolation=cv2.INTER_NEAREST)

        mode         = int(params.get('mode', 0))  # 0=Basic 1=Differential
        differential = (mode == 1)
        min_area     = int(params.get('min_area_px', 30))
        rbc_max      = int(params.get('rbc_max_area_px', 400))
        plt_max      = int(params.get('plt_max_area_px', 60))
        show_labels  = bool(params.get('show_labels', True))
        accent_bgr   = _hex_to_bgr(params.get('accent_color', '#ef4444'))

        overlay = img.copy()

        b_ch, g_ch, r_ch = cv2.split(img.astype(np.float32))
        purple_score = b_ch * 0.5 + r_ch * 0.3 - g_ch * 0.8

        unique_labels = np.unique(labels)
        regions  = []
        counts   = dict(empty_counts)
        wbc_diff = dict(empty_diff)

        for lid in unique_labels:
            if lid == 0:
                continue

            region_mask = (labels == lid).astype(np.uint8)
            area_px = int(region_mask.sum())
            if area_px < min_area:
                continue

            contours, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_NONE)
            if not contours:
                continue
            contour   = max(contours, key=cv2.contourArea)
            perimeter = float(cv2.arcLength(contour, True))
            if perimeter <= 0:
                continue
            circularity = float(4.0 * np.pi * area_px / (perimeter * perimeter))

            ys, xs = np.where(region_mask > 0)
            cy = int(ys.mean())
            cx = int(xs.mean())
            x, y, w, h = cv2.boundingRect(contour)

            region_pixels = img[ys, xs]
            b_mean = float(region_pixels[:, 0].mean())
            g_mean = float(region_pixels[:, 1].mean())
            r_mean = float(region_pixels[:, 2].mean())

            cell_type = _classify_region(area_px, circularity,
                                         b_mean, g_mean, r_mean,
                                         plt_max, rbc_max)

            subtype = None
            if differential and cell_type == 'WBC':
                subtype = _classify_wbc_subtype(
                    region_pixels, region_mask, purple_score, circularity)
                wbc_diff[subtype] = wbc_diff.get(subtype, 0) + 1

            counts[cell_type] = counts.get(cell_type, 0) + 1
            counts['total']   = counts.get('total', 0) + 1

            regions.append({
                'label_id':   int(lid),
                'cell_type':  cell_type,
                'subtype':    subtype,
                'area_px':    area_px,
                'circularity': circularity,
                'centroid':   (cx, cy),
                'bbox':       (int(x), int(y), int(w), int(h)),
                'mean_bgr':   (b_mean, g_mean, r_mean),
            })

            if cell_type == 'PLT':
                radius = max(3, int(np.sqrt(area_px / np.pi)) + 1)
                cv2.circle(overlay, (cx, cy), radius, _BASIC_BGR['PLT'], 2)
                if show_labels:
                    cv2.putText(overlay, 'PLT', (cx + radius + 2, cy + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                                _BASIC_BGR['PLT'], 1, cv2.LINE_AA)
            elif cell_type == 'RBC':
                cv2.drawContours(overlay, [contour], -1, _BASIC_BGR['RBC'], 1)
                if show_labels:
                    cv2.putText(overlay, 'RBC', (cx - 10, cy + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                                _BASIC_BGR['RBC'], 1, cv2.LINE_AA)
            else:
                if differential and subtype is not None:
                    color = _SUBTYPE_BGR.get(subtype, _BASIC_BGR['WBC'])
                    tag   = subtype[:4]
                else:
                    color = _BASIC_BGR['WBC']
                    tag   = 'WBC'
                cv2.drawContours(overlay, [contour], -1, color, 3)
                if show_labels:
                    cv2.putText(overlay, tag, (cx - 14, cy + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                color, 1, cv2.LINE_AA)

        if show_labels:
            header = (f"Total {counts['total']}  "
                      f"RBC {counts['RBC']}  "
                      f"WBC {counts['WBC']}  "
                      f"PLT {counts['PLT']}")
            cv2.rectangle(overlay, (0, 0), (overlay.shape[1], 22),
                          accent_bgr, -1)
            cv2.putText(overlay, header, (8, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)

        return {
            'overlay':  overlay,
            'counts':   counts,
            'wbc_diff': wbc_diff,
            'regions':  regions,
        }
