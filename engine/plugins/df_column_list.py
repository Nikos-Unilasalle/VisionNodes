"""
DF Column → List.

df_column_list : extract one column of a DataFrame as a plain list (array).
    Generic, reusable: feed the output into DataFrame Plot's X/Y inputs, into a
    Plotter, statistics, or any node that accepts a 'list'. Drop two of these
    (one for X, one for Y) to drive a chart directly from raw columns.

Outputs the column values (numeric or string), plus its length.
"""
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'df_column_list'


def _resolve_col(df, name: str):
    """Match a user-typed column name: exact first, then trimmed/case-insensitive.
    Returns the real column name, or None when nothing matches."""
    name = str(name or '').strip()
    if not name:
        return None
    if name in df.columns:
        return name
    lowered = {str(c).strip().lower(): c for c in df.columns}
    return lowered.get(name.lower())


@vision_node(
    type_id='df_column_list',
    label='DF Column → List',
    category='DataFrame',
    icon='List',
    description=(
        "Extract one DataFrame column, as a list (array) and as a single-column "
        "DataFrame. Reusable everywhere a 'list' is accepted — wire it into "
        "DataFrame Plot X/Y, a Plotter, or stats. Blank column = the first one. "
        "Optionally drop NaNs and coerce to numeric."
    ),
    inputs=[
        {'id': 'table', 'color': 'data', 'label': 'DataFrame'},
    ],
    outputs=[
        {'id': 'list',    'color': 'list',   'label': 'Values'},
        {'id': 'table',   'color': 'data',   'label': 'Column (DF)'},
        {'id': 'count',   'color': 'scalar', 'label': 'Count'},
        {'id': 'df_meta', 'color': 'dict',   'label': 'Columns'},
    ],
    params=[
        {'id': 'column',  'label': 'Column', 'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': 'dropna',  'label': 'Drop NaN', 'type': 'bool', 'default': True},
        {'id': 'numeric', 'label': 'Coerce to numeric', 'type': 'bool', 'default': False},
    ],
)
class DFColumnListNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        requested = str(params.get('column', '')).strip()
        dropna  = bool(params.get('dropna', True))
        numeric = bool(params.get('numeric', False))

        # Emitted first: the inspector reads it to offer the column-name chips.
        meta = {
            'shape':   list(df.shape),
            'columns': [str(c) for c in df.columns],
            'dtypes':  {str(c): str(df[c].dtype) for c in df.columns},
        }

        if len(df.columns) == 0:
            return {'df_meta': meta}

        # Fall back to the first column so the node is useful before configuration.
        col = _resolve_col(df, requested) or (None if requested else str(df.columns[0]))
        if col is None:
            send_notification(f"DF Column → List: column '{requested}' not found",
                              level='warning', notif_id=_NOTIF_ID)
            return {'df_meta': meta}

        series = df[col]
        if numeric:
            import pandas as pd
            series = pd.to_numeric(series, errors='coerce')
        if dropna:
            series = series.dropna()

        values = series.tolist()
        # Convert numpy scalars to native Python types for clean JSON serialization.
        values = [v.item() if isinstance(v, np.generic) else v for v in values]

        return {
            'list':    values,
            'table':   series.to_frame(name=col),
            'count':   float(len(values)),
            'df_meta': meta,
        }
