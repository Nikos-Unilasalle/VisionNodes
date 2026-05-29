import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
import pandas as pd
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_circle.py')
_spec = importlib.util.spec_from_file_location('plugins.geo_circle', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GeoCircleNode = NODE_CLASS_REGISTRY['geo_circle']


def test_geo_circle_single():
    # 10x10 empty base raster
    bands = np.zeros((1, 10, 10), dtype=np.float32)

    from affine import Affine
    # 0.01 degree per pixel. Centered around -53.0 W, 5.0 N
    transform = Affine(0.01, 0.0, -53.0, 0.0, -0.01, 5.0)

    geo = {
        'bands': bands,
        'count': 1,
        'crs': 'EPSG:4326',
        'transform': transform,
        'band_names': ['mask']
    }

    # Draw single circle at lat=4.95, lon=-52.95 (col=5, row=5)
    # Radius = 1.0 pixel, thickness = -1 (filled)
    node = GeoCircleNode()
    res = node.process(
        {'geotiff': geo},
        {
            'latitude': 4.95,
            'longitude': -52.95,
            'radius': 1.0,
            'radius_unit': 1,  # 1 = pixels
            'thickness': -1,
            'fill': True,
            'color': '#FFFFFF',
            'burn_mode': 1  # first_band
        }
    )

    assert 'geotiff' in res
    assert 'preview' in res
    
    out_bands = res['geotiff']['bands']
    assert out_bands.shape == (1, 10, 10)
    # The center pixel (5, 5) must be 255.0 (White)
    assert out_bands[0, 5, 5] == 255.0


def test_geo_circle_table():
    bands = np.zeros((1, 10, 10), dtype=np.float32)

    from affine import Affine
    transform = Affine(0.01, 0.0, -53.0, 0.0, -0.01, 5.0)

    geo = {
        'bands': bands,
        'count': 1,
        'crs': 'EPSG:4326',
        'transform': transform,
        'band_names': ['mask']
    }

    # DataFrame with two points: (4.98, -52.98) -> (2,2) and (4.93, -52.93) -> (7,7)
    df = pd.DataFrame({
        'lat': [4.98, 4.93],
        'lon': [-52.98, -52.93]
    })

    node = GeoCircleNode()
    res = node.process(
        {'geotiff': geo, 'table': df},
        {
            'lat_col': 'lat',
            'lon_col': 'lon',
            'radius': 0.5,
            'radius_unit': 1,  # pixels
            'thickness': -1,
            'fill': True,
            'color': '#FFFFFF',
            'burn_mode': 0  # new_band
        }
    )

    assert 'geotiff' in res
    out_bands = res['geotiff']['bands']
    # If new_band was used, output count should be 2 (original band + circle band)
    assert out_bands.shape == (2, 10, 10)
    assert out_bands[1, 2, 2] == 255.0
    assert out_bands[1, 7, 7] == 255.0
