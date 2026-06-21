"""
DataFrame Plot — generic charting node.

df_plot : one node, many chart types, rendered in the node body + image output.
    Chart types: Line, Bar, Scatter, Histogram, Box, Area, Pie.
    Pick X column + one or more Y columns (comma-separated) and tune the look.
    Renders directly in the node body (base64 `preview`) AND emits a BGR image
    on `main` for wiring into Output Display / export.

Self-contained: matplotlib Agg backend, no cross-plugin imports.
"""
import io
import base64
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'df_plot'

_CMAPS   = ['tab10', 'Set1', 'Set2', 'viridis', 'plasma', 'coolwarm', 'RdYlGn']
_CLABELS = ['Tab10', 'Set1', 'Set2', 'Viridis', 'Plasma', 'Coolwarm', 'RdYlGn']

_CHART_TYPES = ['Line', 'Bar', 'Scatter', 'Histogram', 'Box', 'Area', 'Pie']

_MPL_DARK = {
    'figure.facecolor':  '#161616',
    'axes.facecolor':    '#1e1e1e',
    'axes.edgecolor':    '#555555',
    'axes.labelcolor':   '#cccccc',
    'text.color':        '#cccccc',
    'xtick.color':       '#aaaaaa',
    'ytick.color':       '#aaaaaa',
    'grid.color':        '#333333',
    'grid.linestyle':    '--',
    'grid.linewidth':    0.5,
    'legend.facecolor':  '#2a2a2a',
    'legend.edgecolor':  '#555555',
}


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


def _bgr_to_b64(img: np.ndarray) -> str:
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf).decode('utf-8') if ok else ''


def _out_size(params, default_w=560, default_h=400, inputs=None):
    dpi   = max(72, int(params.get('out_dpi', 100)))
    out_w = int(params.get('out_w', 0))
    out_h = int(params.get('out_h', 0))
    if out_w > 0 and out_h > 0:
        return out_w / dpi, out_h / dpi, dpi
    s    = inputs.get('img_size') if inputs else None
    ui_w = int(s[0]) if isinstance(s, (list, tuple)) and len(s) >= 2 else default_w
    ui_h = int(s[1]) if isinstance(s, (list, tuple)) and len(s) >= 2 else default_h
    return ui_w / dpi, ui_h / dpi, dpi


def _split_cols(s):
    return [c.strip() for c in str(s or '').split(',') if c.strip()]


def _numeric_cols(df):
    return [c for c in df.columns if df[c].dtype.kind in 'biufc']


def _resolve_y_cols(df, y_str):
    """Return requested numeric Y columns, or all numeric if blank/invalid."""
    num = _numeric_cols(df)
    req = [c for c in _split_cols(y_str) if c in df.columns and df[c].dtype.kind in 'biufc']
    return req if req else num


def _as_columns(v):
    """Coerce a 'list' input into a list of 1D float arrays (one per series).

    Accepts ndarray (1D or 2D), pandas Series/DataFrame, list of numbers, or
    list of lists. Returns [] if it cannot be made numeric.
    """
    if v is None:
        return []
    # pandas Series / DataFrame
    if hasattr(v, 'values') and hasattr(v, 'ndim'):
        v = v.values
    arr = np.asarray(v, dtype=object)
    try:
        arr = arr.astype(float)
    except (ValueError, TypeError):
        return []
    if arr.ndim == 1:
        return [arr]
    if arr.ndim == 2:
        # treat the smaller axis as the number of series
        return [arr[:, j] for j in range(arr.shape[1])] if arr.shape[0] >= arr.shape[1] else [arr[i] for i in range(arr.shape[0])]
    return []


def _df_from_xy(x_in, y_in):
    """Build a DataFrame + (x_col, y_cols) from raw x/y list inputs. y required."""
    import pandas as pd
    y_series = _as_columns(y_in)
    if not y_series:
        return None, None, None
    n = min(len(s) for s in y_series)
    y_series = [s[:n] for s in y_series]
    data, y_cols = {}, []
    for i, s in enumerate(y_series):
        col = 'y' if len(y_series) == 1 else f'y{i + 1}'
        data[col] = s
        y_cols.append(col)
    x_cols = _as_columns(x_in)
    x_col = None
    if x_cols:
        data['x'] = x_cols[0][:n]
        x_col = 'x'
    return pd.DataFrame(data), x_col, y_cols


