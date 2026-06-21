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


@vision_node(
    type_id='df_column_list',
    label='DF Column → List',
    category='DataFrame',
    icon='List',
    description=(
        "Extract one DataFrame column as a list (array). Reusable everywhere a "
        "'list' is accepted — wire it into DataFrame Plot X/Y, a Plotter, or stats. "
        "Optionally drop NaNs and coerce to numeric."
    ),
    inputs=[
        {'id': 'table', 'color': 'data', 'label': 'DataFrame'},
    ],
    outputs=[
        {'id': 'list',  'color': 'list',   'label': 'Values'},
        {'id': 'count', 'color': 'scalar', 'label': 'Count'},
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

        col     = str(params.get('column', '')).strip()
        dropna  = bool(params.get('dropna', True))
        numeric = bool(params.get('numeric', False))

        if not col:
            # Fall back to the first column so the node is useful before configuration.
            if len(df.columns) == 0:
                return {}
            col = str(df.columns[0])

        if col not in df.columns:
            send_notification(f"DF Column → List: column '{col}' not found", level='warning', notif_id=_NOTIF_ID)
            return {}

        series = df[col]
        if numeric:
            import pandas as pd
            series = pd.to_numeric(series, errors='coerce')
        if dropna:
            series = series.dropna()

        values = series.tolist()
        # Convert numpy scalars to native Python types for clean JSON serialization.
        values = [v.item() if isinstance(v, np.generic) else v for v in values]

        return {'list': values, 'count': float(len(values))}
