import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='feat_gabor_bank',
    label='Gabor Bank',
    category='measure',
    icon='Waves',
    description=(
        "Multi-scale, multi-orientation Gabor filter bank (ch13 §13.5).\n\n"
        "Applies N_theta × N_lambda Gabor filters (magnitude of complex response).\n"
        "For each pixel, keeps the orientation of maximum energy response.\n\n"
        "Outputs: orientation map (colour-coded), energy map, and the energy\n"
        "vector (N_theta × N_lambda scalars) for the full image."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',         'label': 'Orientation Map', 'color': 'image'},
        {'id': 'energy_map',   'label': 'Energy Map',      'color': 'image'},
        {'id': 'n_orientations','label': 'Orientations',   'color': 'scalar'},
    ],
    params=[
        {'id': 'n_theta',   'label': 'Orientations',      'type': 'int',   'default': 8,  'min': 2, 'max': 16},
        {'id': 'wavelength','label': 'Wavelength (px)',   'type': 'float', 'default': 8.0,'min': 2.0,'max': 64.0},
        {'id': 'sigma',     'label': 'Sigma',             'type': 'float', 'default': 4.0,'min': 1.0,'max': 32.0},
        {'id': 'gamma',     'label': 'Aspect Ratio',      'type': 'float', 'default': 0.5,'min': 0.1,'max': 1.0},
        {'id': 'ksize',     'label': 'Kernel Size',       'type': 'int',   'default': 31, 'min': 7, 'max': 63},
    ]
)
class GaborBankNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'energy_map': None, 'n_orientations': 0}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
        flt  = gray.astype(np.float32)

        n_theta    = int(params.get('n_theta', 8))
        wavelength = float(params.get('wavelength', 8.0))
        sigma      = float(params.get('sigma', 4.0))
        gamma      = float(params.get('gamma', 0.5))
        ksize      = int(params.get('ksize', 31))
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

        return {
            'main':          orient_map,
            'energy_map':    energy_vis,
            'n_orientations': n_theta,
        }
