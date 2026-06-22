"""
Gabor Filter node for VNStudio.
Chapters 5 (filtering) & 13 (texture).
Applies a Gabor kernel (oriented sinusoid modulated by a Gaussian) via cv2.filter2D.
"""

import math
import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='filter_gabor',
    label='Gabor Filter',
    category='image',
    icon='Waves',
    description="Oriented Gabor filtering for edge and texture analysis. "
                "Builds a Gabor kernel (cv2.getGaborKernel) and convolves the image.",
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Filtered', 'color': 'image'},
        {'id': 'kernel', 'label': 'Kernel', 'color': 'image'},
    ],
    params=[
        {'id': '_sec_kernel', 'label': 'Kernel Config', 'type': 'section'},
        {'id': 'ksize', 'label': 'Kernel Size', 'type': 'int', 'min': 3, 'max': 99, 'default': 31},
        {'id': 'sigma', 'label': 'Sigma', 'type': 'float', 'min': 0.5, 'max': 30.0, 'default': 4.0},
        {'id': 'theta_deg', 'label': 'Orientation (deg)', 'type': 'float', 'min': 0.0, 'max': 180.0, 'default': 0.0},
        {'id': 'lambda', 'label': 'Wavelength', 'type': 'float', 'min': 1.0, 'max': 100.0, 'default': 10.0},
        {'id': 'gamma', 'label': 'Aspect Ratio', 'type': 'float', 'min': 0.1, 'max': 2.0, 'default': 0.5},
        {'id': 'psi_deg', 'label': 'Phase (deg)', 'type': 'float', 'min': 0.0, 'max': 360.0, 'default': 0.0},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'show_kernel', 'label': 'Show Kernel', 'type': 'bool', 'default': False},
    ]
)
class GaborFilterNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'kernel': None}

        # Read parameters
        ksize = int(params.get('ksize', 31))
        if ksize < 3:
            ksize = 3
        if ksize % 2 == 0:  # kernel size must be odd
            ksize += 1
        sigma = float(params.get('sigma', 4.0))
        theta = math.radians(float(params.get('theta_deg', 0.0)))
        lambd = float(params.get('lambda', 10.0))
        gamma = float(params.get('gamma', 0.5))
        psi = math.radians(float(params.get('psi_deg', 0.0)))
        show_kernel = bool(params.get('show_kernel', False))

        # Build the Gabor kernel
        kernel = cv2.getGaborKernel(
            (ksize, ksize), sigma, theta, lambd, gamma, psi, ktype=cv2.CV_32F
        )

        # Convert to grayscale, filter
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        filtered = cv2.filter2D(gray.astype(np.float32), cv2.CV_32F, kernel)

        # Normalize result to 0-255 uint8, then BGR
        filtered = np.nan_to_num(filtered, nan=0.0, posinf=0.0, neginf=0.0)
        norm = cv2.normalize(filtered, None, 0, 255, cv2.NORM_MINMAX)
        norm = norm.astype(np.uint8)
        result_bgr = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)

        kernel_bgr = None
        if show_kernel:
            kvis = cv2.normalize(kernel, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            # Upscale small kernels so the preview is readable
            scale = max(1, 256 // max(1, ksize))
            kvis = cv2.resize(kvis, (ksize * scale, ksize * scale), interpolation=cv2.INTER_NEAREST)
            kernel_bgr = cv2.applyColorMap(kvis, cv2.COLORMAP_VIRIDIS)

        return {'main': result_bgr, 'kernel': kernel_bgr}
