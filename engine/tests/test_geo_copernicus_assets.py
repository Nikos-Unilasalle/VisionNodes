"""
test_geo_copernicus_assets.py — STAC asset selection must honour the Bands parameter.

Regression guard for a silent data loss: the STAC backend carried a hardcoded
`asset_keys` list and ignored the user's `bands` parameter entirely. Requesting
"B04,B03,B02,B08,B11,B12" returned five bands (B12 dropped) with no warning, and the
failure only surfaced far downstream as `name 'B6' is not defined` inside a spectral-index
expression — a message that points at the wrong node.

Delivering fewer bands than requested must be impossible-or-loud, never silent.
"""
import os
import sys
import importlib.util

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'geo_copernicus.py'
)
_spec = importlib.util.spec_from_file_location('_isolated_geo_copernicus', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_resolve = _mod.GeoCopernicusNode._resolve_stac_assets
S2 = _mod.COLLECTIONS['Sentinel-2 L2A (Planetary)']


# ── the actual regression ─────────────────────────────────────────────────────

def test_requested_bands_are_honoured_including_swir2():
    # Arrange: the exact request from the Monte-Carlo water graph
    requested = 'B04,B03,B02,B08,B11,B12'

    # Act
    keys, missing = _resolve(S2, requested)

    # Assert: all six come back, in the requested order — B12 is not dropped
    assert keys == ['B04', 'B03', 'B02', 'B08', 'B11', 'B12']
    assert missing == []


def test_requested_order_is_preserved():
    # Band order is positional downstream (B1..Bn in expressions), so it is load-bearing
    keys, _ = _resolve(S2, 'B12,B02,B08')
    assert keys == ['B12', 'B02', 'B08']


def test_default_asset_keys_include_swir2():
    # Arrange / Act: no explicit request → collection default
    keys, missing = _resolve(S2, '')

    # Assert: the default must cover both SWIR bands, otherwise AWEIsh/MBWI cannot run
    assert 'B11' in keys and 'B12' in keys
    assert missing == []


# ── unavailable bands must be reported, never silently dropped ────────────────

def test_unavailable_band_is_reported():
    # Arrange: B99 does not exist in this collection
    keys, missing = _resolve(S2, 'B04,B99,B08')

    # Assert: the caller learns exactly what it will not receive
    assert keys == ['B04', 'B08']
    assert missing == ['B99']


def test_all_bands_unavailable_falls_back_to_defaults_and_reports():
    keys, missing = _resolve(S2, 'XX,YY')
    assert keys, 'must not return an empty band list'
    assert missing == ['XX', 'YY']


@pytest.mark.parametrize('raw,expected', [
    ('B04, B03 , B02', ['B04', 'B03', 'B02']),      # whitespace
    ('b04,b03', ['B04', 'B03']),                     # case-insensitive
    ('B04,B04,B03', ['B04', 'B03']),                 # duplicates collapse
    ('  ', None),                                    # blank → defaults
    (None, None),                                    # missing → defaults
])
def test_bands_string_parsing(raw, expected):
    keys, missing = _resolve(S2, raw)
    if expected is None:
        assert keys == S2['asset_keys']
    else:
        assert keys == expected
    assert missing == []


# ── SAR is selected by polarization, not by the Bands string ──────────────────

def test_sar_collection_is_unaffected():
    sar = _mod.COLLECTIONS['Sentinel-1 RTC (Planetary)']
    keys, missing = _resolve(sar, 'B04,B03')
    # None of the optical names exist for SAR → fall back to the collection's own assets
    assert keys == sar['asset_keys']
    assert missing == ['B04', 'B03']


# ── the downstream half: the error must point at the real cause ───────────────

def test_spectral_index_error_names_the_available_bands(monkeypatch):
    """A truncated stack must produce a message that identifies the missing band.

    The original failure read `custom2 expression error: name 'B6' is not defined`,
    which names neither the node at fault (the fetch) nor the fact that only five
    bands arrived. The message must carry the band count and the available names.
    """
    import numpy as np
    # Load under a private module name and do NOT leave it in sys.modules: other tests
    # import this plugin too, and a leaked module object with a stubbed
    # send_notification silently swallows their notifications.
    spec = importlib.util.spec_from_file_location(
        '_isolated_geo_spectral_indices',
        os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     'plugins', 'geo_spectral_indices.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    captured = []
    monkeypatch.setattr(mod, 'send_notification',
                        lambda msg, **kw: captured.append(msg))

    geo = {'bands': np.ones((5, 4, 4), np.float32), 'count': 5,
           'transform': (10, 0, 0, 0, -10, 0), 'crs': 'EPSG:32631'}
    mod.SpectralIndicesNode().process({'geotiff': geo}, {
        'ndvi': False, 'ndwi': True, 'mndwi': True,
        'expr1_enable': True, 'expr1_label': 'AWEIsh',
        'expr1': 'BLUE + 2.5*GREEN - 1.5*(NIR + SWIR) - 0.25*B6',
        'nir_band': 4, 'red_band': 1, 'green_band': 2, 'blue_band': 3, 'swir_band': 5,
    })

    assert captured, 'no notification was emitted'
    msg = ' '.join(captured)
    assert 'B6' in msg
    assert '5' in msg, f'message must state how many bands arrived: {msg}'
    assert 'B5' in msg or 'available' in msg.lower(), f'must list what exists: {msg}'


# ── cache correctness: the key must follow the requested bands ────────────────

def _sig(assets):
    return _mod.GeoCopernicusNode._stac_cache_sig(
        'Sentinel-2 L2A (Planetary)', [1.87, 48.88, 2.20, 49.02],
        '2021-09-02', '2021-09-03', 10, '', '', 'median', False, 8, assets, S2)


def test_cache_key_changes_with_the_requested_bands():
    """Editing Bands must invalidate the cache.

    The signature used to hash the collection's DEFAULT asset list, so changing the
    Bands field produced the same cache path and served a stale raster with the wrong
    band count — the same silent truncation, one layer down.
    """
    five = ['B04', 'B03', 'B02', 'B08', 'B11']
    six = ['B04', 'B03', 'B02', 'B08', 'B11', 'B12']
    assert _sig(five) != _sig(six)


def test_cache_key_is_stable_for_the_same_request():
    six = ['B04', 'B03', 'B02', 'B08', 'B11', 'B12']
    assert _sig(six) == _sig(list(six))


def test_cache_key_tracks_band_order():
    # Order is positional downstream, so a reordered request is a different product
    assert _sig(['B04', 'B03']) != _sig(['B03', 'B04'])


def test_resolved_bands_flow_into_the_cache_key():
    # End-to-end of the two helpers: the resolver's output is what keys the cache
    keys_a, _ = _resolve(S2, 'B04,B03,B02,B08,B11')
    keys_b, _ = _resolve(S2, 'B04,B03,B02,B08,B11,B12')
    assert _sig(keys_a) != _sig(keys_b)


# ── a logging call must never abort the work it is describing ─────────────────

def test_log_survives_a_broken_stderr(monkeypatch):
    """`[Errno 32] Broken pipe` while logging must not kill the fetch.

    The STAC path logs progress to stderr with flush=True. When the engine is launched
    from a GUI, that stderr can be a pipe whose reader goes away; the write then raises
    BrokenPipeError, which `_do_fetch` catches as 'unexpected crash' and the whole
    download is lost — because of a log line.
    """
    class _DeadStderr:
        def write(self, *_a):
            raise BrokenPipeError(32, 'Broken pipe')

        def flush(self):
            raise BrokenPipeError(32, 'Broken pipe')

    monkeypatch.setattr(_mod.sys, 'stderr', _DeadStderr())
    _mod._stderr_log('[STAC]', 'progress message')      # must not raise


def test_log_writes_when_stderr_is_healthy(capsys):
    _mod._stderr_log('[STAC]', 'hello')
    assert 'hello' in capsys.readouterr().err


# ── an unexpected crash must be diagnosable ───────────────────────────────────

def test_crash_notification_carries_the_location(monkeypatch):
    """Reporting only the exception message makes the failure unactionable.

    `Copernicus: unexpected crash: [Errno 32] Broken pipe` names neither the file nor
    the line, so there is nothing to act on. The notification must carry the origin.
    """
    node = _mod.GeoCopernicusNode()
    captured = []
    monkeypatch.setattr(_mod, 'send_notification',
                        lambda msg, **kw: captured.append(msg))

    def _boom(*_a, **_k):
        raise BrokenPipeError(32, 'Broken pipe')

    monkeypatch.setattr(node, '_do_fetch_impl', _boom)
    node._do_fetch({}, auto=False, my_gen=node._generation)

    assert captured, 'no crash notification emitted'
    msg = captured[-1]
    assert 'Broken pipe' in msg
    assert 'BrokenPipeError' in msg, f'exception type must be named: {msg}'
    assert '_boom' in msg or 'line' in msg.lower(), f'origin must be named: {msg}'


# ── band post-processing: dB is a SAR operation, not a universal one ──────────

_post = lambda *a, **k: _mod.GeoCopernicusNode._postprocess_band(*a, **k)   # noqa: E731
SAR = _mod.COLLECTIONS['Sentinel-1 RTC (Planetary)']


def test_optical_bands_are_not_log_transformed():
    """`stac_to_db` is labelled "SAR → dB" but used to apply to every collection.

    Sentinel-2 reflectance came back as 10*log10(DN): every spectral index was then
    computed on log-transformed data, the reflectance-unit gate caps were meaningless
    against a 20-42 dB range, and an additive noise sigma specified in reflectance units
    perturbed the signal by ~0.02 % — so a Monte-Carlo ensemble injected essentially no
    noise at all.
    """
    dn = np.array([[2897.0, 110.0]], dtype='float32')     # land NIR, water NIR
    out = _post(dn.copy(), S2, to_db=True, is_cat=False)

    # reflectance, not decibels
    assert np.allclose(out, [[0.2897, 0.0110]], atol=1e-4), out


def test_optical_bands_are_scaled_to_reflectance():
    dn = np.array([[10000.0]], dtype='float32')
    out = _post(dn.copy(), S2, to_db=False, is_cat=False)
    assert np.isclose(out[0, 0], 1.0), 'DN 10000 must map to reflectance 1.0'


def test_sar_bands_still_get_db_when_requested():
    lin = np.array([[100.0]], dtype='float32')
    out = _post(lin.copy(), SAR, to_db=True, is_cat=False)
    assert np.isclose(out[0, 0], 20.0), '10*log10(100) = 20 dB'


def test_sar_bands_stay_linear_when_db_is_off():
    lin = np.array([[100.0]], dtype='float32')
    out = _post(lin.copy(), SAR, to_db=False, is_cat=False)
    assert np.isclose(out[0, 0], 100.0)


def test_zeros_become_nodata_for_continuous_bands():
    a = np.array([[0.0, 5000.0]], dtype='float32')
    out = _post(a.copy(), S2, to_db=False, is_cat=False)
    assert np.isnan(out[0, 0]) and not np.isnan(out[0, 1])


def test_categorical_bands_are_left_alone():
    a = np.array([[0, 80]], dtype='float32')
    lulc = _mod.COLLECTIONS['ESA WorldCover (Planetary)'] \
        if 'ESA WorldCover (Planetary)' in _mod.COLLECTIONS else S2
    out = _post(a.copy(), lulc, to_db=True, is_cat=True)
    assert out.dtype == np.uint8
    assert out.tolist() == [[0, 80]], 'class codes must survive untouched'


def test_reflectance_round_trip_is_physically_plausible():
    # p50 values actually observed on the Seine scene, as raw DN
    dn = np.array([[650.1, 712.9, 484.2, 2897.3, 1940.9, 1270.6]], dtype='float32')
    out = _post(dn.copy(), S2, to_db=True, is_cat=False)
    assert out.min() > 0.0 and out.max() < 1.0, f'reflectance out of range: {out}'


def test_cache_key_tracks_the_effective_band_transform():
    """Changing how bands are post-processed must invalidate the cache.

    The signature recorded the raw `to_db` request, not the transform actually applied.
    When dB stopped being applied to optical collections the key did not move, so a
    cache hit kept serving log-transformed reflectance and the fix appeared to do
    nothing.
    """
    sig = _mod.GeoCopernicusNode._stac_cache_sig
    args = ('Sentinel-2 L2A (Planetary)', [1.87, 48.88, 2.20, 49.02],
            '2021-09-02', '2021-09-03', 10, '', '', 'median')
    assets = ['B04', 'B08']
    optical = sig(*args, to_db=True, max_scenes=8, assets=assets, col_cfg=S2)
    sar_like = sig(*args, to_db=True, max_scenes=8, assets=assets, col_cfg=SAR)
    assert optical != sar_like, 'a dB-transformed product must not share a key'


def test_cache_key_tracks_the_value_scale():
    sig = _mod.GeoCopernicusNode._stac_cache_sig
    args = ('c', [0, 0, 1, 1], 'a', 'b', 10, '', '', 'median')
    unscaled = dict(S2); unscaled.pop('value_scale', None)
    assert sig(*args, to_db=False, max_scenes=8, assets=['B04'], col_cfg=S2) != \
           sig(*args, to_db=False, max_scenes=8, assets=['B04'], col_cfg=unscaled)
