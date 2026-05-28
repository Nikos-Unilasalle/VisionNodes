"""
ml_bar_chart.py — Universal bar chart node.

Accepts:
  - A DataFrame (data port): uses x_col (categories) + y_col (values),
    with optional hue_col for grouped bars.
  - A dict (dict port): {label: value} rendered as a simple bar chart.
    Keys become category labels, values become bar heights.

Typical uses:
  - Ablation study: F1 per class for S1-only vs S1+S2 (two dicts)
  - Feature importance ranking (alternative to the built-in chart)
  - Per-class area (ha) from geo_class_stats
  - Any scalar comparison

Connect dict output (e.g. from geo_class_stats or geo_rf_classifier report_data)
directly — no DataFrame conversion needed.
"""
from __future__ import annotations
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'bar_chart'

_CMAPS       = ['tab10', 'Set2', 'Set1', 'viridis', 'plasma', 'RdYlGn', 'coolwarm']
_CMAP_LABELS = ['Tab10', 'Set2', 'Set1', 'Viridis', 'Plasma', 'RdYlGn', 'Coolwarm']

_EXPORT_PARAMS = [
    {'id': 'out_dpi', 'label': 'DPI (100=screen, 300=print)', 'type': 'int',
     'default': 100, 'min': 72, 'max': 600},
    {'id': 'out_w',   'label': 'Width px  (0 = node width)',  'type': 'int',
     'default': 0, 'min': 0, 'max': 5000},
    {'id': 'out_h',   'label': 'Height px (0 = node height)', 'type': 'int',
     'default': 0, 'min': 0, 'max': 5000},
]


def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


