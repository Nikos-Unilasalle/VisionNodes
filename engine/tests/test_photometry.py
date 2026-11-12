"""Photometric normalisation: uneven lighting and flattened contrast undone, correct images untouched."""
import os
import sys

import cv2
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import photometry_lib as PH  # noqa: E402

SIZE, R_ROOT = 600, 200
BACKDROP, WALL, LUMEN = 228.0, 80.0, 205.0


def _micrograph(seed=0):
    """Bright backdrop, a root of pale cells with dark walls, sensor noise."""
    rng = np.random.default_rng(seed)
    img = np.full((SIZE, SIZE), BACKDROP, np.float32)
    cv2.circle(img, (SIZE // 2, SIZE // 2), R_ROOT, LUMEN, -1)
    for y in range(SIZE // 2 - R_ROOT, SIZE // 2 + R_ROOT, 14):
        cv2.line(img, (0, y), (SIZE, y), WALL, 2)
    for x in range(SIZE // 2 - R_ROOT, SIZE // 2 + R_ROOT, 14):
        cv2.line(img, (x, 0), (x, SIZE), WALL, 2)
    outside = np.hypot(*np.indices((SIZE, SIZE)) - SIZE // 2) > R_ROOT
    img[outside] = BACKDROP
    cv2.circle(img, (SIZE // 2, SIZE // 2), R_ROOT, WALL, 3)
    img = img + rng.normal(0, 3, img.shape)
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR), ~outside


def _contrast(img, root):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(float)
    return np.median(g[~root]) - np.percentile(g[root & (g < np.median(g[~root]) - 15)], 2)


def test_a_correct_micrograph_passes_through_unchanged():
    img, _ = _micrograph()
    out, rep = PH.normalise(img)
    assert np.array_equal(out, img)
    assert not rep['flat_field'] and rep['stretch'] == 1.0


@pytest.mark.parametrize('gain', [0.6, 0.4, 0.25])
def test_flattened_contrast_is_restored(gain):
    img, root = _micrograph()
    f = img.astype(np.float32)
    mean = f[root].mean()
    flat = np.clip(mean + gain * (f - mean), 0, 255).astype(np.uint8)
    out, rep = PH.normalise(flat)
    assert rep['stretch'] > 1.0
    assert _contrast(out, root) == pytest.approx(PH.MIN_CONTRAST, rel=0.12)


@pytest.mark.parametrize('amplitude', [0.2, 0.5])
def test_an_illumination_gradient_is_flattened(amplitude):
    img, root = _micrograph()
    xx = np.indices((SIZE, SIZE))[1] / SIZE - 0.5
    lit = np.clip(img * (1 - amplitude * (xx + 0.5))[..., None], 0, 255).astype(np.uint8)  # no saturation
    out, rep = PH.normalise(lit)
    assert rep['flat_field']
    g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).astype(float)
    left, right = g[:, :60][~root[:, :60]], g[:, -60:][~root[:, -60:]]
    assert abs(np.median(left) - np.median(right)) < 6          # was amplitude x 228 x 0.9 apart


def test_the_backdrop_excludes_lumens_enclosed_by_tissue():
    img, root = _micrograph()
    mask = PH.backdrop_mask(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32))
    assert mask[~root].mean() > 0.9 and mask[root].mean() < 0.1


def test_a_root_filling_the_frame_is_left_alone():
    img, _ = _micrograph()
    crop = cv2.resize(img[SIZE // 2 - 120:SIZE // 2 + 120, SIZE // 2 - 120:SIZE // 2 + 120], (SIZE, SIZE))
    out, rep = PH.normalise(crop)
    assert not rep['flat_field']


def test_the_input_is_not_modified():
    img, _ = _micrograph()
    before = img.copy()
    PH.normalise(np.clip(img * 0.5 + 60, 0, 255).astype(np.uint8))
    PH.normalise(img)
    assert np.array_equal(img, before)
