"""
DataFrame manipulation nodes — pandas operations for VNStudio.
Category: 'DataFrame'
All nodes accept/output 'data' color handles (orange).
"""
import os
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'df_nodes'

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False


def _check_pd(node_name: str) -> bool:
    if not _PD_OK:
        send_notification(f"{node_name}: pandas not installed", level='error', notif_id=_NOTIF)
        return False
    return True


def _df_meta(df) -> dict:
    r, c = df.shape
    head_df = df.head(8)
    return {
        'shape':   [r, c],
        'columns': [str(col) for col in df.columns],
        'dtypes':  {str(col): str(df[col].dtype) for col in df.columns},
        'nulls':   {str(col): int(df[col].isna().sum()) for col in df.columns},
        'head':    [{str(k): (None if (isinstance(v, float) and v != v) else (
                        int(v) if hasattr(v, 'item') and isinstance(v, (int,)) else
                        float(v) if isinstance(v, float) else str(v)
                    )) for k, v in row.items()}
                   for _, row in head_df.iterrows()],
    }


def _render_text_panel(text: str, w: int, h: int, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
    x0, y0, line_h = 8, 44, 15
    for i, line in enumerate(text.split('\n')[:(h - y0) // line_h]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, line[:100], (x0, y0 + i * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
    return img


def _render_df_head(df, w: int, h: int, title: str = '') -> np.ndarray:
    MAX_R, MAX_C = 8, 7
    sub   = df.iloc[:MAX_R, :MAX_C]
    col_w = 13
    header = ' | '.join(str(c)[:col_w].ljust(col_w) for c in sub.columns)
    sep    = '-' * len(header)
    rows   = [' | '.join(str(v)[:col_w].ljust(col_w) for v in row) for _, row in sub.iterrows()]
    return _render_text_panel('\n'.join([header, sep] + rows), w, h, title=title)


def _meta_and_preview(df, w: int = 420, h: int = 200, title: str = '') -> dict:
    try:
        meta    = _df_meta(df)
        preview = _render_df_head(df, w, h, title=title)
    except Exception:
        meta    = {}
        preview = np.zeros((h, w, 3), dtype=np.uint8)
    return {'df_meta': meta, 'preview': preview}


# ─── DF Export ────────────────────────────────────────────────────────────────

_FMT_LABELS = ['CSV', 'Excel (.xlsx)', 'JSON', 'Parquet']


@vision_node(
    type_id='df_export',
    label='DF Export',
    category='DataFrame',
    icon='Save',
    description="Save a DataFrame to CSV, Excel, JSON or Parquet. Trigger the Save button once to write the file.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[],
    params=[
        {'id': 'save',      'label': 'Save',            'type': 'trigger', 'default': 0},
        {'id': 'path',      'label': 'File Path',       'type': 'string',  'default': 'output.csv'},
        {'id': 'format',    'label': 'Format',          'type': 'enum',    'options': _FMT_LABELS, 'default': 0},
        {'id': 'separator', 'label': 'CSV Separator',   'type': 'string',  'default': ','},
        {'id': 'index',     'label': 'Write Index',     'type': 'bool',    'default': False},
    ]
)
class DfExportNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Export'):
            return {}
        if not int(params.get('save', 0)):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            send_notification("DF Export: no DataFrame connected", level='warning', notif_id=_NOTIF)
            return {}
        path   = str(params.get('path', 'output.csv')).strip()
        fmt    = int(params.get('format', 0))
        sep    = str(params.get('separator', ','))
        index  = bool(params.get('index', False))
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            if fmt == 0:
                df.to_csv(path, sep=sep, index=index)
            elif fmt == 1:
                df.to_excel(path, index=index)
            elif fmt == 2:
                df.to_json(path, orient='records', indent=2)
            else:
                df.to_parquet(path, index=index)
            r, c = df.shape
            send_notification(f"DF Export: saved {r}×{c} → {os.path.basename(path)}", level='info', notif_id=_NOTIF)
        except Exception as e:
            send_notification(f"DF Export error: {e}", level='error', notif_id=_NOTIF)
        return {}


# ─── DF Select Columns ────────────────────────────────────────────────────────

@vision_node(
    type_id='df_select',
    label='DF Select',
    category='DataFrame',
    icon='Columns',
    description="Keep specific columns, drop others, or rename them. Columns: comma-separated names. Drop: columns to remove. Rename: old:new,old2:new2.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'col_count', 'color': 'scalar', 'label': 'Cols'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'keep',   'label': 'Keep Columns (blank = all)', 'type': 'string', 'default': ''},
        {'id': 'drop',   'label': 'Drop Columns',               'type': 'string', 'default': ''},
        {'id': 'rename', 'label': 'Rename  (old:new, …)',       'type': 'string', 'default': ''},
    ],
    resizable=True, min_width=260, min_height=160,
)
class DfSelectNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Select'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        keep   = [c.strip() for c in str(params.get('keep', '')).split(',') if c.strip()]
        drop   = [c.strip() for c in str(params.get('drop', '')).split(',') if c.strip()]
        rename = str(params.get('rename', '')).strip()
        out = df.copy()
        if keep:
            valid = [c for c in keep if c in out.columns]
            out = out[valid]
        if drop:
            out = out.drop(columns=[c for c in drop if c in out.columns], errors='ignore')
        if rename:
            rmap = {}
            for pair in rename.split(','):
                if ':' in pair:
                    old, new = pair.split(':', 1)
                    rmap[old.strip()] = new.strip()
            out = out.rename(columns=rmap)
        r, c = out.shape
        extra = _meta_and_preview(out, title='Select')
        return {'table': out, 'row_count': float(r), 'col_count': float(c), **extra}


# ─── DF Sort ──────────────────────────────────────────────────────────────────

@vision_node(
    type_id='df_sort',
    label='DF Sort',
    category='DataFrame',
    icon='ArrowUpDown',
    description="Sort rows by one or more columns. Column: comma-separated names for multi-level sort.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',   'color': 'data',  'label': 'DataFrame'},
        {'id': 'preview', 'color': 'image', 'label': 'Preview'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'by',        'label': 'Sort By (column name)',       'type': 'string', 'default': ''},
        {'id': 'ascending', 'label': 'Ascending',                   'type': 'bool',   'default': True},
        {'id': 'na_pos',    'label': 'NaN position (first/last)',   'type': 'enum',   'options': ['last', 'first'], 'default': 0},
    ],
    resizable=True, min_width=240, min_height=160,
)
class DfSortNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Sort'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        by  = [c.strip() for c in str(params.get('by', '')).split(',') if c.strip()]
        asc = bool(params.get('ascending', True))
        na  = 'first' if int(params.get('na_pos', 0)) == 1 else 'last'
        if not by:
            return _meta_and_preview(df, title='Sort (no column)')  | {'table': df}
        valid = [c for c in by if c in df.columns]
        if not valid:
            return _meta_and_preview(df, title='Sort (column not found)') | {'table': df}
        out   = df.sort_values(by=valid, ascending=asc, na_position=na)
        extra = _meta_and_preview(out, title=f'Sort by {valid[0]}')
        return {'table': out, **extra}


# ─── DF Sample / Head / Tail ──────────────────────────────────────────────────

_SAMPLE_MODES = ['head', 'tail', 'sample', 'slice']


@vision_node(
    type_id='df_sample',
    label='DF Sample',
    category='DataFrame',
    icon='Rows',
    description="Extract a subset of rows: head (first N), tail (last N), random sample, or slice (start:end).",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'mode',  'label': 'Mode', 'type': 'enum', 'options': _SAMPLE_MODES, 'default': 0},
        {'id': 'n',     'label': 'N rows (head/tail/sample)',  'type': 'int', 'default': 10, 'min': 1, 'max': 100000},
        {'id': 'start', 'label': 'Start index (slice)',        'type': 'int', 'default': 0,  'min': 0, 'max': 100000},
        {'id': 'end',   'label': 'End index   (slice)',        'type': 'int', 'default': 10, 'min': 1, 'max': 100000},
        {'id': 'seed',  'label': 'Random seed (sample)',       'type': 'int', 'default': 42, 'min': 0, 'max': 9999},
    ],
    resizable=True, min_width=240, min_height=160,
)
class DfSampleNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Sample'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        mode  = _SAMPLE_MODES[int(params.get('mode', 0))]
        n     = max(1, int(params.get('n', 10)))
        start = int(params.get('start', 0))
        end   = int(params.get('end', 10))
        seed  = int(params.get('seed', 42))
        if mode == 'head':
            out = df.head(n)
        elif mode == 'tail':
            out = df.tail(n)
        elif mode == 'sample':
            out = df.sample(min(n, len(df)), random_state=seed)
        else:  # slice
            out = df.iloc[start:end]
        extra = _meta_and_preview(out, title=mode)
        return {'table': out, 'row_count': float(len(out)), **extra}


