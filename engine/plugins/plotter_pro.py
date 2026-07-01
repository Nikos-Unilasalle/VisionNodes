import cv2
import numpy as np
import pandas as pd
from registry import NodeProcessor, vision_node

# Reserved input keys that are never treated as plottable series.
_RESERVED_INPUTS = {"raw_frame", "ticks"}
# Result keys the frontend must not mistake for a data series.
_META_KEYS = {"main", "dict", "table", "series_keys", "_available_keys"}

# Fixed BGR colors for the rendered image output (independent of the UI palette).
_IMG_COLORS = [
    (120, 180, 255),  # warm blue
    (120, 235, 140),  # green
    (235, 160, 120),  # blue-ish
    (120, 200, 245),  # amber
    (220, 130, 235),  # magenta
    (200, 220, 130),  # teal
]

DEFAULT_BUFFER = 200


@vision_node(
    type_id="plotter_pro",
    label="Plotter Pro",
    category="visualize",
    icon="Activity",
    description=(
        "Real-time multi-series plotter. Dynamic scalar and dict inputs, a fixed "
        "'ticks' input to synchronise curves, per-series toggles, normalization, and "
        "dict + dataframe outputs. Resizable."
    ),
    resizable=True,
    dynamic_inputs=True,
    inputs=[
        {"id": "ticks", "color": "scalar"},
    ],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "dict", "color": "dict"},
        {"id": "table", "color": "data"},
    ],
    params=[
        {"id": "buffer_size", "label": "History Size", "type": "scalar",
         "min": 10, "max": 2000, "default": DEFAULT_BUFFER},
        {"id": "normalize", "label": "Normalize Curves", "type": "boolean", "default": False},
        {"id": "show_grid", "label": "Show Axes / Grid", "type": "boolean", "default": True},
        {"id": "reset", "label": "Reset History", "type": "trigger"},
        {"id": "_sec_image", "label": "Image Output Size", "type": "section"},
        {"id": "width", "label": "Image Width", "type": "scalar", "min": 100, "max": 1920, "default": 640},
        {"id": "height", "label": "Image Height", "type": "scalar", "min": 100, "max": 1080, "default": 360},
    ],
)
class PlotterProNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.history = {}       # series key -> list[float]
        self.ticks = []         # list[float] parallel x axis
        self._tick_counter = 0

    # ── value coercion ────────────────────────────────────────────────
    def _to_float(self, v):
        """Coerce a scalar-ish value to float, or None if not numeric."""
        if v is None:
            return None
        if isinstance(v, bool):
            return float(v)
        if isinstance(v, (int, float, np.number)):
            return float(v)
        if isinstance(v, (list, np.ndarray)):
            arr = np.asarray(v, dtype=object).ravel()
            if arr.size == 0:
                return None
            try:
                return float(np.nanmean(arr.astype(float)))
            except (ValueError, TypeError):
                return float(arr.size)
        return None

    def _expand(self, key, value):
        """Yield (series_key, float_value) pairs from one input value.

        Dicts expand into one series per numeric member; scalars/lists become a
        single series named after the port.
        """
        if isinstance(value, dict):
            for sub, sub_v in value.items():
                f = self._to_float(sub_v)
                if f is not None:
                    yield f"{key}:{sub}", f
        else:
            f = self._to_float(value)
            if f is not None:
                yield key, f

    # ── main entry ────────────────────────────────────────────────────
    def process(self, inputs, params):
        # Defensive re-init (processors may be reused across graph edits).
        if not hasattr(self, "history") or self.history is None:
            self.history = {}
        if not hasattr(self, "ticks") or self.ticks is None:
            self.ticks = []

        buffer_size = max(2, int(params.get("buffer_size", DEFAULT_BUFFER)))
        normalize = bool(params.get("normalize", False))
        show_grid = bool(params.get("show_grid", True))
        w = int(params.get("width", 640))
        h = int(params.get("height", 360))

        # Reset trigger — clear everything and redraw an empty frame.
        if params.get("reset"):
            self.history = {}
            self.ticks = []
            self._tick_counter = 0

        # Collect this frame's series values from every non-reserved input.
        frame_vals = {}
        for key, value in inputs.items():
            if key in _RESERVED_INPUTS or value is None:
                continue
            for series_key, f in self._expand(key, value):
                frame_vals[series_key] = f

        # Prune series whose input is no longer connected/present.
        for k in list(self.history.keys()):
            if k not in frame_vals:
                del self.history[k]

        # Fill the history from the left, then FREEZE when full — no sliding
        # window. Once every connected series reaches buffer_size the plot stops
        # updating. Toggling a series off only hides it from outputs; its history
        # stays continuous so re-enabling resumes seamlessly.
        ticks_input = self._to_float(inputs.get("ticks"))
        grew = False
        for k, f in frame_vals.items():
            hist = self.history.setdefault(k, [])
            if len(hist) < buffer_size:
                hist.append(f)
                grew = True
        if grew:
            if ticks_input is not None:
                tick_val = ticks_input
            else:
                tick_val = float(self._tick_counter)
                self._tick_counter += 1
            self.ticks.append(tick_val)

        def is_active(k):
            return params.get(f"active_{k}", True) is not False

        img = self._render(w, h, normalize, show_grid, params, buffer_size)

        result = {"main": img}

        # Emit every series' latest value so the in-node React chart can track it,
        # plus the current x (tick) so the chart shares a synchronized time axis and
        # can freeze once full.
        for k, hist in self.history.items():
            if hist:
                result[k] = hist[-1]
        result["_tick"] = self.ticks[-1] if self.ticks else 0.0

        # Grouped dict — active series only.
        result["dict"] = {k: hist[-1] for k, hist in self.history.items()
                          if hist and is_active(k)}
        # Keys list drives the inspector's per-series enable toggles (all connected).
        result["series_keys"] = list(frame_vals.keys())
        result["_available_keys"] = list(frame_vals.keys())
        # DataFrame of aligned histories — active series only.
        result["table"] = self._build_table(is_active)
        return result

    # ── dataframe ─────────────────────────────────────────────────────
    def _build_table(self, is_active):
        series = {k: h for k, h in self.history.items() if h and is_active(k)}
        if not series:
            return pd.DataFrame()
        n = max(len(h) for h in series.values())
        data = {}
        if len(self.ticks) == n:
            data["tick"] = list(self.ticks)
        for k, hist in series.items():
            # Left-pad shorter series with NaN so all columns align on the right.
            pad = [np.nan] * (n - len(hist))
            data[k] = pad + list(hist)
        return pd.DataFrame(data)

    # ── image rendering ───────────────────────────────────────────────
    def _render(self, w, h, normalize, show_grid, params, buffer_size):
        img = np.full((h, w, 3), 22, dtype=np.uint8)

        pad_l, pad_r, pad_t, pad_b = 8, 8, 10, 16
        plot_w = max(1, w - pad_l - pad_r)
        plot_h = max(1, h - pad_t - pad_b)

        active = {k: hist for k, hist in self.history.items()
                  if hist and params.get(f"active_{k}", True) is not False}

        # X positions are anchored to the buffer, so points fill from the left and
        # the axis maps directly to tick values.
        x_span = max(1, buffer_size - 1)

        def tick_at(idx):
            return self.ticks[idx] if 0 <= idx < len(self.ticks) else idx

        if show_grid:
            grid = (44, 44, 44)
            for i in range(0, 5):
                y = pad_t + int(plot_h * i / 4)
                cv2.line(img, (pad_l, y), (pad_l + plot_w, y), grid, 1, cv2.LINE_AA)
            for i in range(0, 5):
                x = pad_l + int(plot_w * i / 4)
                cv2.line(img, (x, pad_t), (x, pad_t + plot_h), grid, 1, cv2.LINE_AA)
            axis = (90, 90, 90)
            cv2.line(img, (pad_l, pad_t + plot_h), (pad_l + plot_w, pad_t + plot_h), axis, 1, cv2.LINE_AA)
            cv2.line(img, (pad_l, pad_t), (pad_l, pad_t + plot_h), axis, 1, cv2.LINE_AA)
            # X-axis value labels along the bottom (5 ticks across the buffer).
            for i in range(0, 5):
                idx = int(round(i * x_span / 4))
                x = pad_l + int(plot_w * i / 4)
                label = f"{tick_at(idx):.4g}"
                (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.3, 1)
                tx = int(np.clip(x - tw // 2, 0, w - tw))
                cv2.putText(img, label, (tx, h - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (140, 140, 140), 1, cv2.LINE_AA)

        if not active:
            cv2.putText(img, "connect data", (pad_l + 6, pad_t + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1, cv2.LINE_AA)
            return img

        # Shared Y range across all active series (unless normalizing per-series).
        all_vals = [v for hist in active.values() for v in hist]
        g_min, g_max = (min(all_vals), max(all_vals)) if all_vals else (0.0, 1.0)
        if g_max == g_min:
            g_max += 1.0

        legend_y = pad_t + 4
        for i, (k, hist) in enumerate(active.items()):
            color = _IMG_COLORS[i % len(_IMG_COLORS)]

            if normalize:
                lo, hi = min(hist), max(hist)
                rng = (hi - lo) or 1.0
                norm = [(v - lo) / rng for v in hist]
                v_min, v_range = 0.0, 1.0
            else:
                norm = hist
                v_min, v_range = g_min, (g_max - g_min)

            if len(norm) >= 2:
                pts = []
                for j, v in enumerate(norm):
                    x = pad_l + int(j * plot_w / x_span)
                    y = pad_t + plot_h - int((v - v_min) / v_range * plot_h)
                    pts.append([x, int(np.clip(y, pad_t, pad_t + plot_h))])
                cv2.polylines(img, [np.array(pts, np.int32)], False, color, 1, cv2.LINE_AA)

            # Legend: series name + latest (non-rounded) value, in series color.
            label = f"{k}: {hist[-1]:.4g}"
            legend_y += 14
            cv2.putText(img, label, (pad_l + 6, legend_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)

        return img
