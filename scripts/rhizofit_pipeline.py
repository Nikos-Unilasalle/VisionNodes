"""RhizoFit segmentation pipeline as plain Python calls (no .vn template, no graph engine).

This is the Predictive Ellipse Zoning template (public/templates/root_predictive_ellipse_zoning.vn)
written out node by node, in topological order, with the template's parameters. Each step calls
the `process` method of the plugin class that implements the node, with the inputs and parameters
the headless executor would give it, so the outputs are identical to running the template.
Only the nodes the analysis reads are run (display, legend and report nodes are left out).

`run(image_path)` searches the metaxylem ring twice, as anchor_choice_lib describes:
  'stele'  vessel candidates restricted to the stele (the template as it is);
  'whole'  candidates taken from the whole section, ring pattern keeping the innermost ring of
           large lumens (geom_ring_pattern select=1).
The nodes upstream of the vessel search are shared by both searches and run once.

Each search returns {node_id: outputs}, the same layout as a template run, so
`pipe['cells']['labels']`, `pipe['mx_ring']['radius']`, ... read the same values.
"""
import contextlib
import copy
import importlib
import io
import os
import sys

_ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'engine')
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

# Plugin module (engine/plugins/<name>.py) of every node type used here. Plain literal: the web
# app bundler (scripts/build_root_webapp.py) reads it without importing this module.
PLUGINS = {
    'input_image': 'core_sources',
    'filter_gray': 'core_filters',
    'filter_blur': 'core_filters',
    'util_roi_polygon': 'geometry_op',
    'filter_auto_polarity': 'filter_auto_polarity',
    'cv_adaptive_threshold': 'cv_adaptive_threshold',
    'feat_threshold_adv': 'watershed_analysis',
    'feat_morphology_adv': 'watershed_analysis',
    'fill_holes': 'fill_holes',
    'mask_operations': 'mask_ops',
    'mask_keep_largest': 'mask_keep_largest',
    'filter_ridge': 'filter_ridge',
    'seg_cell_tessellation': 'seg_cell_tessellation',
    'geom_radial_coords': 'geom_radial_coords',
    'seg_cells_from_walls': 'seg_cells_from_walls',
    'sci_connected_components': 'sci_connected_components',
    'sci_profile_zoning': 'sci_profile_zoning',
    'sci_stats': 'analytics',
    'math_expr': 'math_expr',
    'geom_ring_contour': 'geom_ring_contour',
    'points_to_mask': 'points_to_mask',
    'mask_select_by_marker': 'mask_select_by_marker',
    'geom_ring_pattern': 'geom_ring_pattern',
    'filter_blob_filter': 'blob_filter',
    'geom_ellipse_propagation': 'geom_ellipse_propagation',
    'draw_root_publication': 'draw_root_publication',   # run by the web runner for the figure
}

SEARCHES = ('stele', 'whole')
INNERMOST_LARGE = 1       # geom_ring_pattern 'select': innermost ring of large objects

# mask_operations 'operation' values
_UNION, _SUBTRACT, _INTERSECT = 0, 1, 2

