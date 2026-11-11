"""Cortical cell files (CF): the number of cell layers between the endodermis and the rhizodermis.

A file count along a fixed ray is fragile: a ray running along a radial wall picks up cells of
the neighbouring file in the same layer, and a ray crossing a lacuna loses the cells it replaces.
Here the cortex is read as a graph of touching cells and, for every cell under the rhizodermis,
CF is the fewest cells a chain must cross to reach it from the endodermis. A shortest chain never
steps sideways within a layer when it can step outward, and it goes round a lacuna along the
cells that line it, so each layer is counted once.

  inner end   cells reaching within CHAIN_SEED_DEPTH typical radial thicknesses of endo_outer (rho)
  outer end   cells touching the rhizodermis band, which follows the section contour (distance
              to the edge <= the measured outer layer), so the chain stops on the exodermis
              whatever the shape of the section; rhizodermis cells themselves are excluded
  merged cell a cell k times thicker radially than the cells it touches (CHAIN_REF_QUANTILE of
              their thicknesses) counts for k layers
"""
import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import shortest_path

import radial_zoning_lib as R

CHAIN_SEED_DEPTH = 0.3     # typical radial thicknesses: how far past endo_outer a seed cell may start
CHAIN_TOUCH_PX = 2         # px: a cell this close to the rhizodermis band touches it
WALL_REACH = 0.15          # fraction of the typical cell diameter: cells this close across a wall touch
MIN_WALL_REACH_PX = 2
CHAIN_REF_QUANTILE = 35    # percentile of the radial thicknesses of a cell and its neighbours taken as one layer


def touching_pairs(labels, reach):
    """Unique (a, b) pairs, a < b, of labelled cells that come within `reach` px of each other."""
    h, w = labels.shape
    pairs = []
    for dy in range(0, reach + 1):
        for dx in range(-reach, reach + 1):
            if (dy == 0 and dx <= 0) or dx * dx + dy * dy > reach * reach:
                continue
            a = labels[0:h - dy, max(-dx, 0):w - max(dx, 0)]
            b = labels[dy:h, max(dx, 0):w - max(-dx, 0)]
            m = (a > 0) & (b > 0) & (a != b)
            if m.any():
                pairs.append(np.stack([a[m], b[m]], 1))
    if not pairs:
        return np.zeros((0, 2), labels.dtype)
    return np.unique(np.sort(np.concatenate(pairs), 1), axis=0)


def _layer_cost(thickness, a, b, n):
    """Layers each cell spans: its radial thickness over that of the cells it touches.

    The reference is a low percentile (CHAIN_REF_QUANTILE) of the thicknesses of the cell and its
    neighbours, so a cell merged across two layers is compared with its unmerged inner and outer
    neighbours. Being local, it holds when the cortex is thicker on one side of the section.
    """
    owner = np.concatenate([a, b, np.arange(n)])
    other = np.concatenate([b, a, np.arange(n)])
    order = np.argsort(owner, kind='stable')
    owner, vals = owner[order], thickness[other[order]]
    starts = np.searchsorted(owner, np.arange(n))
    ends = np.searchsorted(owner, np.arange(n), side='right')
    ref = np.array([np.percentile(vals[s:e], CHAIN_REF_QUANTILE) for s, e in zip(starts, ends)])
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.maximum(1.0, np.nan_to_num(np.round(thickness / ref), nan=1.0, posinf=1.0))


def _cell_table(labels, section, ell):
    n = int(labels.max()) + 1
    idx = np.arange(n)
    rho = R.rho_field(labels.shape, ell)
    to_edge = cv2.distanceTransform(section.astype(np.uint8), cv2.DIST_L2, 5)
    area = np.bincount(labels.ravel(), minlength=n)
    with np.errstate(invalid='ignore', divide='ignore'):
        return {'n': n, 'area': area,
                'rho': np.bincount(labels.ravel(), rho.ravel(), minlength=n) / np.maximum(area, 1),
                'depth': np.bincount(labels.ravel(), to_edge.ravel(), minlength=n) / np.maximum(area, 1),
                'depth_min': np.asarray(ndi.minimum(to_edge, labels, idx)),
                'rho_min': np.asarray(ndi.minimum(rho, labels, idx)),
                'rho_max': np.asarray(ndi.maximum(rho, labels, idx))}


def cortical_cell_files(labels, section, ell, endo_outer, rhizo_px):
    """CF as (median, 25th, 75th percentile) over the cells under the rhizodermis.

    labels      cell label map (0 = walls / background), not modified
    section     section mask
    ell         metaxylem anchor ellipse (radial_zoning_lib)
    endo_outer  outer edge of the endodermis (rho)
    rhizo_px    width of the rhizodermis band along the contour (px)
    """
    if not np.isfinite(rhizo_px) or rhizo_px < 0:
        raise ValueError(f'invalid rhizodermis width: {rhizo_px}')
    labels = np.asarray(labels).astype(np.int64)
    section = np.asarray(section) > 0
    t = _cell_table(labels, section, ell)
    n, area = t['n'], t['area']
    rhizo = (area > 0) & (t['depth'] <= rhizo_px)
    cortex = (area > 0) & (t['rho'] > endo_outer) & ~rhizo
    cortex[0] = rhizo[0] = False
    if not cortex.any():
        raise ValueError('no cortex cell between the endodermis and the rhizodermis')
    thickness = t['rho_max'] - t['rho_min']
    typical = float(np.median(thickness[cortex]))
    reach = max(MIN_WALL_REACH_PX, int(round(WALL_REACH * np.sqrt(np.median(area[cortex])))))
    pairs = touching_pairs(labels, reach)
    a, b = (pairs[:, 0], pairs[:, 1]) if len(pairs) else (np.zeros(0, int), np.zeros(0, int))
    under_rhizo = np.zeros(n, bool)
    under_rhizo[a[cortex[a] & rhizo[b]]] = True
    under_rhizo[b[cortex[b] & rhizo[a]]] = True
    targets = np.nonzero(cortex & (under_rhizo | (t['depth_min'] <= rhizo_px + CHAIN_TOUCH_PX)))[0]
    seeds = np.nonzero(cortex & (t['rho_min'] <= endo_outer + CHAIN_SEED_DEPTH * typical))[0]
    if not len(seeds) or not len(targets):
        raise ValueError('no cell chain across the cortex')
    inner = cortex[a] & cortex[b]
    cost = _layer_cost(thickness, a[inner], b[inner], n)
    src = np.full(len(seeds), n)                           # virtual source joined to every seed
    u = np.concatenate([a[inner], b[inner], src])
    v = np.concatenate([b[inner], a[inner], seeds])
    graph = coo_matrix((cost[v], (u, v)), shape=(n + 1, n + 1)).tocsr()
    dist = shortest_path(graph, directed=True, indices=n)[targets]
    dist = dist[np.isfinite(dist)]
    if not dist.size:
        raise ValueError('no cell chain across the cortex')
    lo, med, hi = np.percentile(dist, [25, 50, 75])
    return float(med), float(lo), float(hi)
