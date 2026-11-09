"""Measured tissue boundaries of a root cross-section, from radial density profiles.

The section is unwrapped in the metaxylem-anchored elliptical frame (rho, phi): rho = 1
on the outer envelope of the metaxylem ring. Along every iso-rho line, without any cell
segmentation, two profiles are measured per angular sector:

  darkness   mean wall darkness
  L_theta    circumferential mean linear intercept = arc length / wall crossings
             (stereological cell-size estimator); L_rho is the same along rays.

Boundaries
  pith        inner edge of the metaxylem ring (median over vessels of their minimum rho)
  metaxylem   rho = 1 by construction
  endodermis  outer edge: change point of [log L_theta, darkness] beyond the ring;
              inner edge: outer edge minus one radial cell (L_rho measured just inside)
  cortex      inner/outer transition: second change point
  rhizodermis one radial cell (measured at the section edge) along the section contour

Change points: optimal piecewise-constant split (dynamic programming) of the sector-median
profiles over rho in [1, edge]; 95 % intervals by bootstrap over angular sectors.
"""
import warnings

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

RHO_MAX, RHO_STEP = 3.2, 0.01
N_PHI = 8192
N_SECTORS = 16
N_BOOT = 200
MIN_SEG = 0.12           # minimal zone width (rho units) for the change-point search
SEARCH_FROM = 1.0        # change points are searched outside the metaxylem ring
EDGE_COVER = 0.5         # rho of the section edge = last rho where >= 50 % of rays are inside
WALL_PROMINENCE = {'drawing': 25.0, 'photo': 6.0}  # grey levels of a wall dip
MIN_VESSEL_AREA = 400    # px, same as the publication node
DRAWING_MEDIAN_GREY = 225  # median grey inside the section above which the image is a line drawing


def anchor_ellipse(mx_mask):
    """Same fit as geom_ellipse_propagation: fitEllipse on the hull of the metaxylem masks."""
    cnts, _ = cv2.findContours((np.asarray(mx_mask) > 0).astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_NONE)
    if not cnts:
        raise ValueError('no metaxylem anchor')
    (cx, cy), (w, h), ang = cv2.fitEllipse(cv2.convexHull(np.vstack(cnts)))
    return cx, cy, max(w, 10) / 2, max(h, 10) / 2, np.deg2rad(ang)


def rho_field(shape, ell):
    cx, cy, a, b, t = ell
    yy, xx = np.indices(shape, dtype=np.float32)
    dx, dy = xx - cx, yy - cy
    xr, yr = np.cos(t) * dx + np.sin(t) * dy, -np.sin(t) * dx + np.cos(t) * dy
    return np.sqrt((xr / a) ** 2 + (yr / b) ** 2)


def _unwrap_maps(ell):
    cx, cy, a, b, t = ell
    rho = np.arange(0, RHO_MAX, RHO_STEP)[:, None]
    phi = np.linspace(0, 2 * np.pi, N_PHI, endpoint=False)[None, :]
    xr, yr = rho * a * np.cos(phi), rho * b * np.sin(phi)
    mx = (cx + np.cos(t) * xr - np.sin(t) * yr).astype(np.float32)
    my = (cy + np.sin(t) * xr + np.cos(t) * yr).astype(np.float32)
    dphi = 2 * np.pi / N_PHI
    ds_phi = rho * np.sqrt((a * np.sin(phi)) ** 2 + (b * np.cos(phi)) ** 2) * dphi
    ds_rho = np.broadcast_to(RHO_STEP * np.sqrt((a * np.cos(phi)) ** 2 + (b * np.sin(phi)) ** 2), ds_phi.shape)
    return mx, my, ds_phi, ds_rho


