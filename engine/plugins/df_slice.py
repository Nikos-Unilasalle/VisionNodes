"""
DF Slice — keep a contiguous row range of a DataFrame (e.g. rows 10 to 200).

Positional slicing on row *position*, not on the index labels, so it behaves the
same on a freshly read CSV and on a filtered/re-indexed table.
Negative positions count from the end (-100 = the last 100 rows).

Self-contained: matplotlib Agg backend, no cross-plugin imports.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'df_slice'

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False

_PREVIEW_ROWS, _PREVIEW_COLS = 8, 7


def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _render_table(df, w: int, h: int, title: str = '') -> np.ndarray:
    """Dark-theme matplotlib table of the first rows/columns."""
    sub = df.iloc[:_PREVIEW_ROWS, :_PREVIEW_COLS]
    col_labels = [str(c)[:16] for c in sub.columns] or ['(no data)']
    rows = [[str(sub.iloc[i][c])[:16] for c in sub.columns] for i in range(len(sub))]
    if not rows:
        rows = [['—'] * len(col_labels)]

    _, plt = _get_mpl()
    fig, ax = plt.subplots(figsize=(w / 100, h / 100))
    ax.set_axis_off()
    fig.patch.set_facecolor('#161616')

    tbl = ax.table(cellText=rows, colLabels=col_labels, loc='upper center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.5)
    for j in range(len(col_labels)):
        cell = tbl[0, j]
        cell.set_facecolor('#2a2a3a')
        cell.set_text_props(color='#a5b4fc', fontweight='bold')
        cell.set_edgecolor('#444466')
    for i in range(len(rows)):
        for j in range(len(col_labels)):
            cell = tbl[i + 1, j]
            cell.set_facecolor('#181820' if i % 2 == 0 else '#1a1a28')
            cell.set_edgecolor('#2a2a40')
            cell.set_text_props(color='#cccccc')

    ax.set_title(title, fontsize=9, color='#cccccc', pad=8)
    fig.tight_layout(pad=0.5)
    img = _fig_to_bgr(fig)
    plt.close(fig)
    return img


def _df_meta(df) -> dict:
    r, c = df.shape
    return {
        'shape':   [r, c],
        'columns': [str(col) for col in df.columns],
        'dtypes':  {str(col): str(df[col].dtype) for col in df.columns},
    }


def _abs_pos(value: int, n: int) -> int:
    """Turn a possibly-negative row position into an absolute one."""
    return value if value >= 0 else n + value


def _scalar_or_param(inputs, params, port: str, key: str, default: int) -> int:
    """A wired scalar wins over the typed parameter."""
    wired = inputs.get(port)
    if isinstance(wired, (int, float, np.integer, np.floating)):
        return int(wired)
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        return default


@vision_node(
    type_id='df_slice',
    label='DF Slice',
    category='DataFrame',
    icon='Scissors',
    description=(
        "Keep a contiguous range of rows, by position (rows 10 to 200). "
        "End = -1 means the last row; negative positions count from the end "
        "(Start -100, End -1 = the last 100 rows). Step > 1 keeps every Nth row. "
        "Start / End can also be driven by wired scalars."
    ),
    inputs=[
        {'id': 'table',    'color': 'data',   'label': 'DataFrame'},
        {'id': 'start',    'color': 'scalar', 'label': 'Start'},
        {'id': 'end',      'color': 'scalar', 'label': 'End'},
        {'id': 'img_size', 'color': 'list',   'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
        {'id': 'img_size',  'color': 'list',   'label': 'Img Size'},
    ],
    params=[
        {'id': 'start',        'label': 'Start Row (0-based, incl.)', 'type': 'int', 'default': 0,  'min': -10_000_000, 'max': 10_000_000},
        {'id': 'end',          'label': 'End Row (incl., -1 = last)', 'type': 'int', 'default': -1, 'min': -10_000_000, 'max': 10_000_000},
        {'id': 'step',         'label': 'Step (1 = every row)',       'type': 'int', 'default': 1,  'min': 1, 'max': 10_000},
        {'id': 'reset_index',  'label': 'Renumber index from 0',      'type': 'bool', 'default': False},
    ],
    resizable=True,
    min_width=260,
    min_height=160,
)
class DfSliceNode(NodeProcessor):
    def process(self, inputs, params):
        if not _PD_OK:
            send_notification("DF Slice: pandas not installed", level='error', notif_id=_NOTIF)
            return {}

        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}

        n = len(df)
        start = _abs_pos(_scalar_or_param(inputs, params, 'start', 'start', 0), n)
        end = _abs_pos(_scalar_or_param(inputs, params, 'end', 'end', -1), n)
        step = max(1, int(params.get('step', 1)))

        start = max(0, min(start, n))
        end = min(end, n - 1)

        if end < start:
            send_notification(f"DF Slice: empty range (start {start} > end {end})",
                              level='warning', notif_id=_NOTIF)
            out = df.iloc[0:0]
        else:
            out = df.iloc[start:end + 1:step]

        if bool(params.get('reset_index', False)):
            out = out.reset_index(drop=True)

        s = inputs.get('img_size')
        w, h = ((int(s[0]), int(s[1])) if isinstance(s, (list, tuple)) and len(s) >= 2
                else (int(params.get('width', 420)), int(params.get('height', 200))))

        try:
            preview = _render_table(out, w, h, title=f"Slice {start}–{end} ({len(out)} rows)")
        except Exception as e:
            send_notification(f"DF Slice: preview failed ({e})", level='warning', notif_id=_NOTIF)
            preview = np.zeros((h, w, 3), dtype=np.uint8)

        return {
            'table':     out,
            'preview':   preview,
            'row_count': float(len(out)),
            'df_meta':   _df_meta(out),
            'img_size':  [w, h],
        }
