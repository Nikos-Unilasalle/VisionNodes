import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import importlib.util
import pytest
import shutil
from unittest.mock import patch
from registry import NODE_CLASS_REGISTRY

# Dynamic load of the plugin under test
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_copernicus_marine.py')
_spec = importlib.util.spec_from_file_location('plugins.geo_copernicus_marine', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GeoCopernicusMarineNode = NODE_CLASS_REGISTRY['geo_copernicus_marine']

@pytest.fixture(autouse=True)
def clear_cache():
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'copernicus_marine_cache')
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    yield
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


import time

def run_node_and_wait(node, inputs, params):
    params = params.copy()
    params['fetch'] = 1
    
    # Ensure rising edge detection triggers
    node._prev_fetch = 0
    
    # First call triggers the background thread
    node.process(inputs, params)
    
    # Wait for the thread to complete
    start_t = time.time()
    while node._loading and time.time() - start_t < 10.0:
        time.sleep(0.01)
        
    # Second call gets the cached results
    return node.process(inputs, params)

def mock_subset(dataset_id, username, password, variables, minimum_longitude, maximum_longitude,
                 minimum_latitude, maximum_latitude, start_datetime, end_datetime, output_filename,
                 overwrite=True):
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

    # Execute process using the async runner helper
    res = run_node_and_wait(node, {}, params)

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
        overwrite=True
    )

    # Cleanup downloaded temp nc file
    output_fn = mock_sub.call_args[1]['output_filename']
    if os.path.exists(output_fn):
        os.remove(output_fn)

def mock_subset_advanced(*args, **kwargs):
    import xarray as xr
    import pandas as pd

    times = pd.date_range("2023-01-01", periods=2)
    lats = np.linspace(4.5, 6.5, 4)
    lons = np.linspace(-53.5, -51.5, 4)

    data = np.random.rand(2, 4, 4)
    ds = xr.Dataset(
        {kwargs['variables'][0]: (["time", "latitude", "longitude"], data)},
        coords={
            "time": times,
            "latitude": lats,
            "longitude": lons,
        }
    )
    ds.to_netcdf(kwargs['output_filename'])

@patch('copernicusmarine.subset', side_effect=mock_subset_advanced)
def test_copernicus_marine_downloader_advanced(mock_sub, tmp_path):
    node = GeoCopernicusMarineNode()
    params = {
        'username': 'mock_user',
        'password': 'mock_password',
        'dataset_id': 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m',
        'variable': 'thetao',
        'date_start': '2023-01-01',
        'date_end': '2023-01-02',
        'bbox': '-53.5,4.5,-51.5,6.5',
        'min_depth': 2.5,
        'max_depth': 15.0,
        'service': 3,  # 'opendap'
        'colormap': 0
    }

    res = run_node_and_wait(node, {}, params)
    assert res is not None
    assert res['grids'].shape == (2, 4, 4)

    # Verify mock was called with depth limits and service setting
    called_kwargs = mock_sub.call_args[1]
    assert called_kwargs['minimum_depth'] == 2.5
    assert called_kwargs['maximum_depth'] == 15.0
    assert called_kwargs['service'] == 'opendap'

    output_fn = called_kwargs['output_filename']
    if os.path.exists(output_fn):
        os.remove(output_fn)

@patch('copernicusmarine.subset', side_effect=mock_subset)
def test_copernicus_marine_credentials_storage(mock_sub, tmp_path):
    # Patch the secrets path to a temporary one to avoid messing with the user's home folder
    temp_secrets_file = str(tmp_path / 'secrets.json')
    original_path = _mod._SECRETS_PATH
    _mod._SECRETS_PATH = temp_secrets_file
    try:
        node = GeoCopernicusMarineNode()
        
        # 1. Run with username/password to save it
        params = {
            'username': 'saved_user',
            'password': 'saved_password',
            'dataset_id': 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m',
            'variable': 'thetao',
            'date_start': '2023-01-01',
            'date_end': '2023-01-03',
            'bbox': '-53.5,4.5,-51.5,6.5',
            'colormap': 0
        }
        res = run_node_and_wait(node, {}, params)
        assert res is not None
        
        # Verify it was saved to the temp secrets file
        import json
        with open(temp_secrets_file) as f:
            data = json.load(f)
        assert data.get('copernicus_marine_username') == 'saved_user'
        assert data.get('copernicus_marine_password') == 'saved_password'
        
        # 2. Run with blank username/password to load from saved secrets
        params_blank = {
            'username': '',
            'password': '',
            'dataset_id': 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m',
            'variable': 'thetao',
            'date_start': '2023-01-01',
            'date_end': '2023-01-03',
            'bbox': '-53.5,4.5,-51.5,6.5',
            'colormap': 0
        }
        
        # Reset mock
        mock_sub.reset_mock()
        
        # Clear cache to force a download and check credential usage
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'copernicus_marine_cache')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        
        res_blank = run_node_and_wait(node, {}, params_blank)
        assert res_blank is not None
        
        # Verify the subset was called with the stored credentials
        mock_sub.assert_called_once()
        called_kwargs = mock_sub.call_args[1]
        assert called_kwargs['username'] == 'saved_user'
        assert called_kwargs['password'] == 'saved_password'
    finally:
        _mod._SECRETS_PATH = original_path


