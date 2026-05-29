import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
import pandas as pd
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_centroids.py')
_spec = importlib.util.spec_from_file_location('plugins.geo_centroids', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GeoCentroidsNode = NODE_CLASS_REGISTRY['geo_centroids']


def test_geo_centroids_basic():
    # 10x10 grid with two white blobs (255)
    # Blob 1: 1 pixel at (2,2) - area = 1
    # Blob 2: 2x2 square at (6,6) to (7,7) - area = 4
    bands = np.zeros((1, 10, 10), dtype=np.float32)
    bands[0, 2, 2] = 255.0
    bands[0, 6, 6] = 255.0
    bands[0, 6, 7] = 255.0
    bands[0, 7, 6] = 255.0
    bands[0, 7, 7] = 255.0

    # Affine transform parameters: (a=0.01, b=0, c=-53.0, d=0, e=-0.01, f=5.0)
    # Using WGS84 so transform maps directly to lon/lat without projection needed
    from affine import Affine
    transform = Affine(0.01, 0.0, -53.0, 0.0, -0.01, 5.0)

    geo = {
        'bands': bands,
        'count': 1,
        'crs': 'EPSG:4326',
        'transform': transform,
        'band_names': ['mask']
    }

    # Test 1: Min Area = 2 (Blob 1 should be filtered out, only Blob 2 remains)
    node = GeoCentroidsNode()
    res = node.process({'geotiff': geo}, {'min_area': 2, 'max_area': 100})
    
    assert 'table' in res
    assert 'out_list' in res
    assert 'preview' in res

    df = res['table']
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]['area_px'] == 4.0
    # Expected centroid of Blob 2 is (6.5, 6.5)
    # lon = -53.0 + 0.01 * 6.5 = -52.935
    # lat = 5.0 - 0.01 * 6.5 = 4.935
    assert np.allclose(df.iloc[0]['longitude'], -52.935)
    assert np.allclose(df.iloc[0]['latitude'], 4.935)

    # Test 2: Min Area = 1 (Both blobs detected)
    res2 = node.process({'geotiff': geo}, {'min_area': 1, 'max_area': 100})
    df2 = res2['table']
    assert len(df2) == 2
    
    # Sort by area_px
    df2_sorted = df2.sort_values(by='area_px').reset_index(drop=True)
    assert df2_sorted.iloc[0]['area_px'] == 1.0
    assert np.allclose(df2_sorted.iloc[0]['longitude'], -53.0 + 0.01 * 2)
    assert np.allclose(df2_sorted.iloc[0]['latitude'], 5.0 - 0.01 * 2)

    assert df2_sorted.iloc[1]['area_px'] == 4.0
    assert np.allclose(df2_sorted.iloc[1]['longitude'], -52.935)
    assert np.allclose(df2_sorted.iloc[1]['latitude'], 4.935)
