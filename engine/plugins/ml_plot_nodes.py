"""
ML Training — Plot Nodes (Scatter Plot).
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


def _fig_to_bgr(fig) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


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
    category='ML / Plot',
    icon='Crosshair',
    description="2D scatter plot from a DataFrame. Set X/Y columns, optionally color by a class column (hue). Ideal for exploring feature relationships and class separability.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[{'id': 'main', 'color': 'image', 'label': 'Plot'}],
    params=[
        {'id': 'x_col',      'label': 'X Column',           'type': 'string', 'default': ''},
        {'id': 'y_col',      'label': 'Y Column',           'type': 'string', 'default': ''},
        {'id': 'hue_col',    'label': 'Color by (hue)',     'type': 'string', 'default': ''},
        {'id': 'colormap',   'label': 'Colormap',           'type': 'enum',   'options': _CLABELS, 'default': 0},
        {'id': 'alpha',      'label': 'Opacity',            'type': 'float',  'default': 0.75, 'min': 0.1, 'max': 1.0, 'step': 0.05},
        {'id': 'dot_size',   'label': 'Dot Size',           'type': 'int',    'default': 40,   'min': 5,   'max': 250},
        {'id': 'regression', 'label': 'Regression Line',    'type': 'bool',   'default': False},
        {'id': 'grid',       'label': 'Grid',               'type': 'bool',   'default': True},
        {'id': 'max_points', 'label': 'Max Points (0=all)', 'type': 'int',    'default': 2000, 'min': 0, 'max': 50000},
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

        if not self.ensure_packages(['matplotlib'], notif_id=_NOTIF_ID):
            return {}

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
        w_px     = int(params.get('width',  540))
        h_px     = int(params.get('height', 400))

        cols = list(df.columns)
        num_cols = [c for c in cols if df[c].dtype.kind in 'biufc']  # numeric

        # Auto-pick columns if not set
        if not x_col or x_col not in cols:
            x_col = num_cols[0] if num_cols else (cols[0] if cols else None)
        if not y_col or y_col not in cols:
            y_col = num_cols[1] if len(num_cols) > 1 else x_col

        if x_col is None or y_col is None:
            send_notification("Scatter Plot: no numeric columns found", level='warning', notif_id=_NOTIF_ID)
            return {}

        # Subsample for performance
        plot_df = df
        if max_pts > 0 and len(df) > max_pts:
            plot_df = df.sample(max_pts, random_state=42)

        with plt.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(w_px / 100, h_px / 100))

            x_data = plot_df[x_col]
            y_data = plot_df[y_col]

            if hue_col and hue_col in plot_df.columns:
                classes = plot_df[hue_col].unique()[:20]  # cap legend at 20 classes
                color_cycle = plt.cm.get_cmap(cmap)(np.linspace(0, 1, len(classes)))
                for cls, color in zip(classes, color_cycle):
                    mask = plot_df[hue_col] == cls
                    ax.scatter(x_data[mask], y_data[mask],
                               label=str(cls), color=color, alpha=alpha, s=s, edgecolors='none')
                ax.legend(fontsize=8, labelcolor='#cccccc', title=hue_col,
                          title_fontsize=8, loc='best')
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
                    ax.legend(fontsize=8, labelcolor='#cccccc', loc='best')
                except Exception as e:
                    send_notification(f"Scatter: regression failed ({e})", level='warning', notif_id=_NOTIF_ID)

            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            title = f"{x_col}  vs  {y_col}"
            if max_pts > 0 and len(df) > max_pts:
                title += f"  (sample {max_pts}/{len(df)})"
            ax.set_title(title, fontsize=10)
            if grid:
                ax.grid(True)

            fig.tight_layout()
            img = _fig_to_bgr(fig)
            plt.close(fig)

        return {'main': img}
