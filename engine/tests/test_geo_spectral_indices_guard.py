"""
test_geo_spectral_indices_guard.py — validity guard on normalised-difference
indices (reference water-mask conformity). Default path stays the legacy
(a - b) / (a + b + ε); with valid_min set, near-zero / sub-floor reflectance
becomes NaN so it casts no downstream vote.
"""
import os
import sys
import importlib.util

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_spectral_indices.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_spectral_indices', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_spectral_indices'] = _mod
_spec.loader.exec_module(_mod)


def test_norm_index_default_is_legacy_fast_path():
    # Arrange
    a = np.array([[0.4]], dtype=np.float32)
    b = np.array([[0.1]], dtype=np.float32)

    # Act
    out = _mod._norm_index(a, b)

    # Assert: unchanged (a - b) / (a + b + 1e-8), no NaN, no clipping branch
    assert abs(float(out[0, 0]) - (0.3 / (0.5 + 1e-8))) < 1e-6


def test_guard_nans_subfloor_and_near_zero_denominator():
    # Arrange: one valid pixel, one sub-floor band, one ~zero denominator
    a = np.array([0.40, -0.005, 0.001], dtype=np.float32).reshape(1, 3)
    b = np.array([0.10,  0.20,  -0.001], dtype=np.float32).reshape(1, 3)

    # Act
    out = _mod._norm_index(a, b, valid_min=-0.002)

    # Assert: valid pixel kept; sub-floor (a ≤ -0.002) NaN; |a+b|<den_min NaN
    assert np.isfinite(out[0, 0])
    assert np.isnan(out[0, 1])
    assert np.isnan(out[0, 2])


def test_guard_clips_to_unit_range():
    # Arrange: a strongly dominates → raw ratio near 1
    a = np.array([[1.0]], dtype=np.float32)
    b = np.array([[-0.9]], dtype=np.float32)  # a+b=0.1 small but > floor

    # Act
    out = _mod._norm_index(a, b, valid_min=-1.0)

    # Assert: bounded to [-1, 1]
    assert -1.0 <= float(out[0, 0]) <= 1.0


def test_process_guard_propagates_nan_into_stack():
    # Arrange: 1x2 scene, blue..swir2 (6 bands); col 1 has sub-floor green & nir
    H, W = 1, 2
    bands = np.zeros((6, H, W), dtype=np.float32)
    # blue, green, red, nir, swir1, swir2
    bands[1] = [[0.30, -0.01]]   # green
    bands[3] = [[0.02, -0.01]]   # nir
    bands[4] = [[0.01, -0.01]]   # swir1
    geo = {'bands': bands, 'count': 6, 'dtype': 'float32'}

    params = {
        'sensor': 0, 'green_band': 2, 'nir_band': 4, 'swir_band': 5,
        'red_band': 3, 'blue_band': 1,
        'ndvi': False, 'ndwi': True, 'mndwi': True,
        'guard_invalid': True, 'valid_min': -0.002,
    }

    # Act
    res = _mod.SpectralIndicesNode().process({'geotiff': geo}, params)
    stack = res['stack']['bands']  # (2, H, W): NDWI, MNDWI

    # Assert: valid column finite, sub-floor column NaN on both indices
    assert np.all(np.isfinite(stack[:, 0, 0]))
    assert np.all(np.isnan(stack[:, 0, 1]))
