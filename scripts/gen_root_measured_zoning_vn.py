"""Generate public/templates/root_measured_zoning.vn

Fourth root template: Predictive Ellipse Zoning whose zone boundaries are MEASURED.
Starts from the Predictive Ellipse graph (gen_root_predictive_ellipse_vn.py) and inserts:

  ellipse_prior  — first Ellipse Propagation pass (anchor + prior shells) -> float ρ field
  rho_cells      — List Sample Map: every measured cell gets its elliptical ρ ('rho_e')
  profile        — Profile Zoning of log(cell radius) along ρ_e: optimal split, number of
                   zones by BIC, bootstrap interval on every boundary
  ellipse_prop   — final pass: each prior boundary snaps to the nearest measured one
                   (within Δρ tolerance); the report flags measured vs prior boundaries

Downstream nodes (zones, report, publication figure) are unchanged and keep reading
`ellipse_prop`, so the benchmark script runs on this template as-is.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import gen_root_predictive_ellipse_vn as G  # noqa: E402  (builds the base graph on import)

OUT = os.path.join(REPO, 'public', 'templates', 'root_measured_zoning.vn')
SNAP_TOLERANCE = 0.15
ABOVE_ONLY = 1
ROW_Y_EXTRA = 3720

FINAL_INPUTS = [('metaxylem', 'mask', 'landmarks'), ('section', 'mask', 'boundary'),
                ('cells', 'labels', 'labels'), ('cells', 'main', 'image')]


def _base_params(nid):
    params = next(n for n in G.NODES if n['id'] == nid)['data']['params']
    return {k: v for k, v in params.items() if k not in ('color_index', 'node_note')}


def build():
    prop = _base_params('ellipse_prop')
    f = G.frame('frame-10', 'Step 8b: Measured Zone Boundaries (Profile Zoning along ρ)',
                0, ROW_Y_EXTRA, 4, 2, 3)

    G.node('ellipse_prior', 'geom_ellipse_propagation', f, 0, 0, {**prop, 'show_shells': False},
           'PRIOR PASS: metaxylem anchor + allometric prior shells. Only its float ρ field is used.')
    for src, sport, tport in FINAL_INPUTS:
        G.edge(src, sport, 'ellipse_prior', tport)

    G.node('rho_cells', 'list_sample_map', f, 1, 0, {'key': 'rho_e', 'x_key': 'cx', 'y_key': 'cy'},
           'Each measured cell gets its elliptical ρ.')
    G.edge('tess', 'cells', 'rho_cells', 'items')
    G.edge('ellipse_prior', 'rho', 'rho_cells', 'map')

    G.node('profile', 'sci_profile_zoning', f, 2, 0,
           {'position_key': 'rho_e', 'value_key': 'radius', 'weight_key': 'score',
            'log_values': True, 'zones': 0, 'max_zones': 8, 'outlier_mad': 3.0,
            'outlier_side': ABOVE_ONLY, 'min_items': 12, 'core_rule': 1, 'n_boot': 50, 'seed': 0},
           'MEASURED BOUNDARIES: cell size along ρ is split where it changes level '
           '(number of zones by BIC, 90 % bootstrap band on each boundary). '
           'Large outliers (vessels) are set aside.')
    G.edge('rho_cells', 'items', 'profile', 'items')
    G.edge('ellipse_prior', 'rho', 'profile', 'position')

    G.node('profile_display', 'output_display', f, 3, 0)
    G.edge('profile', 'main', 'profile_display', 'main')

    G.node('profile_stats', 'dict_report_panel', f, 2, 1,
           {'title': 'Measured Boundaries (Profile Zoning)', 'groups': '', 'digits': 3})
    G.edge('profile', 'stats', 'profile_stats', 'dict')

    final = next(n for n in G.NODES if n['id'] == 'ellipse_prop')
    final['data']['params'].update(snap_tolerance=SNAP_TOLERANCE)
    final['data']['params']['node_note'] = (
        'FINAL PASS: every prior shell snaps to the nearest measured boundary within Δρ '
        f'{SNAP_TOLERANCE}; report flags measured_* vs prior.')
    G.edge('profile', 'boundaries', 'ellipse_prop', 'boundaries')

    report = next(n for n in G.NODES if n['id'] == 'report')
    report['data']['params']['title'] = 'Measured Ellipse Zoning Report'
    report['data']['params']['groups'] += (
        ' | Measured vs Prior Boundaries: measured_boundaries, measured_pith, measured_lpsc, '
        'measured_endodermis, measured_inner_cortex, measured_outer_cortex')

    return {'nodes': G.FRAMES + G.NODES, 'edges': G.EDGES, 'ui': G.vn['ui']}


if __name__ == '__main__':
    vn = build()
    with open(OUT, 'w') as fh:
        json.dump(vn, fh, indent=2, ensure_ascii=False)
    print(f"{len(G.NODES)} nodes, {len(G.EDGES)} edges, {len(G.FRAMES)} frames -> {OUT}")
