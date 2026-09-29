"""Generate public/templates/root_anatomy_analysis.vn from generic nodes only.

Usage:  .venv/bin/python scripts/gen_root_anatomy_vn.py

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
_dyn_counter = {}


def frame(fid, title, x, y, cols, rows, color):
    w, h = cols * DX + 60, rows * DY + 90
    FRAMES.append({
        'id': fid, 'type': 'canvas_frame', 'position': {'x': x, 'y': y},
        'style': {'width': w, 'height': h, 'zIndex': -1},
        'data': {'label': title, 'params': {'title': title, 'color_index': color}},
        'width': w, 'height': h,
    })
    return (x + 30, y + 70, color)


def node(nid, type_, label, origin, col, row, params=None, note=None, ports=None):
    assert H.schema(type_) is not None, f'unknown type {type_}'
    ox, oy, color = origin
    p = dict(params or {})
    p['color_index'] = color
    if note:
        p['node_note'] = note
    # Never rename a node: data.label keeps the canonical schema label so the node type
    # stays identifiable; the descriptive name goes in userLabel (shown in the header).
    canonical = H.schema(type_)['label']
    data = {'label': canonical, 'params': p}
    if label and label != canonical:
        data['userLabel'] = label
    if ports is not None:
        data['ports'] = ports
    NODES.append({'id': nid, 'type': type_, 'position': {'x': ox + col * DX, 'y': oy + row * DY}, 'data': data})


def _port_color(type_, port, side):
    sch = H.schema(type_)
    specs = sch['inputs'] if side == 'in' else sch['outputs']
    for s in specs:
        if s['id'] == port:
            return s['color']
    return None


def _type_of(nid):
    return next(n['type'] for n in NODES if n['id'] == nid)


# UI components whose handle id differs from the schema port (engine aliases main→image)
UI_INPUT_ALIASES = {('filter_blur', 'image'): 'main'}


def edge(src, sport, tgt, tport):
    st, tt = _type_of(src), _type_of(tgt)
    sc = _port_color(st, sport, 'out')
    assert sc, f'{src}({st}) has no output {sport}'
    tn = next(n for n in NODES if n['id'] == tgt)
    tc = _port_color(tt, tport, 'in')
    if tc is None:  # dynamic input port
        sch = H.schema(tt)
        dyn = sch.get('dynamic_inputs') or tt in ('output_display', 'util_csv_export', 'dict_builder', 'math_expr')
        assert dyn, f'{tgt}({tt}) has no input {tport}'
        ports = tn['data'].setdefault('ports', [])
        tc = sc
        pid = f'{tc}__{tport}'
        if not any(p['id'] == pid for p in ports):
            ports.append({'id': pid, 'color': tc, 'label': tport.split('_', 1)[-1] if tt == 'math_expr' else tport})
    else:
        ok = sc == tc or 'any' in (sc, tc)
        assert ok, f'color mismatch {src}.{sport}({sc}) -> {tgt}.{tport}({tc})'
    tport = UI_INPUT_ALIASES.get((tt, tport), tport)
    EDGES.append({'id': f'e{len(EDGES) + 1}', 'source': src, 'target': tgt,
                  'sourceHandle': f'{sc}__{sport}', 'targetHandle': f'{tc}__{tport}'})




# ── Enum indices (see schemas) ───────────────────────────────────────────────
OPEN, CLOSE, DILATE, ERODE = 0, 1, 5, 6
ELLIPSE = 2
OTSU, OTSU_INV, TRIANGLE_INV = 2, 3, 6
AND, SUB = 2, 1
BY_PEAK = 1
FRAME_GAP = 60
ROW_Y = [0, 700, 2210]


def row_frames(row, specs):
    """specs: [(fid, title, cols, rows)] laid out left to right; returns {fid: origin}."""
    x, out = 0, {}
    for i, (fid, title, cols, rows) in enumerate(specs):
        out[fid] = frame(fid, title, x, ROW_Y[row], cols, rows, len(FRAMES) % 8)
        x += cols * DX + 60 + FRAME_GAP
    return out


F = row_frames(0, [('frame-1', 'Step 1: Input & Scale Bar', 3, 2),
                   ('frame-2', 'Step 2: Section (everything darker than the backdrop)', 4, 2),
                   ('frame-3', 'Step 3: Cell Lumens & Scale', 4, 2),
                   ('frame-4', 'Step 4: Coarse Stele (cell-size texture)', 4, 2)])
F.update(row_frames(1, [('frame-5', 'Step 5: Stele Refinement (cell level)', 5, 2),
                        ('frame-6', 'Step 6: Tissues', 5, 5),
                        ('frame-7', 'Step 7: Cortical Cells & Radial Zones', 4, 3)]))
F.update(row_frames(2, [('frame-8', 'Step 8: RootScan Variables', 7, 5),
                        ('frame-9', 'Step 9: Segmentation Map (RootScan colours)', 7, 5)]))

# ── Step 1 ───────────────────────────────────────────────────────────────────
f = F['frame-1']
node('src', 'input_image', 'Root Section', f, 0, 0,
     {'path': 'samples/root_section_brightfield_a.jpg'},
     'Bright-field or fluorescence cross-section. Other samples: root_section_brightfield_b.jpg, '
     'root_section.png (fluo), root_section_lateral.png (fluo + lateral roots).')
node('scale', 'sci_scale_bar_detect', 'Scale Bar → px/mm', f, 0, 1,
     {'source': 0, 'bar_length': 500.0, 'unit': 0, 'fallback_px_per_mm': 784.0},
     'Enter the length printed next to the scale bar (500 µm on the bright-field samples, '
     '200 µm on root_section.png, 100 µm on root_section_lateral.png). Fallback used if no bar is found.')
node('ruler', 'sci_interactive_calibration', 'Draw on Scale Bar (optional)', f, 1, 1,
     {'points': '[]', 'real_len': 0.5, 'unit': 'mm', 'readout': 1},
     'Draw a line over the scale bar and enter its length in mm (500 µm = 0.5). Then set '
     'Scale Bar → px/mm to Source = Manual.')
node('gray', 'filter_gray', 'Grayscale', f, 1, 0)
node('pol', 'filter_auto_polarity', 'Bright Backdrop', f, 2, 0, {'target': 0, 'method': BY_PEAK},
     'Fluorescence (bright walls on black) is inverted: afterwards walls are dark and lumens bright.')
edge('src', 'main', 'gray', 'image')
edge('src', 'main', 'scale', 'image')
edge('src', 'main', 'ruler', 'image')
edge('ruler', 'factor', 'scale', 'manual_px_per_mm')
edge('gray', 'main', 'pol', 'image')

# ── Step 2: section ──────────────────────────────────────────────────────────
f = F['frame-2']
node('sec_blur', 'filter_blur', 'Smooth (cell scale)', f, 0, 0, {'method': 0, 'size': 49, 'sigma': 0})
node('sec_thr', 'feat_threshold_adv', 'Darker than Backdrop', f, 1, 0, {'mode': TRIANGLE_INV, 'offset': -10},
     'Triangle = the dominant histogram peak is the backdrop; everything darker is tissue, '
     'including out-of-focus parts. Offset: margin below the backdrop tone.')
node('sec_close', 'feat_morphology_adv', 'Close Gaps', f, 2, 0, {'operation': CLOSE, 'shape': ELLIPSE, 'size': 31, 'iterations': 1})
node('sec_fill', 'fill_holes', 'Fill Holes', f, 3, 0, {'method': 0})
node('sec_open', 'feat_morphology_adv', 'Remove Scale Bar & Debris', f, 0, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 25, 'iterations': 2},
     'Removes anything thinner than ~50 px (scale bar, hairs, specks).')
node('roi', 'util_roi_polygon', 'Keep Region (optional)', f, 1, 1, {'points': '[]', 'filled': True},
     'Optional: draw a polygon around the main root to cut lateral roots or debris. Empty = keep all.')
node('sec_and', 'mask_operations', 'Apply Region', f, 2, 1, {'operation': AND})
node('section', 'mask_keep_largest', 'SECTION', f, 3, 1, {'count': 1})
edge('pol', 'main', 'sec_blur', 'image')
edge('sec_blur', 'main', 'sec_thr', 'image')
edge('sec_thr', 'mask', 'sec_close', 'mask')
edge('sec_close', 'mask', 'sec_fill', 'mask')
edge('sec_fill', 'main', 'sec_open', 'mask')
edge('src', 'main', 'roi', 'image')
edge('sec_open', 'mask', 'sec_and', 'mask_a')
edge('roi', 'mask', 'sec_and', 'mask_b')
edge('sec_and', 'mask', 'section', 'mask')

# ── Step 3: lumens & scale ───────────────────────────────────────────────────
f = F['frame-3']
node('walls', 'cv_adaptive_threshold', 'Cell Walls', f, 0, 0, {'block_size': 41, 'c': 1, 'adaptive_method': 1, 'invert': False},
     'Walls = pixels darker than their neighbourhood. Low C keeps faint walls (dark/low-contrast tissue).')
node('lum_sub', 'mask_operations', 'Section − Walls', f, 1, 0, {'operation': SUB})
node('lumens', 'feat_morphology_adv', 'LUMENS', f, 2, 0, {'operation': OPEN, 'shape': ELLIPSE, 'size': 5, 'iterations': 1},
     'One blob per cell interior.')
node('lum_cc', 'sci_connected_components', 'Lumen Areas', f, 3, 0,
     {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True, 'show_cross': False})
node('lum_med', 'sci_stats', 'Median Lumen Area', f, 0, 1)
node('sigma', 'math_expr', 'Texture Scale σ', f, 1, 1, {'expression': 'sqrt(a) / 2.7'},
     'σ ≈ typical cell diameter / 2.7 → detectors adapt to magnification automatically.')
edge('pol', 'main', 'walls', 'image')
edge('section', 'mask', 'lum_sub', 'mask_a')
edge('walls', 'main', 'lum_sub', 'mask_b')
edge('lum_sub', 'mask', 'lumens', 'mask')
edge('lumens', 'mask', 'lum_cc', 'image')
edge('lum_cc', 'areas', 'lum_med', 'data_list')
edge('lum_med', 'median', 'sigma', '0_med')

# ── Step 4: coarse stele ─────────────────────────────────────────────────────
f = F['frame-4']
node('dog', 'filter_dog', 'Band Energy (DoG)', f, 0, 0, {'sigma': 5.0, 'ratio': 2.0, 'output': 0},
     'Energy at the cortical-cell scale: high in the cortex (large cells), low in the stele (small cells).')
node('en_blur', 'filter_blur', 'Smooth', f, 1, 0, {'method': 0, 'size': 91, 'sigma': 0})
node('inner', 'feat_morphology_adv', 'Inner Section', f, 2, 0, {'operation': ERODE, 'shape': ELLIPSE, 'size': 31, 'iterations': 2},
     'Ignore the rim so the epidermis does not bias the threshold.')
node('st_thr', 'feat_threshold_adv', 'Low Energy (Otsu in section)', f, 3, 0, {'mode': OTSU_INV, 'offset': 0},
     'Offset < 0 shrinks the stele, > 0 grows it (e.g. −10 for root_section_lateral.png).')
node('st_open', 'feat_morphology_adv', 'Detach', f, 0, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 31, 'iterations': 2})
node('st_big', 'mask_keep_largest', 'Largest', f, 1, 1, {'count': 1})
node('st_close', 'feat_morphology_adv', 'Smooth Outline', f, 2, 1, {'operation': CLOSE, 'shape': ELLIPSE, 'size': 31, 'iterations': 2})
node('coarse', 'fill_holes', 'COARSE STELE (±1 cell)', f, 3, 1, {'method': 0})
edge('pol', 'main', 'dog', 'image')
edge('sigma', 'result', 'dog', 'sigma')
edge('dog', 'main', 'en_blur', 'image')
edge('section', 'mask', 'inner', 'mask')
edge('en_blur', 'main', 'st_thr', 'image')
edge('inner', 'mask', 'st_thr', 'mask')
edge('st_thr', 'mask', 'st_open', 'mask')
edge('st_open', 'mask', 'st_big', 'mask')
edge('st_big', 'mask', 'st_close', 'mask')
edge('st_close', 'mask', 'coarse', 'mask')

# ── Step 5: stele refinement ─────────────────────────────────────────────────
f = F['frame-5']
node('band_out', 'feat_morphology_adv', 'Band Outer (+2 cells)', f, 0, 0, {'operation': DILATE, 'shape': ELLIPSE, 'size': 31, 'iterations': 2},
     'The true boundary lies within ~2 cortical cells of the coarse stele.')
node('core', 'feat_morphology_adv', 'Sure Stele (−3 cells)', f, 1, 0, {'operation': ERODE, 'shape': ELLIPSE, 'size': 31, 'iterations': 3})
node('ring', 'mask_operations', 'Search Band', f, 2, 0, {'operation': SUB})
node('snap', 'feat_threshold_adv', 'Dense / Dark Side (Otsu in band)', f, 3, 0, {'mode': OTSU_INV, 'offset': 8},
     'Inside the boundary tissue is darker on average (dense walls of endodermis/pericycle, or '
     'stained ring); outside are the large bright cortical lumens. Offset > 0 moves the line outward.')
node('st_union', 'mask_operations', 'Sure + Dark Band', f, 4, 0, {'operation': 0})
node('st_open2', 'feat_morphology_adv', 'Detach', f, 0, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 15, 'iterations': 1})
node('st_big2', 'mask_keep_largest', 'Largest', f, 1, 1, {'count': 1})
node('st_fill2', 'fill_holes', 'Fill', f, 2, 1, {'method': 0})
edge('coarse', 'main', 'band_out', 'mask')
edge('coarse', 'main', 'core', 'mask')
edge('band_out', 'mask', 'ring', 'mask_a')
edge('core', 'mask', 'ring', 'mask_b')
edge('sec_blur', 'main', 'snap', 'image')
edge('ring', 'mask', 'snap', 'mask')
edge('core', 'mask', 'st_union', 'mask_a')
edge('snap', 'mask', 'st_union', 'mask_b')
edge('st_union', 'mask', 'st_open2', 'mask')
edge('st_open2', 'mask', 'st_big2', 'mask')
edge('st_big2', 'mask', 'st_fill2', 'mask')

# ── Step 6: tissues ──────────────────────────────────────────────────────────
f = F['frame-6']
node('stele', 'feat_morphology_adv', 'STELE', f, 0, 0, {'operation': CLOSE, 'shape': ELLIPSE, 'size': 31, 'iterations': 1},
     'Smooths the cell-level outline (outer edge of the endodermis).')
node('cortex', 'mask_operations', 'CORTEX = Section − Stele', f, 1, 0, {'operation': SUB})
edge('st_fill2', 'main', 'stele', 'mask')
edge('section', 'mask', 'cortex', 'mask_a')
edge('stele', 'mask', 'cortex', 'mask_b')
# metaxylem
node('mx_lum', 'cv_adaptive_threshold', 'Bright Highlights', f, 0, 1, {'block_size': 71, 'c': -8, 'adaptive_method': 1, 'invert': True},
     'Vessel lumens shine brighter than their surroundings: used only as markers.')
node('mx_and', 'mask_operations', 'In Stele', f, 1, 1, {'operation': AND})
node('mx_open', 'feat_morphology_adv', 'Clean Markers', f, 2, 1, {'operation': OPEN, 'shape': ELLIPSE, 'size': 7, 'iterations': 1})
node('st_lum', 'mask_operations', 'Stele Lumens', f, 3, 1, {'operation': AND})
node('st_lum_fill', 'fill_holes', 'Fill', f, 4, 1, {'method': 0})
node('vessels', 'mask_select_by_marker', 'Whole Vessels', f, 0, 2, {'mode': 0, 'connectivity': 0},
     'Complete lumens (from the wall map) that contain a bright highlight.')
node('mx_cc', 'sci_connected_components', 'Vessel Areas', f, 1, 2,
     {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True, 'show_cross': False})
node('mx_floor', 'math_expr', 'Floor = 2 × Median Lumen', f, 2, 2, {'expression': '2 * a'},
     'Ignore ordinary cells: only lumens at least twice the median cell are vessel candidates.')
node('mx_break', 'list_natural_break', 'Small | Large Split', f, 3, 2, {'log_scale': True, 'min_value': 0},
     'Metaxylem = the large-vessel population, split from small vessels without a fixed size.')
node('metaxylem', 'filter_blob_filter', 'METAXYLEM', f, 4, 2, {'min_area': 1000, 'max_area': 0, 'circ_min': 0.3, 'connectivity': 4},
     'Circularity ≥ 0.3 rejects torn tissue (ragged streaks) mistaken for a lumen.')
edge('pol', 'main', 'mx_lum', 'image')
edge('mx_lum', 'main', 'mx_and', 'mask_a')
edge('stele', 'mask', 'mx_and', 'mask_b')
edge('mx_and', 'mask', 'mx_open', 'mask')
edge('lumens', 'mask', 'st_lum', 'mask_a')
edge('stele', 'mask', 'st_lum', 'mask_b')
edge('st_lum', 'mask', 'st_lum_fill', 'mask')
edge('st_lum_fill', 'main', 'vessels', 'mask')
edge('mx_open', 'mask', 'vessels', 'marker')
edge('vessels', 'mask', 'mx_cc', 'image')
edge('mx_cc', 'areas', 'mx_break', 'values')
edge('lum_med', 'median', 'mx_floor', '0_med')
edge('mx_floor', 'result', 'mx_break', 'min_value')
edge('vessels', 'mask', 'metaxylem', 'mask')
edge('mx_break', 'threshold', 'metaxylem', 'min_area')
# aerenchyma (RootScan: lacunae lie in the middle of the cortex)
node('ae_thr', 'feat_threshold_adv', 'Bright in Cortex', f, 0, 3, {'mode': OTSU})
node('ae_open', 'feat_morphology_adv', 'Keep Wide Spaces', f, 1, 3, {'operation': OPEN, 'shape': ELLIPSE, 'size': 21, 'iterations': 2},
     'Only spaces wider than ~2 cortical cells survive = lacunae.')
node('ae_big', 'filter_blob_filter', 'Large Spaces', f, 2, 3, {'min_area': 2000, 'max_area': 0})
node('aerenchyma', 'mask_select_by_marker', 'AERENCHYMA', f, 3, 3, {'mode': 0, 'connectivity': 0},
     'RootScan rule: a lacuna must reach the middle third of the cortex (excludes gaps at the rim and near the stele).')
edge('pol', 'main', 'ae_thr', 'image')
edge('cortex', 'mask', 'ae_thr', 'mask')
edge('ae_thr', 'mask', 'ae_open', 'mask')
edge('ae_open', 'mask', 'ae_big', 'mask')
edge('ae_big', 'main', 'aerenchyma', 'mask')
# endodermis / exodermis bands
node('st_ero', 'feat_morphology_adv', 'Stele − 1 layer', f, 0, 4, {'operation': ERODE, 'shape': ELLIPSE, 'size': 21, 'iterations': 1},
     'Kernel ≈ endodermis thickness.')
node('endo', 'mask_operations', 'ENDODERMIS band', f, 1, 4, {'operation': SUB})
node('sec_ero', 'feat_morphology_adv', 'Section − 1 layer', f, 2, 4, {'operation': ERODE, 'shape': ELLIPSE, 'size': 31, 'iterations': 1})
node('exo', 'mask_operations', 'EXODERMIS band', f, 3, 4, {'operation': SUB})
edge('stele', 'mask', 'st_ero', 'mask')
edge('stele', 'mask', 'endo', 'mask_a')
edge('st_ero', 'mask', 'endo', 'mask_b')
edge('section', 'mask', 'sec_ero', 'mask')
edge('section', 'mask', 'exo', 'mask_a')
edge('sec_ero', 'mask', 'exo', 'mask_b')

# ── Step 7: cortical cells & radial zones ───────────────────────────────────
f = F['frame-7']
node('zones', 'mask_depth_bands', 'Inner | Middle | Outer Cortex', f, 0, 0, {'bands': 3, 'range_low': 0.2, 'range_high': 0.8, 'ignore_border': True},
     '0 = stele edge, 1 = section edge. The image frame is not an edge (sections cut by the frame).')
edge('stele', 'mask', 'zones', 'inner')
edge('section', 'mask', 'zones', 'outer')
edge('zones', 'band_2', 'aerenchyma', 'marker')
node('cell_region', 'mask_operations', 'Cortex − Lacunae', f, 1, 0, {'operation': SUB})
node('cell_rad', 'math_expr', 'Cell Radius (px)', f, 2, 0, {'expression': 'sqrt(a / pi)'})
node('cell_sig', 'math_expr', 'Peak Smoothing σ', f, 3, 0, {'expression': '0.5 * a'})
node('peaks', 'feat_peak_markers', 'One Marker per Cell', f, 0, 1, {'polarity': 0, 'sigma': 3.5, 'min_distance': 7.0},
     'Each cell interior is a bright dome after smoothing; its top seeds one cell.')
node('ws', 'feat_watershed', 'Cells (Watershed)', f, 1, 1, {'visualization': 0, 'boundary_color': '#FF0000', 'boundary_thickness': 1},
     'Grows each marker until it meets the neighbouring cell on the wall → whole cells, walls included.')
node('cell_stats', 'sci_zone_stats', 'Cells per Zone', f, 2, 1, {'min_area': 30, 'max_area': 50000, 'ignore_label': -99},
     'Count and mean size per band (CSic / CSmc / CSoc). Max Area drops the watershed background region '
     '(label numbering differs between engines, its size does not).')
node('cz_ic', 'plugin_dict_get', 'CSic | CSmc | CSoc', f, 3, 1,
     {'key_1': 'zone_1_mean_area', 'key_2': 'zone_2_mean_area', 'key_3': 'zone_3_mean_area'})
edge('cortex', 'mask', 'cell_region', 'mask_a')
edge('aerenchyma', 'mask', 'cell_region', 'mask_b')
edge('lum_med', 'median', 'cell_rad', '0_med')
edge('cell_rad', 'result', 'cell_sig', '0_rad')
edge('pol', 'main', 'peaks', 'image')
edge('cell_region', 'mask', 'peaks', 'mask')
edge('cell_sig', 'result', 'peaks', 'sigma')
edge('cell_rad', 'result', 'peaks', 'min_distance')
edge('pol', 'main', 'ws', 'image')
edge('peaks', 'markers', 'ws', 'markers')
edge('cell_region', 'mask', 'ws', 'mask')
edge('ws', 'markers_out', 'cell_stats', 'regions')
edge('zones', 'bands', 'cell_stats', 'zones')
edge('cell_stats', 'stats', 'cz_ic', 'dict_in')

# ── Step 8: RootScan variables (Burton et al. 2012, Table 1) ─────────────────
f = F['frame-8']
node('wall_sec', 'mask_operations', 'Walls ∩ Section', f, 0, 0, {'operation': AND})
node('wall_ctx', 'mask_operations', 'Walls ∩ Cortex', f, 0, 1, {'operation': AND})
node('wall_st', 'mask_operations', 'Walls ∩ Stele', f, 0, 2, {'operation': AND})
node('lat', 'mask_operations', 'Excluded by Region', f, 0, 3, {'operation': SUB})
node('lat_sec', 'mask_operations', 'Lateral ∩ Tissue', f, 0, 4, {'operation': AND})
for n_, m_ in (('wall_sec', 'section'), ('wall_ctx', 'cortex'), ('wall_st', 'stele')):
    edge('walls', 'main', n_, 'mask_a')
    edge(m_, 'mask', n_, 'mask_b')
edge('sec_open', 'mask', 'lat', 'mask_a')
edge('roi', 'mask', 'lat', 'mask_b')
edge('lat', 'mask', 'lat_sec', 'mask_a')
edge('sec_open', 'mask', 'lat_sec', 'mask_b')

AREAS = [('section', 'mask', 'rxsa', 'RXSA'), ('wall_sec', 'mask', 'xscwa', 'XSCWA'),
         ('cortex', 'mask', 'tca', 'TCA'), ('wall_ctx', 'mask', 'ccwa', 'CCWA'),
         ('aerenchyma', 'mask', 'aa', 'AA'), ('lat_sec', 'mask', 'la', 'LA'),
         ('stele', 'mask', 'tsa', 'TSA'), ('wall_st', 'mask', 'scwa', 'SCWA'),
         ('metaxylem', 'mask', 'xva', 'XVA'), ('endo', 'mask', 'ea', 'EA'), ('exo', 'mask', 'exa', 'ExA')]
for i, (src, port, k, name) in enumerate(AREAS):
    node(f'px_{k}', 'feat_mask_stats', f'{name} (px²)', f, 1 + i // 5, i % 5, {})
    edge(src, port, f'px_{k}', 'mask')

node('cca', 'math_expr', 'CCA = TCA − AA', f, 4, 0, {'expression': 'a - b'})
edge('px_tca', 'area_px', 'cca', '0_tca')
edge('px_aa', 'area_px', 'cca', '1_aa')

DERIVED = [('pct_a', '%A', '100 * a / b', ('px_aa', 'px_tca')),
           ('pct_cca', '%CCA', '100 * a / b', (('cca', 'result'), 'px_rxsa')),
           ('tsa_rxsa', 'TSA:RXSA', 'a / b', ('px_tsa', 'px_rxsa')),
           ('tsa_tca', 'TSA:TCA', 'a / b', ('px_tsa', 'px_tca'))]
for i, (k, name, expr, srcs) in enumerate(DERIVED):
    node(f'r_{k}', 'math_expr', name, f, 4, 1 + i, {'expression': expr})
    for j, s_ in enumerate(srcs):
        sid, sport = s_ if isinstance(s_, tuple) else (s_, 'area_px')
        edge(sid, sport, f'r_{k}', f'{j}_{sid}')
node('n_cf', 'math_expr', '#CF (cell files)', f, 3, 3, {'expression': '(sqrt(a / pi) - sqrt(b / pi)) / (2 * sqrt(c / pi))'},
     'Radial cortex thickness / mean cell diameter (RootScan #CF).')
edge('px_rxsa', 'area_px', 'n_cf', '0_rxsa')
edge('px_tsa', 'area_px', 'n_cf', '1_tsa')
edge('cell_stats', 'mean_area', 'n_cf', '2_cell')
node('quality', 'scalar_input', 'Quality Score (1–5)', f, 3, 4, {'value': 5, 'format': 0, 'min': 1, 'max': 5, 'step': 1},
     'Manual image quality rating (RootScan Part VI).')

AREA_KEYS = [(f'px_{k}', 'area_px', k, name) for _, _, k, name in AREAS] + \
            [('cca', 'result', 'cca', 'CCA'), ('cz_ic', 'val_1', 'csic', 'CSic'),
             ('cz_ic', 'val_2', 'csmc', 'CSmc'), ('cz_ic', 'val_3', 'csoc', 'CSoc')]
OTHER_KEYS = [('r_pct_a', 'result', 'pct_a', '%A'), ('r_pct_cca', 'result', 'pct_cca', '%CCA'),
              ('aerenchyma', 'count', 'n_lac', '#Lac'), ('cell_stats', 'total_count', 'n_cc', '#CC'),
              ('n_cf', 'result', 'n_cf', '#CF'), ('metaxylem', 'count', 'n_mx', '#MX'),
              ('r_tsa_rxsa', 'result', 'tsa_rxsa', 'TSA:RXSA'), ('r_tsa_tca', 'result', 'tsa_tca', 'TSA:TCA'),
              ('scale', 'px_per_mm', 'px_per_mm', 'px_per_mm'), ('quality', 'value', 'quality', 'quality_score')]
node('areas_px', 'dict_builder', 'Areas (px²)', f, 5, 0, {f'name_{k}': n for _, _, k, n in AREA_KEYS})
node('others', 'dict_builder', 'Counts & Ratios', f, 5, 2, {f'name_{k}': n for _, _, k, n in OTHER_KEYS})
for sid, sport, k, _ in AREA_KEYS:
    edge(sid, sport, 'areas_px', k)
for sid, sport, k, _ in OTHER_KEYS:
    edge(sid, sport, 'others', k)
node('areas_mm', 'dict_scale', 'px² → mm²', f, 5, 1, {'operation': 1, 'factor': 784.0, 'power': 2, 'digits': 5},
     'Every area ÷ (px/mm)². Calibration comes from the scale bar.')
edge('areas_px', 'dict', 'areas_mm', 'dict')
edge('scale', 'px_per_mm', 'areas_mm', 'factor')

GROUPS = ('Cross-Section: RXSA, XSCWA, LA, TSA:RXSA | '
          'Cortex: TCA, CCWA, CCA, %CCA, #CC, #CF | '
          'Aerenchyma: AA, %A, #Lac | '
          'Cell Size by Zone: CSic, CSmc, CSoc | '
          'Stele: TSA, SCWA, XVA, #MX, TSA:TCA | '
          'Layers & Quality: EA, ExA, px_per_mm, quality_score')
node('report', 'dict_report_panel', 'Anatomy Report', f, 6, 0, {'title': 'Anatomy Report', 'groups': GROUPS, 'digits': 4},
     'Areas in mm², counts, ratios — RootScan Table 1. Click Full Report for every variable.')
edge('areas_mm', 'dict', 'report', 'dict')
edge('others', 'dict', 'report', 'dict_2')
node('csv', 'util_csv_export', 'CSV Export', f, 6, 3, {'filename': 'root_anatomy', 'path': 'exports', 'auto_timestamp': True},
     'Click Snapshot: one row per image, one column per variable.')
edge('report', 'report', 'csv', 'report_0')

# ── Step 9: RootScan-style segmentation map ─────────────────────────────────
f = F['frame-9']
_slot = iter((c, r) for r in range(5) for c in range(7))


def viz(nid, type_, label, params=None, note=None):
    c, r = next(_slot)
    node(nid, type_, label, f, c, r, params, note)


viz('not_sec', 'plugin_invert_mask', 'Outside Section')
viz('cc_lum', 'mask_operations', 'Cortical Cell Lumens', {'operation': AND},
    'Only the lumens are coloured, so the walls stay visible as a dark network.')
viz('cells_in', 'mask_operations', 'Inner Cells', {'operation': AND})
viz('cells_mid', 'mask_operations', 'Middle Cells', {'operation': AND})
viz('cells_out', 'mask_operations', 'Outer Cells', {'operation': AND})
edge('section', 'mask', 'not_sec', 'mask')
edge('lumens', 'mask', 'cc_lum', 'mask_a')
edge('cell_region', 'mask', 'cc_lum', 'mask_b')
for n_, b_ in (('cells_in', 'band_1'), ('cells_mid', 'band_2'), ('cells_out', 'band_3')):
    edge('cc_lum', 'mask', n_, 'mask_a')
    edge('zones', b_, n_, 'mask_b')
viz('endo_lum', 'mask_operations', 'Endodermis Lumens', {'operation': AND})
viz('exo_lum', 'mask_operations', 'Exodermis Lumens', {'operation': AND})
for n_, m_ in (('endo_lum', 'endo'), ('exo_lum', 'exo')):
    edge('lumens', 'mask', n_, 'mask_a')
    edge(m_, 'mask', n_, 'mask_b')
viz('ol_sec', 'mask_outline', 'Section Outline', {'thickness': 3})
viz('ol_st', 'mask_outline', 'Stele Outline', {'thickness': 3})
viz('ol_mx', 'mask_outline', 'Vessel Outlines', {'thickness': 2})
viz('ol_1', 'mask_operations', 'Outlines', {'operation': 0})
viz('ol_all', 'mask_operations', 'All Outlines', {'operation': 0})
edge('section', 'mask', 'ol_sec', 'mask')
edge('stele', 'mask', 'ol_st', 'mask')
edge('metaxylem', 'main', 'ol_mx', 'mask')
edge('ol_sec', 'mask', 'ol_1', 'mask_a')
edge('ol_st', 'mask', 'ol_1', 'mask_b')
edge('ol_1', 'mask', 'ol_all', 'mask_a')
edge('ol_mx', 'mask', 'ol_all', 'mask_b')

# Painting order = z-order (flat fills, like RootScan Fig. 1f)
LAYERS = [
    ('not_sec', 'main', '#ffffff', 'Background'),
    ('section', 'mask', '#f3ead3', 'Tissue'),
    ('stele', 'mask', '#b2dfdb', 'Stele Tissue'),
    ('wall_sec', 'mask', '#3e2723', 'Cell Walls'),
    ('cells_out', 'mask', '#ff7043', 'Outer Cortex Cells'),
    ('cells_mid', 'mask', '#ffca28', 'Middle Cortex Cells'),
    ('cells_in', 'mask', '#9ccc65', 'Inner Cortex Cells'),
    ('st_lum', 'mask', '#e0f7fa', 'Stele Cell Lumens'),
    ('exo_lum', 'mask', '#b39ddb', 'Exodermis / Epidermis Cells'),
    ('endo_lum', 'mask', '#00acc1', 'Endodermis Cells'),
    ('aerenchyma', 'mask', '#6d2c1f', 'Aerenchyma Lacunae'),
    ('metaxylem', 'main', '#2e7d32', 'Metaxylem'),
    ('ws', 'boundaries', '#3e2723', 'Cell Boundaries'),
    ('ol_all', 'mask', '#111111', 'Outlines'),
]
prev = ('src', 'main')
for i, (src, port, col, label) in enumerate(LAYERS):
    nid = f'paint_{i}'
    viz(nid, 'draw_tint_mask', label, {'color': col, 'alpha': 1.0})
    edge(prev[0], prev[1], nid, 'image')
    edge(src, port, nid, 'mask')
    prev = (nid, 'main')
LEGEND = [(lbl, col) for src, _, col, lbl in LAYERS if src not in ('not_sec', 'section', 'ws', 'ol_all')]
viz('legend', 'image_legend', 'Legend', {'entries': '\n'.join(f'{l}:{c}' for l, c in LEGEND),
                                          'position': 'top-left', 'font_scale': 0.9, 'swatch_size': 26,
                                          'bg_alpha': 0.8, 'padding': 14})
edge(prev[0], prev[1], 'legend', 'image')
prev = ('legend', 'main')
viz('compose', 'util_compose', 'Original | Segmentation', {'mode': 0, 'gap': 4})
viz('display', 'output_display', 'Display')
edge('src', 'main', 'compose', 'image_a')
edge(prev[0], prev[1], 'compose', 'image_b')
edge('compose', 'main', 'display', 'main')

vn = {'nodes': FRAMES + NODES, 'edges': EDGES,
      'ui': {'previewSize': {'w': 900, 'h': 450}, 'previewPos': {'x': 420, 'y': -60}, 'visualizedNodeId': 'display'}}

if __name__ == '__main__':
    out = os.path.join(REPO, 'public', 'templates', 'root_anatomy_analysis.vn')
    with open(out, 'w') as fh:
        json.dump(vn, fh, indent=2, ensure_ascii=False)
    print(f'{len(NODES)} nodes, {len(EDGES)} edges, {len(FRAMES)} frames -> {out}')
