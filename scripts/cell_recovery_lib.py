"""Second-pass segmentation of faint cells inside unresolved regions of the cortex.

Thin, pale cell walls (typically the large parenchyma cells of the inner cortex in bright
field) are missed by the first segmentation; the region they cover is then empty in the label
map and would be counted as aerenchyma. Each empty region is re-examined on its own:

  1. Illumination flattening: grey minus a blur of about one cell diameter, which removes the
     brightness gradient across the region (a global threshold, Otsu included, only separates
     that gradient).
  2. Walls = pixels darker than the region's median by K robust SDs, kept when they form line
     pieces at least half a cell long (isolated noise specks are dropped).
  3. Cells = watershed of the distance to the walls, seeded at its maxima.
  4. The region is accepted as tissue when cell-sized, convex basins cover most of it; it is
     then added to the label map. Otherwise it stays empty: a true lacuna has no wall network.
"""
import cv2
import numpy as np
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

WALL_K_MAD = 1.0          # wall = darker than the region median by this many robust SDs
MIN_WALL_PIECE = 0.5      # wall pieces shorter than this x cell diameter are noise
MIN_REGION_CELLS = 2.0    # regions smaller than this x reference cell area are not re-examined
CELL_AREA_RANGE = (0.25, 6.0)  # accepted basin area, x reference cell area
MIN_SOLIDITY = 0.8
MIN_COVER = 0.3           # share of the region the accepted cells must cover


def reference_cell_area(labels, zone):
    """Median area of the segmented cells whose pixels fall in `zone`."""
    ids = np.unique(labels[zone & (labels > 0)])
    if not len(ids):
        raise ValueError('no segmented cell in the zone')
    return float(np.median(np.bincount(labels.ravel())[ids]))


def _basins(region, flat, ref, cell_d):
    """Watershed basins of one empty region; returns (accepted basin masks, cover share)."""
    v = flat[region]
    med = float(np.median(v))
    mad = 1.4826 * float(np.median(np.abs(v - med)))
    walls = region & (flat < med - WALL_K_MAD * mad)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(walls.astype(np.uint8))
    walls = np.isin(lab, [j for j in range(1, n) if stats[j, cv2.CC_STAT_AREA] >= MIN_WALL_PIECE * cell_d])
    free = region & ~cv2.dilate(walls.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    dist = cv2.distanceTransform(free.astype(np.uint8), cv2.DIST_L2, 5)
    peaks = peak_local_max(dist, min_distance=max(2, int(0.35 * cell_d)), threshold_abs=0.2 * cell_d,
                           labels=free.astype(np.int32))
    if not len(peaks):
        return [], 0.0
    markers = np.zeros(region.shape, np.int32)
    markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    basins = watershed(-dist, markers, mask=region)
    lo, hi = CELL_AREA_RANGE[0] * ref, CELL_AREA_RANGE[1] * ref
    kept, covered = [], 0
    for j in range(1, len(peaks) + 1):
        b = basins == j
        a = int(b.sum())
        if not lo <= a <= hi:
            continue
        cnts, _ = cv2.findContours(b.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if a / max(cv2.contourArea(cv2.convexHull(cnts[0])), 1.0) < MIN_SOLIDITY:
            continue
        kept.append(b)
        covered += a
    return kept, covered / max(int(region.sum()), 1)


def recover_faint_cells(labels, gray, zone):
    """Label map with the faint cells found in the empty regions of `zone` added.

    Returns (new label map, recovered-cell mask, number of cells added). Inputs are not modified.
    """
    labels = np.asarray(labels)
    ref = reference_cell_area(labels, zone)
    cell_d = 2 * np.sqrt(ref / np.pi)
    g = np.asarray(gray, np.float32)
    flat = cv2.GaussianBlur(g, (0, 0), 0.8) - cv2.GaussianBlur(g, (0, 0), 0.6 * cell_d)
    empty = zone & (labels == 0)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(empty.astype(np.uint8))
    out = labels.astype(np.int32).copy()
    next_id = int(out.max()) + 1
    added = 0
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < MIN_REGION_CELLS * ref:
            continue
        cells, cover = _basins(lab == i, flat, ref, cell_d)
        if cover < MIN_COVER:
            continue
        for b in cells:
            out[b & (out == 0)] = next_id
            next_id += 1
            added += 1
    return out, (out > 0) & (labels == 0), added
