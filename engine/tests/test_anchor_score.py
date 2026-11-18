"""Anchor vote: one plausibility score for every candidate metaxylem ring."""
import os
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import anchor_score_lib as A  # noqa: E402

SIZE = (1000, 1000)
CENTRE = np.array([500.0, 500.0])
LUMEN = 100.0


def _ring_pts(n, radius, centre=CENTRE, jitter=0.0):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False) + jitter * np.sin(np.arange(n))
    return centre + radius * np.c_[np.cos(ang), np.sin(ang)]


def _discs(blobs, shape=SIZE):
    m = np.zeros(shape, np.uint8)
    for (x, y), r in blobs:
        cv2.circle(m, (int(x), int(y)), int(r), 255, -1)
    return m


def _ellipses(pts, axes):
    m = np.zeros(SIZE, np.uint8)
    for x, y in pts:
        cv2.ellipse(m, (int(x), int(y)), axes, 0, 0, 360, 255, -1)
    return m


def test_vote_is_the_geometric_mean_of_the_four_criteria():
    assert A.CRITERIA == ('regularity', 'support', 'contrast', 'elongation')
    crit = {k: 0.5 for k in A.CRITERIA}
    assert abs(A.vote(crit) - 0.5) < 1e-9
    crit['contrast'] = 0.0
    assert A.vote(crit) < 0.1 * 0.5      # a failed criterion outweighs every other being average


def test_criteria_of_a_regular_ring_of_round_vessels_are_all_high():
    mask = _discs([(p, 16) for p in _ring_pts(8, 150)])
    best = A.best_anchor({'stele': mask}, lumen_area=LUMEN, floor=50)
    assert set(best['criteria']) == set(A.CRITERIA) | {'score'}
    assert all(best['criteria'][k] > 0.7 for k in A.CRITERIA)


def test_candidates_include_a_four_vessel_ring():
    mask = _discs([(p, 14) for p in _ring_pts(4, 120)])
    rings = A.candidate_rings(mask, floor=50)
    assert any(len(r['members']) == 4 for r in rings)


def test_ring_of_vessels_beats_a_ring_of_small_lumens():
    vessels = _discs([(p, 16) for p in _ring_pts(12, 150)])
    small = _discs([(p, 7) for p in _ring_pts(5, 40, centre=CENTRE + [330, 0])])
    best = A.best_anchor({'stele': vessels, 'whole': small}, lumen_area=LUMEN, floor=50)
    assert best['search'] == 'stele'
    assert best['count'] == 12


def test_round_vessels_beat_flattened_lacunae_of_the_same_area():
    round_ = _discs([(p, 16) for p in _ring_pts(8, 150)])
    flat = _ellipses(_ring_pts(8, 300), (40, 6))
    best = A.best_anchor({'stele': round_, 'whole': flat}, lumen_area=LUMEN, floor=50)
    assert best['search'] == 'stele'


def test_every_vessel_on_the_winning_circle_is_kept_even_a_smaller_one():
    pts = _ring_pts(6, 150, jitter=0.1)
    mask = _discs(list(zip(pts, [17, 17, 17, 17, 17, 13])))
    best = A.best_anchor({'stele': mask}, lumen_area=LUMEN, floor=50)
    assert best['count'] == 6
    assert best['mask'][int(pts[5][1]), int(pts[5][0])]


def test_best_anchor_is_none_without_any_ring():
    empty = np.zeros((300, 300), np.uint8)
    assert A.best_anchor({'stele': empty, 'whole': None}, lumen_area=LUMEN, floor=50) is None