# ─── DF GroupBy ───────────────────────────────────────────────────────────────

_AGG_LABELS = ['mean', 'sum', 'count', 'min', 'max', 'std', 'median', 'nunique']


@vision_node(
    type_id='df_groupby',
    label='DF GroupBy',
    category='DataFrame',
    icon='Group',
    description="Group rows by a column and aggregate numeric columns. Result is a new DataFrame with one row per group.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'Result DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Groups'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'by',  'label': 'Group By column',        'type': 'string', 'default': ''},
        {'id': 'agg', 'label': 'Aggregation',            'type': 'enum',   'options': _AGG_LABELS, 'default': 0},
        {'id': 'cols','label': 'Agg Columns (blank=all)','type': 'string', 'default': ''},
        {'id': 'reset_index', 'label': 'Reset Index',   'type': 'bool',   'default': True},
    ],
    resizable=True, min_width=240, min_height=180,
)
class DfGroupByNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF GroupBy'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        by  = str(params.get('by', '')).strip()
        if not by or by not in df.columns:
            return {}
        agg   = _AGG_LABELS[int(params.get('agg', 0))]
        cols  = [c.strip() for c in str(params.get('cols', '')).split(',') if c.strip()]
        reset = bool(params.get('reset_index', True))
        sub   = df[cols] if cols else df.select_dtypes(include='number')
        sub   = sub.copy()
        sub[by] = df[by]
        grp = sub.groupby(by).agg(agg)
        out = grp.reset_index() if reset else grp
        extra = _meta_and_preview(out, title=f'GroupBy {by} / {agg}')
        return {'table': out, 'row_count': float(len(out)), **extra}


