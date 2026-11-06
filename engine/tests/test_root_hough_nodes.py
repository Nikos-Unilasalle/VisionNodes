"""Tests for the cell-sampling nodes (Circle Verify, Ridge Filter, Cell Tessellation, Radial
Coordinates, Profile Zoning, Sample Projection) and the Root Zoning by Cell Sampling template."""
import importlib.util
import json
import os
import sys

import cv2
import numpy as np
import pytest

_ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(_ENGINE)
sys.path.insert(0, _ENGINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import NODE_CLASS_REGISTRY  # noqa: E402


def _load(name):
    path = os.path.join(_ENGINE, 'plugins', f'{name}.py')
    spec = importlib.util.spec_from_file_location(f'plugins.{name}', path)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


for _p in ('feat_circle_verify', 'filter_ridge', 'seg_cell_tessellation', 'seg_cells_from_walls', 'geom_ring_contour',
           'geom_radial_coords', 'ml_bar_chart', 'mask_to_zones', 'mask_depth_bands', 'seg_isolated_objects',
           'sci_profile_zoning', 'sci_sample_projection', 'points_to_mask'):
    _load(_p)


def _node(type_id):
    return NODE_CLASS_REGISTRY[type_id]()


def _circle(x, y, r, w=200, h=200):
    return {'pts': [[x / w, y / h]], 'radius': r, 'relative': True}


# ── Circle Verify ────────────────────────────────────────────────────────────
def _cells_image():
    img = np.full((200, 200), 210, np.uint8)
    for x, y in ((50, 50), (100, 50), (150, 50)):
        cv2.circle(img, (x, y), 20, 70, 2)          # closed dark wall, clean bright lumen
    cv2.line(img, (30, 150), (170, 150), 70, 2)     # a lone straight wall: not a cell
    return img


def test_circle_verify_keeps_closed_cells_and_rejects_open_edges():
    img = _cells_image()
    cand = [_circle(x, 50, 20) for x in (50, 100, 150)] + [_circle(100, 135, 15)]
    out = _node('feat_circle_verify').process({'image': img, 'circles': cand}, {})
    kept = sorted(round(c['cx']) for c in out['circles_list'])
    assert kept == [50, 100, 150]
    assert out['count'] == 3 and all(c['score'] > 0 for c in out['circles_list'])


def test_circle_verify_suppresses_overlaps_and_merges_bands():
    img = _cells_image()
    out = _node('feat_circle_verify').process(
        {'image': img, 'circles': [_circle(50, 50, 20)], 'circles_2': [_circle(52, 50, 19)],
         'circles_3': [_circle(100, 50, 20)]}, {})
    assert out['count'] == 2


def test_circle_verify_dark_inside_polarity():
    img = 255 - _cells_image()
    out = _node('feat_circle_verify').process({'image': img, 'circles': [_circle(50, 50, 20)]}, {'polarity': 1})
    assert out['count'] == 1


def test_circle_verify_respects_mask():
    img = _cells_image()
    mask = np.zeros_like(img)
    mask[:, :75] = 255
    cand = [_circle(x, 50, 20) for x in (50, 100, 150)]
    out = _node('feat_circle_verify').process({'image': img, 'circles': cand, 'mask': mask}, {})
    assert out['count'] == 1


# ── Radial Coordinates ───────────────────────────────────────────────────────
def test_radial_coords_is_normalised_along_each_ray():
    mask = np.zeros((300, 400), np.uint8)
    cv2.ellipse(mask, (200, 150), (150, 75), 0, 0, 360, 255, -1)
    items = [{'cx': 275.0, 'cy': 150.0}, {'cx': 200.0, 'cy': 112.5}]   # half-way along x and y
    out = _node('geom_radial_coords').process({'mask': mask, 'items': items}, {'smooth': 0})
    assert [it['rho'] for it in out['items']] == pytest.approx([0.5, 0.5], abs=0.03)
    pos = out['position']
    assert pos[0, 0] == -1 and pos[150, 200] == pytest.approx(0, abs=0.02)
    assert pos[150, 348] == pytest.approx(1, abs=0.03)


def test_radial_coords_uses_centre_mask():
    mask = np.zeros((200, 200), np.uint8)
    cv2.circle(mask, (100, 100), 80, 255, -1)
    centre = np.zeros_like(mask)
    cv2.circle(centre, (130, 100), 5, 255, -1)
    out = _node('geom_radial_coords').process({'mask': mask, 'center_mask': centre}, {})
    assert out['center_x'] == pytest.approx(130, abs=1)


# ── Profile Zoning ───────────────────────────────────────────────────────────
def _profile_items(seed=0):
    rng = np.random.default_rng(seed)
    rho = rng.uniform(0, 1, 300)
    radius = np.where(rho < 0.4, 5.0, 12.0) * np.exp(rng.normal(0, 0.08, 300))
    items = [{'rho': float(p), 'radius': float(r), 'score': 1.0} for p, r in zip(rho, radius)]
    items += [{'rho': 0.2, 'radius': 40.0, 'score': 1.0}, {'rho': 0.25, 'radius': 38.0, 'score': 1.0}]
    return items


def test_profile_zoning_finds_size_change_and_outliers():
    pos = np.tile(np.linspace(0, 1, 200, dtype=np.float32), (50, 1))
    out = _node('sci_profile_zoning').process({'items': _profile_items(), 'position': pos},
                                              {'outlier_side': 1, 'n_boot': 30})
    assert out['count'] == 2
    assert out['boundaries'][0] == pytest.approx(0.4, abs=0.03)
    assert sorted(o['radius'] for o in out['outliers']) == [38.0, 40.0]
    lo, hi = out['stats']['boundary_1_low'], out['stats']['boundary_1_high']
    assert lo <= hi and lo < 0.45 and hi > 0.35
    zones = out['zones']
    assert zones[0, 10] == 1 and zones[0, 190] == 2
    assert out['zone_1'][0, 10] == 255 and out['zone_3'] is None
    assert out['membership'].max() <= 1


def test_profile_zoning_fixed_number_of_zones():
    out = _node('sci_profile_zoning').process({'items': _profile_items()}, {'zones': 3, 'n_boot': 0})
    assert out['count'] == 3 and len(out['boundaries']) == 2


def test_profile_zoning_single_zone_has_no_core():
    rng = np.random.default_rng(0)
    items = [{'rho': float(p), 'radius': float(5 * np.exp(rng.normal(0, 0.05))), 'score': 1.0}
             for p in np.linspace(0, 1, 60)]
    out = _node('sci_profile_zoning').process({'items': items, 'position': np.zeros((5, 5), np.float32)},
                                              {'n_boot': 10})
    assert out['count'] == 1 and out['core'] is None


def test_profile_zoning_core_is_inside_the_main_zone():
    rng = np.random.default_rng(0)
    rho = rng.uniform(0, 1, 400)
    radius = np.select([rho < 0.3, rho < 0.35, rho < 0.9], [5.0, 12.0, 13.0], 6.0) * np.exp(rng.normal(0, 0.05, 400))
    items = [{'rho': float(p), 'radius': float(r), 'score': 1.0} for p, r in zip(rho, radius)]
    pos = np.tile(np.linspace(0, 1, 100, dtype=np.float32), (10, 1))
    out = _node('sci_profile_zoning').process({'items': items, 'position': pos}, {'n_boot': 20})
    # 12 and 13 merge into the main zone, so the core stops at 0.3, not 0.35
    assert out['core_edge'] == pytest.approx(0.3, abs=0.02)
    assert out['core'][0, 10] == 255 and out['core'][0, 50] == 0
    st = out['stats']
    assert st['core_edge_low'] <= out['core_edge'] + 1e-9 <= st['core_edge_high'] + 1e-9


def test_profile_zoning_too_few_objects():
    out = _node('sci_profile_zoning').process({'items': _profile_items()[:5]}, {})
    assert out['count'] == 0 and out['zones'] is None


# ── Sample Projection ────────────────────────────────────────────────────────
def _hex_tissue(r=10, size=400):
    """Touching circles on a hexagonal lattice filling a square zone; returns (zones, centres)."""
    d = 2 * r
    pts = [(x + (d / 2 if j % 2 else 0), y) for j, y in enumerate(np.arange(r, size - r + 1, d * np.sqrt(3) / 2))
           for x in np.arange(r, size - r, d)]
    zones = np.zeros((size, size), np.int32)
    zones[:, :] = 1
    return zones, np.array(pts)


def test_sample_projection_recovers_count_from_partial_sample():
    zones, pts = _hex_tissue()
    seen = pts[pts[:, 0] < 140]                       # only a third of the zone is resolved
    items = [{'cx': float(x), 'cy': float(y), 'radius': 10.0} for x, y in seen]
    out = _node('sci_sample_projection').process({'items': items, 'zones': zones}, {'n_boot': 50})
    assert out['packing'] == pytest.approx(np.pi / (2 * np.sqrt(3)), abs=0.03)
    expected = zones.size / (np.sqrt(3) / 2 * 20 ** 2)
    assert out['total'] == pytest.approx(expected, rel=0.05)
    st = out['stats']
    assert st['zone_1_n_detected'] == len(seen)
    assert st['zone_1_completeness'] == pytest.approx(len(seen) / out['total'])


def test_sample_projection_excludes_other_population_and_converts_units():
    zones, pts = _hex_tissue()
    items = [{'cx': float(x), 'cy': float(y), 'radius': 10.0} for x, y in pts]
    vessel = [{'cx': 200.0, 'cy': 200.0, 'radius': 60.0}]
    base = _node('sci_sample_projection').process({'items': items, 'zones': zones}, {'n_boot': 0, 'packing': 0.9})
    excl = _node('sci_sample_projection').process(
        {'items': items, 'zones': zones, 'exclude': vessel, 'px_per_unit': 2.0}, {'n_boot': 0, 'packing': 0.9})
    assert excl['total'] < base['total']
    assert excl['stats']['zone_1_mean_diameter_unit'] == pytest.approx(10.0)


def test_sample_projection_skips_undersampled_zone():
    zones = np.ones((100, 100), np.int32)
    zones[:, 50:] = 2
    items = [{'cx': 10.0 + 8 * i, 'cy': 20.0, 'radius': 3.0} for i in range(5)]
    out = _node('sci_sample_projection').process({'items': items, 'zones': zones}, {'packing': 0.8, 'n_boot': 0})
    assert out['stats']['zone_2_n_estimated'] is None
    assert out['counts'][1] is None


# ── Template ─────────────────────────────────────────────────────────────────
TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_hough_zoning.vn')


@pytest.fixture(scope='module')
def template():
    import vn_headless as H
    H.load_plugins()
    with open(TEMPLATE) as fh:
        return json.load(fh)


def test_template_uses_no_root_domain_nodes(template):
    assert not any(n['type'].startswith('root_') for n in template['nodes'])


def test_template_keeps_registry_labels(template):
    import vn_headless as H
    for n in template['nodes']:
        if n['type'] != 'canvas_frame':
            assert n['data']['label'] == H.schema(n['type'])['label'] and 'userLabel' not in n['data']


ROOTSCAN_KEYS = ['RXSA', 'XSCWA', 'TCA', 'CCWA', 'CCA', '%CCA', 'AA', '%A', '#Lac', '#CF', '#CC',
                 'CSic', 'CSmc', 'CSoc', 'LA', 'TSA', 'SCWA', 'XVA', '#MX', 'TSA:RXSA', 'TSA:TCA', 'EA', 'ExA']


@pytest.mark.parametrize('sample', ['root_section_brightfield_c.jpg', 'root_section_brightfield_a.jpg',
                                    'root_section_brightfield_b.jpg'])
def test_template_reports_rootscan_variables(template, sample):
    import vn_headless as H
    path = os.path.join(REPO, 'samples', sample)
    if not os.path.exists(path):
        pytest.skip(f'missing sample {sample}')
    res = H.run(template, {'src': {'path': path}, 'zoning': {'n_boot': 10}, 'proj': {'n_boot': 20},
                           'proj_ctx': {'n_boot': 50}})
    rep = res['report']['report']
    assert all(rep.get(k) is not None for k in ROOTSCAN_KEYS), [k for k in ROOTSCAN_KEYS if rep.get(k) is None]
    assert rep['#CC_low'] <= rep['#CC'] <= rep['#CC_high']
    assert 0 < rep['cortex_measured_%'] <= 100 and 0 < rep['stele_measured_%'] <= 100
    assert rep['#CC_measured'] + rep['#CC_projected'] == pytest.approx(rep['#CC'])
    assert rep['TSA'] < rep['RXSA'] and rep['XSCWA'] < rep['RXSA']
    assert res['compose']['main'] is not None


def test_template_on_blurred_sample_c(template):
    """C: the pale, blurred inner cortex fooled the watershed template (stele 42 % of the section,
    a false lacuna). Here the stele stops at the small-cell core and no lacuna is reported.
    6 vessels by eye; the two with a ragged lumen are found as measured cells."""
    import vn_headless as H
    path = os.path.join(REPO, 'samples', 'root_section_brightfield_c.jpg')
    res = H.run(template, {'src': {'path': path}, 'zoning': {'n_boot': 20}, 'proj': {'n_boot': 20},
                           'proj_ctx': {'n_boot': 50}})
    rep = res['report']['report']
    assert 0.2 <= rep['TSA:RXSA'] <= 0.33
    assert rep['#Lac'] == 0
    assert 4 <= rep['#MX'] <= 7


def test_template_metaxylem_on_sharp_sample_a(template):
    import vn_headless as H
    path = os.path.join(REPO, 'samples', 'root_section_brightfield_a.jpg')
    res = H.run(template, {'src': {'path': path}, 'zoning': {'n_boot': 0}, 'proj': {'n_boot': 0},
                           'proj_ctx': {'n_boot': 0}})
    # 16 large vessels by eye (RootScan); the 3 smallest lumens of the ring are borderline
    assert 15 <= res['report']['report']['#MX'] <= 19
    assert 0.17 <= res['report']['report']['TSA:RXSA'] <= 0.22   # RootScan: 0.19


def test_template_follows_an_off_centre_stele_on_b(template):
    """B: section cut by the frame, stele off-centre. The size-based core alone gave 0.08–0.14;
    the ring contour, re-centred on itself, matches RootScan (0.22)."""
    import vn_headless as H
    path = os.path.join(REPO, 'samples', 'root_section_brightfield_b.jpg')
    res = H.run(template, {'src': {'path': path}, 'zoning': {'n_boot': 0}, 'proj': {'n_boot': 0},
                           'proj_ctx': {'n_boot': 0}})
    assert 0.19 <= res['report']['report']['TSA:RXSA'] <= 0.26


def test_template_report_reaches_the_ui(template):
    """The engine only sends outputs that pass _is_serializable to the UI; a report with
    more keys than its dict cap used to show every key with an empty value."""
    import contextlib
    import io

    import vn_headless as H
    with contextlib.redirect_stdout(io.StringIO()):
        import engine
    path = os.path.join(REPO, 'samples', 'root_section_brightfield_c.jpg')
    res = H.run(template, {'src': {'path': path}, 'zoning': {'n_boot': 5}, 'proj': {'n_boot': 20}})
    assert engine._is_serializable(res['report']['report'])


def test_radial_coords_ignores_the_image_frame():
    mask = np.zeros((200, 300), np.uint8)
    cv2.circle(mask, (150, 160), 80, 255, -1)        # cut by the bottom of the frame
    centre = np.zeros_like(mask)
    cv2.circle(centre, (150, 160), 3, 255, -1)
    item = [{'cx': 150.0, 'cy': 195.0}]               # towards the cut: 35 px of an 80 px radius
    out = _node('geom_radial_coords').process({'mask': mask, 'center_mask': centre, 'items': item},
                                              {'smooth': 0, 'ignore_border': True})
    cut = _node('geom_radial_coords').process({'mask': mask, 'center_mask': centre, 'items': item},
                                              {'smooth': 0, 'ignore_border': False})
    assert out['items'][0]['rho'] == pytest.approx(35 / 80, abs=0.05)
    assert cut['items'][0]['rho'] > 0.85                # the frame taken as the outline


def test_sample_projection_count_mask_shrinks_zone():
    zones, pts = _hex_tissue()
    items = [{'cx': float(x), 'cy': float(y), 'radius': 10.0} for x, y in pts]
    keep = np.zeros(zones.shape, np.uint8)
    keep[:, :200] = 255
    full = _node('sci_sample_projection').process({'items': items, 'zones': zones}, {'n_boot': 0, 'packing': 0.9})
    half = _node('sci_sample_projection').process({'items': items, 'zones': zones, 'mask': keep},
                                                  {'n_boot': 0, 'packing': 0.9})
    assert half['total'] == pytest.approx(full['total'] / 2, rel=0.02)


def _tissue_image(r=10, size=300, blur_right=False):
    """Bright lumens separated by 2-px dark walls (hexagonal cells); on the right half the walls
    are blurred away under camera noise."""
    img = np.full((size, size), 200, np.uint8)
    d = 2 * r
    for j, y in enumerate(np.arange(0, size + d, d * np.sqrt(3) / 2)):
        for x in np.arange(0, size + d, d):
            cv2.circle(img, (int(x + (r if j % 2 else 0)), int(y)), r, 60, 2)
    if blur_right:
        noisy = cv2.GaussianBlur(img, (0, 0), 10).astype(np.float32)
        noisy += np.random.default_rng(0).normal(0, 4, img.shape)
        img[:, size // 2:] = np.clip(noisy, 0, 255).astype(np.uint8)[:, size // 2:]
    return img


def test_ridge_filter_marks_walls_not_lumens():
    img = _tissue_image()
    out = _node('filter_ridge').process({'image': img}, {})
    rid = out['ridge']
    assert rid[img < 100].mean() > 3 * rid[img > 150].mean()
    assert out['main'].dtype == np.uint8


def test_cell_tessellation_resolves_sharp_cells_only():
    img = _tissue_image(blur_right=True)
    rid = _node('filter_ridge').process({'image': img}, {})['ridge']
    out = _node('seg_cell_tessellation').process({'walls': rid}, {})
    xs = np.array([c['cx'] for c in out['cells']])
    left = ((xs > 20) & (xs < 130)).sum()
    assert left >= 0.8 * (110 * 300) / (np.sqrt(3) / 2 * 20 ** 2)   # most sharp cells found
    assert (xs > 170).sum() < 0.2 * left                           # blurred half left unresolved
    assert out['unresolved'][:, 200:].mean() > out['unresolved'][:, :100].mean()
    areas = np.array([c['area'] for c in out['cells'] if 20 < c['cx'] < 130 and 20 < c['cy'] < 280])
    assert np.median(areas) == pytest.approx(np.sqrt(3) / 2 * 20 ** 2, rel=0.25)   # hexagon territory


def test_sample_projection_counts_measured_area_exactly():
    zones, pts = _hex_tissue()
    seen = pts[pts[:, 0] < 140]
    items = [{'cx': float(x), 'cy': float(y), 'area': float(np.sqrt(3) / 2 * 400)} for x, y in seen]
    measured = np.zeros(zones.shape, np.uint8)
    measured[:, :150] = 255
    out = _node('sci_sample_projection').process(
        {'items': items, 'zones': zones, 'measured': measured},
        {'size_key': 'area', 'size_kind': 2, 'packing': 1.0, 'n_boot': 20})
    st = out['stats']
    assert st['zone_1_n_detected'] == len(seen)
    assert st['zone_1_n_estimated'] == pytest.approx(len(seen) + st['zone_1_n_projected'])
    assert st['zone_1_measured_share'] == pytest.approx(150 / 400)
    assert st['zone_1_n_estimated'] == pytest.approx(len(pts), rel=0.08)
    assert st['zone_1_n_low'] >= len(seen)


def test_profile_zoning_main_rise_skips_a_large_celled_pith():
    rng = np.random.default_rng(1)
    rho = rng.uniform(0, 1, 600)
    base = np.where(rho < 0.15, 14.0, np.where(rho < 0.4, 5.0, 12.0))   # pith | stele | cortex
    items = [{'rho': float(p), 'radius': float(b * np.exp(rng.normal(0, 0.06))), 'score': 1.0}
             for p, b in zip(rho, base)]
    out = _node('sci_profile_zoning').process({'items': items},
                                              {'zones': 3, 'core_rule': 1, 'n_boot': 0, 'outlier_mad': 0})
    assert out['core_edge'] == pytest.approx(0.4, abs=0.03)


def test_points_to_mask_reads_pixel_centres():
    out = _node('points_to_mask').process({'points': [{'cx': 50.0, 'cy': 20.0}]},
                                          {'radius': 2, 'width': 100, 'height': 40})
    assert out['mask'][20, 50] == 255 and out['mask'].sum() < 255 * 30


def test_ring_contour_finds_an_off_centre_dark_body():
    img = np.full((300, 400), 200, np.uint8)
    cv2.circle(img, (200, 150), 140, 170, -1)                  # region (pale tissue)
    cv2.circle(img, (230, 165), 50, 90, -1)                     # dark inner body, off-centre
    img = np.clip(img + np.random.default_rng(0).normal(0, 6, img.shape), 0, 255).astype(np.uint8)
    region = np.zeros_like(img)
    cv2.circle(region, (200, 150), 140, 255, -1)
    prior = np.zeros_like(img)
    cv2.circle(prior, (200, 150), 60, 255, -1)                  # first guess: centred, too big
    out = _node('geom_ring_contour').process({'image': img, 'prior': prior, 'region': region}, {})
    truth = np.zeros_like(img)
    cv2.circle(truth, (230, 165), 50, 255, -1)
    inter = ((out['mask'] > 0) & (truth > 0)).sum()
    union = ((out['mask'] > 0) | (truth > 0)).sum()
    assert inter / union > 0.85
    assert out['center_x'] == pytest.approx(230, abs=4) and out['center_y'] == pytest.approx(165, abs=4)


def test_cells_from_walls_adds_only_new_cells():
    img = _tissue_image()
    walls = (img < 120).astype(np.uint8) * 255
    out = _node('seg_cells_from_walls').process({'walls': walls, 'image': img}, {'footprint': 0, 'min_contrast': 20})
    n = out['count']
    expected = (300 * 300) / (np.sqrt(3) / 2 * 20 ** 2)
    assert 0.7 * expected <= n <= 1.1 * expected
    keep = out['labels'].copy()
    keep[:, 150:] = 0                                            # trusted cells: left half only
    again = _node('seg_cells_from_walls').process({'walls': walls, 'existing': keep}, {'footprint': 0})
    assert np.array_equal(again['labels'][keep > 0], keep[keep > 0])
    assert again['added'] == pytest.approx(n - len(np.unique(keep)) + 1, abs=3)


def test_cells_from_walls_lumen_test_drops_dark_gaps():
    img = np.full((100, 100), 200, np.uint8)
    walls = np.zeros_like(img)
    cv2.rectangle(walls, (10, 10), (40, 40), 255, 2)
    cv2.rectangle(walls, (60, 10), (90, 40), 255, 2)
    img[walls > 0] = 60
    img[13:38, 63:88] = 70                                        # second box: dark inside
    out = _node('seg_cells_from_walls').process({'walls': walls, 'image': img},
                                                {'footprint': 0, 'min_contrast': 20, 'max_area': 2000})
    assert out['count'] == 1 and out['cells'][0]['cx'] < 50


def test_sample_projection_single_mask_zone():
    zones, pts = _hex_tissue()
    items = [{'cx': float(x), 'cy': float(y), 'radius': 10.0} for x, y in pts]
    mask = (zones > 0).astype(np.uint8) * 255
    a = _node('sci_sample_projection').process({'items': items, 'zones': zones}, {'n_boot': 0, 'packing': 0.9})
    b = _node('sci_sample_projection').process({'items': items, 'mask': mask}, {'n_boot': 0, 'packing': 0.9})
    assert b['total'] == pytest.approx(a['total'])


def test_bar_chart_stacks_series_b():
    out = _node('ml_bar_chart').process({'data_a': {'x': 10.0, 'y': 5.0}, 'data_b': {'x': 2.0, 'y': 4.0}},
                                        {'b_mode': 1, 'orientation': 1})
    assert out['main'] is not None and out['main'].ndim == 3


def test_masks_to_zones_later_mask_wins():
    a = np.zeros((10, 10), np.uint8); a[:, :6] = 255
    b = np.zeros((10, 10), np.uint8); b[:, 4:] = 255
    out = _node('mask_to_zones').process({'mask_1': a, 'mask_2': b}, {'names': 'left, right'})
    assert out['zones'][0, 0] == 1 and out['zones'][0, 5] == 2 and out['names'] == ['left', 'right']


def test_depth_bands_without_inner_measure_from_the_centre():
    disc = np.zeros((201, 201), np.uint8)
    cv2.circle(disc, (100, 100), 100, 255, -1)
    out = _node('mask_depth_bands').process({'outer': disc}, {'range_low': 0.0, 'range_high': 0.3})
    core = out['range_mask'] > 0
    assert core[100, 100] and not core[100, 160]
    assert core.sum() == pytest.approx(np.pi * 30 ** 2, rel=0.15)


def test_sample_projection_names_its_zone_dicts():
    zones, pts = _hex_tissue()
    zones[:, 200:] = 2
    items = [{'cx': float(x), 'cy': float(y), 'radius': 10.0} for x, y in pts]
    out = _node('sci_sample_projection').process({'items': items, 'zones': zones, 'names': ['left', 'right']},
                                                 {'n_boot': 0, 'packing': 0.9})
    assert set(out['detected_by_zone']) == {'left', 'right'}
    assert out['estimated_by_zone']['left'] == pytest.approx(out['stats']['zone_1_n_estimated'])


def test_template_counts_cells_in_five_tissues(template):
    import vn_headless as H
    path = os.path.join(REPO, 'samples', 'root_section_brightfield_c.jpg')
    res = H.run(template, {'src': {'path': path}, 'zoning': {'n_boot': 0}, 'proj': {'n_boot': 0},
                           'proj_ctx': {'n_boot': 0}})
    est = res['proj_z']['estimated_by_zone']
    assert len(est) == 5 and all(v > 0 for v in est.values())
    det = res['proj_z']['detected_by_zone']
    assert all(det[k] <= est[k] for k in est)
    assert res['chart']['main'] is not None


def test_isolated_objects_picks_the_lone_large_cell():
    lab = np.zeros((200, 200), np.int32)
    k = 1
    for y in range(10, 100, 12):                       # packed small cells (top half)
        for x in range(10, 190, 12):
            cv2.circle(lab, (x, y), 5, k, -1); k += 1
    cv2.circle(lab, (100, 160), 9, k, -1)               # large cell alone in empty tissue
    cv2.rectangle(lab, (20, 150), (60, 154), k + 1, -1)  # alone but elongated
    out = _node('seg_isolated_objects').process({'labels': lab}, {})
    assert out['count'] == 1
    assert out['items'][0]['cy'] == pytest.approx(160, abs=1)
