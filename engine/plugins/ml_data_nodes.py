"""
ML Training — Data Nodes (CSV Reader, DataFrame Filter, DataFrame Stats).
Designed for VNStudio ML formation: no realtime dependencies, static graph.
DataFrame objects travel between nodes as native Python objects in-process.
Handle color: 'data' (orange, already defined in HANDLE_COLORS).
"""
import os
import cv2
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_data'

# ─── Shared render helpers ────────────────────────────────────────────────────

def _render_text_panel(text: str, w: int, h: int, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
    font    = cv2.FONT_HERSHEY_SIMPLEX
    scale   = 0.36
    line_h  = 15
    x0, y0 = 8, 44
    max_lines = (h - y0) // line_h
    for i, line in enumerate(text.split('\n')[:max_lines]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, line[:100], (x0, y0 + i * line_h), font, scale, color, 1, cv2.LINE_AA)
    return img


def _render_df_head(df, w: int, h: int, title: str = '') -> np.ndarray:
    """Render DataFrame.head() as a monospaced table image."""
    MAX_R, MAX_C = 8, 7
    sub = df.iloc[:MAX_R, :MAX_C]
    col_w = 13
    header = ' | '.join(str(c)[:col_w].ljust(col_w) for c in sub.columns)
    sep    = '-' * len(header)
    rows   = []
    for _, row in sub.iterrows():
        cells = (str(v)[:col_w].ljust(col_w) for v in row)
        rows.append(' | '.join(cells))
    text = '\n'.join([header, sep] + rows)
    return _render_text_panel(text, w, h, title=title)


# ─── CSV Reader ───────────────────────────────────────────────────────────────

_SEPARATORS = [',', ';', '\t', '|']
_SEP_LABELS  = ['Comma (,)', 'Semicolon (;)', 'Tab (\\t)', 'Pipe (|)']

@vision_node(
    type_id='ml_csv_reader',
    label='CSV Reader',
    category='ML / Data',
    icon='FileText',
    description="Load a CSV file as a DataFrame. Connect to DF Filter or DF Stats.",
    inputs=[],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
        {'id': 'col_count', 'color': 'scalar', 'label': 'Cols'},
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
    category='ML / Data',
    icon='Filter',
    description="Filter rows of a DataFrame by a column condition. Chain multiple filters for complex queries.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',     'color': 'data',   'label': 'Filtered DataFrame'},
        {'id': 'preview',   'color': 'image',  'label': 'Preview'},
        {'id': 'row_count', 'color': 'scalar', 'label': 'Rows'},
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
        }


# ─── DataFrame Stats ──────────────────────────────────────────────────────────

_MODES = ['describe()', 'head(10)', 'dtypes + shape', 'value_counts (1 col)']


@vision_node(
    type_id='ml_df_stats',
    label='DF Stats',
    category='ML / Data',
    icon='BarChart2',
    description="Show descriptive statistics of a DataFrame: describe(), head, dtypes, or value counts.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[{'id': 'preview', 'color': 'image', 'label': 'Stats'}],
    params=[
        {'id': 'mode',    'label': 'Display Mode',          'type': 'enum',   'options': _MODES, 'default': 0},
        {'id': 'columns', 'label': 'Columns (blank = all)', 'type': 'string', 'default': ''},
        {'id': 'col_vc',  'label': 'Column (value_counts)', 'type': 'string', 'default': ''},
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
        w        = int(params.get('width',  560))
        h        = int(params.get('height', 340))

        # Column subset
        if cols_str:
            sel = [c.strip() for c in cols_str.split(',') if c.strip() in df.columns]
            if sel:
                df = df[sel]

        if mode == 0:
            text  = df.describe().round(3).to_string()
            title = f"describe()  —  {df.shape[0]} rows × {df.shape[1]} cols"
        elif mode == 1:
            text  = df.head(10).to_string()
            title = f"head(10)  —  {df.shape[0]} rows × {df.shape[1]} cols"
        elif mode == 2:
            lines = [f"Shape : {df.shape[0]} rows × {df.shape[1]} cols", ""]
            for c in df.columns:
                null_n = int(df[c].isna().sum())
                lines.append(f"  {str(c):<22} {str(df[c].dtype):<12}  nulls={null_n}")
            text  = '\n'.join(lines)
            title = "dtypes + shape"
        else:  # value_counts
            if col_vc and col_vc in df.columns:
                vc   = df[col_vc].value_counts()
                text = vc.head(20).to_string()
                title = f"value_counts({col_vc})"
            else:
                text  = "Set 'Column (value_counts)' to a valid column name."
                title = "value_counts"

        return {'preview': _render_text_panel(text, w, h, title=title)}


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
    category='ML / Data',
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
        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
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
