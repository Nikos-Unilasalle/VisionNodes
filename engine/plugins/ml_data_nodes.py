"""
ML Training — Data Nodes (CSV Reader, DataFrame Filter, DataFrame Stats).
Designed for VNStudio ML formation: no realtime dependencies, static graph.
DataFrame objects travel between nodes as native Python objects in-process.
Handle color: 'data' (orange, already defined in HANDLE_COLORS).
"""
import io
import os
import cv2
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_data'

# ─── Shared render helpers ────────────────────────────────────────────────────

def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


_MPL_DARK = {
    'figure.facecolor': '#161616',
    'axes.facecolor':   '#1e1e1e',
    'axes.edgecolor':   '#555555',
    'axes.labelcolor':  '#cccccc',
    'text.color':       '#cccccc',
    'xtick.color':      '#aaaaaa',
    'ytick.color':      '#aaaaaa',
    'grid.color':       '#333333',
    'grid.linestyle':   '--',
    'grid.linewidth':   0.5,
}


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _table_img(col_labels, rows, w, h, title, row_colors=None, dpi=100) -> np.ndarray:
    """Generic matplotlib table renderer."""
    _, plt = _get_mpl()
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi))
    ax.set_axis_off()
    fig.patch.set_facecolor('#161616')

    tbl = ax.table(cellText=rows, colLabels=col_labels,
                   loc='upper center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.5)

    for j in range(len(col_labels)):
        cell = tbl[0, j]
        cell.set_facecolor('#2a2a3a')
        cell.set_text_props(color='#a5b4fc', fontweight='bold')
        cell.set_edgecolor('#444466')

    for i, row in enumerate(rows):
        bg = '#181820' if i % 2 == 0 else '#1a1a28'
        for j in range(len(col_labels)):
            cell = tbl[i + 1, j]
            cell.set_facecolor(bg)
            cell.set_edgecolor('#2a2a40')
            color = (row_colors[i][j] if row_colors and row_colors[i][j] else '#cccccc')
            cell.set_text_props(color=color)

    ax.set_title(title, fontsize=9, color='#cccccc', pad=8)
    fig.tight_layout(pad=0.5)
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img


def _df_meta(df) -> dict:
    """Serializable DataFrame metadata for the inspector panel."""
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
    """Legacy fallback — used by CSV Reader and DF Filter head preview."""
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
    """Render DataFrame.head() as a monospaced table image (CSV/Filter preview)."""
    MAX_R, MAX_C = 8, 7
    sub = df.iloc[:MAX_R, :MAX_C]
    col_w = 13
    header = ' | '.join(str(c)[:col_w].ljust(col_w) for c in sub.columns)
    sep    = '-' * len(header)
    rows   = [' | '.join(str(v)[:col_w].ljust(col_w) for v in row) for _, row in sub.iterrows()]
    return _render_text_panel('\n'.join([header, sep] + rows), w, h, title=title)


# ─── CSV Reader ───────────────────────────────────────────────────────────────

_SEPARATORS = [',', ';', '\t', '|']
_SEP_LABELS  = ['Comma (,)', 'Semicolon (;)', 'Tab (\\t)', 'Pipe (|)']

@vision_node(
    type_id='ml_csv_reader',
    label='CSV Reader',
    category='DataFrame',
    icon='FileText',
    description="Load a CSV file as a DataFrame. Connect to DF Filter or DF Stats.",
    inputs=[],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'col_count', 'color': 'scalar', 'label': 'Cols'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'path',      'label': 'File Path',          'type': 'string', 'default': 'data.csv'},
        {'id': 'separator', 'label': 'Separator',          'type': 'enum',   'options': _SEP_LABELS, 'default': 0},
        {'id': 'max_rows',  'label': 'Max Rows (0 = all)', 'type': 'int',    'default': 0, 'min': 0, 'max': 100000},
        {'id': 'reload',    'label': 'Reload',             'type': 'trigger','default': 0},
    ],
    resizable=True,
    min_width=290,
    min_height=200,
)
class MLCsvReaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._df        = None
        self._last_key  = None   # (path, sep, nrows)

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF_ID):
            return {}
        import pandas as pd

        path    = str(params.get('path', 'data.csv')).strip()
        sep_idx = int(params.get('separator', 0))
        sep     = _SEPARATORS[sep_idx]
        max_r   = int(params.get('max_rows', 0))
        reload  = int(params.get('reload', 0))
        nrows   = max_r if max_r > 0 else None

        key = (path, sep, nrows)
        if key != self._last_key or reload or self._df is None:
            if not os.path.isfile(path):
                send_notification(f"CSV Reader: file not found → {path}", level='error', notif_id=_NOTIF_ID)
                return {}
            try:
                self._df       = pd.read_csv(path, sep=sep, nrows=nrows)
                self._last_key = key
                r, c = self._df.shape
                send_notification(f"CSV Reader: {r} rows × {c} cols loaded", notif_id=_NOTIF_ID)
            except Exception as e:
                send_notification(f"CSV Reader error: {e}", level='error', notif_id=_NOTIF_ID)
                return {}

        w = int(params.get('width',  420))
        h = int(params.get('height', 240))
        preview = _render_df_head(self._df, w, h, title=os.path.basename(path))
        return {
            'table':     self._df,
            'preview':   preview,
            'row_count': float(len(self._df)),
            'col_count': float(len(self._df.columns)),
            'df_meta':   _df_meta(self._df),
        }


