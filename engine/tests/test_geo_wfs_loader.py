"""
test_geo_wfs_loader.py — Unit tests for the generic WFS loader/rasterizer.

Uses a local GeoJSON cache file (no network) to exercise the rasterization path:
constant burn, numeric-field burn, and categorical value-map burn.
"""
import sys
import os
import json
import importlib.util
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_wfs_loader.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_wfs_loader', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_wfs_loader'] = _mod
_spec.loader.exec_module(_mod)

fiona = pytest.importorskip('fiona')
rasterio = pytest.importorskip('rasterio')


def _ref_geo():
    """10x10 reference grid, EPSG:4326, 1° pixels at origin (0,10)."""
    from rasterio.transform import from_origin
    return {
        'bands': np.zeros((1, 10, 10), dtype=np.float32),
        'crs': 'EPSG:4326',
        'transform': from_origin(0, 10, 1, 1),  # top-left (0,10), 1° pixels
    }


def _write_geojson(path, polys_props):
    """polys_props: list of (bbox(minx,miny,maxx,maxy), props_dict)."""
    feats = []
    for (minx, miny, maxx, maxy), props in polys_props:
        feats.append({
            'type': 'Feature',
            'properties': props,
            'geometry': {'type': 'Polygon', 'coordinates': [[
                [minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]]},
        })
    with open(path, 'w') as f:
        json.dump({'type': 'FeatureCollection',
                   'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}},
                   'features': feats}, f)


def _run(tmp_path, params_extra, polys):
    cache_dir = str(tmp_path)
    type_name = 'test:layer'
    cache_file = _mod.WFSLoaderNode._cache_name(type_name, cache_dir)
    _write_geojson(cache_file, polys)
    node = _mod.WFSLoaderNode()
    params = {'fetch': 0, 'type_name': type_name, 'cache_dir': cache_dir,
              'bbox_filter': False, **params_extra}
    return node.process({'reference': _ref_geo()}, params)


def test_missing_typename_returns_empty(tmp_path):
    node = _mod.WFSLoaderNode()
    res = node.process({'reference': _ref_geo()}, {'fetch': 0, 'type_name': ''})
    assert res == {}


def test_constant_burn(tmp_path):
    # One polygon covering rows 1-3, cols 1-3 (in 0..10 lon, 0..10 lat space)
    res = _run(tmp_path, {'default_value': 1.0},
               [((1, 6, 3, 8), {'k': 'a'})])
    assert res['n_feat'] == 1.0
    burned = res['geotiff']['bands'][0]
    assert burned.max() == 1.0
    assert (burned > 0).sum() > 0


def test_numeric_field_burn(tmp_path):
    res = _run(tmp_path, {'burn_field': 'score'},
               [((1, 6, 3, 8), {'score': 7.0})])
    burned = res['geotiff']['bands'][0]
    assert burned.max() == 7.0


def test_categorical_value_map(tmp_path):
    polys = [
        ((1, 6, 3, 8), {'litho': 'Volcanisme basique'}),   # → 3
        ((5, 1, 7, 3), {'litho': 'Grès et quartzites'}),   # → 1
        ((5, 6, 7, 8), {'litho': 'Inconnu'}),              # → default 0
    ]
    vmap = json.dumps({'Volcanisme basique': 3, 'Grès et quartzites': 1})
    res = _run(tmp_path, {'burn_field': 'litho', 'value_map': vmap, 'default_value': 0.0}, polys)
    burned = res['geotiff']['bands'][0]
    vals = set(np.unique(burned).tolist())
    assert 3.0 in vals and 1.0 in vals
    assert res['n_feat'] == 3.0
