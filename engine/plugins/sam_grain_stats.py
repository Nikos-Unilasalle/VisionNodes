import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _parse_color(hex_str, fallback=(247, 195, 79)):
    try:
        h = str(hex_str).lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (b, g, r)
    except Exception:
        return fallback


def _feret_diameters(cnt):
    """Max and min Feret diameters from convex hull (px)."""
    hull = cv2.convexHull(cnt)
    pts = hull.reshape(-1, 2).astype(np.float32)
    if len(pts) < 2:
        return 0.0, 0.0
    # Max Feret: largest pairwise distance on convex hull
    diff = pts[:, np.newaxis] - pts[np.newaxis, :]
    dists = np.sqrt((diff ** 2).sum(axis=2))
    feret_max = float(dists.max())
    # Min Feret: minimum width = short side of min-area rect
    rect = cv2.minAreaRect(cnt)
    rw, rh = rect[1]
    feret_min = float(min(rw, rh)) if min(rw, rh) > 0 else 0.0
    return feret_max, feret_min


@vision_node(
    type_id='sam_grain_stats',
    label='Region Statistics',
    category='geology',
    icon='BarChart2',
    description=(
        "Métriques morphométriques depuis la segmentation automatique SAM ou FastSAM.\n\n"
        "Connecter 'Contours' depuis SAM Segmenter (mode Auto) ou FastSAM Segmenter.\n"
        "Connecter optionnellement le facteur de calibration (px/µm).\n\n"
        "Métriques : count, diamètre équivalent, Feret max/min, circularité, rapport de forme,\n"
        "fraction de grain — plus histogramme et courbe cumulative de taille."
    ),
    inputs=[
        {'id': 'contours',  'color': 'contours', 'label': 'Contours (SAM / FastSAM Auto)'},
        {'id': 'image',     'color': 'image',  'label': 'Image source (pour fraction)'},
        {'id': 'um_per_px', 'color': 'scalar', 'label': 'Px/µm (Calibration)'},
    ],
    outputs=[
        {'id': 'histogram',         'color': 'image',  'label': 'Histogramme + Courbe cumulative'},
        {'id': 'count',             'color': 'scalar', 'label': 'Nombre de grains'},
        {'id': 'mean_dia_um',       'color': 'scalar', 'label': 'Diamètre moyen (µm)'},
        {'id': 'median_dia_um',     'color': 'scalar', 'label': 'Diamètre médian (µm)'},
        {'id': 'mean_feret_max',    'color': 'scalar', 'label': 'Feret max moyen (µm)'},
        {'id': 'mean_feret_min',    'color': 'scalar', 'label': 'Feret min moyen (µm)'},
        {'id': 'mean_circularity',  'color': 'scalar', 'label': 'Circularité moyenne'},
        {'id': 'mean_aspect_ratio', 'color': 'scalar', 'label': 'Rapport de forme moyen'},
        {'id': 'grain_fraction',    'color': 'scalar', 'label': 'Fraction de grain (%)'},
        {'id': 'regions',           'color': 'regions', 'label': 'Régions (par grain)'},
    ],
    params=[
        {'id': 'min_area',   'label': 'Aire min (px²)',   'type': 'int',   'default': 200,      'min': 1,    'max': 500000},
        {'id': 'hist_bins',  'label': 'Bins histogramme', 'type': 'int',   'default': 30,       'min': 5,    'max': 100},
        {'id': 'hist_color', 'label': 'Couleur barres',   'type': 'color', 'default': '#4FC3F7'},
        {'id': 'um_per_px',  'label': 'Px/µm (fallback)', 'type': 'float', 'default': 1.0,    'min': 0.001, 'max': 10000.0},
    ]
)
class SAMGrainStats(NodeProcessor):

    def process(self, inputs, params):
        contours_in = inputs.get('contours')
        if not contours_in:
            return {'histogram': np.zeros((480, 600, 3), dtype=np.uint8), 'count': 0.0}

        image = inputs.get('image')
        um_px_in = inputs.get('um_per_px')
        um_per_px = float(um_px_in) if um_px_in is not None else float(params.get('um_per_px', 1.0))
        calibrated = um_per_px != 1.0
        um2_per_px2 = um_per_px ** 2
        unit_len  = 'µm' if calibrated else 'px'
        unit_area = 'µm²' if calibrated else 'px²'

        min_area  = int(params.get('min_area', 200))
        hist_bins = int(params.get('hist_bins', 30))
        bar_bgr   = _parse_color(params.get('hist_color', '#4FC3F7'))

        total_px = 0
        if image is not None:
            h_img, w_img = image.shape[:2]
            total_px = h_img * w_img

        regions = []
        grain_area_px = 0

        for pts in contours_in:
            cnt = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue

            perimeter = cv2.arcLength(cnt, True)
            circularity = (4.0 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0

            rect = cv2.minAreaRect(cnt)
            rw, rh = rect[1]
            aspect_ratio = (max(rw, rh) / min(rw, rh)) if min(rw, rh) > 0 else 1.0

            feret_max_px, feret_min_px = _feret_diameters(cnt)

            M = cv2.moments(cnt)
            if M['m00'] > 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
            else:
                x, y, bw, bh = cv2.boundingRect(cnt)
                cx, cy = x + bw // 2, y + bh // 2

            area_cal     = area * um2_per_px2
            dia_cal      = round(2.0 * np.sqrt(area_cal / np.pi), 2)
            feret_max_cal = round(feret_max_px * um_per_px, 2)
            feret_min_cal = round(feret_min_px * um_per_px, 2)

            regions.append({
                'area_px2':     round(float(area), 1),
                'area_cal':     round(float(area_cal), 2),
                'diameter_um':  dia_cal,
                'feret_max':    feret_max_cal,
                'feret_min':    feret_min_cal,
                'circularity':  round(float(circularity), 4),
                'aspect_ratio': round(float(aspect_ratio), 4),
                'centroid_x':   cx,
                'centroid_y':   cy,
            })
            grain_area_px += area

        if not regions:
            return {
                'histogram': np.zeros((480, 600, 3), dtype=np.uint8),
                'count': 0.0, 'mean_dia_um': 0.0, 'median_dia_um': 0.0,
                'mean_feret_max': 0.0, 'mean_feret_min': 0.0,
                'mean_circularity': 0.0, 'mean_aspect_ratio': 0.0,
                'grain_fraction': 0.0, 'regions': [],
            }

        count         = len(regions)
        areas_cal     = np.array([r['area_cal'] for r in regions],    dtype=np.float32)
        diameters     = np.array([r['diameter_um'] for r in regions], dtype=np.float32)
        feret_maxs    = np.array([r['feret_max'] for r in regions],   dtype=np.float32)
        feret_mins    = np.array([r['feret_min'] for r in regions],   dtype=np.float32)
        circs         = np.array([r['circularity'] for r in regions], dtype=np.float32)
        aspects       = np.array([r['aspect_ratio'] for r in regions],dtype=np.float32)

        mean_dia      = float(np.mean(diameters))
        median_dia    = float(np.median(diameters))
        mean_feret_mx = float(np.mean(feret_maxs))
        mean_feret_mn = float(np.mean(feret_mins))
        mean_circ     = float(np.mean(circs))
        mean_ar       = float(np.mean(aspects))
        mean_area_c   = float(np.mean(areas_cal))
        median_area_c = float(np.median(areas_cal))
        std_area_c    = float(np.std(areas_cal))
        grain_frac    = round(100.0 * grain_area_px / total_px, 2) if total_px > 0 else 0.0

        hist_img = _histogram(
            areas_cal, diameters, count, hist_bins, bar_bgr,
            mean_dia, mean_circ, mean_ar, grain_frac,
            mean_area_c, median_area_c, std_area_c,
            mean_feret_mx, mean_feret_mn,
            unit_len, unit_area,
        )

        return {
            'histogram':         hist_img,
            'count':             float(count),
            'mean_dia_um':       round(mean_dia, 2),
            'median_dia_um':     round(median_dia, 2),
            'mean_feret_max':    round(mean_feret_mx, 2),
            'mean_feret_min':    round(mean_feret_mn, 2),
            'mean_circularity':  round(mean_circ, 4),
            'mean_aspect_ratio': round(mean_ar, 4),
            'grain_fraction':    grain_frac,
            'regions':           regions,
        }


def _histogram(areas_cal, diameters, count, bins, bar_bgr,
               mean_dia, mean_circ, mean_ar, grain_frac,
               mean_area, median_area, std_area,
               mean_feret_max, mean_feret_min,
               unit_len, unit_area):

    IW, IH = 600, 480
    img = np.full((IH, IW, 3), 30, dtype=np.uint8)

    # ── Upper panel: size histogram ───────────────────────────────────────────
    HIST_TOP = 10
    HIST_BOT = 270  # bottom of histogram area

    hist_vals, bin_edges = np.histogram(diameters, bins=bins)
    max_c = max(hist_vals.max(), 1)
    bar_w = max(1, (IW - 80) // bins)
    x0 = 50

    for i, (c, edge) in enumerate(zip(hist_vals, bin_edges[:-1])):
        bar_h = int((c / max_c) * (HIST_BOT - HIST_TOP - 40))
        bx = x0 + i * bar_w
        by = HIST_BOT - bar_h
        cv2.rectangle(img, (bx, by), (bx + bar_w - 2, HIST_BOT), bar_bgr, -1)

    cv2.putText(img, f'Grain Size Distribution  (n={count})',
                (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    cv2.putText(img, f'Equiv. Diameter ({unit_len})',
                (IW // 2 - 55, HIST_BOT + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
    cv2.putText(img, f'{bin_edges[0]:.2g}',
                (x0, HIST_BOT + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)
    cv2.putText(img, f'{bin_edges[-1]:.2g}',
                (x0 + bins * bar_w - 30, HIST_BOT + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)

    # Stats panel (right side of histogram)
    stats_lines = [
        f'Count : {count}',
        f'Mean  : {mean_area:.2g} {unit_area}',
        f'Median: {median_area:.2g} {unit_area}',
        f'StdDev: {std_area:.2g} {unit_area}',
        f'Diam. : {mean_dia:.2g} {unit_len}',
        f'FerMax: {mean_feret_max:.2g} {unit_len}',
        f'FerMin: {mean_feret_min:.2g} {unit_len}',
        f'Circ. : {mean_circ:.3f}',
        f'AR    : {mean_ar:.2f}',
        f'Grain : {grain_frac:.1f}%',
    ]
    for i, line in enumerate(stats_lines):
        cv2.putText(img, line, (IW - 175, 35 + i * 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 230, 200), 1)

    # ── Lower panel: cumulative frequency curve ───────────────────────────────
    CUM_TOP  = HIST_BOT + 35
    CUM_BOT  = IH - 20
    CUM_LEFT = x0
    CUM_RIGHT = IW - 20

    # Axes
    cv2.line(img, (CUM_LEFT, CUM_TOP), (CUM_LEFT, CUM_BOT), (100, 100, 100), 1)
    cv2.line(img, (CUM_LEFT, CUM_BOT), (CUM_RIGHT, CUM_BOT), (100, 100, 100), 1)
    cv2.putText(img, 'Cumulative frequency (%)',
                (CUM_LEFT, CUM_TOP - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)

    sorted_d = np.sort(diameters)
    d_min, d_max = float(sorted_d[0]), float(sorted_d[-1])
    d_range = max(d_max - d_min, 1e-6)
    cum_pcts = np.arange(1, len(sorted_d) + 1) / len(sorted_d) * 100.0

    def _x(d):
        return int(CUM_LEFT + (float(d) - d_min) / d_range * (CUM_RIGHT - CUM_LEFT))

    def _y(pct):
        return int(CUM_BOT - float(pct) / 100.0 * (CUM_BOT - CUM_TOP))

    # Draw curve
    pts_curve = [(_x(d), _y(p)) for d, p in zip(sorted_d, cum_pcts)]
    for j in range(len(pts_curve) - 1):
        cv2.line(img, pts_curve[j], pts_curve[j + 1], bar_bgr, 1)

    # D10, D50, D90 percentile markers
    for pct_val, label in [(10, 'D10'), (50, 'D50'), (90, 'D90')]:
        d_pct = float(np.percentile(sorted_d, pct_val))
        px = _x(d_pct)
        py = _y(pct_val)
        cv2.line(img, (px, CUM_BOT), (px, py), (80, 80, 80), 1)
        cv2.circle(img, (px, py), 3, (255, 220, 80), -1)
        cv2.putText(img, f'{label}={d_pct:.2g}',
                    (max(CUM_LEFT, px - 14), CUM_BOT + 13),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 100), 1)

    # Y-axis ticks: 0, 25, 50, 75, 100
    for tick_pct in [0, 25, 50, 75, 100]:
        ty = _y(tick_pct)
        cv2.line(img, (CUM_LEFT - 3, ty), (CUM_LEFT, ty), (100, 100, 100), 1)
        cv2.putText(img, str(tick_pct),
                    (CUM_LEFT - 28, ty + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (140, 140, 140), 1)

    return img
