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
    assert [i['id'] for i in res['images']] == ['input', 'section', 'walls', 'cells', 'anchor', 'rho', 'unwrap',
                                                'zones', 'publication']
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
    assert 'images/09_publication.png' in names and 'charts/01_profiles.png' in names
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
    flat = cv2.imread(W._flatten_to_png(str(path)))
    assert flat.shape == (300, 300, 3) and flat.min() == 255


def test_bundle_holds_every_plugin_the_template_needs(tmp_path):
    out = tmp_path / 'engine.zip'
    files = B.build(str(out))
    names = zipfile.ZipFile(out).namelist()
    assert 'scripts/root_web_runner.py' in names and 'engine/tests/vn_headless.py' in names
    assert any(n.endswith('draw_root_publication.py') for n in names)
    assert len(names) == len(files)
