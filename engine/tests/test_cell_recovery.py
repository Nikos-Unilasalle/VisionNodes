"""Second-pass segmentation of faint cortex cells (scripts/cell_recovery_lib.py)."""
import os
import sys

import cv2
import numpy as np

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
