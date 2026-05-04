import cv2
import numpy as np
from registry import NodeProcessor, vision_node


def _hex_to_bgr(hex_color: str):
    h = hex_color.lstrip('#')
    r = int(h[0:2], 16) if len(h) >= 2 else 255
    g = int(h[2:4], 16) if len(h) >= 4 else 100
    b = int(h[4:6], 16) if len(h) >= 6 else 100
    return (b, g, r)


def _apply_filter(data, filter_type, window):
    """filter_type: 0=None, 1=MovingAvg, 2=Median, 3=EMA, 4=Gaussian"""
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
    """norm_type: 0=None, 1=MinMax, 2=ZScore, 3=Robust"""
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
    """Return (max_indices, min_indices) for local extrema using scipy."""
    if len(data) < 3:
        return [], []
    from scipy.signal import find_peaks
    arr = np.array(data, dtype=np.float64)
    # Maxima
    peaks_max, _ = find_peaks(arr, distance=window, prominence=prominence)
    # Minima (inverted maxima)
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


@vision_node(
    type_id="plotter_pro",
    label="Plotter Pro",
    category=["visualize", "analysis"],
    icon="Activity",
    description="Advanced dual-series plotter with filtering, thresholding, normalization, and peak detection.",
    inputs=[
        {"id": "series_a", "color": "scalar"},
        {"id": "series_b", "color": "scalar"},
    ],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "a", "color": "scalar"},
        {"id": "b", "color": "scalar"},
    ],
    params=[
        # --- Controls ---
        {"id": "reset", "label": "Reset History", "type": "trigger", "default": 0},
        # --- Display ---
        {"id": "buffer_size", "label": "History Size", "type": "scalar", "min": 10, "max": 2000, "default": 300},
        {"id": "min_y", "label": "Y-Axis Min", "type": "float", "default": 0},
        {"id": "max_y", "label": "Y-Axis Max", "type": "float", "default": 100},
        {"id": "auto_scale", "label": "Auto-Scale", "type": "boolean", "default": True},
        {"id": "line_width", "label": "Line Width", "type": "scalar", "min": 1, "max": 6, "default": 2},
        {"id": "show_grid", "label": "Show Grid", "type": "boolean", "default": True},
        # --- Filtering ---
        {"id": "filter_type", "label": "Filter", "type": "enum", "options": ["None", "Moving Average", "Median", "Low-Pass (EMA)", "Gaussian"], "default": 0},
        {"id": "filter_window", "label": "Filter Window", "type": "scalar", "min": 2, "max": 100, "default": 5},
        # --- Thresholding ---
        {"id": "threshold_min", "label": "Threshold Min", "type": "float", "default": 0.0},
        {"id": "threshold_max", "label": "Threshold Max", "type": "float", "default": 255.0},
        {"id": "clamp_enabled", "label": "Clamp Values", "type": "boolean", "default": False},
        {"id": "show_thresholds", "label": "Show Thresholds", "type": "boolean", "default": True},
        # --- Normalization ---
        {"id": "normalize", "label": "Normalize", "type": "enum", "options": ["None", "Min-Max [0,1]", "Z-Score", "Robust (IQR)"], "default": 0},
        # --- Peak detection ---
        {"id": "show_peaks", "label": "Show Peaks", "type": "boolean", "default": False},
        {"id": "peak_window", "label": "Peak Distance", "type": "scalar", "min": 2, "max": 100, "default": 10},
        {"id": "peak_prominence", "label": "Peak Prominence", "type": "float", "min": 0, "max": 100, "default": 0.5},
        {"id": "peak_radius", "label": "Peak Marker Size", "type": "scalar", "min": 2, "max": 10, "default": 4},
        # --- Colors ---
        {"id": "color_a", "label": "Color A", "type": "color", "default": "#ff6464"},
        {"id": "color_b", "label": "Color B", "type": "color", "default": "#64ff64"},
    ]
)
class PlotterProNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.history = {}

    def process(self, inputs, params):
        if not hasattr(self, 'history') or self.history is None:
            self.history = {}

        # --- Read params ---
        reset = int(params.get('reset', 0))
        buffer_size = int(params.get('buffer_size', 300))
        min_y = float(params.get('min_y', 0))
        max_y = float(params.get('max_y', 100))
        auto_scale = bool(params.get('auto_scale', True))
        w, h = 640, 360  # Default resolution
        line_width = int(params.get('line_width', 2))
        show_grid = bool(params.get('show_grid', True))

        if reset == 1:
            self.history = {}

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

        color_a = _hex_to_bgr(str(params.get('color_a', '#ff6464')))
        color_b = _hex_to_bgr(str(params.get('color_b', '#64ff64')))

        # --- Collect fixed inputs ---
        raw_a = self._to_float(inputs.get('series_a'))
        raw_b = self._to_float(inputs.get('series_b'))

        # Maintain history
        for key, val in [('series_a', raw_a), ('series_b', raw_b)]:
            if val is None:
                continue
            if key not in self.history:
                self.history[key] = []
            self.history[key].append(val)
            if len(self.history[key]) > buffer_size:
                self.history[key] = self.history[key][-buffer_size:]

        # Prune disconnected
        active = {k for k, v in [('series_a', raw_a), ('series_b', raw_b)] if v is not None}
        for k in list(self.history.keys()):
            if k not in active:
                del self.history[k]

        # --- Process each series ---
        processed = {}
        for key in ['series_a', 'series_b']:
            hist = self.history.get(key, [])
            if len(hist) < 2:
                processed[key] = hist
                continue
            data = list(hist)

            # 1. Filter
            data = _apply_filter(data, filter_type, filter_window)
            # 2. Clamp
            if clamp_enabled:
                data = [max(threshold_min, min(threshold_max, v)) for v in data]
            # 3. Normalize
            data = _apply_normalize(data, normalize)
            processed[key] = data

        # --- Render ---
        img = np.zeros((h, w, 3), dtype=np.uint8) + 20

        margin = 40
        plot_h = h - margin * 2
        plot_w = w - margin * 2

        # Grid
        if show_grid:
            gc = (60, 60, 60)
            for i in range(1, 4):
                y = int(margin + plot_h * i / 4)
                cv2.line(img, (margin, y), (w - margin, y), gc, 1, cv2.LINE_AA)
            for i in range(1, 5):
                x = int(margin + plot_w * i / 5)
                cv2.line(img, (x, margin), (x, h - margin), gc, 1, cv2.LINE_AA)

        # Auto-scale across both series
        if auto_scale:
            all_vals = []
            for data in processed.values():
                all_vals.extend(data)
            if show_thresholds:
                # Force thresholds to be visible in autoscale
                all_vals.extend([threshold_min, threshold_max])
            
            if all_vals:
                min_y_data = min(all_vals)
                max_y_data = max(all_vals)
                # Add a 10% margin
                y_margin = (max_y_data - min_y_data) * 0.1 if max_y_data != min_y_data else 1.0
                min_y = min_y_data - y_margin
                max_y = max_y_data + y_margin
                if max_y == min_y:
                    max_y += 1.0

        y_range = max_y - min_y
        if y_range == 0:
            y_range = 1.0

        series_cfgs = [
            ('series_a', color_a, 'A'),
            ('series_b', color_b, 'B'),
        ]

        latest = {}

        for key, color, label in series_cfgs:
            data = processed.get(key, [])
            if len(data) < 2:
                continue
            latest[label] = data[-1]

            # Draw polyline
            pts = []
            for j, val in enumerate(data):
                x_px = int(margin + j * plot_w / (buffer_size - 1)) if buffer_size > 1 else margin
                y_px = int(margin + plot_h - ((val - min_y) / y_range * plot_h))
                pts.append([x_px, int(np.clip(y_px, margin, margin + plot_h))])
            cv2.polylines(img, [np.array(pts, np.int32)], False, color, line_width, cv2.LINE_AA)

            # Peaks
            if show_peaks and len(data) >= 3:
                max_idx, min_idx = _detect_peaks(data, peak_window, peak_prominence)
                for idx in max_idx:
                    val = data[idx]
                    x_px = int(margin + idx * plot_w / (buffer_size - 1)) if buffer_size > 1 else margin
                    y_px = int(margin + plot_h - ((val - min_y) / y_range * plot_h))
                    y_px = int(np.clip(y_px, margin, margin + plot_h))
                    cv2.circle(img, (x_px, y_px), peak_radius, color, -1, cv2.LINE_AA)
                    cv2.circle(img, (x_px, y_px), peak_radius + 1, (255, 255, 255), 1, cv2.LINE_AA)
                for idx in min_idx:
                    val = data[idx]
                    x_px = int(margin + idx * plot_w / (buffer_size - 1)) if buffer_size > 1 else margin
                    y_px = int(margin + plot_h - ((val - min_y) / y_range * plot_h))
                    y_px = int(np.clip(y_px, margin, margin + plot_h))
                    cv2.drawMarker(img, (x_px, y_px), color, cv2.MARKER_TILTED_CROSS, peak_radius + 1, 1, cv2.LINE_AA)

        # Threshold lines
        if show_thresholds:
            for th, th_label in [(threshold_min, 'min'), (threshold_max, 'max')]:
                th_y = int(margin + plot_h - ((th - min_y) / y_range * plot_h))
                th_y = int(np.clip(th_y, margin, margin + plot_h))
                # Brighter yellow (0, 255, 255)
                cv2.line(img, (margin, th_y), (w - margin, th_y), (0, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(img, f"{th_label}:{th:.1f}", (w - 90, th_y - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1, cv2.LINE_AA)

        # Legend
        for i, (key, color, label) in enumerate(series_cfgs):
            data = processed.get(key, [])
            val_str = f"{data[-1]:.2f}" if data else "--"
            cv2.putText(img, f"{label}: {val_str}", (8, 22 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

        result = {'main': img}
        if latest:
            result['a'] = latest.get('A', 0.0)
            result['b'] = latest.get('B', 0.0)
        
        # Also send peaks to frontend for better visualization
        if show_peaks:
            for key, p_key in [('series_a', 'peaks_a'), ('series_b', 'peaks_b')]:
                data = processed.get(key, [])
                if len(data) >= 3:
                    ma, mi = _detect_peaks(data, peak_window, peak_prominence)
                    result[p_key] = {'max': ma, 'min': mi}
        
        return result

    def _to_float(self, v):
        return _to_float(v)
