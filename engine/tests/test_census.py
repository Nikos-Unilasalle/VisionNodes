"""Territory-density census (scripts/census_lib.py)."""
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import census_lib as CS  # noqa: E402


def _tissue(cell=20, wall=3, size=400):
    """Grid of cells (lumen = cell - wall) over the whole zone."""
    labels = np.zeros((size, size), np.int32)
    lid = 1
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            labels[y + wall:y + cell, x + wall:x + cell] = lid
            lid += 1
    return labels, lid - 1


def test_complete_tissue_is_counted_exactly():
    labels, n = _tissue()
    zone = np.ones(labels.shape, bool)
    obs, tot, _ = CS.zone_census(labels, zone, np.zeros_like(zone))
    assert obs == n and abs(tot - n) <= 0.02 * n


def test_lost_cells_are_imputed_from_territory_density_walls_included():
    labels, n = _tissue()
    labels[:, :200] = 0                     # half the cells lost, walls and all
    zone = np.ones(labels.shape, bool)
    obs, tot, _ = CS.zone_census(labels, zone, np.zeros_like(zone))
    assert abs(obs - n / 2) <= 20
    assert abs(tot - n) <= 0.06 * n         # lumen-area division would give ~+40 %


def test_large_uncovered_cortex_region_is_kept_as_lacuna():
    labels, n = _tissue()
    labels[100:300, 100:300] = 0            # ~100 cells missing in one block
    zone = np.ones(labels.shape, bool)
    _, tot_imputed, _ = CS.zone_census(labels, zone, np.zeros_like(zone))
    _, tot_cortex, lac = CS.zone_census(labels, zone, np.zeros_like(zone), keep_lacunae=True)
    assert tot_imputed > tot_cortex and lac > 0
