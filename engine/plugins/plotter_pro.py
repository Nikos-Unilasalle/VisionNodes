import cv2
import numpy as np
from registry import NodeProcessor, vision_node

PALETTE = [
    (100, 100, 255), (100, 255, 100), (60, 180, 255),
    (100, 255, 255), (255, 100, 255), (255, 255, 100),
    (200, 150, 255), (100, 200, 255),
]


def _hex_to_bgr(hex_color: str):
    h = hex_color.lstrip('#')
    r = int(h[0:2], 16) if len(h) >= 2 else 255
    g = int(h[2:4], 16) if len(h) >= 4 else 100
    b = int(h[4:6], 16) if len(h) >= 6 else 100
    return (b, g, r)


def _apply_filter(data, filter_type, window):
    if filter_type == 0 or len(data) < 2:
        return list(data)
    arr = np.array(data, dtype=np.float64)
    w = min(window, len(arr))
    if w < 2:
        return list(data)
    if filter_type == 1:
        kernel = np.ones(w) / w
        return np.convolve(arr, kernel, mode='same').tolist()
    elif filter_type == 2:
        half = w // 2
        out = np.zeros_like(arr)
        for i in range(len(arr)):
            lo = max(0, i - half)
            hi = min(len(arr), i + half + 1)
            out[i] = np.median(arr[lo:hi])
        return out.tolist()
    elif filter_type == 3:
        alpha = 2.0 / (w + 1)
        out = [arr[0]]
        for i in range(1, len(arr)):
            out.append(alpha * arr[i] + (1 - alpha) * out[-1])
        return out
    elif filter_type == 4:
        sigma = w / 3.0
        half = w // 2
        k = np.exp(-np.arange(-half, half + 1) ** 2 / (2 * sigma ** 2))
        k /= k.sum()
        return np.convolve(arr, k, mode='same').tolist()
    return list(data)


def _apply_normalize(data, norm_type):
    if norm_type == 0 or len(data) < 2:
        return list(data)
    arr = np.array(data, dtype=np.float64)
    if norm_type == 1:
        lo, hi = arr.min(), arr.max()
        if hi > lo:
            return ((arr - lo) / (hi - lo)).tolist()
        return arr.tolist()
    elif norm_type == 2:
        mu, sd = arr.mean(), arr.std()
        if sd > 0:
            return ((arr - mu) / sd).tolist()
        return arr.tolist()
    elif norm_type == 3:
        med = np.median(arr)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        if iqr > 0:
            return ((arr - med) / iqr).tolist()
        return arr.tolist()
    return list(data)


def _detect_peaks(data, window, prominence=0.1):
    if len(data) < 3:
        return [], []
    from scipy.signal import find_peaks
    arr = np.array(data, dtype=np.float64)
    peaks_max, _ = find_peaks(arr, distance=window, prominence=prominence)
    peaks_min, _ = find_peaks(-arr, distance=window, prominence=prominence)
    return peaks_max.tolist(), peaks_min.tolist()


def _to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float, np.number)):
        return float(v)
    if isinstance(v, (list, np.ndarray)):
        if len(v) == 0:
            return 0.0
        if isinstance(v[0], dict):
            for key in ['area', 'scalar', 'value', 'confidence']:
                if key in v[0]:
                    return float(np.mean([it.get(key, 0) for it in v]))
            return float(len(v))
        try:
            return float(np.mean(v))
        except Exception:
            return 0.0
    if isinstance(v, dict):
        for key in ['area', 'scalar', 'value', 'confidence']:
            if key in v:
                return float(v[key])
        return 1.0
    return 0.0


