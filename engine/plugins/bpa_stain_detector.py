from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import math

_NULL = {'annotated': None, 'mask': None, 'stain_count': 0, 'mean_angle': None, 'stains': None}


def _segment_blood(bgr, blur_r, a_thresh, val_max):
    blurred = cv2.GaussianBlur(bgr, (blur_r | 1, blur_r | 1), 0)

    # LAB A channel — dried blood has high A (red-green axis)
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    a_ch = lab[:, :, 1].astype(np.int16) - 128  # center at 0
    mask_a = (a_ch > a_thresh).astype(np.uint8) * 255

    # Value mask — exclude near-white background
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask_v = (hsv[:, :, 2] < val_max).astype(np.uint8) * 255

    return cv2.bitwise_and(mask_a, mask_v)


def _fit_stains(mask, min_area, max_area, min_aspect):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    stains = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area or len(cnt) < 5:
            continue
        ellipse = cv2.fitEllipse(cnt)
        (cx, cy), (ax1, ax2), rot = ellipse
        minor = min(ax1, ax2)
        major = max(ax1, ax2)
        if major == 0:
            continue
        aspect = minor / major
        if aspect < min_aspect:
            continue
        ratio = min(1.0, aspect)
        impact_angle = math.degrees(math.asin(ratio))
        stains.append({
            'cx': round(float(cx), 1),
            'cy': round(float(cy), 1),
            'major_px': round(float(major), 1),
            'minor_px': round(float(minor), 1),
            'aspect':   round(float(aspect), 4),
            'rot_deg':  round(float(rot), 2),
            'impact_angle_deg': round(float(impact_angle), 2),
            'area_px':  round(float(area), 1),
            '_ellipse': ellipse,
        })
    return stains


def _annotate(bgr, stains, show_ellipses, show_angles, show_centers):
    out = bgr.copy()
    for s in stains:
        e = s['_ellipse']
        cx, cy = int(s['cx']), int(s['cy'])
        if show_ellipses:
            cv2.ellipse(out, e, (0, 255, 80), 1, cv2.LINE_AA)
        if show_centers:
            cv2.circle(out, (cx, cy), 3, (0, 200, 255), -1)
        if show_angles:
            label = f"{s['impact_angle_deg']:.1f}deg"
            cv2.putText(out, label, (cx + 4, cy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1, cv2.LINE_AA)
    n = len(stains)
    cv2.putText(out, f'n={n}', (6, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


@vision_node(
    type_id='bpa_stain_detector',
    label='BPA Stain Detector',
    category='forensics',
    icon='Crosshair',
    description=(
        "Detects bloodstain ellipses on white substrate. "
        "Segments via LAB-A channel + value mask, fits ellipses per contour, "
        "computes impact angle: sin(α) = minor/major."
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',     'color': 'image',  'label': 'Image'},
        {'id': 'px_per_cm', 'color': 'scalar', 'label': 'px/cm (opt)'},
    ],
    outputs=[
        {'id': 'annotated',   'color': 'image',  'label': 'Annotated'},
        {'id': 'mask',        'color': 'mask',   'label': 'Mask'},
        {'id': 'stain_count', 'color': 'scalar', 'label': 'Stain Count'},
        {'id': 'mean_angle',  'color': 'scalar', 'label': 'Mean Angle (°)'},
        {'id': 'stains',      'color': 'dict',   'label': 'Stains Data'},
    ],
    params=[
        {'id': 'a_threshold', 'label': 'LAB-A Threshold', 'type': 'int',
         'default': 8, 'min': 1, 'max': 60},
        {'id': 'val_max',     'label': 'Max Value (BG)',   'type': 'int',
         'default': 210, 'min': 80, 'max': 255},
        {'id': 'blur_r',      'label': 'Blur Radius',      'type': 'int',
         'default': 3, 'min': 1, 'max': 15},
        {'id': 'min_area',    'label': 'Min Area (px²)',   'type': 'int',
         'default': 30, 'min': 5, 'max': 5000},
        {'id': 'max_area',    'label': 'Max Area (px²)',   'type': 'int',
         'default': 20000, 'min': 100, 'max': 200000},
        {'id': 'min_aspect',  'label': 'Min Aspect Ratio', 'type': 'float',
         'default': 0.15, 'min': 0.01, 'max': 1.0, 'step': 0.01},
        {'id': 'show_ellipses', 'label': 'Show Ellipses', 'type': 'bool', 'default': True},
        {'id': 'show_angles',   'label': 'Show Angles',   'type': 'bool', 'default': True},
        {'id': 'show_centers',  'label': 'Show Centers',  'type': 'bool', 'default': True},
    ],
)
class BPAStainDetectorNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return _NULL

        a_thresh    = int(params.get('a_threshold', 8))
        val_max     = int(params.get('val_max', 210))
        blur_r      = int(params.get('blur_r', 3))
        min_area    = int(params.get('min_area', 30))
        max_area    = int(params.get('max_area', 20000))
        min_aspect  = float(params.get('min_aspect', 0.15))
        show_ell    = bool(params.get('show_ellipses', True))
        show_ang    = bool(params.get('show_angles', True))
        show_ctr    = bool(params.get('show_centers', True))

        mask   = _segment_blood(img, blur_r, a_thresh, val_max)
        stains = _fit_stains(mask, min_area, max_area, min_aspect)

        angles = [s['impact_angle_deg'] for s in stains]
        mean_angle = round(float(np.mean(angles)), 2) if angles else None

        annotated = _annotate(img, stains, show_ell, show_ang, show_ctr)

        # Strip internal _ellipse before output
        stains_out = [{k: v for k, v in s.items() if k != '_ellipse'} for s in stains]

        return {
            'annotated':   annotated,
            'mask':        mask,
            'stain_count': len(stains),
            'mean_angle':  mean_angle,
            'stains':      {'stains': stains_out, 'count': len(stains_out)},
        }
