import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_region_color_stats',
    label='Region Color Stats',
    category='measure',
    icon='Palette',
    description=(
        'Enriches a regions list with per-region color statistics.\n\n'
        'Takes the label map and original image, computes mean/std for each BGR channel '
        'and HSV channel per labeled region. Outputs an augmented regions list '
        'compatible with Region Classifier and Region Props.\n\n'
        'New fields added to each region dict: '
        'mean_b, mean_g, mean_r, std_b, std_g, std_r, '
        'mean_h, mean_s, mean_v, dominant_hue.'
    ),
    resizable=True,
    min_width=240,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'image',      'label': 'Image (BGR)',  'color': 'image'},
        {'id': 'labels_map', 'label': 'Labels Map',   'color': 'markers'},
        {'id': 'regions_in', 'label': 'Regions (opt)','color': 'regions'},
    ],
    outputs=[
        {'id': 'regions', 'label': 'Regions + Color', 'color': 'regions'},
        {'id': 'count',   'label': 'Count',           'color': 'scalar'},
        {'id': 'main',    'label': 'Preview',         'color': 'image'},
    ],
    params=[
        {'id': 'colorspace', 'label': 'Color Space',    'type': 'enum', 'options': ['BGR', 'BGR + HSV', 'HSV only'], 'default': 1},
        {'id': 'show_ids',   'label': 'Show Region IDs','type': 'bool', 'default': False},
    ],
)
class RegionColorStatsNode(NodeProcessor):
    def process(self, inputs, params):
        img    = inputs.get('image')
        labels = inputs.get('labels_map')

        if img is None or labels is None:
            return {'regions': inputs.get('regions_in') or [], 'count': 0, 'main': img}

        src = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        lbl = labels.astype(np.int32)
        if lbl.ndim == 3:
            lbl = lbl[..., 0]
        if lbl.shape[:2] != src.shape[:2]:
            lbl = cv2.resize(lbl, (src.shape[1], src.shape[0]),
                             interpolation=cv2.INTER_NEAREST)

        colorspace = int(params.get('colorspace', 1))  # 0=BGR 1=BGR+HSV 2=HSV only
        do_bgr     = colorspace in (0, 1)
        do_hsv     = colorspace in (1, 2)
        show_ids    = bool(params.get('show_ids', False))

        hsv = cv2.cvtColor(src, cv2.COLOR_BGR2HSV).astype(np.float32) if do_hsv else None

        existing = {r['label_id']: r for r in (inputs.get('regions_in') or [])
                    if isinstance(r, dict) and 'label_id' in r}

        regions  = []
        unique   = np.unique(lbl)
        unique   = unique[unique > 0]

        for lid in unique:
            ys, xs = np.where(lbl == lid)
            if ys.size == 0:
                continue
            px_bgr = src[ys, xs].astype(np.float32)

            r = dict(existing.get(int(lid), {'label_id': int(lid)}))
            r['label_id'] = int(lid)

            if do_bgr:
                r['mean_b'] = round(float(px_bgr[:, 0].mean()), 2)
                r['mean_g'] = round(float(px_bgr[:, 1].mean()), 2)
                r['mean_r'] = round(float(px_bgr[:, 2].mean()), 2)
                r['std_b']  = round(float(px_bgr[:, 0].std()),  2)
                r['std_g']  = round(float(px_bgr[:, 1].std()),  2)
                r['std_r']  = round(float(px_bgr[:, 2].std()),  2)

            if do_hsv and hsv is not None:
                px_hsv = hsv[ys, xs]
                r['mean_h']       = round(float(px_hsv[:, 0].mean()), 2)
                r['mean_s']       = round(float(px_hsv[:, 1].mean()), 2)
                r['mean_v']       = round(float(px_hsv[:, 2].mean()), 2)
                r['dominant_hue'] = round(float(np.median(px_hsv[:, 0])), 2)

            regions.append(r)

        # Preview: colorize by mean hue or mean R
        preview = src.copy()
        for r in regions:
            lid = r['label_id']
            cy  = int(np.mean(np.where(lbl == lid)[0]))
            cx  = int(np.mean(np.where(lbl == lid)[1]))
            color = (int(r.get('mean_b', 128)),
                     int(r.get('mean_g', 128)),
                     int(r.get('mean_r', 128)))
            cv2.circle(preview, (cx, cy), 4, color, -1)
            cv2.circle(preview, (cx, cy), 5, (255, 255, 255), 1)
            if show_ids:
                cv2.putText(preview, str(lid), (cx + 6, cy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.30, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.putText(preview, f'n={len(regions)}', (6, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        return {'regions': regions, 'count': len(regions), 'main': preview}
