"""Synthetic-degradation benchmark helpers for root cross-section cell imputation.

Two pure building blocks, independent of the VNStudio graph:

* ``damage_image`` — degrades a clean section image with a controlled,
  seeded amount of damage (washed-out walls, tears, peripheral tissue loss),
  confined to the section mask. Returns the image and the damaged-pixel mask.
* ``impute_counts`` — the "measured + projected" estimator of the methods
  draft: per zone, N_proj = round(max(0, A_theo - A_obs) / median cell area).
  ``territory_px`` > 0 grows each cell into the surrounding walls before
  measuring A_obs (otherwise wall pixels are counted as "missing" tissue).

Ground truth for the benchmark = counts on the undamaged image.
"""
from dataclasses import dataclass

import cv2
import numpy as np
from skimage import measure, segmentation

DAMAGE_KINDS = ('wash', 'tear', 'loss')
_WASH_STRENGTH = 0.85
_MAX_DRAWS = 400


@dataclass(frozen=True)
class ZoneCount:
    zone: str
    n_obs: int
    n_proj: int
    a_theo: float
    a_obs: float
    a_mean: float

    @property
    def a_med(self):
        """Backward-compatibility alias."""
        return self.a_mean

    @property
    def n_total(self):
        return self.n_obs + self.n_proj


# --------------------------------------------------------------------------
# Damage
# --------------------------------------------------------------------------

def _brightness_levels(gray, section):
    inside = gray[section]
    outside = gray[~section]
    lumen = float(np.percentile(inside, 90)) if inside.size else 255.0
    backdrop = float(np.median(outside)) if outside.size else 255.0
    return lumen, backdrop


def _wash_patch(rng, h, w, center, radius):
    patch = np.zeros((h, w), np.uint8)
    axes = (int(radius), int(radius * rng.uniform(0.5, 1.0)))
    cv2.ellipse(patch, (int(center[0]), int(center[1])), axes,
                float(rng.uniform(0, 180)), 0, 360, 255, -1)
    return patch > 0


def _tear_patch(rng, h, w, center, radius):
    patch = np.zeros((h, w), np.uint8)
    angle = rng.uniform(0, np.pi)
    n_pts = 6
    steps = np.linspace(-radius, radius, n_pts)
    jitter = rng.normal(0, radius * 0.08, n_pts)
    xs = center[0] + steps * np.cos(angle) - jitter * np.sin(angle)
    ys = center[1] + steps * np.sin(angle) + jitter * np.cos(angle)
    pts = np.stack([xs, ys], 1).astype(np.int32)
    width = max(3, int(radius * rng.uniform(0.10, 0.20)))
    cv2.polylines(patch, [pts], False, 255, width)
    return patch > 0


def _loss_patch(rng, h, w, center, radius, section_center):
    """Wedge of tissue torn off from the periphery towards the centre."""
    patch = np.zeros((h, w), np.uint8)
    cx, cy = section_center
    ang = np.arctan2(center[1] - cy, center[0] - cx)
    span = rng.uniform(0.15, 0.35)
    far = 4 * max(h, w)
    depth = radius * rng.uniform(1.0, 2.0)
    tip = (center[0] - np.cos(ang) * depth, center[1] - np.sin(ang) * depth)
    pts = np.array([
        tip,
        (tip[0] + far * np.cos(ang - span), tip[1] + far * np.sin(ang - span)),
        (tip[0] + far * np.cos(ang + span), tip[1] + far * np.sin(ang + span)),
    ], np.int32)
    cv2.fillPoly(patch, [pts], 255)
    return patch > 0


def _pick_center(rng, section, kind, section_center, max_r):
    ys, xs = np.nonzero(section)
    if kind != 'loss':
        i = rng.integers(len(xs))
        return float(xs[i]), float(ys[i])
    # loss: start on the section rim
    ang = rng.uniform(0, 2 * np.pi)
    cx, cy = section_center
    return cx + np.cos(ang) * max_r, cy + np.sin(ang) * max_r


