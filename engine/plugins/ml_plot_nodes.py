"""
ML Training — Plot Nodes (Scatter Plot, Histogram, Correlation Heatmap).
Uses matplotlib with Agg backend (no display needed, server-side rendering).
Handle color: 'data' (orange) for DataFrame inputs.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_plot'

_CMAPS  = ['tab10', 'Set1', 'Set2', 'viridis', 'plasma', 'coolwarm', 'RdYlGn']
_CLABELS = ['Tab10', 'Set1', 'Set2', 'Viridis', 'Plasma', 'Coolwarm', 'RdYlGn']

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


_EXPORT_PARAMS = [
    {'id': 'out_dpi', 'label': 'Export DPI (100=screen, 300=pub)', 'type': 'int', 'default': 100, 'min': 72, 'max': 600},
    {'id': 'out_w',   'label': 'Export width px (0 = node size)',    'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
    {'id': 'out_h',   'label': 'Export height px (0 = node size)',    'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
]


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


# Above this many distinct values a numeric hue column is treated as continuous
# (colorbar) instead of one scatter call + legend entry per class.
_MAX_HUE_CLASSES = 20


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


def _is_continuous(series) -> bool:
    """True for numeric hue columns with too many distinct values to enumerate."""
    return series.dtype.kind in 'ifc' and series.nunique(dropna=True) > _MAX_HUE_CLASSES


def _class_colors(plt, cmap_name: str, n: int) -> list:
    """n distinct colors from a colormap.

    Qualitative maps (tab10, Set1, Set2) are indexed slot by slot so neighbouring
    classes stay far apart; continuous maps are sampled evenly.
    """
    cmap = plt.get_cmap(cmap_name)
    if getattr(cmap, 'colors', None) is not None:
        return [cmap(i % cmap.N) for i in range(n)]
    return [cmap(t) for t in np.linspace(0.0, 1.0, max(n, 2))][:n]


def _out_size(params, default_w=540, default_h=400, inputs=None):
    """Return (fig_w_inches, fig_h_inches, dpi) for matplotlib subplots."""
    dpi   = max(72, int(params.get('out_dpi', 100)))
    out_w = int(params.get('out_w', 0))
    out_h = int(params.get('out_h', 0))
    if out_w > 0 and out_h > 0:
        return out_w / dpi, out_h / dpi, dpi
    s    = inputs.get('img_size') if inputs else None
    ui_w = int(s[0]) if isinstance(s, (list, tuple)) and len(s) >= 2 else int(params.get('width',  default_w))
    ui_h = int(s[1]) if isinstance(s, (list, tuple)) and len(s) >= 2 else int(params.get('height', default_h))
    return ui_w / dpi, ui_h / dpi, dpi


def _get_mpl():
    """Import matplotlib with Agg backend, return (matplotlib, pyplot) or raise."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


