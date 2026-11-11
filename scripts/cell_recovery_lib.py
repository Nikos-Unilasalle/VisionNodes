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


# --------------------------------------------------------------------------- polar size check
RHO_BIN = 0.1             # width of the rho bands of the expected-size profile
MIN_BAND_CELLS = 8        # bands with fewer reference cells borrow from their neighbours
CLUSTER_RATIO = 2.0       # a recovered region larger than this x expected area is a cluster
LACUNA_MAX_CELLS = 3.0    # an empty region up to this x expected area is unseen cells, not aerenchyma
LACUNA_MIN_CELLS = 0.4    # ... and at least this x expected area
MIN_LACUNA_SOLIDITY = 0.8


def _centroids(labels):
    n = int(labels.max())
    area = np.bincount(labels.ravel(), minlength=n + 1).astype(float)
    ys, xs = np.indices(labels.shape)
    cy = np.bincount(labels.ravel(), ys.ravel(), minlength=n + 1) / np.maximum(area, 1)
    cx = np.bincount(labels.ravel(), xs.ravel(), minlength=n + 1) / np.maximum(area, 1)
    return area, cy, cx


def expected_area_profile(labels, rho, zone):
    """Expected cell area as a function of rho: median area of the reference (first-pass) cells
    whose centroid falls in each rho band of `zone`, over the whole circumference.

    Returns a callable rho -> area (px). Bands with too few cells are filled by interpolation.
    """
    area, cy, cx = _centroids(np.asarray(labels))
    ids = np.nonzero(area[1:])[0] + 1
    r, c = np.round(cy[ids]).astype(int), np.round(cx[ids]).astype(int)
    inside = np.asarray(zone)[r, c]
    ids, rr = ids[inside], np.asarray(rho)[r[inside], c[inside]]
    if len(ids) < MIN_BAND_CELLS:
        raise ValueError('too few reference cells for a size profile')
    edges = np.arange(np.floor(rr.min() / RHO_BIN) * RHO_BIN, rr.max() + RHO_BIN, RHO_BIN)
    centres, medians = [], []
    for lo in edges[:-1]:
        sel = (rr >= lo) & (rr < lo + RHO_BIN)
        if sel.sum() >= MIN_BAND_CELLS:
            centres.append(lo + RHO_BIN / 2)
            medians.append(float(np.median(area[ids[sel]])))
    if not centres:
        med = float(np.median(area[ids]))
        return lambda x: np.full(np.shape(x), med) if np.ndim(x) else med
    centres, medians = np.array(centres), np.array(medians)
    return lambda x: np.interp(x, centres, medians)