# ─── DataFrame Filter ─────────────────────────────────────────────────────────

_OPS        = ['==', '!=', '>', '<', '>=', '<=', 'contains', 'is null', 'is not null']
_OPS_LABELS = ['== (equal)', '!= (different)', '> (greater)', '< (less)', '>= (≥)', '<= (≤)', 'contains (text)', 'is null', 'is not null']


def _apply_op(df, col, op, val):
    s = df[col]
    if op == 'is null':     return df[s.isna()]
    if op == 'is not null': return df[s.notna()]
    if op == 'contains':    return df[s.astype(str).str.contains(val, na=False, regex=False)]
    try:
        num = float(val)
        if op == '==':  return df[s == num]
        if op == '!=':  return df[s != num]
        if op == '>':   return df[s > num]
        if op == '<':   return df[s < num]
        if op == '>=':  return df[s >= num]
        if op == '<=':  return df[s <= num]
    except ValueError:
        sv = s.astype(str)
        if op == '==':  return df[sv == val]
        if op == '!=':  return df[sv != val]
    return df


@vision_node(
    type_id='ml_df_filter',
    label='DF Filter',
    category='DataFrame',
    icon='Filter',
    description="Filter rows of a DataFrame by a column condition. Chain multiple filters for complex queries.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'Filtered DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'df_meta',   'color': 'dict',   'label': 'DF Metadata'},
    ],
    params=[
        {'id': 'enabled',  'label': 'Enable Filter', 'type': 'bool',   'default': True},
        {'id': 'column',   'label': 'Column',        'type': 'string', 'default': ''},
        {'id': 'operator', 'label': 'Operator',      'type': 'enum',   'options': _OPS_LABELS, 'default': 0},
        {'id': 'value',    'label': 'Value',         'type': 'string', 'default': ''},
        {'id': 'dropna',   'label': 'Drop NaN rows', 'type': 'bool',   'default': False},
    ],
    resizable=True,
    min_width=270,
    min_height=180,
)
class MLDfFilterNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        enabled = bool(params.get('enabled', True))
        dropna  = bool(params.get('dropna', False))

        if dropna:
            df = df.dropna()

        if enabled:
            col    = str(params.get('column', '')).strip()
            op_idx = int(params.get('operator', 0))
            op     = _OPS[op_idx]
            val    = str(params.get('value', '')).strip()
            if col and col in df.columns:
                try:
                    df = _apply_op(df, col, op, val)
                except Exception as e:
                    send_notification(f"DF Filter error: {e}", level='error', notif_id=_NOTIF_ID)
            elif col:
                send_notification(f"DF Filter: column '{col}' not found", level='warning', notif_id=_NOTIF_ID)

        w = int(params.get('width',  380))
        h = int(params.get('height', 200))
        preview = _render_df_head(df, w, h, title=f"Filtered — {len(df)} rows")
        return {
            'table':     df,
            'preview':   preview,
            'row_count': float(len(df)),
            'df_meta':   _df_meta(df),
        }


# ─── DataFrame Stats ──────────────────────────────────────────────────────────

_MODES = ['describe()', 'head(10)', 'dtypes + shape', 'value_counts (1 col)']


