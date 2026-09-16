"""
test_geo_raster_noise.py — Unit tests for the generic per-band raster Gaussian noise node.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_raster_noise.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_raster_noise', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_raster_noise'] = _mod
_spec.loader.exec_module(_mod)


def _geo(bands):
    return {'bands': bands.astype(np.float32), 'count': bands.shape[0],
            'band_names': [f'B{i+1}' for i in range(bands.shape[0])], 'dtype': 'float32'}


def test_missing_input():
    node = _mod.RasterNoiseNode()
    res = node.process({}, {})
    assert res['geotiff'] is None
    assert res['preview'] is None


def test_perturbs_and_preserves_shape():
    bands = np.full((3, 16, 16), 0.4, dtype=np.float32)
    node = _mod.RasterNoiseNode()
    res = node.process({'geotiff': _geo(bands)}, {'sigma_abs': 0.02, 'sigma_rel': 0.0, 'seed': 7})
    out = res['geotiff']['bands']
    assert out.shape == bands.shape
    assert out.dtype == np.float32
    # noise actually applied
    assert not np.allclose(out, bands)
    # ~σ on a flat 0.4 field with sigma_rel=0 → std close to sigma_abs
    assert abs(float(out.std()) - 0.02) < 0.01


def test_sigma_zero_is_identity():
    bands = np.random.default_rng(1).random((2, 8, 8)).astype(np.float32)
    node = _mod.RasterNoiseNode()
    res = node.process({'geotiff': _geo(bands)}, {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 0})
    assert np.allclose(res['geotiff']['bands'], bands)


def test_clip_negative():
    bands = np.full((1, 8, 8), 0.001, dtype=np.float32)
    node = _mod.RasterNoiseNode()
    res = node.process({'geotiff': _geo(bands)},
                       {'sigma_abs': 0.5, 'sigma_rel': 0.0, 'seed': 3, 'clip_negative': True})
    assert float(res['geotiff']['bands'].min()) >= 0.0


def test_clip_range_bounds_and_supersedes_clip_negative():
    # Arrange: heavy noise so draws blow past both bounds; range = [-0.01, 0.5]
    bands = np.full((1, 16, 16), 0.25, dtype=np.float32)
    node = _mod.RasterNoiseNode()

    # Act
    res = node.process(
        {'geotiff': _geo(bands)},
        {'sigma_abs': 1.0, 'sigma_rel': 0.0, 'seed': 5,
         'clip_negative': True, 'clip_min': -0.01, 'clip_max': 0.5},
    )
    out = res['geotiff']['bands']

    # Assert: clamped to [-0.01, 0.5]; range clip lets values go negative even
    # though clip_negative=True (range supersedes the legacy floor)
    assert float(out.min()) >= -0.01
    assert float(out.max()) <= 0.5
    assert float(out.min()) < 0.0


def test_clip_range_disabled_when_max_le_min():
    # Arrange: defaults 0/0 → range off → legacy clip_negative path stays active
    bands = np.full((1, 8, 8), 0.001, dtype=np.float32)
    node = _mod.RasterNoiseNode()

    # Act
    res = node.process(
        {'geotiff': _geo(bands)},
        {'sigma_abs': 0.5, 'sigma_rel': 0.0, 'seed': 3,
         'clip_negative': True, 'clip_min': 0.0, 'clip_max': 0.0},
    )

    # Assert: still floored at 0 by clip_negative
    assert float(res['geotiff']['bands'].min()) >= 0.0


def test_relative_noise_scales_with_signal():
    """σ_rel should produce larger spread on larger values."""
    low  = np.full((1, 32, 32), 0.1, dtype=np.float32)
    high = np.full((1, 32, 32), 0.9, dtype=np.float32)
    p = {'sigma_abs': 0.0, 'sigma_rel': 0.1, 'seed': 5, 'clip_negative': False}
    n1, n2 = _mod.RasterNoiseNode(), _mod.RasterNoiseNode()
    s_low  = _mod.RasterNoiseNode().process({'geotiff': _geo(low)},  p)['geotiff']['bands'].std()
    s_high = _mod.RasterNoiseNode().process({'geotiff': _geo(high)}, p)['geotiff']['bands'].std()
    assert s_high > s_low * 3  # ~9x more spread expected


def test_seed_reproducible_sequence_varies_per_tick():
    bands = np.full((1, 12, 12), 0.5, dtype=np.float32)
    p = {'sigma_abs': 0.05, 'sigma_rel': 0.0, 'seed': 42, 'clip_negative': False}

    a = _mod.RasterNoiseNode()
    b = _mod.RasterNoiseNode()
    a1 = a.process({'geotiff': _geo(bands)}, p)['geotiff']['bands'].copy()
    a2 = a.process({'geotiff': _geo(bands)}, p)['geotiff']['bands'].copy()
    b1 = b.process({'geotiff': _geo(bands)}, p)['geotiff']['bands'].copy()

    # Reproducible across instances at the same tick…
    assert np.allclose(a1, b1)
    # …but each tick is a fresh draw (Monte-Carlo variation)
    assert not np.allclose(a1, a2)


def test_start_stop_button_toggles_and_freezes():
    """The Start/Stop trigger flips the running state on each rising edge. When
    stopped the node is paused (engine caches it) and returns the frozen last frame
    — this is the CPU brake. Mirrors how the UI pulses a trigger 0→1→0."""
    bands = np.full((1, 12, 12), 0.5, dtype=np.float32)
    geo = _geo(bands)
    node = _mod.RasterNoiseNode()
    P = {'sigma_abs': 0.05}

    # Runs by default (no press)
    running = node.process({'geotiff': geo}, {**P, 'toggle_run': 0})
    assert node._paused is False
    frozen_ref = running['geotiff']['bands'].copy()

    # Press Stop: rising edge 0→1 flips to stopped; trigger then resets to 0
    s1 = node.process({'geotiff': geo}, {**P, 'toggle_run': 1})
    s2 = node.process({'geotiff': geo}, {**P, 'toggle_run': 0})   # trigger auto-reset
    assert node._paused is True
    assert np.array_equal(s1['geotiff']['bands'], frozen_ref)
    assert np.array_equal(s2['geotiff']['bands'], frozen_ref)

    # A held value (no new rising edge) must NOT flip again
    s3 = node.process({'geotiff': geo}, {**P, 'toggle_run': 0})
    assert node._paused is True
    assert np.array_equal(s3['geotiff']['bands'], frozen_ref)

    # Press Start: next rising edge flips back to running and redraws
    node.process({'geotiff': geo}, {**P, 'toggle_run': 1})
    assert node._paused is False
    resumed = node.process({'geotiff': geo}, {**P, 'toggle_run': 0})
    assert not np.array_equal(resumed['geotiff']['bands'], frozen_ref)


def test_entropy_seed_varies():
    bands = np.full((1, 12, 12), 0.5, dtype=np.float32)
    p = {'sigma_abs': 0.05, 'sigma_rel': 0.0, 'seed': -1, 'clip_negative': False}
    r1 = _mod.RasterNoiseNode().process({'geotiff': _geo(bands)}, p)['geotiff']['bands']
    r2 = _mod.RasterNoiseNode().process({'geotiff': _geo(bands)}, p)['geotiff']['bands']
    assert not np.allclose(r1, r2)


def test_max_ticks_auto_stops():
    """Target N: after N realisations the node pauses and freezes its output."""
    bands = np.full((1, 8, 8), 0.4, dtype=np.float32)
    geo = _geo(bands)
    node = _mod.RasterNoiseNode()
    P = {'sigma_abs': 0.02, 'sigma_rel': 0.0, 'seed': 5, 'clip_negative': False, 'max_ticks': 3}

    o1 = node.process({'geotiff': geo}, P); assert o1['tick'] == 1
    o2 = node.process({'geotiff': geo}, P); assert o2['tick'] == 2
    o3 = node.process({'geotiff': geo}, P); assert o3['tick'] == 3
    assert node._paused is False  # still drawing on the 3rd

    # 4th call: tick already == max → paused, output frozen at the 3rd realisation
    o4 = node.process({'geotiff': geo}, P)
    assert node._paused is True
    assert o4['tick'] == 3
    assert np.array_equal(o4['geotiff']['bands'], o3['geotiff']['bands'])


def test_reset_button_rewinds_tick_and_resumes():
    bands = np.full((1, 8, 8), 0.4, dtype=np.float32)
    geo = _geo(bands)
    node = _mod.RasterNoiseNode()
    P = {'sigma_abs': 0.02, 'sigma_rel': 0.0, 'seed': 5, 'clip_negative': False, 'max_ticks': 2}

    first = node.process({'geotiff': geo}, P)        # tick → 1
    node.process({'geotiff': geo}, P)                # tick → 2, then auto-stop arms
    node.process({'geotiff': geo}, P)                # paused
    assert node._paused is True

    # Reset (rising edge): tick → 0, resume, redraw the seed-0 realisation
    after = node.process({'geotiff': geo}, {**P, 'reset': 1})
    assert node._paused is False
    assert after['tick'] == 1
    # Same seed+tick sequence ⇒ identical to the very first realisation (reproducible)
    assert np.array_equal(after['geotiff']['bands'], first['geotiff']['bands'])


# ── MINOR 17: independent error terms combine in quadrature, not linearly ─────

def _sigma_of(node, value, n=4000, **params):
    """Empirical per-pixel sigma of the perturbation at a constant reflectance."""
    bands = np.full((1, 1, n), value, dtype=np.float32)
    base = {'sigma_abs': 0.005, 'sigma_rel': 0.015, 'seed': 3,
            'clip_negative': False}
    base.update(params)
    out = node.process({'geotiff': _geo(bands)}, base)['geotiff']['bands']
    return float(np.std(out - value))


def test_linear_combination_is_the_default():
    # Back-compatible: sigma = sigma_abs + sigma_rel*|rho|
    node = _mod.RasterNoiseNode()
    got = _sigma_of(node, 0.3)
    assert abs(got - (0.005 + 0.015 * 0.3)) < 0.0005, got


def test_quadrature_combination_is_available():
    # sqrt(sigma_abs^2 + (sigma_rel*rho)^2) — the correct combination for
    # independent error contributions
    node = _mod.RasterNoiseNode()
    got = _sigma_of(node, 0.3, sigma_combine=1)
    want = np.sqrt(0.005 ** 2 + (0.015 * 0.3) ** 2)
    assert abs(got - want) < 0.0005, (got, want)


def test_linear_overstates_sigma_on_bright_pixels():
    """The reason this matters: on bright land the two differ by ~34 %."""
    node = _mod.RasterNoiseNode()
    lin = _sigma_of(node, 0.3, sigma_combine=0)
    quad = _sigma_of(node, 0.3, sigma_combine=1)
    assert lin / quad > 1.25, (lin, quad)
    # ...while being indistinguishable over water, where rho is tiny
    lin_w = _sigma_of(node, 0.005, sigma_combine=0)
    quad_w = _sigma_of(node, 0.005, sigma_combine=1)
    assert abs(lin_w / quad_w - 1.0) < 0.05


# ── SERIOUS 10: co-registration is the dominant term for boundary metrics ─────

def _ramp(h=64, w=64, n_bands=2):
    """A diagonal ramp: any translation changes the values measurably."""
    yy, xx = np.mgrid[0:h, 0:w]
    a = (xx + yy).astype(np.float32) / (h + w)
    return np.stack([a] * n_bands)


def test_no_geometric_shift_by_default():
    node = _mod.RasterNoiseNode()
    bands = _ramp()
    out = node.process({'geotiff': _geo(bands)},
                       {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 1})['geotiff']['bands']
    assert np.allclose(out, bands, atol=1e-5), 'default must not move the raster'


def test_subpixel_shift_moves_the_raster():
    node = _mod.RasterNoiseNode()
    bands = _ramp()
    out = node.process({'geotiff': _geo(bands)},
                       {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 1,
                        'shift_px': 0.5})['geotiff']['bands']
    inner = (slice(None), slice(8, -8), slice(8, -8))
    assert not np.allclose(out[inner], bands[inner], atol=1e-4)


def test_shift_is_common_to_all_bands():
    """Co-registration error is a scene-level rigid shift, not per-band jitter."""
    node = _mod.RasterNoiseNode()
    bands = _ramp(n_bands=3)
    out = node.process({'geotiff': _geo(bands)},
                       {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 5,
                        'shift_px': 1.0})['geotiff']['bands']
    inner = (slice(8, -8), slice(8, -8))
    assert np.allclose(out[0][inner], out[1][inner], atol=1e-5)
    assert np.allclose(out[0][inner], out[2][inner], atol=1e-5)


def test_shift_magnitude_follows_the_parameter():
    """A larger shift_px must displace the scene further, on average."""
    bands = _ramp(128, 128)
    inner = (slice(16, -16), slice(16, -16))

    def mean_abs_move(px, draws=12):
        node = _mod.RasterNoiseNode()
        tot = []
        for i in range(draws):
            out = node.process({'geotiff': _geo(bands)},
                               {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 100,
                                'shift_px': px})['geotiff']['bands'][0]
            tot.append(float(np.nanmean(np.abs(out[inner] - bands[0][inner]))))
        return float(np.mean(tot))

    assert mean_abs_move(2.0) > 2.0 * mean_abs_move(0.5)


def test_shift_is_reproducible_under_a_fixed_seed():
    bands = _ramp()
    a = _mod.RasterNoiseNode().process(
        {'geotiff': _geo(bands)},
        {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 42, 'shift_px': 1.0})['geotiff']['bands']
    b = _mod.RasterNoiseNode().process(
        {'geotiff': _geo(bands)},
        {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 42, 'shift_px': 1.0})['geotiff']['bands']
    # equal_nan: the shift leaves a NaN border by design, marking pixels that moved in
    # from outside the scene as invalid rather than silently duplicating the edge.
    assert np.allclose(a, b, equal_nan=True)


def test_shift_marks_vacated_pixels_invalid():
    bands = _ramp()
    out = _mod.RasterNoiseNode().process(
        {'geotiff': _geo(bands)},
        {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 42, 'shift_px': 1.5})['geotiff']['bands']
    assert np.isnan(out).any(), 'pixels shifted in from outside must not be fabricated'
    assert np.isfinite(out[:, 8:-8, 8:-8]).all(), 'the interior must stay valid'
