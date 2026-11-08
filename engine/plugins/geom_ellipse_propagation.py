import cv2
import numpy as np
from registry import vision_node, NodeProcessor

ZONE_KEYS = ('pith', 'mx', 'lpsc', 'endo', 'inner', 'outer')
REPORT_NAMES = {'pith': 'pith', 'mx': 'metaxylem', 'lpsc': 'lpsc', 'endo': 'endodermis',
                'inner': 'inner_cortex', 'outer': 'outer_cortex'}
DEFAULT_SNAP_TOLERANCE = 0.15


def snap_boundaries(priors, measured, tolerance, fixed=()):
    """Move each prior boundary (name -> rho) onto the nearest measured one within `tolerance`.

    Closest pairs are matched first, each measured boundary is used once, fixed names never
    move, and a snap that would break the inner-to-outer order of the priors is refused.
    Returns (snapped dict, measured-flag dict); inputs are not modified.
    """
    order = sorted(priors, key=priors.get)
    cand = [float(m) for m in (measured or []) if m is not None and np.isfinite(float(m))]
    pairs = sorted((abs(cand[j] - priors[n]), n, j) for n in order if n not in fixed
                   for j in range(len(cand)) if abs(cand[j] - priors[n]) <= tolerance)
    snapped, flags, used = dict(priors), {n: False for n in priors}, set()
    for _, name, j in pairs:
        if flags[name] or j in used:
            continue
        trial = {**snapped, name: cand[j]}
        values = [trial[n] for n in order]
        if all(lo < hi for lo, hi in zip(values, values[1:])):
            snapped, flags[name] = trial, True
            used.add(j)
    return snapped, flags


def _binary(m, shape=None):
    if m is None:
        return None
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if shape is not None and m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


