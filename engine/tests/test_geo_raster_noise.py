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
