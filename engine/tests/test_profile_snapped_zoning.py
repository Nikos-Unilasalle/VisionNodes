"""Measured zone boundaries: List Sample Map + boundary snapping in Ellipse Propagation."""
import os
import sys

import cv2
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'engine'))
sys.path.insert(0, os.path.join(REPO, 'engine', 'tests'))

import vn_headless as H  # noqa: E402

H.load_plugins()
from registry import NODE_CLASS_REGISTRY  # noqa: E402
from plugins.geom_ellipse_propagation import snap_boundaries  # noqa: E402


# --- List Sample Map --------------------------------------------------------

def test_sample_map_adds_value_at_item_position():
    field = np.arange(100, dtype=np.float32).reshape(10, 10)
    items = [{'cx': 3.2, 'cy': 1.0, 'area': 5}, {'cx': 9, 'cy': 9, 'area': 7}]

    out = NODE_CLASS_REGISTRY['list_sample_map']().process(
        {'items': items, 'map': field}, {'key': 'rho_e'})

    assert [it['rho_e'] for it in out['items']] == [13.0, 99.0]
    assert out['values'] == [13.0, 99.0]
    assert 'rho_e' not in items[0]  # inputs untouched


def test_sample_map_drops_items_outside_or_on_nan():
    field = np.ones((5, 5), np.float32)
    field[2, 2] = np.nan
    items = [{'cx': 2, 'cy': 2}, {'cx': 50, 'cy': 1}, {'cx': 1, 'cy': 1}, {'x': 1}]

    out = NODE_CLASS_REGISTRY['list_sample_map']().process(
        {'items': items, 'map': field}, {'key': 'v'})

    assert len(out['items']) == 1 and out['dropped'] == 3


def test_sample_map_without_map_returns_empty():
    out = NODE_CLASS_REGISTRY['list_sample_map']().process({'items': [{'cx': 1, 'cy': 1}]}, {})
    assert out['items'] == [] and out['values'] == []


# --- snap_boundaries ----------------------------------------------------------

PRIORS = {'pith': 0.65, 'mx': 1.0, 'endo': 1.30, 'inner': 1.85, 'outer': 2.45}


def test_snap_moves_each_prior_to_nearest_measured_boundary_within_tolerance():
    snapped, measured = snap_boundaries(PRIORS, [0.70, 1.80, 2.60], tolerance=0.2, fixed=('mx',))

    assert snapped == {'pith': 0.70, 'mx': 1.0, 'endo': 1.30, 'inner': 1.80, 'outer': 2.60}
    assert measured == {'pith': True, 'mx': False, 'endo': False, 'inner': True, 'outer': True}


def test_snap_uses_each_measured_boundary_once():
    snapped, measured = snap_boundaries({'a': 1.0, 'b': 1.1}, [1.05], tolerance=0.2)
    assert sum(measured.values()) == 1
    assert sorted(snapped.values()) == [1.05, 1.1] or sorted(snapped.values()) == [1.0, 1.05]


def test_snap_never_breaks_zone_order():
    snapped, _ = snap_boundaries({'a': 1.0, 'b': 1.2}, [1.25, 1.05], tolerance=0.3)
    assert snapped['a'] < snapped['b']


def test_snap_ignores_fixed_and_far_boundaries():
    snapped, measured = snap_boundaries(PRIORS, [1.02, 5.0], tolerance=0.1, fixed=('mx',))
    assert snapped == PRIORS and not any(measured.values())


# --- Ellipse Propagation with measured boundaries -------------------------------

def _anchor(h=400, w=400):
    mx = np.zeros((h, w), np.uint8)
    for k in range(6):
        th = k * np.pi / 3
        cv2.circle(mx, (int(200 + 60 * np.cos(th)), int(200 + 45 * np.sin(th))), 10, 255, -1)
    return mx


def test_ellipse_propagation_outputs_float_rho_field():
    res = NODE_CLASS_REGISTRY['geom_ellipse_propagation']().process({'landmarks': _anchor()}, {})
    rho = res['rho']
    assert rho.dtype == np.float32 and rho.shape == (400, 400)
    assert rho[200, 200] < 0.2 and rho[0, 0] > 2


def test_ellipse_propagation_snaps_to_measured_boundaries_and_reports_them():
    node = NODE_CLASS_REGISTRY['geom_ellipse_propagation']()
    params = {'auto_calibrate': False, 'snap_tolerance': 0.15}

    res = node.process({'landmarks': _anchor(), 'boundaries': [0.55, 1.95, 3.5]}, params)

    rep = res['report']
    assert rep['scale_pith'] == pytest.approx(0.55)
    assert rep['scale_inner_cortex'] == pytest.approx(1.95)
    assert rep['scale_outer_cortex'] == pytest.approx(2.45)
    assert rep['measured_pith'] is True and rep['measured_outer_cortex'] is False
    assert rep['measured_boundaries'] == 2
    pith = res['pith_mask'] > 0
    assert res['rho'][pith].max() <= 0.55 + 1e-6


def test_ellipse_propagation_without_boundaries_is_unchanged():
    node = NODE_CLASS_REGISTRY['geom_ellipse_propagation']()
    rep = node.process({'landmarks': _anchor()}, {'auto_calibrate': False})['report']
    assert rep['scale_pith'] == pytest.approx(0.65)
    assert rep['measured_boundaries'] == 0


# --- Template ------------------------------------------------------------------

TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_measured_zoning.vn')
NEW_NODES = ('ellipse_prior', 'rho_cells', 'profile', 'profile_display', 'profile_stats')


def _load_template():
    import json
    with open(TEMPLATE) as f:
        return json.load(f)


def test_measured_zoning_template_edges_hit_declared_ports():
    vn = _load_template()
    new_edges = [e for e in vn['edges'] if e['source'] in NEW_NODES or e['target'] in NEW_NODES]
    assert len(new_edges) >= 10
    assert not [e for e in new_edges if e['sourceHandle'].startswith('None') or e['targetHandle'].startswith('None')]
    assert any(e['source'] == 'profile' and e['target'] == 'ellipse_prop' for e in vn['edges'])


def test_measured_zoning_template_measures_boundaries_on_brightfield_sample():
    vn = _load_template()
    sample = os.path.join(REPO, 'samples', 'root_section_brightfield_a.jpg')

    res = H.run(vn, {'src': {'path': sample}})

    assert res['profile']['count'] >= 3
    assert res['ellipse_prop']['report']['measured_boundaries'] >= 1
    assert res['pub_fig']['predictive_report']
