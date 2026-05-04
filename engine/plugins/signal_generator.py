"""
Signal Generator + Clock — synthetic waveforms, noise, and a pure time source.
Both nodes register as REALTIME so the engine ticks at 30 fps even without a camera.
"""

import math
import time
import numpy as np
from registry import vision_node, NodeProcessor


# ── Clock ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='signal_clock',
    label='Clock',
    category='signal',
    icon='Clock',
    description="Pure time source. No inputs needed — forces 30 fps engine ticking. Use as modulation source or pipeline driver.",
    inputs=[],
    outputs=[
        {'id': 't',      'color': 'scalar'},
        {'id': 'ms',     'color': 'scalar'},
        {'id': 'frame',  'color': 'scalar'},
        {'id': 'sin_t',  'color': 'scalar'},
        {'id': 'cos_t',  'color': 'scalar'},
    ],
    params=[
        {'id': 'speed', 'label': 'Speed (%)', 'min': 1, 'max': 1000, 'step': 1, 'default': 100},
        {'id': 'reset', 'label': 'Reset',     'type': 'trigger'},
    ]
)
class ClockNode(NodeProcessor):
    def __init__(self):
        self._t0    = time.time()
        self._frame = 0

    def process(self, inputs, params):
        if params.get('reset'):
            self._t0    = time.time()
            self._frame = 0

        speed = max(1, int(params.get('speed', 100))) / 100.0
        t     = (time.time() - self._t0) * speed
        self._frame += 1

        return {
            't':            t,
            'ms':           t * 1000.0,
            'frame':        float(self._frame),
            'sin_t':        math.sin(t),
            'cos_t':        math.cos(t),
            'display_text': f"t={t:.3f}s  frame={self._frame}",
        }

_WAVEFORM_NAMES = ['Sine', 'Square', 'Triangle', 'Sawtooth', 'White Noise', 'Random Walk']


@vision_node(
    type_id='signal_generator',
    label='Signal Generator',
    category='signal',
    icon='Waves',
    description="Generates synthetic waveforms and noise. Useful for testing signal pipelines without physical sensors.",
    inputs=[
        {'id': 'freq_mod', 'color': 'scalar'},
        {'id': 'amp_mod',  'color': 'scalar'},
    ],
    outputs=[
        {'id': 'value', 'color': 'scalar'},
        {'id': 't',     'color': 'scalar'},
    ],
    params=[
        {
            'id': 'waveform', 'label': 'Waveform',
            'type': 'enum',
            'options': _WAVEFORM_NAMES,
            'default': 0,
        },
        {'id': 'frequency', 'label': 'Frequency (Hz)', 'min': 0,   'max': 100,   'step': 1,    'default': 1},
        {'id': 'freq_fine', 'label': 'Fine (mHz)',     'min': 0,   'max': 999,   'step': 1,    'default': 0},
        {'id': 'amplitude', 'label': 'Amplitude',      'min': 0,   'max': 10000, 'step': 1,    'default': 100},
        {'id': 'offset',    'label': 'Offset',         'min': -10000, 'max': 10000, 'step': 1, 'default': 0},
        {'id': 'phase',     'label': 'Phase (deg)',    'min': 0,   'max': 359,   'step': 1,    'default': 0},
        {'id': 'duty',      'label': 'Duty Cycle (%)', 'min': 1,   'max': 99,    'step': 1,    'default': 50},
        {'id': 'rw_step',   'label': 'Walk Step (%)', 'min': 1,   'max': 100,   'step': 1,    'default': 5},
        {'id': 'seed',      'label': 'Seed (-1=off)',  'min': -1,  'max': 9999,  'step': 1,    'default': -1},
    ]
)
class SignalGeneratorNode(NodeProcessor):
    def __init__(self):
        self._t0       = time.time()
        self._rw_state = 0.0
        self._rng      = None
        self._seed     = -2  # sentinel: force init on first process()

    def process(self, inputs, params):
        waveform = int(params.get('waveform', 0))
        freq     = float(params.get('frequency', 1)) + float(params.get('freq_fine', 0)) / 1000.0
        freq     = max(0.0001, freq)
        amp      = float(params.get('amplitude', 100)) / 100.0
        offset   = float(params.get('offset', 0))      / 100.0
        phase_offset = float(params.get('phase', 0)) / 360.0
        duty     = float(params.get('duty', 50)) / 100.0
        rw_step  = float(params.get('rw_step', 5)) / 100.0
        seed     = int(params.get('seed', -1))

        # Input modulation overrides params
        freq_mod = inputs.get('freq_mod')
        amp_mod  = inputs.get('amp_mod')
        if freq_mod is not None:
            freq = max(0.0001, float(freq_mod))
        if amp_mod is not None:
            amp = float(amp_mod)

        # RNG management — recreate only when seed changes
        if seed != self._seed:
            self._seed = seed
            self._rng  = np.random.default_rng(seed if seed >= 0 else None)

        t = time.time() - self._t0
        p = (freq * t + phase_offset) % 1.0  # normalized phase in [0, 1)

        if waveform == 0:    # Sine
            v = math.sin(2.0 * math.pi * p)

        elif waveform == 1:  # Square
            v = 1.0 if p < duty else -1.0

        elif waveform == 2:  # Triangle
            v = 1.0 - 4.0 * abs(p - 0.5)

        elif waveform == 3:  # Sawtooth (rising)
            v = 2.0 * p - 1.0

        elif waveform == 4:  # White Noise
            v = float(self._rng.uniform(-1.0, 1.0))

        else:                # Random Walk
            self._rw_state += float(self._rng.normal(0.0, rw_step))
            self._rw_state  = max(-1.0, min(1.0, self._rw_state))
            v = self._rw_state

        value = amp * v + offset
        name  = _WAVEFORM_NAMES[waveform] if waveform < len(_WAVEFORM_NAMES) else '?'
        return {
            'value':        value,
            't':            t,
            'display_text': f"{name}  {freq:.3f} Hz → {value:.4f}",
        }
