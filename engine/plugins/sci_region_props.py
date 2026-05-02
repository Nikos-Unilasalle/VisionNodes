import cv2
import numpy as np
from registry import vision_node, NodeProcessor

try:
    from skimage.measure import regionprops as _regionprops
    _SKIMAGE = True
except ImportError:
    _SKIMAGE = False


@vision_node(
    type_id='sci_region_props',
    label='Region Props',
    category=['analysis', 'scientific'],
    icon='Database',
    description=(
        "Extract shape and intensity features from a labeled region map (from Connected Components). "
        "Outputs a list of dicts: area, perimeter, circularity, aspect_ratio, solidity, eccentricity, "
        "equivalent_diameter, orientation, centroid_x/y, bbox. "
        "Connects image input for mean/max/std intensity per region."
    ),
    inputs=[
        {'id': 'labels_map', 'color': 'any',   'label': 'Label Map'},
        {'id': 'image',      'color': 'image',  'label': 'Image (intensity, optional)'},
    ],
    outputs=[
        {'id': 'regions', 'color': 'list',   'label': 'Regions'},
        {'id': 'count',   'color': 'scalar', 'label': 'Count'},
        {'id': 'main',    'color': 'image',  'label': 'Preview'},
    ],
    params=[
        {'id': 'intensity',    'label': 'Intensity Features', 'type': 'bool', 'default': True},
        {'id': 'show_ids',     'label': 'Show IDs',           'type': 'bool', 'default': False},
        {'id': 'show_ellipse', 'label': 'Show Ellipses',      'type': 'bool', 'default': False},
    ]
)
class RegionPropsNode(NodeProcessor):
    def process(self, inputs, params):
        labels = inputs.get('labels_map')
        img    = inputs.get('image')

        if labels is None:
            return {'regions': [], 'count': 0, 'main': img}

        label_img    = labels.astype(np.int32)
        do_intensity = bool(params.get('intensity', True)) and img is not None

        intensity_img = None
        if do_intensity:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
            intensity_img = gray.astype(np.float32)

        regions = []

        if _SKIMAGE:
            props = _regionprops(label_img, intensity_image=intensity_img)
            for p in props:
                area  = int(p.area)
                perim = float(p.perimeter) if p.perimeter > 0 else 1.0
                circ  = round(4.0 * np.pi * area / (perim ** 2), 4)
                maj   = float(p.axis_major_length)
                mino  = float(p.axis_minor_length)
                ar    = round(maj / mino, 4) if mino > 0 else 0.0
                cy, cx = p.centroid
                bb = p.bbox  # (min_row, min_col, max_row, max_col)
                r = {
                    'id':                   int(p.label),
                    'area':                 area,
                    'perimeter':            round(perim, 2),
                    'circularity':          circ,
                    'aspect_ratio':         ar,
                    'solidity':             round(float(p.solidity), 4),
                    'eccentricity':         round(float(p.eccentricity), 4),
                    'equivalent_diameter':  round(float(p.equivalent_diameter_area), 2),
                    'orientation':          round(float(p.orientation), 4),
                    'centroid_x':           round(float(cx), 1),
                    'centroid_y':           round(float(cy), 1),
                    'bbox':                 [int(bb[1]), int(bb[0]), int(bb[3] - bb[1]), int(bb[2] - bb[0])],
                }
                if do_intensity and intensity_img is not None:
                    px = intensity_img[label_img == p.label]
                    r['mean_intensity'] = round(float(p.intensity_mean), 2)
                    r['max_intensity']  = round(float(p.intensity_max), 2)
                    r['min_intensity']  = round(float(p.intensity_min), 2)
                    r['std_intensity']  = round(float(np.std(px)), 2)
                regions.append(r)
        else:
            # cv2 fallback — basic props without skimage
            unique = np.unique(label_img)
            unique = unique[unique > 0]
            solid_mask = (label_img > 0).astype(np.uint8) * 255
            cnts_all, _ = cv2.findContours(solid_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            cnt_by_label = {}
            for c in cnts_all:
                M = cv2.moments(c)
                if M['m00'] == 0:
                    continue
                cx_ = int(M['m10'] / M['m00'])
                cy_ = int(M['m01'] / M['m00'])
                lbl_at = int(label_img[cy_, cx_]) if 0 <= cy_ < label_img.shape[0] and 0 <= cx_ < label_img.shape[1] else 0
                if lbl_at > 0:
                    cnt_by_label[lbl_at] = c
            for lbl in unique:
                mask_l = (label_img == lbl).astype(np.uint8)
                area   = int(np.sum(mask_l))
                cnts_l, _ = cv2.findContours(mask_l * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cnts_l:
                    continue
                cnt = cnts_l[0]
                perim = float(cv2.arcLength(cnt, True))
                circ  = round(4.0 * np.pi * area / (perim ** 2), 4) if perim > 0 else 0.0
                hull  = cv2.convexHull(cnt)
                hull_area = float(cv2.contourArea(hull))
                solidity = round(area / hull_area, 4) if hull_area > 0 else 1.0
                rect = cv2.minAreaRect(cnt)
                ww, hh = rect[1]
                ar = round(max(ww, hh) / min(ww, hh), 4) if min(ww, hh) > 0 else 0.0
                M = cv2.moments(cnt)
                if M['m00'] == 0:
                    continue
                cx_ = M['m10'] / M['m00']
                cy_ = M['m01'] / M['m00']
                bx, by, bw, bh = cv2.boundingRect(cnt)
                eq_diam = round(float(np.sqrt(4.0 * area / np.pi)), 2)
                r = {
                    'id': int(lbl), 'area': area, 'perimeter': round(perim, 2),
                    'circularity': circ, 'aspect_ratio': ar, 'solidity': solidity,
                    'eccentricity': 0.0, 'equivalent_diameter': eq_diam, 'orientation': 0.0,
                    'centroid_x': round(float(cx_), 1), 'centroid_y': round(float(cy_), 1),
                    'bbox': [bx, by, bw, bh],
                }
                if do_intensity and intensity_img is not None:
                    px = intensity_img[label_img == lbl]
                    r['mean_intensity'] = round(float(np.mean(px)), 2)
                    r['max_intensity']  = round(float(np.max(px)), 2)
                    r['min_intensity']  = round(float(np.min(px)), 2)
                    r['std_intensity']  = round(float(np.std(px)), 2)
                regions.append(r)

        # ── Preview ──────────────────────────────────────────────────────────
        h, w = label_img.shape[:2]
        rng = np.random.default_rng(42)
        max_lbl = int(label_img.max()) if label_img.max() > 0 else 1
        lut = np.zeros((max_lbl + 1, 3), dtype=np.uint8)
        for r in regions:
            lut[r['id']] = rng.integers(80, 230, 3)

        colored = lut[np.clip(label_img, 0, max_lbl)]

        if img is not None:
            base = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            preview = cv2.addWeighted(base, 0.45, colored, 0.55, 0)
        else:
            preview = colored.copy()

        show_ids     = bool(params.get('show_ids', False))
        show_ellipse = bool(params.get('show_ellipse', False))

        for r in regions:
            cx_i, cy_i = int(r['centroid_x']), int(r['centroid_y'])
            cv2.drawMarker(preview, (cx_i, cy_i), (255, 255, 255), cv2.MARKER_CROSS, 8, 1, cv2.LINE_AA)
            if show_ids:
                cv2.putText(preview, str(r['id']), (cx_i + 5, cy_i - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1, cv2.LINE_AA)
            if show_ellipse and _SKIMAGE:
                maj_ax = r.get('equivalent_diameter', 10) / 2
                axes = (max(1, int(maj_ax)), max(1, int(maj_ax * (1.0 - r.get('eccentricity', 0)))))
                angle = int(np.degrees(r.get('orientation', 0)))
                cv2.ellipse(preview, (cx_i, cy_i), axes, angle, 0, 360, (200, 200, 200), 1, cv2.LINE_AA)

        cv2.putText(preview, f"n={len(regions)}", (6, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        return {'regions': regions, 'count': len(regions), 'main': preview}
