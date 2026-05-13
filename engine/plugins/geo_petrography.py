from registry import vision_node, NodeProcessor
import cv2
import numpy as np


@vision_node(
    type_id='geo_opaque_detect',
    label='Opaque Mineral Detect',
    category='geology',
    icon='Moon',
    description=(
        "Detects opaque minerals (magnetite, ilmenite, pyrite…) in thin section images. "
        "Dark large blobs in XPL (and PPL when available) are isolated from thin grain-boundary lines "
        "using morphological opening and area filtering."
    ),
    inputs=[
        {'id': 'xpl', 'color': 'image', 'label': 'XPL'},
        {'id': 'ppl', 'color': 'image', 'label': 'PPL (optional)'},
    ],
    outputs=[
        {'id': 'mask',    'color': 'mask',  'label': 'Opaque Mask'},
        {'id': 'overlay', 'color': 'image', 'label': 'Overlay'},
        {'id': 'count',   'color': 'scalar','label': 'Count'},
    ],
    params=[
        {'id': 'blur_radius',   'label': 'Blur Radius',      'type': 'int',   'default': 4,   'min': 1,  'max': 15},
        {'id': 'dark_thresh',   'label': 'Darkness Threshold','type': 'int',   'default': 35,  'min': 5,  'max': 120},
        {'id': 'opening_size',  'label': 'Opening Size (px)', 'type': 'int',   'default': 15,  'min': 3,  'max': 51},
        {'id': 'min_area',      'label': 'Min Area (px)',     'type': 'int',   'default': 300, 'min': 50, 'max': 50000},
        {'id': 'overlay_color', 'label': 'Overlay Color',     'type': 'color', 'default': '#8B0000'},
    ]
)
class GeoOpaqueDetect(NodeProcessor):

    def _to_gray(self, img, ksize):
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return cv2.GaussianBlur(gray, (ksize, ksize), 0)

    def process(self, inputs, params):
        xpl = inputs.get('xpl')
        if xpl is None:
            return {}
        if len(xpl.shape) == 2:
            xpl = cv2.cvtColor(xpl, cv2.COLOR_GRAY2BGR)
        ppl = inputs.get('ppl')
        if ppl is not None and len(ppl.shape) == 2:
            ppl = cv2.cvtColor(ppl, cv2.COLOR_GRAY2BGR)

        blur_r      = int(params.get('blur_radius', 4))
        dark_t      = int(params.get('dark_thresh', 35))
        open_sz     = int(params.get('opening_size', 15))
        min_area    = int(params.get('min_area', 300))

        ksize = blur_r * 2 + 1
        open_sz = open_sz if open_sz % 2 == 1 else open_sz + 1

        # Dark mask from XPL
        xpl_gray = self._to_gray(xpl, ksize)
        dark = (xpl_gray < dark_t).astype(np.uint8) * 255

        # Intersect with PPL dark mask if available (true opaques = dark in both)
        if ppl is not None:
            ppl_gray = self._to_gray(ppl, ksize)
            dark_ppl = (ppl_gray < dark_t).astype(np.uint8) * 255
            dark = cv2.bitwise_and(dark, dark_ppl)

        # Opening: erode large → thin boundary lines vanish, opaque blobs survive
        k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_sz, open_sz))
        opened = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k_open)

        # Area filter
        n, lbl, stats, _ = cv2.connectedComponentsWithStats(opened)
        mask = np.zeros_like(opened)
        count = 0
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                mask[lbl == i] = 255
                count += 1

        # Overlay color parsing
        hex_c = str(params.get('overlay_color', '#8B0000')).lstrip('#')
        try:
            r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
            bgr = (b, g, r)
        except Exception:
            bgr = (0, 0, 139)

        overlay = xpl.copy()
        overlay[mask == 255] = bgr

        return {'mask': mask, 'overlay': overlay, 'count': count}


