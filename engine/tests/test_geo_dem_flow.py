"""Regression tests for geo_dem_flow priority-flood depression filling.

The original `_fill_pits` raised pits to the minimum neighbour elevation, which
left flat plateaus where `_d8_fdir` returns -1 (no descent). On low-relief DEMs
this fragmented the drainage network and capped flow accumulation far below true
values, which in turn left `geo_dem_hand` unseeded (HAND = 0 everywhere).

`_priority_flood_eps` (Barnes, Lehman & Mulla 2014) imposes a strictly
descending path from every cell to the DEM border, guaranteeing a connected
drainage network with no interior sinks.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util

import numpy as np

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_dem_flow.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_dem_flow', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_dem_flow'] = _mod
_spec.loader.exec_module(_mod)


def _sloped_dem_with_pit(h: int = 20, w: int = 20) -> np.ndarray:
    """Plane sloping toward row 0, gently converging on the centre column,
    with a dug depression that naive pit-filling would leave flat."""
    yy, xx = np.mgrid[0:h, 0:w]
    dem = (yy * 1.0 + 0.05 * np.abs(xx - w / 2)).astype(np.float32)
    dem[h // 2:h // 2 + 4, w // 2 - 2:w // 2 + 2] -= 8.0
    return dem


def test_priority_flood_removes_interior_sinks():
    dem = _sloped_dem_with_pit()
    filled = _mod._priority_flood_eps(dem)
    fdir = _mod._d8_fdir(filled.astype(np.float64), 1.0, 1.0)

    # Every interior cell must have a defined downstream direction.
    interior_sinks = int((fdir[1:-1, 1:-1] < 0).sum())
    assert interior_sinks == 0


def test_flow_drains_through_depression():
    dem = _sloped_dem_with_pit(20, 20)
    filled = _mod._priority_flood_eps(dem)
    fdir = _mod._d8_fdir(filled.astype(np.float64), 1.0, 1.0)
    acc = _mod._flow_acc(fdir, filled)

    # With full drainage connectivity, the trunk outlet accumulates the whole
    # domain (no fragmentation at the pit).
    assert int(acc.max()) == dem.size


def test_priority_flood_preserves_relief_order():
    """ε-fill must not distort real relief: a clearly sloped DEM keeps its
    monotonic ordering (filled surface stays close to the original)."""
    yy, _ = np.mgrid[0:30, 0:30]
    dem = (yy * 2.0).astype(np.float32)          # strong, sink-free slope
    filled = _mod._priority_flood_eps(dem)
    # No real depressions → fill should barely change anything (within a few ε).
    assert np.allclose(filled, dem, atol=1e-2)


def test_full_node_reports_connected_network():
    dem = _sloped_dem_with_pit(24, 24)
    geo = {
        'bands': dem[np.newaxis],
        'count': 1,
        'crs': 'EPSG:32622',
        'transform': None,          # node falls back to 30 m pixels
        'nodata': None,
    }
    node = _mod.DemFlowNode()
    res = node.process({'geotiff': geo}, {})
    acc = res['flow_acc']['bands'][0]
    # Accumulation should greatly exceed the degenerate per-cell floor of 1.
    assert float(acc.max()) >= dem.size * 0.5
