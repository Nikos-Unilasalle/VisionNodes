import numpy as np
from registry import vision_node, NodeProcessor

_MODES = ['Running Mean', 'Running Max', 'Running Min', 'Running Std', 'Temporal Diff']

_MODE_STD = 3          # index of 'Running Std' in _MODES
_U8_MAX = 255.0        # full-scale of the uint8 `main` output
_DIFF_GAIN = 4.0       # temporal-diff display gain (legacy)
_EPS = 1e-8


@vision_node(
    type_id='sci_frame_accumulator',
    label='Frame Accumulator',
    category='measure',
    icon='Film',
    description=(
        "Accumulate frames over time: mean (noise reduction / Monte-Carlo P), std "
        "(motion / uncertainty map), temporal diff, running max/min. Cumulative mode "
        "aggregates ALL frames since reset (stable N-sample estimate); window mode "
        "keeps only the last W frames (sliding average)."
    ),
    inputs=[
        {'id': 'image', 'color': 'any'},
        {'id': 'tick',  'color': 'scalar', 'label': 'Upstream tick (auto-reset on 0)'},
    ],
    outputs=[
        {'id': 'main',        'color': 'image',  'label': 'Result'},
        {'id': 'frame_count', 'color': 'scalar', 'label': 'Frames accumulated'},
        {'id': 'done',        'color': 'scalar', 'label': 'Reached Target N (0/1)'},
        {'id': 'scale',       'color': 'scalar', 'label': 'Value of main=255, input units'},
    ],
    params=[
        {'id': 'mode',       'label': 'Mode',            'type': 'enum', 'options': _MODES, 'default': 0},
        {'id': 'cumulative', 'label': 'Cumulative (all frames since reset)', 'type': 'bool', 'default': True},
        {'id': 'target_n',   'label': 'Target N (0 = unlimited)', 'type': 'int', 'default': 0, 'min': 0, 'max': 1_000_000, 'step': 1},
        {'id': 'window',     'label': 'Window (frames, sliding mode)', 'type': 'int', 'default': 16, 'min': 2, 'max': 128,
         'show_if': {'param': 'cumulative', 'value': False}},
        {'id': 'normalize',  'label': 'Stretch std to 0-255 (display); off = σ in input units',
         'type': 'bool', 'default': True, 'show_if': {'param': 'mode', 'value': 3}},
        {'id': 'reset',      'label': '↺ Reset Buffer', 'type': 'trigger', 'default': 0},
    ],
)
class FrameAccumulatorNode(NodeProcessor):
    """Streaming frame aggregator.

    Cumulative mode keeps O(1) memory via Welford accumulators (count, running
    mean, running M2, running max/min, last frame) — it never stores N full
    frames, so a 100-realisation Monte-Carlo over full Sentinel-2 scenes stays
    light. Sliding-window mode keeps the last W frames in a buffer.

    Recovering physical values from `main`
    -------------------------------------
    `main` is uint8, so every mode also emits `scale` = the input-unit value that
    `main == 255` represents::

        value_in_input_units = main / 255 * scale

    All modes except Running Std carry values directly, so `scale == 255`. Running
    Std with ``normalize=True`` (the legacy display default) stretches the map by
    its own per-tick maximum, and `scale` is that maximum — WITHOUT it the map is a
    purely relative quantity whose maximum is pinned to 255 on every tick, so it
    cannot decrease as N grows and any downstream SE = <σ>/sqrt(N) is wrong by an
    unreported, run-dependent factor. Monte-Carlo consumers that need σ in
    probability units should set ``normalize=False`` and read::

        sigma_P = main * scale / 255**2      # frames in 0-255 → σ in [0, 0.5]
    """

    def __init__(self):
        self._buffer = []          # sliding-window mode
        self._count = 0            # cumulative mode
        self._mean = None
        self._m2 = None
        self._max = None
        self._min = None
        self._prev = None          # previous frame (temporal diff)
        self._last_reset = 0.0
        self._last_tick = None

    def _reset_state(self):
        self._buffer = []
        self._count = 0
        self._mean = None
        self._m2 = None
        self._max = None
        self._min = None
        self._prev = None

    @staticmethod
    def _std_to_u8(s: np.ndarray, normalize: bool) -> tuple[np.ndarray, float]:
        """Map a std map to the uint8 output range, returning (result, scale).

        `scale` is the input-unit value that 255 represents, so a consumer always
        recovers physical units with ``main / 255 * scale`` regardless of the
        normalize setting.
        """
        if not normalize:
            return s, _U8_MAX
        peak = float(s.max())
        if peak <= 0.0:
            return s, _U8_MAX
        return s / (peak + _EPS) * _U8_MAX, peak

    @staticmethod
    def _as_u8(arr: np.ndarray) -> np.ndarray:
        """Round (never truncate) before the uint8 cast.

        Truncation biases every accumulated value down by up to 1/255 — on a
        Monte-Carlo P map that is a systematic ~0.002 probability bias.
        """
        return np.rint(arr).clip(0, _U8_MAX).astype(np.uint8)

    def _to_float(self, img):
        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)
        return img.astype(np.float32)

    def process(self, inputs, params):
        img = inputs.get('image')

        # Edge-triggered reset: button press (trigger pulses 0→1) clears all state.
        do_reset = float(params.get('reset', 0) or 0)
        if do_reset > 0.5 and self._last_reset <= 0.5:
            self._reset_state()
        self._last_reset = do_reset

        # Auto-reset: when the upstream Monte-Carlo driver restarts, its tick output
        # drops back to 0 — clear so a single upstream Reset re-runs the whole chain.
        tick = inputs.get('tick')
        if tick is not None:
            tick = float(tick)
            if self._last_tick is not None and tick < self._last_tick:
                self._reset_state()
            self._last_tick = tick

        if img is None:
            return {'main': None, 'frame_count': self._count or len(self._buffer),
                    'done': 0.0, 'scale': _U8_MAX}

        mode        = int(params.get('mode', 0))
        cumulative  = bool(params.get('cumulative', True))
        target_n    = int(params.get('target_n', 0) or 0)
        normalize   = bool(params.get('normalize', True))

        if cumulative:
            return self._process_cumulative(img, mode, target_n, normalize)
        return self._process_window(img, mode, params, normalize)

    # ---- cumulative (O(1) memory, stable N-sample estimate) -------------------
    def _process_cumulative(self, img, mode, target_n, normalize=True):
        reached = target_n > 0 and self._count >= target_n
        if not reached:
            f = self._to_float(img)
            self._count += 1
            if self._mean is None:
                self._mean = f.copy()
                self._m2 = np.zeros_like(f)
                self._max = f.copy()
                self._min = f.copy()
            else:
                delta = f - self._mean
                self._mean += delta / self._count
                self._m2 += delta * (f - self._mean)
                np.maximum(self._max, f, out=self._max)
                np.minimum(self._min, f, out=self._min)
            self._diff = np.abs(f - self._prev) * _DIFF_GAIN if self._prev is not None else f
            self._prev = f
            reached = target_n > 0 and self._count >= target_n

        if self._mean is None:
            return {'main': None, 'frame_count': 0, 'done': 0.0, 'scale': _U8_MAX}

        scale = _U8_MAX
        if mode == 0:
            result = self._mean
        elif mode == 1:
            result = self._max
        elif mode == 2:
            result = self._min
        elif mode == _MODE_STD:
            s = np.sqrt(self._m2 / max(self._count, 1))
            result, scale = self._std_to_u8(s, normalize)
        else:
            result = self._diff

        return {
            'main':        self._as_u8(result),
            'frame_count': self._count,
            'done':        1.0 if reached else 0.0,
            'scale':       float(scale),
        }

    # ---- sliding window (last W frames) ---------------------------------------
    def _process_window(self, img, mode, params, normalize=True):
        window = int(params.get('window', 16))
        self._buffer.append(self._to_float(img))
        if len(self._buffer) > window:
            self._buffer.pop(0)

        stack = np.stack(self._buffer, axis=0)
        scale = _U8_MAX
        if mode == 0:
            result = np.mean(stack, axis=0)
        elif mode == 1:
            result = np.max(stack, axis=0)
        elif mode == 2:
            result = np.min(stack, axis=0)
        elif mode == _MODE_STD:
            result, scale = self._std_to_u8(np.std(stack, axis=0), normalize)
        elif len(self._buffer) >= 2:
            result = np.abs(self._buffer[-1] - self._buffer[-2]) * _DIFF_GAIN
        else:
            result = stack[0]

        return {
            'main':        self._as_u8(result),
            'frame_count': len(self._buffer),
            'done':        0.0,
            'scale':       float(scale),
        }
