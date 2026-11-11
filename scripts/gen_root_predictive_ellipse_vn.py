"""Generate public/templates/root_predictive_ellipse_zoning.vn

Predictive Root Cross-Section Zoning by Multi-Stage Geometric Propagation
Anchored on the Metaxylem Envelope.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'tests'))
os.chdir(REPO)
import vn_headless as H  # noqa: E402

H.load_plugins()

NODES, EDGES, FRAMES = [], [], []
DX, DY = 250, 270


def frame(fid, title, x, y, cols, rows, color):
    w, h = cols * DX + 60, rows * DY + 90
    FRAMES.append({
        'id': fid, 'type': 'canvas_frame', 'position': {'x': x, 'y': y},
        'style': {'width': w, 'height': h, 'zIndex': -1},
        'data': {'label': 'Frame', 'params': {'title': title, 'color_index': color}},
        'width': w, 'height': h,
    })
    return (x + 30, y + 70, color)


def node(nid, type_, origin, col, row, params=None, note=None):
    sch = H.schema(type_)
    assert sch is not None, f'unknown type {type_}'
    ox, oy, color = origin
    p = dict(params or {})
    p['color_index'] = color
    if note:
        p['node_note'] = note
    NODES.append({'id': nid, 'type': type_, 'position': {'x': ox + col * DX, 'y': oy + row * DY},
                  'data': {'label': sch['label'], 'params': p}})


def _port_color(type_, port, side):
    specs = H.schema(type_)['inputs' if side == 'in' else 'outputs']
    return next((s['color'] for s in specs if s['id'] == port), None)


def _type_of(nid):
    return next(n['type'] for n in NODES if n['id'] == nid)


def edge(src, sport, tgt, tport):
    sc = _port_color(_type_of(src), sport, 'out')
    tc = _port_color(_type_of(tgt), tport, 'in')
    EDGES.append({'id': f'e{len(EDGES) + 1}', 'source': src, 'target': tgt,
                  'sourceHandle': f'{sc}__{sport}', 'targetHandle': f'{tc}__{tport}'})


# ── Enum indices ─────────────────────────────────────────────────────────────
OPEN, CLOSE, DILATE, ERODE = 0, 1, 5, 6
ELLIPSE = 2
OTSU, TRIANGLE_INV = 2, 6
OR, SUB, AND = 0, 1, 2
KEEP, REMOVE = 0, 1
BY_PEAK = 1
ABOVE_ONLY = 1
FRAME_GAP = 60
ROW_Y = [0, 1240, 2480]


def row_frames(row, specs):
    x, out = 0, {}
    for fid, title, cols, rows in specs:
        out[fid] = frame(fid, title, x, ROW_Y[row], cols, rows, len(FRAMES) % 8)
        x += cols * DX + 60 + FRAME_GAP
    return out


F = row_frames(0, [('frame-1', 'Step 1: Input & Scale Bar', 2, 2),
                   ('frame-2', 'Step 2: Section', 4, 2),
                   ('frame-3', 'Step 3: Cell Walls', 1, 2),
                   ('frame-4', 'Step 4: Cells Segmentation', 3, 2),
                   ('frame-5', 'Step 5: Radial Prior & Center', 2, 4)])
F.update(row_frames(1, [('frame-6', 'Step 6: Stele & Tissue Priors', 5, 3),
                        ('frame-7', 'Step 7: Metaxylem Anchor Detection', 5, 4)]))
F.update(row_frames(2, [('frame-8', 'Step 8: Predictive Ellipse Propagation', 4, 4),
                        ('frame-9', 'Step 9: Reconstruction & Report', 5, 4)]))

# ── Step 1 ───────────────────────────────────────────────────────────────────
f = F['frame-1']
node('src', 'input_image', f, 0, 0, {'path': 'samples/root.png'},
     'Root cross-section image (drawing or photo).')
node('scale', 'sci_scale_bar_detect', f, 0, 1,
     {'source': 0, 'bar_length': 500.0, 'unit': 0, 'fallback_px_per_mm': 118.0},
     'Scale calibration: detected or fallback (px/mm).')
node('gray', 'filter_gray', f, 1, 0)
node('pol', 'filter_auto_polarity', f, 1, 1, {'target': 0, 'method': BY_PEAK},
     'Bright backdrop, dark walls, bright lumens.')
edge('src', 'main', 'gray', 'image')
edge('src', 'main', 'scale', 'image')
edge('gray', 'main', 'pol', 'image')

# ── Step 2: section ──────────────────────────────────────────────────────────
f = F['frame-2']
node('sec_blur', 'filter_blur', f, 0, 0, {'method': 0, 'size': 15, 'sigma': 0})
node('sec_thr', 'feat_threshold_adv', f, 1, 0, {'mode': TRIANGLE_INV, 'offset': -30},
     'Darker than backdrop is tissue.')
node('sec_close', 'feat_morphology_adv', f, 2, 0, {'operation': CLOSE, 'shape': ELLIPSE, 'size': 31, 'iterations': 1})
node('sec_fill', 'fill_holes', f, 3, 0, {'method': 0})
node('sec_open', 'feat_morphology_adv', f, 0, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 25, 'iterations': 2})
node('roi', 'util_roi_polygon', f, 1, 1, {'points': '[]', 'filled': True})
node('sec_and', 'mask_operations', f, 2, 1, {'operation': AND})
node('section', 'mask_keep_largest', f, 3, 1, {'count': 1}, 'ROOT SECTION')
edge('pol', 'main', 'sec_blur', 'image')
edge('sec_blur', 'main', 'sec_thr', 'image')
edge('sec_thr', 'mask', 'sec_close', 'mask')
edge('sec_close', 'mask', 'sec_fill', 'mask')
edge('sec_fill', 'main', 'sec_open', 'mask')
edge('src', 'main', 'roi', 'image')
edge('sec_open', 'mask', 'sec_and', 'mask_a')
edge('roi', 'mask', 'sec_and', 'mask_b')
edge('sec_and', 'mask', 'section', 'mask')

# ── Step 3: wall map ─────────────────────────────────────────────────────────
f = F['frame-3']
node('ridge', 'filter_ridge', f, 0, 0,
     {'method': 0, 'polarity': 0, 'sigma_min': 1.0, 'sigma_max': 4.0, 'n_scales': 4,
      'norm_radius': 15, 'floor_pct': 40},
     'Cell walls = dark lines, multiscale ridge filter.')
edge('pol', 'main', 'ridge', 'image')
edge('section', 'mask', 'ridge', 'mask')

# ── Step 4: cells ────────────────────────────────────────────────────────────
f = F['frame-4']
node('tess', 'seg_cell_tessellation', f, 0, 0,
     {'smooth': 1.0, 'depth': 0.3, 'wall_level': 0.7, 'wall_ratio': 3.0, 'min_closure': 0.8,
      'min_solidity': 0.85, 'min_area': 15, 'max_area': 0})
edge('ridge', 'ridge', 'tess', 'walls')
edge('section', 'mask', 'tess', 'mask')
node('walls_a', 'cv_adaptive_threshold', f, 1, 0, {'block_size': 31, 'c': -2, 'adaptive_method': 1, 'invert': True})
node('med3', 'filter_blur', f, 1, 1, {'method': 1, 'size': 3, 'sigma': 0})
node('walls_b', 'cv_adaptive_threshold', f, 2, 1, {'block_size': 31, 'c': 0, 'adaptive_method': 1, 'invert': False})
node('cells', 'seg_cells_from_walls', f, 2, 0,
     {'min_area': 12, 'max_area': 6000, 'min_solidity': 0.82, 'overlap': 0.10, 'footprint': 2,
      'min_contrast': 10},
     'Segmented individual cell bodies.')
edge('ridge', 'main', 'walls_a', 'image')
edge('pol', 'main', 'med3', 'image')
edge('med3', 'main', 'walls_b', 'image')
edge('walls_a', 'main', 'cells', 'walls')
edge('walls_b', 'main', 'cells', 'walls_2')
edge('section', 'mask', 'cells', 'region')
edge('tess', 'resolved_labels', 'cells', 'existing')
edge('pol', 'main', 'cells', 'image')

# ── Step 5: radial position & zoning ─────────────────────────────────────────
f = F['frame-5']
node('radial0', 'geom_radial_coords', f, 0, 0, {'smooth': 3.0, 'ignore_border': True})
node('zoning0', 'sci_profile_zoning', f, 1, 0,
     {'position_key': 'rho', 'value_key': 'radius', 'weight_key': 'score', 'log_values': True,
      'zones': 0, 'max_zones': 6, 'outlier_mad': 3.0, 'outlier_side': ABOVE_ONLY,
      'min_items': 12, 'core_rule': 1, 'n_boot': 0, 'seed': 0})
node('radial', 'geom_radial_coords', f, 0, 2, {'smooth': 3.0, 'ignore_border': True})
node('zoning', 'sci_profile_zoning', f, 1, 2,
     {'position_key': 'rho', 'value_key': 'radius', 'weight_key': 'score', 'log_values': True,
      'zones': 0, 'max_zones': 6, 'outlier_mad': 3.0, 'outlier_side': ABOVE_ONLY,
      'min_items': 12, 'core_rule': 1, 'n_boot': 50, 'seed': 0})
edge('section', 'mask', 'radial0', 'mask')
edge('tess', 'cells', 'radial0', 'items')
edge('radial0', 'items', 'zoning0', 'items')
edge('radial0', 'position', 'zoning0', 'position')
edge('section', 'mask', 'radial', 'mask')
edge('zoning0', 'core', 'radial', 'center_mask')
edge('tess', 'cells', 'radial', 'items')
edge('radial', 'items', 'zoning', 'items')
edge('radial', 'position', 'zoning', 'position')

# ── Step 6: tissues & walls ──────────────────────────────────────────────────
f = F['frame-6']
node('ring', 'geom_ring_contour', f, 1, 1,
     {'side': 0, 'sigma': 8.0, 'band_low': 0.5, 'band_high': 1.5, 'max_step': 1, 'passes': 6})
edge('pol', 'main', 'ring', 'image')
edge('zoning', 'core', 'ring', 'prior')
edge('section', 'mask', 'ring', 'region')
node('stele', 'mask_operations', f, 0, 0, {'operation': AND})
node('cortex', 'mask_operations', f, 1, 0, {'operation': SUB})
edge('ring', 'mask', 'stele', 'mask_a')
edge('section', 'mask', 'stele', 'mask_b')
edge('section', 'mask', 'cortex', 'mask_a')
edge('stele', 'mask', 'cortex', 'mask_b')

node('walls', 'cv_adaptive_threshold', f, 0, 1, {'block_size': 41, 'c': 1, 'adaptive_method': 1, 'invert': False})
edge('pol', 'main', 'walls', 'image')

# ── Step 7: metaxylem ────────────────────────────────────────────────────────
f = F['frame-7']
node('lum_sub', 'mask_operations', f, 0, 0, {'operation': SUB})
node('lumens', 'feat_morphology_adv', f, 1, 0, {'operation': OPEN, 'shape': ELLIPSE, 'size': 5, 'iterations': 1})
node('lum_cc', 'sci_connected_components', f, 2, 0,
     {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True, 'show_cross': False})
node('lum_med', 'sci_stats', f, 3, 0)
node('mx_lum', 'cv_adaptive_threshold', f, 4, 0, {'block_size': 71, 'c': -8, 'adaptive_method': 1, 'invert': True})
node('mx_and', 'mask_operations', f, 0, 1, {'operation': AND})
node('mx_open', 'feat_morphology_adv', f, 1, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 7, 'iterations': 1})
node('st_lum2', 'mask_operations', f, 2, 1, {'operation': AND})
node('st_lum_fill', 'fill_holes', f, 3, 1, {'method': 0})
node('vessels', 'mask_select_by_marker', f, 4, 1, {'mode': KEEP, 'connectivity': 0})
node('mx_cc', 'sci_connected_components', f, 0, 2,
     {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True, 'show_cross': False})
node('mx_floor', 'math_expr', f, 1, 2, {'expression': '2 * a'})
node('mx_break', 'list_natural_break', f, 2, 2, {'log_scale': True, 'min_value': 0, 'min_ratio': 1.5})
node('metaxylem', 'filter_blob_filter', f, 3, 2, {'min_area': 1000, 'max_area': 0, 'circ_min': 0.3, 'connectivity': 4},
     'METAXYLEM ANCHOR (6 VESSELS)')
edge('section', 'mask', 'lum_sub', 'mask_a')
edge('walls', 'main', 'lum_sub', 'mask_b')
edge('lum_sub', 'mask', 'lumens', 'mask')
edge('lumens', 'mask', 'lum_cc', 'image')
edge('lum_cc', 'areas', 'lum_med', 'data_list')
edge('pol', 'main', 'mx_lum', 'image')
edge('mx_lum', 'main', 'mx_and', 'mask_a')
edge('stele', 'mask', 'mx_and', 'mask_b')
edge('mx_and', 'mask', 'mx_open', 'mask')
edge('lumens', 'mask', 'st_lum2', 'mask_a')
edge('stele', 'mask', 'st_lum2', 'mask_b')
edge('st_lum2', 'mask', 'st_lum_fill', 'mask')
edge('st_lum_fill', 'main', 'vessels', 'mask')
node('mx_tess', 'mask_operations', f, 2, 3, {'operation': AND})
edge('cells', 'interiors', 'mx_tess', 'mask_a')
edge('stele', 'mask', 'mx_tess', 'mask_b')
node('mx_pts', 'points_to_mask', f, 0, 3, {'radius': 2})
edge('zoning', 'outliers', 'mx_pts', 'points')
edge('src', 'main', 'mx_pts', 'reference')
node('mx_sel', 'mask_select_by_marker', f, 3, 3, {'mode': KEEP, 'connectivity': 0})
edge('mx_tess', 'mask', 'mx_sel', 'mask')
edge('mx_pts', 'mask', 'mx_sel', 'marker')
node('mx_mark', 'mask_operations', f, 1, 3, {'operation': OR})
edge('mx_open', 'mask', 'mx_mark', 'mask_a')
edge('mx_pts', 'mask', 'mx_mark', 'mask_b')
edge('mx_mark', 'mask', 'vessels', 'marker')
node('mx_cand', 'mask_operations', f, 4, 3, {'operation': OR})
edge('vessels', 'mask', 'mx_cand', 'mask_a')
edge('mx_sel', 'mask', 'mx_cand', 'mask_b')
edge('mx_cand', 'mask', 'mx_cc', 'image')
edge('lum_med', 'median', 'mx_floor', '0_med')
edge('mx_cc', 'areas', 'mx_break', 'values')
edge('mx_floor', 'result', 'mx_break', 'min_value')
edge('mx_cand', 'mask', 'metaxylem', 'mask')
edge('mx_break', 'threshold', 'metaxylem', 'min_area')

# ── Step 8: Predictive Ellipse Propagation ───────────────────────────────────
f = F['frame-8']
node('ellipse_prop', 'geom_ellipse_propagation', f, 0, 0,
     {'auto_calibrate': True,
      'scale_pith': 0.65,
      'scale_mx': 1.00,
      'scale_lpsc': 1.18,
      'scale_endo': 1.32,
      'scale_inner_cortex': 1.88,
      'scale_outer_cortex': 2.45,
      'scale_rhizodermis': 2.80,
      'show_shells': True,
      'shell_thickness': 2},
     'PREDICTIVE ELLIPSE PROPAGATION: Fits outer envelope to metaxylem anchor, '
     'estimates tilt & eccentricity, then propagates concentric allometric shells.')
edge('metaxylem', 'mask', 'ellipse_prop', 'landmarks')
edge('section', 'mask', 'ellipse_prop', 'boundary')
edge('cells', 'labels', 'ellipse_prop', 'labels')
edge('cells', 'main', 'ellipse_prop', 'image')

node('ol_st_pred', 'mask_outline', f, 1, 0, {'thickness': 3}, 'Predicted Stele Boundary')
edge('ellipse_prop', 'stele_mask', 'ol_st_pred', 'mask')

ZONE_NAMES = [
    'Pith', 'Vascular cylinder', 'Large Peripheral Stele Cells',
    'Endodermis', 'Inner cortex', 'Outer cortex', 'Rhizodermis / Exodermis'
]
node('zones_all', 'mask_to_zones', f, 0, 1, {'names': ', '.join(ZONE_NAMES)})
for idx, port in enumerate([
    'pith_mask', 'vascular_mask', 'lpsc_mask', 'endodermis_mask',
    'inner_cortex_mask', 'outer_cortex_mask', 'rhizodermis_mask'
], start=1):
    edge('ellipse_prop', port, 'zones_all', f'mask_{idx}')

# ── Step 9: Reconstruction & Report ──────────────────────────────────────────
f = F['frame-9']
node('report', 'dict_report_panel', f, 0, 0,
     {'title': 'Predictive Ellipse Phenotyping Report',
      'groups': 'Anchor Metaxylem Ellipse: center_x, center_y, major_axis, minor_axis, aspect_ratio, tilt_angle_deg | '
                'Allometric Scales: calibrated_section_ratio, scale_pith, scale_metaxylem, scale_lpsc, scale_endodermis, scale_inner_cortex, scale_outer_cortex, scale_rhizodermis | '
                'Cell Partitioning: cells_pith, cells_vascular, cells_lpsc, cells_endodermis, cells_inner_cortex, cells_outer_cortex, cells_rhizodermis',
      'digits': 3})
edge('ellipse_prop', 'report', 'report', 'dict')

node('compose', 'util_compose', f, 0, 1, {'mode': 0, 'gap': 4},
     'Side-by-side: Original image | Predictive elliptical propagation.')
edge('src', 'main', 'compose', 'image_a')
edge('ellipse_prop', 'main', 'compose', 'image_b')

LEGEND = [
    ('Metaxylem Anchor (Lumina)', '#008300'),
    ('Pith (Moelle)', '#e87ba4'),
    ('Vascular Cylinder', '#00a1ed'),
    ('Large Peripheral Stele Cells', '#d97706'),
    ('Endodermis Monolayer', '#c2577e'),
    ('Inner Cortex', '#1baf7a'),
    ('Outer Cortex', '#eb6834'),
    ('Rhizodermis / Exodermis', '#2a78d6'),
    ('Propagated Elliptical Shells', '#00e5ff'),
]
node('legend', 'image_legend', f, 0, 2,
     {'entries': '\n'.join(f'{l}:{c}' for l, c in LEGEND),
      'position': 'top-left', 'font_scale': 0.85, 'swatch_size': 24,
      'bg_alpha': 0.82, 'padding': 12})
edge('compose', 'main', 'legend', 'image')

node('display', 'output_display', f, 1, 2)
edge('legend', 'main', 'display', 'main')

# Publication Figure Node with exact anatomical styling, geometric completion & predictive accounting
node('pub_fig', 'draw_root_publication', f, 0, 3,
     {'canvas_mode': 'clean_white', 'zone_opacity': 0.32, 'cell_opacity': 0.90,
      'pt_to_px': 1.33, 'complete_steles': True, 'hatch_lacunae': True,
      'lacunae_min_area': 25, 'draw_legend': True, 'draw_scale_bar': True,
      'scale_bar_um': 200, 'pixel_size_um': 0.50})
edge('cells', 'main', 'pub_fig', 'image')
edge('cells', 'labels', 'pub_fig', 'labels')
edge('section', 'mask', 'pub_fig', 'boundary')
edge('metaxylem', 'mask', 'pub_fig', 'landmarks')
edge('ellipse_prop', 'pith_mask', 'pub_fig', 'pith_mask')
edge('ellipse_prop', 'vascular_mask', 'pub_fig', 'vascular_mask')
edge('ellipse_prop', 'endodermis_mask', 'pub_fig', 'endodermis_mask')
edge('ellipse_prop', 'inner_cortex_mask', 'pub_fig', 'inner_cortex_mask')
edge('ellipse_prop', 'outer_cortex_mask', 'pub_fig', 'outer_cortex_mask')
edge('ellipse_prop', 'rhizodermis_mask', 'pub_fig', 'rhizodermis_mask')
edge('ellipse_prop', 'report', 'pub_fig', 'ellipse_report')

node('pub_display', 'output_display', f, 1, 3)
edge('pub_fig', 'figure_with_legend', 'pub_display', 'main')

vn = {
    'nodes': FRAMES + NODES,
    'edges': EDGES,
    'ui': {
        'previewSize': {'w': 900, 'h': 450},
        'previewPos': {'x': 420, 'y': -60},
        'visualizedNodeId': 'display'
    }
}

if __name__ == '__main__':
    out = os.path.join(REPO, 'public', 'templates', 'root_predictive_ellipse_zoning.vn')
    with open(out, 'w') as fh:
        json.dump(vn, fh, indent=2, ensure_ascii=False)
    print(f'{len(NODES)} nodes, {len(EDGES)} edges, {len(FRAMES)} frames -> {out}')
