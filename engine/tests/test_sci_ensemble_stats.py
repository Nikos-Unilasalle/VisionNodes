"""
test_sci_ensemble_stats.py — Monte-Carlo ensemble statistics accumulator.

The per-pixel std of a binary-outcome ensemble is analytically sqrt(P(1-P)), so it
carries no information beyond the mean map. The informative quantities are per-realisation
AGGREGATES — area, component count, boundary displacement — whose ensemble spread depends
on the spatial structure of the perturbation. These tests pin that behaviour down.
"""
import os
import sys
import importlib.util

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'sci_ensemble_stats.py'
)
_spec = importlib.util.spec_from_file_location('plugins.sci_ensemble_stats', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.sci_ensemble_stats'] = _mod
_spec.loader.exec_module(_mod)

SHAPE = (64, 64)


def _disc(radius, shape=SHAPE):
    """Binary mask: centred disc of the given radius."""
    cy, cx = shape[0] / 2.0, shape[1] / 2.0
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (((yy - cy) ** 2 + (xx - cx) ** 2) <= radius ** 2).astype(np.uint8) * 255


def _feed(node, masks, **params):
    base = {'components': True, 'boundary': False}
    base.update(params)
    out = None
    for i, m in enumerate(masks):
        out = node.process({'mask': m, 'tick': i}, base)
    return out


# ── area: the headline aggregate ──────────────────────────────────────────────

def test_area_mean_matches_the_realisation_areas():
    # Arrange: discs of radius 10 and 12 alternating → mean area is their average
    node = _mod.EnsembleStatsNode()
    small, big = _disc(10), _disc(12)
    a_small = int((small > 127).sum())
    a_big = int((big > 127).sum())

    # Act
    out = _feed(node, [small if i % 2 else big for i in range(20)])

    # Assert
    assert out['frame_count'] == 20
    assert abs(out['area_mean'] - (a_small + a_big) / 2.0) < 1.0


def test_constant_ensemble_has_zero_spread():
    # Arrange: every realisation identical → no ensemble uncertainty at all
    node = _mod.EnsembleStatsNode()

    # Act
    out = _feed(node, [_disc(11) for _ in range(15)])

    # Assert
    assert out['area_sd'] == 0.0
    assert out['stats']['area']['cv'] == 0.0
    assert out['stats']['area']['ci_lo'] == out['stats']['area']['ci_hi']


def test_correlated_noise_inflates_area_spread_over_iid():
    # Arrange: same marginal P per pixel, two different spatial error structures.
    # i.i.d. errors cancel in the sum; correlated errors move whole patches together.
    import cv2
    from scipy.special import ndtr
    p_true = np.full(SHAPE, 0.5)

    def run(correlated, seed=0):
        rng = np.random.default_rng(seed)
        node = _mod.EnsembleStatsNode()
        out = None
        for i in range(120):
            if correlated:
                g = rng.standard_normal(SHAPE).astype(np.float32)
                g = cv2.GaussianBlur(g, (0, 0), 4.0)
                g /= g.std()
                u = ndtr(g).astype(np.float32)
            else:
                u = rng.random(SHAPE).astype(np.float32)
            frame = ((u < p_true) * 255).astype(np.uint8)
            out = node.process({'mask': frame, 'tick': i},
                               {'components': False, 'boundary': False})
        return out

    # Act
    iid = run(False)
    corr = run(True)

    # Assert: identical mean area, far larger ensemble spread when errors correlate
    assert abs(iid['area_mean'] - corr['area_mean']) / iid['area_mean'] < 0.05
    assert corr['area_sd'] > 3.0 * iid['area_sd']


# ── confidence interval ───────────────────────────────────────────────────────

def test_ci_brackets_the_realisation_range():
    # Arrange: two distinct areas → the 95 % CI must sit inside [min, max]
    node = _mod.EnsembleStatsNode()

    # Act
    out = _feed(node, [_disc(10) if i % 2 else _disc(14) for i in range(40)])
    area = out['stats']['area']

    # Assert
    assert area['min'] <= area['ci_lo'] <= area['ci_hi'] <= area['max']
    assert area['ci_lo'] < area['mean'] < area['ci_hi']


# ── component count: topology, not derivable from the mean map ────────────────

def test_component_count_is_tracked_per_realisation():
    # Arrange: one disc vs two separated dots → component count alternates 1 / 2
    node = _mod.EnsembleStatsNode()
    two = np.zeros(SHAPE, np.uint8)
    two[10, 10] = 255
    two[50, 50] = 255

    # Act
    out = _feed(node, [_disc(8) if i % 2 else two for i in range(20)],
                components=True)

    # Assert
    comp = out['stats']['components']
    assert comp['min'] == 1 and comp['max'] == 2
    assert abs(comp['mean'] - 1.5) < 0.1


# ── boundary displacement against a reference ─────────────────────────────────

def test_boundary_displacement_grows_with_reference_mismatch():
    # Arrange: reference is the r=12 disc; realisations are r=12 (aligned) then r=16
    node_aligned = _mod.EnsembleStatsNode()
    node_off = _mod.EnsembleStatsNode()
    ref = _disc(12)
    params = {'components': False, 'boundary': True}

    # Act
    for i in range(6):
        aligned = node_aligned.process({'mask': _disc(12), 'tick': i, 'reference': ref}, params)
        off = node_off.process({'mask': _disc(16), 'tick': i, 'reference': ref}, params)

    # Assert: aligned boundaries sit on the reference, offset ones are ~4 px away
    assert aligned['stats']['boundary_dist']['mean'] < 1.0
    assert off['stats']['boundary_dist']['mean'] > 3.0


def test_boundary_metric_absent_without_reference():
    # Arrange / Act: boundary enabled but no reference wired
    node = _mod.EnsembleStatsNode()
    out = _feed(node, [_disc(10) for _ in range(5)], boundary=True)

    # Assert: the node does not fabricate the metric
    assert 'boundary_dist' not in out['stats']


# ── lifecycle: reset, target N, empty input ───────────────────────────────────

def test_upstream_tick_drop_resets_the_ensemble():
    # Arrange: accumulate while tick rises, then the driver restarts (tick → 0)
    node = _mod.EnsembleStatsNode()
    for t in (1, 2, 3):
        node.process({'mask': _disc(20), 'tick': t}, {'components': False})

    # Act
    out = node.process({'mask': _disc(5), 'tick': 0}, {'components': False})

    # Assert: only the post-reset realisation counts
    assert out['frame_count'] == 1
    assert abs(out['area_mean'] - int((_disc(5) > 127).sum())) < 1.0


def test_reset_button_clears_the_ensemble():
    # Arrange
    node = _mod.EnsembleStatsNode()
    node.process({'mask': _disc(20)}, {'components': False})
    node.process({'mask': _disc(20)}, {'components': False})

    # Act: rising-edge trigger
    out = node.process({'mask': _disc(6)}, {'components': False, 'reset': 1})

    # Assert
    assert out['frame_count'] == 1


def test_target_n_freezes_the_ensemble_and_flags_done():
    # Arrange
    node = _mod.EnsembleStatsNode()

    # Act: 10 realisations fed, Target N = 4
    dones = []
    out = None
    for i in range(10):
        out = node.process({'mask': _disc(9), 'tick': i},
                           {'components': False, 'target_n': 4})
        dones.append(out['done'])

    # Assert
    assert out['frame_count'] == 4
    assert dones[3] == 1.0 and dones[-1] == 1.0
    assert dones[0] == 0.0


def test_missing_mask_is_not_counted_as_a_realisation():
    # Arrange: a None input must not pollute the ensemble with a zero-area draw
    node = _mod.EnsembleStatsNode()
    node.process({'mask': _disc(10)}, {'components': False})

    # Act
    out = node.process({'mask': None}, {'components': False})

    # Assert
    assert out['frame_count'] == 1


def test_grid_change_resets_rather_than_crashing():
    # Arrange: upstream resolution change mid-run — areas are not comparable
    node = _mod.EnsembleStatsNode()
    node.process({'mask': _disc(10, (64, 64))}, {'components': False})

    # Act
    out = node.process({'mask': _disc(10, (32, 32))}, {'components': False})

    # Assert: fresh ensemble on the new grid
    assert out['frame_count'] == 1


def test_figure_is_rendered_as_bgr_image():
    # Arrange / Act
    node = _mod.EnsembleStatsNode()
    out = _feed(node, [_disc(10) if i % 2 else _disc(13) for i in range(12)])

    # Assert
    assert out['main'] is not None
    assert out['main'].ndim == 3 and out['main'].shape[2] == 3


# ── figure throttling: rendering must not run on every tick ───────────────────

def test_figure_render_is_throttled(monkeypatch):
    # Arrange: count actual renders while feeding 20 realisations with stride 5
    node = _mod.EnsembleStatsNode()
    calls = {'n': 0}
    real_render = node._render

    def counting_render(stats, ci):
        calls['n'] += 1
        return real_render(stats, ci)

    monkeypatch.setattr(node, '_render', counting_render)

    # Act
    for i in range(20):
        node.process({'mask': _disc(10), 'tick': i},
                     {'components': False, 'fig_every': 5})

    # Assert: first render plus one per stride — nowhere near 20
    assert calls['n'] <= 5, f'rendered {calls["n"]} times for 20 ticks'
    assert calls['n'] >= 1


def test_figure_always_refreshed_when_target_reached():
    # Arrange: a long stride would otherwise leave a stale figure at the end of a run
    node = _mod.EnsembleStatsNode()
    params = {'components': False, 'fig_every': 1000, 'target_n': 4}

    # Act
    out = None
    for i in range(4):
        out = node.process({'mask': _disc(10), 'tick': i}, params)

    # Assert
    assert out['done'] == 1.0
    assert out['main'] is not None
