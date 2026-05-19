import cv2
import numpy as np
from registry import vision_node, NodeProcessor

# Named presets (f, k)
_PRESETS = {
    'custom':     None,
    'coral':      (0.0545, 0.0620),
    'mitosis':    (0.0367, 0.0649),
    'worms':      (0.0780, 0.0610),
    'spots':      (0.0350, 0.0650),
    'labyrinth':  (0.0300, 0.0590),
    'solitons':   (0.0300, 0.0620),
    'negatons':   (0.0460, 0.0590),
    'fingerprint':(0.0550, 0.0630),
}
_PRESET_NAMES = list(_PRESETS.keys())

_COLORMAPS = {
    0: cv2.COLORMAP_INFERNO,
    1: cv2.COLORMAP_VIRIDIS,
    2: cv2.COLORMAP_JET,
    3: cv2.COLORMAP_TURBO,
    4: cv2.COLORMAP_HOT,
    5: -1,  # grayscale
}


def _laplacian(Z: np.ndarray) -> np.ndarray:
    return (np.roll(Z, 1, axis=0) + np.roll(Z, -1, axis=0) +
            np.roll(Z, 1, axis=1) + np.roll(Z, -1, axis=1) - 4.0 * Z)


@vision_node(
    type_id='gen_gray_scott',
    label='Gray-Scott',
    category='utility',
    icon='Atom',
    description="Gray-Scott reaction-diffusion simulation. Stateful: runs N iterations per frame. Connect Canvas nodes for U/V init, or let it self-initialize. Connect a grayscale image to 'mask' for image-guided RD (bright=pattern, dark=suppressed). Reset to restart.",
    inputs=[
        {'id': 'init_u',    'color': 'image'},
        {'id': 'init_v',    'color': 'image'},
        {'id': 'mask',      'color': 'image'},
        {'id': 'seed_x',    'color': 'scalar'},
        {'id': 'seed_y',    'color': 'scalar'},
        {'id': 'seed_trig', 'color': 'scalar'},
        {'id': 'reset',     'color': 'scalar'},
    ],
    outputs=[
        {'id': 'U',       'color': 'image'},
        {'id': 'V',       'color': 'image'},
        {'id': 'preview', 'color': 'image'},
    ],
    params=[
        {'id': 'preset',     'label': 'Preset',        'type': 'enum',   'options': _PRESET_NAMES, 'default': 1},
        {'id': 'f',          'label': 'f  (feed)',      'type': 'float',  'default': 0.0545, 'min': 0.0,  'max': 0.2,  'step': 0.0005},
        {'id': 'k',          'label': 'k  (kill)',      'type': 'float',  'default': 0.0620, 'min': 0.0,  'max': 0.2,  'step': 0.0005},
        {'id': 'Du',         'label': 'Du (diffusion U)','type': 'float', 'default': 0.16,   'min': 0.01, 'max': 1.0,  'step': 0.005},
        {'id': 'Dv',         'label': 'Dv (diffusion V)','type': 'float', 'default': 0.08,   'min': 0.01, 'max': 1.0,  'step': 0.005},
        {'id': 'dt',         'label': 'dt (time step)', 'type': 'float',  'default': 1.0,    'min': 0.1,  'max': 2.0,  'step': 0.05},
        {'id': 'iterations', 'label': 'Iter / frame',   'type': 'int',    'default': 8,      'min': 1,    'max': 50},
        {'id': 'width',      'label': 'Width',          'type': 'int',    'default': 256,    'min': 16,   'max': 1024},
        {'id': 'height',     'label': 'Height',         'type': 'int',    'default': 256,    'min': 16,   'max': 1024},
        {'id': 'seed_radius','label': 'Seed Radius',    'type': 'float',  'default': 0.05,   'min': 0.005,'max': 0.3,  'step': 0.005},
        {'id': 'init_mode',  'label': 'Init Mode',      'type': 'enum',   'options': ['Scattered','Center Dot'], 'default': 0},
        {'id': 'seed',       'label': 'Random Seed',    'type': 'int',    'default': 42,     'min': 0,    'max': 9999},
        {'id': 'colormap',   'label': 'Colormap',       'type': 'enum',   'options': ['Inferno','Viridis','Jet','Turbo','Hot','Gray'], 'default': 0},
        {'id': 'reset',      'label': 'Reset',          'type': 'trigger','default': 0},
    ]
)
class GrayScottNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._U: np.ndarray | None = None
        self._V: np.ndarray | None = None
        self._prev_reset = 0.0
        self._prev_seed_trig = 0.0

    # ── Initialization ────────────────────────────────────────────────────

    def _init_state(self, params, init_u, init_v):
        w = int(params.get('width',  256))
        h = int(params.get('height', 256))

        if init_u is not None:
            U = self._to_float(init_u, w, h)
        else:
            U = np.ones((h, w), dtype=np.float32)

        if init_v is not None:
            V = self._to_float(init_v, w, h)
        else:
            seed = int(params.get('seed', 42))
            rng = np.random.default_rng(seed)
            init_mode = int(params.get('init_mode', 0))
            if init_mode == 0:
                # Scattered random patches covering the whole field
                V = np.zeros((h, w), dtype=np.float32)
                n_seeds = max(10, (w * h) // 1500)
                r = max(2, int(min(w, h) * 0.03))
                for _ in range(n_seeds):
                    px = rng.integers(r, w - r)
                    py = rng.integers(r, h - r)
                    Y_g, X_g = np.ogrid[:h, :w]
                    mask = (X_g - px) ** 2 + (Y_g - py) ** 2 <= r ** 2
                    V[mask] = 1.0
                V += rng.random((h, w)).astype(np.float32) * 0.02
            else:
                # Single center dot
                V = np.zeros((h, w), dtype=np.float32)
                rc = max(2, int(min(w, h) * 0.05))
                cx, cy = w // 2, h // 2
                Y_g, X_g = np.ogrid[:h, :w]
                mask = (X_g - cx) ** 2 + (Y_g - cy) ** 2 <= rc ** 2
                V[mask] = 1.0
                V += rng.random((h, w)).astype(np.float32) * 0.05
            V = np.clip(V, 0.0, 1.0)

        self._U = U
        self._V = V

    @staticmethod
    def _to_float(img: np.ndarray, w: int, h: int) -> np.ndarray:
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        out = img.astype(np.float32)
        if out.max() > 1.0:
            out /= 255.0
        if out.shape[:2] != (h, w):
            out = cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)
        return np.clip(out, 0.0, 1.0)

    # ── Step ──────────────────────────────────────────────────────────────

    def _step(self, Du, Dv, f, k, dt, mask=None):
        U, V = self._U, self._V
        uvv  = U * V * V
        lapU = _laplacian(U)
        lapV = _laplacian(V)
        self._U = np.clip(U + dt * (Du * lapU - uvv + f * (1.0 - U)), 0.0, 1.0)
        self._V = np.clip(V + dt * (Dv * lapV + uvv - (f + k) * V),   0.0, 1.0)
        if mask is not None:
            # Suppress V in dark regions; restore U toward 1 where V is killed
            self._V *= mask
            self._U = np.clip(self._U + (1.0 - mask) * 0.05, 0.0, 1.0)

    # ── Paint seed at (x,y) ───────────────────────────────────────────────

    def _paint_seed(self, x_norm, y_norm, radius_rel):
        if self._V is None:
            return
        h, w = self._V.shape[:2]
        cx = int(x_norm * w)
        cy = int(y_norm * h)
        r  = max(1, int(min(w, h) * radius_rel))
        Y_g, X_g = np.ogrid[:h, :w]
        mask = (X_g - cx) ** 2 + (Y_g - cy) ** 2 <= r ** 2
        self._V[mask] = 1.0
        if self._U is not None:
            self._U[mask] = 0.5

    # ── Process ───────────────────────────────────────────────────────────

    def process(self, inputs, params):
        # Reset detection
        reset_raw = inputs.get('reset', params.get('reset', 0))
        try:
            reset = float(reset_raw) if reset_raw is not None else 0.0
        except (TypeError, ValueError):
            reset = 0.0

        init_u = inputs.get('init_u')
        init_v = inputs.get('init_v')

        if self._U is None or (reset > 0.5 and self._prev_reset <= 0.5):
            self._init_state(params, init_u, init_v)
        self._prev_reset = reset

        # Interactive seed on rising edge of seed_trig
        seed_trig_raw = inputs.get('seed_trig', 0)
        try:
            seed_trig = float(seed_trig_raw) if seed_trig_raw is not None else 0.0
        except (TypeError, ValueError):
            seed_trig = 0.0

        if seed_trig > 0.5 and self._prev_seed_trig <= 0.5:
            sx = inputs.get('seed_x')
            sy = inputs.get('seed_y')
            if sx is not None and sy is not None:
                try:
                    self._paint_seed(float(sx), float(sy), float(params.get('seed_radius', 0.05)))
                except (TypeError, ValueError):
                    pass
        self._prev_seed_trig = seed_trig

        # Resolve f/k from preset
        preset_idx = int(params.get('preset', 0))
        preset_name = _PRESET_NAMES[preset_idx] if preset_idx < len(_PRESET_NAMES) else 'custom'
        preset_fk   = _PRESETS.get(preset_name)
        if preset_fk is not None:
            f, k = preset_fk
        else:
            f = float(params.get('f', 0.0545))
            k = float(params.get('k', 0.0620))

        Du         = float(params.get('Du', 0.16))
        Dv         = float(params.get('Dv', 0.08))
        dt         = float(params.get('dt', 1.0))
        iterations = int(params.get('iterations', 8))

        # Image-guided mask: bright=pattern develops, dark=V suppressed
        w = int(params.get('width', 256))
        h = int(params.get('height', 256))
        mask_img = inputs.get('mask')
        rd_mask = self._to_float(mask_img, w, h) if mask_img is not None else None

        for _ in range(iterations):
            self._step(Du, Dv, f, k, dt, mask=rd_mask)

        # Build preview
        cmap_idx  = int(params.get('colormap', 0))
        cmap_code = _COLORMAPS.get(cmap_idx, cv2.COLORMAP_INFERNO)
        v8 = (self._V * 255).clip(0, 255).astype(np.uint8)
        if cmap_code == -1:
            preview = cv2.cvtColor(v8, cv2.COLOR_GRAY2BGR)
        else:
            preview = cv2.applyColorMap(v8, cmap_code)

        return {
            'U':       self._U.copy(),
            'V':       self._V.copy(),
            'preview': preview,
        }
