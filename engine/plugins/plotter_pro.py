"""
Plotter Pro — multi-series live plotter.
Up to 5 dynamic inputs, colour palette selector, axes display,
DataFrame output, and fill-under-curve.
"""
import cv2
import numpy as np
from registry import NodeProcessor, vision_node

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False

# ── Palettes: 5 colours (BGR) ────────────────────────────────────────────────
_PALETTES: dict[str, list[tuple[int, int, int]]] = {
    'Classic':     [(60, 60, 255),  (60, 220, 60),  (255, 100, 60),  (60, 220, 220), (220, 60, 220)],
    'Neon':        [(0, 255, 255),  (0, 255, 80),   (255, 0, 200),   (0, 200, 255),  (255, 200, 0)],
    'Pastel':      [(180, 160, 255),(160, 230, 200),(200, 200, 255), (180, 230, 255),(255, 200, 200)],
    'Cold':        [(255, 200, 60), (255, 140, 0),  (255, 80, 60),   (200, 180, 255),(100, 120, 200)],
    'Monochrome':  [(240, 240, 240),(180, 180, 180),(130, 130, 130), (90, 90, 90),   (50, 50, 50)],
}
MAX_SERIES = 5

# Keys injected by the engine as compatibility shims — not real series.
_SKIP_KEYS = frozenset({'raw_frame', 'image', 'data', 'in', 'value', 'main'})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float, np.number)):
        return float(v)
    if isinstance(v, (list, np.ndarray)):
        if len(v) == 0:
            return 0.0
        if isinstance(v[0], dict):
            for key in ('area', 'scalar', 'value', 'confidence'):
                if key in v[0]:
                    return float(np.mean([it.get(key, 0) for it in v]))
            return float(len(v))
        try:
            return float(np.mean(v))
        except Exception:
            return 0.0
    if isinstance(v, dict):
        for key in ('area', 'scalar', 'value', 'confidence'):
            if key in v:
                return float(v[key])
        return 1.0
    return 0.0


def _apply_normalize(data: list[float], norm_type: int) -> list[float]:
    """0=None, 1=Min-Max [0,1], 2=Z-Score, 3=Robust (IQR)."""
    if norm_type == 0 or len(data) < 2:
        return list(data)
    arr = np.array(data, dtype=np.float64)
    if norm_type == 1:
        lo, hi = arr.min(), arr.max()
        return ((arr - lo) / (hi - lo)).tolist() if hi > lo else arr.tolist()
    if norm_type == 2:
        mu, sd = arr.mean(), arr.std()
        return ((arr - mu) / sd).tolist() if sd > 0 else arr.tolist()
    if norm_type == 3:
        med = np.median(arr)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        return ((arr - med) / iqr).tolist() if iqr > 0 else arr.tolist()
    return list(data)


def _apply_filter(data: list[float], filter_type: int, window: int) -> list[float]:
    if filter_type == 0 or len(data) < 2:
        return list(data)
    arr = np.array(data, dtype=np.float64)
    w = min(window, len(arr))
    if w < 2:
        return list(data)
    if filter_type == 1:  # moving average
        return np.convolve(arr, np.ones(w) / w, mode='same').tolist()
    if filter_type == 2:  # median
        half = w // 2
        out = np.empty_like(arr)
        for i in range(len(arr)):
            out[i] = np.median(arr[max(0, i - half): min(len(arr), i + half + 1)])
        return out.tolist()
    if filter_type == 3:  # EMA
        alpha = 2.0 / (w + 1)
        out = [arr[0]]
        for v in arr[1:]:
            out.append(alpha * v + (1 - alpha) * out[-1])
        return out
    if filter_type == 4:  # Gaussian
        half = w // 2
        sigma = w / 3.0
        k = np.exp(-np.arange(-half, half + 1) ** 2 / (2 * sigma ** 2))
        k /= k.sum()
        return np.convolve(arr, k, mode='same').tolist()
    return list(data)


def _smooth_pts(
    data: list[float],
    min_y: float, max_y: float,
    margin: int, plot_w: int, plot_h: int,
) -> np.ndarray:
    """Return (N,2) int32 pixel coords, spline-smoothed."""
    n = len(data)
    y_range = (max_y - min_y) or 1.0
    y_data = np.array(data, dtype=np.float64)

    if n > plot_w:
        idx = np.linspace(0, n - 1, plot_w).astype(int)
        y_data = y_data[idx]
        n = len(y_data)

    x_t = np.linspace(0.0, 1.0, n)
    y_px = margin + plot_h - ((y_data - min_y) / y_range * plot_h)
    y_px = np.clip(y_px, margin, margin + plot_h)

    if n >= 4:
        try:
            from scipy.interpolate import make_interp_spline
            n_out = min(plot_w, n * 4)
            t_new = np.linspace(0.0, 1.0, n_out)
            y_smooth = np.clip(make_interp_spline(x_t, y_px, k=3)(t_new), margin, margin + plot_h)
            x_px = margin + t_new * plot_w
        except Exception:
            x_px = margin + x_t * plot_w
            y_smooth = y_px
    else:
        x_px = margin + x_t * plot_w
        y_smooth = y_px

    return np.column_stack([x_px, y_smooth]).astype(np.int32)


