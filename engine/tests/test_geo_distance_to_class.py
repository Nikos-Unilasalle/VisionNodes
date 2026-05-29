import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_distance_to_class.py')
_spec = importlib.util.spec_from_file_location('plugins.geo_distance_to_class', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DistanceToClassNode = NODE_CLASS_REGISTRY['geo_distance_to_class']


def test_distance_to_class_basic():
    # 5x5 grid. Target class is 1 (water). Put water at (2,2)
    bands = np.zeros((1, 5, 5), dtype=np.float32)
    bands[0, 2, 2] = 1

    geo = {
        'bands': bands,
        'count': 1,
        'crs': 'EPSG:32622',
        'transform': [10.0, 0.0, 0.0, 0.0, -10.0, 0.0]
    }

    node = DistanceToClassNode()
    res = node.process({'geotiff': geo}, {'target_class': 1, 'pixel_size_m': 10.0})

    out_bands = res['geotiff']['bands']
    assert out_bands.shape == (1, 5, 5)

    # Distance to target at (2,2) should be 0
    assert out_bands[0, 2, 2] == 0.0

    # Distance at adjacent (2,3) should be 10.0 meters
    assert np.allclose(out_bands[0, 2, 3], 10.0, atol=1e-2)

    # Distance at diagonal (3,3) should be 14.14 meters (OpenCV uses approximation, so tolerance atol=0.2)
    assert np.allclose(out_bands[0, 3, 3], 14.14, atol=0.2)


def test_distance_to_class_missing():
    # Grid without any target class 1
    bands = np.zeros((1, 5, 5), dtype=np.float32)

    geo = {
        'bands': bands,
        'count': 1,
        'crs': 'EPSG:32622',
        'transform': [10.0, 0.0, 0.0, 0.0, -10.0, 0.0]
    }

    node = DistanceToClassNode()
    res = node.process({'geotiff': geo}, {'target_class': 1, 'pixel_size_m': 10.0})

    out_bands = res['geotiff']['bands']
    assert np.all(out_bands == 99999.0)
