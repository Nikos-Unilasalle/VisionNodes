"""Integration test: run public/templates/root_anatomy_analysis.vn headlessly on the samples.

Guards the generic-node rewrite of the Root Anatomy template against regressions on
bright-field (dark walls on white) and fluorescence (bright walls on black) sections.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vn_headless as H  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_anatomy_analysis.vn')

# (sample, printed scale-bar length µm, expected px/mm, TSA:RXSA range, metaxylem count range)
# Metaxylem counts were checked visually (A: 16 large vessels, B: 7).
CASES = [
    ('root_section_brightfield_a.jpg', 500, 786, (0.17, 0.22), (15, 17)),
    ('root_section_brightfield_b.jpg', 500, 784, (0.19, 0.25), (6, 8)),
    ('root_section.png', 200, 560, (0.19, 0.27), (4, 7)),
]
ROOTSCAN_KEYS = ['RXSA', 'XSCWA', 'TCA', 'CCWA', 'CCA', '%CCA', 'AA', '%A', '#Lac', '#CF', '#CC',
                 'CSic', 'CSmc', 'CSoc', 'LA', 'TSA', 'SCWA', 'XVA', 'TSA:RXSA', 'TSA:TCA']

H.load_plugins()


@pytest.fixture(scope='module')
def template():
    with open(TEMPLATE) as fh:
        return json.load(fh)


def test_template_uses_no_root_domain_nodes(template):
    types = {n['type'] for n in template['nodes']}
    assert not any(t.startswith('root_') for t in types)


def test_every_edge_targets_an_existing_node(template):
    ids = {n['id'] for n in template['nodes']}
    for e in template['edges']:
        assert e['source'] in ids and e['target'] in ids


@pytest.mark.parametrize('sample,bar_um,px_mm,ratio_range,mx_range', CASES)
def test_template_segments_sample(template, sample, bar_um, px_mm, ratio_range, mx_range):
    path = os.path.join(REPO, 'samples', sample)
    if not os.path.exists(path):
        pytest.skip(f'missing sample {sample}')

    results = H.run(template, {'src': {'path': path}, 'scale': {'bar_length': bar_um}})
    report = results['report']['report']

    assert all(k in report for k in ROOTSCAN_KEYS), set(ROOTSCAN_KEYS) - set(report)
    assert report['px_per_mm'] == pytest.approx(px_mm, rel=0.01)
    lo, hi = ratio_range
    assert lo <= report['TSA:RXSA'] <= hi
    assert mx_range[0] <= report['#MX'] <= mx_range[1]
    assert report['RXSA'] == pytest.approx(report['TSA'] + report['TCA'], rel=1e-3)
    assert report['CCA'] == pytest.approx(report['TCA'] - report['AA'], rel=1e-3)
    assert report['#CC'] > 300
    assert results['display'] is not None


def test_nodes_keep_canonical_label(template):
    """Nodes are never renamed: data.label = schema label, custom names live in userLabel."""
    for n in template['nodes']:
        sch = H.schema(n['type'])
        if sch is None or n['type'].startswith('canvas_'):
            continue
        assert n['data']['label'] == sch['label'], n['id']
