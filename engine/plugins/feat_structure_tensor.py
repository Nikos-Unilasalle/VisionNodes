import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='feat_structure_tensor',
    label='Structure Tensor',
    category='measure',
    icon='Grid',
    description=(
        "Computes the structure tensor J in each pixel's neighbourhood (ch6 §6.4).\n\n"
        "J = [Σ(Ix²)   Σ(IxIy)]\n"
        "    [Σ(IxIy)  Σ(Iy²) ]   (Gaussian-weighted sum over neighbourhood)\n\n"
        "Eigenvalues λ₁ ≥ λ₂ of J reveal local geometry:\n"
        "  λ₁ ≈ λ₂ ≈ 0   → flat region\n"
        "  λ₁ ≫ λ₂ ≈ 0   → edge (one dominant direction)\n"
        "  λ₁ ≈ λ₂ ≫ 0   → corner / texture\n\n"
        "Overlay: blue=flat, green=edge, red=corner.\n"
        "Harris response R = λ₁λ₂ − k·(λ₁+λ₂)² also computed."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',    'label': 'Classification',  'color': 'image'},
        {'id': 'harris',  'label': 'Harris Response',  'color': 'image'},
        {'id': 'lambda1', 'label': 'λ₁ map',           'color': 'image'},
        {'id': 'lambda2', 'label': 'λ₂ map',           'color': 'image'},
    ],
    params=[
        {'id': 'sigma_deriv', 'label': 'Deriv Sigma',  'type': 'float',
         'default': 1.0, 'min': 0.5, 'max': 5.0, 'step': 0.5},
        {'id': 'sigma_int',   'label': 'Integration Sigma', 'type': 'float',
         'default': 3.0, 'min': 1.0, 'max': 10.0, 'step': 0.5},
        {'id': 'k_harris',    'label': 'Harris k',    'type': 'float',
         'default': 0.04, 'min': 0.01, 'max': 0.10, 'step': 0.01},
        {'id': 'flat_thresh', 'label': 'Flat Threshold',  'type': 'float',
         'default': 0.001, 'min': 0.0, 'max': 0.1, 'step': 0.001},
        {'id': 'edge_ratio',  'label': 'Edge Ratio (λ₁/λ₂)', 'type': 'float',
         'default': 4.0, 'min': 1.5, 'max': 20.0, 'step': 0.5},
    ]
)
class StructureTensorNode(NodeProcessor):

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None:
            return {'main': None, 'harris': None, 'lambda1': None, 'lambda2': None}

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        gray = gray.astype(np.float32) / 255.0

        sigma_d = float(params.get('sigma_deriv', 1.0))
        sigma_i = float(params.get('sigma_int',   3.0))
        k       = float(params.get('k_harris',    0.04))
        flat_t  = float(params.get('flat_thresh', 0.001))
        edge_r  = float(params.get('edge_ratio',  4.0))

        # Derivative kernel size (odd, ≥ 3)
        kd = max(3, int(6 * sigma_d + 1) | 1)
        ki = max(3, int(6 * sigma_i + 1) | 1)

        # Smooth before derivation for LoG-style stability
        blurred = cv2.GaussianBlur(gray, (kd, kd), sigma_d)

        # Partial derivatives
        Ix = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        Iy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)

        # Structure tensor components — Gaussian-smoothed products
        Ixx = cv2.GaussianBlur(Ix * Ix, (ki, ki), sigma_i)
        Iyy = cv2.GaussianBlur(Iy * Iy, (ki, ki), sigma_i)
        Ixy = cv2.GaussianBlur(Ix * Iy, (ki, ki), sigma_i)

        # Eigenvalues via closed-form 2×2 symmetric
        trace = Ixx + Iyy
        det   = Ixx * Iyy - Ixy * Ixy
        disc  = np.sqrt(np.maximum(((Ixx - Iyy) / 2) ** 2 + Ixy ** 2, 0))
        lam1  = trace / 2.0 + disc   # larger eigenvalue
        lam2  = trace / 2.0 - disc   # smaller eigenvalue (≥0 by construction)
        lam2  = np.maximum(lam2, 0.0)

        # Harris response
        harris = det - k * trace ** 2

        # Normalize for display
        def _norm8(arr):
            mn, mx = arr.min(), arr.max()
            if mx - mn < 1e-8:
                return np.zeros_like(arr, dtype=np.uint8)
            return ((arr - mn) / (mx - mn) * 255).astype(np.uint8)

        lam1_8 = _norm8(lam1)
        lam2_8 = _norm8(lam2)
        harris_8 = _norm8(np.clip(harris, 0, harris.max() + 1e-8))

        # Classification
        H, W = gray.shape
        classify = np.zeros((H, W, 3), dtype=np.uint8)

        # Normalize λ for thresholding
        lam1_n = lam1 / (lam1.max() + 1e-8)
        lam2_n = lam2 / (lam1.max() + 1e-8)

        flat_mask   = lam1_n < flat_t
        corner_mask = (lam2_n >= flat_t) & (lam1_n / (lam2_n + 1e-8) < edge_r)
        edge_mask   = (~flat_mask) & (~corner_mask)

        classify[flat_mask]   = (180, 60,  0)    # blue  = flat
        classify[edge_mask]   = (0, 180,  60)    # green = edge
        classify[corner_mask] = (0,  60, 220)    # red   = corner

        # Legend
        cv2.putText(classify, 'flat',   (8, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (180, 60, 0),   1, cv2.LINE_AA)
        cv2.putText(classify, 'edge',   (50, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (0, 180, 60),   1, cv2.LINE_AA)
        cv2.putText(classify, 'corner', (95, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (0, 60, 220),   1, cv2.LINE_AA)

        return {
            'main':    classify,
            'harris':  cv2.applyColorMap(harris_8, cv2.COLORMAP_VIRIDIS),
            'lambda1': cv2.applyColorMap(lam1_8,  cv2.COLORMAP_PLASMA),
            'lambda2': cv2.applyColorMap(lam2_8,  cv2.COLORMAP_PLASMA),
        }
