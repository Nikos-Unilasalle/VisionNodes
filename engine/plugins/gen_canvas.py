import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_PATTERNS = [
    'solid', 'center_dot', 'white_noise', 'value_noise',
    'checkerboard', 'stripes_h', 'stripes_v', 'dots_grid',
    'gradient_h', 'gradient_v', 'gradient_radial', 'rings',
]

@vision_node(
    type_id='gen_canvas',
    label='Canvas',
    category='input',
    icon='Square',
    description=(
        "Generates a procedural float32 image. Patterns: solid fill, center dot, "
        "noise, value noise, checkerboard, stripes, dots, gradients, rings. "
        "Static by default (caches result); enable Animate for live generation. "
        "Designed for reaction-diffusion init and generative pipelines."
    ),
    inputs=[
        {'id': 'reset', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'image', 'color': 'image'},
    ],
    params=[
        {'id': 'pattern',    'label': 'Pattern',      'type': 'enum',   'options': _PATTERNS, 'default': 0},
        {'id': 'width',      'label': 'Width',        'type': 'int',    'default': 512,  'min': 16,    'max': 2048},
        {'id': 'height',     'label': 'Height',       'type': 'int',    'default': 512,  'min': 16,    'max': 2048},
        {'id': '_sec_value_range', 'label': 'Value Range', 'type': 'section'},
        {'id': 'value_min',  'label': 'Value Min',    'type': 'float',  'default': 0.0,  'min': 0.0,   'max': 1.0,  'step': 0.01},
        {'id': 'value_max',  'label': 'Value Max',    'type': 'float',  'default': 1.0,  'min': 0.0,   'max': 1.0,  'step': 0.01},
        {'id': '_sec_pattern_config', 'label': 'Pattern Config', 'type': 'section'},
        {'id': 'seed_size',  'label': 'Size / Radius','type': 'float',  'default': 0.05, 'min': 0.001, 'max': 0.5,  'step': 0.005},
        {'id': 'tile_count', 'label': 'Tile Count',   'type': 'int',    'default': 8,    'min': 1,     'max': 64},
        {'id': 'octaves',    'label': 'Octaves',      'type': 'int',    'default': 4,    'min': 1,     'max': 8},
        {'id': 'noise_scale','label': 'Noise Scale',  'type': 'float',  'default': 0.1,  'min': 0.001, 'max': 1.0,  'step': 0.005},
        {'id': 'seed',       'label': 'Random Seed',  'type': 'int',    'default': 42,   'min': 0,     'max': 9999},
        {'id': '_sec_control', 'label': 'Control', 'type': 'section'},
        {'id': 'animate',    'label': 'Animate',      'type': 'bool',   'default': False},
        {'id': 'regenerate', 'label': 'Regenerate',   'type': 'trigger','default': 0},
    ]
)
class CanvasNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._canvas: np.ndarray | None = None
        self._prev_reset = 0.0
        self._prev_regen = 0
        self._frame = 0

    def process(self, inputs, params):
        reset_raw = inputs.get('reset', 0)
        try:
            reset = float(reset_raw) if reset_raw is not None else 0.0
        except (TypeError, ValueError):
            reset = 0.0

        regen   = int(params.get('regenerate', 0))
        animate = bool(params.get('animate', False))

        needs_build = (
            self._canvas is None
            or (reset > 0.5 and self._prev_reset <= 0.5)
            or (regen == 1 and self._prev_regen == 0)
            or animate
        )

        if needs_build:
            self._canvas = self._build(params)
            if animate:
                self._frame += 1

        self._prev_reset = reset
        self._prev_regen = regen
        return {'image': self._canvas}

    def _build(self, params) -> np.ndarray:
        w      = int(params.get('width',       512))
        h      = int(params.get('height',      512))
        p_idx  = int(params.get('pattern',     0))
        vmin   = float(params.get('value_min', 0.0))
        vmax   = float(params.get('value_max', 1.0))
        size   = float(params.get('seed_size', 0.05))
        tiles  = int(params.get('tile_count',  8))
        octaves= int(params.get('octaves',     4))
        scale  = float(params.get('noise_scale',0.1))
        seed   = int(params.get('seed',        42)) + self._frame
        name   = _PATTERNS[p_idx] if p_idx < len(_PATTERNS) else 'solid'

        raw = self._generate(name, w, h, size, tiles, octaves, scale, seed)
        return np.clip(vmin + raw * (vmax - vmin), 0.0, 1.0).astype(np.float32)

    def _generate(self, name, w, h, size, tiles, octaves, scale, seed) -> np.ndarray:
        Y, X   = np.indices((h, w), dtype=np.float32)
        cx, cy = w / 2.0, h / 2.0
        rng    = np.random.default_rng(seed)

        if name == 'solid':
            return np.ones((h, w), dtype=np.float32)

        elif name == 'center_dot':
            r = max(1, int(min(w, h) * size))
            mask = (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2
            return mask.astype(np.float32)

        elif name == 'white_noise':
            return rng.random((h, w)).astype(np.float32)

        elif name == 'value_noise':
            return self._value_noise(w, h, scale, octaves, seed)

        elif name == 'checkerboard':
            cell = max(1, min(w, h) // tiles)
            return (((X.astype(int) // cell) + (Y.astype(int) // cell)) % 2).astype(np.float32)

        elif name == 'stripes_h':
            cell = max(1, h // tiles)
            return ((Y.astype(int) // cell) % 2).astype(np.float32)

        elif name == 'stripes_v':
            cell = max(1, w // tiles)
            return ((X.astype(int) // cell) % 2).astype(np.float32)

        elif name == 'dots_grid':
            cell = max(1, min(w, h) // tiles)
            r    = max(1, int(cell * size * 4))
            cx_g = (X.astype(int) % cell) - cell // 2
            cy_g = (Y.astype(int) % cell) - cell // 2
            return (cx_g ** 2 + cy_g ** 2 <= r ** 2).astype(np.float32)

        elif name == 'gradient_h':
            return np.tile(np.linspace(0, 1, w, dtype=np.float32), (h, 1))

        elif name == 'gradient_v':
            return np.tile(np.linspace(0, 1, h, dtype=np.float32)[:, None], (1, w))

        elif name == 'gradient_radial':
            dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            mx   = dist.max() or 1.0
            return (1.0 - dist / mx).astype(np.float32)

        elif name == 'rings':
            dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            freq = tiles / (min(w, h) / 2.0)
            return ((np.sin(dist * freq * np.pi) + 1.0) * 0.5).astype(np.float32)

        return np.zeros((h, w), dtype=np.float32)

    @staticmethod
    def _value_noise(w, h, scale, octaves, seed) -> np.ndarray:
        result, amp, freq, total_amp = np.zeros((h, w), dtype=np.float32), 1.0, scale, 0.0
        rng = np.random.default_rng(seed)
        for _ in range(octaves):
            gw = max(2, int(w * freq))
            gh = max(2, int(h * freq))
            noise = rng.random((gh, gw)).astype(np.float32)
            result += cv2.resize(noise, (w, h), interpolation=cv2.INTER_CUBIC) * amp
            total_amp += amp
            amp  *= 0.5
            freq *= 2.0
        return (result / total_amp).clip(0, 1)