# Template parameters, node by node (color_index and node_note are display-only and left out).
PARAMS = {
    'src': {},   # path given at run time
    'gray': {},
    'roi': {'points': '[]', 'filled': True},
    'pol': {'target': 0, 'method': 1},
    'sec_blur': {'method': 0, 'size': 15, 'sigma': 0},
    'med3': {'method': 1, 'size': 3, 'sigma': 0},
    'walls': {'block_size': 41, 'c': 1, 'adaptive_method': 1, 'invert': False},
    'mx_lum': {'block_size': 71, 'c': -8, 'adaptive_method': 1, 'invert': True},
    'sec_thr': {'mode': 6, 'offset': -30},
    'walls_b': {'block_size': 31, 'c': 0, 'adaptive_method': 1, 'invert': False},
    'sec_close': {'operation': 1, 'shape': 2, 'size': 31, 'iterations': 1},
    'sec_fill': {'method': 0},
    'sec_open': {'operation': 0, 'shape': 2, 'size': 25, 'iterations': 2},
    'sec_and': {'operation': _INTERSECT},
    'section': {'count': 1},
    'ridge': {'method': 0, 'polarity': 0, 'sigma_min': 1.0, 'sigma_max': 4.0, 'n_scales': 4,
              'norm_radius': 15, 'floor_pct': 40},
    'lum_sub': {'operation': _SUBTRACT},
    'tess': {'smooth': 1.0, 'depth': 0.3, 'wall_level': 0.7, 'wall_ratio': 3.0, 'min_closure': 0.8,
             'min_solidity': 0.85, 'min_area': 15, 'max_area': 0},
    'walls_a': {'block_size': 31, 'c': -2, 'adaptive_method': 1, 'invert': True},
    'lumens': {'operation': 0, 'shape': 2, 'size': 5, 'iterations': 1},
    'radial0': {'smooth': 3.0, 'ignore_border': True, 'envelope': True},
    'cells': {'min_area': 12, 'max_area': 6000, 'min_solidity': 0.82, 'overlap': 0.1, 'footprint': 2,
              'min_contrast': 10},
    'lum_cc': {'threshold': 128, 'min_area': 30, 'max_area': 500000, 'connectivity': 1, 'colorize': True,
               'show_cross': False},
    'zoning0': {'position_key': 'rho', 'value_key': 'radius', 'weight_key': 'score', 'log_values': True,
                'zones': 0, 'max_zones': 6, 'outlier_mad': 3.0, 'outlier_side': 1, 'min_items': 12,
                'core_rule': 1, 'n_boot': 0, 'seed': 0},
    'lum_med': {},
    'radial': {'smooth': 3.0, 'ignore_border': True, 'envelope': True},
    'mx_floor': {'expression': '2 * a'},
    'zoning': {'position_key': 'rho', 'value_key': 'radius', 'weight_key': 'score', 'log_values': True,
               'zones': 0, 'max_zones': 6, 'outlier_mad': 3.0, 'outlier_side': 1, 'min_items': 12,
               'core_rule': 1, 'n_boot': 50, 'seed': 0},
    'ring': {'side': 0, 'sigma': 8.0, 'band_low': 0.5, 'band_high': 1.5, 'max_step': 1, 'passes': 6},
    'mx_pts': {'radius': 2},
    'stele': {'operation': _INTERSECT},
    'mx_and': {'operation': _INTERSECT},
    'st_lum2': {'operation': _INTERSECT},
    'mx_region': {'operation': _UNION},
    'mx_open': {'operation': 0, 'shape': 2, 'size': 7, 'iterations': 1},
    'st_lum_fill': {'method': 0},
    'mx_tess': {'operation': _INTERSECT},
    'mx_mark': {'operation': _UNION},
    'mx_sel': {'mode': 0, 'connectivity': 0},
    'vessels': {'mode': 0, 'connectivity': 0},
    'mx_cand': {'operation': _UNION},
    'mx_ring': {'min_count': 5, 'size_ratio': 2.0, 'radius_tol': 0.25, 'circ_min': 0.3, 'max_candidates': 40},
    'metaxylem': {'min_area': 1000, 'max_area': 0, 'circ_min': 0.3, 'connectivity': 4},
    'ellipse_prop': {'auto_calibrate': True, 'scale_pith': 0.65, 'scale_mx': 1.0, 'scale_lpsc': 1.18,
                     'scale_endo': 1.32, 'scale_inner_cortex': 1.88, 'scale_outer_cortex': 2.45,
                     'scale_rhizodermis': 2.8, 'show_shells': True, 'shell_thickness': 2},
}

# Parameters of the publication figure (template node 'pub_fig').
PUBLICATION_PARAMS = {'canvas_mode': 'clean_white', 'zone_opacity': 0.32, 'cell_opacity': 0.9, 'pt_to_px': 1.33,
                      'complete_steles': True, 'hatch_lacunae': True, 'lacunae_min_area': 25,
                      'draw_legend': True, 'draw_scale_bar': True, 'scale_bar_um': 200, 'pixel_size_um': 0.5}