@vision_node(
    type_id='geom_ellipse_propagation',
    label='Predictive Ellipse Propagation',
    category='geometry',
    icon='Maximize2',
    description=(
        "Predictive tissue zoning by multi-stage geometric propagation anchored on metaxylem.\n\n"
        "1. Fits an anisotropic enclosing ellipse to the outer envelope (convex hull) of metaxylem vessels.\n"
        "2. Extracts invariant organ parameters: physiological center (cx, cy), cut tilt orientation (angle), "
        "and eccentricity/aspect ratio (a/b) invariant to oblique sectioning.\n"
        "3. Propagates this geometric shell inwards (pith) and outwards in calibrated allometric steps:\n"
        "   - Pith (Moelle centrale): inward contraction\n"
        "   - Vascular cylinder & metaxylem ring\n"
        "   - Large Peripheral Stele Cells (LPSC mantle)\n"
        "   - Endodermis (outer stele boundary)\n"
        "   - Inner & Outer Cortex\n"
        "   - Rhizodermis / Exodermis (outer root surface)\n"
        "4. Auto-calibrates expansion ratios when an outer section boundary is supplied, scaling all layers proportionally."
    ),
    inputs=[
        {'id': 'landmarks', 'color': 'mask', 'label': 'Metaxylem Mask (Anchor)'},
        {'id': 'boundary', 'color': 'mask', 'label': 'Section Boundary (opt.)'},
        {'id': 'labels', 'color': 'markers', 'label': 'Cell Labels (opt.)'},
        {'id': 'image', 'color': 'image', 'label': 'Background Image (opt.)'},
        {'id': 'boundaries', 'color': 'list', 'label': 'Measured Boundaries ρ (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Propagation Overlay'},
        {'id': 'zones', 'color': 'markers', 'label': 'Predicted Zone Map'},
        {'id': 'rho_map', 'color': 'image', 'label': 'Elliptical Rho Field'},
        {'id': 'rho', 'color': 'any', 'label': 'ρ Field (float)'},
        {'id': 'pith_mask', 'color': 'mask', 'label': 'Pith Mask'},
        {'id': 'vascular_mask', 'color': 'mask', 'label': 'Vascular Mask'},
        {'id': 'lpsc_mask', 'color': 'mask', 'label': 'LPSC Mask'},
        {'id': 'endodermis_mask', 'color': 'mask', 'label': 'Endodermis Mask'},
        {'id': 'stele_mask', 'color': 'mask', 'label': 'Stele Mask'},
        {'id': 'inner_cortex_mask', 'color': 'mask', 'label': 'Inner Cortex Mask'},
        {'id': 'outer_cortex_mask', 'color': 'mask', 'label': 'Outer Cortex Mask'},
        {'id': 'rhizodermis_mask', 'color': 'mask', 'label': 'Rhizodermis Mask'},
        {'id': 'ellipse_box', 'color': 'dict', 'label': 'Base Ellipse Box'},
        {'id': 'report', 'color': 'dict', 'label': 'Propagation Report'},
    ],
    params=[
        {'id': 'auto_calibrate', 'label': 'Auto-Calibrate by Section', 'type': 'bool', 'default': True},
        {'id': 'scale_pith', 'label': 'Pith Scale', 'type': 'float', 'default': 0.65, 'min': 0.2, 'max': 1.0, 'step': 0.02},
        {'id': 'scale_mx', 'label': 'Metaxylem Scale', 'type': 'float', 'default': 1.00, 'min': 0.8, 'max': 1.2, 'step': 0.02},
        {'id': 'scale_lpsc', 'label': 'LPSC Scale', 'type': 'float', 'default': 1.18, 'min': 1.0, 'max': 1.5, 'step': 0.02},
        {'id': 'scale_endo', 'label': 'Endodermis Scale', 'type': 'float', 'default': 1.32, 'min': 1.1, 'max': 1.6, 'step': 0.02},
        {'id': 'scale_inner_cortex', 'label': 'Inner Cortex Scale', 'type': 'float', 'default': 1.88, 'min': 1.4, 'max': 2.3, 'step': 0.05},
        {'id': 'scale_outer_cortex', 'label': 'Outer Cortex Scale', 'type': 'float', 'default': 2.45, 'min': 1.8, 'max': 3.0, 'step': 0.05},
        {'id': 'scale_rhizodermis', 'label': 'Rhizodermis Scale', 'type': 'float', 'default': 2.80, 'min': 2.0, 'max': 4.0, 'step': 0.05},
        {'id': 'snap_tolerance', 'label': 'Snap to Measured Boundary (Δρ)', 'type': 'float',
         'default': DEFAULT_SNAP_TOLERANCE, 'min': 0.0, 'max': 1.0, 'step': 0.01},
        {'id': 'show_shells', 'label': 'Draw Elliptical Shells', 'type': 'bool', 'default': True},
        {'id': 'shell_thickness', 'label': 'Shell Thickness', 'type': 'int', 'default': 2, 'min': 1, 'max': 5},
    ],
)
class GeomEllipsePropagationNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {
            'main': None, 'zones': None, 'rho_map': None, 'rho': None, 'pith_mask': None,
            'vascular_mask': None, 'lpsc_mask': None, 'endodermis_mask': None,
            'stele_mask': None, 'inner_cortex_mask': None, 'outer_cortex_mask': None,
            'rhizodermis_mask': None, 'ellipse_box': {}, 'report': {}
        }
        lm_in = inputs.get('landmarks')
        if lm_in is None:
            return empty

        # Shape inference
        if isinstance(lm_in, np.ndarray):
            h, w = lm_in.shape[:2]
        elif 'image' in inputs and isinstance(inputs['image'], np.ndarray):
            h, w = inputs['image'].shape[:2]
        elif 'boundary' in inputs and isinstance(inputs['boundary'], np.ndarray):
            h, w = inputs['boundary'].shape[:2]
        else:
            return empty

        mx_mask = _binary(lm_in, (h, w))
        section = _binary(inputs.get('boundary'), (h, w))
        labels = inputs.get('labels')
        labels = labels.astype(np.int32) if isinstance(labels, np.ndarray) and labels.shape == (h, w) else None

        bg_img = inputs.get('image')
        if bg_img is not None and isinstance(bg_img, np.ndarray):
            if bg_img.shape[:2] != (h, w):
                bg_img = cv2.resize(bg_img, (w, h))
            if bg_img.ndim == 2:
                bg_img = cv2.cvtColor(bg_img, cv2.COLOR_GRAY2BGR)
            vis = bg_img.copy()
        else:
            vis = np.zeros((h, w, 3), dtype=np.uint8)
            vis[:] = (45, 45, 45)

        # 1. Fit outer envelope ellipse on metaxylem
        cnts, _ = cv2.findContours(mx_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            return empty

        all_pts = np.vstack(cnts)
        if len(all_pts) < 5:
            return empty

        hull = cv2.convexHull(all_pts)
        if len(hull) < 5:
            # Fallback minAreaRect
            r = cv2.minAreaRect(all_pts)
            cx, cy = r[0]
            w_box, h_box = r[1]
            angle = r[2]
        else:
            ellipse_box = cv2.fitEllipse(hull)
            (cx, cy), (w_box, h_box), angle = ellipse_box

        # Ensure sensible axis lengths
        w_box = max(float(w_box), 10.0)
        h_box = max(float(h_box), 10.0)
        a = w_box / 2.0
        b = h_box / 2.0
        aspect_ratio = max(a, b) / max(min(a, b), 1e-6)

        # 2. Scale calibration
        auto_calib = bool(params.get('auto_calibrate', True))
        s_pith = float(params.get('scale_pith', 0.65))
        s_mx = float(params.get('scale_mx', 1.00))
        s_lpsc = float(params.get('scale_lpsc', 1.18))
        s_endo = float(params.get('scale_endo', 1.32))
        s_inner = float(params.get('scale_inner_cortex', 1.88))
        s_outer = float(params.get('scale_outer_cortex', 2.45))
        s_rhizo = float(params.get('scale_rhizodermis', 2.80))

        s_sec_calib = s_rhizo
        if auto_calib and section is not None and np.any(section):
            r_sec = float(np.sqrt(section.sum() / np.pi))
            r_mx = float(np.sqrt(a * b))
            if r_mx > 5.0:
                s_sec_calib = r_sec / r_mx
                s_pith = 0.23 * s_sec_calib
                s_mx = 0.36 * s_sec_calib
                s_lpsc = 0.42 * s_sec_calib
                s_endo = 0.47 * s_sec_calib
                s_inner = 0.67 * s_sec_calib
                s_outer = 0.88 * s_sec_calib
                s_rhizo = 1.00 * s_sec_calib

        # 2b. Measured boundaries (e.g. Profile Zoning of cell size along rho) replace priors
        priors = {'pith': s_pith, 'mx': s_mx, 'lpsc': s_lpsc, 'endo': s_endo,
                  'inner': s_inner, 'outer': s_outer}
        snapped, measured = snap_boundaries(
            priors, inputs.get('boundaries'),
            float(params.get('snap_tolerance', DEFAULT_SNAP_TOLERANCE)), fixed=('mx',))
        s_pith, s_lpsc, s_endo = snapped['pith'], snapped['lpsc'], snapped['endo']
        s_inner, s_outer = snapped['inner'], snapped['outer']

        # 3. Vectorized elliptical distance field rho(x, y)
        Y, X = np.ogrid[:h, :w]
        dx = X - cx
        dy = Y - cy
        th_rad = np.deg2rad(angle)
        cos_t, sin_t = np.cos(th_rad), np.sin(th_rad)
        x_rot = cos_t * dx + sin_t * dy
        y_rot = -sin_t * dx + cos_t * dy
        rho_map = np.sqrt((x_rot / a)**2 + (y_rot / b)**2)

        # 4. Generate anatomical masks
        m_pith = (rho_map <= s_pith)
        m_vasc = (rho_map > s_pith) & (rho_map <= s_mx)
        m_lpsc = (rho_map > s_mx) & (rho_map <= s_lpsc)
        m_endo = (rho_map > s_lpsc) & (rho_map <= s_endo)
        m_stele = (rho_map <= s_endo)
        m_inner = (rho_map > s_endo) & (rho_map <= s_inner)
        m_outer = (rho_map > s_inner) & (rho_map <= s_outer)
        m_rhizo = (rho_map > s_outer) & (rho_map <= s_rhizo)

        if section is not None:
            # Constrain outer layers within the section boundary
            m_outer = m_outer & section
            m_rhizo = m_rhizo & section

        # Integer zone map
        zone_map = np.zeros((h, w), dtype=np.int32)
        zone_map[m_pith] = 1
        zone_map[m_vasc] = 2
        zone_map[m_lpsc] = 3
        zone_map[m_endo] = 4
        zone_map[m_inner] = 5
        zone_map[m_outer] = 6
        zone_map[m_rhizo] = 7

        # 5. Cell Classification (if cell label map provided)
        cell_counts = {
            'pith': 0, 'vascular': 0, 'lpsc': 0, 'endodermis': 0,
            'inner_cortex': 0, 'outer_cortex': 0, 'rhizodermis': 0
        }
        if labels is not None:
            from skimage import measure
            props = measure.regionprops(labels)
            for p in props:
                cy_p, cx_p = p.centroid
                dx_p, dy_p = cx_p - cx, cy_p - cy
                xr = cos_t * dx_p + sin_t * dy_p
                yr = -sin_t * dx_p + cos_t * dy_p
                r_cell = np.sqrt((xr / a)**2 + (yr / b)**2)

                c_mask = (labels == p.label)
                if np.any(c_mask & mx_mask):
                    cell_counts['vascular'] += 1
                elif r_cell <= s_pith:
                    cell_counts['pith'] += 1
                elif r_cell <= s_mx:
                    cell_counts['vascular'] += 1
                elif r_cell <= s_lpsc:
                    cell_counts['lpsc'] += 1
                elif r_cell <= s_endo:
                    cell_counts['endodermis'] += 1
                elif r_cell <= s_inner:
                    cell_counts['inner_cortex'] += 1
                elif r_cell <= s_outer:
                    cell_counts['outer_cortex'] += 1
                elif r_cell <= s_rhizo * 1.05:
                    cell_counts['rhizodermis'] += 1
                else:
                    cell_counts['outer_cortex'] += 1

        # 6. Overlay rendering
        TISSUE_COLORS = [
            (m_pith, (232, 123, 164), 0.75),    # Pith (pink)
            (m_vasc, (0, 161, 237), 0.70),      # Vascular / Yellow
            (m_lpsc, (6, 119, 217), 0.85),      # LPSC (amber)
            (m_endo, (194, 87, 126), 0.90),     # Endodermis (purple)
            (m_inner, (27, 175, 122), 0.75),    # Inner cortex (green)
            (m_outer, (52, 104, 235), 0.75),    # Outer cortex (orange)
            (m_rhizo, (214, 120, 42), 0.85),    # Rhizodermis (blue)
        ]
        for m, col, alpha in TISSUE_COLORS:
            if np.any(m):
                vis[m] = ((1 - alpha) * vis[m] + alpha * np.array(col)).astype(np.uint8)

        # Highlight segmented metaxylem lumina in deep green
        vis[mx_mask] = (0, 131, 0)

        # 7. Draw propagating elliptical shells
        show_shells = bool(params.get('show_shells', True))
        thick = int(params.get('shell_thickness', 2))
        if show_shells:
            # Base metaxylem hull
            cv2.drawContours(vis, [hull], -1, (0, 255, 0), 1, cv2.LINE_AA)
            SHELL_STYLES = [
                (s_pith, (240, 160, 200), thick, 'Pith'),
                (s_mx, (0, 255, 0), thick + 1, 'Metaxylem Anchor'),
                (s_lpsc, (0, 210, 255), thick, 'LPSC'),
                (s_endo, (255, 120, 255), thick + 1, 'Endodermis'),
                (s_inner, (120, 255, 150), thick, 'Inner Cortex'),
                (s_outer, (100, 160, 255), thick, 'Outer Cortex'),
                (s_rhizo, (255, 200, 80), thick + 1, 'Rhizodermis'),
            ]
            for s, col, th_line, _ in SHELL_STYLES:
                box_s = ((float(cx), float(cy)), (float(w_box * s), float(h_box * s)), float(angle))
                cv2.ellipse(vis, box_s, col, th_line, cv2.LINE_AA)

        # 8. Rho distance map visualization
        rho_norm = (np.clip(rho_map / max(s_rhizo, 1e-3), 0.0, 1.0) * 255).astype(np.uint8)
        rho_vis = cv2.applyColorMap(rho_norm, cv2.COLORMAP_TURBO)
        if section is not None:
            rho_vis[~section] = 0

        # Stats dictionary
        stats = {
            'center_x': float(cx),
            'center_y': float(cy),
            'major_axis': float(max(a, b)),
            'minor_axis': float(min(a, b)),
            'aspect_ratio': float(aspect_ratio),
            'tilt_angle_deg': float(angle),
            'scale_pith': float(s_pith),
            'scale_metaxylem': float(s_mx),
            'scale_lpsc': float(s_lpsc),
            'scale_endodermis': float(s_endo),
            'scale_inner_cortex': float(s_inner),
            'scale_outer_cortex': float(s_outer),
            'scale_rhizodermis': float(s_rhizo),
            'calibrated_section_ratio': float(s_sec_calib),
            **{f'measured_{REPORT_NAMES[k]}': bool(measured[k]) for k in ZONE_KEYS},
            'measured_boundaries': int(sum(measured.values())),
            **{f'cells_{k}': int(v) for k, v in cell_counts.items()}
        }

        ellipse_box_dict = {
            'cx': float(cx), 'cy': float(cy),
            'width': float(w_box), 'height': float(h_box),
            'angle': float(angle)
        }

        def to_u8(m): return (m.astype(np.uint8) * 255)

        return {
            'main': vis,
            'zones': zone_map,
            'rho_map': rho_vis,
            'rho': rho_map.astype(np.float32),
            'pith_mask': to_u8(m_pith),
            'vascular_mask': to_u8(m_vasc),
            'lpsc_mask': to_u8(m_lpsc),
            'endodermis_mask': to_u8(m_endo),
            'stele_mask': to_u8(m_stele),
            'inner_cortex_mask': to_u8(m_inner),
            'outer_cortex_mask': to_u8(m_outer),
            'rhizodermis_mask': to_u8(m_rhizo),
            'ellipse_box': ellipse_box_dict,
            'report': stats,
        }