# ─── DF Merge ─────────────────────────────────────────────────────────────────

_HOW_LABELS = ['inner', 'left', 'right', 'outer']


@vision_node(
    type_id='df_merge',
    label='DF Merge',
    category='DataFrame',
    icon='Merge',
    description="Merge two DataFrames on key columns (SQL-style join). Connect left and right DataFrames.",
    inputs=[
        {'id': 'left',  'color': 'data', 'label': 'Left DF'},
        {'id': 'right', 'color': 'data', 'label': 'Right DF'},
    ],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'Merged DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'left_on',  'label': 'Left key column',  'type': 'string', 'default': ''},
        {'id': 'right_on', 'label': 'Right key column', 'type': 'string', 'default': ''},
        {'id': 'how',      'label': 'Join type',         'type': 'enum',   'options': _HOW_LABELS, 'default': 0},
    ],
    resizable=True, min_width=260, min_height=160,
)
class DfMergeNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Merge'):
            return {}
        left  = inputs.get('left')
        right = inputs.get('right')
        if not isinstance(left, pd.DataFrame) or not isinstance(right, pd.DataFrame):
            return {}
        left_on  = str(params.get('left_on',  '')).strip()
        right_on = str(params.get('right_on', '')).strip() or left_on
        how = _HOW_LABELS[int(params.get('how', 0))]
        try:
            if left_on and left_on in left.columns and right_on in right.columns:
                out = pd.merge(left, right, left_on=left_on, right_on=right_on, how=how)
            else:
                common = list(set(left.columns) & set(right.columns))
                if not common:
                    return {}
                out = pd.merge(left, right, on=common, how=how)
        except Exception as e:
            send_notification(f"DF Merge error: {e}", level='error', notif_id=_NOTIF)
            return {}
        extra = _meta_and_preview(out, title=f'Merge ({how})')
        return {'table': out, 'row_count': float(len(out)), **extra}


# ─── DF Fill / Drop NaN ───────────────────────────────────────────────────────

_FILL_STRATEGIES = ['value', 'mean', 'median', 'mode', 'ffill', 'bfill', 'drop_rows', 'drop_cols']


