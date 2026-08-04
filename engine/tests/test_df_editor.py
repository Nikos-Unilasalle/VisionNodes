import sys
import os
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from registry import NODE_SCHEMAS, NODE_CLASS_REGISTRY

# Force plugin registration
import importlib.util
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'df_editor.py')
_spec = importlib.util.spec_from_file_location('plugins.df_editor', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DataFrameEditorNode = NODE_CLASS_REGISTRY['df_editor']

def test_df_editor_registration():
    schema = next((s for s in NODE_SCHEMAS if s['type'] == 'df_editor'), None)
    assert schema is not None
    assert schema['label'] == 'DF Editor'
    assert len(schema['inputs']) == 1
    assert len(schema['outputs']) == 3

def test_df_editor_no_edits():
    df = pd.DataFrame({
        'A': [1, 2, 3],
        'B': ['a', 'b', 'c']
    })
    node = DataFrameEditorNode()
    res = node.process({'table': df}, {'edits': '[]'})
    
    assert res is not None
    assert 'table' in res
    assert 'df_meta' in res
    assert 'preview' in res
    
    # Value is a copy, content should be identical
    pd.testing.assert_frame_equal(res['table'], df)
    
    meta = res['df_meta']
    assert meta['shape'] == [3, 2]
    assert meta['columns'] == ['A', 'B']
    assert meta['truncated'] is False

    rows = json.loads(meta['table_json'])['rows']
    assert len(rows) == 3
    assert rows[0]['A'] == 1
    assert rows[0]['B'] == 'a'
    assert rows[0]['__row_index__'] == 0


def test_df_editor_meta_survives_the_engine_payload_filter():
    """Large frames must still reach the UI: the engine drops any node output
    holding a >2000-item list or a >64-key dict, so rows travel JSON-encoded."""
    from engine import _is_serializable

    wide_long = pd.DataFrame({f'c{i}': np.arange(5000) for i in range(80)})
    res = DataFrameEditorNode().process({'table': wide_long}, {'edits': '[]'})
    meta = res['df_meta']

    assert _is_serializable(meta)
    assert meta['shape'] == [5000, 80]
    assert meta['truncated'] is True
    assert len(json.loads(meta['table_json'])['rows']) == 500  # default window


def test_df_editor_row_window_follows_offset():
    df = pd.DataFrame({'A': range(1000)})
    res = DataFrameEditorNode().process({'table': df},
                                        {'edits': '[]', 'row_offset': 900, 'max_rows': 50})
    meta = res['df_meta']
    rows = json.loads(meta['table_json'])['rows']

    assert meta['offset'] == 900
    assert len(rows) == 50
    assert rows[0]['__row_index__'] == 900
    assert rows[-1]['__row_index__'] == 949

def test_df_editor_apply_edits():
    df = pd.DataFrame({
        'A': [1, 2, 3],
        'B': ['a', 'b', 'c']
    })
    node = DataFrameEditorNode()
    
    # Modify A at index 1 to 20, B at index 2 to 'z'
    edits = [
        {'index': 1, 'col': 'A', 'val': '20'},
        {'index': 2, 'col': 'B', 'val': 'z'}
    ]
    edits_str = json.dumps(edits)
    
    res = node.process({'table': df}, {'edits': edits_str})
    
    res_df = res['table']
    assert res_df.at[1, 'A'] == 20
    assert res_df.at[2, 'B'] == 'z'
    
    # Types should be preserved
    assert isinstance(res_df.at[1, 'A'], (int, np.integer))
    assert res_df.at[0, 'A'] == 1  # unchanged

def test_df_editor_invalid_json():
    df = pd.DataFrame({
        'A': [1, 2, 3]
    })
    node = DataFrameEditorNode()
    # Invalid JSON string should be handled gracefully (no crash)
    res = node.process({'table': df}, {'edits': '{invalid json'})
    pd.testing.assert_frame_equal(res['table'], df)
