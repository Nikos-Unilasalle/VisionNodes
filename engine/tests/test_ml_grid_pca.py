import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'ml_grid_pca.py')
_spec = importlib.util.spec_from_file_location('plugins.ml_grid_pca', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SpatialGridPCANode = NODE_CLASS_REGISTRY['ml_grid_pca']

def test_spatial_pca():
    # Simulate a time series of 15 frames, size 8x8
    grids = np.random.rand(15, 8, 8)
    
    # Introduce NaN mask on top left pixels (simulating land)
    grids[:, 0:3, 0:3] = np.nan

    node = SpatialGridPCANode()
    res = node.process({'grids': grids}, {
        'n_components': 3,
        'standardize': True,
        'colormap': 3
    })

    assert res is not None
    assert 'reconstructed' in res
    assert 'modes' in res
    assert 'preview' in res
    assert 'mse' in res

    recon = res['reconstructed']
    modes = res['modes']
    mse = res['mse']

    assert recon.shape == (15, 8, 8)
    assert modes.shape == (3, 8, 8)
    assert isinstance(mse, float)

    # Verify that the NaN land mask was preserved in the reconstruction
    assert np.isnan(recon[:, 0:3, 0:3]).all()
    # Verify that ocean pixels are reconstructed without NaNs
    assert not np.isnan(recon[:, 3:, 3:]).any()

    # Verify modes have NaNs preserved on the land
    assert np.isnan(modes[:, 0:3, 0:3]).all()
    assert not np.isnan(modes[:, 3:, 3:]).any()

def test_spatial_pca_advanced():
    grids = np.random.rand(10, 6, 6)
    grids[:, 0, 0] = np.nan

    node = SpatialGridPCANode()
    meta = {'lat_min': -30.0, 'lat_max': -20.0}

    # Test with detrend='Linear', cos_lat=True, solver='randomized'
    res = node.process({
        'grids': grids,
        'meta': meta
    }, {
        'n_components': 2,
        'standardize': True,
        'detrend': 2,       # 'Linear'
        'cos_lat': True,
        'solver': 3,        # 'randomized'
        'colormap': 0
    })

    assert res is not None
    assert 'reconstructed' in res
    assert 'modes' in res
    assert res['reconstructed'].shape == (10, 6, 6)
    assert res['modes'].shape == (2, 6, 6)
    assert np.isnan(res['reconstructed'][:, 0, 0]).all()

