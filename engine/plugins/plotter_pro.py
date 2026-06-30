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
# NOTE: 'dict_in' is NOT skipped — it's a real port whose dict is unpacked
# into per-key sub-series (see the collection loop in process()).
_SKIP_KEYS = frozenset({'raw_frame', 'image', 'data', 'in', 'value', 'main'})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None  # never coerce booleans into a series value
    if isinstance(v, (int, float, np.number)):
        f = float(v)
        return f if np.isfinite(f) else None
    if isinstance(v, (list, np.ndarray)):
        if len(v) == 0:
            return None
        if isinstance(v[0], dict):
            for key in ('area', 'scalar', 'value', 'confidence'):
                if key in v[0]:
                    return float(np.mean([it.get(key, 0) for it in v]))
            return None  # list of opaque dicts → no meaningful scalar
        try:
            return float(np.mean(v))
        except Exception:
            return None
    if isinstance(v, dict):
        for key in ('area', 'scalar', 'value', 'confidence'):
            if key in v:
                return float(v[key])
        return None  # opaque dict → skip (do NOT inject a constant 1.0)
    return 0.0


def _apply_normalize(data: list[float], norm_type: int) -> list[float]:
    """0=None, 1=Min-Max [0,1], 2=Z-Score, 3=Robust (IQR)."""
    if norm_type == 0 or len(data) < 2:
        return list(data)
    arr = np.array(data, dtype=np.float64)
    # Relative epsilon: a near-constant series has negligible spread compared
    # to its magnitude. Dividing by that tiny spread amplifies rounding noise
    # into huge spurious spikes, so treat such a series as flat (zeros).
    scale = max(abs(float(arr.mean())), 1.0)
    eps = 1e-6 * scale
    if norm_type == 1:
        lo, hi = arr.min(), arr.max()
        return ((arr - lo) / (hi - lo)).tolist() if (hi - lo) > eps else np.zeros_like(arr).tolist()
    if norm_type == 2:
        mu, sd = arr.mean(), arr.std()
        return ((arr - mu) / sd).tolist() if sd > eps else np.zeros_like(arr).tolist()
    if norm_type == 3:
        med = np.median(arr)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        return ((arr - med) / iqr).tolist() if iqr > eps else np.zeros_like(arr).tolist()
    return list(data)


def _apply_filter(data: list[float], filter_type: int, window: int) -> list[float]:
    if filter_type == 0 or len(data) < 2:
        return list(data)
    arr = np.array(data, dtype=np.float64)
    w = min(window, len(arr))
    if w < 2:
        return list(data)
    if filter_type == 1:  # moving average (edge-padded to avoid boundary dips)
        half = w // 2
        padded = np.pad(arr, half, mode='edge')
        sm = np.convolve(padded, np.ones(w) / w, mode='valid')
        return sm[:len(arr)].tolist()
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
    if filter_type == 4:  # Gaussian (edge-padded)
        half = w // 2
        sigma = w / 3.0
        k = np.exp(-np.arange(-half, half + 1) ** 2 / (2 * sigma ** 2))
        k /= k.sum()
        padded = np.pad(arr, half, mode='edge')
        sm = np.convolve(padded, k, mode='valid')
        return sm[:len(arr)].tolist()
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


def _describe(v) -> str:
    """Compact, safe description of an input value for debug logging."""
    if isinstance(v, np.ndarray):
        return f"ndarray{v.shape}:{v.dtype}"
    if isinstance(v, dict):
        items = list(v.items())[:8]
        body = ', '.join(f"{k}={_describe(vv)}" for k, vv in items)
        more = '…' if len(v) > 8 else ''
        return f"dict({len(v)}){{{body}{more}}}"
    if isinstance(v, (list, tuple)):
        head = ', '.join(_describe(x) for x in list(v)[:4])
        more = '…' if len(v) > 4 else ''
        return f"{type(v).__name__}({len(v)})[{head}{more}]"
    if isinstance(v, bool):
        return f"bool:{v}"
    if isinstance(v, (int, float, np.number)):
        return f"{type(v).__name__}:{v}"
    if isinstance(v, str):
        return f"str:'{v[:20]}'"
    return type(v).__name__


