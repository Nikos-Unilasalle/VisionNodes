"""Choice of the metaxylem anchor between the stele search and the whole-section search."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                'scripts'))

import anchor_choice_lib as A  # noqa: E402


def _ring(count=6, cx=100.0, cy=100.0, radius=50.0, regularity=0.9):
    return {'count': count, 'cx': cx, 'cy': cy, 'radius': radius, 'regularity': regularity}


def test_only_one_search_finds_a_ring():
    assert A.choose(None, _ring())[0] == 'whole'
    assert A.choose(_ring(), None)[0] == 'stele'
    assert A.choose(None, None)[0] is None


def test_same_ring_keeps_the_stele_search_unless_the_other_has_more_vessels():
    assert A.choose(_ring(count=6), _ring(count=6, cx=103, radius=52))[0] == 'stele'
    assert A.choose(_ring(count=6), _ring(count=7, cx=103, radius=52))[0] == 'whole'


def test_different_rings_keep_the_clearly_more_regular_one():
    inner, outer = _ring(regularity=0.70), _ring(radius=120, regularity=0.95)
    assert A.choose(inner, outer)[0] == 'whole'
    assert A.choose(_ring(regularity=0.90), _ring(radius=120, regularity=0.93))[0] == 'stele'


def test_whole_section_template_rewires_the_stele_inputs_and_selects_the_innermost_ring():
    vn = {'nodes': [{'id': 'mx_ring', 'data': {'params': {'min_count': 5}}}],
          'edges': [{'source': 'stele', 'target': 'mx_and'}, {'source': 'stele', 'target': 'cortex'},
                    {'source': 'stele', 'target': 'mx_region'}]}
    out = A.whole_section_template(vn)
    assert [e['source'] for e in out['edges']] == ['section', 'stele', 'section']
    assert out['nodes'][0]['data']['params']['select'] == A.INNERMOST_LARGE
    assert vn['edges'][0]['source'] == 'stele'          # the original template is left untouched


def test_a_ring_left_with_too_few_cleaned_vessels_is_not_plausible():
    pipe = {'mx_ring': {'count': 7, 'center_x': 100, 'center_y': 100, 'radius': 50, 'regularity': 0.95}}
    assert A.ring_of(pipe, A.MIN_VESSELS - 1) is None
    ring = A.ring_of(pipe, A.MIN_VESSELS + 1)
    assert ring['count'] == A.MIN_VESSELS + 1          # judged on the vessels that survive the cleaning