# ─── Scatter Plot ─────────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_scatter_plot',
    label='Scatter Plot',
    category='DataFrame',
    icon='Crosshair',
    description="2D scatter plot from a DataFrame. Set X/Y columns, optionally color by a class column (hue). Ideal for exploring feature relationships and class separability.",
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'main',    'color': 'image', 'label': 'Plot'},
        {'id': 'df_meta', 'color': 'dict',  'label': 'Columns'},
    ],
    params=[
        {'id': 'x_col',      'label': 'X Column',           'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': 'y_col',      'label': 'Y Column',           'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': 'hue_col',    'label': 'Color by (hue)',     'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': '_sec_appearance', 'label': 'Appearance', 'type': 'section'},
        {'id': 'colormap',   'label': 'Colormap',           'type': 'enum',   'options': _CLABELS, 'default': 0},
        {'id': 'alpha',      'label': 'Opacity',            'type': 'float',  'default': 0.75, 'min': 0.1, 'max': 1.0, 'step': 0.05},
        {'id': 'dot_size',   'label': 'Dot Size',           'type': 'int',    'default': 40,   'min': 5,   'max': 250},
        {'id': '_sec_options', 'label': 'Options', 'type': 'section'},
        {'id': 'regression', 'label': 'Regression Line',    'type': 'bool',   'default': False},
        {'id': 'grid',       'label': 'Grid',               'type': 'bool',   'default': True},
        {'id': 'max_points', 'label': 'Max Points (0=all)', 'type': 'int',    'default': 2000, 'min': 0, 'max': 50000},
        {'id': '_sec_export', 'label': 'Export', 'type': 'section'},
        *_EXPORT_PARAMS,
    ],
    resizable=True,
    min_width=300,
    min_height=240,
)
class MLScatterPlotNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        # Emitted even when the plot cannot be drawn: the inspector uses it to
        # offer the column-name shortcuts for X / Y / hue.
        meta = {
            'shape':   list(df.shape),
            'columns': [str(c) for c in df.columns],
        }

        if not self.ensure_packages(['matplotlib'], notif_id=_NOTIF_ID):
            return {'df_meta': meta}

        _, plt = _get_mpl()

        x_col    = str(params.get('x_col', '')).strip()
        y_col    = str(params.get('y_col', '')).strip()
        hue_col  = str(params.get('hue_col', '')).strip()
        cmap_idx = int(params.get('colormap', 0))
        cmap     = _CMAPS[cmap_idx]
        alpha    = float(params.get('alpha', 0.75))
        s        = int(params.get('dot_size', 40))
        regress  = bool(params.get('regression', False))
        grid     = bool(params.get('grid', True))
        max_pts  = int(params.get('max_points', 2000))
        fig_w, fig_h, dpi = _out_size(params, 540, 400, inputs=inputs)

        cols = list(df.columns)
        num_cols = [c for c in cols if df[c].dtype.kind in 'biufc']  # numeric

        x_col = _resolve_col(df, x_col)
        y_col = _resolve_col(df, y_col)

        # Auto-pick columns if not set
        if x_col is None:
            x_col = num_cols[0] if num_cols else (cols[0] if cols else None)
        if y_col is None:
            y_col = num_cols[1] if len(num_cols) > 1 else x_col

        if x_col is None or y_col is None:
            send_notification("Scatter Plot: no numeric columns found", level='warning', notif_id=_NOTIF_ID)
            return {'df_meta': meta}

        hue_req = hue_col
        hue_col = _resolve_col(df, hue_col)
        if hue_req and hue_col is None:
            send_notification(f"Scatter Plot: hue column '{hue_req}' not in the DataFrame",
                              level='warning', notif_id=_NOTIF_ID)

        # Subsample for performance
        plot_df = df
        if max_pts > 0 and len(df) > max_pts:
            plot_df = df.sample(max_pts, random_state=42)

        with plt.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(fig_w, fig_h))

            x_data = plot_df[x_col]
            y_data = plot_df[y_col]

            hue_data = plot_df[hue_col] if hue_col else None
            legend_title = None

            if hue_data is not None and _is_continuous(hue_data):
                # Many distinct numeric values: colormap + colorbar, one class per
                # value would drop most of the points and blow up the legend.
                sc = ax.scatter(x_data, y_data, alpha=alpha, s=s,
                                c=hue_data.astype(float), cmap=cmap, edgecolors='none')
                cbar = fig.colorbar(sc, ax=ax, pad=0.01, fraction=0.03)
                cbar.set_label(hue_col, fontsize=8)
            elif hue_data is not None:
                classes = list(hue_data.dropna().unique())
                colors = _class_colors(plt, cmap, len(classes))
                for cls, color in zip(classes, colors):
                    mask = hue_data == cls
                    ax.scatter(x_data[mask], y_data[mask],
                               label=str(cls), color=color, alpha=alpha, s=s, edgecolors='none')
                # Every class is drawn; only the legend is capped.
                if len(classes) <= _MAX_HUE_CLASSES:
                    legend_title = hue_col
                else:
                    send_notification(
                        f"Scatter Plot: '{hue_col}' has {len(classes)} classes — legend hidden",
                        level='info', notif_id=_NOTIF_ID)
            else:
                sc = ax.scatter(x_data, y_data, alpha=alpha, s=s,
                                c=np.arange(len(x_data)), cmap=cmap, edgecolors='none')
                fig.colorbar(sc, ax=ax, pad=0.01, fraction=0.03)

            if regress:
                try:
                    valid = plot_df[[x_col, y_col]].dropna()
                    xv = valid[x_col].astype(float).values
                    yv = valid[y_col].astype(float).values
                    m, b = np.polyfit(xv, yv, 1)
                    xline = np.linspace(xv.min(), xv.max(), 200)
                    ax.plot(xline, m * xline + b, '--', color='#ff7f50',
                            linewidth=1.5, label=f'y = {m:.2f}x + {b:.2f}')
                except Exception as e:
                    send_notification(f"Scatter: regression failed ({e})", level='warning', notif_id=_NOTIF_ID)

            # One legend call for hue classes + regression line together.
            if ax.get_legend_handles_labels()[0]:
                ax.legend(fontsize=8, labelcolor='#cccccc', loc='best',
                          title=legend_title, title_fontsize=8)

            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            title = f"{x_col}  vs  {y_col}"
            if max_pts > 0 and len(df) > max_pts:
                title += f"  (sample {max_pts}/{len(df)})"
            ax.set_title(title, fontsize=10)
            if grid:
                ax.grid(True)

            fig.tight_layout()
            img = _fig_to_bgr(fig, dpi)
            plt.close(fig)

        return {'main': img, 'df_meta': meta}


