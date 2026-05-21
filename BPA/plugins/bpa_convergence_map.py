"""
BPA Convergence Map — heatmap des intersections de rayons de stringing.

Pour chaque tache, on trace une ligne infinie dans la direction de la trajectoire
(axe majeur de l'ellipse). Chaque pixel traversé par une ligne reçoit +1.
Après accumulation, le buffer est normalisé et affiché avec un colormap chaud
(noir → rouge → jaune → blanc). La zone la plus chaude = estimation de l'origine
par convergence visuelle.

Plus robuste que le moindre carré face aux outliers individuels.
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import math

_NULL = {'heatmap': None, 'blend': None, 'peak_px': None}


def _accumulate_lines(stains, w, h):
    """Float accumulation buffer — Bresenham-style via cv2.line on float32."""
    buf = np.zeros((h, w), dtype=np.float32)
    for s in stains:
        cx, cy  = float(s['cx']), float(s['cy'])
        rot_deg = float(s['rot_deg'])
        rad = math.radians(rot_deg)
        dx, dy = math.cos(rad), -math.sin(rad)
        diag = int(math.hypot(w, h))
        x0 = int(cx - dx * diag)
        y0 = int(cy - dy * diag)
        x1 = int(cx + dx * diag)
        y1 = int(cy + dy * diag)
        cv2.line(buf, (x0, y0), (x1, y1), 1.0, 1)
    return buf


def _buf_to_heatmap(buf, blur_sigma):
    """Normalize + optional Gaussian smoothing + apply colormap."""
    if blur_sigma > 0:
        k = int(blur_sigma * 6) | 1
        buf = cv2.GaussianBlur(buf, (k, k), blur_sigma)
    vmax = buf.max()
    if vmax <= 0:
        return None
    norm = (buf / vmax * 255).astype(np.uint8)
    # COLORMAP_HOT: black → red → yellow → white
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_HOT)
    return colored


@vision_node(
    type_id='bpa_convergence_map',
    label='BPA Convergence Map',
    category='forensics',
    icon='Flame',
    description=(
        "Heatmap de convergence des rayons de stringing. "
        "Chaque tache génère une ligne infinie dans la direction de sa trajectoire. "
        "L'accumulation de ces lignes produit une carte de chaleur : "
        "zone blanche/jaune = forte convergence = origine probable. "
        "Plus robuste que la reconstruction par moindres carrés face aux outliers."
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',  'color': 'image', 'label': 'Image (pour blend)'},
        {'id': 'stains', 'color': 'dict',  'label': 'Stains Data'},
    ],
    outputs=[
        {'id': 'heatmap',  'color': 'image', 'label': 'Heatmap seul'},
        {'id': 'blend',    'color': 'image', 'label': 'Blend image+heatmap'},
        {'id': 'peak_px',  'color': 'dict',  'label': 'Peak position (px)'},
    ],
    params=[
        {'id': 'blur_sigma', 'label': 'Smoothing σ (px)', 'type': 'float',
         'default': 8.0, 'min': 0.0, 'max': 80.0, 'step': 1.0,
         'description': 'Gaussian blur applied after accumulation. Larger = softer heatmap.'},
        {'id': 'blend_alpha', 'label': 'Heatmap opacity', 'type': 'float',
         'default': 0.65, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'threshold_pct', 'label': 'Peak threshold (%)', 'type': 'int',
         'default': 85, 'min': 50, 'max': 99,
         'description': 'Percentile above which to show peak region.'},
        {'id': 'show_peak_marker', 'label': 'Show Peak Marker', 'type': 'bool', 'default': True},
    ],
)
class BPAConvergenceMapNode(NodeProcessor):
    def process(self, inputs, params):
        img         = inputs.get('image')
        stains_data = inputs.get('stains')
        if img is None or not stains_data:
            return _NULL

        stains = stains_data.get('stains', [])
        if not stains:
            return _NULL

        h, w       = img.shape[:2]
        blur_sigma = float(params.get('blur_sigma', 8.0))
        alpha      = float(params.get('blend_alpha', 0.65))
        thr_pct    = int(params.get('threshold_pct', 85))
        show_peak  = bool(params.get('show_peak_marker', True))

        # Accumulate
        buf     = _accumulate_lines(stains, w, h)
        heatmap = _buf_to_heatmap(buf, blur_sigma)
        if heatmap is None:
            return _NULL

        # Find peak
        blurred = cv2.GaussianBlur(buf, (0, 0), max(1.0, blur_sigma))
        _, _, _, peak_loc = cv2.minMaxLoc(blurred)
        peak_px = {'x': int(peak_loc[0]), 'y': int(peak_loc[1])}

        # Blend with image
        blend = cv2.addWeighted(img, 1.0 - alpha, heatmap, alpha, 0)

        if show_peak:
            px, py = peak_loc
            cv2.drawMarker(blend, (px, py), (255, 255, 255),
                           cv2.MARKER_STAR, 40, 2, cv2.LINE_AA)
            cv2.putText(blend, f'peak ({px},{py})', (px + 14, py - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            # Draw threshold contour
            thr_val = np.percentile(blurred, thr_pct)
            mask = (blurred >= thr_val).astype(np.uint8) * 255
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(blend, cnts, -1, (255, 220, 80), 1, cv2.LINE_AA)

        n = len(stains)
        cv2.putText(blend, f'n={n} rays  peak=({peak_px["x"]},{peak_px["y"]})',
                    (6, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)

        return {'heatmap': heatmap, 'blend': blend, 'peak_px': peak_px}
