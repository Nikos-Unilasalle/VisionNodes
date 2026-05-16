import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_DEFAULT_CODE = '''\
# Classify each region. Variable `r` is a dict with all region fields.
# Return a string class label.
#
# Available fields (if upstream nodes connected):
#   r['area_px'], r['circularity'], r['aspect_ratio'], r['solidity']
#   r['mean_r'], r['mean_g'], r['mean_b']   (needs Region Color Stats)
#   r['mean_h'], r['mean_s'], r['mean_v']   (needs Region Color Stats, BGR+HSV)
#
# Example — classify by size:
if r.get('area_px', 0) < 60:
    return 'Small'
elif r.get('circularity', 0) > 0.75:
    return 'Round'
else:
    return 'Other'
'''

_CLASS_COLORS = [
    (80,  200, 80),   # green
    (80,  80,  220),  # red
    (0,   200, 240),  # yellow
    (220, 120, 40),   # blue
    (180, 80,  220),  # purple
    (80,  220, 200),  # teal
    (220, 160, 60),   # cyan
    (200, 80,  140),  # pink
]


def _run_classifier(code: str, region: dict):
    wrapped = 'def _clf(r):\n'
    for line in code.splitlines():
        wrapped += '    ' + line + '\n'
    wrapped += '\n_result = _clf(_r)\n'
    ns = {'_r': region}
    exec(wrapped, ns)  # noqa: S102
    return str(ns.get('_result', 'Unknown'))


@vision_node(
    type_id='sci_region_classifier',
    label='Region Classifier',
    category='measure',
    icon='Tag',
    description=(
        'Classifies labeled regions using a user-defined Python rule.\n\n'
        'Connect a regions list (from Region Props or Region Color Stats) '
        'and a label map, then write your classification logic in the code block. '
        'The variable `r` is a dict of all region features. Return a string class label.\n\n'
        'Outputs: classified regions list, counts per class, colored overlay.'
    ),
    resizable=True,
    min_width=300,
    min_height=220,
    colorable=True,
    inputs=[
        {'id': 'regions',    'label': 'Regions',    'color': 'list'},
        {'id': 'labels_map', 'label': 'Labels Map', 'color': 'any'},
        {'id': 'image',      'label': 'Image',      'color': 'image'},
    ],
    outputs=[
        {'id': 'regions_out','label': 'Regions + Class', 'color': 'list'},
        {'id': 'counts',     'label': 'Counts',          'color': 'dict'},
        {'id': 'overlay',    'label': 'Overlay',         'color': 'image'},
    ],
    params=[
        {'id': 'code',        'label': 'Classification Rule', 'type': 'code',  'default': _DEFAULT_CODE},
        {'id': 'show_labels', 'label': 'Show Labels',         'type': 'bool',  'default': True},
        {'id': 'outline_only','label': 'Outline Only',        'type': 'bool',  'default': False},
    ],
)
class RegionClassifierNode(NodeProcessor):
    def process(self, inputs, params):
        regions    = inputs.get('regions') or []
        labels_map = inputs.get('labels_map')
        img        = inputs.get('image')
        code       = str(params.get('code', _DEFAULT_CODE))
        show_lbl   = bool(params.get('show_labels', True))
        outline    = bool(params.get('outline_only', False))

        if not regions:
            return {'regions_out': [], 'counts': {}, 'overlay': img}

        src = None
        if img is not None:
            src = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif labels_map is not None:
            h, w = labels_map.shape[:2]
            src = np.zeros((h, w, 3), dtype=np.uint8)

        # Assign a stable color index per class name (deterministic order)
        class_color_map: dict[str, tuple] = {}
        color_idx = 0

        classified = []
        counts: dict[str, int] = {}

        for r in regions:
            try:
                cls = _run_classifier(code, r)
            except Exception as e:
                cls = f'Error: {e}'
            new_r = dict(r)
            new_r['class'] = cls
            classified.append(new_r)
            counts[cls] = counts.get(cls, 0) + 1
            if cls not in class_color_map:
                class_color_map[cls] = _CLASS_COLORS[color_idx % len(_CLASS_COLORS)]
                color_idx += 1

        # Draw overlay
        if src is not None and labels_map is not None:
            lbl = labels_map.astype(np.int32)
            if lbl.ndim == 3:
                lbl = lbl[..., 0]
            if lbl.shape[:2] != src.shape[:2]:
                lbl = cv2.resize(lbl, (src.shape[1], src.shape[0]),
                                 interpolation=cv2.INTER_NEAREST)
            overlay = src.copy()
            for cr in classified:
                lid   = cr.get('label_id')
                cls   = cr.get('class', 'Unknown')
                color = class_color_map.get(cls, (200, 200, 200))
                if lid is None:
                    continue
                region_mask = (lbl == lid).astype(np.uint8) * 255
                contours, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    continue
                if outline:
                    cv2.drawContours(overlay, contours, -1, color, 2)
                else:
                    fill = np.zeros_like(overlay)
                    cv2.drawContours(fill, contours, -1, color, -1)
                    overlay = cv2.addWeighted(overlay, 0.7, fill, 0.3, 0)
                    cv2.drawContours(overlay, contours, -1, color, 1)
                if show_lbl:
                    cx_r = cr.get('centroid', (None, None))
                    if isinstance(cx_r, (list, tuple)) and len(cx_r) == 2:
                        cx_i, cy_i = int(cx_r[0]), int(cx_r[1])
                    else:
                        ys, xs = np.where(lbl == lid)
                        cy_i, cx_i = int(ys.mean()), int(xs.mean())
                    cv2.putText(overlay, cls, (cx_i - 14, cy_i + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)
            # Legend top-right
            lx = overlay.shape[1] - 140
            ly = 10
            for cls, color in class_color_map.items():
                cv2.rectangle(overlay, (lx, ly), (lx + 14, ly + 14), color, -1)
                cv2.putText(overlay, f'{cls} ({counts.get(cls, 0)})',
                            (lx + 18, ly + 11),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (220, 220, 220), 1, cv2.LINE_AA)
                ly += 18
        else:
            overlay = img

        return {'regions_out': classified, 'counts': counts, 'overlay': overlay}
