import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from registry import NODE_SCHEMAS, NODE_CLASS_REGISTRY

# Force plugin registration
import importlib.util
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'df_column_list.py')
_spec = importlib.util.spec_from_file_location('plugins.df_column_list', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ColumnNode = NODE_CLASS_REGISTRY['df_column_list']


def _df():
    return pd.DataFrame({'A': [1.0, 2.0, np.nan], 'Name': ['x', 'y', 'z']})


def test_registration_exposes_list_and_table_outputs():
    schema = next((s for s in NODE_SCHEMAS if s['type'] == 'df_column_list'), None)
    assert schema is not None
    assert [p['id'] for p in schema['outputs']] == ['list', 'table', 'count', 'df_meta']


def test_extracts_column_as_list_and_single_column_frame():
    res = ColumnNode().process({'table': _df()}, {'column': 'Name', 'dropna': True})
    assert res['list'] == ['x', 'y', 'z']
    assert res['count'] == 3.0
    assert list(res['table'].columns) == ['Name']


def test_dropna_removes_missing_values():
    res = ColumnNode().process({'table': _df()}, {'column': 'A', 'dropna': True})
    assert res['list'] == [1.0, 2.0]

    kept = ColumnNode().process({'table': _df()}, {'column': 'A', 'dropna': False})
    assert len(kept['list']) == 3


def test_column_name_is_matched_case_insensitively():
    res = ColumnNode().process({'table': _df()}, {'column': ' name '})
    assert res['list'] == ['x', 'y', 'z']


def test_blank_column_falls_back_to_the_first_one():
    res = ColumnNode().process({'table': _df()}, {'column': ''})
    assert list(res['table'].columns) == ['A']


def test_meta_is_emitted_even_when_the_column_is_unknown():
    """The inspector needs df_meta to render the column-name chips."""
    res = ColumnNode().process({'table': _df()}, {'column': 'nope'})
    assert res['df_meta']['columns'] == ['A', 'Name']
    assert 'list' not in res


def test_numeric_coercion_turns_text_into_nan():
    df = pd.DataFrame({'mixed': ['1', 'oops', '3']})
    res = ColumnNode().process({'table': df}, {'column': 'mixed', 'numeric': True, 'dropna': True})
    assert res['list'] == [1.0, 3.0]
