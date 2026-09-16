"""
test_geo_gsw_monthly.py — JRC Global Surface Water MonthlyHistory reference mask.

This node exists to fix an estimand problem: a prediction made from ONE acquisition must
be scored against a reference describing the SAME period. WorldCover is annual and
encodes *permanent* water, so seasonal water correctly detected scores as a false
positive. GSW MonthlyHistory is per calendar month, so it can be matched to the image.

The band semantics are the trap these tests guard: `water` is 0 = NOT OBSERVED,
1 = land, 2 = water. Treating 0 as land silently converts missing observations into
false negatives, so the node must expose a separate validity mask.
"""
import io
import os
import sys
import importlib.util
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Fake `ee` so the plugin imports and runs with no network / credentials ─────


class _FakeEEImage:
    def __init__(self, array):
        self._array = array

    def select(self, *_a, **_k):
        return self

    def clip(self, *_a, **_k):
        return self

    def rename(self, *_a, **_k):
        return self

    def getDownloadURL(self, _params):
        return 'https://fake.invalid/gsw.npy'


class _FakeCollection:
    def __init__(self, array):
        self._array = array
        self.filter_dates = []

    def filterDate(self, start, end):
        self.filter_dates.append((str(start), str(end)))
        return self

    def filterBounds(self, *_a):
        return self

    def first(self):
        return _FakeEEImage(self._array)

    def size(self):
        return types.SimpleNamespace(getInfo=lambda: 1)


def _make_fake_ee(array):
    """Build a minimal fake `ee` module; returns (module, collection stub)."""
    coll = _FakeCollection(array)
    fake = types.ModuleType('ee')
    fake.Initialize = lambda *a, **k: None
    fake.ImageCollection = lambda _id: coll
    fake.Image = lambda x: x if isinstance(x, _FakeEEImage) else _FakeEEImage(array)
    fake.Geometry = types.SimpleNamespace(Rectangle=lambda *a, **k: 'ROI')
    fake.Date = lambda *a, **k: types.SimpleNamespace(
        advance=lambda *_a, **_k: 'DATE', format=lambda *_a: 'DATE')
    return fake, coll


class _FakeResponse:
    def __init__(self, array):
        buf = io.BytesIO()
        np.save(buf, array)
        self.content = buf.getvalue()
        self.status_code = 200
        self.text = ''


def _patch_plugin(array):
    """Point the already-imported plugin at fresh `ee` / `requests` stubs.

    The plugin binds `ee` and `requests` at import time, so replacing
    sys.modules afterwards would have no effect — patch the module attributes.
    """
    fake_ee, coll = _make_fake_ee(array)
    _mod.ee = fake_ee
    _mod.requests = types.SimpleNamespace(get=lambda *a, **k: _FakeResponse(array))
    return coll


