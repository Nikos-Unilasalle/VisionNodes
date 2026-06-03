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
    assert len(meta['rows']) == 3
    assert meta['rows'][0]['A'] == 1
    assert meta['rows'][0]['B'] == 'a'
    assert meta['rows'][0]['__row_index__'] == 0

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
