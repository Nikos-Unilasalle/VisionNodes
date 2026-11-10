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
