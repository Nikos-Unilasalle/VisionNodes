"""
cv_directional_dilate.py — orientation-aware (anisotropic) dilation.

Closes gaps in thin structures (skeletons, river networks) WITHOUT fattening
them sideways. A bridge or a tree canopy breaks a river into two collinear stubs;
an isotropic dilate would also smear unrelated branches together. Here each pixel
is dilated with a SHORT LINE kernel aligned to the local tangent, so only
collinear neighbours get bridged.

Two modes:
  • Auto (tangent)  — local orientation from the structure tensor, per angle bin.
  • Fixed angle     — single global direction (deg).
"""

import cv2
import numpy as np

try:
    from scipy.ndimage import gaussian_filter
    _SCIPY_OK = True
except Exception:
    _SCIPY_OK = False

from registry import vision_node, NodeProcessor


def _line_kernel(length: int, angle_deg: float) -> np.ndarray:
    """Binary line structuring element of given length at angle_deg (0 = →)."""
    length = max(1, int(length) | 1)            # force odd
    k = np.zeros((length, length), np.uint8)
    c = length // 2
    a = np.deg2rad(angle_deg)
    dx, dy = np.cos(a), -np.sin(a)              # image y is down
    for t in np.linspace(-c, c, length * 2):
        x = int(round(c + t * dx)); y = int(round(c + t * dy))
        if 0 <= x < length and 0 <= y < length:
            k[y, x] = 1
    return k


@vision_node(
    type_id='cv_directional_dilate',
    label='Directional Dilate',
    category='mask',
    icon='Spline',
    description=(
        "Orientation-aware dilation. Dilates each pixel with a short line kernel "
        "aligned to the local tangent (structure tensor), so collinear gaps "
        "(bridges, canopy) close while parallel branches stay separate. Use to "
        "repair a broken skeleton / hydrographic network. Fixed-angle mode applies "
        "one global direction."
    ),
    resizable=True, min_width=220, min_height=180, colorable=True,
    inputs=[
        {'id': 'mask', 'label': 'Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Repaired', 'color': 'mask'},
        {'id': 'preview', 'label': 'Preview', 'color': 'image'},
    ],
    params=[
        {'id': 'mode',      'label': 'Mode',        'type': 'enum', 'options': ['Auto (tangent)', 'Fixed angle'], 'default': 0},
        {'id': 'length',    'label': 'Reach (px)',  'type': 'int',  'default': 11, 'min': 3,  'max': 81},
        {'id': 'angle',     'label': 'Angle (deg)', 'type': 'int',  'default': 0,  'min': 0,  'max': 180},
        {'id': 'bins',      'label': 'Angle Bins',  'type': 'int',  'default': 8,  'min': 2,  'max': 18},
        {'id': 'tensor_sigma', 'label': 'Tensor Smooth', 'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 8.0, 'step': 0.5},
        {'id': 'iterations','label': 'Iterations',  'type': 'int',  'default': 1,  'min': 1,  'max': 6},
        {'id': 'then_close','label': 'Final Close', 'type': 'bool', 'default': True},
    ]
)
class DirectionalDilateNode(NodeProcessor):

    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'main': None, 'preview': None}
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        binm = (mask > 0).astype(np.uint8) * 255

        length = int(params.get('length', 11))
        iters  = int(params.get('iterations', 1))
        fixed  = int(params.get('mode', 0)) == 1

        out = binm.copy()
        if fixed:
            ker = _line_kernel(length, float(params.get('angle', 0)))
            out = cv2.dilate(out, ker, iterations=iters)
        else:
            out = self._auto(out, length, iters, params)

        if bool(params.get('then_close', True)):
            out = cv2.morphologyEx(out, cv2.MORPH_CLOSE,
                                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

        preview = cv2.cvtColor(binm, cv2.COLOR_GRAY2BGR)
        added = (out > 0) & (binm == 0)
        preview[added] = (60, 220, 60)          # new bridge pixels = green
        return {'main': out, 'preview': preview}

    def _auto(self, binm, length, iters, params):
        """Per-pixel tangent dilation via structure-tensor orientation binning."""
        sigma = float(params.get('tensor_sigma', 2.0))
        nbins = int(params.get('bins', 8))
        f = binm.astype(np.float32) / 255.0

        gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        if _SCIPY_OK:
            jxx = gaussian_filter(gx * gx, sigma); jyy = gaussian_filter(gy * gy, sigma); jxy = gaussian_filter(gx * gy, sigma)
        else:
            ks = max(3, int(sigma * 4) | 1)
            jxx = cv2.GaussianBlur(gx * gx, (ks, ks), sigma); jyy = cv2.GaussianBlur(gy * gy, (ks, ks), sigma); jxy = cv2.GaussianBlur(gx * gy, (ks, ks), sigma)
        # gradient orientation; tangent = gradient + 90deg
        grad_ang = 0.5 * np.arctan2(2 * jxy, jxx - jyy)          # radians, [-pi/2, pi/2]
        tangent_deg = (np.rad2deg(grad_ang) + 90.0) % 180.0

        result = binm.copy()
        edges = np.linspace(0, 180, nbins + 1)
        for b in range(nbins):
            lo, hi = edges[b], edges[b + 1]
            center = 0.5 * (lo + hi)
            sel = (tangent_deg >= lo) & (tangent_deg < hi) & (binm > 0)
            if not sel.any():
                continue
            layer = (sel.astype(np.uint8)) * 255
            ker = _line_kernel(length, center)
            layer = cv2.dilate(layer, ker, iterations=iters)
            result = cv2.bitwise_or(result, layer)
        return result
