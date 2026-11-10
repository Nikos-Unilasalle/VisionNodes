"""Cell census by territory density.

Each counted cell owns a territory: its lumen grown by about a quarter of a cell diameter, so
that the territories of well-segmented neighbours tile the tissue walls included. The density
of cells per unit of territory is then applied to the part of the zone no territory covers:

    N_zone = N_obs + A_uncovered x N_obs / A_territories

Unlike dividing the uncovered area by the mean lumen area, this counts wall pixels on both
sides of the ratio and needs no wall-thickness correction. In the cortex, uncovered regions
larger than LACUNA_CELLS cells are aerenchyma and are left empty.
"""
import cv2
import numpy as np
from skimage.segmentation import expand_labels

TERRITORY_GROWTH = 0.25   # territory = lumen grown by this x the zone's median cell diameter
LACUNA_CELLS = 3.0        # uncovered cortex regions holding more cells than this are lacunae


def _centroid_ids(labels):
    n = int(labels.max())
    area = np.bincount(labels.ravel(), minlength=n + 1)
    ys, xs = np.indices(labels.shape)
    cy = np.bincount(labels.ravel(), ys.ravel(), minlength=n + 1) / np.maximum(area, 1)
    cx = np.bincount(labels.ravel(), xs.ravel(), minlength=n + 1) / np.maximum(area, 1)
    ids = np.nonzero(area[1:])[0] + 1
    return ids, area, np.round(cy[ids]).astype(int), np.round(cx[ids]).astype(int)


def zone_census(labels, zone, vessels, keep_lacunae=False):
    """(observed, estimated total, uncovered area kept as lacunae) for one zone mask."""
    labels = np.asarray(labels)
    zone = np.asarray(zone, bool) & ~np.asarray(vessels, bool)
    ids, area, r, c = _centroid_ids(labels)
    sel = ids[zone[r, c] & ~np.asarray(vessels, bool)[r, c]]
    n_obs = len(sel)
    if n_obs == 0:
        return 0, 0, 0
    diameter = 2 * np.sqrt(np.median(area[sel]) / np.pi)
    own = np.where(np.isin(labels, sel), labels, 0)
    territory = (expand_labels(own, distance=max(2, int(TERRITORY_GROWTH * diameter))) > 0) & zone
    density = n_obs / max(int(territory.sum()), 1)
    uncovered = zone & ~territory
    lacunae = 0
    if keep_lacunae:
        n, lab, stats, _ = cv2.connectedComponentsWithStats(uncovered.astype(np.uint8))
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] * density > LACUNA_CELLS:
                uncovered[lab == i] = False
                lacunae += int(stats[i, cv2.CC_STAT_AREA])
    return n_obs, int(round(n_obs + uncovered.sum() * density)), lacunae
