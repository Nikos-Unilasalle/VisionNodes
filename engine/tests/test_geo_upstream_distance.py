"""
test_geo_upstream_distance.py — Unit tests for the hydrological upstream distance node.
"""
import sys
import os
import importlib.util
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_upstream_distance.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_upstream_distance', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_upstream_distance'] = _mod
_spec.loader.exec_module(_mod)


def _vertical_river(h=20, w=11, col=5, rows=19):
    """D8 field with a single south-flowing river column (direction 4 = South)."""
    fdir = np.full((h, w), -1, dtype=np.float32)
    fdir[0:rows, col] = 4
    return fdir


def test_missing_inputs_returns_none():
    node = _mod.UpstreamDistanceNode()
    res = node.process({}, {})
    assert res['search_zone'] is None
    assert res['distance'] is None


def test_upstream_only_not_downstream():
    """Distance accumulates upstream; the cell below the seed must stay unreached."""
    fdir = _vertical_river()
    seed = np.zeros((20, 11), dtype=np.uint8)
    seed[18, 5] = 255

    node = _mod.UpstreamDistanceNode()
    res = node.process(
        {'flow_dir': {'bands': fdir[np.newaxis]}, 'seed': seed},
        {'max_distance_km': 1.0, 'channel_min_acc': 0, 'pixel_size_m': 30.0},
    )
    dist = res['distance']['bands'][0]

    assert dist[18, 5] == 0.0           # seed itself
    assert dist[17, 5] == 30.0          # one cell upstream
    assert dist[16, 5] == 60.0          # two cells upstream
    assert dist[19, 5] == -1.0          # downstream → unreachable


def test_distance_cap_excludes_far_cells():
    """Cells beyond max reach are not included."""
    fdir = _vertical_river()
    seed = np.zeros((20, 11), dtype=np.uint8)
    seed[18, 5] = 255

    node = _mod.UpstreamDistanceNode()
    res = node.process(
        {'flow_dir': {'bands': fdir[np.newaxis]}, 'seed': seed},
        {'max_distance_km': 0.09, 'channel_min_acc': 0, 'pixel_size_m': 30.0},
    )
    dist = res['distance']['bands'][0]

    # cap = 90m → rows 17(30) 16(60) 15(90) reachable, row 14(120) not
    assert dist[15, 5] == 90.0
    assert dist[14, 5] == -1.0


def test_diagonal_step_length():
    """Diagonal moves cost pixel_size * sqrt(2)."""
    fdir = np.full((10, 10), -1, dtype=np.float32)
    for i in range(9):
        fdir[i, i] = 3  # SE
    seed = np.zeros((10, 10), dtype=np.uint8)
    seed[8, 8] = 255

    node = _mod.UpstreamDistanceNode()
    res = node.process(
        {'flow_dir': {'bands': fdir[np.newaxis]}, 'seed': seed},
        {'max_distance_km': 1.0, 'channel_min_acc': 0, 'pixel_size_m': 30.0},
    )
    dist = res['distance']['bands'][0]

    expected = 30.0 * np.sqrt(2.0)
    assert abs(dist[7, 7] - expected) < 1e-3
    assert abs(dist[6, 6] - 2 * expected) < 1e-3


def test_channel_constraint_filters_search_zone():
    """With a flow_acc channel threshold, off-channel upstream cells are excluded."""
    fdir = _vertical_river()
    seed = np.zeros((20, 11), dtype=np.uint8)
    seed[18, 5] = 255

    # Only the upper half of the river column qualifies as a channel
    acc = np.zeros((20, 11), dtype=np.float32)
    acc[0:10, 5] = 1000.0

    node = _mod.UpstreamDistanceNode()
    res = node.process(
        {'flow_dir': {'bands': fdir[np.newaxis]}, 'seed': seed, 'flow_acc': {'bands': acc[np.newaxis]}},
        {'max_distance_km': 5.0, 'channel_min_acc': 500, 'pixel_size_m': 30.0},
    )
    zone = res['search_zone']

    assert zone[5, 5] == 255    # upstream AND channel
    assert zone[15, 5] == 0     # upstream but below channel threshold
    assert res['stats']['seed_sites'] == 1