def _fig_to_bgr(fig, dpi: int = 100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _out_size(params: dict, default_w: int = 540, default_h: int = 400):
    dpi   = max(72, int(params.get('out_dpi', 100)))
    out_w = int(params.get('out_w', 0))
    out_h = int(params.get('out_h', 0))
    if out_w > 0 and out_h > 0:
        return out_w / dpi, out_h / dpi, dpi
    return default_w / dpi, default_h / dpi, dpi


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


@vision_node(
    type_id='ml_bar_chart',
    label='Bar Chart',
    category='DataFrame',
    icon='BarChart2',
    description=(
        "Universal bar chart. "
        "Accepts a DataFrame (set x_col + y_col) OR a plain dict ({label: value}). "
        "Supports grouped bars (hue_col), horizontal/vertical layout, "
        "sorted display, error bars, and a second series overlay for comparison. "
        "Ideal for: F1-per-class ablation, feature importance, area statistics."
    ),
    inputs=[
        {'id': 'table',   'color': 'data', 'label': 'DataFrame'},
        {'id': 'data_b',  'color': 'dict', 'label': 'Dict B (comparison overlay)'},
    ],
    outputs=[
        {'id': 'main',  'color': 'image', 'label': 'Bar chart'},
    ],
    params=[
        # ── DataFrame mode ────────────────────────────────────────────────────
        {'id': 'x_col',      'label': 'Category column (DataFrame mode)',
         'type': 'string', 'default': ''},
        {'id': 'y_col',      'label': 'Value column (DataFrame mode)',
         'type': 'string', 'default': ''},
        {'id': 'hue_col',    'label': 'Group by (hue)',
         'type': 'string', 'default': ''},
        # ── Dict mode (auto when table absent) ───────────────────────────────
        {'id': 'dict_key_a', 'label': 'Dict A label (legend)',
         'type': 'string', 'default': 'Series A'},
        {'id': 'dict_key_b', 'label': 'Dict B label (legend)',
         'type': 'string', 'default': 'Series B'},
        # ── Layout ────────────────────────────────────────────────────────────
        {'id': 'orientation', 'label': 'Orientation',
         'type': 'enum', 'options': ['Vertical', 'Horizontal'], 'default': 0},
        {'id': 'sorted',      'label': 'Sort by value',
         'type': 'bool', 'default': False},
        {'id': 'show_values', 'label': 'Show value labels',
         'type': 'bool', 'default': True},
        {'id': 'title',       'label': 'Title',
         'type': 'string', 'default': ''},
        {'id': 'xlabel',      'label': 'X axis label',
         'type': 'string', 'default': ''},
        {'id': 'ylabel',      'label': 'Y axis label',
         'type': 'string', 'default': ''},
        # ── Style ─────────────────────────────────────────────────────────────
        {'id': 'colormap',   'label': 'Colormap',
         'type': 'enum', 'options': _CMAP_LABELS, 'default': 0},
        {'id': 'bar_width',  'label': 'Bar width',
         'type': 'float', 'default': 0.75, 'min': 0.1, 'max': 1.0},
        {'id': 'alpha',      'label': 'Opacity',
         'type': 'float', 'default': 0.85, 'min': 0.1, 'max': 1.0},
        *_EXPORT_PARAMS,
    ],
    resizable=True, min_width=300, min_height=240,
)
class MLBarChartNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        _, plt = _get_mpl()

        df     = inputs.get('table')
        dict_b = inputs.get('data_b')

        # ── Resolve data ──────────────────────────────────────────────────────
        try:
            import pandas as pd
            has_pandas = True
        except ImportError:
            has_pandas = False

        x_col  = str(params.get('x_col', '')).strip()
        y_col  = str(params.get('y_col', '')).strip()
        hue    = str(params.get('hue_col', '')).strip()

        # Mode A: dict input (no DataFrame)
        use_dict_mode = (df is None or (has_pandas and not isinstance(df, pd.DataFrame)))

        categories: list = []
        values_a:   list = []
        values_b:   list | None = None

        if use_dict_mode:
            # Accept dict from `table` port too if it's a dict
            dict_a = df if isinstance(df, dict) else {}
            dict_b_ = dict_b if isinstance(dict_b, dict) else {}

            if not dict_a and not dict_b_:
                send_notification('Bar Chart: no data — connect a DataFrame or dict',
                                  level='warning', notif_id=_NOTIF)
                return {}

            # Merge keys
            all_keys = list(dict(sorted(
                {**dict_a, **dict_b_}.items(),
                key=lambda kv: float(kv[1]) if isinstance(kv[1], (int, float)) else 0,
                reverse=True,
            )).keys())
            categories = [str(k) for k in all_keys]
            values_a   = [float(dict_a.get(k, 0)) for k in all_keys]
            if dict_b_:
                values_b = [float(dict_b_.get(k, 0)) for k in all_keys]

        else:  # DataFrame mode
            if not has_pandas:
                send_notification('Bar Chart: pandas not available', level='error', notif_id=_NOTIF)
                return {}

            if x_col not in df.columns:
                x_col = df.columns[0]
            if y_col not in df.columns:
                num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc' and c != x_col]
                y_col = num_cols[0] if num_cols else df.columns[-1]

            if hue and hue in df.columns:
                # Grouped bars via pivot
                pivot = df.pivot_table(index=x_col, columns=hue, values=y_col, aggfunc='mean')
                categories = [str(c) for c in pivot.index]
                # Will handle below
                values_a = None  # signal grouped mode
                _pivot_df = pivot
            else:
                agg = df.groupby(x_col)[y_col].mean()
                categories = [str(c) for c in agg.index]
                values_a   = list(agg.values)

            if isinstance(dict_b, dict) and dict_b:
                values_b = [float(dict_b.get(c, 0)) for c in categories]

        # ── Sort ──────────────────────────────────────────────────────────────
        if params.get('sorted', False) and values_a is not None and not use_dict_mode is False:
            order = np.argsort(values_a)[::-1]
            categories = [categories[i] for i in order]
            values_a   = [values_a[i] for i in order]
            if values_b:
                values_b = [values_b[i] for i in order]

        # ── Plot ──────────────────────────────────────────────────────────────
        horiz      = int(params.get('orientation', 0)) == 1
        show_vals  = bool(params.get('show_values', True))
        title      = str(params.get('title', '')).strip()
        xlabel_str = str(params.get('xlabel', '')).strip()
        ylabel_str = str(params.get('ylabel', '')).strip()
        bw         = float(params.get('bar_width', 0.75))
        alpha      = float(params.get('alpha', 0.85))
        cmap_idx   = int(params.get('colormap', 0)) if isinstance(params.get('colormap'), int) else 0
        cmap_name  = _CMAPS[cmap_idx] if cmap_idx < len(_CMAPS) else 'tab10'
        fig_w, fig_h, dpi = _out_size(params, 540, max(320, len(categories) * 28 if horiz else 400))

        with plt.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(fig_w, fig_h))

            n = len(categories)
            cmap_fn = plt.cm.get_cmap(cmap_name)

            if values_a is not None:
                colors = [cmap_fn(i / max(n - 1, 1)) for i in range(n)]
                x_pos  = np.arange(n)

                if values_b is not None:
                    # Grouped two-series
                    offset = bw / 2 * 0.5
                    ba = x_pos - offset
                    bb = x_pos + offset
                    label_a = str(params.get('dict_key_a', 'Series A'))
                    label_b = str(params.get('dict_key_b', 'Series B'))
                    if horiz:
                        ax.barh(ba, values_a, height=bw / 2, color='#3b82f6', alpha=alpha,
                                label=label_a, edgecolor='none')
                        ax.barh(bb, values_b, height=bw / 2, color='#f97316', alpha=alpha,
                                label=label_b, edgecolor='none')
                        ax.set_yticks(x_pos); ax.set_yticklabels(categories)
                    else:
                        ax.bar(ba, values_a, width=bw / 2, color='#3b82f6', alpha=alpha,
                               label=label_a, edgecolor='none')
                        ax.bar(bb, values_b, width=bw / 2, color='#f97316', alpha=alpha,
                               label=label_b, edgecolor='none')
                        ax.set_xticks(x_pos); ax.set_xticklabels(categories, rotation=35, ha='right')
                    ax.legend(fontsize=8, labelcolor='#cccccc')
                else:
                    # Single series
                    if horiz:
                        bars = ax.barh(x_pos, values_a, height=bw, color=colors,
                                       alpha=alpha, edgecolor='none')
                        ax.set_yticks(x_pos); ax.set_yticklabels(categories, fontsize=8)
                        if show_vals:
                            for bar, val in zip(bars, values_a):
                                ax.text(bar.get_width() + 0.01 * max(values_a or [1]),
                                        bar.get_y() + bar.get_height() / 2,
                                        f'{val:.3g}', va='center', ha='left', fontsize=7,
                                        color='#aaaaaa')
                    else:
                        bars = ax.bar(x_pos, values_a, width=bw, color=colors,
                                      alpha=alpha, edgecolor='none')
                        ax.set_xticks(x_pos); ax.set_xticklabels(categories, rotation=35, ha='right', fontsize=8)
                        if show_vals:
                            for bar, val in zip(bars, values_a):
                                ax.text(bar.get_x() + bar.get_width() / 2,
                                        bar.get_height() + 0.01 * max(values_a or [1]),
                                        f'{val:.3g}', ha='center', va='bottom', fontsize=7,
                                        color='#aaaaaa')

            else:
                # Grouped DataFrame mode (pivot)
                _pivot_df.plot(kind='barh' if horiz else 'bar', ax=ax,
                               width=bw, alpha=alpha, colormap=cmap_name, edgecolor='none')
                ax.legend(fontsize=7, labelcolor='#cccccc')

            if title:
                ax.set_title(title, fontsize=10, pad=8)
            if xlabel_str:
                ax.set_xlabel(xlabel_str)
            if ylabel_str:
                ax.set_ylabel(ylabel_str)

            ax.grid(True, axis='x' if horiz else 'y', alpha=0.4)
            ax.spines[['top', 'right']].set_visible(False)
            fig.tight_layout()
            img = _fig_to_bgr(fig, dpi)
            plt.close(fig)

        return {'main': img}
