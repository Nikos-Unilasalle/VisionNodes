"""Vessel lumen edge at half height between the lumen and the darkest point of its wall."""
import os
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import vessel_edge_lib as VE  # noqa: E402

SIZE = 300
CENTRE = (150, 150)
LUMEN_R = 30
WALL_R = 38


def _vessel(lumen=200, wall=60, around=150, blur=2.0, axes=(LUMEN_R, LUMEN_R)):
    img = np.full((SIZE, SIZE), around, np.float32)
    cv2.ellipse(img, CENTRE, (axes[0] + WALL_R - LUMEN_R, axes[1] + WALL_R - LUMEN_R), 0, 0, 360, wall, -1)
    cv2.ellipse(img, CENTRE, axes, 0, 0, 360, lumen, -1)
    return cv2.GaussianBlur(img, (0, 0), blur).astype(np.uint8)


def _disc(r):
    m = np.zeros((SIZE, SIZE), bool)
    cv2.circle(m.view(np.uint8), CENTRE, r, 1, -1)
    return m


def test_an_oversized_mask_is_brought_back_to_the_lumen():
    area = VE.lumen_area(_vessel(), _disc(LUMEN_R + 4))
    assert abs(area / (np.pi * LUMEN_R ** 2) - 1) < 0.05


def test_an_undersized_mask_is_brought_out_to_the_lumen():
    area = VE.lumen_area(_vessel(), _disc(LUMEN_R - 4))
    assert abs(area / (np.pi * LUMEN_R ** 2) - 1) < 0.05


def test_the_edge_does_not_depend_on_the_grey_levels():
    a = VE.lumen_area(_vessel(lumen=240, wall=120, around=200), _disc(LUMEN_R + 3))
    b = VE.lumen_area(_vessel(lumen=140, wall=20, around=60), _disc(LUMEN_R + 3))
    assert abs(a / b - 1) < 0.03


def test_an_elliptical_lumen_keeps_its_area():
    axes = (36, 24)
    area = VE.lumen_area(_vessel(axes=axes), _disc(32))
    assert abs(area / (np.pi * axes[0] * axes[1]) - 1) < 0.06


def test_a_vessel_without_a_wall_profile_keeps_its_mask_area():
    flat = np.full((SIZE, SIZE), 128, np.uint8)
    mask = _disc(LUMEN_R)
    assert VE.lumen_area(flat, mask) == float(mask.sum())


def test_runner_vessel_table_measures_the_lumen_not_the_mask():
    import root_web_runner as W
    mask = _disc(LUMEN_R + 4)
    with_image = W._metaxylem_vessels(mask, 50, _vessel())[0]
    without = W._metaxylem_vessels(mask, 50)[0]
    target = np.pi * LUMEN_R ** 2
    assert abs(with_image['raw'] / target - 1) < 0.05
    assert abs(with_image['reg'] / target - 1) < 0.05
    assert without['raw'] > 1.2 * target