@vision_node(
    type_id='ml_df_stats',
    label='DF Stats',
    category='DataFrame',
    icon='BarChart2',
    description="Show descriptive statistics of a DataFrame: describe(), head, dtypes, or value counts.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'preview',    'color': 'image', 'label': 'Stats'},
        {'id': 'stats_data', 'color': 'dict',  'label': 'Stats dict'},
    ],
    params=[
        {'id': 'mode',    'label': 'Display Mode',          'type': 'enum',   'options': _MODES, 'default': 0},
        {'id': 'columns', 'label': 'Columns (blank = all)', 'type': 'string', 'default': ''},
        {'id': 'col_vc',  'label': 'Column (value_counts)', 'type': 'string', 'default': ''},
        {'id': 'out_w',   'label': 'Export width px  (0 = taille nœud)', 'type': 'int', 'default': 0, 'min': 0, 'max': 4000},
        {'id': 'out_h',   'label': 'Export height px (0 = taille nœud)', 'type': 'int', 'default': 0, 'min': 0, 'max': 4000},
    ],
    resizable=True,
    min_width=320,
    min_height=220,
)
class MLDfStatsNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        mode     = int(params.get('mode', 0))
        cols_str = str(params.get('columns', '')).strip()
        col_vc   = str(params.get('col_vc', '')).strip()
        out_w    = int(params.get('out_w', 0))
        out_h    = int(params.get('out_h', 0))
        w        = out_w if out_w > 0 else int(params.get('width',  580))
        h        = out_h if out_h > 0 else int(params.get('height', 360))

        if cols_str:
            sel = [c.strip() for c in cols_str.split(',') if c.strip() in df.columns]
            if sel:
                df = df[sel]

        rows_n, cols_n = df.shape
        stats_data: dict = {}
        preview: np.ndarray

        if mode == 0:  # ── describe() ─────────────────────────────────────
            desc = df.describe().round(4)
            num_cols = list(desc.columns)
            stat_rows_idx = list(desc.index)
            col_labels = ['stat'] + [str(c)[:14] for c in num_cols]
            rows_data = [[str(idx)] + [str(desc.loc[idx, c]) for c in num_cols]
                         for idx in stat_rows_idx]
            # Color mean row blue, std orange
            row_colors = []
            for idx in stat_rows_idx:
                if idx == 'mean':
                    row_colors.append(['#93c5fd'] + ['#93c5fd'] * len(num_cols))
                elif idx == 'std':
                    row_colors.append(['#fdba74'] + ['#fdba74'] * len(num_cols))
                else:
                    row_colors.append([None] * (len(num_cols) + 1))

            title = f"describe()  —  {rows_n} rows × {cols_n} cols"
            preview = _table_img(col_labels, rows_data, w, h, title, row_colors)
            stats_data = {
                'mode': 'describe',
                'shape': [rows_n, cols_n],
                'stats': {
                    str(c): {k: float(desc.loc[k, c]) for k in stat_rows_idx
                             if k in desc.index}
                    for c in num_cols
                },
            }

        elif mode == 1:  # ── head(10) ────────────────────────────────────
            sub = df.head(10)
            MAX_C = 8
            visible = list(sub.columns[:MAX_C])
            col_labels = [str(c)[:14] for c in visible]
            rows_data = [[str(sub.iloc[i][c])[:14] for c in visible]
                         for i in range(len(sub))]
            title = f"head(10)  —  {rows_n} rows × {cols_n} cols"
            preview = _table_img(col_labels, rows_data, w, h, title)
            stats_data = {
                'mode': 'head',
                'shape': [rows_n, cols_n],
                'columns': list(df.columns),
            }

        elif mode == 2:  # ── dtypes + shape ──────────────────────────────
            col_labels = ['Column', 'Type', 'Nulls', 'Null %']
            rows_data = []
            col_info = []
            for c in df.columns:
                nulls = int(df[c].isna().sum())
                pct   = round(nulls / rows_n * 100, 1) if rows_n > 0 else 0.0
                rows_data.append([str(c)[:20], str(df[c].dtype), str(nulls), f"{pct}%"])
                col_info.append({'name': str(c), 'dtype': str(df[c].dtype), 'nulls': nulls, 'null_pct': pct})
            # Color null % red when > 0
            row_colors = [
                [None, '#a5b4fc', ('#f87171' if int(r[2]) > 0 else '#6ee7b7'), ('#f87171' if int(r[2]) > 0 else '#6ee7b7')]
                for r in rows_data
            ]
            title = f"dtypes + shape  —  {rows_n} rows × {cols_n} cols"
            preview = _table_img(col_labels, rows_data, w, h, title, row_colors)
            stats_data = {
                'mode': 'dtypes',
                'shape': [rows_n, cols_n],
                'columns': col_info,
            }

        else:  # ── value_counts ─────────────────────────────────────────
            if col_vc and col_vc in df.columns:
                vc     = df[col_vc].value_counts().head(20)
                total  = int(vc.sum())
                col_labels = ['Value', 'Count', '%']
                rows_data  = [[str(v)[:20], str(c), f"{c/total*100:.1f}%"]
                              for v, c in vc.items()]
                # Color count bar using gradient: high → green, low → red
                max_c = vc.max()
                row_colors = [
                    [None, '#93c5fd', '#a5b4fc']
                    for _ in rows_data
                ]
                title = f"value_counts({col_vc})  —  {len(vc)} unique / {total} total"
                preview = _table_img(col_labels, rows_data, w, h, title, row_colors)
                stats_data = {
                    'mode': 'value_counts',
                    'column': col_vc,
                    'total': total,
                    'counts': [{'value': str(v), 'count': int(c), 'pct': round(c/total*100, 1)}
                               for v, c in vc.items()],
                }
            else:
                # Fallback blank
                _, plt = _get_mpl()
                fig, ax = plt.subplots(figsize=(w/100, h/100))
                ax.set_axis_off()
                fig.patch.set_facecolor('#161616')
                ax.text(0.5, 0.5, "Set 'Column (value_counts)' param",
                        transform=ax.transAxes, ha='center', va='center', color='#888')
                preview = _fig_to_bgr(fig)
                plt.close(fig)
                stats_data = {'mode': 'value_counts', 'column': None}

        return {'preview': preview, 'stats_data': stats_data}


