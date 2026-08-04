import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from registry import NODE_SCHEMAS, NODE_CLASS_REGISTRY

# Force plugin registration
import importlib.util
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'df_slice.py')
_spec = importlib.util.spec_from_file_location('plugins.df_slice', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DfSliceNode = NODE_CLASS_REGISTRY['df_slice']


def _df(n=100):
    return pd.DataFrame({'A': range(n), 'B': [f'r{i}' for i in range(n)]})


def test_registration_exposes_slice_ports():
    schema = next((s for s in NODE_SCHEMAS if s['type'] == 'df_slice'), None)
    assert schema is not None
    assert schema['label'] == 'DF Slice'
    assert [p['id'] for p in schema['inputs']] == ['table', 'start', 'end', 'img_size']
    assert [p['id'] for p in schema['outputs']] == ['table', 'preview', 'row_count', 'df_meta', 'img_size']


def test_keeps_inclusive_row_range():
    res = DfSliceNode().process({'table': _df()}, {'start': 10, 'end': 200})
    out = res['table']
    assert list(out['A']) == list(range(10, 100))  # end clamped to the last row

    res = DfSliceNode().process({'table': _df()}, {'start': 10, 'end': 20})
    assert list(res['table']['A']) == list(range(10, 21))
    assert res['row_count'] == 11.0


def test_negative_positions_count_from_the_end():
    res = DfSliceNode().process({'table': _df()}, {'start': -5, 'end': -1})
    assert list(res['table']['A']) == [95, 96, 97, 98, 99]


def test_step_keeps_every_nth_row():
    res = DfSliceNode().process({'table': _df(10)}, {'start': 0, 'end': -1, 'step': 3})
    assert list(res['table']['A']) == [0, 3, 6, 9]


def test_wired_scalars_override_params():
    res = DfSliceNode().process({'table': _df(), 'start': 3.0, 'end': 5.0},
                                {'start': 50, 'end': 60})
    assert list(res['table']['A']) == [3, 4, 5]


def test_inverted_range_returns_empty_frame():
    res = DfSliceNode().process({'table': _df()}, {'start': 80, 'end': 20})
    assert len(res['table']) == 0
    assert res['row_count'] == 0.0


def test_reset_index_renumbers_from_zero():
    res = DfSliceNode().process({'table': _df()}, {'start': 40, 'end': 42, 'reset_index': True})
    assert list(res['table'].index) == [0, 1, 2]


def test_missing_table_is_a_noop():
    assert DfSliceNode().process({}, {'start': 0, 'end': 10}) == {}