# ─── Histogram (DataFrame column) ─────────────────────────────────────────────

@vision_node(
    type_id='ml_histogram',
    label='ML Histogram',
    category='DataFrame',
    icon='BarChart2',
    description="Distribution histogram of a DataFrame column. Optional KDE overlay and per-class breakdown (hue).",
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[{'id': 'main', 'color': 'image', 'label': 'Plot'}],
    params=[
        {'id': 'column',   'label': 'Column',          'type': 'string', 'default': ''},
        {'id': 'hue_col',  'label': 'Split by (hue)',  'type': 'string', 'default': ''},
        {'id': 'bins',     'label': 'Bins',             'type': 'int',    'default': 30,  'min': 5, 'max': 200},
        {'id': '_sec_hist_options', 'label': 'Options', 'type': 'section'},
        {'id': 'kde',      'label': 'KDE overlay',      'type': 'bool',   'default': True},
        {'id': 'density',  'label': 'Normalize (density)', 'type': 'bool', 'default': False},
        {'id': 'colormap', 'label': 'Colormap',         'type': 'enum',   'options': _CLABELS, 'default': 0},
        {'id': 'grid',     'label': 'Grid',             'type': 'bool',   'default': True},
        {'id': '_sec_hist_export', 'label': 'Export', 'type': 'section'},
        *_EXPORT_PARAMS,
    ],
    resizable=True,
    min_width=300,
    min_height=240,
)
class MLHistogramNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        if not self.ensure_packages(['matplotlib'], notif_id=_NOTIF_ID):
            return {}

        _, plt = _get_mpl()

        col     = str(params.get('column', '')).strip()
        hue_col = str(params.get('hue_col', '')).strip()
        bins    = int(params.get('bins', 30))
        kde     = bool(params.get('kde', True))
        density = bool(params.get('density', False))
        cmap    = _CMAPS[int(params.get('colormap', 0))]
        grid    = bool(params.get('grid', True))
        fig_w, fig_h, dpi = _out_size(params, 540, 380, inputs=inputs)

        num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc']
        if not col or col not in df.columns:
            col = num_cols[0] if num_cols else None
        if col is None:
            send_notification("ML Histogram: no numeric column found", level='warning', notif_id=_NOTIF_ID)
            return {}

        with plt.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(fig_w, fig_h))

            if hue_col and hue_col in df.columns:
                classes = df[hue_col].unique()[:10]
                colors  = plt.cm.get_cmap(cmap)(np.linspace(0, 1, len(classes)))
                for cls, color in zip(classes, colors):
                    data = df[df[hue_col] == cls][col].dropna()
                    ax.hist(data, bins=bins, alpha=0.55, color=color,
                            label=str(cls), density=density, edgecolor='none')
                    if kde and len(data) > 2:
                        from scipy.stats import gaussian_kde
                        xs = np.linspace(data.min(), data.max(), 300)
                        kde_fn = gaussian_kde(data)
                        scale = 1.0 if density else len(data) * (data.max() - data.min()) / bins
                        ax.plot(xs, kde_fn(xs) * scale, color=color, linewidth=1.5)
                ax.legend(fontsize=8, labelcolor='#cccccc', title=hue_col, title_fontsize=8)
            else:
                data = df[col].dropna()
                ax.hist(data, bins=bins, alpha=0.75, color='#3b82f6',
                        density=density, edgecolor='none', label=col)
                if kde and len(data) > 2:
                    if not self.ensure_packages(['scipy'], notif_id=_NOTIF_ID):
                        pass
                    else:
                        from scipy.stats import gaussian_kde
                        xs = np.linspace(data.min(), data.max(), 300)
                        kde_fn = gaussian_kde(data)
                        scale = 1.0 if density else len(data) * (data.max() - data.min()) / bins
                        ax.plot(xs, kde_fn(xs) * scale, color='#f97316', linewidth=2, label='KDE')
                        ax.legend(fontsize=8, labelcolor='#cccccc')

            ax.set_xlabel(col)
            ax.set_ylabel('Density' if density else 'Count')
            ax.set_title(f"Distribution — {col}  ({len(df[col].dropna())} values)", fontsize=10)
            if grid:
                ax.grid(True, axis='y')
            fig.tight_layout()
            img = _fig_to_bgr(fig, dpi)
            plt.close(fig)

        return {'main': img}


