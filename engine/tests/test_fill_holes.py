"""Fill Holes: the 'Enclosed by Larger' method fills a hole only when the object around it is larger."""
import os
import sys

import cv2
import numpy as np

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)

from plugins.fill_holes import FillHolesNode  # noqa: E402

ENCLOSED_BY_LARGER = 3


def _fill(mask):
    return FillHolesNode().process({'mask': mask}, {'method': ENCLOSED_BY_LARGER})['main'] > 0


def test_a_speck_inside_a_lumen_is_filled_whatever_its_size_in_pixels():
    mask = np.zeros((400, 400), np.uint8)
    cv2.circle(mask, (200, 200), 120, 255, -1)
    cv2.circle(mask, (200, 200), 40, 0, -1)            # 5000 px: larger than any fixed default
    assert _fill(mask)[200, 200]


def test_the_inside_of_a_thin_loop_is_left_empty():
    mask = np.zeros((400, 400), np.uint8)
    cv2.circle(mask, (200, 200), 150, 255, 6)
    out = _fill(mask)
    assert not out[200, 200]
    assert out.sum() == (mask > 0).sum()


def test_each_hole_is_judged_against_its_own_enclosing_object():
    mask = np.zeros((400, 400), np.uint8)
    cv2.circle(mask, (200, 200), 150, 255, 6)          # thin loop: its inside stays empty
    cv2.circle(mask, (200, 200), 40, 255, -1)          # a lumen inside the loop, with a speck
    cv2.circle(mask, (200, 200), 5, 0, -1)
    out = _fill(mask)
    assert out[200, 200]
    assert not out[200, 120]


def test_other_methods_are_unchanged():
    mask = np.zeros((400, 400), np.uint8)
    cv2.circle(mask, (200, 200), 150, 255, 6)
    out = FillHolesNode().process({'mask': mask}, {'method': 0})['main'] > 0
    assert out[200, 200]
