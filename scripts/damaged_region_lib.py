"""Damaged regions of a section, and the census completed over them from the healthy tissue.

A micrograph can lose part of the section: torn away (a wedge, a bite out of the edge) or out of
focus (a section cut at a slant is sharp along one line and blurred away from it, until its cells
merge). Counting the cells seen there would under-estimate the section, so each zone is counted on
its healthy part and completed layer by layer in the polar frame.

  frame     (rho, phi) anchored on the metaxylem ellipse, as for the zoning
  torn      deep deficits of the section's convex hull; over the angles they span, the section
            edge is interpolated from both sides and the expected section restored up to it
  blurred   wall sharpness = high percentile of the high-pass amplitude on wall pixels, per
            (phi sector, rho band); a sector far less sharp than the sharpest sectors of its band
            is blurred. A uniformly blurred image has no sharp reference and is not flagged
  complete  a zone's rows follow its cell layers: relative depth between the zone's inner and
            outer limit at each angle (an oblique section spreads the layers on its wide side).
            Each row's healthy cells are scaled by the row's angle over its healthy angle. A layer
            along the section outline (rhizodermis) is scaled by outline length instead

A correct micrograph has no damaged region and its census is unchanged.
"""
import cv2
import numpy as np

N_EDGE_BINS = 180          # angular bins of the edge profile
TORN_DEPTH = 0.12          # rho: depth of a convex-hull deficit that marks a tear (~ two rhizodermis layers)
MIN_TORN_BINS = 2          # contiguous angular bins: thinner gaps are cracks, left to the census
N_SHARP_SECTORS = 36
SHARP_BAND_RHO = 0.4       # radial extent of a sharpness band (rho)
SHARP_PERCENTILE = 90      # wall amplitude of a sector
WALL_MARGIN = 3.0          # grey levels under the local mean: a wall pixel
MIN_WALL_SHARE = 0.15      # sectors with fewer wall (dark) pixels are lacunae, not judged
SHARP_REF_PERCENTILE = 75  # sharpest sectors of a band: the reference
BLUR_RATIO = 0.35          # sector amplitude / band reference below this: blurred enough to lose or merge
                           # cells (a sharp micrograph has its weakest sectors near 0.5)
HIGHPASS_SIGMA = 2.0       # px (working scale): wall amplitude = |grey - its Gaussian blur|
N_ROWS = 8                 # relative-depth rows of a zone for the polar completion
MIN_DAMAGED_SHARE = 0.03   # less damaged section than this: no damage (noise of the detectors)


def phi_field(shape, ell):
    """Angle in the anchored elliptical frame, [0, 2 pi)."""
    cx, cy, a, b, t = ell
    yy, xx = np.indices(shape, dtype=np.float32)
    dx, dy = xx - cx, yy - cy
    xr, yr = np.cos(t) * dx + np.sin(t) * dy, -np.sin(t) * dx + np.cos(t) * dy
    return np.mod(np.arctan2(yr / b, xr / a), 2 * np.pi)


def edge_profile(section, rho, phi):
    """rho of the section edge per angular bin (NaN where the bin holds no section)."""
    bins = _bins(phi, N_EDGE_BINS)[section]
    edge = np.full(N_EDGE_BINS, -np.inf)
    np.maximum.at(edge, bins, rho[section])
    return np.where(np.isfinite(edge), edge, np.nan)


def _bins(phi, n):
    return np.minimum((phi / (2 * np.pi) * n).astype(int), n - 1)


def _runs(flags, min_len):
    """flags kept only in circular runs of at least min_len."""
    n, out = len(flags), np.zeros_like(flags)
    if flags.all():
        return flags.copy()
    start = int(np.argmin(flags))                       # a False bin: no run wraps past it
    rolled = np.roll(flags, -start)
    idx = np.flatnonzero(np.diff(np.concatenate([[0], rolled.astype(int), [0]])))
    for s, e in zip(idx[::2], idx[1::2]):
        if e - s >= min_len:
            out[(np.arange(s, e) + start) % n] = True
    return out


