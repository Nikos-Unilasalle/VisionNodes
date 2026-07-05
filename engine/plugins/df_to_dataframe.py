"""Dict to DataFrame — turns a dict of metrics into a DataFrame for clean CSV export.

Handles the common metric shapes:
  {'mae': 0.1, 'rmse': 0.2}          -> 1 row, one column per key
  {'a': [1,2,3], 'b': [4,5,6]}       -> 3 rows, columns a,b
  {'a': 1, 'b': [4,5,6]}             -> scalars broadcast to the list length
"""
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'df_to_dataframe'

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False


def _py(v):
    """Coerce numpy scalars / nested containers into JSON-friendly Python values."""
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


def _df_meta(df) -> dict:
    r, c = df.shape

    def _ser(v):
        if isinstance(v, float) and v != v:
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, (float, np.floating)):
            return float(v)
        if isinstance(v, int):
            return v
        return str(v)

    return {
        'shape':   [r, c],
        'columns': [str(col) for col in df.columns],
        'dtypes':  {str(col): str(df[col].dtype) for col in df.columns},
        'nulls':   {str(col): int(df[col].isna().sum()) for col in df.columns},
        'head':    [{str(k): _ser(v) for k, v in row.items()}
                    for _, row in df.head(8).iterrows()],
    }


@vision_node(
    type_id='df_to_dataframe',
    label='Dict to DataFrame',
    category='DataFrame',
    icon='Table',
    description="Builds a DataFrame from a dict. Scalar values give one row (one column per key); "
                "list/array values give one row each and scalars are broadcast to match. "
                "Key/Value mode emits a 2-column (metric, value) table instead. Connect to DF Collect or DF Export.",
    inputs=[{'id': 'dict_in', 'color': 'dict', 'label': 'Dict'}],
    outputs=[
        {'id': 'data',    'color': 'data',  'label': 'DataFrame'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'orient', 'label': 'Layout', 'type': 'enum',
         'options': ['Columns (keys = columns)', 'Key/Value rows'], 'default': 0},
    ]
)
class DictToDataFrameNode(NodeProcessor):
    def process(self, inputs, params):
        if not _PD_OK:
            send_notification("Dict to DataFrame: pandas not installed", level='error', notif_id=_NOTIF)
            return {}

        d = inputs.get('dict_in')
        if not isinstance(d, dict) or not d:
            send_notification("Dict to DataFrame: no dict connected", level='warning', notif_id=_NOTIF)
            return {}

        orient = int(params.get('orient', 0))

        if orient == 1:
            # Key/Value 2-column table (one metric per row)
            rows = [{'metric': str(k), 'value': _py(v)} for k, v in d.items()]
            df = pd.DataFrame(rows, columns=['metric', 'value'])
            return {'data': df, 'df_meta': _df_meta(df)}

        # Columns layout: list/array values become columns of N rows; scalars broadcast.
        values = {k: _py(v) for k, v in d.items()}
        lengths = [len(v) for v in values.values() if isinstance(v, list)]
        n = max(lengths) if lengths else 1
        cols = {}
        for k, v in values.items():
            if isinstance(v, list):
                if len(v) == n:
                    cols[str(k)] = v
                else:
                    # ragged list — keep as one cell so no data is silently dropped
                    cols[str(k)] = [v] + [None] * (n - 1)
            else:
                cols[str(k)] = [v] * n

        try:
            df = pd.DataFrame(cols)
        except Exception as e:
            send_notification(f"Dict to DataFrame: could not build ({e})", level='error', notif_id=_NOTIF)
            return {}

        send_notification(f"Dict to DataFrame: {df.shape[0]}×{df.shape[1]}", level='info', notif_id=_NOTIF)
        return {'data': df, 'df_meta': _df_meta(df)}
