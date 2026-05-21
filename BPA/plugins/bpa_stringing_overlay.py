"""
BPA Stringing Overlay — dessine les "cordes" forensiques sur l'image.

Pour chaque tache :
  - Ligne tracée dans la direction de la trajectoire (axe majeur de l'ellipse)
  - Prolongée sur toute l'image dans les deux sens
  - Couleur = angle d'impact (bleu=faible/loin, rouge=élevé/proche)

Si les coordonnées de l'origine estimée sont disponibles :
  - La projection de l'origine sur le plan cible est marquée sur l'image
  - Un cercle de convergence est dessiné autour du centroïde des intersections

Utilisation forensique : les lignes convergent visuellement vers la zone d'origine.
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import math

_NULL = {'overlay': None, 'convergence_px': None}


def _angle_color(impact_deg: float) -> tuple:
    """Blue (low impact/far) → yellow → red (high impact/close)."""
    t = max(0.0, min(1.0, impact_deg / 90.0))
    if t < 0.5:
        r = int(255 * t * 2)
        g = int(255 * t * 2)
        b = 255
    else:
        r = 255
        g = int(255 * (1.0 - (t - 0.5) * 2))
        b = 0
    return (b, g, r)  # BGR


def _line_endpoints(cx, cy, rot_deg, img_w, img_h, length_px):
    """Endpoints of a line through (cx,cy) at angle rot_deg, clipped to image."""
    rad = math.radians(rot_deg)
    dx = math.cos(rad)
    dy = -math.sin(rad)
    # Extend in both directions
    x0 = int(cx - dx * length_px)
    y0 = int(cy - dy * length_px)
    x1 = int(cx + dx * length_px)
    y1 = int(cy + dy * length_px)
    return (x0, y0), (x1, y1)


def _project_origin_to_image(est_x, est_y, est_z, x_t, y_t, z_t,
                               px_per_cm, img_h_px):
    """World origin (est_x, est_y, est_z) → pixel coords on target image.

    The projection is only meaningful if est_x ≈ x_t (origin is near target plane).
    For far origins (est_x >> x_t) the projection is the vanishing point of the fan.
    """
    u_cm = est_y - y_t          # horizontal offset on target
    v_cm = z_t + img_h_px / px_per_cm - est_z  # vertical offset (image top = high z)
    px = int(u_cm * px_per_cm)
    py = int(v_cm * px_per_cm)
    return px, py


@vision_node(
    type_id='bpa_stringing_overlay',
    label='BPA Stringing Overlay',
    category='forensics',
    icon='GitMerge',
    description=(
        "Forensic stringing overlay: draws a trajectory line through each detected stain "
        "along its major axis direction. Lines converge toward the blood origin. "
        "Color encodes impact angle (blue=low/far, red=high/close). "
        "Optionally marks the projected origin and convergence centroid."
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',     'color': 'image',  'label': 'Image'},
        {'id': 'stains',    'color': 'dict',   'label': 'Stains Data'},
        {'id': 'px_per_cm', 'color': 'scalar', 'label': 'px/cm'},
        {'id': 'est_y',     'color': 'scalar', 'label': 'Est. Y (cm)'},
        {'id': 'est_z',     'color': 'scalar', 'label': 'Est. Z (cm)'},
        {'id': 'gt_y',      'color': 'scalar', 'label': 'GT Y (cm)'},
        {'id': 'gt_z',      'color': 'scalar', 'label': 'GT Z (cm)'},
        {'id': 'y_t',       'color': 'scalar', 'label': 'Target Y (cm)'},
        {'id': 'z_t',       'color': 'scalar', 'label': 'Target Z (cm)'},
    ],
    outputs=[
        {'id': 'overlay',        'color': 'image',  'label': 'Stringing Overlay'},
        {'id': 'convergence_px', 'color': 'dict',   'label': 'Convergence Point (px)'},
    ],
    params=[
        {'id': 'line_alpha',  'label': 'Line Opacity',    'type': 'float',
         'default': 0.45, 'min': 0.05, 'max': 1.0, 'step': 0.05},
        {'id': 'line_thick',  'label': 'Line Thickness',  'type': 'int',
         'default': 1, 'min': 1, 'max': 5},
        {'id': 'show_origin', 'label': 'Show Origin Proj.','type': 'bool', 'default': True},
        {'id': 'show_gt',     'label': 'Show GT Origin',  'type': 'bool', 'default': True},
        {'id': 'show_convergence', 'label': 'Show Convergence Centroid', 'type': 'bool', 'default': True},
        {'id': 'darken_bg',   'label': 'Darken Background','type': 'bool', 'default': False},
    ],
)
class BPAStringingOverlayNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        stains_data = inputs.get('stains')
        if img is None or not stains_data:
            return _NULL

        stains = stains_data.get('stains', [])
        if not stains:
            return _NULL

        px_per_cm = float(inputs.get('px_per_cm') or 23.62)
        h, w = img.shape[:2]
        diag = int(math.hypot(w, h))

        alpha     = float(params.get('line_alpha', 0.45))
        thick     = int(params.get('line_thick', 1))
        show_orig = bool(params.get('show_origin', True))
        show_gt   = bool(params.get('show_gt', True))
        show_conv = bool(params.get('show_convergence', True))
        darken    = bool(params.get('darken_bg', False))

        base = img.copy()
        if darken:
            base = (base * 0.4).astype(np.uint8)

        overlay = base.copy()

        # Draw stringing lines
        for s in stains:
            cx, cy   = float(s['cx']), float(s['cy'])
            rot      = float(s['rot_deg'])
            impact   = float(s['impact_angle_deg'])
            color    = _angle_color(impact)
            p0, p1   = _line_endpoints(cx, cy, rot, w, h, diag)
            cv2.line(overlay, p0, p1, color, thick, cv2.LINE_AA)

        # Blend lines with base
        result = cv2.addWeighted(base, 1.0 - alpha, overlay, alpha, 0)

        # Re-draw stain centers on top (always fully opaque)
        for s in stains:
            cx, cy = int(s['cx']), int(s['cy'])
            color  = _angle_color(float(s['impact_angle_deg']))
            cv2.circle(result, (cx, cy), 3, color, -1, cv2.LINE_AA)

        # Convergence centroid: median of stain centers
        conv_px = None
        if show_conv and stains:
            cxs = [s['cx'] for s in stains]
            cys = [s['cy'] for s in stains]
            mx, my = int(np.median(cxs)), int(np.median(cys))
            conv_px = {'x': mx, 'y': my}
            cv2.drawMarker(result, (mx, my), (0, 255, 255),
                           cv2.MARKER_CROSS, 30, 2, cv2.LINE_AA)
            cv2.circle(result, (mx, my), 20, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(result, 'centroid', (mx + 12, my - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)

        # Estimated origin projection on target face
        est_y = inputs.get('est_y')
        est_z = inputs.get('est_z')
        y_t   = inputs.get('y_t')
        z_t   = inputs.get('z_t')
        if show_orig and None not in (est_y, est_z, y_t, z_t):
            px, py = _project_origin_to_image(None, est_y, est_z, None, y_t, z_t, px_per_cm, h)
            cv2.drawMarker(result, (px, py), (0, 80, 255),
                           cv2.MARKER_STAR, 40, 2, cv2.LINE_AA)
            cv2.putText(result, 'est.origin', (px + 16, py),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 80, 255), 1, cv2.LINE_AA)

        # Ground truth origin projection
        gt_y = inputs.get('gt_y')
        gt_z = inputs.get('gt_z')
        if show_gt and None not in (gt_y, gt_z, y_t, z_t):
            px, py = _project_origin_to_image(None, gt_y, gt_z, None, y_t, z_t, px_per_cm, h)
            cv2.drawMarker(result, (px, py), (0, 220, 60),
                           cv2.MARKER_TILTED_CROSS, 40, 2, cv2.LINE_AA)
            cv2.putText(result, 'GT origin', (px + 16, py),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 60), 1, cv2.LINE_AA)

        # Legend (top-left)
        for i, (label, color) in enumerate([
            ('low angle (far)', _angle_color(15)),
            ('mid angle',       _angle_color(45)),
            ('high angle (close)', _angle_color(80)),
        ]):
            y_leg = 20 + i * 18
            cv2.line(result, (8, y_leg), (30, y_leg), color, 2)
            cv2.putText(result, label, (34, y_leg + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, (200, 200, 200), 1)

        n = len(stains)
        cv2.putText(result, f'n={n} strings', (8, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

        return {'overlay': result, 'convergence_px': conv_px}
