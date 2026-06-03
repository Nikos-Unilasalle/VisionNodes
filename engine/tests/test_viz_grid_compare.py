import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'viz_grid_compare.py')
_spec = importlib.util.spec_from_file_location('plugins.viz_grid_compare', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GridCompareDashboardNode = NODE_CLASS_REGISTRY['viz_grid_compare']

def test_grid_compare():
    orig = np.random.rand(10, 6, 6)
    recon = orig + np.random.normal(0, 0.05, (10, 6, 6))

    # Add land mask
    orig[:, 0:2, 0:2] = np.nan
    recon[:, 0:2, 0:2] = np.nan

    node = GridCompareDashboardNode()
    res = node.process({'original': orig, 'reconstructed': recon}, {
        'frame_idx': 2,
        'colormap': 0
    })

    assert res is not None
    assert 'preview' in res
    assert 'frame_mse' in res
    assert 'frame_psnr' in res

    assert isinstance(res['frame_mse'], float)
    assert isinstance(res['frame_psnr'], float)
    assert res['frame_mse'] > 0
    assert res['preview'] is not None
    assert isinstance(res['preview'], np.ndarray)