SHARED_STEPS = 31   # nodes run once (src .. stele)
SEARCH_STEPS = 13   # nodes run by each vessel-ring search (mx_and .. ellipse_prop)
TOTAL_STEPS = SHARED_STEPS + len(SEARCHES) * SEARCH_STEPS


def load_plugins():
    """Import the plugin modules (registering their node classes); returns the class registry."""
    for module in sorted(set(PLUGINS.values())):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            importlib.import_module(f'plugins.{module}')
    import registry
    return registry.NODE_CLASS_REGISTRY


def node_class(type_id):
    cls = load_plugins().get(type_id)
    if cls is None:
        raise KeyError(f'no plugin class for node type {type_id}')
    return cls


def output(result, key):
    """Output `key` of a node result, matched case-insensitively as the engine does (None if absent)."""
    if result is None:
        return None
    val = result.get(key)
    if val is None:
        val = {k.lower(): v for k, v in result.items()}.get(key)
    return val


class _Runner:
    """Runs nodes one at a time and keeps their outputs under the template's node ids."""

    def __init__(self, registry, results=None, on_step=None, step=0):
        self.registry = registry
        self.results = {} if results is None else results
        self.on_step = on_step
        self.step = step

    def out(self, node_id, key):
        return output(self.results.get(node_id), key)

    def node(self, node_id, type_id, params=None, **inputs):
        """Run one node. Inputs that are None are not connected, as in the engine; an input whose
        name is also a parameter replaces that parameter."""
        if self.on_step is not None:
            self.on_step(self.step, TOTAL_STEPS, node_id)
        self.step += 1
        connected = {k: v for k, v in inputs.items() if v is not None}
        params = {**PARAMS[node_id], **(params or {})}
        params.update({k: v for k, v in connected.items() if k in params})
        cls = self.registry[type_id]
        try:
            proc = cls()
        except TypeError:
            proc = cls(None)
        self.results[node_id] = proc.process({'raw_frame': None, **connected}, params) or {}
        return self.results[node_id]


def _shared(r, image_path):
    """Nodes upstream of the vessel search: section, walls, cells, radial zoning, stele."""
    o = r.out
    r.node('src', 'input_image', {'path': image_path})
    r.node('gray', 'filter_gray', image=o('src', 'main'))
    r.node('roi', 'util_roi_polygon', image=o('src', 'main'))
    r.node('pol', 'filter_auto_polarity', image=o('gray', 'main'))
    r.node('sec_blur', 'filter_blur', image=o('pol', 'main'))
    r.node('med3', 'filter_blur', image=o('pol', 'main'))
    r.node('walls', 'cv_adaptive_threshold', image=o('pol', 'main'))
    r.node('mx_lum', 'cv_adaptive_threshold', image=o('pol', 'main'))
    r.node('sec_thr', 'feat_threshold_adv', image=o('sec_blur', 'main'))
    r.node('walls_b', 'cv_adaptive_threshold', image=o('med3', 'main'))
    r.node('sec_close', 'feat_morphology_adv', mask=o('sec_thr', 'mask'))
    r.node('sec_fill', 'fill_holes', mask=o('sec_close', 'mask'))
    r.node('sec_open', 'feat_morphology_adv', mask=o('sec_fill', 'main'))
    r.node('sec_and', 'mask_operations', mask_a=o('sec_open', 'mask'), mask_b=o('roi', 'mask'))
    r.node('section', 'mask_keep_largest', mask=o('sec_and', 'mask'))
    r.node('ridge', 'filter_ridge', image=o('pol', 'main'), mask=o('section', 'mask'))
    r.node('lum_sub', 'mask_operations', mask_a=o('section', 'mask'), mask_b=o('walls', 'main'))
    r.node('tess', 'seg_cell_tessellation', walls=o('ridge', 'ridge'), mask=o('section', 'mask'))
    r.node('walls_a', 'cv_adaptive_threshold', image=o('ridge', 'main'))
    r.node('lumens', 'feat_morphology_adv', mask=o('lum_sub', 'mask'))
    r.node('radial0', 'geom_radial_coords', mask=o('section', 'mask'), items=o('tess', 'cells'))
    r.node('cells', 'seg_cells_from_walls', walls=o('walls_a', 'main'), walls_2=o('walls_b', 'main'),
           region=o('section', 'mask'), existing=o('tess', 'resolved_labels'), image=o('pol', 'main'))
    r.node('lum_cc', 'sci_connected_components', image=o('lumens', 'mask'))
    r.node('zoning0', 'sci_profile_zoning', items=o('radial0', 'items'), position=o('radial0', 'position'))
    r.node('lum_med', 'sci_stats', data_list=o('lum_cc', 'areas'))
    r.node('radial', 'geom_radial_coords', mask=o('section', 'mask'), center_mask=o('zoning0', 'core'),
           items=o('tess', 'cells'))
    r.node('mx_floor', 'math_expr', **{'0_med': o('lum_med', 'median')})
    r.node('zoning', 'sci_profile_zoning', items=o('radial', 'items'), position=o('radial', 'position'))
    r.node('ring', 'geom_ring_contour', image=o('pol', 'main'), prior=o('zoning', 'core'),
           region=o('section', 'mask'))
    r.node('mx_pts', 'points_to_mask', points=o('zoning', 'outliers'), reference=o('src', 'main'))
    r.node('stele', 'mask_operations', mask_a=o('ring', 'mask'), mask_b=o('section', 'mask'))


