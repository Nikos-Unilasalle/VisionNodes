"""Second-pass segmentation of faint cortex cells (scripts/cell_recovery_lib.py)."""
import os
import sys

import cv2
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import cell_recovery_lib as CR  # noqa: E402

SIZE, CELL = 400, 24


def _scene(faint_walls):
    """Left half: segmented cells (labels). Right half: unsegmented, with faint walls or empty,
    under a strong brightness gradient that defeats a global threshold."""
    xx = np.tile(np.arange(SIZE, dtype=np.float32), (SIZE, 1))
    gray = 170 + 60 * xx / SIZE
    labels = np.zeros((SIZE, SIZE), np.int32)
    lid = 1
    for y in range(0, SIZE, CELL):
        for x in range(0, SIZE, CELL):
            if x < SIZE // 2:
                labels[y + 2:y + CELL - 2, x + 2:x + CELL - 2] = lid
                lid += 1
                gray[y:y + CELL, x:x + 2] -= 80
                gray[y:y + 2, x:x + CELL] -= 80
            elif faint_walls:
                gray[y:y + CELL, x:x + 2] -= 12
                gray[y:y + 2, x:x + CELL] -= 12
    rng = np.random.default_rng(0)
    gray += rng.normal(0, 2.0, gray.shape)
    zone = np.ones((SIZE, SIZE), bool)
    return labels, np.clip(gray, 0, 255).astype(np.uint8), zone