def _split(region, n):
    """Split a region into n compact parts (k-means on pixel coordinates); list of masks."""
    ys, xs = np.nonzero(region)
    pts = np.column_stack([xs, ys]).astype(np.float32)
    n = int(min(n, len(pts)))
    if n < 2:
        return [region]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(0)
    _, lab, _ = cv2.kmeans(pts, n, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    parts = []
    for k in range(n):
        m = np.zeros(region.shape, bool)
        m[ys[lab.ravel() == k], xs[lab.ravel() == k]] = True
        parts.append(m)
    return parts


def check_against_polar_profile(labels, recovered, rho, zone, expected):
    """Second look at the uncertain regions with the expected cell size at their rho.

    * recovered cells larger than CLUSTER_RATIO x expected are clusters whose thin walls were
      missed: split into round(area / expected) compact cells;
    * empty regions of `zone` between LACUNA_MIN_CELLS and LACUNA_MAX_CELLS x expected and
      convex are unseen cells, not aerenchyma: filled with round(area / expected) cells.

    Returns (labels, mask of the cells created, n_split_regions, n_filled_regions).
    """
    out = np.asarray(labels).astype(np.int32).copy()
    rho = np.asarray(rho)
    created = np.zeros(out.shape, bool)
    next_id = int(out.max()) + 1
    n_split = n_filled = 0

    area, cy, cx = _centroids(out)
    for lid in np.unique(out[recovered]):
        if lid == 0:
            continue
        exp_a = float(expected(rho[int(round(cy[lid])), int(round(cx[lid]))]))
        if area[lid] <= CLUSTER_RATIO * exp_a:
            continue
        region = out == lid
        parts = _split(region, round(area[lid] / exp_a))
        for p in parts[1:]:
            out[p] = next_id
            next_id += 1
        created |= region
        n_split += 1

    empty = np.asarray(zone) & (out == 0)
    n, lab, stats, cents = cv2.connectedComponentsWithStats(empty.astype(np.uint8))
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        cxi, cyi = cents[i]
        exp_a = float(expected(rho[int(round(cyi)), int(round(cxi))]))
        if not LACUNA_MIN_CELLS * exp_a <= a <= LACUNA_MAX_CELLS * exp_a:
            continue
        region = lab == i
        cnts, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if a / max(cv2.contourArea(cv2.convexHull(cnts[0])), 1.0) < MIN_LACUNA_SOLIDITY:
            continue
        for p in _split(region, max(1, round(a / exp_a))):
            out[p] = next_id
            next_id += 1
        created |= region
        n_filled += 1
    return out, created, n_split, n_filled


FRAGMENT_RATIO = 0.25     # cortex objects below this x expected area at their rho are wall fragments


def drop_fragments(labels, rho, zone, expected):
    """Labels without the tiny objects of `zone` (intercellular spaces, wall fragments).

    An object whose area is under FRAGMENT_RATIO x the expected cell area at its rho is not a
    cell. Returns (labels, number dropped); the input is not modified.
    """
    out = np.asarray(labels).astype(np.int32).copy()
    area, cy, cx = _centroids(out)
    ids = np.nonzero(area[1:])[0] + 1
    r, c = np.round(cy[ids]).astype(int), np.round(cx[ids]).astype(int)
    inside = np.asarray(zone)[r, c]
    exp_a = expected(np.asarray(rho)[r, c])
    tiny = ids[inside & (area[ids] < FRAGMENT_RATIO * exp_a)]
    out[np.isin(out, tiny)] = 0
    return out, len(tiny)


# --------------------------------------------------------------------------- walled lacunae
#
# An aerenchyma lacuna whose border walls are intact is enclosed like a cell, so the first
# segmentation outlines it as one giant object, or cuts it into cell-sized pieces along lines
# where the image shows no wall at all. Two rules recover it:
#   1. a cell is a region closed by walls: neighbours whose shared border shows no wall (less
#      than WALL_LESS x the darkness of a typical border of the zone, after illumination
#      flattening) merge. On bright-field micrographs the interior texture is half as contrasted
#      as a wall, so the criterion is relative to the walls, not to the noise; pale walls keep
#      20 % or more of a typical wall's contrast, wall-less watershed lines about 2 %;
#   2. a lacuna is a radial sector spanning several layers: an object larger than
#      LACUNA_MAX_CELLS expected cells at its rho, deeper than LACUNA_MIN_DEPTH cell sizes along
#      rho and not elongated along the layers (spread along rho / spread along the tangent >=
#      LACUNA_MIN_ELONGATION) is aerenchyma, not a cell. Lysigenous aerenchyma forms sectors
#      separated by radial bridges of living cells; a band of pale cells along a layer, or a
#      large cell confined to one layer, stays cells.

SEAM_WINDOW = 5           # px; a seam pixel sees two different labels within this window
MIN_SEAM = 0.3            # seams shorter than this x cell diameter are corner contacts, not borders
LACUNA_MIN_DEPTH = 3.0    # radial extent of a lacuna, in expected cell sizes (sqrt of the area)
LACUNA_MIN_ELONGATION = 0.8  # spread along rho / spread along the tangent of a lacuna
WALL_LESS = 0.1           # a border with less than this x the contrast of a typical border has no wall


def _flatten(gray, cell_d):
    g = np.asarray(gray, np.float32)
    return cv2.GaussianBlur(g, (0, 0), 0.8) - cv2.GaussianBlur(g, (0, 0), 0.6 * cell_d)


def _seams(labels, zone):
    """(rows, cols, lower label, upper label) of the pixels of `zone` that see two labels nearby."""
    k = np.ones((SEAM_WINDOW, SEAM_WINDOW), np.uint8)
    lab = np.where(zone, labels, 0).astype(np.float32)
    hi = cv2.dilate(lab, k)
    lo = cv2.erode(np.where(lab > 0, lab, np.float32(np.inf)), k)
    seam = zone & np.isfinite(lo) & (hi > lo)
    r, c = np.nonzero(seam)
    return r, c, lo[r, c].astype(np.int64), hi[r, c].astype(np.int64)


def _find(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _interior_levels(labels, flat, zone, n):
    """Median flattened level of the interior of every object (away from its borders)."""
    core = cv2.erode((zone & (labels > 0)).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    core &= cv2.erode(labels.astype(np.float32), np.ones((5, 5), np.uint8)) == labels  # one label around
    med = np.zeros(n)
    for i in np.unique(labels[core]):
        med[i] = np.median(flat[core & (labels == i)])
    return med


def merge_wall_less(labels, gray, zone):
    """Label map where neighbouring objects of `zone` with no wall between them are merged.

    A border has no wall when it is darker than the two interiors by less than WALL_LESS x the
    contrast of a typical border of the zone. Returns (new label map, number of merges). Inputs
    are not modified.
    """
    labels = np.asarray(labels).astype(np.int32)
    ref = reference_cell_area(labels, zone)
    cell_d = 2 * np.sqrt(ref / np.pi)
    flat = _flatten(gray, cell_d)
    r, c, lo, hi = _seams(labels, zone)
    if not len(r):
        return labels.copy(), 0
    n = int(labels.max()) + 1
    med = _interior_levels(labels, flat, zone, n)
    pair = lo * n + hi
    pairs, inv = np.unique(pair, return_inverse=True)
    seam_lvl = np.array([np.median(flat[r[inv == k], c[inv == k]]) for k in range(len(pairs))])
    seam_len = np.bincount(inv, minlength=len(pairs))
    contrast = 0.5 * (med[pairs // n] + med[pairs % n]) - seam_lvl
    typical = float(np.median(contrast[seam_len >= MIN_SEAM * cell_d])) if (seam_len >= MIN_SEAM * cell_d).any() else 0.0
    if typical <= 0:
        return labels.copy(), 0
    parent = np.arange(n)
    merges = 0
    for k, p in enumerate(pairs):
        if seam_len[k] < MIN_SEAM * cell_d or contrast[k] >= WALL_LESS * typical:
            continue
        ra, rb = _find(parent, int(p // n)), _find(parent, int(p % n))
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
            merges += 1
    if not merges:
        return labels.copy(), 0
    root = np.array([_find(parent, i) for i in range(n)])
    out = root[labels]
    # the border pixels between merged pieces join the merged object
    k = np.ones((SEAM_WINDOW, SEAM_WINDOW), np.uint8)
    near_hi = cv2.dilate(out.astype(np.float32), k)
    near_lo = cv2.erode(np.where(out > 0, out, np.float32(np.inf)).astype(np.float32), k)
    merged_roots = np.unique(root[root != np.arange(n)])
    fill = zone & (labels == 0) & (near_hi == near_lo) & np.isin(near_hi.astype(np.int64), merged_roots)
    out[fill] = near_hi[fill].astype(np.int32)
    return out.astype(np.int32), merges


def radial_elongation(mask, grad):
    """Spread of `mask` along the rho direction at its centroid / spread along the tangent.

    `grad` is np.gradient(rho) (rows, cols). Above 1: a radial sector; below 1: a band along a layer.
    """
    ys, xs = np.nonzero(mask)
    cy, cx = ys.mean(), xs.mean()
    iy, ix = int(round(cy)), int(round(cx))
    g = np.array([grad[1][iy, ix], grad[0][iy, ix]])
    g /= np.linalg.norm(g) + 1e-12
    d = np.column_stack([xs - cx, ys - cy])
    return float((d @ g).std() / max((d @ np.array([-g[1], g[0]])).std(), 1e-6))


def lacunae_from_cells(labels, rho, zone, expected, px_per_rho):
    """Label map without the objects of `zone` that are aerenchyma lacunae, not cells.

    An object is a lacuna when its area exceeds LACUNA_MAX_CELLS x the expected cell area at its
    rho, its radial extent exceeds LACUNA_MIN_DEPTH expected cell sizes and it is not elongated
    along the layers (radial_elongation >= LACUNA_MIN_ELONGATION). Returns (new label map,
    number of lacunae). Inputs are not modified.
    """
    out = np.asarray(labels).astype(np.int32).copy()
    rho = np.asarray(rho, np.float64)
    grad = np.gradient(rho)
    area, cy, cx = _centroids(out)
    removed = 0
    for i in np.unique(out[zone & (out > 0)]):
        e = float(expected(rho[int(round(cy[i])), int(round(cx[i]))]))
        if area[i] <= LACUNA_MAX_CELLS * e:
            continue
        m = out == i
        depth = (rho[m].max() - rho[m].min()) * px_per_rho / np.sqrt(e)
        if depth > LACUNA_MIN_DEPTH and radial_elongation(m, grad) >= LACUNA_MIN_ELONGATION:
            out[m] = 0
            removed += 1
    return out, removed


def remove_walled_lacunae(labels, gray, zone, rho, expected, px_per_rho):
    """Label map without the walled lacunae of `zone`; every other object is left as it was.

    Wall-less neighbours are merged only to recognise a lacuna (merge_wall_less, then
    lacunae_from_cells); pieces of a merged region that is not a lacuna keep their own labels.
    Returns (new label map, number of lacunae, lacuna mask). Inputs are not modified.
    """
    labels = np.asarray(labels).astype(np.int32)
    merged, _ = merge_wall_less(labels, gray, zone)
    kept, n = lacunae_from_cells(merged, rho, zone, expected, px_per_rho)
    lacuna = (merged > 0) & (kept == 0)
    out = labels.copy()
    out[lacuna] = 0
    return out, n, lacuna