@vision_node(
    type_id='geo_grain_markers',
    label='Grain Markers',
    category='geology',
    icon='Target',
    description=(
        "Builds watershed markers for grain segmentation. Takes a grain-interior mask and an opaque mask, "
        "applies per-component morphological closing to fill micro-fractures without merging adjacent grains, "
        "then places exactly one seed per grain. Feed markers into the Watershed node."
    ),
    inputs=[
        {'id': 'interior', 'color': 'any',  'label': 'Interior Mask'},
        {'id': 'opaques',  'color': 'any',  'label': 'Opaque Mask (optional)'},
        {'id': 'boundary', 'color': 'any',  'label': 'Boundary Mask (optional)'},
    ],
    outputs=[
        {'id': 'markers',  'color': 'any',  'label': 'Markers (int32)'},
        {'id': 'preview',  'color': 'image','label': 'Preview'},
        {'id': 'count',    'color': 'scalar','label': 'Grain Count'},
    ],
    params=[
        {'id': 'min_grain_px', 'label': 'Min Grain (px)',       'type': 'int', 'default': 500, 'min': 50,  'max': 50000},
        {'id': 'fill_radius',  'label': 'Fill Radius (cracks)', 'type': 'int', 'default': 5,   'min': 0,   'max': 30},
        {'id': 'seed_erosion', 'label': 'Seed Erosion (px)',    'type': 'int', 'default': 5,   'min': 1,   'max': 30},
    ]
)
class GeoGrainMarkers(NodeProcessor):

    def _to_mask(self, img):
        if img is None:
            return None
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img.astype(np.uint8)

    def process(self, inputs, params):
        interior_raw = self._to_mask(inputs.get('interior'))
        if interior_raw is None:
            return {}

        opaques  = self._to_mask(inputs.get('opaques'))
        boundary = self._to_mask(inputs.get('boundary'))

        min_px     = int(params.get('min_grain_px', 500))
        fill_r     = int(params.get('fill_radius', 5))
        seed_er    = int(params.get('seed_erosion', 5))

        h, w = interior_raw.shape[:2]

        # Binarize interior
        _, interior = cv2.threshold(interior_raw, 127, 255, cv2.THRESH_BINARY)

        # Remove opaque zones from interior
        if opaques is not None:
            _, op_bin = cv2.threshold(opaques, 127, 255, cv2.THRESH_BINARY)
            interior = cv2.bitwise_and(interior, cv2.bitwise_not(op_bin))

        # Build markers: 1 = background, grains start at 2
        markers = np.ones((h, w), dtype=np.int32)

        # Mark opaque zones as background (label 1)
        # Mark boundary as unknown (label 0)
        if boundary is not None:
            _, bnd_bin = cv2.threshold(boundary, 127, 255, cv2.THRESH_BINARY)
            markers[bnd_bin == 255] = 0

        # Process each connected component independently
        n, comp_lbl, stats, centroids = cv2.connectedComponentsWithStats(interior)

        grain_id = 2
        k_fill = (cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                  (fill_r * 2 + 1, fill_r * 2 + 1)) if fill_r > 0 else None)
        k_seed = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                  (seed_er * 2 + 1, seed_er * 2 + 1))

        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < min_px:
                continue

            # Isolate component
            blob = (comp_lbl == i).astype(np.uint8) * 255

            # Fill micro-cracks per-component (closing on isolated blob → no inter-grain merge)
            if k_fill is not None:
                blob = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, k_fill)
                # Reapply opaque exclusion after closing
                if opaques is not None:
                    blob = cv2.bitwise_and(blob, cv2.bitwise_not(op_bin))

            # Erode to get safe interior core (seed zone)
            core = cv2.erode(blob, k_seed)

            if cv2.countNonZero(core) > 0:
                markers[core > 0] = grain_id
            else:
                # Fallback: centroid pixel
                cx, cy = int(centroids[i][0]), int(centroids[i][1])
                if 0 <= cy < h and 0 <= cx < w:
                    markers[cy, cx] = grain_id

            grain_id += 1

        # Apply boundary unknown zone on top of markers
        if boundary is not None:
            markers[bnd_bin == 255] = 0

        count = grain_id - 2

        # Preview: colorize markers
        max_id = max(1, count)
        vis = (np.clip(markers, 0, None).astype(np.float32) * (255.0 / (max_id + 1))).astype(np.uint8)
        preview = cv2.applyColorMap(vis, cv2.COLORMAP_TURBO)
        preview[markers <= 1] = 0
        if boundary is not None:
            preview[bnd_bin == 255] = [64, 64, 64]

        return {'markers': markers, 'preview': preview, 'count': count}


