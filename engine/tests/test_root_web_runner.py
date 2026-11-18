"""RhizoFit web app: analysis runner and Pyodide bundle."""
import io
import json
import os
import sys
import zipfile

import cv2
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import build_root_webapp as B  # noqa: E402
import root_web_runner as W  # noqa: E402

SAMPLE = os.path.join(REPO, 'samples', 'root_photo_b.jpg')


@pytest.fixture(scope='module')
def result():
    stages = []
    res = W.analyze(SAMPLE, pixel_size_um=0.5, n_boot=10, progress=lambda s, f: stages.append(s))
    return res, stages


def test_analysis_returns_every_panel(result):
    res, stages = result
    assert [i['id'] for i in res['images']] == ['input', 'section', 'walls', 'cells', 'recovered', 'anchor', 'rho',
                                                'unwrap', 'zones', 'publication']
    assert [c['id'] for c in res['charts']] == ['profiles', 'counts', 'areas', 'composition']
    assert all(item['png'].startswith(b'\x89PNG') for item in res['images'] + res['charts'])
    assert [t['id'] for t in res['tables']] == ['summary', 'boundaries', 'census', 'metaxylem', 'geometry']
    assert stages[0] == W.STAGES[0] and stages[-1] == W.STAGES[-1]


def test_tables_are_rectangular_and_json_serialisable(result):
    res, _ = result
    for t in res['tables']:
        assert all(len(r) == len(t['columns']) for r in t['rows']), t['id']
    json.dumps(res['tables'])


def test_census_totals_match_the_summary(result):
    res, _ = result
    census = next(t for t in res['tables'] if t['id'] == 'census')
    total = census['rows'][-1]
    assert total[0] == 'Total'
    assert total[1] == res['summary']['cells_observed'] == sum(r[1] for r in census['rows'][:-1])
    assert total[3] == res['summary']['cells_estimated']
    assert 'µm²' in census['columns'][4]


def test_boundaries_are_ordered(result):
    b = result[0]['summary']['boundaries']
    assert b['pith'] < 1.0 < b['endo_inner'] < b['endo_outer'] < b['cortex_transition'] < b['edge']


def test_bundle_zip_contains_images_charts_and_tables(result):
    names = zipfile.ZipFile(io.BytesIO(W.bundle_zip(result[0]))).namelist()
    assert 'images/10_publication.png' in names and 'charts/01_profiles.png' in names
    assert 'tables/census.csv' in names and 'tables/metrics.json' in names


def test_unreadable_file_gives_a_user_message(tmp_path):
    bad = tmp_path / 'bad.png'
    bad.write_bytes(b'not an image')
    with pytest.raises(W.AnalysisError, match='could not be read'):
        W.analyze(str(bad))


def test_image_without_a_root_gives_a_user_message(tmp_path):
    blank = tmp_path / 'blank.png'
    cv2.imwrite(str(blank), np.full((400, 400, 3), 255, np.uint8))
    with pytest.raises(W.AnalysisError):
        W.analyze(str(blank), n_boot=0)


def test_invalid_pixel_size_is_rejected():
    with pytest.raises(W.AnalysisError, match='pixel size'):
        W.analyze(SAMPLE, pixel_size_um=-1)


def test_transparent_png_is_flattened_on_white(tmp_path):
    rgba = np.zeros((300, 300, 4), np.uint8)
    path = tmp_path / 'alpha.png'
    cv2.imwrite(str(path), rgba)
    flat = W._read_bgr(str(path))
    assert flat.shape == (300, 300, 3) and flat.min() == 255


@pytest.mark.parametrize('factor', [0.5, 2.0])
def test_root_diameter_is_proportional_to_resolution(factor):
    img = cv2.imread(SAMPLE)
    d1 = W.root_diameter_px(img)
    d2 = W.root_diameter_px(cv2.resize(img, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA))
    assert d2 / d1 == pytest.approx(factor, rel=0.03)


def test_bundle_holds_every_plugin_the_pipeline_needs(tmp_path):
    out = tmp_path / 'engine.zip'
    files = B.build(str(out))
    names = zipfile.ZipFile(out).namelist()
    assert 'scripts/root_web_runner.py' in names and 'scripts/rhizofit_pipeline.py' in names
    assert 'engine/registry.py' in names and not any(n.endswith('.vn') or 'vn_headless' in n for n in names)
    assert any(n.endswith('draw_root_publication.py') for n in names)
    assert len(names) == len(files)