@vision_node(
    type_id='df_plot',
    label='DataFrame Plot',
    category='DataFrame',
    icon='ChartLine',
    description=(
        "Generic DataFrame chart. One node, many chart types (line, bar, scatter, "
        "histogram, box, area, pie) with styling options. Renders in the node body "
        "and outputs an image. Either connect a DataFrame + pick X/Y column names, or "
        "wire raw X/Y arrays directly (e.g. CSV Reader columns). X/Y inputs win over the table."
    ),
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame'},
        {'id': 'x',        'color': 'list', 'label': 'X values'},
        {'id': 'y',        'color': 'list', 'label': 'Y values'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'main',    'color': 'image', 'label': 'Plot'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'Columns'},
    ],
    params=[
        {'id': 'chart_type', 'label': 'Chart type', 'type': 'enum', 'options': _CHART_TYPES, 'default': 0},
        {'id': 'x_col',      'label': 'X column (category / axis / labels)', 'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': 'y_cols',     'label': 'Y columns (comma-separated)',         'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': 'hue_col',    'label': 'Color by (hue)', 'type': 'string', 'default': '', 'hints': 'df_columns',
         'show_if': {'param': 'chart_type', 'value': 2}},
        {'id': 'bins',       'label': 'Bins', 'type': 'int', 'default': 30, 'min': 5, 'max': 200,
         'show_if': {'param': 'chart_type', 'value': 3}},
        {'id': 'horizontal', 'label': 'Horizontal bars', 'type': 'bool', 'default': False,
         'show_if': {'param': 'chart_type', 'value': 1}},
        {'id': 'stacked',    'label': 'Stacked', 'type': 'bool', 'default': False,
         'show_if': {'param': 'chart_type', 'value': 1}},
        {'id': 'sort_x',     'label': 'Sort by X', 'type': 'bool', 'default': False},
        {'id': 'max_points', 'label': 'Max points (0=all)', 'type': 'int', 'default': 5000, 'min': 0, 'max': 100000},
        {'id': 'colormap',   'label': 'Colormap', 'type': 'enum', 'options': _CLABELS, 'default': 0},
        {'id': 'alpha',      'label': 'Opacity', 'type': 'float', 'default': 0.85, 'min': 0.1, 'max': 1.0, 'step': 0.05},
        {'id': 'marker_size','label': 'Marker / line size', 'type': 'int', 'default': 40, 'min': 1, 'max': 250},
        {'id': 'title',      'label': 'Title', 'type': 'string', 'default': ''},
        {'id': 'grid',       'label': 'Grid', 'type': 'bool', 'default': True},
        {'id': 'legend',     'label': 'Legend', 'type': 'bool', 'default': True},
        {'id': 'x_log',      'label': 'Log X', 'type': 'bool', 'default': False},
        {'id': 'y_log',      'label': 'Log Y', 'type': 'bool', 'default': False},
        {'id': 'out_dpi',    'label': 'Export DPI (100=screen, 300=pub)', 'type': 'int', 'default': 100, 'min': 72, 'max': 600},
        {'id': 'out_w',      'label': 'Export width px (0 = node size)',  'type': 'int', 'default': 0, 'min': 0, 'max': 5000},
        {'id': 'out_h',      'label': 'Export height px (0 = node size)', 'type': 'int', 'default': 0, 'min': 0, 'max': 5000},
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class DataFramePlotNode(NodeProcessor):
    def process(self, inputs, params):
        if not self.ensure_packages(['matplotlib', 'pandas'], notif_id=_NOTIF_ID):
            return {}

        # Direct mode: raw x/y arrays wired in (e.g. columns from CSV Reader) take
        # precedence over a connected DataFrame + column-name params.
        xy_df, xy_x, xy_y = _df_from_xy(inputs.get('x'), inputs.get('y'))
        df = xy_df if xy_df is not None else inputs.get('table')
        if df is None or len(df) == 0:
            return {}

        mpl, plt = _get_mpl()

        chart   = _CHART_TYPES[int(params.get('chart_type', 0))]
        x_col   = str(params.get('x_col', '')).strip()
        hue_col = str(params.get('hue_col', '')).strip()
        bins    = int(params.get('bins', 30))
        horiz   = bool(params.get('horizontal', False))
        stacked = bool(params.get('stacked', False))
        sort_x  = bool(params.get('sort_x', False))
        max_pts = int(params.get('max_points', 5000))
        cmap    = _CMAPS[int(params.get('colormap', 0))]
        alpha   = float(params.get('alpha', 0.85))
        msize   = int(params.get('marker_size', 40))
        title   = str(params.get('title', '')).strip()
        grid    = bool(params.get('grid', True))
        legend  = bool(params.get('legend', True))
        x_log   = bool(params.get('x_log', False))
        y_log   = bool(params.get('y_log', False))
        fig_w, fig_h, dpi = _out_size(params, inputs=inputs)

        df_meta = {
            'shape': list(df.shape),
            'columns': [str(c) for c in df.columns],
            'numeric': _numeric_cols(df),
            'chart': chart,
        }

        # Direct x/y inputs override the string column params.
        if xy_df is not None:
            x_col = xy_x or ''

        work = df
        if sort_x and x_col and x_col in df.columns:
            work = df.sort_values(x_col)
        if max_pts and len(work) > max_pts:
            work = work.iloc[:: max(1, len(work) // max_pts)]

        y_cols = xy_y if xy_df is not None else _resolve_y_cols(work, params.get('y_cols', ''))
        cmap_obj = mpl.colormaps[cmap]

        try:
            with plt.rc_context(_MPL_DARK):
                fig, ax = plt.subplots(figsize=(fig_w, fig_h))
                x = work[x_col] if (x_col and x_col in work.columns) else None

                if chart == 'Scatter':
                    self._scatter(ax, work, x_col, y_cols, hue_col, cmap, cmap_obj, alpha, msize)
                elif chart == 'Histogram':
                    self._histogram(ax, work, y_cols, bins, alpha, cmap_obj)
                elif chart == 'Box':
                    self._box(ax, work, y_cols, cmap_obj)
                elif chart == 'Pie':
                    self._pie(ax, work, x_col, y_cols, cmap_obj)
                    legend = False
                elif chart == 'Bar':
                    self._bar(ax, work, x, y_cols, horiz, stacked, alpha, cmap_obj)
                else:  # Line / Area
                    self._line(ax, work, x, y_cols, alpha, msize, cmap_obj, fill=(chart == 'Area'))

                if chart not in ('Pie',):
                    if x_log:
                        ax.set_xscale('log')
                    if y_log:
                        ax.set_yscale('log')
                    ax.grid(grid)
                    if x_col and chart not in ('Histogram', 'Box'):
                        ax.set_xlabel(x_col)
                    # Line / Area / Bar manage multi-series via labelled artists; others
                    # (Scatter, Histogram, Box) add their own legend inside the renderer.
                    if legend and chart in ('Line', 'Area', 'Bar') and len(y_cols) > 1:
                        ax.legend(fontsize=7, labelcolor='#cccccc', framealpha=0.4, loc='best')

                ax.set_title(title or f'{chart} chart', fontsize=10)
                fig.tight_layout()
                img = _fig_to_bgr(fig, dpi)
                plt.close(fig)
        except Exception as e:
            send_notification(f"DataFrame Plot: {e}", level='warning', notif_id=_NOTIF_ID)
            return {'df_meta': df_meta}

        return {'main': img, 'preview': _bgr_to_b64(img), 'df_meta': df_meta}

    # ── chart renderers ────────────────────────────────────────────────────────
    def _colors(self, cmap_obj, n):
        return cmap_obj(np.linspace(0, 1, max(1, n)))

    def _line(self, ax, work, x, y_cols, alpha, msize, cmap_obj, fill=False):
        colors = self._colors(cmap_obj, len(y_cols))
        xs = x.values if x is not None else np.arange(len(work))
        lw = max(1.0, msize / 20.0)
        for col, color in zip(y_cols, colors):
            ax.plot(xs, work[col].values, color=color, alpha=alpha, linewidth=lw, label=str(col))
            if fill:
                ax.fill_between(xs, work[col].values, alpha=alpha * 0.35, color=color)

    def _bar(self, ax, work, x, y_cols, horiz, stacked, alpha, cmap_obj):
        colors = self._colors(cmap_obj, len(y_cols))
        labels = [str(v) for v in (x.values if x is not None else np.arange(len(work)))]
        idx = np.arange(len(work))
        n = len(y_cols)
        bottom = np.zeros(len(work))
        width = 0.8 if stacked else 0.8 / max(1, n)
        for i, (col, color) in enumerate(zip(y_cols, colors)):
            vals = work[col].values.astype(float)
            if stacked:
                if horiz:
                    ax.barh(idx, vals, left=bottom, color=color, alpha=alpha, label=str(col))
                else:
                    ax.bar(idx, vals, bottom=bottom, color=color, alpha=alpha, label=str(col))
                bottom = bottom + vals
            else:
                off = (i - (n - 1) / 2) * width
                if horiz:
                    ax.barh(idx + off, vals, height=width, color=color, alpha=alpha, label=str(col))
                else:
                    ax.bar(idx + off, vals, width=width, color=color, alpha=alpha, label=str(col))
        if horiz:
            ax.set_yticks(idx)
            ax.set_yticklabels(labels, fontsize=7)
        else:
            ax.set_xticks(idx)
            ax.set_xticklabels(labels, fontsize=7, rotation=45, ha='right')

    def _scatter(self, ax, work, x_col, y_cols, hue_col, cmap, cmap_obj, alpha, msize):
        if not x_col or x_col not in work.columns or not y_cols:
            raise ValueError('Scatter needs X column + ≥1 Y column')
        y_col = y_cols[0]
        if hue_col and hue_col in work.columns:
            classes = list(work[hue_col].unique())[:20]
            colors = self._colors(cmap_obj, len(classes))
            for cls, color in zip(classes, colors):
                m = work[hue_col] == cls
                ax.scatter(work[x_col][m], work[y_col][m], color=color, alpha=alpha,
                           s=msize, edgecolors='none', label=str(cls))
            ax.legend(fontsize=7, labelcolor='#cccccc', framealpha=0.4, title=hue_col, title_fontsize=7)
        else:
            ax.scatter(work[x_col], work[y_col], c=np.arange(len(work)), cmap=cmap,
                       alpha=alpha, s=msize, edgecolors='none')
        ax.set_ylabel(y_col)

    def _histogram(self, ax, work, y_cols, bins, alpha, cmap_obj):
        colors = self._colors(cmap_obj, len(y_cols))
        for col, color in zip(y_cols, colors):
            ax.hist(work[col].dropna().values, bins=bins, alpha=alpha, color=color,
                    edgecolor='none', label=str(col))
        ax.set_ylabel('Count')
        if len(y_cols) > 1:
            ax.legend(fontsize=7, labelcolor='#cccccc', framealpha=0.4)

    def _box(self, ax, work, y_cols, cmap_obj):
        data = [work[c].dropna().values for c in y_cols]
        bp = ax.boxplot(data, labels=[str(c) for c in y_cols], patch_artist=True)
        colors = self._colors(cmap_obj, len(y_cols))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        for med in bp['medians']:
            med.set_color('#ffffff')

    def _pie(self, ax, work, x_col, y_cols, cmap_obj):
        if not y_cols:
            raise ValueError('Pie needs a Y column')
        vals = work[y_cols[0]].values.astype(float)
        vals = np.abs(vals)
        labels = [str(v) for v in work[x_col].values] if (x_col and x_col in work.columns) else None
        colors = self._colors(cmap_obj, len(vals))
        ax.pie(vals, labels=labels, colors=colors, autopct='%1.1f%%',
               textprops={'fontsize': 7, 'color': '#dddddd'})
        ax.set_aspect('equal')