# ── Node ─────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='plotter_pro',
    label='Plotter Pro',
    category='visualize',
    icon='Activity',
    description='Multi-series live plotter: up to 5 curves, palette selector, axes, DataFrame output, fill option.',
    resizable=True,
    dynamic_inputs=True,
    inputs=[
        {'id': 'dict_in', 'color': 'dict', 'label': 'Dict'},
    ],
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
        {'id': '_sec_debug',   'label': 'Debug',         'type': 'section'},
        {'id': 'debug_dump',   'label': 'Debug Dump (~/plotter_debug.log)', 'type': 'boolean', 'default': False},
    ],
)
class PlotterProNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.history: dict[str, list[float]] = {}
        self._dbg_n = 0

    def process(self, inputs: dict, params: dict) -> dict:
        if not hasattr(self, 'history') or self.history is None:
            self.history = {}
        if not hasattr(self, '_dbg_n'):
            self._dbg_n = 0

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

        def _is_active(key: str) -> bool:
            v = params.get(f'active_{key}', True)
            if isinstance(v, str):
                return v.lower() != 'false'
            return bool(v)

        def _numeric(x):
            """Return a finite float, or None if x isn't a plain scalar number."""
            if isinstance(x, bool) or isinstance(x, (dict, list, tuple, np.ndarray)):
                return None
            try:
                f = float(x)
            except (TypeError, ValueError):
                return None
            return f if np.isfinite(f) else None

        # ── Separate scalar inputs from dict inputs ───────────────────────
        # A dict on ANY port (the static dict_in OR a dynamic port) is unpacked
        # into one sub-series per numeric key. Scalars become one series each.
        scalar_inputs: dict[str, float] = {}   # series_key -> value
        all_dict_keys: list[str] = []          # dict sub-keys (for inspector toggles)
        dict_vals: dict[str, float] = {}       # active dict sub-key -> value

        for k, v in inputs.items():
            if k in _SKIP_KEYS or v is None:
                continue
            if isinstance(v, dict):
                for dk, dv in v.items():
                    nv = _numeric(dv)
                    if nv is None:
                        continue
                    skey = str(dk)
                    all_dict_keys.append(skey)
                    if _is_active(skey):
                        dict_vals[skey] = nv
            else:
                nv = _to_float(v)
                if nv is not None:
                    scalar_inputs[k] = nv

        # Cap at MAX_SERIES: scalars first, then dict sub-series fill the rest.
        scalar_keys = list(scalar_inputs.keys())[:MAX_SERIES]
        remaining = max(0, MAX_SERIES - len(scalar_keys))
        dict_keys_capped = list(dict_vals.keys())[:remaining]
        active_keys = scalar_keys + dict_keys_capped

        # ── Build unified raw values dict (this frame) ────────────────────
        raw_vals: dict[str, float] = {}
        for k in scalar_keys:
            raw_vals[k] = scalar_inputs[k]
        for k in dict_keys_capped:
            raw_vals[k] = dict_vals[k]

        # Drop history for series no longer active (disconnected / toggled off)
        for k in list(self.history.keys()):
            if k not in active_keys:
                del self.history[k]

        # CRITICAL: every active series advances by exactly one sample per call,
        # so all histories stay the same length and share a common x-axis.
        # A series missing a value this frame carries forward its last value
        # (hold) instead of falling behind → prevents horizontal desync.
        for k in active_keys:
            buf = self.history.setdefault(k, [])
            if k in raw_vals:
                buf.append(raw_vals[k])
            elif buf:
                buf.append(buf[-1])
            else:
                continue  # no value yet for a brand-new series
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

        # ── Auto-scale (robust: 2nd–98th percentile, outlier-resistant) ────
        if auto_scale:
            all_vals = [v for d in processed.values() for v in d]
            if all_vals:
                arr = np.asarray(all_vals, dtype=np.float64)
                lo, hi = np.percentile(arr, [2, 98])
                if hi <= lo:  # too few / near-constant points → fall back to min/max
                    lo, hi = float(arr.min()), float(arr.max())
                pad = (hi - lo) * 0.1 if hi > lo else (abs(hi) * 0.05 or 1.0)
                min_y, max_y = lo - pad, hi + pad
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
            label = f'{key}: {data[-1]:.4f}'
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

        # Deduplicated, order-preserving list of dict sub-keys for the inspector.
        unique_dict_keys = list(dict.fromkeys(all_dict_keys))
        out: dict = {'main': img, 'table': table, 'dict_keys': unique_dict_keys}

        # Echo full processed series as lists so param changes (filter, normalize…)
        # immediately redraw the in-node chart history. Frontend handles arrays
        # by replacing histories[k] directly (see scientific.tsx lines 354-356).
        for k, data in processed.items():
            if data:
                out[k] = list(data)

        # ── Debug dump (gated) ────────────────────────────────────────────
        # Captures ground-truth input shapes for the first 60 frames after the
        # toggle is enabled, so we can see exactly what reaches the node.
        if bool(params.get('debug_dump', False)):
            if self._dbg_n < 60:
                try:
                    import os
                    lines = [f"=== frame {self._dbg_n} ==="]
                    for ik, iv in inputs.items():
                        if ik == 'raw_frame':
                            continue
                        lines.append(f"  in[{ik}] = {_describe(iv)}")
                    lines.append(f"  active_keys = {active_keys}")
                    lines.append(f"  raw_vals = { {k: round(v, 5) for k, v in raw_vals.items()} }")
                    lines.append(f"  hist_len = { {k: len(v) for k, v in self.history.items()} }")
                    lines.append(f"  last = { {k: (round(v[-1], 5) if v else None) for k, v in self.history.items()} }")
                    lines.append(f"  params: filter={filter_type} window={filter_window} "
                                 f"norm={normalize} auto={auto_scale} buf={buffer_size}")
                    with open(os.path.expanduser('~/plotter_debug.log'), 'a') as fh:
                        fh.write('\n'.join(lines) + '\n')
                    self._dbg_n += 1
                except Exception:
                    pass
        else:
            self._dbg_n = 0

        return out
