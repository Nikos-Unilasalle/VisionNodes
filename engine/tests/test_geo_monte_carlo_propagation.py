"""
test_geo_monte_carlo_propagation.py — Unit tests for the Monte Carlo propagation geoprocessing node.
"""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_monte_carlo_propagation.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_monte_carlo_propagation', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_monte_carlo_propagation'] = _mod
_spec.loader.exec_module(_mod)


def test_reproject_onto_fallback():
    """Test _reproject_onto when no CRS/transform is available (should use OpenCV fallback)."""
    # Target grid: 10x10
    target_geo = {
        'bands': np.zeros((1, 10, 10), dtype=np.float32),
        'crs': None,
        'transform': None
    }
    # Source grid: 5x5 containing ones
    source_geo = {
        'bands': np.ones((1, 5, 5), dtype=np.float32),
        'crs': None,
        'transform': None
    }

    aligned = _mod._reproject_onto(target_geo, source_geo)
    assert aligned.shape == (10, 10)
    assert np.allclose(aligned, 1.0)


def test_process_missing_inputs():
    """Test process method with missing inputs."""
    node = _mod.GeoMonteCarloPropagationNode()
    res = node.process({}, {})
    assert res['risk'] is None
    assert res['preview'] is None
    assert res['stats'] is None


def test_process_with_valid_inputs():
    """Test process method with valid dummy geotiffs."""
    # 20x20 grids
    active_arr = np.zeros((20, 20), dtype=np.float32)
    # Seed active mines in center
    active_arr[10, 10] = 1.0

    slope_arr = np.ones((20, 20), dtype=np.float32) * 5.0  # low slope (5 degrees)
    hand_arr = np.ones((20, 20), dtype=np.float32) * 3.0   # low HAND (3 meters)

    active_geo = {
        'bands': active_arr[np.newaxis],
        'crs': 'EPSG:4326',
        'transform': [0.0001, 0.0, -53.0, 0.0, -0.0001, 4.0]
    }
    slope_geo = {
        'bands': slope_arr[np.newaxis],
        'crs': 'EPSG:4326',
        'transform': [0.0001, 0.0, -53.0, 0.0, -0.0001, 4.0]
    }
    hand_geo = {
        'bands': hand_arr[np.newaxis],
        'crs': 'EPSG:4326',
        'transform': [0.0001, 0.0, -53.0, 0.0, -0.0001, 4.0]
    }

    inputs = {
        'active': active_geo,
        'slope': slope_geo,
        'hand': hand_geo
    }

    params = {
        'n_simulations': 50,
        'n_steps': 3,
        'prob_threshold': 0.5,
        'hand_max': 12.0,
        'slope_max': 15.0
    }

    node = _mod.GeoMonteCarloPropagationNode()
    res = node.process(inputs, params)

    # Validate output structure
    assert 'risk' in res
    assert 'preview' in res
    assert 'stats' in res
    assert '_thumb' in res

    # Validate risk geodict
    risk_geo = res['risk']
    assert risk_geo['bands'].shape == (1, 20, 20)
    assert risk_geo['dtype'] == 'float32'
    assert risk_geo['count'] == 1

    # Active site must be registered as active at T0
    assert np.allclose(risk_geo['bands'][0, 10, 10], 100.0)

    # Stats validation
    stats = res['stats']
    assert stats['simulations_run'] == 50
    assert stats['surface_active_T0_pct'] > 0.0
    assert 'surface_risk_high_pct' in stats
    assert 'surface_risk_medium_pct' in stats
    assert 'surface_risk_low_pct' in stats

    # Visual preview validation
    preview = res['preview']
    assert preview.shape == (20, 20, 3)
    # The active seed pixel at (10, 10) must be colored Cyan-Blue BGR: [200, 100, 40]
    assert np.array_equal(preview[10, 10], [200, 100, 40])