def damage_image(image, section, kind, severity, seed=0, patch_radius=None):
    """Degrade ``image`` inside ``section`` until ~``severity`` of it is hit.

    Returns ``(damaged_image, damaged_mask, achieved_fraction)``.
    """
    if kind not in DAMAGE_KINDS:
        raise ValueError(f'unknown damage kind {kind!r}; expected one of {DAMAGE_KINDS}')
    if not 0.0 <= severity < 1.0:
        raise ValueError('severity must be in [0, 1)')
    section = np.asarray(section) > 0
    if not section.any():
        raise ValueError('empty section mask')

    out = image.copy()
    h, w = section.shape
    hit = np.zeros((h, w), bool)
    if severity == 0:
        return out, hit, 0.0

    rng = np.random.default_rng(seed)
    area = section.sum()
    m = cv2.moments(section.astype(np.uint8), binaryImage=True)
    s_center = (m['m10'] / m['m00'], m['m01'] / m['m00'])
    max_r = float(np.sqrt(area / np.pi))
    radius = patch_radius or max_r * 0.18
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    lumen, backdrop = _brightness_levels(gray, section)

    for _ in range(_MAX_DRAWS):
        if hit.sum() / area >= severity:
            break
        center = _pick_center(rng, section, kind, s_center, max_r)
        r = radius * rng.uniform(0.6, 1.4)
        if kind == 'wash':
            patch = _wash_patch(rng, h, w, center, r)
        elif kind == 'tear':
            patch = _tear_patch(rng, h, w, center, r)
        else:
            patch = _loss_patch(rng, h, w, center, r, s_center)
        hit |= patch & section

    out = _paint(out, hit, section, kind, lumen, backdrop)
    return out, hit, float(hit.sum() / area)


def _paint(image, hit, section, kind, lumen, backdrop):
    out = image.astype(np.float32)
    if kind == 'wash':
        soft = cv2.GaussianBlur(hit.astype(np.float32), (0, 0), 3.0) * section
        alpha = np.clip(soft, 0, 1) * _WASH_STRENGTH
        if out.ndim == 3:
            alpha = alpha[..., None]
        out = out * (1 - alpha) + lumen * alpha
    else:
        level = lumen if kind == 'tear' else backdrop
        out[hit] = level
    return np.clip(out, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# Estimator
# --------------------------------------------------------------------------

def assign_cells(labels, zones):
    """Map each cell id to the zone holding its centroid (None = outside)."""
    assignment = {}
    for p in measure.regionprops(labels):
        r, c = (int(round(v)) for v in p.centroid)
        assignment[p.label] = next((z for z, m in zones.items() if m[r, c]), None)
    return assignment


def extract_cortical_lacunae(labels, zones, min_area=25):
    """Extract cortical lacunae (aerenchyma cavities) within inner & outer cortex."""
    labels = np.asarray(labels)
    inner = zones.get('inner_cortex')
    outer = zones.get('outer_cortex')
    if inner is None or outer is None:
        return np.zeros(labels.shape, bool)
    cortex = (np.asarray(inner) > 0) | (np.asarray(outer) > 0)
    gaps = cortex & (labels == 0)
    n_gaps, gap_labels, gap_stats, _ = cv2.connectedComponentsWithStats(gaps.astype(np.uint8))
    lacunae = np.zeros(labels.shape, bool)
    for i in range(1, n_gaps):
        if gap_stats[i, cv2.CC_STAT_AREA] >= min_area:
            lacunae |= (gap_labels == i)
    return lacunae


def impute_counts(labels, zones, territory_px=0, exclude=None):
    """Measured + projected cell counts per zone.

    ``zones``: {name: bool mask}. ``exclude``: bool mask removed from every
    zone's theoretical area (e.g. metaxylem lumens, cortical lacunae).
    ``territory_px`` grows cells into adjacent walls before summing their areas.
    """
    labels = np.asarray(labels)
    zones = {z: np.asarray(m) > 0 for z, m in zones.items()}
    keep = ~np.asarray(exclude, bool) if exclude is not None else np.ones(labels.shape, bool)
    grown = segmentation.expand_labels(labels, territory_px) if territory_px > 0 else labels
    assignment = assign_cells(labels, zones)
    areas = dict(zip(*np.unique(grown[grown > 0], return_counts=True)))

    counts = {}
    for z, mask in zones.items():
        ids = [cid for cid, zz in assignment.items() if zz == z]
        cell_areas = np.array([areas.get(cid, 0) for cid in ids], float)
        a_theo = float((mask & keep).sum())
        a_obs = float(cell_areas.sum())
        a_mean = float(np.mean(cell_areas)) if len(ids) else 0.0
        missing = max(0.0, a_theo - a_obs)
        n_proj = int(np.floor(missing / a_mean + 0.5)) if a_mean > 0 else 0
        counts[z] = ZoneCount(z, len(ids), n_proj, a_theo, a_obs, a_mean)
    return counts