def _remap(img, mx, my, nearest=False):
    return cv2.remap(img, mx, my, cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _dips(line, prominence):
    pk, _ = find_peaks(255 - gaussian_filter1d(line.astype(np.float32), 1.0), prominence=prominence)
    out = np.zeros(line.shape, bool)
    out[pk] = True
    return out


def _label_changes(line):
    inside = line > 0
    change = np.r_[False, line[1:] != line[:-1]]
    return change & inside & np.r_[False, inside[:-1]] | (np.r_[False, inside[1:] & ~inside[:-1]])


def _sector_of_phi():
    return np.arange(N_PHI) * N_SECTORS // N_PHI


def _per_sector(values_fn):
    """Stack values_fn(sector columns) for every sector; empty sectors give NaN silently."""
    sec = _sector_of_phi()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        return np.stack([values_fn(sec == s) for s in range(N_SECTORS)], 1)


def _intercepts(cross, inside, ds):
    def one(cols):
        length = (ds[:, cols] * inside[:, cols]).sum(1)
        n = (cross[:, cols] & inside[:, cols]).sum(1)
        with np.errstate(all='ignore'):
            return np.where((n >= 2) & (length > 0), length / np.maximum(n, 1), np.nan)
    return _per_sector(one)


def polar_profiles(gray, section, ell, prominence=None, labels=None):
    """Per-sector radial profiles (rho x sector) of L_theta, L_rho and wall darkness.

    With `labels` (a ground-truth label map) wall crossings are label changes, not dips.
    """
    mx, my, ds_phi, ds_rho = _unwrap_maps(ell)
    inside = _remap(section.astype(np.uint8), mx, my, nearest=True) > 0
    if labels is not None:
        pol = _remap(labels.astype(np.float32), mx, my, nearest=True).astype(np.int32)
        cross_t = np.array([_label_changes(r) for r in pol])
        cross_r = np.array([_label_changes(c) for c in pol.T]).T
        dark = None
    else:
        pol = _remap(gray, mx, my)
        cross_t = np.array([_dips(r, prominence) for r in pol])
        cross_r = np.array([_dips(c, prominence) for c in pol.T]).T
        d = np.where(inside, 255.0 - pol, np.nan)
        with np.errstate(all='ignore'):
            dark = _per_sector(lambda cols: np.nanmean(d[:, cols], 1))
    cover = inside.mean(1)
    edge_idx = int(np.nonzero(cover >= EDGE_COVER)[0].max())
    return {'Lt': _intercepts(cross_t, inside, ds_phi), 'Lr': _intercepts(cross_r, inside, ds_rho),
            'dark': dark, 'cover': cover, 'edge_rho': edge_idx * RHO_STEP, 'polar': pol,
            'cross_r': cross_r, 'inside': inside, 'ds_rho': ds_rho,
            'px_per_rho': float(np.median(ds_rho[0]) / RHO_STEP)}


def _segment(f, k, min_len):
    """Optimal split of an (n, d) profile into k constant segments; returns the k-1 cut indices."""
    n = len(f)
    cs = np.vstack([np.zeros((1, f.shape[1])), np.cumsum(f, 0)])
    cs2 = np.r_[0.0, np.cumsum((f ** 2).sum(1))]
    D = np.full((k + 1, n + 1), np.inf)
    B = np.zeros((k + 1, n + 1), int)
    D[0, 0] = 0
    i_all = np.arange(n + 1)
    for s in range(1, k + 1):
        for j in range(s * min_len, n + 1):
            i = i_all[(s - 1) * min_len: j - min_len + 1]
            m = (j - i).astype(float)
            cost = (cs2[j] - cs2[i]) - ((cs[j] - cs[i]) ** 2).sum(1) / m
            tot = D[s - 1, i] + cost
            q = int(np.argmin(tot))
            D[s, j], B[s, j] = tot[q], i[q]
    cuts, j = [], n
    for s in range(k, 0, -1):
        j = B[s, j]
        cuts.append(j)
    return sorted(cuts)[1:]


def _features(prof, rows, px_per_rho):
    with np.errstate(all='ignore'), warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        lt = np.log(np.nanmedian(prof['Lt'][:, rows], 1) / px_per_rho)
        dk = np.nanmedian(prof['dark'][:, rows], 1)
    f = np.column_stack([lt, dk])
    f = np.nan_to_num((f - np.nanmean(f, 0)) / np.nanstd(f, 0))
    return gaussian_filter1d(f, 2.0, axis=0)


def change_points(prof, rng, n_boot=N_BOOT):
    """Endodermis outer edge and cortex transition (rho), with bootstrap 95 % intervals over sectors."""
    rho = np.arange(0, RHO_MAX, RHO_STEP)
    sel = (rho >= SEARCH_FROM) & (rho <= prof['edge_rho'] - 0.05)
    rr = rho[sel]
    min_len = int(round(MIN_SEG / RHO_STEP))

    def run(rows):
        return [float(rr[c]) for c in _segment(_features(prof, rows, prof['px_per_rho'])[sel], 3, min_len)]
    base = run(np.arange(N_SECTORS))
    if n_boot:
        boots = np.array([run(rng.integers(0, N_SECTORS, N_SECTORS)) for _ in range(n_boot)])
        ci = np.percentile(boots, [2.5, 97.5], 0).T
    else:
        ci = np.array([[np.nan, np.nan], [np.nan, np.nan]])
    return {'endo_outer': base[0], 'cortex_transition': base[1],
            'endo_outer_ci': ci[0].tolist(), 'cortex_transition_ci': ci[1].tolist()}


def radial_cell_size(prof, lo, hi):
    """Median radial intercept (px) over rho in [lo, hi], all sectors."""
    rho = np.arange(0, RHO_MAX, RHO_STEP)
    band = prof['Lr'][(rho >= lo) & (rho <= hi)]
    if not np.isfinite(band).any():
        raise ValueError(f'no radial cell size measured between rho {lo:.2f} and {hi:.2f}')
    return float(np.nanmedian(band))


def outermost_layer_px(prof, max_px=120):
    """Radial size of the outermost cell layer: gap between the first two walls met inward from the edge.

    The first wall is the outer (epidermal) wall itself, the second the layer's inner wall.
    """
    inside, cross, ds = prof['inside'], prof['cross_r'], prof['ds_rho']
    out = []
    for j in range(inside.shape[1]):
        idx = np.nonzero(inside[:, j])[0]
        if not len(idx):
            continue
        d, walls = 0.0, []
        for k in range(idx.max(), -1, -1):
            d += ds[k, j]
            if d >= max_px or len(walls) == 2:
                break
            if cross[k, j]:
                walls.append(d)
        if len(walls) == 2:
            out.append(walls[1] - walls[0])
    return float(np.median(out)) if out else float('nan')


def vessel_inner_edges(mx_mask, rho):
    """Minimum rho of every metaxylem vessel (the inner edge of the ring)."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats((np.asarray(mx_mask) > 0).astype(np.uint8))
    return [float(rho[lab == i].min()) for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= MIN_VESSEL_AREA]


def guess_kind(gray, section):
    """'drawing' for a line drawing (mostly white inside the section), else 'photo'."""
    return 'drawing' if float(np.median(gray[section])) >= DRAWING_MEDIAN_GREY else 'photo'


def measure_boundaries(gray, section, mx_mask, kind=None, rng=None, n_boot=N_BOOT):
    """All boundaries of one section, in rho units, with their uncertainty and the zone masks."""
    section = np.asarray(section) > 0
    kind = kind or guess_kind(gray, section)
    rng = rng if rng is not None else np.random.default_rng(0)
    ell = anchor_ellipse(mx_mask)
    rho = rho_field(section.shape, ell)
    prof = polar_profiles(gray, section, ell, WALL_PROMINENCE[kind])
    cp = change_points(prof, rng, n_boot)
    vessels = vessel_inner_edges(mx_mask, rho)
    endo_cell_rho = radial_cell_size(prof, cp['endo_outer'] - 0.10, cp['endo_outer']) / prof['px_per_rho']
    rhizo_px = outermost_layer_px(prof)
    b = {'pith': float(np.median(vessels)), 'pith_range': [min(vessels), max(vessels)], 'n_vessels': len(vessels),
         'metaxylem': 1.0, 'endo_inner': cp['endo_outer'] - endo_cell_rho, **cp,
         'endo_cell_rho': endo_cell_rho, 'edge': prof['edge_rho'], 'rhizo_layer_px': rhizo_px,
         'px_per_rho': prof['px_per_rho']}
    return b, zone_masks(rho, section, b), ell, prof


def zone_masks(rho, section, b):
    """Zone masks from measured boundaries; the rhizodermis follows the section contour."""
    sec = section.astype(bool)
    dist = cv2.distanceTransform(sec.astype(np.uint8), cv2.DIST_L2, 5)
    rhizo = sec & (dist <= b['rhizo_layer_px'])
    body = sec & ~rhizo
    return {
        'pith_mask': body & (rho <= b['pith']),
        'vascular_mask': body & (rho > b['pith']) & (rho <= b['endo_inner']),
        'endodermis_mask': body & (rho > b['endo_inner']) & (rho <= b['endo_outer']),
        'inner_cortex_mask': body & (rho > b['endo_outer']) & (rho <= b['cortex_transition']),
        'outer_cortex_mask': body & (rho > b['cortex_transition']),
        'rhizodermis_mask': rhizo,
    }


def ellipse_report(base_report, b):
    """Ellipse report with the measured boundaries in place of the prior scales."""
    return {**base_report, 'scale_pith': b['pith'], 'scale_lpsc': b['endo_inner'],
            'scale_endodermis': b['endo_outer'], 'scale_inner_cortex': b['cortex_transition'],
            'scale_outer_cortex': b['edge'] - b['rhizo_layer_px'] / b['px_per_rho'],
            'scale_rhizodermis': b['edge']}