# ─── Correlation Heatmap ───────────────────────────────────────────────────────

@vision_node(
    type_id='ml_corr_heatmap',
    label='Correlation Heatmap',
    category='DataFrame',
    icon='Grid',
    description="Pearson correlation matrix of numeric DataFrame columns. Essential for feature selection.",
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[{'id': 'main', 'color': 'image', 'label': 'Heatmap'}],
    params=[
        {'id': 'columns',  'label': 'Columns (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'method',   'label': 'Method',   'type': 'enum', 'options': ['pearson', 'spearman', 'kendall'], 'default': 0},
        {'id': 'annot',    'label': 'Show values', 'type': 'bool', 'default': True},
        {'id': 'colormap', 'label': 'Colormap',   'type': 'enum', 'options': ['coolwarm', 'RdYlGn', 'viridis', 'plasma'], 'default': 0},
        {'id': '_sec_heatmap_export', 'label': 'Export', 'type': 'section'},
        *_EXPORT_PARAMS,
    ],
    resizable=True,
    min_width=300,
    min_height=280,
)
class MLCorrHeatmapNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        if not self.ensure_packages(['matplotlib'], notif_id=_NOTIF_ID):
            return {}

        _, plt = _get_mpl()

        cols_str = str(params.get('columns', '')).strip()
        methods  = ['pearson', 'spearman', 'kendall']
        method   = methods[int(params.get('method', 0))]
        annot    = bool(params.get('annot', True))
        cmaps    = ['coolwarm', 'RdYlGn', 'viridis', 'plasma']
        cmap     = cmaps[int(params.get('colormap', 0))]
        fig_w, fig_h, dpi = _out_size(params, 520, 480, inputs=inputs)

        num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc']
        if cols_str:
            sel = [c.strip() for c in cols_str.split(',') if c.strip() in num_cols]
            if sel:
                num_cols = sel

        if len(num_cols) < 2:
            send_notification("Corr Heatmap: need ≥ 2 numeric columns", level='warning', notif_id=_NOTIF_ID)
            return {}

        corr = df[num_cols].corr(method=method)
        n    = len(num_cols)

        with plt.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(fig_w, fig_h))
            im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect='auto')
            fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)

            ax.set_xticks(range(n))
            ax.set_yticks(range(n))
            ax.set_xticklabels(num_cols, rotation=45, ha='right', fontsize=8)
            ax.set_yticklabels(num_cols, fontsize=8)

            if annot:
                for i in range(n):
                    for j in range(n):
                        val = corr.values[i, j]
                        color = 'white' if abs(val) > 0.6 else '#aaaaaa'
                        ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                                fontsize=7, color=color)

            ax.set_title(f"Correlation ({method})  —  {n} features", fontsize=10)
            fig.tight_layout()
            img = _fig_to_bgr(fig, dpi)
            plt.close(fig)

        return {'main': img}
