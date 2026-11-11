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

def _grid(wall_free_box=None, pale_box=None):
    """Grid of walled cells (labels separated by 1-px gaps). Inside `wall_free_box` the image has
    no wall but the labels are still cut (watershed pieces of a lacuna); inside `pale_box` the
    walls are faint but present."""
    gray = np.full((SIZE, SIZE), 210, np.float32)
    labels = np.zeros((SIZE, SIZE), np.int32)
    lid = 1
    for y in range(0, SIZE, CELL):
        for x in range(0, SIZE, CELL):
            labels[y + 2:y + CELL - 1, x + 2:x + CELL - 1] = lid
            lid += 1
            gray[y:y + CELL, x:x + 2] = 90
            gray[y:y + 2, x:x + CELL] = 90
    if pale_box is not None:
        y0, y1, x0, x1 = pale_box
        g = gray[y0:y1, x0:x1]
        g[g < 200] = 185
    if wall_free_box is not None:
        y0, y1, x0, x1 = wall_free_box
        gray[y0 + 2:y1, x0 + 2:x1] = 210
    return gray, labels


def test_pieces_without_walls_between_them_are_merged():
    gray, labels = _grid(wall_free_box=(96, 168, 96, 168))   # 3 x 3 cells with no wall inside
    zone = np.ones_like(labels, bool)
    out, n = CR.merge_wall_less(labels, gray, zone)
    inside = np.unique(out[100:166, 100:166])
    assert len(inside[inside > 0]) == 1
    assert n == 8
    assert len(np.unique(out[out > 0])) == len(np.unique(labels[labels > 0])) - 8


def test_walled_cells_are_not_merged_even_with_pale_walls():
    gray, labels = _grid(pale_box=(96, 240, 96, 240))
    zone = np.ones_like(labels, bool)
    out, n = CR.merge_wall_less(labels, gray, zone)
    assert n == 0
    assert np.array_equal(out, labels)


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


def test_lacuna_rules_do_not_modify_inputs():
    gray, labels = _grid(wall_free_box=(96, 168, 96, 168))
    before = labels.copy()
    CR.merge_wall_less(labels, gray, np.ones_like(labels, bool))
    assert np.array_equal(labels, before)


def test_remove_walled_lacunae_keeps_other_pieces_unmerged():
    # wall-free block 5 cells deep along rho (lacuna) and a wall-free pair in one layer (not one)
    gray, labels = _grid(wall_free_box=(96, 216, 168, 216))
    g2, _ = _grid(wall_free_box=(312, 336, 24, 72))
    gray[312:336, 24:72] = g2[312:336, 24:72]
    yy, _ = np.indices(labels.shape)
    rho = yy / float(CELL)                       # rho grows with the row: 1 cell = 1 rho
    zone = np.ones_like(labels, bool)
    out, n, lac = CR.remove_walled_lacunae(labels, gray, zone, rho, lambda _r: CELL * CELL * 0.8,
                                           px_per_rho=float(CELL))
    assert n == 1
    assert lac[120:200, 175:210].all() and not (out[120:200, 175:210] > 0).any()
    piece = out[314:334, 26:70]
    assert len(np.unique(piece[piece > 0])) == 2               # the two pieces stay two cells
    assert out[10, 10] == labels[10, 10]


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
