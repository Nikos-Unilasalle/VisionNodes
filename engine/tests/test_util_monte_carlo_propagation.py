"""
test_util_monte_carlo_propagation.py — Unit tests for the generic Monte Carlo propagation utility node.
"""
import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'util_monte_carlo_propagation.py'
)
_spec = importlib.util.spec_from_file_location('plugins.util_monte_carlo_propagation', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.util_monte_carlo_propagation'] = _mod
_spec.loader.exec_module(_mod)


def test_process_missing_seed():
    """Test process method with missing seed input."""
    node = _mod.UtilMonteCarloPropagationNode()
    res = node.process({}, {})
    assert res['probability'] is None
    assert res['preview'] is None
    assert res['stats'] is None


def test_process_with_raw_inputs():
    """Test process method with raw NumPy array inputs (no geodict)."""
    # 20x20 binary mask seed
    seed = np.zeros((20, 20), dtype=np.uint8)
    seed[10, 10] = 255  # seed in the center

    # 20x20 attractiveness map (all ones)
    attr = np.ones((20, 20), dtype=np.uint8) * 255

    inputs = {
        'seed': seed,
        'attractiveness': attr
    }

    params = {
        'n_simulations': 50,
        'n_steps': 5,
        'resistance': 0.3,
        'neighborhood': '8-connected'
    }

    node = _mod.UtilMonteCarloPropagationNode()
    res = node.process(inputs, params)

    # Validate output structure
    assert 'probability' in res
    assert 'preview' in res
    assert 'stats' in res
    assert '_thumb' in res

    # Validate probability map
    prob = res['probability']
    assert prob.shape == (20, 20)
    assert prob.dtype == np.uint8
    # The starting seed must have 100% probability (represented as 255)
    assert prob[10, 10] == 255

    # Stats validation
    stats = res['stats']
    assert stats['simulations_run'] == 50
    assert stats['seed_surface_pct'] > 0.0

    # Visual preview validation
    preview = res['preview']
    assert preview.shape == (20, 20, 3)
    # The active seed pixel at (10, 10) must be highlighted in Cyan BGR: [255, 255, 0]
    assert np.array_equal(preview[10, 10], [255, 255, 0])


def test_process_with_mismatched_shapes():
    """Test that attractiveness map is correctly resized to match the seed map shape."""
    seed = np.zeros((10, 10), dtype=np.uint8)
    seed[5, 5] = 255

    # 20x20 attractiveness map (mismatched shape)
    attr = np.ones((20, 20), dtype=np.uint8) * 128

    inputs = {
        'seed': seed,
        'attractiveness': attr
    }

    params = {
        'n_simulations': 20,
        'n_steps': 2,
        'resistance': 0.5,
        'neighborhood': '4-connected'
    }

    node = _mod.UtilMonteCarloPropagationNode()
    res = node.process(inputs, params)

    assert res['probability'].shape == (10, 10)
    assert res['preview'].shape == (10, 10, 3)
