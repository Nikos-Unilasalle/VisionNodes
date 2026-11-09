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
