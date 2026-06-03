import json
import numpy as np
import pandas as pd
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'df_editor'

def _df_meta_with_rows(df, max_rows=5000) -> dict:
    r, c = df.shape
    slice_df = df.head(max_rows)
    
    def _serialize(v):
        if isinstance(v, float) and v != v:  # NaN
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, (int,)):
            return v
        if isinstance(v, (float, np.floating)):
            return float(v)
        return str(v)
        
    rows = []
    for idx, row in slice_df.iterrows():
        row_dict = {str(k): _serialize(v) for k, v in row.items()}
        row_dict['__row_index__'] = int(idx) if isinstance(idx, (int, np.integer)) else str(idx)
        rows.append(row_dict)
        
    return {
        'shape':   [r, c],
        'columns': [str(col) for col in df.columns],
        'dtypes':  {str(col): str(df[col].dtype) for col in df.columns},
        'nulls':   {str(col): int(df[col].isna().sum()) for col in df.columns},
        'rows':    rows,
        'truncated': r > max_rows
    }

def _cast_val(val, dtype_str):
    if val is None or val == "":
        # For numeric columns, use NaN; for object/string columns, use None or ""
        if dtype_str.startswith('int') or dtype_str.startswith('float'):
            return np.nan
        return None
    if dtype_str.startswith('int'):
        try:
            return int(float(val))
        except ValueError:
            return val
    if dtype_str.startswith('float'):
        try:
            return float(val)
        except ValueError:
            return val
    if dtype_str.startswith('bool'):
        return str(val).lower() in ('true', '1', 'yes')
    return val

@vision_node(
    type_id='df_editor',
    label='DF Editor',
    category='DataFrame',
    icon='Edit3',
    description="Interactive DataFrame cell editor. Double-click cells to modify values.",
    inputs=[
        {'id': 'table', 'color': 'data', 'label': 'DataFrame'}
    ],
    outputs=[
        {'id': 'table',   'color': 'data',  'label': 'DataFrame'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'DF Metadata'},
        {'id': 'preview', 'color': 'image', 'label': 'Preview'}
    ],
    params=[
        {'id': 'edits', 'label': 'Edits JSON', 'type': 'string', 'default': '[]'}
    ],
    resizable=True,
    min_width=260,
    min_height=180
)
class DataFrameEditorNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}
            
        df_mod = df.copy()
        
        # Parse and apply edits
        edits_raw = params.get('edits', '[]')
        edits = []
        if isinstance(edits_raw, str):
            try:
                edits = json.loads(edits_raw)
            except Exception as e:
                send_notification(f"DF Editor: JSON parse error in edits: {e}", level='error', notif_id=_NOTIF_ID)
        elif isinstance(edits_raw, list):
            edits = edits_raw
            
        applied_count = 0
        if isinstance(edits, list) and len(edits) > 0:
            for edit in edits:
                idx = edit.get('index')
                col = edit.get('col')
                val = edit.get('val')
                
                # Check column and index exist
                if col in df_mod.columns:
                    # Cast index key if needed (match df_mod.index type)
                    target_idx = idx
                    if isinstance(df_mod.index, pd.RangeIndex) or df_mod.index.dtype.kind in 'iu':
                        try:
                            target_idx = int(idx)
                        except (ValueError, TypeError):
                            pass
                            
                    if target_idx in df_mod.index:
                        dtype_str = str(df_mod[col].dtype)
                        casted = _cast_val(val, dtype_str)
                        df_mod.at[target_idx, col] = casted
                        applied_count += 1
                        
            if applied_count > 0:
                send_notification(f"DF Editor: applied {applied_count} cell edits", notif_id=_NOTIF_ID)

        # Matplotlib renderer for node preview image
        from plugins.ml_data_nodes import _render_df_table
        w = int(params.get('width', 380))
        h = int(params.get('height', 200))
        preview = _render_df_table(df_mod, w, h, title=f"DF Editor ({len(df_mod)} rows)")
        
        return {
            'table':   df_mod,
            'df_meta': _df_meta_with_rows(df_mod),
            'preview': preview
        }