@vision_node(
    type_id='df_fillna',
    label='DF Fill NA',
    category='DataFrame',
    icon='Eraser',
    description="Handle missing values: fill with constant, statistics, forward/back fill, or drop rows/columns.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'null_count','color': 'scalar', 'label': 'Nulls before'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'strategy', 'label': 'Strategy',                      'type': 'enum',   'options': _FILL_STRATEGIES, 'default': 0},
        {'id': 'value',    'label': 'Fill value (strategy=value)',    'type': 'string', 'default': '0'},
        {'id': 'columns',  'label': 'Columns (blank = all)',          'type': 'string', 'default': ''},
        {'id': 'thresh',   'label': 'Min non-null (drop_cols only)',  'type': 'int',    'default': 1, 'min': 1, 'max': 100000},
    ],
    resizable=True, min_width=240, min_height=180,
)
class DfFillNaNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Fill NA'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        strategy = _FILL_STRATEGIES[int(params.get('strategy', 0))]
        cols_raw = [c.strip() for c in str(params.get('columns', '')).split(',') if c.strip()]
        cols     = [c for c in cols_raw if c in df.columns] or list(df.columns)
        null_before = float(df.isna().sum().sum())
        out = df.copy()
        try:
            if strategy == 'drop_rows':
                out = out.dropna(subset=cols)
            elif strategy == 'drop_cols':
                thresh = int(params.get('thresh', 1))
                out = out.dropna(axis=1, thresh=thresh)
            elif strategy == 'ffill':
                out[cols] = out[cols].ffill()
            elif strategy == 'bfill':
                out[cols] = out[cols].bfill()
            elif strategy == 'mean':
                out[cols] = out[cols].fillna(out[cols].mean())
            elif strategy == 'median':
                out[cols] = out[cols].fillna(out[cols].median())
            elif strategy == 'mode':
                for c in cols:
                    m = out[c].mode()
                    if not m.empty:
                        out[c] = out[c].fillna(m.iloc[0])
            else:  # value
                raw_val = str(params.get('value', '0'))
                try:
                    fill = float(raw_val)
                except ValueError:
                    fill = raw_val
                out[cols] = out[cols].fillna(fill)
        except Exception as e:
            send_notification(f"DF Fill NA error: {e}", level='error', notif_id=_NOTIF)
        extra = _meta_and_preview(out, title=f'Fill NA ({strategy})')
        return {'table': out, 'null_count': null_before, **extra}


# ─── DF New Column ────────────────────────────────────────────────────────────

@vision_node(
    type_id='df_new_col',
    label='DF New Column',
    category='DataFrame',
    icon='PlusSquare',
    description="Add a computed column using a Python expression. Use df['col'] to reference columns. Example: df['a'] + df['b'].",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',   'color': 'data',  'label': 'DataFrame'},
        {'id': 'preview', 'color': 'image', 'label': 'Preview'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'name', 'label': 'New column name', 'type': 'string', 'default': 'new_col'},
        {'id': 'expr', 'label': 'Expression',      'type': 'code',   'default': "df['col_a'] + df['col_b']"},
    ],
    resizable=True, min_width=260, min_height=160,
)
class DfNewColNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF New Column'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        name = str(params.get('name', 'new_col')).strip() or 'new_col'
        expr = str(params.get('expr', '')).strip()
        if not expr:
            return {'table': df, **_meta_and_preview(df)}
        out = df.copy()
        try:
            import numpy as _np
            result = eval(expr, {'df': out, 'pd': pd, 'np': _np})  # noqa: S307
            out[name] = result
        except Exception as e:
            send_notification(f"DF New Column error: {e}", level='error', notif_id=_NOTIF)
        extra = _meta_and_preview(out, title=name)
        return {'table': out, **extra}


# ─── DF Rename ────────────────────────────────────────────────────────────────

@vision_node(
    type_id='df_rename',
    label='DF Rename',
    category='DataFrame',
    icon='Type',
    description="Rename columns. Format: old:new,old2:new2. Leave blank to pass through unchanged.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',   'color': 'data',  'label': 'DataFrame'},
        {'id': 'preview', 'color': 'image', 'label': 'Preview'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'map', 'label': 'Rename map  (old:new, …)', 'type': 'string', 'default': ''},
        {'id': 'strip_spaces', 'label': 'Strip spaces in column names', 'type': 'bool', 'default': False},
    ],
    resizable=True, min_width=240, min_height=140,
)
class DfRenameNode(NodeProcessor):
    def process(self, inputs, params):
        if not _check_pd('DF Rename'):
            return {}
        df = inputs.get('table')
        if not isinstance(df, pd.DataFrame):
            return {}
        out = df.copy()
        if bool(params.get('strip_spaces', False)):
            out.columns = [str(c).strip() for c in out.columns]
        raw = str(params.get('map', '')).strip()
        if raw:
            rmap = {}
            for pair in raw.split(','):
                if ':' in pair:
                    old, new = pair.split(':', 1)
                    rmap[old.strip()] = new.strip()
            out = out.rename(columns=rmap)
        extra = _meta_and_preview(out, title='Rename')
        return {'table': out, **extra}