def _interpolate_circular(values, missing):
    """values[missing] linearly interpolated from the nearest kept bins on both sides (circular)."""
    n = len(values)
    kept = np.flatnonzero(~missing)
    x = np.concatenate([kept - n, kept, kept + n])
    return np.where(missing, np.interp(np.arange(n), x, np.tile(values[kept], 3)), values)


def torn_region(section, rho, phi, px_per_rho):
    """(pixels torn away from the expected section, expected section).

    Tears are the deep deficits of the section's convex hull. Over the angles they span, the
    edge is interpolated from both sides and the section restored up to it.
    """
    section = np.asarray(section, bool)
    cnts, _ = cv2.findContours(section.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return np.zeros_like(section), section
    hull = np.zeros(section.shape, np.uint8)
    cv2.drawContours(hull, [cv2.convexHull(max(cnts, key=cv2.contourArea))], -1, 1, -1)
    deficit = (hull > 0) & ~section
    n, lab = cv2.connectedComponents(deficit.astype(np.uint8))
    depth = cv2.distanceTransform(deficit.astype(np.uint8), cv2.DIST_L2, 5)
    deep = np.zeros(n, bool)
    np.maximum.at(deep, lab.ravel(), depth.ravel() >= TORN_DEPTH * px_per_rho)
    deep[0] = False
    tears = deep[lab]
    if not tears.any():
        return np.zeros_like(section), section
    bins = _bins(phi, N_EDGE_BINS)
    gap = np.zeros(N_EDGE_BINS, bool)
    gap[np.unique(bins[tears])] = True
    gap = _runs(gap, MIN_TORN_BINS)
    edge = edge_profile(section, rho, phi)
    if gap.all() or not gap.any():
        return np.zeros_like(section), section
    expected = _interpolate_circular(np.nan_to_num(edge), gap | ~np.isfinite(edge))
    torn = gap[bins] & (rho <= expected[bins]) & ~section
    return torn, section | torn


def sharpness_ratio(gray, section, rho, phi):
    """Per pixel of the section: its sector's wall amplitude / the sharpest sectors of its band."""
    g = gray.astype(np.float32)
    local = cv2.GaussianBlur(g, (0, 0), HIGHPASS_SIGMA)
    hp = np.abs(g - local)
    wall = section & (g < cv2.GaussianBlur(g, (0, 0), 4 * HIGHPASS_SIGMA) - WALL_MARGIN)
    band = (rho / SHARP_BAND_RHO).astype(int)
    sector = np.minimum((phi / (2 * np.pi) * N_SHARP_SECTORS).astype(int), N_SHARP_SECTORS - 1)
    ratio = np.ones(gray.shape, np.float32)
    for k in np.unique(band[section]):
        in_band = section & (band == k)
        amp = np.full(N_SHARP_SECTORS, np.nan)
        for s in range(N_SHARP_SECTORS):
            here = in_band & (sector == s)
            v = hp[here & wall]
            if v.size >= 50 and v.size >= MIN_WALL_SHARE * here.sum():
                amp[s] = np.percentile(v, SHARP_PERCENTILE)
        if np.isfinite(amp).sum() < N_SHARP_SECTORS // 2:
            continue
        ref = np.nanpercentile(amp, SHARP_REF_PERCENTILE)
        r = np.where(np.isfinite(amp), amp / max(ref, 1e-6), 1.0)
        ratio[in_band] = r[sector[in_band]]
    return ratio


def blurred_region(gray, section, rho, phi):
    """Section pixels in sectors much less sharp than the sharpest of their band (bool)."""
    return section & (sharpness_ratio(gray, section, rho, phi) < BLUR_RATIO)


def damaged_regions(gray, section, rho, phi, px_per_rho):
    """{'torn', 'blurred', 'expected_section'} masks and their shares of the expected section.

    Below MIN_DAMAGED_SHARE a region is noise of its detector and is cleared.
    """
    section = np.asarray(section, bool)
    torn, expected = torn_region(section, rho, phi, px_per_rho)
    blurred = blurred_region(gray, section, rho, phi)
    total = max(int(expected.sum()), 1)
    if torn.sum() < MIN_DAMAGED_SHARE * total:
        torn, expected = np.zeros_like(section), section
    if blurred.sum() < MIN_DAMAGED_SHARE * total:
        blurred = np.zeros_like(section)
    return {'torn': torn, 'blurred': blurred, 'expected_section': expected,
            'torn_share': float(torn.sum() / total), 'blurred_share': float(blurred.sum() / total)}


def _row_of(zone, rho, bins):
    """Relative depth row (0..N_ROWS-1) of every pixel, between the zone's limits at its angle."""
    lo, hi = np.full(N_EDGE_BINS, np.inf), np.full(N_EDGE_BINS, -np.inf)
    np.minimum.at(lo, bins[zone], rho[zone])
    np.maximum.at(hi, bins[zone], rho[zone])
    depth = (rho - lo[bins]) / np.maximum(hi[bins] - lo[bins], 1e-6)
    return np.clip((depth * N_ROWS).astype(int), 0, N_ROWS - 1)


def polar_completion(labels, zone, damaged, vessels, rho, phi):
    """Factor completing a zone's healthy count over its damaged angles, row by row (>= 1)."""
    zone, damaged, vessels = (np.asarray(m, bool) for m in (zone, damaged, vessels))
    labels = np.asarray(labels)
    bins = _bins(phi, N_EDGE_BINS)
    rows = _row_of(zone, rho, bins)
    n = int(labels.max())
    area = np.bincount(labels.ravel(), minlength=n + 1)
    ys, xs = np.indices(labels.shape)
    ids = np.nonzero(area[1:])[0] + 1
    r = np.round(np.bincount(labels.ravel(), ys.ravel(), minlength=n + 1)[ids] / area[ids]).astype(int)
    c = np.round(np.bincount(labels.ravel(), xs.ravel(), minlength=n + 1)[ids] / area[ids]).astype(int)
    healthy_cell = (zone & ~damaged & ~vessels)[r, c]
    cell_row = rows[r, c][healthy_cell]
    scaled = counted = 0.0
    for k in range(N_ROWS):
        in_row = zone & (rows == k)
        every = np.bincount(bins[in_row], minlength=N_EDGE_BINS)
        sound = np.bincount(bins[in_row & ~damaged], minlength=N_EDGE_BINS)
        healthy_angle = float((sound / np.maximum(every, 1)).sum())
        cells = int((cell_row == k).sum())
        if healthy_angle > 0 and cells:
            scaled += cells * (every > 0).sum() / healthy_angle
            counted += cells
    return scaled / counted if counted else 1.0


def outline_completion(expected_section, damaged):
    """Factor completing a layer along the section outline: outline length over its healthy length."""
    cnts, _ = cv2.findContours(np.asarray(expected_section, np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return 1.0
    pts = max(cnts, key=cv2.contourArea).reshape(-1, 2)
    near = cv2.dilate(np.asarray(damaged, np.uint8), np.ones((5, 5), np.uint8)) > 0
    healthy = 1.0 - float(near[pts[:, 1], pts[:, 0]].mean())
    return 1.0 / healthy if healthy > 0 else 1.0


def completed_count(zone_census, labels, zone, damaged, vessels, factor, **kw):
    """(observed in the whole zone, total): the zone's healthy census times its completion factor.

    zone_census(labels, zone, vessels, **kw) -> (observed, total, lacunae) counts one region;
    factor() is called only when the zone is damaged (polar_completion or outline_completion).
    """
    zone, damaged, vessels = (np.asarray(m, bool) for m in (zone, damaged, vessels))
    observed, total, _ = zone_census(labels, zone, vessels, **kw)
    if not (zone & damaged).any():
        return observed, total
    _, healthy_total, _ = zone_census(labels, zone & ~damaged, vessels, **kw)
    return observed, int(round(healthy_total * factor()))