_bootstrap_ee, _ = _make_fake_ee(np.zeros((4, 4), np.uint8))
sys.modules['ee'] = _bootstrap_ee

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_gsw_monthly.py'
)
_spec = importlib.util.spec_from_file_location('plugins.geo_gsw_monthly', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.geo_gsw_monthly'] = _mod
_spec.loader.exec_module(_mod)

NODE = lambda: _mod.GswMonthlyNode()          # noqa: E731


def _geo(shape=(8, 8), dates='2021-09-02 → 2021-09-03'):
    return {
        'bands': [np.zeros(shape, np.float32)],
        'transform': (10.0, 0.0, 400000.0, 0.0, -10.0, 5430000.0),
        'crs': 'EPSG:32631',
        '_dates': dates,
    }


# ── band semantics: 0 = not observed, 1 = land, 2 = water ─────────────────────

def test_decode_separates_water_from_unobserved():
    # Arrange: one pixel of each GSW code
    raw = np.array([[0, 1, 2]], dtype=np.uint8)

    # Act
    mask, valid = _mod.GswMonthlyNode._decode(raw)

    # Assert: only code 2 is water; code 0 is NOT land, it is unobserved
    assert mask.tolist() == [[0, 0, 255]]
    assert valid.tolist() == [[0, 255, 255]]


def test_unobserved_is_never_reported_as_land():
    # Arrange: a fully unobserved month
    raw = np.zeros((3, 3), np.uint8)

    # Act
    mask, valid = _mod.GswMonthlyNode._decode(raw)

    # Assert: no water AND no valid observation — the caller can tell the two apart
    assert mask.sum() == 0
    assert valid.sum() == 0


# ── date handling: the reference must follow the imagery ──────────────────────

@pytest.mark.parametrize('dates,expected', [
    ('2021-09-02 → 2021-09-03', (2021, 9)),
    ('2021-09-02 -> 2021-09-03', (2021, 9)),
    ('1998-03-01 → 1998-04-01', (1998, 3)),
    ('2021-12-31', (2021, 12)),
])
def test_parse_year_month_from_imagery_dates(dates, expected):
    assert _mod.GswMonthlyNode._parse_year_month(dates) == expected


@pytest.mark.parametrize('bad', ['', None, 'no dates here', 'static product'])
def test_parse_year_month_returns_none_when_undetectable(bad):
    assert _mod.GswMonthlyNode._parse_year_month(bad) is None


def test_auto_date_uses_the_imagery_month():
    # Arrange: imagery from 2021-09; node params say 1999-01 but auto_date is on
    coll = _patch_plugin(np.full((8, 8), 2, np.uint8))
    node = NODE()

    # Act
    node.process({'geotiff': _geo()},
                 {'auto_date': True, 'year': 1999, 'month': 1, 'gcp_project': ''})

    # Assert: the collection was filtered on the imagery's month, not the params
    assert coll.filter_dates, 'collection was never date-filtered'
    assert coll.filter_dates[-1][0].startswith('2021-09')


def test_manual_date_is_used_when_auto_is_off():
    # Arrange
    coll = _patch_plugin(np.full((8, 8), 2, np.uint8))
    node = NODE()

    # Act
    node.process({'geotiff': _geo()},
                 {'auto_date': False, 'year': 2019, 'month': 4, 'gcp_project': ''})

    # Assert
    assert coll.filter_dates[-1][0].startswith('2019-04')


def test_date_outside_dataset_coverage_is_reported_not_silently_wrong():
    # Arrange: GSW MonthlyHistory stops at 2021-12; 2024 imagery cannot be matched
    _patch_plugin(np.full((8, 8), 2, np.uint8))
    node = NODE()

    # Act
    out = node.process({'geotiff': _geo(dates='2024-01-01 → 2024-06-01')},
                       {'auto_date': True, 'gcp_project': ''})

    # Assert: explicit failure, no fabricated reference
    assert out['mask'] is None
    assert 'coverage' in out['meta'].lower() or '2021' in out['meta']


# ── plumbing ──────────────────────────────────────────────────────────────────

def test_missing_geotiff_is_handled():
    _patch_plugin(np.zeros((4, 4), np.uint8))
    out = NODE().process({'geotiff': None}, {})
    assert out['mask'] is None
    assert out['meta']


def test_mask_is_resampled_to_the_input_grid():
    # Arrange: GSW arrives at 30 m (coarser); the prediction grid is 10 m
    _patch_plugin(np.full((4, 4), 2, np.uint8))
    node = NODE()

    # Act
    out = node.process({'geotiff': _geo(shape=(12, 12))},
                       {'auto_date': True, 'gcp_project': ''})

    # Assert: reference lands exactly on the prediction grid, nearest-neighbour
    assert out['mask'].shape == (12, 12)
    assert out['valid'].shape == (12, 12)
    assert set(np.unique(out['mask'])) <= {0, 255}


def test_meta_reports_water_and_valid_fractions():
    # Arrange: half water, half unobserved → 50 % valid, and water is 100 % of valid
    raw = np.array([[2, 2], [0, 0]], dtype=np.uint8)
    _patch_plugin(raw)

    # Act
    out = NODE().process({'geotiff': _geo(shape=(2, 2))},
                         {'auto_date': True, 'gcp_project': ''})

    # Assert
    assert out['stats']['valid_fraction'] == pytest.approx(0.5)
    assert out['stats']['water_fraction_of_valid'] == pytest.approx(1.0)
    assert out['stats']['year'] == 2021 and out['stats']['month'] == 9


# ── CRS interop: loaders hand back CRS objects, Earth Engine wants a string ────

class _CRSObject:
    """Stand-in for rasterio.CRS: prints as an EPSG code but is not a str."""
    def __init__(self, code='EPSG:32631'):
        self._code = code

    def __str__(self):
        return self._code

    def __repr__(self):
        return f"CRS.from_wkt('PROJCS[...{self._code}...]')"


def test_crs_object_is_coerced_to_a_string(monkeypatch):
    """A rasterio CRS object must not reach Earth Engine unconverted.

    The STAC loader stores `crs` as a rasterio CRS instance. Passing it straight to
    ee.Geometry.Rectangle raises `EEException: Cannot encode object: EPSG:32631`, and the
    reference mask silently comes back as None — the whole validation half of a graph
    loses its ground truth.
    """
    _patch_plugin(np.full((8, 8), 2, np.uint8))
    seen = {}

    def _rect(coords, crs, geodesic):
        seen['crs'] = crs
        return 'ROI'

    monkeypatch.setattr(_mod.ee, 'Geometry',
                        types.SimpleNamespace(Rectangle=_rect))

    geo = _geo()
    geo['crs'] = _CRSObject()
    out = NODE().process({'geotiff': geo}, {'auto_date': True, 'gcp_project': ''})

    assert isinstance(seen.get('crs'), str), \
        f"ee.Geometry.Rectangle received {type(seen.get('crs')).__name__}, not str"
    assert seen['crs'] == 'EPSG:32631'
    assert out['mask'] is not None, 'a CRS object must not break the fetch'
