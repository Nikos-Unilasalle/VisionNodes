"""Cortical cell files (CF) counted as the shortest chain of touching cells across the cortex."""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import cell_files_lib as CF  # noqa: E402
import radial_zoning_lib as R  # noqa: E402

SIZE, C = 800, 400
INNER, LAYER, WALL = 100, 20, 2           # cortex starts at r = 100 px; layers 20 px thick, 2 px walls
ELL = (C, C, 100.0, 100.0, 0.0)           # rho = r / 100
RHIZO_PX = 20                             # one outer (epidermal) layer along the contour


def _section(n_layers):
    """Disc whose cortex holds n_layers layers, then one epidermal layer, then the edge."""
    yy, xx = np.indices((SIZE, SIZE))
    r = np.hypot(xx - C, yy - C)
    edge = INNER + (n_layers + 1) * LAYER
    return r, np.degrees(np.arctan2(yy - C, xx - C)) + 180, r <= edge, edge


def _layers(n_layers, sectors=36, stagger=False):
    """Concentric layers cut into angular cells; staggered layers shift every other one by half a cell."""
    r, phi, section, edge = _section(n_layers)
    layer = ((r - INNER) // LAYER).astype(int)
    width = 360 / sectors
    shift = np.where(layer % 2 == 1, width / 2, 0) if stagger else 0
    sector = (((phi + shift) % 360) // width).astype(int)
    labels = np.zeros((SIZE, SIZE), np.int32)
    cells = (r >= INNER) & (r < edge)
    labels[cells] = 1 + layer[cells] * 1000 + sector[cells]
    walls = cells & ((((r - INNER) % LAYER) < WALL) | ((((phi + shift) % 360) % width) < 0.6))
    labels[walls] = 0
    return labels, section, r, phi, layer


def _count(labels, section, n_layers):
    endo_outer = INNER / 100
    return CF.cortical_cell_files(labels, section, ELL, endo_outer, RHIZO_PX)


def test_counts_concentric_layers_and_skips_the_epidermis():
    labels, section, *_ = _layers(8)
    med, lo, hi = _count(labels, section, 8)
    assert (med, lo, hi) == (8, 8, 8)


def test_staggered_layers_are_counted_once_each():
    labels, section, *_ = _layers(10, stagger=True)
    med, lo, hi = _count(labels, section, 10)
    assert med == 10 and lo >= 10 and hi <= 10


def test_a_lacuna_across_three_layers_does_not_lower_the_count():
    labels, section, r, phi, layer = _layers(9)
    lacuna = (layer >= 2) & (layer <= 4) & (phi > 40) & (phi < 70)
    labels[lacuna] = 0
    med, lo, hi = _count(labels, section, 9)
    assert (med, lo, hi) == (9, 9, 9)


def test_a_cell_merged_across_two_layers_counts_for_two():
    labels, section, r, phi, layer = _layers(8)
    span = (phi > 100) & (phi < 200)
    upper = span & (layer == 4) & (labels > 0)
    labels[upper] -= 1000                                  # layer-4 cells take their layer-3 neighbour's label
    gap = span & (layer == 4) & (((r - INNER) % LAYER) < WALL) & ((phi % 10) >= 0.6)
    labels[gap] = 1 + 3 * 1000 + (phi[gap] // 10).astype(int)   # no wall between the two merged layers
    med, lo, hi = _count(labels, section, 8)
    assert (med, lo, hi) == (8, 8, 8)


def test_the_outer_end_follows_the_section_contour_not_a_rho_ellipse():
    """Elliptical section, circular anchor: the cortex ends at rho 2.2 on one axis and 3.2 on the other."""
    import cv2
    yy, xx = np.indices((SIZE, SIZE))
    a_ax, b_ax, n = 320.0, 220.0, 7
    section = ((xx - C) / a_ax) ** 2 + ((yy - C) / b_ax) ** 2 <= 1
    d_edge = cv2.distanceTransform(section.astype(np.uint8), cv2.DIST_L2, 5)
    r = np.hypot(xx - C, yy - C)
    phi = np.arctan2(yy - C, xx - C)
    outer = a_ax * b_ax / np.hypot(b_ax * np.cos(phi), a_ax * np.sin(phi)) - RHIZO_PX
    t = (r - INNER) / (outer - INNER)                      # 0 at the endodermis, 1 under the epidermis
    cortex = section & (t >= 0) & (d_edge > RHIZO_PX)
    layer = np.clip((t * n).astype(int), 0, n - 1)
    sector = ((np.degrees(phi) + 180) // 10).astype(int)
    labels = np.zeros((SIZE, SIZE), np.int32)
    labels[cortex] = 1 + layer[cortex] * 1000 + sector[cortex]
    epi = section & (d_edge <= RHIZO_PX) & (d_edge > 2)
    labels[epi] = 500000 + sector[epi]
    walls = (((t * n) % 1) * (outer - INNER) / n < WALL) | ((((np.degrees(phi) + 180) % 10) < 0.6))
    labels[walls & (labels > 0) & cortex] = 0
    med, lo, hi = CF.cortical_cell_files(labels, section, ELL, 1.0, RHIZO_PX)
    assert (med, lo, hi) == (n, n, n)


def test_inputs_are_not_modified():
    labels, section, *_ = _layers(6)
    before_l, before_s = labels.copy(), section.copy()
    _count(labels, section, 6)
    assert np.array_equal(labels, before_l) and np.array_equal(section, before_s)


@pytest.mark.parametrize('rhizo_px', [float('nan'), -1.0])
def test_invalid_rhizodermis_width_fails_clearly(rhizo_px):
    labels, section, *_ = _layers(6)
    with pytest.raises(ValueError, match='rhizodermis'):
        CF.cortical_cell_files(labels, section, ELL, 1.0, rhizo_px)


def test_no_cortex_cell_fails_clearly():
    _, section, *_ = _layers(6)
    with pytest.raises(ValueError, match='no cortex cell'):
        CF.cortical_cell_files(np.zeros((SIZE, SIZE), np.int32), section, ELL, 1.0, RHIZO_PX)


def test_rho_field_matches_the_test_frame():
    r, *_ = _section(4)
    assert np.allclose(R.rho_field((SIZE, SIZE), ELL), r / 100, atol=1e-4)
