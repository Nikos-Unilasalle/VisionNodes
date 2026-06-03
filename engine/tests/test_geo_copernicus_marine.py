import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
from unittest.mock import patch
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_copernicus_marine.py')
_spec = importlib.util.spec_from_file_location('plugins.geo_copernicus_marine', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GeoCopernicusMarineNode = NODE_CLASS_REGISTRY['geo_copernicus_marine']

def mock_subset(dataset_id, username, password, variables, minimum_longitude, maximum_longitude,
                minimum_latitude, maximum_latitude, start_datetime, end_datetime, output_filename,
                force_download=True):
    # When called, write a dummy NetCDF file with expected structure
    import xarray as xr
    import pandas as pd

    times = pd.date_range("2023-01-01", periods=3)
    lats = np.linspace(minimum_latitude, maximum_latitude, 5)
    lons = np.linspace(minimum_longitude, maximum_longitude, 5)

    data = np.random.rand(3, 5, 5)
    # Add land NaNs
    data[:, 0, 0] = np.nan

    ds = xr.Dataset(
        {variables[0]: (["time", "latitude", "longitude"], data)},
        coords={
            "time": times,
            "latitude": lats,
            "longitude": lons,
        }
    )
    ds.to_netcdf(output_filename)

@patch('copernicusmarine.subset', side_effect=mock_subset)
def test_copernicus_marine_downloader(mock_sub, tmp_path):
    node = GeoCopernicusMarineNode()
    
    # We will temporarily patch the cache directory inside the node processor's cache logic
    # by letting it write to a unique file. We can pass coordinates and trigger.
    params = {
        'username': 'mock_user',
        'password': 'mock_password',
        'dataset_id': 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m',
        'variable': 'thetao',
        'date_start': '2023-01-01',
        'date_end': '2023-01-03',
        'bbox': '-53.5,4.5,-51.5,6.5',
        'colormap': 0
    }

    # Execute process
    res = node.process({}, params)

    assert res is not None
    assert 'grids' in res
    assert 'preview' in res
    assert 'meta' in res

    grids = res['grids']
    assert isinstance(grids, np.ndarray)
    assert grids.shape == (3, 5, 5)
    assert np.isnan(grids[:, 0, 0]).all()  # NaN land mask check

    meta = res['meta']
    assert meta['variable'] == 'thetao'
    assert meta['dataset_id'] == 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m'
    assert meta['time_len'] == 3

    # Verify mock called with correct params
    mock_sub.assert_called_once_with(
        dataset_id='cmems_mod_glo_phy_anfc_0.083deg_PT1D-m',
        username='mock_user',
        password='mock_password',
        variables=['thetao'],
        minimum_longitude=-53.5,
        maximum_longitude=-51.5,
        minimum_latitude=4.5,
        maximum_latitude=6.5,
        start_datetime='2023-01-01T00:00:00',
        end_datetime='2023-01-03T23:59:59',
        output_filename=mock_sub.call_args[1]['output_filename'],
        force_download=True
    )

    # Cleanup downloaded temp nc file
    output_fn = mock_sub.call_args[1]['output_filename']
    if os.path.exists(output_fn):
        os.remove(output_fn)
