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


def _growth(labels, sel):
    """Territory growth (px) of the observed cells `sel`: TERRITORY_GROWTH x their median diameter."""
    area = np.bincount(np.asarray(labels).ravel())
    return max(2, int(TERRITORY_GROWTH * 2 * np.sqrt(np.median(area[sel]) / np.pi)))


def _territories(labels, zone, vessels):
    """(observed cell ids, territory mask, cells per territory pixel) of one zone; None without cells."""
    labels = np.asarray(labels)
    zone = np.asarray(zone, bool) & ~np.asarray(vessels, bool)
    ids, area, r, c = _centroid_ids(labels)
    sel = ids[zone[r, c] & ~np.asarray(vessels, bool)[r, c]]
    if len(sel) == 0:
        return None
    own = np.where(np.isin(labels, sel), labels, 0)
    territory = (expand_labels(own, distance=_growth(labels, sel)) > 0) & zone
    return sel, territory, len(sel) / max(int(territory.sum()), 1)


def _lacunae(uncovered, density):
    """Uncovered regions holding more than LACUNA_CELLS cells at the zone's density."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(uncovered.astype(np.uint8))
    big = np.zeros(n, bool)
    big[1:] = stats[1:, cv2.CC_STAT_AREA] * density > LACUNA_CELLS
    return big[lab]


def lacuna_mask(labels, zone, vessels):
    """Lacunae of one zone: uncovered by any cell territory and larger than LACUNA_CELLS cells.

    The single definition of aerenchyma used by the census, %AA and the figure: walls between
    cells lie inside the territories, and a few unseen cells are imputed, not called lacunae.
    """
    t = _territories(labels, zone, vessels)
    if t is None:
        return np.zeros(np.asarray(zone).shape, bool)
    _, territory, density = t
    zone = np.asarray(zone, bool) & ~np.asarray(vessels, bool)
    lac = _lacunae(zone & ~territory, density)
    if not lac.any():
        return lac
    # a recognised lacuna reaches the cells around it: the territory rim it lost is given back
    free = zone & (np.asarray(labels) <= 0)
    n, lab = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)
    keep = np.zeros(n, bool)
    keep[np.unique(lab[lac])] = True
    keep[0] = False
    grown = expand_labels(lac.astype(np.int32), distance=_growth(labels, t[0])) > 0
    return lac | (grown & keep[lab])


def zone_census(labels, zone, vessels, keep_lacunae=False):
    """(observed, estimated total, uncovered area kept as lacunae) for one zone mask."""
    t = _territories(labels, zone, vessels)
    if t is None:
        return 0, 0, 0
    sel, territory, density = t
    zone = np.asarray(zone, bool) & ~np.asarray(vessels, bool)
    uncovered = zone & ~territory
    lacunae = 0
    if keep_lacunae:
        lac = lacuna_mask(labels, zone, vessels)
        uncovered &= ~lac
        lacunae = int(lac.sum())
    return len(sel), int(round(len(sel) + uncovered.sum() * density)), lacunae