def _smooth_pts(data, min_y, max_y, margin, plot_w, plot_h):
    """Return (N,2) int32 array of pixel coordinates, spline-smoothed."""
    n = len(data)
    y_range = (max_y - min_y) or 1.0
    y_data = np.array(data, dtype=np.float64)

    # Downsample if more points than pixels
    if n > plot_w:
        idx = np.linspace(0, n - 1, plot_w).astype(int)
        y_data = y_data[idx]
        n = len(y_data)

    x_t = np.linspace(0.0, 1.0, n)
    y_px = margin + plot_h - ((y_data - min_y) / y_range * plot_h)
    y_px = np.clip(y_px, margin, margin + plot_h)

    if n >= 4:
        from scipy.interpolate import make_interp_spline
        n_out = min(plot_w, n * 4)
        t_new = np.linspace(0.0, 1.0, n_out)
        spl = make_interp_spline(x_t, y_px, k=3)
        y_smooth = np.clip(spl(t_new), margin, margin + plot_h)
        x_px = margin + t_new * plot_w
    else:
        x_px = margin + x_t * plot_w
        y_smooth = y_px

    return np.column_stack([x_px, y_smooth]).astype(np.int32)


@vision_node(
    type_id="plotter_pro",
    label="Plotter Pro",
    category=["visualize", "analysis"],
    icon="Activity",
    description="Advanced multi-series plotter with smooth curves, filtering, thresholding, normalization, and peak detection.",
    inputs=[],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "reset", "label": "Reset History", "type": "trigger", "default": 0},
        {"id": "buffer_size", "label": "History Size", "type": "scalar", "min": 10, "max": 2000, "default": 300},
        {"id": "min_y", "label": "Y-Axis Min", "type": "float", "default": 0},
        {"id": "max_y", "label": "Y-Axis Max", "type": "float", "default": 100},
        {"id": "auto_scale", "label": "Auto-Scale", "type": "boolean", "default": True},
        {"id": "line_width", "label": "Line Width", "type": "scalar", "min": 1, "max": 6, "default": 2},
        {"id": "show_grid", "label": "Show Grid", "type": "boolean", "default": True},
        {"id": "filter_type", "label": "Filter", "type": "enum", "options": ["None", "Moving Average", "Median", "Low-Pass (EMA)", "Gaussian"], "default": 0},
        {"id": "filter_window", "label": "Filter Window", "type": "scalar", "min": 2, "max": 100, "default": 5},
        {"id": "threshold_min", "label": "Threshold Min", "type": "float", "default": 0.0},
        {"id": "threshold_max", "label": "Threshold Max", "type": "float", "default": 255.0},
        {"id": "clamp_enabled", "label": "Clamp Values", "type": "boolean", "default": False},
        {"id": "show_thresholds", "label": "Show Thresholds", "type": "boolean", "default": True},
        {"id": "normalize", "label": "Normalize", "type": "enum", "options": ["None", "Min-Max [0,1]", "Z-Score", "Robust (IQR)"], "default": 0},
        {"id": "show_peaks", "label": "Show Peaks", "type": "boolean", "default": False},
        {"id": "peak_window", "label": "Peak Distance", "type": "scalar", "min": 2, "max": 100, "default": 10},
        {"id": "peak_prominence", "label": "Peak Prominence", "type": "float", "min": 0, "max": 100, "default": 0.5},
        {"id": "peak_radius", "label": "Peak Marker Size", "type": "scalar", "min": 2, "max": 10, "default": 4},
    ]
)
class PlotterProNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.history = {}

    def process(self, inputs, params):
        if not hasattr(self, 'history') or self.history is None:
            self.history = {}

        reset = int(params.get('reset', 0))
        buffer_size = int(params.get('buffer_size', 300))
        min_y = float(params.get('min_y', 0))
        max_y = float(params.get('max_y', 100))
        auto_scale = bool(params.get('auto_scale', True))
        w, h = 640, 360
        line_width = int(params.get('line_width', 2))
        show_grid = bool(params.get('show_grid', True))
        filter_type = int(params.get('filter_type', 0))
        filter_window = int(params.get('filter_window', 5))
        threshold_min = float(params.get('threshold_min', 0.0))
        threshold_max = float(params.get('threshold_max', 255.0))
        clamp_enabled = bool(params.get('clamp_enabled', False))
        show_thresholds = bool(params.get('show_thresholds', True))
        normalize = int(params.get('normalize', 0))
        show_peaks = bool(params.get('show_peaks', False))
        peak_window = int(params.get('peak_window', 10))
        peak_prominence = float(params.get('peak_prominence', 0.5))
        peak_radius = int(params.get('peak_radius', 4))

        if reset == 1:
            self.history = {}

        # Dynamic inputs
        series = {k: v for k, v in inputs.items() if k != 'raw_frame' and v is not None}

        for k in list(self.history.keys()):
            if k not in series:
                del self.history[k]

        for k, v in series.items():
            val = _to_float(v)
            if val is not None:
                if k not in self.history:
                    self.history[k] = []
                self.history[k].append(val)
                if len(self.history[k]) > buffer_size:
                    self.history[k] = self.history[k][-buffer_size:]

        # Filter / clamp / normalize each series
        processed = {}
        for key, hist in self.history.items():
            if len(hist) < 2:
                processed[key] = hist
                continue
            data = _apply_filter(list(hist), filter_type, filter_window)
            if clamp_enabled:
                data = [max(threshold_min, min(threshold_max, v)) for v in data]
            data = _apply_normalize(data, normalize)
            processed[key] = data

        # --- Render ---
        img = np.zeros((h, w, 3), dtype=np.uint8) + 20
        margin = 40
        plot_h = h - margin * 2
        plot_w = w - margin * 2

        if show_grid:
            gc = (60, 60, 60)
            for i in range(1, 4):
                yg = int(margin + plot_h * i / 4)
                cv2.line(img, (margin, yg), (w - margin, yg), gc, 1, cv2.LINE_AA)
            for i in range(1, 5):
                xg = int(margin + plot_w * i / 5)
                cv2.line(img, (xg, margin), (xg, h - margin), gc, 1, cv2.LINE_AA)

        if auto_scale:
            all_vals = [v for d in processed.values() for v in d]
            if show_thresholds:
                all_vals.extend([threshold_min, threshold_max])
            if all_vals:
                min_v, max_v = min(all_vals), max(all_vals)
                ym = (max_v - min_v) * 0.1 if max_v != min_v else 1.0
                min_y, max_y = min_v - ym, max_v + ym
                if max_y == min_y:
                    max_y += 1.0

        y_range = (max_y - min_y) or 1.0

        for i, (key, data) in enumerate(processed.items()):
            color = PALETTE[i % len(PALETTE)]
            if len(data) < 2:
                continue

            # Smooth spline curve
            pts = _smooth_pts(data, min_y, max_y, margin, plot_w, plot_h)
            cv2.polylines(img, [pts], False, color, line_width, cv2.LINE_AA)

            # Peak markers (on original data coordinates)
            if show_peaks and len(data) >= 3:
                n_orig = len(data)
                max_idx, min_idx = _detect_peaks(data, peak_window, peak_prominence)
                for idx in max_idx:
                    val = data[idx]
                    xp = int(margin + (idx / (n_orig - 1)) * plot_w) if n_orig > 1 else margin
                    yp = int(np.clip(margin + plot_h - ((val - min_y) / y_range * plot_h), margin, margin + plot_h))
                    cv2.circle(img, (xp, yp), peak_radius, color, -1, cv2.LINE_AA)
                    cv2.circle(img, (xp, yp), peak_radius + 1, (255, 255, 255), 1, cv2.LINE_AA)
                for idx in min_idx:
                    val = data[idx]
                    xp = int(margin + (idx / (n_orig - 1)) * plot_w) if n_orig > 1 else margin
                    yp = int(np.clip(margin + plot_h - ((val - min_y) / y_range * plot_h), margin, margin + plot_h))
                    cv2.drawMarker(img, (xp, yp), color, cv2.MARKER_TILTED_CROSS, peak_radius + 1, 1, cv2.LINE_AA)

            # Legend
            val_str = f"{data[-1]:.2f}"
            cv2.putText(img, f"S{i+1}: {val_str}", (8, 22 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

        # Threshold lines
        if show_thresholds:
            for th, th_label in [(threshold_min, 'min'), (threshold_max, 'max')]:
                th_y = int(np.clip(margin + plot_h - ((th - min_y) / y_range * plot_h), margin, margin + plot_h))
                cv2.line(img, (margin, th_y), (w - margin, th_y), (0, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(img, f"{th_label}:{th:.1f}", (w - 90, th_y - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1, cv2.LINE_AA)

        result = {'main': img}
        for key, data in processed.items():
            if data:
                result[key] = float(data[-1])
        return result
