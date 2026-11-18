"""Metaxylem anchor: every candidate ring gets one plausibility score; the best one is the anchor.

A metaxylem ring is recognised the way a reader recognises it: large, unflattened lumens, evenly
spaced on a circle. Each criterion lies in [0, 1] and has a meaningful zero:

  regularity   1 - CV(angular gaps)     evenly spaced around the circle (geom_ring_pattern).
  support      1 - 2 / n                three points always lie on a circle; each further member
                                         on it is evidence that the circle is real.
  contrast     1 - l / median(a)        a: member areas, l: median cell lumen of the section.
                                         Members no larger than ordinary cells bring nothing.
  elongation   median minor / major     a vessel is not flattened (ellipse fitted to the contour).

The vote is their geometric mean, with equal weights: a ring that fails one criterion outright
loses, and no weight needs tuning. On candidate rings of 314 sections (rice, millet, sorghum,
GRANAR renders), each of the four is needed and further criteria (homogeneity of sizes, solidity,
roundness) bring nothing more. There is no branch: the ring of highest vote wins.

Candidates are the rings proposed by geom_ring_pattern's consensus search (triplets of
size-compatible round blobs, refined and grown) on the vessel candidates of each search. Each
ring then takes every blob the search's own membership rule accepts on its circle, and the circle
is refitted, so a vessel left out of a triplet is not lost; the number of vessels is a
measurement, not a condition.
"""
import importlib
import math

import cv2
import numpy as np

CRITERIA = ('regularity', 'support', 'contrast', 'elongation')
MIN_MEMBERS = 3             # three points define a circle
SCORE_FLOOR = 1e-6          # a zero criterion vetoes the ring without breaking the logarithm
# Blob filter and membership rule of the template's ring search (rhizofit_pipeline PARAMS['mx_ring']).
CIRC_MIN = 0.3
SIZE_RATIO = 2.0
RADIUS_TOL = 0.25
MAX_BLOBS = 40
MIN_CONTOUR = 5             # points needed to fit an ellipse


def _ring_module():
    return importlib.import_module('plugins.geom_ring_pattern')


def vote(crit):
    """Geometric mean of the criteria (each in [0, 1])."""
    return math.exp(sum(math.log(max(crit[k], SCORE_FLOOR)) for k in CRITERIA) / len(CRITERIA))


def elongation(component):
    """Minor / major axis of the ellipse fitted to one blob mask (uint8, 0/1); 1 = not flattened."""
    cnts, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=len)
    if len(c) < MIN_CONTOUR:
        return 0.0
    _, (a1, a2), _ = cv2.fitEllipse(c)
    return min(a1, a2) / max(a1, a2, 1e-9)


def _blobs(mask, floor):
    """Round blobs >= floor px, largest MAX_BLOBS: labels, ids, areas, centroids, elongations."""
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    lab, rows = _ring_module().blob_table(binary)
    rows = sorted((r for r in rows if r[1] >= floor and r[2] >= CIRC_MIN), key=lambda r: -r[1])[:MAX_BLOBS]
    ids = np.array([r[0] for r in rows], int)
    elong = np.array([elongation(np.pad(_crop(lab, i), 1)) for i in ids], float)
    return {'labels': lab, 'ids': ids, 'areas': np.array([r[1] for r in rows], float),
            'centroids': np.array([r[3] for r in rows], float).reshape(-1, 2), 'elongation': elong}


def _crop(lab, i):
    ys, xs = np.nonzero(lab == i)
    return (lab[ys.min():ys.max() + 1, xs.min():xs.max() + 1] == i).astype(np.uint8)


def criteria(blobs, members, centre, lumen_area):
    """Criteria of one ring and their vote ('score')."""
    regularity, _ = _ring_module().angular_regularity(blobs['centroids'][members], centre)
    crit = {'regularity': float(regularity),
            'support': 1 - 2 / len(members),
            'contrast': max(0.0, 1 - lumen_area / float(np.median(blobs['areas'][members]))),
            'elongation': float(np.median(blobs['elongation'][members]))}
    crit['score'] = vote(crit)
    return crit


def candidate_rings(mask, floor, blobs=None):
    """Every distinct ring of at least MIN_MEMBERS blobs of `mask`, with all the blobs its circle
    accepts: [{'members' (indices into the blobs), 'centre', 'radius'}]."""
    G = _ring_module()
    blobs = _blobs(mask, floor) if blobs is None else blobs
    areas, cents = blobs['areas'], blobs['centroids']
    if len(areas) < MIN_MEMBERS:
        return []
    rule = G._Ring(areas, cents, SIZE_RATIO, RADIUS_TOL)
    seen, rings = set(), []
    for idx, centre, radius, _ in G.candidate_rings(areas, cents, MIN_MEMBERS, SIZE_RATIO, RADIUS_TOL):
        idx = np.union1d(idx, rule.members(centre, radius, float(np.median(np.log(areas[idx])))))
        key = idx.tobytes()
        if key in seen:
            continue
        seen.add(key)
        centre, radius = G.fit_circle(cents[idx])
        rings.append({'members': idx, 'centre': np.asarray(centre, float), 'radius': float(radius)})
    return rings


def best_anchor(candidate_masks, lumen_area, floor):
    """The ring of highest vote over all searches, or None when no search proposes one.

    candidate_masks: {search: vessel candidate mask or None}. Returns {'search', 'mask', 'count',
    'centre', 'radius', 'criteria'}; 'criteria' holds the criteria and the vote ('score')."""
    best = None
    for search, mask in candidate_masks.items():
        if mask is None:
            continue
        blobs = _blobs(mask, floor)
        for ring in candidate_rings(mask, floor, blobs):
            crit = criteria(blobs, ring['members'], ring['centre'], lumen_area)
            if best is None or crit['score'] > best[0]['score']:
                best = (crit, search, ring, blobs)
    if best is None:
        return None
    crit, search, ring, blobs = best
    lab = blobs['labels']
    keep = np.zeros(lab.max() + 1, bool)
    keep[blobs['ids'][ring['members']]] = True
    return {'search': search, 'mask': keep[lab], 'count': int(len(ring['members'])),
            'centre': ring['centre'], 'radius': ring['radius'], 'criteria': crit}
