"""test_geo_persistence.py — Tests for geo_persistence (topological persistence node).

Threshold-free water-body extraction by 0-D persistent homology. All synthetic data.
"""
import sys
import os
import importlib.util
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
_PLUGINS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins')


def _load(modname):
    path = os.path.join(_PLUGINS, f'{modname}.py')
    spec = importlib.util.spec_from_file_location(f'plugins.{modname}', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f'plugins.{modname}'] = mod
    spec.loader.exec_module(mod)
    return mod


def _node():
    return _load('geo_persistence').TopologicalPersistenceNode()


def _prob_geo(prob_arr):
    bands = prob_arr[np.newaxis, :, :].astype(np.float32)
    return {'bands': bands, 'count': 1, 'band_names': ['prob'],
            'crs': None, 'transform': None, 'nodata': None, 'dtype': 'float32'}


def _scene(noise=0.04, seed=0):
    """2 strong lakes + 1 weak speckle, on a noisy background."""
    h = w = 120
    yy, xx = np.mgrid[0:h, 0:w]

    def blob(cy, cx, r, amp):
        return amp * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r * r))

    p = np.zeros((h, w), np.float32)
    p += blob(35, 35, 12, 0.95)     # strong lake A
    p += blob(75, 85, 10, 0.88)     # strong lake B
    p += blob(20, 95, 4, 0.55)      # weak speckle
    rng = np.random.default_rng(seed)
    p += rng.normal(0, noise, (h, w)).astype(np.float32)
    return np.clip(p, 0, 1)


# ──────────────────────────────────────────────────────────────────────────────

def test_returns_all_ports():
    out = _node().process({'geotiff': _prob_geo(_scene())},
                          {'band': 1, 'min_persistence': 0.0})
    for key in ('persistence_map', 'colormap', 'mask', 'diagram', 'stats', 'n_significant'):
        assert key in out, f'missing output {key}'
    assert out['persistence_map']['count'] == 1
    assert out['mask'].dtype == np.uint8
    assert set(np.unique(out['mask'])).issubset({0, 255})


def test_none_input_returns_empty():
    out = _node().process({'geotiff': None}, {})
    assert out['persistence_map'] is None and out['mask'] is None


def test_auto_gap_separates_lakes_from_noise():
    """No threshold set: the auto gap should isolate exactly the 3 planted blobs."""
    out = _node().process({'geotiff': _prob_geo(_scene())},
                          {'band': 1, 'min_persistence': 0.0})
    df = out['diagram']
    top3 = df.nlargest(3, 'persistence')['persistence'].to_numpy()
    rest = df['persistence'].to_numpy()
    rest = np.sort(rest)[::-1][3:]
    # The 3 planted features are clearly more persistent than everything else.
    assert top3.min() > 0.3
    assert rest.max() < 0.25
    # Auto cut lands in the gap and selects the significant features.
    assert 0.25 <= out['stats']['persistence_cut'] <= 0.55
    assert out['n_significant'] >= 3


def test_persistence_map_brightest_at_lakes():
    arr = _scene()
    out = _node().process({'geotiff': _prob_geo(arr)}, {'band': 1})
    pmap = out['persistence_map']['bands'][0]
    # Lake A centre (35,35) should carry near-maximal persistence.
    assert pmap[35, 35] > 0.5 * pmap.max()
    # A background corner should carry low persistence.
    assert pmap[5, 5] < 0.25 * pmap.max()


def test_manual_persistence_override():
    out = _node().process({'geotiff': _prob_geo(_scene())},
                          {'band': 1, 'min_persistence': 0.7})
    assert out['stats']['cut_mode'] == 'manual'
    assert out['stats']['persistence_cut'] == 0.7
    # Only the two strong lakes survive a 0.7 cut (speckle ~0.55 dies).
    assert out['n_significant'] == 2


def test_downsample_guard_runs():
    """Large raster triggers the downsample path without error."""
    big = np.tile(_scene(), (4, 4))  # 480x480 = 230400 px
    out = _node().process({'geotiff': _prob_geo(big)},
                          {'band': 1, 'max_pixels': 20000})
    assert out['persistence_map']['bands'][0].shape == big.shape
    assert out['stats']['n_water_bodies'] >= 3


def test_image_input_like_frame_accumulator():
    """The MC probability map arrives as a uint8 image (0-255), not a geotiff."""
    img = (_scene() * 255).clip(0, 255).astype(np.uint8)   # accumulator-style output
    out = _node().process({'geotiff': None, 'image': img}, {'min_persistence': 0.0})
    assert out['mask'] is not None and out['mask'].dtype == np.uint8
    assert out['stats']['n_water_bodies'] >= 3
    # Persistence is recovered on the [0,1] normalized scale.
    assert out['stats']['max_persistence'] > 0.5


def test_image_3channel_input():
    """A 3-channel BGR image is reduced to grayscale before analysis."""
    gray = (_scene() * 255).clip(0, 255).astype(np.uint8)
    bgr = np.stack([gray, gray, gray], axis=-1)
    out = _node().process({'image': bgr}, {})
    assert out['stats']['n_water_bodies'] >= 3


def test_minima_polarity():
    """Inverting polarity finds dark basins instead of bright peaks."""
    arr = 1.0 - _scene()  # lakes become dark wells
    out = _node().process({'geotiff': _prob_geo(arr)},
                          {'band': 1, 'feature': 'minima (dark)'})
    assert out['n_significant'] >= 3
