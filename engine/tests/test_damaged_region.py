"""Damaged regions of a section: tears restored, severe partial blur found, census completed."""
import os
import sys

import cv2
import numpy as np
import pytest
from functools import partial

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import census_lib as CS  # noqa: E402
import damaged_region_lib as DR  # noqa: E402
import radial_zoning_lib as R  # noqa: E402

SIZE, C, R_ROOT, R_STELE = 700, 350, 300, 110
ELL = (float(C), float(C), 100.0, 100.0, 0.0)       # anchor ellipse: rho = r / 100
PX_PER_RHO = 100.0
BACKDROP, WALL, LUMEN = 228.0, 80.0, 200.0
GRID = 16


def _section(torn_deg=0.0):
    """Disc section; a cortex wedge of torn_deg degrees (centred on phi = 0) torn away."""
    yy, xx = np.indices((SIZE, SIZE))
    r = np.hypot(xx - C, yy - C)
    sec = r <= R_ROOT
    if torn_deg:
        phi = np.abs(np.angle(np.exp(1j * np.arctan2(yy - C, xx - C))))
        sec &= ~((phi <= np.deg2rad(torn_deg) / 2) & (r > R_STELE))
    return sec


def _micrograph(section, blur_from=None, sigma=6.0, seed=0):
    """Grid of cells inside the section; pixels with x > blur_from are defocused."""
    rng = np.random.default_rng(seed)
    img = np.full((SIZE, SIZE), LUMEN, np.float32)
    for k in range(0, SIZE, GRID):
        img[k:k + 2, :] = WALL
        img[:, k:k + 2] = WALL
    img[~section] = BACKDROP
    if blur_from is not None:
        soft = cv2.GaussianBlur(img, (0, 0), sigma)
        img[:, blur_from:] = soft[:, blur_from:]
    return np.clip(img + rng.normal(0, 3, img.shape), 0, 255).astype(np.uint8)


def _frame(section):
    return R.rho_field(section.shape, ELL), DR.phi_field(section.shape, ELL)


def _grid_labels(section):
    """One label per grid cell lumen inside the section."""
    yy, xx = np.indices((SIZE, SIZE))
    lab = (yy // GRID) * (SIZE // GRID + 1) + xx // GRID + 1
    lumen = (yy % GRID >= 2) & (xx % GRID >= 2) & section
    return np.where(lumen, lab, 0).astype(np.int32)


def test_an_intact_sharp_section_has_no_damage():
    sec = _section()
    rho, phi = _frame(sec)
    d = DR.damaged_regions(_micrograph(sec).astype(np.float32), sec, rho, phi, PX_PER_RHO)
    assert not d['torn'].any() and not d['blurred'].any()
    assert np.array_equal(d['expected_section'], sec)


@pytest.mark.parametrize('degrees', [40, 60, 90])
def test_a_torn_wedge_is_restored_to_the_round_outline(degrees):
    sec = _section(degrees)
    rho, phi = _frame(sec)
    torn, expected = DR.torn_region(sec, rho, phi, PX_PER_RHO)
    lost = _section() & ~sec
    assert (torn & lost).sum() / lost.sum() > 0.9            # the wedge comes back
    assert (torn & ~lost).sum() / lost.sum() < 0.1           # nothing outside it
    assert np.array_equal(expected, sec | torn)


def test_a_thin_crack_is_not_a_tear():
    sec = _section()
    yy, xx = np.indices((SIZE, SIZE))
    sec = sec & ~((np.abs(yy - C) <= 2) & (xx > C + R_STELE))
    rho, phi = _frame(sec)
    torn, _ = DR.torn_region(sec, rho, phi, PX_PER_RHO)
    assert torn.sum() < 0.005 * sec.sum()


def test_a_severely_blurred_side_is_found_and_a_sharp_one_is_not():
    sec = _section()
    rho, phi = _frame(sec)
    blurred = DR.blurred_region(_micrograph(sec, blur_from=C + 120).astype(np.float32), sec, rho, phi)
    xx = np.indices((SIZE, SIZE))[1]
    assert blurred[sec & (xx > C + 200)].mean() > 0.7
    assert blurred[sec & (xx < C)].mean() < 0.02


def test_a_uniformly_blurred_section_is_not_flagged():
    sec = _section()
    rho, phi = _frame(sec)
    img = _micrograph(sec, blur_from=0).astype(np.float32)
    assert not DR.blurred_region(img, sec, rho, phi).any()


def test_the_census_is_completed_over_the_damaged_part_at_the_healthy_density():
    full = _section()
    labels = _grid_labels(full)
    zone = full & (np.hypot(*(np.indices(full.shape) - C)) > R_STELE)
    none = np.zeros_like(full)
    _, truth, _ = CS.zone_census(labels, zone, none)
    xx = np.indices(full.shape)[1]
    damaged = zone & (xx > C + 150)
    merged = np.where(damaged, 0, labels)
    merged[damaged & (labels > 0)] = labels.max() + 1        # the blurred side read as one blob
    rho, phi = _frame(full)
    factor = partial(DR.polar_completion, merged, zone, damaged, none, rho, phi)
    obs, total = DR.completed_count(CS.zone_census, merged, zone, damaged, none, factor)
    assert total == pytest.approx(truth, rel=0.03)
    assert obs < truth


def test_without_damage_the_census_is_unchanged():
    sec = _section()
    labels = _grid_labels(sec)
    none = np.zeros_like(sec)
    never = lambda: pytest.fail('no damage: the completion factor is not needed')  # noqa: E731
    assert DR.completed_count(CS.zone_census, labels, sec, none, none, never) == CS.zone_census(labels, sec, none)[:2]


def test_an_outline_layer_is_completed_by_outline_length():
    sec = _section()
    xx = np.indices(sec.shape)[1]
    assert DR.outline_completion(sec, sec & (xx > C)) == pytest.approx(2.0, rel=0.05)
    assert DR.outline_completion(sec, np.zeros_like(sec)) == 1.0


def test_the_polar_completion_follows_the_layers_of_an_eccentric_section():
    """A cortex twice as wide on one side, same number of cells per layer and angle: by area the
    wide side would weigh double, by layer and angle it weighs its angle."""
    yy, xx = np.indices((SIZE, SIZE))
    r, ang = np.hypot(xx - C, yy - C), np.arctan2(yy - C, xx - C)
    outer = R_STELE + 90 * (1.5 + 0.5 * np.cos(ang))            # 135 px thick on the right, 45 px on the left
    zone = (r > R_STELE) & (r <= outer)
    depth = np.clip((r - R_STELE) / (outer - R_STELE), 0, 0.999)
    labels = np.where(zone, 1 + (depth * 6).astype(int) * 1000 + ((ang + np.pi) / (2 * np.pi) * 90).astype(int), 0)
    damaged = zone & (xx > C)                                  # the wide half
    rho, phi = _frame(zone)
    f = DR.polar_completion(labels, zone, damaged, np.zeros_like(zone), rho, phi)
    assert f == pytest.approx(2.0, rel=0.08)


def test_inputs_are_not_modified():
    sec = _section(60)
    img = _micrograph(sec, blur_from=C + 120)
    before_sec, before_img = sec.copy(), img.copy()
    rho, phi = _frame(sec)
    DR.damaged_regions(img.astype(np.float32), sec, rho, phi, PX_PER_RHO)
    assert np.array_equal(sec, before_sec) and np.array_equal(img, before_img)
