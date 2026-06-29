import numpy as np
from registry import vision_node, NodeProcessor

_MODES = ['Running Mean', 'Running Max', 'Running Min', 'Running Std', 'Temporal Diff']


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
    ],
    params=[
        {'id': 'mode',       'label': 'Mode',            'type': 'enum', 'options': _MODES, 'default': 0},
        {'id': 'cumulative', 'label': 'Cumulative (all frames since reset)', 'type': 'bool', 'default': True},
        {'id': 'target_n',   'label': 'Target N (0 = unlimited)', 'type': 'int', 'default': 0, 'min': 0, 'max': 1_000_000, 'step': 1},
        {'id': 'window',     'label': 'Window (frames, sliding mode)', 'type': 'int', 'default': 16, 'min': 2, 'max': 128,
         'show_if': {'param': 'cumulative', 'value': False}},
        {'id': 'reset',      'label': '↺ Reset Buffer', 'type': 'trigger', 'default': 0},
    ],
)
class FrameAccumulatorNode(NodeProcessor):
    """Streaming frame aggregator.

    Cumulative mode keeps O(1) memory via Welford accumulators (count, running
    mean, running M2, running max/min, last frame) — it never stores N full
    frames, so a 100-realisation Monte-Carlo over full Sentinel-2 scenes stays
    light. Sliding-window mode keeps the last W frames in a buffer.
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
            return {'main': None, 'frame_count': self._count or len(self._buffer), 'done': 0.0}

        mode        = int(params.get('mode', 0))
        cumulative  = bool(params.get('cumulative', True))
        target_n    = int(params.get('target_n', 0) or 0)

        if cumulative:
            return self._process_cumulative(img, mode, target_n)
        return self._process_window(img, mode, params)

    # ---- cumulative (O(1) memory, stable N-sample estimate) -------------------
    def _process_cumulative(self, img, mode, target_n):
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
            self._diff = np.abs(f - self._prev) * 4.0 if self._prev is not None else f
            self._prev = f
            reached = target_n > 0 and self._count >= target_n

        if self._mean is None:
            return {'main': None, 'frame_count': 0, 'done': 0.0}

        if mode == 0:
            result = self._mean
        elif mode == 1:
            result = self._max
        elif mode == 2:
            result = self._min
        elif mode == 3:
            s = np.sqrt(self._m2 / max(self._count, 1))
            m = float(s.max())
            result = (s / (m + 1e-8) * 255) if m > 0 else s
        else:
            result = self._diff

        return {
            'main':        result.clip(0, 255).astype(np.uint8),
            'frame_count': self._count,
            'done':        1.0 if reached else 0.0,
        }

    # ---- sliding window (last W frames) ---------------------------------------
    def _process_window(self, img, mode, params):
        window = int(params.get('window', 16))
        self._buffer.append(self._to_float(img))
        if len(self._buffer) > window:
            self._buffer.pop(0)

        stack = np.stack(self._buffer, axis=0)
        if mode == 0:
            result = np.mean(stack, axis=0)
        elif mode == 1:
            result = np.max(stack, axis=0)
        elif mode == 2:
            result = np.min(stack, axis=0)
        elif mode == 3:
            s = np.std(stack, axis=0)
            m = float(s.max())
            result = (s / (m + 1e-8) * 255) if m > 0 else s
        else:
            result = np.abs(self._buffer[-1] - self._buffer[-2]) * 4.0 if len(self._buffer) >= 2 else stack[0]

        return {
            'main':        result.clip(0, 255).astype(np.uint8),
            'frame_count': len(self._buffer),
            'done':        0.0,
        }
