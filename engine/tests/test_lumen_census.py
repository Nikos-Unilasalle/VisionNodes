"""Stele census by lumens: one cell per brightness maximum, non-convex basins split by their size."""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                'scripts'))

import lumen_census_lib as L  # noqa: E402

PITCH = 14
ROWS = COLS = 8
SHAPE = (int(ROWS * PITCH * 0.866) + PITCH, COLS * PITCH + PITCH + PITCH // 2)
NO_VESSEL = np.zeros(SHAPE, bool)


def _centres():
    """Hexagonal packing: odd rows are shifted by half a pitch."""
    return np.array([(PITCH + r * PITCH * 0.866 - PITCH // 2, PITCH + c * PITCH + (PITCH // 2 if r % 2 else 0) - PITCH // 2)
                     for r in range(ROWS) for c in range(COLS)])


def _cells(merged=()):
    """Label map of hexagonal cells (nearest centre); `merged` = pairs of cell indices sharing one label."""
    yy, xx = np.indices(SHAPE)
    c = _centres()
    labels = 1 + np.argmin((yy[..., None] - c[:, 0]) ** 2 + (xx[..., None] - c[:, 1]) ** 2, -1)
    for a, b in merged:
        labels[labels == b + 1] = a + 1
    return labels


def _image():
    img = np.full(SHAPE, 90, np.uint8)
    for y, x in _centres():
        cv2.circle(img, (int(x), int(y)), PITCH // 2 - 2, 200, -1)
    return cv2.GaussianBlur(img, (0, 0), 1.0)


def test_every_lumen_gets_its_basin_without_any_closed_wall():
    basins = L.lumen_basins(_image(), np.ones(SHAPE, bool))
    assert len(np.unique(basins)) == ROWS * COLS
    assert (basins > 0).all()                                   # the basins tile the region, walls included


def test_convex_basins_are_one_cell_each():
    whole = np.ones(SHAPE, bool)
    assert L.zone_census(_cells(), whole, NO_VESSEL) == (64, 64, 0)


def test_two_cells_sharing_one_basin_are_counted_as_two():
    pairs = [(9, 10), (20, 21), (27, 35), (42, 43), (52, 53)]   # neighbours whose common wall is not seen
    observed, total, _ = L.zone_census(_cells(pairs), np.ones(SHAPE, bool), NO_VESSEL)
    assert observed == 64 - len(pairs)
    assert total == 64


def test_a_large_convex_cell_stays_one_cell():
    yy, xx = np.indices(SHAPE)
    disc = (yy - SHAPE[0] // 2) ** 2 + (xx - SHAPE[1] // 2) ** 2 <= (1.3 * PITCH) ** 2
    labels = np.where(disc, 999, _cells())                      # one round cell over several
    observed, total, _ = L.zone_census(labels, np.ones(SHAPE, bool), NO_VESSEL)
    assert total == observed


def test_only_the_basins_of_the_zone_are_counted_and_vessels_are_left_out():
    labels = _cells()
    top = np.zeros(SHAPE, bool)
    top[:int(PITCH // 2 + 3.5 * PITCH * 0.866)] = True          # the first four rows
    assert L.zone_census(labels, top, NO_VESSEL)[1] == 4 * COLS
    vessels = np.zeros(SHAPE, bool)
    vessels[:int(PITCH // 2 + 1.5 * PITCH * 0.866)] = True       # the first two rows are vessels
    assert L.zone_census(labels, top, vessels)[1] == 2 * COLS


def test_typical_area_ignores_merged_basins_and_fragments():
    areas = [100] * 40 + [200] * 12 + [300] * 4 + [20] * 6
    assert 90 < L.typical_area(areas) < 112


def test_empty_zone():
    assert L.zone_census(_cells(), np.zeros(SHAPE, bool), NO_VESSEL) == (0, 0, 0)
