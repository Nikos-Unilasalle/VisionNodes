"""
ml_robust_line.py — robust straight-line fit for scatter data (L2 / Huber / Theil-Sen).

Fits y = a·x + b to two columns of a DataFrame under three loss models:
ordinary least squares (L2, dragged off by outliers), Huber (down-weights big
residuals) and Theil-Sen / median-of-slopes (very high breakdown point). Overlays
the fitted line on the scatter and reports the slope — the point is to see the
robust fits ignore a few wild outliers that wreck the L2 line (ch16, robust stats).
"""

import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'ml_robust_line'
_MODES = ['Least Squares (L2)', 'Huber', 'Theil-Sen (median)']

_MPL_DARK = {
    'figure.facecolor': '#161616', 'axes.facecolor': '#1e1e1e',
    'axes.edgecolor': '#555555', 'axes.labelcolor': '#cccccc',
    'text.color': '#cccccc', 'xtick.color': '#aaaaaa', 'ytick.color': '#aaaaaa',
    'grid.color': '#333333', 'grid.linestyle': '--', 'grid.linewidth': 0.5,
}


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


@vision_node(
    type_id='ml_robust_line',
    label='Robust Line Fit',
    category='Machine Learning',
    icon='TrendingUp',
    description=(
        "Fits a straight line to two DataFrame columns under a chosen loss: "
        "Least Squares (L2), Huber, or Theil-Sen (median). Robust modes ignore a "
        "few wild outliers that drag the L2 line off the trend. Overlays the fit "
        "on the scatter and reports the slope."
    ),
    inputs=[
        {'id': 'table', 'label': 'DataFrame', 'color': 'data'},
    ],
    outputs=[
        {'id': 'main',      'label': 'Plot', 'color': 'image'},
        {'id': 'slope',     'label': 'Slope', 'color': 'scalar'},
        {'id': 'intercept', 'label': 'Intercept', 'color': 'scalar'},
    ],
    params=[
        {'id': 'x_col',       'label': 'X Column', 'type': 'string', 'default': ''},
        {'id': 'y_col',       'label': 'Y Column', 'type': 'string', 'default': ''},
        {'id': 'mode',        'label': 'Fit', 'type': 'enum', 'options': _MODES, 'default': 0},
        {'id': 'huber_delta', 'label': 'Huber Tolerance', 'type': 'float', 'default': 1.35, 'min': 1.0, 'max': 10.0, 'step': 0.05},
    ]
)
class RobustLineNode(NodeProcessor):

    @staticmethod
    def _pick_cols(df, x_col, y_col):
        import pandas as pd
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        x = x_col if x_col in df.columns else (numeric[0] if numeric else None)
        y = y_col if y_col in df.columns else (numeric[1] if len(numeric) > 1 else None)
        return x, y

    @staticmethod
    def _fit(x, y, mode, delta):
        if mode == 0:  # L2
            a, b = np.polyfit(x, y, 1)
            return float(a), float(b)
        X = x.reshape(-1, 1)
        if mode == 1:
            from sklearn.linear_model import HuberRegressor
            m = HuberRegressor(epsilon=max(1.0001, delta)).fit(X, y)
        else:
            from sklearn.linear_model import TheilSenRegressor
            m = TheilSenRegressor(random_state=0).fit(X, y)
        return float(m.coef_[0]), float(m.intercept_)

    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None or not hasattr(df, 'columns'):
            return {'main': None, 'slope': 0.0, 'intercept': 0.0}

        x_col = str(params.get('x_col', '')).strip()
        y_col = str(params.get('y_col', '')).strip()
        mode  = int(params.get('mode', 0))
        delta = float(params.get('huber_delta', 1.35))

        xc, yc = self._pick_cols(df, x_col, y_col)
        if xc is None or yc is None:
            send_notification("Robust Line Fit: need two numeric columns", level='error', notif_id=_NOTIF)
            return {'main': None, 'slope': 0.0, 'intercept': 0.0}

        sub = df[[xc, yc]].dropna()
        x = sub[xc].to_numpy(dtype=float)
        y = sub[yc].to_numpy(dtype=float)
        if len(x) < 2:
            return {'main': None, 'slope': 0.0, 'intercept': 0.0}

        a, b = self._fit(x, y, mode, delta)

        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig = None
        try:
            with plt.rc_context(_MPL_DARK):
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.scatter(x, y, s=18, c='#38bdf8', alpha=0.8, label='data')
                xs = np.linspace(x.min(), x.max(), 100)
                ax.plot(xs, a * xs + b, c='#22c55e', lw=2,
                        label=f'{_MODES[mode]}: y={a:.3f}x+{b:.2f}')
                ax.set_xlabel(xc); ax.set_ylabel(yc)
                ax.legend(fontsize=8, loc='best')
                ax.grid(True)
                fig.tight_layout()
                plot = _fig_to_bgr(fig)
        finally:
            if fig is not None:
                plt.close(fig)

        return {'main': plot, 'slope': round(a, 5), 'intercept': round(b, 5)}
