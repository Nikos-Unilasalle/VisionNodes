"""Measured tissue boundaries from radial profiles (scripts/radial_zoning_lib.py)."""
import os
import sys

import cv2
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
sys.path.insert(0, os.path.join(REPO, 'engine'))
sys.path.insert(0, os.path.join(REPO, 'engine', 'tests'))

import radial_zoning_lib as R  # noqa: E402

SIZE, CENTER, RING_R = 900, 450, 80


def _synthetic_section(endo_rho=1.4, cortex_rho=2.4, edge_rho=3.0, seed=0):
    """Line drawing: 6 vessels on a ring (rho = 1 at their outer edge), small cells inside endo_rho,
    large cells up to cortex_rho, small cells again up to the edge."""
    rng = np.random.default_rng(seed)
    img = np.full((SIZE, SIZE), 255, np.uint8)
    yy, xx = np.indices(img.shape)
    r = np.hypot(xx - CENTER, yy - CENTER)
    section = r <= edge_rho * RING_R
    # Voronoi-like cells: random seeds whose density depends on rho
    pts = []
    for rho_lo, rho_hi, n in ((0.1, endo_rho, 900), (endo_rho, cortex_rho, 350), (cortex_rho, edge_rho, 1400)):
        rad = RING_R * np.sqrt(rng.uniform(rho_lo ** 2, rho_hi ** 2, n))
        ang = rng.uniform(0, 2 * np.pi, n)
        pts += list(zip(CENTER + rad * np.cos(ang), CENTER + rad * np.sin(ang)))
    sub = cv2.Subdiv2D((0, 0, SIZE, SIZE))
    for p in pts:
        sub.insert((float(p[0]), float(p[1])))
    facets, _ = sub.getVoronoiFacetList([])
    for f in facets:
        cv2.polylines(img, [f.astype(np.int32)], True, 0, 2)
    img[~section] = 255
    mx = np.zeros_like(img)
    for k in range(6):
        th = k * np.pi / 3
        c = (int(CENTER + 0.85 * RING_R * np.cos(th)), int(CENTER + 0.85 * RING_R * np.sin(th)))
        cv2.circle(img, c, 12, 255, -1)
        cv2.circle(img, c, 12, 0, 2)
        cv2.circle(mx, c, 13, 255, -1)
    return img, section, mx


@pytest.fixture(scope='module')
def measured():
    img, section, mx = _synthetic_section()
    b, masks, ell, prof = R.measure_boundaries(img, section, mx, kind='drawing', n_boot=20)
    return b, masks, section


def test_change_points_recover_the_two_cortical_boundaries(measured):
    b, _, _ = measured
    # rho = 1 sits on the outer edge of the vessels (0.85 R + 13 px), so true boundaries scale by that
    unit = (0.85 * RING_R + 13) / RING_R
    assert b['endo_outer'] == pytest.approx(1.4 / unit, abs=0.12)
    assert b['cortex_transition'] == pytest.approx(2.4 / unit, abs=0.12)
    lo, hi = b['endo_outer_ci']
    assert lo <= b['endo_outer'] <= hi


def test_pith_boundary_is_the_inner_edge_of_the_vessels(measured):
    b, _, _ = measured
    unit = (0.85 * RING_R + 13) / RING_R
    assert b['pith'] == pytest.approx((0.85 * RING_R - 13) / RING_R / unit, abs=0.05)
    assert b['n_vessels'] == 6


def test_zone_masks_partition_the_section_without_overlap(measured):
    _, masks, section = measured
    stack = np.stack([m for m in masks.values()])
    assert not np.any(stack.sum(0) > 1)
    assert np.all(stack.any(0) == section)
    assert masks['rhizodermis_mask'].sum() > 0


def test_ellipse_report_carries_measured_scales(measured):
    b, _, _ = measured
    rep = R.ellipse_report({'center_x': 1.0, 'scale_pith': 0.65}, b)
    assert rep['scale_pith'] == b['pith'] and rep['scale_endodermis'] == b['endo_outer']
    assert rep['center_x'] == 1.0


def test_guess_kind_separates_drawings_from_photos():
    sec = np.ones((10, 10), bool)
    assert R.guess_kind(np.full((10, 10), 250, np.uint8), sec) == 'drawing'
    assert R.guess_kind(np.full((10, 10), 150, np.uint8), sec) == 'photo'


