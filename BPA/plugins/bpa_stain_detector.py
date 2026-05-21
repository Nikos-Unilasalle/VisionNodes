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


def _fit_stains(mask, min_area_px, max_area_px, min_aspect):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    stains = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px or area > max_area_px or len(cnt) < 5:
            continue
        ellipse = cv2.fitEllipse(cnt)
        (cx, cy), (ax1, ax2), rot = ellipse
        minor = min(ax1, ax2)
        major = max(ax1, ax2)
        if major < 3:
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


def _filter_outliers(stains, sigma=2.5):
    """Remove spatial outliers (isolated stains far from the main cluster)."""
    if len(stains) < 6:
        return stains
    cx = np.array([s['cx'] for s in stains])
    cy = np.array([s['cy'] for s in stains])
    mc = np.median(cx)
    my = np.median(cy)
    dists = np.sqrt((cx - mc) ** 2 + (cy - my) ** 2)
    thresh = np.median(dists) + sigma * dists.std()
    return [s for s, d in zip(stains, dists) if d <= thresh]


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
            label = f"{s['impact_angle_deg']:.1f}°"
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
        "Detects bloodstain ellipses on white substrate (Attinger dataset). "
        "Segments via LAB-A channel (reddish hue of dried blood) + HSV-V mask (excludes white background). "
        "Fits ellipses to each contour, computes impact angle α via sin(α) = minor/major. "
        "min_stain_mm / max_stain_mm are scale-independent (require px_per_cm input). "
        "Outlier filter removes isolated stains spatially distant from the main pattern."
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',     'color': 'image',  'label': 'Image'},
        {'id': 'px_per_cm', 'color': 'scalar', 'label': 'px/cm'},
    ],
    outputs=[
        {'id': 'annotated',   'color': 'image',  'label': 'Annotated'},
        {'id': 'mask',        'color': 'mask',   'label': 'Mask'},
        {'id': 'stain_count', 'color': 'scalar', 'label': 'Stain Count'},
        {'id': 'mean_angle',  'color': 'scalar', 'label': 'Mean Angle (°)'},
        {'id': 'stains',      'color': 'dict',   'label': 'Stains Data'},
    ],
    params=[
        # Segmentation
        {'id': 'a_threshold', 'label': 'LAB-A Threshold',   'type': 'int',
         'default': 5, 'min': 1, 'max': 60,
         'description': 'Min LAB-A value (0=neutral, >0=reddish). Lower = more sensitive.'},
        {'id': 'val_max',     'label': 'Max HSV-V (BG)',    'type': 'int',
         'default': 230, 'min': 80, 'max': 255,
         'description': 'Exclude pixels brighter than this (white background). 230 keeps faint stains.'},
        {'id': 'blur_r',      'label': 'Blur Radius (px)',  'type': 'int',
         'default': 3, 'min': 1, 'max': 15},
        # Size gates — scale-independent (mm)
        {'id': 'min_stain_mm', 'label': 'Min Stain Ø (mm)', 'type': 'float',
         'default': 1.5, 'min': 0.2, 'max': 30.0, 'step': 0.5,
         'description': 'Minimum stain diameter in mm. Converted to px² using px/cm input.'},
        {'id': 'max_stain_mm', 'label': 'Max Stain Ø (mm)', 'type': 'float',
         'default': 30.0, 'min': 1.0, 'max': 200.0, 'step': 1.0,
         'description': 'Maximum stain diameter in mm. Filters large blobs (pooled blood, shadows).'},
        # Ellipse filter
        {'id': 'min_aspect',  'label': 'Min Aspect Ratio',  'type': 'float',
         'default': 0.1, 'min': 0.01, 'max': 1.0, 'step': 0.01,
         'description': 'Ellipse minor/major ≥ this value. 0.1 keeps elongated satellite stains.'},
        # Spatial outlier filter
        {'id': 'filter_outliers', 'label': 'Spatial Outlier Filter', 'type': 'bool', 'default': True,
         'description': 'Remove stains far from the main cluster (useful for large scans with noise).'},
        # Annotations
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

        px_per_cm = float(inputs.get('px_per_cm') or 23.62)  # fallback: 10% of 600dpi

        a_thresh   = int(params.get('a_threshold', 5))
        val_max    = int(params.get('val_max', 230))
        blur_r     = int(params.get('blur_r', 3))
        min_mm     = float(params.get('min_stain_mm', 1.5))
        max_mm     = float(params.get('max_stain_mm', 30.0))
        min_aspect = float(params.get('min_aspect', 0.1))
        do_filter  = bool(params.get('filter_outliers', True))
        show_ell   = bool(params.get('show_ellipses', True))
        show_ang   = bool(params.get('show_angles', True))
        show_ctr   = bool(params.get('show_centers', True))

        # Convert mm to px² (area of circle with diameter = stain size)
        px_per_mm   = px_per_cm / 10.0
        min_area_px = max(5, int(math.pi * (min_mm * px_per_mm / 2) ** 2))
        max_area_px = int(math.pi * (max_mm * px_per_mm / 2) ** 2)

        mask   = _segment_blood(img, blur_r, a_thresh, val_max)
        stains = _fit_stains(mask, min_area_px, max_area_px, min_aspect)

        if do_filter and stains:
            stains = _filter_outliers(stains)

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