def _vessel_search(r, search):
    """Metaxylem ring and ellipse propagation; `search` = 'stele' or 'whole' (see the module doc)."""
    o = r.out
    region = o('stele' if search == 'stele' else 'section', 'mask')
    ring_params = {'select': INNERMOST_LARGE} if search == 'whole' else None
    floor = o('mx_floor', 'result')
    r.node('mx_and', 'mask_operations', mask_a=o('mx_lum', 'main'), mask_b=region)
    r.node('st_lum2', 'mask_operations', mask_a=o('lumens', 'mask'), mask_b=region)
    r.node('mx_region', 'mask_operations', mask_a=region, mask_b=o('zoning', 'core'))
    r.node('mx_open', 'feat_morphology_adv', mask=o('mx_and', 'mask'))
    r.node('st_lum_fill', 'fill_holes', mask=o('st_lum2', 'mask'))
    r.node('mx_tess', 'mask_operations', mask_a=o('cells', 'interiors'), mask_b=o('mx_region', 'mask'))
    r.node('mx_mark', 'mask_operations', mask_a=o('mx_open', 'mask'), mask_b=o('mx_pts', 'mask'))
    r.node('mx_sel', 'mask_select_by_marker', mask=o('mx_tess', 'mask'), marker=o('mx_pts', 'mask'))
    r.node('vessels', 'mask_select_by_marker', mask=o('st_lum_fill', 'main'), marker=o('mx_mark', 'mask'))
    r.node('mx_cand', 'mask_operations', mask_a=o('vessels', 'mask'), mask_b=o('mx_sel', 'mask'))
    r.node('mx_ring', 'geom_ring_pattern', ring_params, mask=o('mx_cand', 'mask'), min_area=floor)
    r.node('metaxylem', 'filter_blob_filter', mask=o('mx_ring', 'mask'), min_area=floor)
    r.node('ellipse_prop', 'geom_ellipse_propagation', landmarks=o('metaxylem', 'mask'),
           boundary=o('section', 'mask'), labels=o('cells', 'labels'), image=o('cells', 'main'))


def run(image_path, searches=SEARCHES, on_step=None):
    """Run the pipeline on one image file. Returns {search: {node_id: outputs}}.

    `on_step(index, total, node_id)` is called before each node runs (progress reporting).
    Every search works on its own copy of the shared outputs, as two separate template runs would.
    """
    unknown = set(searches) - set(SEARCHES)
    if unknown:
        raise ValueError(f'unknown vessel search(es): {sorted(unknown)}')
    registry = load_plugins()
    shared = _Runner(registry, on_step=on_step)
    _shared(shared, image_path)
    runs = {}
    for search in searches:
        r = _Runner(registry, copy.deepcopy(shared.results), on_step, shared.step)
        _vessel_search(r, search)
        runs[search] = r.results
        shared.step = r.step
    return runs
