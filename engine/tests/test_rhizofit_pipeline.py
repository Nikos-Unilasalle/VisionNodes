"""RhizoFit pipeline without the graph engine: same outputs as the Predictive Ellipse Zoning template."""
import json
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(REPO, 'scripts'), os.path.join(REPO, 'engine', 'tests')]

import anchor_choice_lib as AC  # noqa: E402
import rhizofit_pipeline as P  # noqa: E402
import root_web_runner as W  # noqa: E402
import vn_headless as H  # noqa: E402

TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_predictive_ellipse_zoning.vn')
SAMPLE = os.path.join(REPO, 'samples', 'root_photo_b.jpg')
DISPLAY_ONLY = ('color_index', 'node_note')
RACINES = os.path.expanduser(os.environ.get('RHIZOFIT_RACINES', '~/Desktop/racines'))
RM_PIXEL_UM = 500 / 395
# Results of the template run (graph engine) at n_boot=20: anchor search, vessels, total cells, cell files.
RM_EXPECTED = {
    'RM12e': ('stele', 6, 1187, (8, 7, 8)),
    'RM11NB': ('stele', 6, 1186, (7, 6, 9)),
    'RM18NB': ('stele', 6, 982, (8, 7, 8)),
    'RM20NB': ('stele', 6, 1240, (8, 8, 9)),
    'RM23NB': ('stele', 6, 1454, (9, 8, 10)),
    'RM2NB': ('stele', 6, 1195, (8, 7, 8)),
}


def _template():
    with open(TEMPLATE) as f:
        return json.load(f)


def _differences(a, b, path=''):
    """Paths where two node outputs differ (arrays bit for bit, NaN equal to NaN)."""
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a, b = np.asarray(a), np.asarray(b)
        same = a.shape == b.shape and a.dtype == b.dtype and np.array_equal(a, b, equal_nan=a.dtype.kind in 'fc')
        return [] if same else [path]
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return [f'{path} keys']
        return [d for k in a for d in _differences(a[k], b[k], f'{path}.{k}')]
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [f'{path} length']
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _differences(x, y, f'{path}[{i}]')]
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return []
    return [] if a == b else [f'{path}: {a!r} != {b!r}']


def test_parameters_are_the_template_ones():
    vn = _template()
    for node in vn['nodes']:
        if node['id'] in P.PARAMS and node['id'] != 'src':
            params = {k: v for k, v in node['data']['params'].items() if k not in DISPLAY_ONLY}
            assert P.PARAMS[node['id']] == params, node['id']
    pub = next(n for n in vn['nodes'] if n['id'] == 'pub_fig')['data']['params']
    assert P.PUBLICATION_PARAMS == {k: v for k, v in pub.items() if k not in DISPLAY_ONLY}


def test_pipeline_runs_every_node_the_analysis_reads():
    vn = _template()
    edges = H._collapse_reroutes(vn['edges'], {n['id'] for n in vn['nodes'] if n['type'] == 'canvas_reroute'})
    needed, grew = {'src', 'section', 'ridge', 'cells', 'mx_ring', 'metaxylem', 'ellipse_prop'}, True
    while grew:
        upstream = {e['source'] for e in edges if e['target'] in needed} - needed
        needed |= upstream
        grew = bool(upstream)
    assert set(P.PARAMS) == needed
    types = {n['type'] for n in vn['nodes'] if n['id'] in needed} | {'draw_root_publication'}
    assert types == set(P.PLUGINS)
    assert P.SHARED_STEPS + P.SEARCH_STEPS == len(needed)


def test_unknown_search_is_rejected():
    with pytest.raises(ValueError, match='unknown vessel search'):
        P.run(SAMPLE, searches=('stele', 'pith'))


@pytest.fixture(scope='module')
def upload():
    path, _, _ = W._normalised_upload(SAMPLE)
    yield path
    os.remove(path)


def test_every_node_output_matches_the_template_run(upload):
    steps = []
    runs = P.run(upload, on_step=lambda i, n, nid: steps.append((i, n)))
    assert [i for i, _ in steps] == list(range(P.TOTAL_STEPS)) and {n for _, n in steps} == {P.TOTAL_STEPS}
    H.load_plugins()
    vn = _template()
    graph = {'stele': H.run(vn, {'src': {'path': upload}}),
             'whole': H.run(AC.whole_section_template(vn), {'src': {'path': upload}})}
    for search in P.SEARCHES:
        assert set(runs[search]) == set(P.PARAMS)
        diffs = [d for nid, out in runs[search].items() for d in _differences(graph[search][nid], out, nid)]
        assert diffs == [], f'{search}: {diffs[:10]}'


@pytest.mark.parametrize('name', sorted(RM_EXPECTED))
def test_reference_micrographs_give_the_template_results(name):
    image = os.path.join(RACINES, f'{name}.jpg')
    if not os.path.isfile(image):
        pytest.skip(f'reference micrograph not available: {image}')
    search, n_vessels, total, cell_files = RM_EXPECTED[name]
    st = W.run_pipeline(image, RM_PIXEL_UM, n_boot=20)
    census = W._census_territory(st)
    assert sum(c['total'] for c in census.values()) == total
    assert st['anchor']['search'] == search
    assert len(W._metaxylem_vessels(st['mx'])) == n_vessels
    assert tuple(round(v) for v in st['cell_files']) == cell_files
