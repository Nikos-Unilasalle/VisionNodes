"""Ring Pattern: the blobs of a mask that are arranged as a ring, found by geometric consensus."""
import itertools

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

TRIPLET = 3
REFINE_ITERATIONS = 4
MIN_RADIUS_PX = 2.0
GROWTH_SLACK = 2.0        # growth tries blobs within this many tolerances of the current ring
MISSING_GAP_RATIO = 1.5   # an angular gap this many times the typical gap holds a missing member


def _empty():
    return {'main': None, 'mask': None, 'count': 0, 'center_x': None, 'center_y': None,
            'radius': None, 'regularity': None, 'missing': 0}


def _binary(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return (g > 0).astype(np.uint8)


def _circularity(component, area):
    cnts, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    perimeter = cv2.arcLength(max(cnts, key=len), True)
    return 4 * np.pi * area / max(perimeter ** 2, 1e-9)


def blob_table(binary):
    """Labels and, per blob, (label, area, circularity, centroid)."""
    n, lab, stats, cen = cv2.connectedComponentsWithStats(binary, connectivity=4)
    rows = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        crop = (lab[y:y + h, x:x + w] == i).astype(np.uint8)
        rows.append((i, float(area), _circularity(np.pad(crop, 1), area), cen[i]))
    return lab, rows


def circumcircle(p):
    """Centre and radius of the circle through three points (None when they are aligned)."""
    (x1, y1), (x2, y2), (x3, y3) = p
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    s1, s2, s3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    ux = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / d
    uy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / d
    return np.array([ux, uy]), float(np.hypot(x1 - ux, y1 - uy))


def fit_circle(pts):
    """Least-squares (Kasa) circle through points: centre, radius."""
    a = np.c_[2 * pts, np.ones(len(pts))]
    sol = np.linalg.lstsq(a, (pts ** 2).sum(1), rcond=None)[0]
    centre = sol[:2]
    return centre, float(np.sqrt(max(sol[2] + centre @ centre, 0.0)))


class _Ring:
    """Membership rule of a ring hypothesis: near-equal size and near-equal distance to the centre."""

    def __init__(self, areas, centroids, size_ratio, radius_tol):
        self.log_a = np.log(areas)
        self.pts = centroids
        self.log_size_tol = np.log(size_ratio)
        self.radius_tol = radius_tol

    def members(self, centre, radius, log_size, slack=1.0):
        dist = np.hypot(*(self.pts - centre).T)
        ok = ((np.abs(self.log_a - log_size) <= slack * self.log_size_tol)
              & (np.abs(dist / radius - 1) <= slack * self.radius_tol))
        return np.flatnonzero(ok)

    def refine(self, idx):
        """Iterate fit -> members until stable; returns (members, centre, radius)."""
        centre = radius = None
        for _ in range(REFINE_ITERATIONS):
            if len(idx) < TRIPLET:
                return idx, centre, radius
            centre, radius = fit_circle(self.pts[idx])
            if radius < MIN_RADIUS_PX:
                return idx[:0], centre, radius
            new = self.members(centre, radius, float(np.median(self.log_a[idx])))
            if np.array_equal(new, idx):
                break
            idx = new
        return idx, centre, radius

    def fit_if_consistent(self, idx):
        """(centre, radius) of the circle fitted to idx when every member obeys the rule, else None."""
        centre, radius = fit_circle(self.pts[idx])
        if radius < MIN_RADIUS_PX:
            return None
        ok = self.members(centre, radius, float(np.median(self.log_a[idx])))
        return (centre, radius) if np.isin(idx, ok).all() else None

    def extend(self, idx, centre, radius, areas):
        """Greedy growth: add the blob that most improves ring_score while the refitted ring still
        holds every member. Recovers a member that no circle through the others accepts (a ring
        that is slightly elliptical or off-centre)."""
        score = ring_score(areas[idx], self.pts[idx], centre)
        while True:
            best = None
            near = self.members(centre, radius, float(np.median(self.log_a[idx])), GROWTH_SLACK)
            for j in np.setdiff1d(near, idx):
                trial = np.sort(np.r_[idx, j])
                fit = self.fit_if_consistent(trial)
                if fit is None:
                    continue
                s = ring_score(areas[trial], self.pts[trial], fit[0])
                if s > score and (best is None or s > best[0]):
                    best = (s, trial, fit)
            if best is None:
                return idx, centre, radius
            score, idx, (centre, radius) = best


def ring_score(areas, centroids, centre):
    """Total blob area weighted by the angular regularity: large, evenly spaced rings win."""
    return float(areas.sum()) * angular_regularity(centroids, centre)[0]


def best_ring(areas, centroids, min_count, size_ratio, radius_tol):
    """Consensus search: every size-homogeneous triplet proposes a circle; the members of each
    proposal are refined, then grown greedily; the ring with the best ring_score wins.
    Returns (member indices, centre, radius) or None."""
    ring = _Ring(areas, centroids, size_ratio, radius_tol)
    seen, grown, best, best_score = set(), set(), None, -1.0
    for trip in itertools.combinations(range(len(areas)), TRIPLET):
        a = areas[list(trip)]
        if a.max() > size_ratio * a.min():
            continue
        circle = circumcircle(centroids[list(trip)])
        if circle is None or circle[1] < MIN_RADIUS_PX:
            continue
        start = ring.members(circle[0], circle[1], float(np.median(np.log(a))))
        key = start.tobytes()
        if len(start) < min_count or key in seen:
            continue
        seen.add(key)
        idx, centre, radius = ring.refine(start)
        if len(idx) < TRIPLET or idx.tobytes() in grown:
            continue
        grown.add(idx.tobytes())
        idx, centre, radius = ring.extend(idx, centre, radius, areas)
        score = ring_score(areas[idx], centroids[idx], centre) if len(idx) >= min_count else -1.0
        if score > best_score:
            best, best_score = (idx, centre, radius), score
    return best


def angular_regularity(centroids, centre):
    """(1 - coefficient of variation of the angular gaps, number of members predicted missing)."""
    ang = np.sort(np.arctan2(centroids[:, 1] - centre[1], centroids[:, 0] - centre[0]))
    gaps = np.diff(np.r_[ang, ang[0] + 2 * np.pi])
    regularity = float(np.clip(1 - gaps.std() / gaps.mean(), 0, 1))
    typical = float(np.median(gaps))
    if typical <= 0:
        return regularity, 0
    wide = gaps[gaps >= MISSING_GAP_RATIO * typical]
    return regularity, int(np.round(wide / typical).sum() - len(wide))


def _draw(binary, keep, centre, radius):
    vis = cv2.cvtColor(binary * 120, cv2.COLOR_GRAY2BGR)
    vis[keep > 0] = (0, 200, 0)
    cv2.circle(vis, (int(round(centre[0])), int(round(centre[1]))), int(round(radius)), (0, 0, 255), 2)
    return vis


@vision_node(
    type_id='geom_ring_pattern',
    label='Ring Pattern',
    category='measure',
    icon='CircleDot',
    description=(
        "Keeps the blobs of a mask that form a ring: objects of near-equal size, round, at a "
        "near-constant distance from a common centre — the metaxylem vessels of a root, the "
        "vascular bundles of a stem, the bolt holes of a flange, the petals of a flower.\n\n"
        "Geometric consensus (RANSAC-like): every triplet of size-compatible round blobs proposes "
        "a circle; the blobs agreeing with it (size within Size Ratio of the ring median, distance "
        "within Radius Tolerance of the radius) are gathered and the circle refitted until stable. "
        "The ring with the largest total blob area weighted by its angular regularity wins, so a "
        "ring of large, evenly spaced objects is preferred to a crowd of small ones or to a chance "
        "alignment. No absolute size is needed: the result is scale-free.\n\n"
        "- Min Count: fewer members than this gives an empty selection.\n"
        "- Regularity: 1 − variation of the angular gaps (1 = evenly spaced).\n"
        "- Missing: members predicted from wide angular gaps (merged or undetected objects)."
    ),
    inputs=[
        {'id': 'mask', 'color': 'mask', 'label': 'Candidate Blobs'},
        {'id': 'min_area', 'color': 'scalar', 'label': 'Min Area'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'mask', 'color': 'mask', 'label': 'Ring Members'},
        {'id': 'count', 'color': 'scalar', 'label': 'Member Count'},
        {'id': 'center_x', 'color': 'scalar'},
        {'id': 'center_y', 'color': 'scalar'},
        {'id': 'radius', 'color': 'scalar', 'label': 'Ring Radius (px)'},
        {'id': 'regularity', 'color': 'scalar', 'label': 'Angular Regularity'},
        {'id': 'missing', 'color': 'scalar', 'label': 'Predicted Missing'},
    ],
    params=[
        {'id': 'min_count', 'label': 'Min Count', 'type': 'int', 'default': 5, 'min': 3, 'max': 100},
        {'id': 'size_ratio', 'label': 'Size Ratio (max / ring median)', 'type': 'float', 'default': 2.0,
         'min': 1.1, 'max': 10, 'step': 0.1},
        {'id': 'radius_tol', 'label': 'Radius Tolerance (× radius)', 'type': 'float', 'default': 0.25,
         'min': 0.01, 'max': 0.9, 'step': 0.01},
        {'id': 'circ_min', 'label': 'Min Circularity', 'type': 'float', 'default': 0.3, 'min': 0, 'max': 1,
         'step': 0.01},
        {'id': 'min_area', 'label': 'Min Area (px²)', 'type': 'float', 'default': 0, 'min': 0},
        {'id': 'max_candidates', 'label': 'Max Candidates (largest)', 'type': 'int', 'default': 40,
         'min': 3, 'max': 200},
    ],
)
class RingPatternNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return _empty()
        binary = _binary(np.asarray(mask))
        min_count = int(params.get('min_count', 5))
        floor = max(float(params.get('min_area', 0) or 0), float(inputs.get('min_area') or 0))
        circ_min = float(params.get('circ_min', 0.3))
        lab, rows = blob_table(binary)
        rows = [r for r in rows if r[1] >= floor and r[2] >= circ_min]
        rows = sorted(rows, key=lambda r: -r[1])[:int(params.get('max_candidates', 40))]
        out = {**_empty(), 'main': cv2.cvtColor(binary * 120, cv2.COLOR_GRAY2BGR),
               'mask': np.zeros_like(binary)}
        if len(rows) < max(min_count, TRIPLET):
            return out
        areas = np.array([r[1] for r in rows])
        centroids = np.array([r[3] for r in rows], float)
        found = best_ring(areas, centroids, min_count, float(params.get('size_ratio', 2.0)),
                          float(params.get('radius_tol', 0.25)))
        if found is None:
            return out
        idx, centre, radius = found
        keep_ids = np.zeros(lab.max() + 1, bool)
        keep_ids[[rows[i][0] for i in idx]] = True
        keep = keep_ids[lab].astype(np.uint8) * 255
        regularity, missing = angular_regularity(centroids[idx], centre)
        return {'main': _draw(binary, keep, centre, radius), 'mask': keep, 'count': int(len(idx)),
                'center_x': float(centre[0]), 'center_y': float(centre[1]), 'radius': float(radius),
                'regularity': regularity, 'missing': missing}
