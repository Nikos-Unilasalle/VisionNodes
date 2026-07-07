import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='feat_gabor_bank',
    label='Gabor Bank',
    category='measure',
    icon='Waves',
    description=(
        "Multi-orientation Gabor filter bank (ch13 §13.5).\n\n"
        "Applies N_theta Gabor filters (magnitude of complex response). Each\n"
        "filter responds only to edges/threads at its own orientation and at the\n"
        "chosen wavelength (thread spacing).\n\n"
        "Outputs:\n"
        "• Orientation Map — per-pixel dominant orientation (colour-coded).\n"
        "• Responses Grid — the N individual responses in one labelled montage,\n"
        "  all on a SHARED brightness scale so panels are directly comparable.\n"
        "• Energy Map — per-pixel max energy across orientations.\n"
        "• Signature — mean energy per orientation (a texture signature vector).\n"
        "• Orientations — N_theta (scalar)."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',          'label': 'Orientation Map', 'color': 'image'},
        {'id': 'responses_grid','label': 'Responses Grid',  'color': 'image'},
        {'id': 'energy_map',    'label': 'Energy Map',      'color': 'image'},
        {'id': 'signature',     'label': 'Signature',       'color': 'list'},
        {'id': 'n_orientations','label': 'Orientations',    'color': 'scalar'},
    ],
    params=[
        {'id': 'n_theta',   'label': 'Orientations',      'type': 'int',   'default': 4,  'min': 2, 'max': 16},
        {'id': '_sec_filter', 'label': 'Filter', 'type': 'section'},
        {'id': 'wavelength','label': 'Wavelength (px)',   'type': 'float', 'default': 8.0,'min': 2.0,'max': 64.0},
        {'id': 'sigma',     'label': 'Sigma',             'type': 'float', 'default': 4.0,'min': 1.0,'max': 32.0},
        {'id': 'gamma',     'label': 'Aspect Ratio',      'type': 'float', 'default': 0.5,'min': 0.1,'max': 1.0},
        {'id': 'ksize',     'label': 'Kernel Size',       'type': 'int',   'default': 31, 'min': 7, 'max': 63},
        {'id': '_sec_view', 'label': 'Display', 'type': 'section'},
        {'id': 'panel_px',  'label': 'Panel Size (px)',   'type': 'int',   'default': 256, 'min': 96, 'max': 640},
        {'id': 'colorize',  'label': 'Heatmap Panels',    'type': 'bool',  'default': True},
    ]
)
class GaborBankNode(NodeProcessor):

    @staticmethod
    def _panel(resp_u8: np.ndarray, label: str, panel_px: int, colorize: bool) -> np.ndarray:
        """One labelled response panel, resized to fit within panel_px."""
        h, w = resp_u8.shape[:2]
        scale = panel_px / max(h, w)
        pw, ph = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        small = cv2.resize(resp_u8, (pw, ph), interpolation=cv2.INTER_AREA)
        panel = cv2.applyColorMap(small, cv2.COLORMAP_MAGMA) if colorize \
            else cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (pw - 1, ph - 1), (60, 60, 60), 1)
        cv2.putText(panel, label, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(panel, label, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        return panel

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'responses_grid': None, 'energy_map': None,
                    'signature': [], 'n_orientations': 0}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
        flt  = gray.astype(np.float32)

        n_theta    = int(params.get('n_theta', 4))
        wavelength = float(params.get('wavelength', 8.0))
        sigma      = float(params.get('sigma', 4.0))
        gamma      = float(params.get('gamma', 0.5))
        ksize      = int(params.get('ksize', 31))
        panel_px   = int(params.get('panel_px', 256))
        colorize   = bool(params.get('colorize', True))
        if ksize % 2 == 0:
            ksize += 1

        thetas = [i * np.pi / n_theta for i in range(n_theta)]

        # Stack energy responses: shape (n_theta, H, W)
        responses = np.zeros((n_theta, *flt.shape), dtype=np.float32)
        for k, theta in enumerate(thetas):
            # Real part (even)
            k_real = cv2.getGaborKernel((ksize, ksize), sigma, theta, wavelength, gamma, 0.0, ktype=cv2.CV_32F)
            # Imaginary part (odd, psi=pi/2)
            k_imag = cv2.getGaborKernel((ksize, ksize), sigma, theta, wavelength, gamma, np.pi / 2, ktype=cv2.CV_32F)
            r = cv2.filter2D(flt, cv2.CV_32F, k_real)
            i = cv2.filter2D(flt, cv2.CV_32F, k_imag)
            responses[k] = np.sqrt(r ** 2 + i ** 2)

        # Argmax orientation per pixel
        dominant = np.argmax(responses, axis=0)  # (H, W) index into thetas
        energy   = responses.max(axis=0)          # (H, W) max energy

        # Colour-code orientation (HSV: hue encodes angle, value = energy)
        hue    = (dominant.astype(np.float32) / n_theta * 180).astype(np.uint8)
        energy_norm = cv2.normalize(energy, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        hsv    = np.stack([hue, np.full_like(hue, 220), energy_norm], axis=-1)
        orient_map = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        energy_vis = cv2.applyColorMap(energy_norm, cv2.COLORMAP_MAGMA)

        # ── Per-orientation responses on a SHARED scale (comparable panels) ──
        global_max = float(responses.max()) or 1.0
        resp_u8 = np.clip(responses / global_max * 255.0, 0, 255).astype(np.uint8)

        panels = [
            self._panel(resp_u8[k], f'{int(round(np.degrees(thetas[k])))} deg',
                        panel_px, colorize)
            for k in range(n_theta)
        ]
        grid = self._montage(panels)

        # ── Texture signature: mean energy per orientation (normalised) ──
        means = responses.mean(axis=(1, 2))
        sig_max = float(means.max()) or 1.0
        signature = [round(float(m / sig_max), 4) for m in means]

        return {
            'main':           orient_map,
            'responses_grid': grid,
            'energy_map':     energy_vis,
            'signature':      signature,
            'n_orientations': n_theta,
        }

    @staticmethod
    def _montage(panels: list) -> np.ndarray:
        """Lay panels out in a near-square grid, padded to a uniform cell size."""
        n = len(panels)
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        cell_h = max(p.shape[0] for p in panels)
        cell_w = max(p.shape[1] for p in panels)
        gap = 4
        canvas = np.full((rows * cell_h + (rows + 1) * gap,
                          cols * cell_w + (cols + 1) * gap, 3), 18, dtype=np.uint8)
        for idx, p in enumerate(panels):
            rr, cc = divmod(idx, cols)
            y = gap + rr * (cell_h + gap)
            x = gap + cc * (cell_w + gap)
            canvas[y:y + p.shape[0], x:x + p.shape[1]] = p
        return canvas