def _draw_axes(
    img: np.ndarray,
    min_y: float, max_y: float,
    margin: int, plot_w: int, plot_h: int,
    n_points: int,
    n_x: int = 5, n_y: int = 5,
) -> None:
    """Draw axis lines and tick labels. X axis = sample index (0 → n_points-1)."""
    h, w = img.shape[:2]
    axis_col = (160, 160, 160)
    tick_col = (200, 200, 200)
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.32

    # Border
    cv2.rectangle(img, (margin, margin), (w - margin, h - margin), axis_col, 1, cv2.LINE_AA)

    # X ticks — labelled with the actual sample index (oldest left → newest right)
    last_idx = max(n_points - 1, 0)
    for i in range(n_x + 1):
        xp = int(margin + i * plot_w / n_x)
        cv2.line(img, (xp, h - margin), (xp, h - margin + 4), tick_col, 1)
        idx_label = str(int(round(i * last_idx / n_x)))
        cv2.putText(img, idx_label, (xp - 6, h - margin + 14),
                    font, fs, tick_col, 1, cv2.LINE_AA)

    # Y ticks
    y_range = (max_y - min_y) or 1.0
    for i in range(n_y + 1):
        val = min_y + i * y_range / n_y
        yp = int(margin + plot_h - (val - min_y) / y_range * plot_h)
        cv2.line(img, (margin - 4, yp), (margin, yp), tick_col, 1)
        label = f'{val:.2g}'
        tw, _ = cv2.getTextSize(label, font, fs, 1)[0], None
        cv2.putText(img, label, (margin - len(label) * 5 - 6, yp + 4),
                    font, fs, tick_col, 1, cv2.LINE_AA)


def _fill_under(
    img: np.ndarray,
    pts: np.ndarray,
    color: tuple[int, int, int],
    margin: int, plot_h: int,
    alpha: float = 0.18,
) -> None:
    """Semi-transparent fill between curve and baseline."""
    if len(pts) < 2:
        return
    baseline_y = margin + plot_h
    poly = np.vstack([
        pts,
        [[pts[-1, 0], baseline_y]],
        [[pts[0, 0],  baseline_y]],
    ])
    overlay = img.copy()
    cv2.fillPoly(overlay, [poly], color)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)


