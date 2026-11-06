"""Generate public/templates/root_hough_zoning.vn from generic nodes only.

Usage:  .venv/bin/python scripts/gen_root_hough_vn.py

Cells are rebuilt from a wall map (Ridge Filter → Cell Tessellation); only those closed by a
real wall are measured. Zones are found from cell size along the normalised radius ρ, and the
measured cells are projected over the unresolved (blurred) part of each zone (Sample Projection).
Every edge is validated against the live registry schemas (port ids + colors).
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
    # The node keeps its registry label (students recognise nodes by it); context goes in the note.
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


UI_INPUT_ALIASES = {('filter_blur', 'image'): 'main'}


def edge(src, sport, tgt, tport):
    st, tt = _type_of(src), _type_of(tgt)
    sc = _port_color(st, sport, 'out')
    assert sc, f'{src}({st}) has no output {sport}'
    tc = _port_color(tt, tport, 'in')
    if tc is None:  # dynamic input port
        assert tt in ('output_display', 'util_csv_export', 'dict_builder', 'math_expr'), \
            f'{tgt}({tt}) has no input {tport}'
        tn = next(n for n in NODES if n['id'] == tgt)
        tc = sc
        ports = tn['data'].setdefault('ports', [])
        pid = f'{tc}__{tport}'
        if not any(p['id'] == pid for p in ports):
            ports.append({'id': pid, 'color': tc, 'label': tport.split('_', 1)[-1] if tt == 'math_expr' else tport})
    else:
        assert sc == tc or 'any' in (sc, tc), f'color mismatch {src}.{sport}({sc}) -> {tgt}.{tport}({tc})'
    tport = UI_INPUT_ALIASES.get((tt, tport), tport)
    EDGES.append({'id': f'e{len(EDGES) + 1}', 'source': src, 'target': tgt,
                  'sourceHandle': f'{sc}__{sport}', 'targetHandle': f'{tc}__{tport}'})




# ── Enum indices (see schemas) ───────────────────────────────────────────────
OPEN, CLOSE, DILATE, ERODE = 0, 1, 5, 6
ELLIPSE = 2
OTSU, TRIANGLE_INV = 2, 6
OR, SUB, AND = 0, 1, 2
KEEP, REMOVE = 0, 1
BY_PEAK = 1
GRAY_OUT = 4
ABOVE_ONLY = 1
FRAME_GAP = 60
ROW_Y = [0, 1240, 3120]


def row_frames(row, specs):
    x, out = 0, {}
    for fid, title, cols, rows in specs:
        out[fid] = frame(fid, title, x, ROW_Y[row], cols, rows, len(FRAMES) % 8)
        x += cols * DX + 60 + FRAME_GAP
    return out


F = row_frames(0, [('frame-1', 'Step 1: Input & Scale Bar', 2, 2),
                   ('frame-2', 'Step 2: Section', 4, 2),
                   ('frame-3', 'Step 3: Cell Walls', 1, 2),
                   ('frame-4', 'Step 4: Cells (measured vs unresolved)', 3, 2),
                   ('frame-5', 'Step 5: Zones from Cell Size vs Distance to Centre', 2, 4)])
F.update(row_frames(1, [('frame-6', 'Step 6: Stele, Cortex, Layers & Walls', 5, 3),
                        ('frame-7', 'Step 7: Metaxylem & Aerenchyma', 5, 6),
                        ('frame-8', 'Step 8: Tissue Zones & Projection over Unresolved Areas', 5, 6)]))
F.update(row_frames(2, [('frame-9', 'Step 9: RootScan Variables', 7, 6),
                        ('frame-10', 'Step 10: Cell Map (measured vs unresolved)', 7, 6)]))

# ── Step 1 ───────────────────────────────────────────────────────────────────
f = F['frame-1']
node('src', 'input_image', f, 0, 0, {'path': 'samples/root_section_brightfield_c.jpg'},
     'Bright-field root cross-section. Also try root_section_brightfield_a.jpg / _b.jpg.')
node('scale', 'sci_scale_bar_detect', f, 0, 1,
     {'source': 0, 'bar_length': 500.0, 'unit': 0, 'fallback_px_per_mm': 790.0},
     'Length printed next to the scale bar (500 µm here).')
node('gray', 'filter_gray', f, 1, 0)
node('pol', 'filter_auto_polarity', f, 1, 1, {'target': 0, 'method': BY_PEAK},
     'Bright backdrop, dark walls, bright lumens (fluorescence images are inverted).')
edge('src', 'main', 'gray', 'image')
edge('src', 'main', 'scale', 'image')
edge('gray', 'main', 'pol', 'image')

# ── Step 2: section ──────────────────────────────────────────────────────────
f = F['frame-2']
node('sec_blur', 'filter_blur', f, 0, 0, {'method': 0, 'size': 15, 'sigma': 0})
node('sec_thr', 'feat_threshold_adv', f, 1, 0, {'mode': TRIANGLE_INV, 'offset': -30},
     'Everything clearly darker than the backdrop is tissue; offset -30 leaves out the blurred '
     'halo, which would bias ρ.')
node('sec_close', 'feat_morphology_adv', f, 2, 0, {'operation': CLOSE, 'shape': ELLIPSE, 'size': 31, 'iterations': 1})
node('sec_fill', 'fill_holes', f, 3, 0, {'method': 0})
node('sec_open', 'feat_morphology_adv', f, 0, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 25, 'iterations': 2},
     'Removes the scale bar, hairs and specks.')
node('roi', 'util_roi_polygon', f, 1, 1, {'points': '[]', 'filled': True},
     'Optional: draw a polygon around the main root to cut lateral roots or debris. Empty = keep all.')
node('sec_and', 'mask_operations', f, 2, 1, {'operation': AND})
node('section', 'mask_keep_largest', f, 3, 1, {'count': 1}, 'SECTION')
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
     'Cell walls = dark lines, 2 to 8 px thick (σ 1–4). Local normalisation makes the faint walls of pale or '
     'blurred tissue (pith, inner cortex) count as much as the dark ones.')
edge('pol', 'main', 'ridge', 'image')
edge('section', 'mask', 'ridge', 'mask')

# ── Step 4: cells ────────────────────────────────────────────────────────────
f = F['frame-4']
node('tess', 'seg_cell_tessellation', f, 0, 0,
     {'smooth': 1.0, 'depth': 0.3, 'wall_level': 0.7, 'wall_ratio': 3.0, 'min_closure': 0.8,
      'min_solidity': 0.85, 'min_area': 15, 'max_area': 0},
     'Every cell rebuilt from wall to wall. A cell counts as MEASURED only if a real wall '
     'closes it; elsewhere the tissue is UNRESOLVED (hatched) and its cells are projected in Step 8.')
edge('ridge', 'ridge', 'tess', 'walls')
edge('section', 'mask', 'tess', 'mask')
node('walls_a', 'cv_adaptive_threshold', f, 1, 0, {'block_size': 31, 'c': -2, 'adaptive_method': 1, 'invert': True},
     'Walls seen by the ridge filter (brighter than their surroundings in its map).')
node('med3', 'filter_blur', f, 1, 1, {'method': 1, 'size': 3, 'sigma': 0})
node('walls_b', 'cv_adaptive_threshold', f, 2, 1, {'block_size': 31, 'c': 0, 'adaptive_method': 1, 'invert': False},
     'Walls seen as pixels darker than their surroundings: good on small dark-walled cells.')
node('cells', 'seg_cells_from_walls', f, 2, 0,
     {'min_area': 12, 'max_area': 6000, 'min_solidity': 0.82, 'overlap': 0.10, 'footprint': 2,
      'min_contrast': 10},
     'Adds the cells that the wall-to-wall test left out (small cells of the stele ring, cells '
     'beside vessels): spaces enclosed by the walls of either detector. Cells already resolved '
     'by Cell Tessellation are kept as they are; a new lumen must be 10 grey levels brighter than '
     'its wall (dark gaps between thick walls are no cells). Everything coloured on the map comes from here.')
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
node('radial0', 'geom_radial_coords', f, 0, 0, {'smooth': 3.0, 'ignore_border': True},
     'First pass: centre = centroid of the section (wrong when the frame cuts the section).')
node('zoning0', 'sci_profile_zoning', f, 1, 0,
     {'position_key': 'rho', 'value_key': 'radius', 'weight_key': 'score', 'log_values': True,
      'zones': 0, 'max_zones': 6, 'outlier_mad': 3.0, 'outlier_side': ABOVE_ONLY,
      'min_items': 12, 'core_rule': 1, 'n_boot': 0, 'seed': 0},
     'First pass, only to find the core (stele) and re-centre on it.')
node('radial', 'geom_radial_coords', f, 0, 2, {'smooth': 3.0, 'ignore_border': True},
     'ρ = 0 at the centre of the core found in the first pass, 1 on the section outline, along each ray.')
node('zoning', 'sci_profile_zoning', f, 1, 2,
     {'position_key': 'rho', 'value_key': 'radius', 'weight_key': 'score', 'log_values': True,
      'zones': 0, 'max_zones': 6, 'outlier_mad': 3.0, 'outlier_side': ABOVE_ONLY,
      'min_items': 12, 'core_rule': 1, 'n_boot': 50, 'seed': 0},
     'Zones = stretches of ρ where cell size is homogeneous; number chosen by BIC. Core = '
     'everything inside the largest rise of cell size before the cortex (small stele cells → '
     'larger cortical cells) = the stele. Cells much larger than their neighbours (vessels) are '
     'set aside as outliers.')
edge('section', 'mask', 'radial0', 'mask')
edge('tess', 'cells', 'radial0', 'items')
edge('radial0', 'items', 'zoning0', 'items')
edge('radial0', 'position', 'zoning0', 'position')
edge('section', 'mask', 'radial', 'mask')
edge('zoning0', 'core', 'radial', 'center_mask')
edge('tess', 'cells', 'radial', 'items')
edge('radial', 'items', 'zoning', 'items')
edge('radial', 'position', 'zoning', 'position')
node('zone_get', 'plugin_dict_get', f, 0, 3,
     {'key_1': 'main_zone_median_radius', 'key_2': 'core_edge', 'key_3': 'objects'})
edge('zoning', 'stats', 'zone_get', 'dict_in')

# ── Step 6: tissues & walls ──────────────────────────────────────────────────
f = F['frame-6']
node('ring', 'geom_ring_contour', f, 1, 1,
     {'side': 0, 'sigma': 8.0, 'band_low': 0.5, 'band_high': 1.5, 'max_step': 1, 'passes': 6},
     'The stele is darker than the cortex around it (small cells, many walls). Its outline is '
     'searched all the way round, near the core found from cell sizes (first guess), and '
     're-centred on itself: an off-centre stele is followed.')
edge('pol', 'main', 'ring', 'image')
edge('zoning', 'core', 'ring', 'prior')
edge('section', 'mask', 'ring', 'region')
node('stele', 'mask_operations', f, 0, 0, {'operation': AND},
     'STELE = inside the ring contour, within the section.')
node('cortex', 'mask_operations', f, 1, 0, {'operation': SUB}, 'CORTEX = Section − Stele')
node('depth', 'mask_depth_bands', f, 2, 0, {'bands': 3, 'range_low': 0.2, 'range_high': 0.8, 'ignore_border': True},
     'RootScan thirds of the cortex (inner | middle | outer) for CSic, CSmc, CSoc.')
edge('ring', 'mask', 'stele', 'mask_a')
edge('section', 'mask', 'stele', 'mask_b')
edge('section', 'mask', 'cortex', 'mask_a')
edge('stele', 'mask', 'cortex', 'mask_b')
edge('stele', 'mask', 'depth', 'inner')
edge('section', 'mask', 'depth', 'outer')
node('st_ero', 'feat_morphology_adv', f, 3, 0, {'operation': ERODE, 'shape': ELLIPSE, 'size': 21, 'iterations': 1},
     'Kernel ≈ endodermis thickness (same geometric band as Root Anatomy Analysis).')
node('endo', 'mask_operations', f, 4, 0, {'operation': SUB}, 'ENDODERMIS band')
node('sec_ero', 'feat_morphology_adv', f, 3, 1, {'operation': ERODE, 'shape': ELLIPSE, 'size': 31, 'iterations': 1})
node('exo', 'mask_operations', f, 4, 1, {'operation': SUB}, 'EXODERMIS band')
edge('stele', 'mask', 'st_ero', 'mask')
edge('stele', 'mask', 'endo', 'mask_a')
edge('st_ero', 'mask', 'endo', 'mask_b')
edge('section', 'mask', 'sec_ero', 'mask')
edge('section', 'mask', 'exo', 'mask_a')
edge('sec_ero', 'mask', 'exo', 'mask_b')
node('walls', 'cv_adaptive_threshold', f, 0, 1, {'block_size': 41, 'c': 1, 'adaptive_method': 1, 'invert': False},
     'Walls = pixels darker than their neighbourhood. Trusted only inside measured cells.')
edge('pol', 'main', 'walls', 'image')
WALL_REGIONS = [('sec', 'section'), ('ctx', 'cortex'), ('st', 'stele')]
for i, (k, region) in enumerate(WALL_REGIONS):
    node(f'sh_{k}', 'mask_operations', f, i, 2, {'operation': AND})
    edge('cells', 'resolved', f'sh_{k}', 'mask_a')
    edge(region, 'mask', f'sh_{k}', 'mask_b')

# ── Step 7: metaxylem & aerenchyma ───────────────────────────────────────────
f = F['frame-7']
node('lum_sub', 'mask_operations', f, 0, 0, {'operation': SUB})
node('lumens', 'feat_morphology_adv', f, 1, 0, {'operation': OPEN, 'shape': ELLIPSE, 'size': 5, 'iterations': 1},
     'Lumens (section − walls). Vessels are large and stay visible even on poor images, so they '
     'are segmented directly: circles describe oval or irregular vessels badly.')
node('lum_cc', 'sci_connected_components', f, 2, 0,
     {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True, 'show_cross': False})
node('lum_med', 'sci_stats', f, 3, 0)
node('mx_lum', 'cv_adaptive_threshold', f, 4, 0, {'block_size': 71, 'c': -8, 'adaptive_method': 1, 'invert': True},
     'Vessel lumens shine brighter than their surroundings: used only as markers.')
node('mx_and', 'mask_operations', f, 0, 1, {'operation': AND})
node('mx_open', 'feat_morphology_adv', f, 1, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 7, 'iterations': 1})
node('st_lum2', 'mask_operations', f, 2, 1, {'operation': AND})
node('st_lum_fill', 'fill_holes', f, 3, 1, {'method': 0})
node('vessels', 'mask_select_by_marker', f, 4, 1, {'mode': KEEP, 'connectivity': 0})
node('mx_cc', 'sci_connected_components', f, 0, 2,
     {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True, 'show_cross': False})
node('mx_floor', 'math_expr', f, 1, 2, {'expression': '2 * a'})
node('mx_break', 'list_natural_break', f, 2, 2, {'log_scale': True, 'min_value': 0},
     'Metaxylem = the large-vessel population (same rule as Root Anatomy Analysis).')
node('metaxylem', 'filter_blob_filter', f, 3, 2, {'min_area': 1000, 'max_area': 0, 'circ_min': 0.3, 'connectivity': 4},
     'METAXYLEM')
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
node('mx_tess', 'mask_operations', f, 2, 5, {'operation': AND}, 'Measured cells of the stele.')
edge('cells', 'interiors', 'mx_tess', 'mask_a')
edge('stele', 'mask', 'mx_tess', 'mask_b')
node('mx_pts', 'points_to_mask', f, 0, 5, {'radius': 2},
     'Centres of the cells much larger than their neighbours at the same ρ (Step 5 outliers).')
edge('zoning', 'outliers', 'mx_pts', 'points')
edge('src', 'main', 'mx_pts', 'reference')
node('mx_sel', 'mask_select_by_marker', f, 3, 5, {'mode': KEEP, 'connectivity': 0},
     'Measured stele cells that are outliers: vessels whose wall is sharp (real shape).')
edge('mx_tess', 'mask', 'mx_sel', 'mask')
edge('mx_pts', 'mask', 'mx_sel', 'marker')
node('mx_mark', 'mask_operations', f, 1, 5, {'operation': OR},
     'Vessel markers: bright highlight or outlier cell centre.')
edge('mx_open', 'mask', 'mx_mark', 'mask_a')
edge('mx_pts', 'mask', 'mx_mark', 'mask_b')
edge('mx_mark', 'mask', 'vessels', 'marker')
node('mx_cand', 'mask_operations', f, 4, 5, {'operation': OR},
     'Vessels seen as lumens (blurred or dark stele) or as measured cells (sharp stele).')
edge('vessels', 'mask', 'mx_cand', 'mask_a')
edge('mx_sel', 'mask', 'mx_cand', 'mask_b')
edge('mx_cand', 'mask', 'mx_cc', 'image')
edge('lum_med', 'median', 'mx_floor', '0_med')
edge('mx_cc', 'areas', 'mx_break', 'values')
edge('mx_floor', 'result', 'mx_break', 'min_value')
edge('mx_cand', 'mask', 'metaxylem', 'mask')
edge('mx_break', 'threshold', 'metaxylem', 'min_area')
node('ae_thr', 'feat_threshold_adv', f, 4, 2, {'mode': OTSU})
node('ae_open', 'feat_morphology_adv', f, 0, 3, {'operation': OPEN, 'shape': ELLIPSE, 'size': 21, 'iterations': 2},
     'Only spaces wider than ~2 cortical cells survive.')
node('ae_big', 'filter_blob_filter', f, 1, 3, {'min_area': 2000, 'max_area': 0})
node('ae_mid', 'mask_select_by_marker', f, 2, 3, {'mode': KEEP, 'connectivity': 0},
     'RootScan rule: a lacuna reaches the middle third of the cortex.')
node('big_amin', 'math_expr', f, 3, 3, {'expression': 'pi * (2 * a) * (2 * a)'})
node('big_cells', 'filter_blob_filter', f, 4, 3, {'min_area': 2000, 'max_area': 0})
node('normal', 'mask_operations', f, 0, 4, {'operation': SUB})
node('cores', 'feat_morphology_adv', f, 1, 4, {'operation': ERODE, 'shape': ELLIPSE, 'size': 7, 'iterations': 1},
     'Cores of measured cells of ordinary size.')
node('aerenchyma', 'mask_select_by_marker', f, 2, 4, {'mode': REMOVE, 'connectivity': 0},
     'AERENCHYMA: a bright space that contains measured cells is pale tissue, not a lacuna.')
edge('pol', 'main', 'ae_thr', 'image')
edge('cortex', 'mask', 'ae_thr', 'mask')
edge('ae_thr', 'mask', 'ae_open', 'mask')
edge('ae_open', 'mask', 'ae_big', 'mask')
edge('ae_big', 'main', 'ae_mid', 'mask')
edge('depth', 'band_2', 'ae_mid', 'marker')
edge('zone_get', 'val_1', 'big_amin', '0_rctx')
edge('cells', 'interiors', 'big_cells', 'mask')
edge('big_amin', 'result', 'big_cells', 'min_area')
edge('cells', 'interiors', 'normal', 'mask_a')
edge('big_cells', 'mask', 'normal', 'mask_b')
edge('normal', 'mask', 'cores', 'mask')
edge('ae_mid', 'mask', 'aerenchyma', 'mask')
edge('cores', 'mask', 'aerenchyma', 'marker')

# ── Step 8: projection ───────────────────────────────────────────────────────
f = F['frame-8']
node('cell_region', 'mask_operations', f, 0, 0, {'operation': SUB}, 'Cortex − Lacunae')
edge('cortex', 'mask', 'cell_region', 'mask_a')
edge('aerenchyma', 'mask', 'cell_region', 'mask_b')
node('proj_ctx', 'sci_sample_projection', f, 1, 0,
     {'size_key': 'area', 'size_kind': 2, 'position_key': 'rho', 'bandwidth': 0.05, 'packing': 1.0,
      'min_items': 5, 'n_boot': 300, 'seed': 0},
     'Cortical cells per third of the cortex = cells measured + cells projected over the '
     'unresolved part (band area ÷ mean measured cell area at the same ρ; 95 % bootstrap '
     'interval). Packing 1: wall-to-wall cells tile the tissue.')
edge('cells', 'cells', 'proj_ctx', 'items')
edge('depth', 'bands', 'proj_ctx', 'zones')
edge('radial', 'position', 'proj_ctx', 'position')
edge('zoning', 'outliers', 'proj_ctx', 'exclude')
edge('cell_region', 'mask', 'proj_ctx', 'mask')
edge('scale', 'px_per_um', 'proj_ctx', 'px_per_unit')
edge('cells', 'resolved', 'proj_ctx', 'measured')
node('proj', 'sci_sample_projection', f, 2, 0,
     {'size_key': 'area', 'size_kind': 2, 'position_key': 'rho', 'bandwidth': 0.05, 'packing': 1.0,
      'min_items': 5, 'n_boot': 300, 'seed': 0},
     'Same projection on the data-driven zones of Step 5.')
edge('cells', 'cells', 'proj', 'items')
edge('zoning', 'zones', 'proj', 'zones')
edge('zoning', 'outliers', 'proj', 'exclude')
edge('radial', 'position', 'proj', 'position')
edge('scale', 'px_per_um', 'proj', 'px_per_unit')
edge('cells', 'resolved', 'proj', 'measured')
node('cc_get', 'plugin_dict_get', f, 0, 1, {'key_1': 'total_n_low', 'key_2': 'total_n_high', 'key_3': 'total_completeness'})
node('cc_split', 'plugin_dict_get', f, 3, 2, {'key_1': 'total_n_detected', 'key_2': 'total_n_projected', 'key_3': 'total_measured_share'})
edge('proj_ctx', 'stats', 'cc_split', 'dict_in')
node('cs_n', 'plugin_dict_get', f, 1, 1, {'key_1': 'zone_1_n_estimated', 'key_2': 'zone_2_n_estimated', 'key_3': 'zone_3_n_estimated'})
node('cs_a', 'plugin_dict_get', f, 2, 1, {'key_1': 'zone_1_area_px', 'key_2': 'zone_2_area_px', 'key_3': 'zone_3_area_px'})
edge('proj_ctx', 'stats', 'cc_get', 'dict_in')
edge('proj_ctx', 'stats', 'cs_n', 'dict_in')
edge('proj_ctx', 'stats', 'cs_a', 'dict_in')
for i, k in enumerate(('csic', 'csmc', 'csoc')):
    node(f'r_{k}', 'math_expr', f, i, 2, {'expression': 'a / max(b, 1)'},
         'Cell size = band area ÷ estimated cells in the band (territory, walls included, as RootScan).')
    edge('cs_a', f'val_{i + 1}', f'r_{k}', '0_area')
    edge('cs_n', f'val_{i + 1}', f'r_{k}', '1_n')
# Five tissue zones (cells counted and projected zone by zone)
node('oc_band', 'mask_depth_bands', f, 0, 3, {'bands': 2, 'range_low': 0.55, 'range_high': 1.0, 'ignore_border': True},
     'Outer cortex = the outer 45 % of the cortex depth.')
edge('stele', 'mask', 'oc_band', 'inner')
edge('section', 'mask', 'oc_band', 'outer')
node('z_exo', 'mask_operations', f, 1, 3, {'operation': AND}, 'RHIZODERMIS / EXODERMIS: outer cell layers.')
edge('exo', 'mask', 'z_exo', 'mask_a')
edge('cortex', 'mask', 'z_exo', 'mask_b')
node('z_outer', 'mask_operations', f, 2, 3, {'operation': SUB}, 'OUTER CORTEX')
edge('oc_band', 'range_mask', 'z_outer', 'mask_a')
edge('exo', 'mask', 'z_outer', 'mask_b')
node('z_inner', 'mask_operations', f, 3, 3, {'operation': SUB}, 'INNER CORTEX')
edge('cortex', 'mask', 'z_inner', 'mask_a')
edge('oc_band', 'range_mask', 'z_inner', 'mask_b')
node('pith_band', 'mask_depth_bands', f, 0, 4, {'bands': 1, 'range_low': 0.0, 'range_high': 0.3, 'ignore_border': True},
     'Pith = centre of the stele (inner 30 % of its depth).')
edge('stele', 'mask', 'pith_band', 'outer')
node('z_vasc', 'mask_operations', f, 1, 4, {'operation': SUB}, 'VASCULAR CYLINDER = stele − pith')
edge('stele', 'mask', 'z_vasc', 'mask_a')
edge('pith_band', 'range_mask', 'z_vasc', 'mask_b')
ZONE_NAMES = ['Rhizodermis / exodermis', 'Outer cortex', 'Inner cortex', 'Vascular cylinder', 'Pith']
node('zones5', 'mask_to_zones', f, 2, 4, {'names': ', '.join(ZONE_NAMES)})
for k, (src, port) in enumerate([('z_exo', 'mask'), ('z_outer', 'mask'), ('z_inner', 'mask'), ('z_vasc', 'mask'),
                                 ('pith_band', 'range_mask')], start=1):
    edge(src, port, 'zones5', f'mask_{k}')
node('st_outer', 'mask_depth_bands', f, 3, 5, {'bands': 1, 'range_low': 0.4, 'range_high': 1.0, 'ignore_border': True},
     'Outer 60 % of the stele depth.')
edge('stele', 'mask', 'st_outer', 'outer')
node('st_out_nomx', 'mask_operations', f, 4, 5, {'operation': SUB})
edge('st_outer', 'range_mask', 'st_out_nomx', 'mask_a')
edge('metaxylem', 'mask', 'st_out_nomx', 'mask_b')
node('st_large', 'seg_isolated_objects', f, 4, 3,
     {'size_factor': 1.2, 'ring': 6, 'min_free': 0.5, 'min_round': 0.7},
     'LARGE PERIPHERAL STELE CELLS: round cells, larger than most stele cells, set alone in the dense '
     'dark tissue of the outer stele (at the tips of the small-cell groups).')
edge('cells', 'labels', 'st_large', 'labels')
edge('st_out_nomx', 'mask', 'st_large', 'region')
edge('metaxylem', 'mask', 'st_large', 'occupied')
edge('stele', 'mask', 'st_large', 'tissue')
node('tissue', 'mask_operations', f, 3, 4, {'operation': SUB}, 'Tissue = section − lacunae − metaxylem')
node('tissue2', 'mask_operations', f, 4, 4, {'operation': SUB})
edge('section', 'mask', 'tissue', 'mask_a')
edge('aerenchyma', 'mask', 'tissue', 'mask_b')
edge('tissue', 'mask', 'tissue2', 'mask_a')
edge('metaxylem', 'mask', 'tissue2', 'mask_b')
node('proj_z', 'sci_sample_projection', f, 0, 5,
     {'size_key': 'area', 'size_kind': 2, 'position_key': 'rho', 'bandwidth': 0.05, 'packing': 1.0,
      'min_items': 5, 'n_boot': 0, 'seed': 0},
     'Cells per tissue = measured + projected over the unresolved part of the tissue.')
edge('cells', 'cells', 'proj_z', 'items')
edge('zones5', 'zones', 'proj_z', 'zones')
edge('zones5', 'names', 'proj_z', 'names')
edge('radial', 'position', 'proj_z', 'position')
edge('tissue2', 'mask', 'proj_z', 'mask')
edge('cells', 'resolved', 'proj_z', 'measured')
edge('scale', 'px_per_um', 'proj_z', 'px_per_unit')
node('chart', 'ml_bar_chart', f, 1, 5,
     {'dict_key_a': 'measured', 'dict_key_b': 'projected (unresolved area)', 'b_mode': 1,
      'orientation': 1, 'show_values': True, 'title': 'Cells measured + projected', 'xlabel': 'Number of cells'},
     'Solid = cells measured one by one; hatched = cells projected over the unresolved (blurred) area.')
edge('proj_z', 'detected_by_zone', 'chart', 'data_a')
edge('proj_z', 'projected_by_zone', 'chart', 'data_b')
node('tissue_report', 'dict_report_panel', f, 2, 5,
     {'title': 'Cells by Tissue', 'digits': 0,
      'groups': 'Estimated (measured + projected): ' + ', '.join(ZONE_NAMES)},
     'Number of cells per tissue, measured + projected (metaxylem vessels: #MX in the anatomy report).')
edge('proj_z', 'estimated_by_zone', 'tissue_report', 'dict')
node('zone_report', 'dict_report_panel', f, 3, 0,
     {'title': 'Data-driven Zones', 'digits': 4,
      'groups': ' | '.join(['Zones: zones, boundary_1, boundary_1_low, boundary_1_high, boundary_2, '
                            'boundary_2_low, boundary_2_high, boundary_3, boundary_3_low, boundary_3_high']
                           + [f'Zone {z}: zone_{z}_from, zone_{z}_to, zone_{z}_measured_share, zone_{z}_n_detected, '
                              f'zone_{z}_n_projected, zone_{z}_n_estimated, zone_{z}_n_low, zone_{z}_n_high, '
                              f'zone_{z}_mean_diameter_unit, zone_{z}_outliers' for z in range(1, 5)])},
     'Zones found from cell size alone: share of the zone measured, cells measured, cells '
     'projected over the rest, total with 95 % interval (diameters in µm).')
edge('proj', 'stats', 'zone_report', 'dict')
edge('zoning', 'stats', 'zone_report', 'dict_2')

# ── Step 9: RootScan variables (Burton et al. 2012, Table 1) ─────────────────
f = F['frame-9']
for i, (k, region) in enumerate(WALL_REGIONS):
    node(f'shw_{k}', 'mask_operations', f, 0, i, {'operation': AND})
    edge('walls', 'main', f'shw_{k}', 'mask_a')
    edge(f'sh_{k}', 'mask', f'shw_{k}', 'mask_b')
node('lat', 'mask_operations', f, 0, 3, {'operation': SUB})
node('lat_sec', 'mask_operations', f, 0, 4, {'operation': AND})
edge('sec_open', 'mask', 'lat', 'mask_a')
edge('roi', 'mask', 'lat', 'mask_b')
edge('lat', 'mask', 'lat_sec', 'mask_a')
edge('sec_open', 'mask', 'lat_sec', 'mask_b')

AREAS = [('section', 'mask', 'rxsa'), ('cortex', 'mask', 'tca'), ('stele', 'mask', 'tsa'),
         ('aerenchyma', 'mask', 'aa'), ('lat_sec', 'mask', 'la'), ('metaxylem', 'mask', 'xva'),
         ('endo', 'mask', 'ea'), ('exo', 'mask', 'exa'),
         ('sh_sec', 'mask', 'sh_sec'), ('sh_ctx', 'mask', 'sh_ctx'), ('sh_st', 'mask', 'sh_st'),
         ('shw_sec', 'mask', 'shw_sec'), ('shw_ctx', 'mask', 'shw_ctx'), ('shw_st', 'mask', 'shw_st')]
for i, (src, port, k) in enumerate(AREAS):
    node(f'px_{k}', 'feat_mask_stats', f, 1 + i // 5, i % 5, {})
    edge(src, port, f'px_{k}', 'mask')


def expr(nid, col, row, expression, srcs, note=None):
    node(nid, 'math_expr', f, col, row, {'expression': expression}, note)
    for j, s_ in enumerate(srcs):
        sid, sport = s_ if isinstance(s_, tuple) else (s_, 'area_px')
        edge(sid, sport, nid, f'{j}_{sid}')


WALL_NOTE = 'Wall fraction measured in the sharp patches, applied to the whole region.'
expr('xscwa', 4, 0, 'a / max(b, 1) * c', ('px_shw_sec', 'px_sh_sec', 'px_rxsa'), WALL_NOTE)
expr('ccwa', 4, 1, 'a / max(b, 1) * c', ('px_shw_ctx', 'px_sh_ctx', 'px_tca'), WALL_NOTE)
expr('scwa', 4, 2, 'a / max(b, 1) * c', ('px_shw_st', 'px_sh_st', 'px_tsa'), WALL_NOTE)
expr('cca', 4, 3, 'a - b', ('px_tca', 'px_aa'))
expr('n_cf', 4, 4, '(sqrt(a / pi) - sqrt(b / pi)) / max(2 * sqrt(c / max(d, 1) / pi), 1e-9)',
     ('px_rxsa', 'px_tsa', ('cca', 'result'), ('proj_ctx', 'total')),
     'Radial cortex thickness / mean cell diameter (RootScan #CF).')
DERIVED = [('pct_a', '100 * a / max(b, 1)', ('px_aa', 'px_tca')),
           ('res_sec', '100 * a / max(b, 1)', ('px_sh_sec', 'px_rxsa')),
           ('res_ctx', '100 * a / max(b, 1)', ('px_sh_ctx', 'px_tca')),
           ('res_st', '100 * a / max(b, 1)', ('px_sh_st', 'px_tsa')),
           ('pct_cca', '100 * a / max(b, 1)', (('cca', 'result'), 'px_rxsa')),
           ('tsa_rxsa', 'a / max(b, 1)', ('px_tsa', 'px_rxsa')),
           ('tsa_tca', 'a / max(b, 1)', ('px_tsa', 'px_tca'))]
SLOTS = [(5, 0), (1, 5), (2, 5), (4, 5), (5, 1), (5, 2), (5, 3)]
for (col, row), (k, expression, srcs) in zip(SLOTS, DERIVED):
    expr(f'r_{k}', col, row, expression, srcs)
node('quality', 'scalar_input', f, 3, 4, {'value': 5, 'format': 0, 'min': 1, 'max': 5, 'step': 1},
     'Manual image quality rating (RootScan Part VI).')

AREA_KEYS = [(f'px_{k}', 'area_px', k, name) for k, name in
             (('rxsa', 'RXSA'), ('tca', 'TCA'), ('aa', 'AA'), ('la', 'LA'), ('tsa', 'TSA'),
              ('xva', 'XVA'), ('ea', 'EA'), ('exa', 'ExA'))] + \
            [('xscwa', 'result', 'xscwa', 'XSCWA'), ('ccwa', 'result', 'ccwa', 'CCWA'),
             ('scwa', 'result', 'scwa', 'SCWA'), ('cca', 'result', 'cca', 'CCA'),
             ('r_csic', 'result', 'csic', 'CSic'), ('r_csmc', 'result', 'csmc', 'CSmc'),
             ('r_csoc', 'result', 'csoc', 'CSoc')]
OTHER_KEYS = [('r_pct_a', 'result', 'pct_a', '%A'), ('r_pct_cca', 'result', 'pct_cca', '%CCA'),
              ('aerenchyma', 'count', 'n_lac', '#Lac'), ('proj_ctx', 'total', 'n_cc', '#CC'),
              ('n_cf', 'result', 'n_cf', '#CF'), ('metaxylem', 'count', 'n_mx', '#MX'),
              ('r_tsa_rxsa', 'result', 'tsa_rxsa', 'TSA:RXSA'), ('r_tsa_tca', 'result', 'tsa_tca', 'TSA:TCA'),
              ('scale', 'px_per_mm', 'px_per_mm', 'px_per_mm'), ('quality', 'value', 'quality', 'quality_score'),
              ('cc_get', 'val_1', 'cc_low', '#CC_low'), ('cc_get', 'val_2', 'cc_high', '#CC_high'),
              ('cc_split', 'val_1', 'cc_meas', '#CC_measured'), ('cc_split', 'val_2', 'cc_proj', '#CC_projected'),
              ('r_res_sec', 'result', 'res_sec', 'section_measured_%'),
              ('r_res_ctx', 'result', 'res_ctx', 'cortex_measured_%'),
              ('r_res_st', 'result', 'res_st', 'stele_measured_%'),
              ('cells', 'count', 'n_cells', 'cells_measured'), ('zoning', 'count', 'n_zones', 'zones'),
              ('ring', 'contrast', 'st_edge', 'stele_edge_contrast'),
              ('st_large', 'count', 'n_st_large', 'large_peripheral_stele_cells')]
node('areas_px', 'dict_builder', f, 6, 0, {f'name_{k}': n for _, _, k, n in AREA_KEYS})
node('others', 'dict_builder', f, 6, 2, {f'name_{k}': n for _, _, k, n in OTHER_KEYS})
for sid, sport, k, _ in AREA_KEYS:
    edge(sid, sport, 'areas_px', k)
for sid, sport, k, _ in OTHER_KEYS:
    edge(sid, sport, 'others', k)
node('areas_mm', 'dict_scale', f, 6, 1, {'operation': 1, 'factor': 790.0, 'power': 2, 'digits': 5},
     'Every area ÷ (px/mm)². Calibration comes from the scale bar.')
edge('areas_px', 'dict', 'areas_mm', 'dict')
edge('scale', 'px_per_mm', 'areas_mm', 'factor')

GROUPS = ('Measured vs Projected: section_measured_%, cortex_measured_%, stele_measured_%, cells_measured, '
          '#CC_measured, #CC_projected, #CC, #CC_low, #CC_high | '
          'Cross-Section: RXSA, XSCWA, LA, TSA:RXSA | '
          'Cortex: TCA, CCWA, CCA, %CCA, #CC, #CF | '
          'Aerenchyma: AA, %A, #Lac | '
          'Cell Size by Zone: CSic, CSmc, CSoc | '
          'Stele: TSA, SCWA, XVA, #MX, large_peripheral_stele_cells, TSA:TCA | '
          'Layers & Quality: EA, ExA, px_per_mm, quality_score | '
          'Uncertainty: stele_edge_contrast, zones')
node('report', 'dict_report_panel', f, 6, 3, {'title': 'Anatomy Report', 'groups': GROUPS, 'digits': 4},
     'Same variables as Root Anatomy Analysis (RootScan Table 1), areas in mm². First group: how '
     'much of each tissue was MEASURED (cells closed by a real wall) and how many cortical cells '
     'were PROJECTED over the unresolved rest, with the 95 % interval of the total. Outlines '
     '(RXSA, TCA, TSA, AA, XVA, #MX) are measured; wall areas are measured in the resolved '
     'cells and applied to the whole tissue; #CC, #CF and CS = measured + projected. '
     'stele_edge_contrast: how sharp the stele outline was (below ~1.2, check it on the map).')
edge('areas_mm', 'dict', 'report', 'dict')
edge('others', 'dict', 'report', 'dict_2')
node('csv', 'util_csv_export', f, 6, 4, {'filename': 'root_zoning', 'path': 'exports', 'auto_timestamp': True},
     'Click Snapshot: one row per image (RootScan variables + data-driven zones).')
edge('report', 'report', 'csv', 'report_0')
edge('zone_report', 'report', 'csv', 'report_1')
edge('tissue_report', 'report', 'csv', 'report_2')

# ── Step 10: RootScan-style segmentation map ────────────────────────────────
f = F['frame-10']
_slot = iter((c, r) for r in range(6) for c in range(7))


def viz(nid, type_, params=None, note=None):
    c, r = next(_slot)
    node(nid, type_, f, c, r, params, note)


# Drawn on the reconstruction, not on the photograph: every coloured cell is a measured one,
# with its own outline; hatched grey = unresolved tissue, whose cells are projected (Step 8).
# Whole cells get one colour (a cell touching two zones takes the one painted last), so
# zone limits never cut a cell in two. Endodermis = cells across the stele outline.
ZONE_CELLS = [('c_outer', 'z_outer', 'mask'), ('c_inner', 'z_inner', 'mask'), ('c_exo', 'z_exo', 'mask'),
              ('c_vasc', 'z_vasc', 'mask'), ('c_pith', 'pith_band', 'range_mask')]
for n_, src, port in ZONE_CELLS:
    viz(n_, 'mask_select_by_marker', {'mode': KEEP, 'connectivity': 0})
    edge('cells', 'interiors', n_, 'mask')
    edge(src, port, n_, 'marker')
viz('ol_sec', 'mask_outline', {'thickness': 2})
viz('ol_st', 'mask_outline', {'thickness': 3})
viz('ol_mx', 'mask_outline', {'thickness': 2})
viz('ol_ae', 'mask_outline', {'thickness': 2})
edge('section', 'mask', 'ol_sec', 'mask')
edge('stele', 'mask', 'ol_st', 'mask')
edge('metaxylem', 'mask', 'ol_mx', 'mask')
edge('aerenchyma', 'mask', 'ol_ae', 'mask')
for n_, m_ in (('endo_cells', 'ol_st'),):
    viz(n_, 'mask_select_by_marker', {'mode': KEEP, 'connectivity': 0})
    edge('cells', 'interiors', n_, 'mask')
    edge(m_, 'mask', n_, 'marker')

LAYERS = [
    ('c_outer', 'mask', '#eb6834', 0.85, 'Outer Cortex'),
    ('c_inner', 'mask', '#1baf7a', 0.85, 'Inner Cortex'),
    ('c_exo', 'mask', '#2a78d6', 0.85, 'Rhizodermis / Exodermis'),
    ('c_vasc', 'mask', '#eda100', 0.85, 'Vascular Cylinder'),
    ('c_pith', 'mask', '#e87ba4', 0.85, 'Pith'),
    ('st_large', 'mask', '#8d4f00', 0.9, 'Large Peripheral Stele Cells'),
    ('endo_cells', 'mask', '#7e57c2', 0.85, 'Endodermis'),
    ('aerenchyma', 'mask', '#ef9a9a', 1.0, 'Aerenchyma Lacunae'),
    ('metaxylem', 'mask', '#008300', 1.0, 'Metaxylem'),
    ('ol_ae', 'mask', '#c62828', 1.0, None),
    ('ol_mx', 'mask', '#1b5e20', 1.0, None),
    ('ol_st', 'mask', '#212121', 1.0, 'Section & Stele Outlines'),
    ('ol_sec', 'mask', '#212121', 1.0, None),
]
prev = ('cells', 'main')
for i, (src, port, col, alpha, _) in enumerate(LAYERS):
    nid = f'paint_{i}'
    viz(nid, 'draw_tint_mask', {'color': col, 'alpha': alpha})
    edge(prev[0], prev[1], nid, 'image')
    edge(src, port, nid, 'mask')
    prev = (nid, 'main')
LEGEND = [(lbl, col) for _, _, col, _, lbl in LAYERS if lbl] + [('Unresolved (hatched, projected)', '#afafaf')]
viz('legend', 'image_legend', {'entries': '\n'.join(f'{l}:{c}' for l, c in LEGEND),
                               'position': 'top-left', 'font_scale': 0.9, 'swatch_size': 26,
                               'bg_alpha': 0.8, 'padding': 14})
viz('compose', 'util_compose', {'mode': 0, 'gap': 4},
    'Photograph | reconstruction, side by side: what is coloured was measured, nothing else.')
edge('src', 'main', 'compose', 'image_a')
edge(prev[0], prev[1], 'compose', 'image_b')
edge('compose', 'main', 'legend', 'image')
viz('display', 'output_display')
edge('legend', 'main', 'display', 'main')

vn = {'nodes': FRAMES + NODES, 'edges': EDGES,
      'ui': {'previewSize': {'w': 900, 'h': 450}, 'previewPos': {'x': 420, 'y': -60}, 'visualizedNodeId': 'display'}}

if __name__ == '__main__':
    out = os.path.join(REPO, 'public', 'templates', 'root_hough_zoning.vn')
    with open(out, 'w') as fh:
        json.dump(vn, fh, indent=2, ensure_ascii=False)
    print(f'{len(NODES)} nodes, {len(EDGES)} edges, {len(FRAMES)} frames -> {out}')
