import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
import pytest
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_netcdf_reader.py')
_spec = importlib.util.spec_from_file_location('plugins.geo_netcdf_reader', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

NetCDFGridReaderNode = NODE_CLASS_REGISTRY['geo_netcdf_reader']

@pytest.fixture
def dummy_nc_file(tmp_path):
    import xarray as xr
    import pandas as pd

    # Create dummy spatial-temporal grid data
    times = pd.date_range("2026-06-01", periods=5)
    lats = np.linspace(-35, -31, 10)
    lons = np.linspace(-35, -31, 10)

    # 5 time steps, 10x10 grid
    data = np.random.rand(5, 10, 10)
    # Put some NaNs to simulate land mask
    data[:, 0:2, 0:2] = np.nan

    ds = xr.Dataset(
        {"thetao": (["time", "latitude", "longitude"], data)},
        coords={
            "time": times,
            "latitude": lats,
            "longitude": lons,
        }
    )
    
    file_path = tmp_path / "dummy_data.nc"
    ds.to_netcdf(str(file_path))
    return str(file_path)

def test_netcdf_reader_single_file(dummy_nc_file):
    node = NetCDFGridReaderNode()
    res = node.process({}, {
        'path': dummy_nc_file,
        'variable': 'thetao',
        'lat_range': '-34,-32',
        'lon_range': '-34,-32',
        'colormap': 0
    })

    assert res is not None
    assert 'grids' in res
    assert 'preview' in res
    assert 'meta' in res

    grids = res['grids']
    assert isinstance(grids, np.ndarray)
    assert len(grids.shape) == 3
    assert grids.shape[0] == 5  # 5 time frames
    # Sliced latitude/longitude should be smaller than 10x10
    assert grids.shape[1] < 10
    assert grids.shape[2] < 10

    meta = res['meta']
    assert meta['variable_selected'] == 'thetao'
    assert 'lat_min' in meta
    assert 'lon_min' in meta