def _summary_row(res, name):
    rows = next(t for t in res['tables'] if t['id'] == 'summary')['rows']
    return next(r for r in rows if r[0] == name)


def test_walled_lacuna_detection_is_on_by_default(result):
    res, _ = result
    row = _summary_row(res, 'Walled lacunae')
    assert row[1] is not None and 'backdrop' in row[3]


def test_walled_lacuna_detection_runs_when_enabled(monkeypatch):
    calls = []

    def spy(labels, gray, zone, rho, expected, px_per_rho, background):
        assert background is not None
        calls.append(1)
        return np.asarray(labels).astype(np.int32), 0, np.zeros(np.asarray(labels).shape, bool)

    monkeypatch.setattr(W.CR, 'remove_walled_lacunae', spy)
    res = W.analyze(SAMPLE, pixel_size_um=0.5, n_boot=0, walled_lacunae=True)
    assert calls == [1]
    assert _summary_row(res, 'Walled lacunae')[1] == 0


def test_vessel_floor_is_the_ring_search_floor():
    import radial_zoning_lib as R
    assert W.vessel_floor({'mx_floor': {'result': 221.0}}) == 221.0
    assert W.vessel_floor({'mx_floor': {'result': 900.0}}) == 900.0
    assert W.vessel_floor({}) == R.MIN_VESSEL_AREA


def _pale_cortex_root(size=1200, r_root=480, r_stele=150):
    """Large pale-walled cortex on a bright slide around a small dark stele (thin-walled sections)."""
    img = np.full((size, size), 232, np.uint8)
    c = size // 2
    yy, xx = np.indices(img.shape)
    rr = np.hypot(yy - c, xx - c)
    cortex = rr < r_root
    walls = cortex & (((xx // 55) * 55 == xx) | ((yy // 55) * 55 == yy) | (np.abs(rr - r_root) < 3))
    img[cortex] = 222
    img[walls] = 120
    img[rr < r_stele] = 90
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_root_diameter_spans_a_pale_cortex_not_only_the_dark_stele():
    img = _pale_cortex_root()
    d = W.root_diameter_px(img)
    assert abs(d - 960) / 960 < 0.15


def test_anchor_offset_is_zero_for_a_centred_ring_and_large_for_an_eccentric_one():
    sec = np.zeros((400, 400), bool)
    cv2.circle(sec.view(np.uint8), (200, 200), 150, 1, -1)
    assert W.anchor_offset(sec, (200.0, 200.0, 50.0, 50.0, 0.0)) < 0.01
    assert W.anchor_offset(sec, (200.0, 90.0, 40.0, 40.0, 0.0)) > W.MAX_ANCHOR_OFFSET


def test_central_vessel_is_the_largest_candidate_inside_the_stele():
    cand = np.zeros((200, 200), np.uint8)
    cv2.circle(cand, (100, 100), 15, 255, -1)    # central vessel, inside the stele
    cv2.circle(cand, (170, 170), 22, 255, -1)    # larger cortex cell, outside it
    stele = np.zeros((200, 200), bool)
    cv2.circle(stele.view(np.uint8), (100, 100), 40, 1, -1)
    mx = W.central_vessel(cand, stele, lumen_area=20.0)
    assert mx[100, 100] and not mx[170, 170]


def test_no_central_vessel_when_the_stele_holds_only_small_lumens():
    cand = np.zeros((200, 200), np.uint8)
    cv2.circle(cand, (100, 100), 3, 255, -1)
    stele = np.zeros((200, 200), bool)
    cv2.circle(stele.view(np.uint8), (100, 100), 40, 1, -1)
    assert W.central_vessel(cand, stele, lumen_area=20.0) is None


def test_rhizodermis_by_outline_is_perimeter_over_layer_thickness():
    sec = np.zeros((400, 400), np.uint8)
    cv2.circle(sec, (200, 200), 150, 1, -1)
    assert W.rhizodermis_by_outline(sec, 10.0) == pytest.approx(2 * np.pi * 150 / 10, rel=0.05)


def test_no_central_vessel_when_the_stele_holds_a_ring_of_similar_vessels():
    cand = np.zeros((200, 200), np.uint8)
    for k in range(6):
        th = k * np.pi / 3
        cv2.circle(cand, (int(100 + 25 * np.cos(th)), int(100 + 25 * np.sin(th))), 8, 255, -1)
    stele = np.zeros((200, 200), bool)
    cv2.circle(stele.view(np.uint8), (100, 100), 45, 1, -1)
    assert W.central_vessel(cand, stele, lumen_area=10.0) is None