# ─── Sklearn Demo Datasets ────────────────────────────────────────────────────

_SK_DATASETS = [
    'iris',
    'wine',
    'breast_cancer',
    'diabetes  (régression)',
    'digits',
    'california_housing  (régression)',
]
_SK_KEYS = ['iris', 'wine', 'breast_cancer', 'diabetes', 'digits', 'california_housing']


@vision_node(
    type_id='ml_sklearn_dataset',
    label='Sklearn Dataset',
    category='DataFrame',
    icon='Database',
    description=(
        "Charge un jeu de données de démonstration scikit-learn. "
        "Colonne cible toujours nommée 'target' (labels texte pour les classifications). "
        "Idéal pour commencer sans fichier CSV."
    ),
    inputs=[],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame complet'},
        {'id': 'preview',   'color': 'image',  'label': 'Info panel'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Lignes'},
        {'id': 'col_count', 'color': 'scalar', 'label': 'Colonnes'},
    ],
    params=[
        {'id': 'dataset', 'label': 'Dataset', 'type': 'enum', 'options': _SK_DATASETS, 'default': 0},
    ],
    resizable=True,
    min_width=260,
    min_height=180,
)
class MLSklearnDatasetNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache: dict = {}   # key → DataFrame

    def process(self, inputs, params):
        if not self.ensure_packages(['sklearn', 'pandas'], pip_names=['scikit-learn', 'pandas'], notif_id=_NOTIF_ID):
            return {}

        ds_idx = int(params.get('dataset', 0))
        key    = _SK_KEYS[ds_idx]
        w      = int(params.get('width',  320))
        h      = int(params.get('height', 200))

        if key not in self._cache:
            try:
                import sklearn.datasets as skd
                loaders = {
                    'iris':               skd.load_iris,
                    'wine':               skd.load_wine,
                    'breast_cancer':      skd.load_breast_cancer,
                    'diabetes':           skd.load_diabetes,
                    'digits':             skd.load_digits,
                    'california_housing': skd.fetch_california_housing,
                }
                bunch = loaders[key](as_frame=True)
                df = bunch.frame.copy()

                # Rename target column to 'target' (already named so, but enforce)
                if 'target' not in df.columns and hasattr(bunch, 'target'):
                    df['target'] = bunch.target.values

                # Decode integer class labels to names for classification datasets
                if hasattr(bunch, 'target_names') and df['target'].dtype.kind in 'iu':
                    df['target'] = df['target'].map(
                        lambda i: str(bunch.target_names[i])
                    )

                self._cache[key] = df
                send_notification(
                    f"sklearn: {key} chargé — {df.shape[0]} rows × {df.shape[1]} cols",
                    notif_id=_NOTIF_ID
                )
            except Exception as e:
                send_notification(f"sklearn dataset error: {e}", level='error', notif_id=_NOTIF_ID)
                return {}

        df = self._cache[key]

        # Info panel
        num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc']
        lines = [
            f"Dataset : {key}",
            f"Shape   : {df.shape[0]} rows × {df.shape[1]} cols",
            f"Target  : target  ({df['target'].nunique() if 'target' in df else '?'} valeurs uniques)",
            f"Features: {len(num_cols)} numériques",
            "",
        ] + [f"  {c}" for c in df.columns[:12]]
        if len(df.columns) > 12:
            lines.append(f"  ... +{len(df.columns)-12} autres")

        preview = _render_text_panel('\n'.join(lines), w, h, title=f"sklearn — {key}")

        return {
            'table':     df,
            'preview':   preview,
            'row_count': float(len(df)),
            'col_count': float(len(df.columns)),
        }
