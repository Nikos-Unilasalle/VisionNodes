"""Lumen edge of a metaxylem vessel, placed at half height of the lumen-to-wall intensity drop.

The vessel masks come from a thresholded lumen map, whose boundary sits inside the wall gradient:
on RM12e it lies ~2.5 px beyond the expert's lumen outline on every vessel, so XVA is overestimated
by ~16 % and the axial conductance (sum of r^4) by ~35 %. The expert's outline lies where the
intensity has fallen halfway from the lumen to the darkest point of the wall, the usual half-height
definition of an edge. Here that edge is found along rays cast from the vessel centre:

  lumen level  median intensity over the inner half of the vessel (radius < r_eq / 2);
  wall level   darkest point of the ray between r_eq / 2 and 2 r_eq;
  edge         first point past r_eq / 2 below the mean of the two levels (sub-pixel).

No grey level and no distance is set: both levels are read on each vessel. A ray without a crossing
(no wall darker than the lumen) is dropped; when most rays are dropped the mask is kept as it is.
The image must have bright lumens and dark walls (the pipeline's polarity-normalised image).
"""
import cv2
import numpy as np

N_RAYS = 72               # rays per vessel (5 degrees apart)
STEP_PX = 0.25            # sampling step along a ray
INNER_SHARE = 0.5         # lumen level read inside this fraction of the equivalent radius
OUTER_FACTOR = 2.0        # rays reach this multiple of the equivalent radius
MIN_RAY_SHARE = 0.5       # fewer valid rays than this share: keep the mask


def _profiles(gray, centre, r_max):
    """(radii, profiles[N_RAYS, len(radii)]) sampled bilinearly along rays from `centre`."""
    radii = np.arange(0.0, r_max, STEP_PX, dtype=np.float32)
    ang = np.linspace(0, 2 * np.pi, N_RAYS, endpoint=False, dtype=np.float32)
    xs = (centre[0] + np.cos(ang)[:, None] * radii[None, :]).astype(np.float32)
    ys = (centre[1] + np.sin(ang)[:, None] * radii[None, :]).astype(np.float32)
    prof = cv2.remap(gray.astype(np.float32), xs, ys, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return radii, ang, prof


def _crossing(radii, prof, start):
    """Sub-pixel radius where `prof` first falls below half height past index `start`, or None."""
    lumen = float(np.median(prof[:start + 1]))
    stop = int(np.argmin(prof[start:])) + start
    half = (lumen + float(prof[stop])) / 2
    below = np.nonzero(prof[start:stop + 1] < half)[0]
    if not below.size:
        return None
    k = int(below[0]) + start
    if k == 0:
        return float(radii[0])
    p0, p1 = float(prof[k - 1]), float(prof[k])
    t = (p0 - half) / (p0 - p1) if p0 != p1 else 0.0
    return float(radii[k - 1] + t * (radii[k] - radii[k - 1]))


def lumen_edge(gray, mask):
    """Edge points (N, 2) of the vessel lumen in `mask` (bool, one component), or None."""
    mask = np.asarray(mask, bool)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    centre = (float(xs.mean()), float(ys.mean()))
    r_eq = float(np.sqrt(mask.sum() / np.pi))
    radii, ang, prof = _profiles(np.asarray(gray), centre, OUTER_FACTOR * r_eq)
    start = int(np.searchsorted(radii, INNER_SHARE * r_eq))
    pts = []
    for a, p in zip(ang, prof):
        r = _crossing(radii, p, start)
        if r is not None:
            pts.append((centre[0] + r * np.cos(a), centre[1] + r * np.sin(a)))
    if len(pts) < MIN_RAY_SHARE * N_RAYS:
        return None
    return np.asarray(pts, np.float32)


def lumen_area(gray, mask):
    """Area (px) inside the half-height lumen edge; the mask's own area when no edge is found."""
    pts = lumen_edge(gray, mask)
    if pts is None:
        return float(np.asarray(mask, bool).sum())
    return float(cv2.contourArea(pts.reshape(-1, 1, 2)))