def test_publication_node_counts_cells_in_mask_zones():
    import vn_headless as H
    H.load_plugins()
    node = H.registry.NODE_CLASS_REGISTRY['draw_root_publication']()
    labels = np.zeros((200, 200), np.int32)
    labels[20:40, 20:40] = 1    # in the "pith" mask
    labels[150:170, 150:170] = 2  # in the "outer cortex" mask
    pith = np.zeros((200, 200), np.uint8)
    pith[:100, :100] = 255
    outer = np.zeros((200, 200), np.uint8)
    outer[100:, 100:] = 255
    inputs = {'labels': labels, 'boundary': np.full((200, 200), 255, np.uint8),
              'landmarks': np.zeros((200, 200), np.uint8), 'pith_mask': pith, 'outer_cortex_mask': outer,
              'ellipse_report': {'center_x': 100, 'center_y': 100, 'major_axis': 40, 'minor_axis': 40}}
    rep = node.process(inputs, {'zones_from_masks': True, 'use_antipodal_mirror': False,
                                'draw_legend': False})['predictive_report']
    assert rep['pith_cells_observed'] == 1
    assert rep['outer_cortex_observed'] == 1


def test_main_rise_searches_all_boundaries_when_the_core_is_the_main_zone():
    import vn_headless as H
    H.load_plugins()
    from plugins.sci_profile_zoning import _main_rise
    # innermost zone holds the largest disc share (finely resolved stele): rise at boundary 1
    edges = [0.0, 0.50, 0.69, 0.82, 0.87, 0.93, 1.0]
    medians = list(np.log([7.0, 12.5, 14.0, 10.0, 7.5, 9.5]))
    assert _main_rise(6, edges, medians, 0.8, True) == 1
    # the usual case (core before the main zone) is unchanged
    edges = [0.0, 0.45, 0.53, 0.81, 0.86, 1.0]
    medians = list(np.log([6.0, 7.0, 14.0, 9.0, 8.0]))
    assert _main_rise(5, edges, medians, 0.8, True) == 2


def _ring_of_vessels(extra=None):
    mask = np.zeros((600, 600), np.uint8)
    for k in range(6):
        th = k * np.pi / 3
        cv2.circle(mask, (int(300 + 180 * np.cos(th)), int(300 + 180 * np.sin(th))), 32, 255, -1)
    if extra is not None:
        extra(mask)
    return mask


def _count(mask):
    return cv2.connectedComponents(mask.astype(np.uint8))[0] - 1


def test_clean_vessels_drops_a_small_irregular_candidate():
    def blob(m):  # cluster of small cells: small and far from round
        for dx in (0, 14, 28):
            cv2.circle(m, (260 + dx, 300), 8, 255, -1)
        cv2.rectangle(m, (260, 296), (288, 304), 255, -1)
    assert _count(R.clean_vessels(_ring_of_vessels(blob))) == 6


def test_clean_vessels_keeps_a_small_round_vessel_and_a_leaky_one():
    mask = _ring_of_vessels()
    cv2.circle(mask, (480, 300), 32, 0, -1)
    cv2.circle(mask, (480, 300), 23, 255, -1)              # half the area, still round
    cv2.rectangle(mask, (120, 296), (175, 304), 255, -1)    # leak glued to the vessel at (120, 300)
    assert _count(R.clean_vessels(mask)) == 6


@pytest.mark.parametrize('rx, ry, expected', [(90, 60, 0.0), (60, 90, 90.0)])
def test_reported_tilt_is_the_direction_of_the_major_axis(rx, ry, expected):
    import vn_headless as H
    H.load_plugins()
    mx = np.zeros((500, 500), np.uint8)
    for k in range(6):
        th = k * np.pi / 3
        cv2.circle(mx, (int(250 + rx * np.cos(th)), int(250 + ry * np.sin(th))), 12, 255, -1)
    rep = H.registry.NODE_CLASS_REGISTRY['geom_ellipse_propagation']().process(
        {'landmarks': mx}, {'auto_calibrate': False})['report']
    tilt = rep['tilt_angle_deg'] % 180
    assert min(abs(tilt - expected), 180 - abs(tilt - expected)) < 5
    assert R.major_axis_tilt_deg(R.anchor_ellipse(mx)) == pytest.approx(tilt, abs=1e-6)