# ── Node ─────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='plotter_pro',
    label='Plotter Pro',
    category='visualize',
    icon='Activity',
    description='Multi-series live plotter: up to 5 curves, palette selector, axes, DataFrame output, fill option.',
    resizable=True,
    dynamic_inputs=True,
    inputs=[],
    outputs=[
        {'id': 'main',  'color': 'image', 'label': 'Plot'},
        {'id': 'table', 'color': 'data',  'label': 'DataFrame'},
    ],
    params=[
        {'id': '_sec_display', 'label': 'Display',       'type': 'section'},
        {'id': 'line_width',   'label': 'Line Width',    'type': 'scalar', 'min': 1, 'max': 6, 'default': 2},
        {'id': 'show_grid',    'label': 'Show Grid',     'type': 'boolean', 'default': True},
        {'id': 'show_axes',    'label': 'Show Axes',     'type': 'boolean', 'default': True},
        {'id': 'fill_curve',   'label': 'Fill Under Curve', 'type': 'boolean', 'default': False},
        {'id': '_sec_scale',   'label': 'Scale',         'type': 'section'},
        {'id': 'auto_scale',   'label': 'Auto-Scale',    'type': 'boolean', 'default': True},
        {'id': 'min_y',        'label': 'Y Min',         'type': 'float',  'default': 0},
        {'id': 'max_y',        'label': 'Y Max',         'type': 'float',  'default': 100},
        {'id': '_sec_filter',  'label': 'Filter',        'type': 'section'},
        {'id': 'filter_type',  'label': 'Filter',        'type': 'enum',
         'options': ['None', 'Moving Average', 'Median', 'EMA', 'Gaussian'], 'default': 0},
        {'id': 'filter_window','label': 'Window',        'type': 'scalar', 'min': 2, 'max': 100, 'default': 5},
        {'id': 'normalize',    'label': 'Normalize',     'type': 'enum',
         'options': ['None', 'Min-Max [0,1]', 'Z-Score', 'Robust (IQR)'], 'default': 0},
        {'id': '_sec_history', 'label': 'History',       'type': 'section'},
        {'id': 'buffer_size',  'label': 'History Size',  'type': 'scalar', 'min': 10, 'max': 2000, 'default': 300},
        {'id': 'reset',        'label': 'Reset History', 'type': 'trigger', 'default': 0},
    ],
)
class PlotterProNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.history: dict[str, list[float]] = {}

    def process(self, inputs: dict, params: dict) -> dict:
        if not hasattr(self, 'history') or self.history is None:
            self.history = {}

        if int(params.get('reset', 0)) == 1:
            self.history = {}

        # ── Params ────────────────────────────────────────────────────────
        # Image output uses a fixed palette; the in-node chart follows the
        # global top-menu palette (frontend-only, not available to the engine).
        palette       = _PALETTES['Classic']
        line_width    = int(params.get('line_width', 2))
        show_grid     = bool(params.get('show_grid', True))
        show_axes     = bool(params.get('show_axes', True))
        fill_curve    = bool(params.get('fill_curve', False))
        auto_scale    = bool(params.get('auto_scale', True))
        min_y         = float(params.get('min_y', 0))
        max_y         = float(params.get('max_y', 100))
        filter_type   = int(params.get('filter_type', 0))
        filter_window = int(params.get('filter_window', 5))
        normalize     = int(params.get('normalize', 0))
        buffer_size   = int(params.get('buffer_size', 300))

        # ── Collect dynamic inputs (max 5) ────────────────────────────────
        raw_series = {k: v for k, v in inputs.items()
                      if v is not None and k not in _SKIP_KEYS}
        # Keep insertion order, cap at MAX_SERIES
        keys = list(raw_series.keys())[:MAX_SERIES]

        # Drop history for disconnected series
        for k in list(self.history.keys()):
            if k not in keys:
                del self.history[k]

        for k in keys:
            val = _to_float(raw_series[k])
            if val is not None:
                buf = self.history.setdefault(k, [])
                buf.append(val)
                if len(buf) > buffer_size:
                    self.history[k] = buf[-buffer_size:]

        # ── Filter + normalize (per series) ───────────────────────────────
        processed: dict[str, list[float]] = {}
        for k, hist in self.history.items():
            if len(hist) >= 2:
                data = _apply_filter(list(hist), filter_type, filter_window)
                data = _apply_normalize(data, normalize)
            else:
                data = list(hist)
            processed[k] = data

        # ── Auto-scale ────────────────────────────────────────────────────
        if auto_scale:
            all_vals = [v for d in processed.values() for v in d]
            if all_vals:
                mn, mx = min(all_vals), max(all_vals)
                pad = (mx - mn) * 0.1 if mx != mn else 1.0
                min_y, max_y = mn - pad, mx + pad
                if max_y == min_y:
                    max_y += 1.0

        y_range = (max_y - min_y) or 1.0

        # ── Render ────────────────────────────────────────────────────────
        w, h   = 640, 360
        margin = 50 if show_axes else 30
        plot_h = h - margin * 2
        plot_w = w - margin * 2

        img = np.full((h, w, 3), 18, dtype=np.uint8)

        if show_grid:
            gc = (55, 55, 55)
            for i in range(1, 5):
                yg = int(margin + plot_h * i / 5)
                cv2.line(img, (margin, yg), (w - margin, yg), gc, 1, cv2.LINE_AA)
            for i in range(1, 6):
                xg = int(margin + plot_w * i / 6)
                cv2.line(img, (xg, margin), (xg, h - margin), gc, 1, cv2.LINE_AA)

        if show_axes:
            n_points = max((len(d) for d in processed.values()), default=0)
            _draw_axes(img, min_y, max_y, margin, plot_w, plot_h, n_points)

        # ── Draw curves ───────────────────────────────────────────────────
        for i, (key, data) in enumerate(processed.items()):
            color = palette[i % len(palette)]
            if len(data) < 2:
                continue
            pts = _smooth_pts(data, min_y, max_y, margin, plot_w, plot_h)
            if fill_curve:
                _fill_under(img, pts, color, margin, plot_h)
            cv2.polylines(img, [pts], False, color, line_width, cv2.LINE_AA)

            # Legend chip
            lx, ly = 8, 20 + i * 22
            cv2.rectangle(img, (lx, ly - 10), (lx + 10, ly), color, -1)
            label = f'{key}: {data[-1]:.3g}'
            cv2.putText(img, label, (lx + 14, ly - 1),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

        # ── DataFrame output ──────────────────────────────────────────────
        table = None
        if _PD_OK and processed:
            max_len = max(len(v) for v in processed.values())
            df_data = {}
            for k, data in processed.items():
                # Pad shorter series with NaN at the front
                pad = max_len - len(data)
                df_data[k] = [float('nan')] * pad + list(data)
            table = pd.DataFrame(df_data)

        out = {'main': img, 'table': table}

        # Echo latest value per series so the in-node Recharts chart can plot
        # (frontend reads nd[seriesKey]); also feeds downstream scalar consumers.
        for k, data in processed.items():
            if data:
                out[k] = float(data[-1])
        return out