@vision_node(
    type_id='geo_grain_stats',
    label='Grain Population Stats',
    category='geology',
    icon='BarChart2',
    description=(
        "Computes population-level grain statistics from a watershed label map: "
        "count, area distribution, circularity, aspect ratio, grain/opaque surface fractions, "
        "and a grain-size histogram image."
    ),
    inputs=[
        {'id': 'markers',   'color': 'any',    'label': 'Markers (watershed)'},
        {'id': 'image',     'color': 'image',  'label': 'XPL Image (intensity)'},
        {'id': 'opaques',   'color': 'any',    'label': 'Opaque Mask (optional)'},
        {'id': 'um_per_px', 'color': 'scalar', 'label': 'µm/pixel (Calibration)'},
    ],
    outputs=[
        {'id': 'histogram',        'color': 'image',  'label': 'Size Histogram'},
        {'id': 'summary',          'color': 'any',    'label': 'Summary (text)'},
        {'id': 'count',            'color': 'scalar', 'label': 'Grain Count'},
        {'id': 'mean_area',        'color': 'scalar', 'label': 'Mean Area (px²)'},
        {'id': 'median_area',      'color': 'scalar', 'label': 'Median Area (px²)'},
        {'id': 'mean_area_um2',    'color': 'scalar', 'label': 'Mean Area (µm²)'},
        {'id': 'mean_dia_um',      'color': 'scalar', 'label': 'Mean Diameter (µm)'},
        {'id': 'mean_circularity', 'color': 'scalar', 'label': 'Mean Circularity'},
        {'id': 'grain_fraction',   'color': 'scalar', 'label': 'Grain Fraction (%)'},
        {'id': 'opaque_fraction',  'color': 'scalar', 'label': 'Opaque Fraction (%)'},
        {'id': 'regions',          'color': 'list',   'label': 'Regions (list)'},
    ],
    params=[
        {'id': 'min_area',   'label': 'Min Area (px)',  'type': 'int',   'default': 100,  'min': 1,    'max': 100000},
        {'id': 'hist_bins',  'label': 'Histogram Bins', 'type': 'int',   'default': 30,   'min': 5,    'max': 100},
        {'id': 'hist_color', 'label': 'Bar Color',      'type': 'color', 'default': '#4FC3F7'},
        {'id': 'um_per_px',  'label': 'µm / pixel',     'type': 'float', 'default': 1.0,  'min': 0.01, 'max': 1000.0, 'step': 0.1},
    ]
)
class GeoGrainStats(NodeProcessor):

    def _parse_color(self, hex_str, fallback=(79, 195, 247)):
        try:
            h = str(hex_str).lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (b, g, r)  # BGR
        except Exception:
            return fallback

    def process(self, inputs, params):
        markers_raw = inputs.get('markers')
        if markers_raw is None:
            return {}

        markers = markers_raw.astype(np.int32)
        image   = inputs.get('image')
        opaques = inputs.get('opaques')

        min_area  = int(params.get('min_area', 100))
        hist_bins = int(params.get('hist_bins', 30))
        bar_bgr   = self._parse_color(params.get('hist_color', '#4FC3F7'))
        um_px_input = inputs.get('um_per_px')
        um_per_px = float(um_px_input) if um_px_input is not None else float(params.get('um_per_px', 1.0))
        calibrated = um_per_px != 1.0
        um2_per_px2 = um_per_px ** 2
        unit_area = "µm²" if calibrated else "px²"
        unit_len  = "µm"  if calibrated else "px"

        h, w = markers.shape[:2]
        total_px = h * w

        # ── Opaque fraction ──────────────────────────────────────────────
        opaque_px = 0
        if opaques is not None:
            op = opaques if len(opaques.shape) == 2 else cv2.cvtColor(opaques, cv2.COLOR_BGR2GRAY)
            opaque_px = int(np.count_nonzero(op > 127))

        # ── Per-grain measurements ────────────────────────────────────────
        gray = None
        if image is not None:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()

        unique_labels = np.unique(markers)
        unique_labels = unique_labels[unique_labels > 1]  # skip bg (1) and unknown (0/-1)

        regions = []
        for label in unique_labels:
            mask = (markers == label).astype(np.uint8)
            area = int(np.count_nonzero(mask))
            if area < min_area:
                continue

            # Contour for shape descriptors
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            cnt = max(cnts, key=cv2.contourArea)
            perimeter = cv2.arcLength(cnt, True)

            circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0

            # Bounding rect → aspect ratio
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = float(bw) / bh if bh > 0 else 1.0

            # Centroid
            M = cv2.moments(cnt)
            cx = int(M['m10'] / M['m00']) if M['m00'] > 0 else x + bw // 2
            cy = int(M['m01'] / M['m00']) if M['m00'] > 0 else y + bh // 2

            rec = {
                'label':        int(label),
                'area':         area,
                'perimeter':    round(float(perimeter), 2),
                'circularity':  round(float(circularity), 4),
                'aspect_ratio': round(aspect_ratio, 4),
                'centroid_x':   cx,
                'centroid_y':   cy,
            }

            if gray is not None:
                px_vals = gray[mask == 1].astype(np.float32)
                if len(px_vals) > 0:
                    rec['mean_intensity'] = round(float(np.mean(px_vals)), 2)
                    rec['std_intensity']  = round(float(np.std(px_vals)),  2)

            regions.append(rec)

        count = len(regions)
        if count == 0:
            return {
                'histogram': np.zeros((300, 500, 3), dtype=np.uint8),
                'summary':   'No grains detected.',
                'count': 0, 'mean_area': 0, 'median_area': 0,
                'mean_area_um2': 0, 'mean_dia_um': 0,
                'mean_circularity': 0, 'grain_fraction': 0,
                'opaque_fraction': 0, 'regions': [],
            }

        areas         = np.array([r['area'] for r in regions], dtype=np.float32)
        circularities = np.array([r['circularity'] for r in regions], dtype=np.float32)
        aspects       = np.array([r['aspect_ratio'] for r in regions], dtype=np.float32)

        grain_px         = int(np.sum(areas))
        grain_fraction   = round(100.0 * grain_px / total_px, 2)
        opaque_fraction  = round(100.0 * opaque_px / total_px, 2)
        mean_circularity = float(np.mean(circularities))
        mean_aspect      = float(np.mean(aspects))

        # Convert to calibrated units for all display/output
        areas_cal     = areas * um2_per_px2
        mean_area_cal = float(np.mean(areas_cal))
        median_area_cal = float(np.median(areas_cal))
        std_area_cal  = float(np.std(areas_cal))
        mean_dia_cal  = round(2.0 * np.sqrt(mean_area_cal / np.pi), 2)

        # Keep raw px values only for internal use (grain_fraction, opaque_fraction)
        mean_area_um2 = round(mean_area_cal, 2)
        mean_dia_um   = mean_dia_cal

        # ── Histogram image ───────────────────────────────────────────────
        IW, IH = 600, 340
        hist_img = np.full((IH, IW, 3), 30, dtype=np.uint8)

        counts, bin_edges = np.histogram(areas_cal, bins=hist_bins)
        max_count = max(counts.max(), 1)
        bar_w = max(1, (IW - 80) // hist_bins)
        x0 = 50

        for i, (cnt_val, edge) in enumerate(zip(counts, bin_edges[:-1])):
            bar_h = int((cnt_val / max_count) * (IH - 70))
            bx = x0 + i * bar_w
            by = IH - 40 - bar_h
            cv2.rectangle(hist_img, (bx, by), (bx + bar_w - 2, IH - 40), bar_bgr, -1)

        # Axis labels
        cv2.putText(hist_img, f'Grain Size Distribution  (n={count})',
                    (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(hist_img, f'Area ({unit_area})',
                    (IW // 2 - 30, IH - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
        cv2.putText(hist_img, f'{bin_edges[0]:.2g}',
                    (x0, IH - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)
        cv2.putText(hist_img, f'{bin_edges[-1]:.2g}',
                    (x0 + hist_bins * bar_w - 30, IH - 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)

        # Stats inset
        lines = [
            f'Count : {count}',
            f'Mean  : {mean_area_cal:.2g} {unit_area}',
            f'Median: {median_area_cal:.2g} {unit_area}',
            f'StdDev: {std_area_cal:.2g} {unit_area}',
            f'Diam. : {mean_dia_cal:.2g} {unit_len}',
            f'Circ. : {mean_circularity:.3f}',
            f'AR    : {mean_aspect:.2f}',
            f'Grain : {grain_fraction:.1f}%',
            f'Opaque: {opaque_fraction:.1f}%',
        ]
        for i, line in enumerate(lines):
            cv2.putText(hist_img, line,
                        (IW - 175, 35 + i * 17),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 230, 200), 1)

        # ── Summary text ──────────────────────────────────────────────────
        calib_str = f"{um_per_px:.4g} µm/px" if calibrated else "non calibré — connecter Math Div ou saisir µm/pixel"
        summary = (
            f"Grain count: {count}\n"
            f"Calibration: {calib_str}\n"
            f"Mean area: {mean_area_cal:.3g} {unit_area} ± {std_area_cal:.3g}\n"
            f"Median area: {median_area_cal:.3g} {unit_area}\n"
            f"Mean diameter (equiv.): {mean_dia_cal:.3g} {unit_len}\n"
            f"Mean circularity: {mean_circularity:.3f}  (1=perfect circle)\n"
            f"Mean aspect ratio: {mean_aspect:.2f}\n"
            f"Grain fraction: {grain_fraction:.1f}%\n"
            f"Opaque fraction: {opaque_fraction:.1f}%\n"
            f"Image size: {w}×{h} px"
        )

        return {
            'histogram':        hist_img,
            'summary':          summary,
            'count':            count,
            'mean_area':        round(mean_area_cal, 4),
            'median_area':      round(median_area_cal, 4),
            'mean_area_um2':    mean_area_um2,
            'mean_dia_um':      mean_dia_um,
            'mean_circularity': round(mean_circularity, 4),
            'grain_fraction':   grain_fraction,
            'opaque_fraction':  opaque_fraction,
            'unit':             unit_area,
            'regions':          regions,
        }
