"""Tests for the synthetic-degradation imputation benchmark helpers."""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import root_bench_lib as B  # noqa: E402

SIZE = 200
CELL = 10
WALL = 2


def _grid_labels():
    """Square cells (CELL px pitch, WALL px walls) filling a disk."""
    yy, xx = np.mgrid[:SIZE, :SIZE]
    disk = (xx - SIZE / 2) ** 2 + (yy - SIZE / 2) ** 2 <= (SIZE * 0.45) ** 2
    labels = np.zeros((SIZE, SIZE), np.int32)
    k = 1
    for r in range(0, SIZE, CELL):
        for c in range(0, SIZE, CELL):
            labels[r + WALL:r + CELL, c + WALL:c + CELL] = k
            k += 1
    labels[~disk] = 0
    return labels, disk


def _zones(disk):
    yy, xx = np.mgrid[:SIZE, :SIZE]
    inner = (xx - SIZE / 2) ** 2 + (yy - SIZE / 2) ** 2 <= (SIZE * 0.25) ** 2
    return {'inner': inner & disk, 'outer': disk & ~inner}


def _image(disk):
    img = np.full((SIZE, SIZE, 3), 240, np.uint8)
    img[disk] = 120
    return img


def test_clean_image_projects_wall_area_without_territory():
    labels, disk = _grid_labels()
    counts = B.impute_counts(labels, _zones(disk))
    # walls are ~36% of each pitch -> raw estimator invents cells on a clean section
    assert counts['inner'].n_proj > 0.3 * counts['inner'].n_obs


def test_territory_removes_clean_bias():
    labels, disk = _grid_labels()
    counts = B.impute_counts(labels, _zones(disk), territory_px=WALL)
    for c in counts.values():
        assert abs(c.n_total - c.n_obs) <= 0.1 * c.n_obs


def test_territory_recovers_removed_cells():
    labels, disk = _grid_labels()
    truth = B.impute_counts(labels, _zones(disk), territory_px=WALL)
    rng = np.random.default_rng(1)
    ids = np.unique(labels[labels > 0])
    drop = rng.choice(ids, size=len(ids) // 3, replace=False)
    damaged = np.where(np.isin(labels, drop), 0, labels)

    est = B.impute_counts(damaged, _zones(disk), territory_px=WALL)

    for z in truth:
        assert est[z].n_obs < truth[z].n_obs
        assert abs(est[z].n_total - truth[z].n_obs) <= 0.15 * truth[z].n_obs


def test_exclude_mask_reduces_theoretical_area():
    labels, disk = _grid_labels()
    zones = _zones(disk)
    exclude = np.zeros_like(disk)
    exclude[90:110, 90:110] = True
    full = B.impute_counts(labels, zones)['inner'].a_theo
    cut = B.impute_counts(labels, zones, exclude=exclude)['inner'].a_theo
    assert cut == full - exclude.sum()


@pytest.mark.parametrize('kind', B.DAMAGE_KINDS)
def test_damage_hits_requested_fraction_inside_section(kind):
    _, disk = _grid_labels()
    out, hit, frac = B.damage_image(_image(disk), disk, kind, 0.25, seed=3)
    assert 0.25 <= frac < 0.6
    assert not (hit & ~disk).any()
    assert out.shape == (SIZE, SIZE, 3)
    assert (out[~disk] == 240).all()


def test_damage_is_reproducible_and_seed_dependent():
    _, disk = _grid_labels()
    img = _image(disk)
    a = B.damage_image(img, disk, 'tear', 0.2, seed=7)[1]
    b = B.damage_image(img, disk, 'tear', 0.2, seed=7)[1]
    c = B.damage_image(img, disk, 'tear', 0.2, seed=8)[1]
    assert (a == b).all()
    assert not (a == c).all()


def test_zero_severity_returns_untouched_copy():
    _, disk = _grid_labels()
    img = _image(disk)
    out, hit, frac = B.damage_image(img, disk, 'wash', 0.0)
    assert frac == 0.0 and not hit.any()
    assert (out == img).all() and out is not img


def test_damage_rejects_bad_arguments():
    _, disk = _grid_labels()
    img = _image(disk)
    with pytest.raises(ValueError):
        B.damage_image(img, disk, 'fire', 0.1)
    with pytest.raises(ValueError):
        B.damage_image(img, disk, 'wash', 1.2)
    with pytest.raises(ValueError):
        B.damage_image(img, np.zeros_like(disk), 'wash', 0.1)
