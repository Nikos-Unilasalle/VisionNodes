"""Tests for geom_ring_pattern: selection of the blobs arranged as a ring by geometric consensus.

The scenes mimic a polyarch metaxylem ring (n near-equal round lumens on a circle) surrounded by
clutter: many small cells (also on concentric circles), and a few large blobs off the ring.
"""
import importlib.util
import os
import sys

import cv2
import numpy as np
import pytest

_ENGINE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ENGINE)

from registry import NODE_CLASS_REGISTRY  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'plugins.geom_ring_pattern', os.path.join(_ENGINE, 'plugins', 'geom_ring_pattern.py'))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SIZE = 800
CENTRE = (400, 400)


def _node():
    return NODE_CLASS_REGISTRY['geom_ring_pattern']()


def _ring_scene(n, ring_r=200, blob_r=26, scale=1.0, skip=(), clutter=True, seed=0):
    """Binary scene: n discs on a circle (minus `skip` indices) plus clutter."""
    rng = np.random.default_rng(seed)
    size = int(SIZE * scale)
    m = np.zeros((size, size), np.uint8)
    cx, cy = CENTRE[0] * scale, CENTRE[1] * scale
    phase = rng.uniform(0, 2 * np.pi)
    for k in range(n):
        if k in skip:
            continue
        a = phase + 2 * np.pi * k / n
        r = blob_r * scale * rng.uniform(0.9, 1.1)
        cv2.circle(m, (int(cx + ring_r * scale * np.cos(a)), int(cy + ring_r * scale * np.sin(a))),
                   int(round(r)), 255, -1)
    if clutter:
        for rr in (60, 110, 150):          # small cells on concentric circles (inner tissue)
            for k in range(int(2 * np.pi * rr / 22)):
                a = 2 * np.pi * k / int(2 * np.pi * rr / 22)
                cv2.circle(m, (int(cx + rr * scale * np.cos(a)), int(cy + rr * scale * np.sin(a))),
                           int(round(6 * scale)), 255, -1)
        for (x, y, r) in ((90, 90, 30), (700, 120, 22), (120, 690, 35)):   # large blobs off the ring
            cv2.circle(m, (int(x * scale), int(y * scale)), int(r * scale), 255, -1)
    return m


def _count(mask):
    return cv2.connectedComponents((np.asarray(mask) > 0).astype(np.uint8))[0] - 1


PARAMS = {'min_count': 5}


@pytest.mark.parametrize('n', [5, 6, 7, 8, 9, 10, 12])
def test_selects_exactly_the_ring_members(n):
    # Arrange
    scene = _ring_scene(n, blob_r=26 if n <= 9 else 18)
    # Act
    out = _node().process({'mask': scene}, PARAMS)
    # Assert
    assert out['count'] == n
    assert _count(out['mask']) == n
    assert abs(out['center_x'] - CENTRE[0]) < 5 and abs(out['center_y'] - CENTRE[1]) < 5
    assert abs(out['radius'] - 200) < 8


# Vessel centroids (offset from the ring centre, px) and areas of a real micrograph whose ring is
# irregular: no circle through five of the vessels holds the sixth within tolerance.
IRREGULAR_RING = [((-45.0, -100.7), 4255), ((84.2, -49.5), 4233), ((33.8, 94.9), 3833),
                  ((119.1, 53.8), 3696), ((-97.1, 39.5), 3592), ((-117.4, -44.6), 2102)]


def test_irregular_real_ring_keeps_all_its_vessels():
    m = np.zeros((SIZE, SIZE), np.uint8)
    for (dx, dy), area in IRREGULAR_RING:
        cv2.circle(m, (int(CENTRE[0] + dx), int(CENTRE[1] + dy)), int(round(np.sqrt(area / np.pi))), 255, -1)
    out = _node().process({'mask': m}, PARAMS)
    assert out['count'] == 6


def test_member_blobs_are_kept_pixel_exact():
    scene = _ring_scene(8)
    out = _node().process({'mask': scene}, PARAMS)
    kept = out['mask'] > 0
    assert np.all(scene[kept] > 0)                  # nothing added
    n, lab = cv2.connectedComponents((scene > 0).astype(np.uint8), connectivity=4)
    for i in np.unique(lab[kept]):
        assert np.all(kept[lab == i])               # every kept blob is whole


@pytest.mark.parametrize('scale', [0.5, 2.0])
def test_scale_free(scale):
    out = _node().process({'mask': _ring_scene(9, scale=scale)}, PARAMS)
    assert out['count'] == 9


def test_too_few_members_gives_empty_selection():
    out = _node().process({'mask': _ring_scene(4, clutter=False)}, PARAMS)
    assert out['count'] == 0
    assert not np.any(out['mask'])


def test_large_ring_preferred_to_ring_of_many_small_cells():
    # 30+ small cells per concentric circle outnumber the 7 vessels: the ring of large lumens wins
    out = _node().process({'mask': _ring_scene(7)}, PARAMS)
    assert out['count'] == 7
    assert abs(out['radius'] - 200) < 8


def test_missing_member_is_predicted_from_the_angular_gaps():
    out = _node().process({'mask': _ring_scene(9, skip=(3,))}, PARAMS)
    assert out['count'] == 8
    assert out['missing'] == 1


def test_regular_ring_has_high_regularity():
    regular = _node().process({'mask': _ring_scene(8)}, PARAMS)
    gapped = _node().process({'mask': _ring_scene(9, skip=(2, 3))}, PARAMS)
    assert regular['regularity'] > 0.9
    assert gapped['regularity'] < regular['regularity']


def test_min_area_input_ignores_smaller_blobs():
    scene = _ring_scene(6)
    out = _node().process({'mask': scene, 'min_area': 4000}, PARAMS)   # vessels are ~2100 px
    assert out['count'] == 0


def test_irregular_blobs_are_not_members():
    scene = _ring_scene(6, clutter=False)
    cv2.line(scene, (100, 100), (300, 120), 255, 9)   # elongated blobs, not round
    out = _node().process({'mask': scene}, {**PARAMS, 'circ_min': 0.3})
    assert out['count'] == 6


def test_empty_input():
    out = _node().process({'mask': None}, PARAMS)
    assert out['mask'] is None and out['count'] == 0
    out = _node().process({'mask': np.zeros((50, 50), np.uint8)}, PARAMS)
    assert out['count'] == 0


# ── RhizoFit template wiring ─────────────────────────────────────────────────

_TEMPLATE = os.path.join(os.path.dirname(_ENGINE), 'public', 'templates', 'root_predictive_ellipse_zoning.vn')


def _template_graph():
    import json
    with open(_TEMPLATE) as fh:
        vn = json.load(fh)
    types = {n['id']: n['type'] for n in vn['nodes']}
    links = {(e['source'], e['target']) for e in vn['edges']}
    return types, links


def test_metaxylem_is_selected_by_ring_consensus_not_by_size_break():
    types, links = _template_graph()
    assert types['mx_ring'] == 'geom_ring_pattern'
    assert ('mx_cand', 'mx_ring') in links and ('mx_ring', 'metaxylem') in links
    assert ('mx_cand', 'metaxylem') not in links
    assert 'mx_break' not in types


def test_tessellated_vessels_are_searched_beyond_the_stele_contour():
    # a ring of many vessels can pull the stele contour inside them
    types, links = _template_graph()
    assert ('mx_region', 'mx_tess') in links
    assert ('stele', 'mx_region') in links and ('zoning', 'mx_region') in links