def test_faint_wall_network_becomes_cells():
    labels, gray, zone = _scene(faint_walls=True)
    out, recovered, n = CR.recover_faint_cells(labels, gray, zone)
    right = np.zeros_like(zone)
    right[:, SIZE // 2:] = True
    assert n >= 0.6 * (SIZE // CELL) * (SIZE // 2 // CELL)
    assert recovered[right].mean() > 0.5
    assert np.array_equal(out[labels > 0], labels[labels > 0])  # first pass untouched


def test_empty_region_stays_a_lacuna():
    labels, gray, zone = _scene(faint_walls=False)
    _, recovered, n = CR.recover_faint_cells(labels, gray, zone)
    assert n == 0 and not recovered.any()


def _grid_labels(size=300, cell=20):
    labels = np.zeros((size, size), np.int32)
    lid = 1
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            labels[y:y + cell, x:x + cell] = lid  # touching cells: walls are not empty space
            lid += 1
    rho = np.tile(np.linspace(0, 3, size, dtype=np.float32), (size, 1))
    return labels, rho, np.ones((size, size), bool)


def test_expected_area_follows_rho_bands():
    labels, rho, zone = _grid_labels()
    expected = CR.expected_area_profile(labels, rho, zone)
    assert expected(1.5) == pytest.approx(20 * 20, rel=0.05)


def test_oversized_recovered_region_is_split_by_expected_size():
    labels, rho, zone = _grid_labels()
    expected = CR.expected_area_profile(labels, rho, zone)
    out = labels.copy()
    out[100:160, 100:160] = 0
    out[101:159, 101:159] = 999                      # one "cell" of ~10 expected cells
    recovered = out == 999
    res, created, n_split, n_filled = CR.check_against_polar_profile(out, recovered, rho, zone, expected)
    assert n_split == 1 and created[recovered].all()
    assert 8 <= len(np.unique(res[recovered])) <= 12


def test_small_empty_region_becomes_cells_and_large_one_stays_a_lacuna():
    labels, rho, zone = _grid_labels()
    expected = CR.expected_area_profile(labels, rho, zone)
    out = labels.copy()
    out[40:80, 40:60] = 0                              # ~2 cells wide hole: unseen cells
    out[180:280, 180:280] = 0                          # ~25 cells: aerenchyma
    res, created, _, n_filled = CR.check_against_polar_profile(out, np.zeros_like(zone), rho, zone, expected)
    assert n_filled == 1
    assert (res[42:78, 42:58] > 0).all()
    assert (res[200:260, 200:260] == 0).all()


# --------------------------------------------------------------------------- walled lacunae

def _rho_scene():
    """rho = distance to the centre / 10 px; expected cell area 100 px (10 x 10, 1 rho deep)."""
    yy, xx = np.indices((SIZE, SIZE))
    c = SIZE // 2
    r = np.hypot(yy - c, xx - c)
    labels = np.zeros((SIZE, SIZE), np.int32)
    labels[c - 5:c + 5, c + 20:c + 70] = 1                        # radial strip, 5 cells deep: lacuna
    labels[(r >= 120) & (r < 130) & (yy < c - 60)] = 2            # tangential band, one layer deep: cell
    labels[c + 100:c + 110, c - 5:c + 5] = 3                      # ordinary cell
    return labels, r / 10.0, c


def test_object_spanning_several_layers_becomes_a_lacuna():
    labels, rho, _ = _rho_scene()
    zone = np.ones_like(labels, bool)
    out, n = CR.lacunae_from_cells(labels, rho, zone, lambda _r: 100.0, px_per_rho=10.0)
    assert n == 1
    assert not (out == 1).any()
    assert (out == 2).any() and (out == 3).any()


def test_large_cell_within_one_layer_stays_a_cell():
    labels, rho, _ = _rho_scene()
    assert (labels == 2).sum() > CR.LACUNA_MAX_CELLS * 100      # large, but one layer deep
    zone = np.ones_like(labels, bool)
    out, _ = CR.lacunae_from_cells(labels, rho, zone, lambda _r: 100.0, px_per_rho=10.0)
    assert (out == 2).sum() == (labels == 2).sum()


def test_thick_arc_along_the_layers_stays_cells():
    # 3.5 layers deep but spread along the circumference: a band of pale cells, not a radial sector
    yy, xx = np.indices((SIZE, SIZE))
    c = SIZE // 2
    r = np.hypot(yy - c, xx - c)
    labels = np.zeros((SIZE, SIZE), np.int32)
    labels[(r >= 100) & (r < 135) & (yy < c)] = 1
    zone = np.ones_like(labels, bool)
    out, n = CR.lacunae_from_cells(labels, r / 10.0, zone, lambda _r: 100.0, px_per_rho=10.0)
    assert n == 0 and (out == 1).sum() == (labels == 1).sum()


def _toned(labels, strip_level, lumen=120.0):
    gray = np.full(labels.shape, 60.0, np.float32)          # walls and tissue
    gray[labels > 0] = lumen
    gray[labels == 1] = strip_level
    return gray


def test_a_lacuna_must_be_as_empty_as_the_backdrop():
    labels, rho, _ = _rho_scene()
    zone = np.ones_like(labels, bool)
    full = CR.lacunae_from_cells(labels, rho, zone, lambda _r: 100.0, px_per_rho=10.0,
                                 gray=_toned(labels, 120.0), background=230.0)
    assert full[1] == 0 and (full[0] == 1).any()              # filled like a cell: stays a cell
    empty = CR.lacunae_from_cells(labels, rho, zone, lambda _r: 100.0, px_per_rho=10.0,
                                  gray=_toned(labels, 225.0), background=230.0)
    assert empty[1] == 1 and not (empty[0] == 1).any()        # as bright as the backdrop: a lacuna


def test_remove_walled_lacunae_takes_out_the_empty_sector_only():
    labels, rho, _ = _rho_scene()
    gray = _toned(labels, 225.0)
    before = labels.copy()
    out, n, lac = CR.remove_walled_lacunae(labels, gray, np.ones_like(labels, bool), rho,
                                           lambda _r: 100.0, px_per_rho=10.0, background=230.0)
    assert n == 1 and lac[labels == 1].all() and not lac[labels != 1].any()
    assert (out == 2).sum() == (labels == 2).sum() and (out == 3).sum() == (labels == 3).sum()
    assert np.array_equal(labels, before)

