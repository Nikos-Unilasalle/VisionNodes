import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_color_distance',
    label='Color Distance',
    category='measure',
    icon='Ruler',
    description=(
        "Pixel-wise color distance map between image and a reference color (ch3).\n\n"
        "L1 = Σ|Δc|, L2 = √(Σ Δc²), L∞ = max|Δc| (§3.1 — Minkowski).\n"
        "Cosine = 1 − (A·B)/(|A||B|) : shape similarity, ignores brightness (§3.3).\n"
        "Mahalanobis: accounts for channel correlations and variance (§3.2).\n\n"
        "Reference source: 'Ref Mask' region mean (if connected), else 'Ref Color' picker.\n"
        "Outputs a float32 distance map (normalized 0–1 for display), a threshold mask,\n"
        "and the scalar min distance."
    ),
    inputs=[
        {'id': 'image',    'label': 'Image',    'color': 'image'},
        {'id': 'ref_mask', 'label': 'Ref Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'dist_map', 'label': 'Distance Map', 'color': 'image'},
        {'id': 'mask',     'label': 'Threshold Mask', 'color': 'mask'},
        {'id': 'min_dist', 'label': 'Min Dist',    'color': 'scalar'},
    ],
    params=[
        {'id': 'metric',    'label': 'Metric',        'type': 'enum',
         'options': ['L2', 'L1', 'L∞', 'Cosine', 'Mahalanobis'], 'default': 'L2'},
        {'id': 'ref_color', 'label': 'Ref Color',     'type': 'color', 'default': '#ff0000'},
        {'id': 'threshold', 'label': 'Threshold',     'type': 'float',
         'default': 0.20, 'min': 0.0, 'max': 1.0, 'step': 0.01},
        {'id': 'colormap',  'label': 'Colormap',      'type': 'enum',
         'options': ['Viridis', 'Jet', 'Plasma', 'Grayscale'], 'default': 'Viridis'},
    ]
)
class ColorDistanceNode(NodeProcessor):

    _CMAPS = {
        'Viridis':   cv2.COLORMAP_VIRIDIS,
        'Jet':       cv2.COLORMAP_JET,
        'Plasma':    cv2.COLORMAP_PLASMA,
        'Grayscale': None,
    }

    @staticmethod
    def _hex_to_bgr(hex_color: str) -> np.ndarray:
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return np.array([b, g, r], dtype=np.float32)

    @staticmethod
    def _ref_from_mask(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        binary = (mask > 127).astype(np.uint8)
        if binary.shape[:2] != image.shape[:2]:
            binary = cv2.resize(binary, (image.shape[1], image.shape[0]),
                                interpolation=cv2.INTER_NEAREST)
        pixels = image[binary > 0].astype(np.float32)
        if len(pixels) == 0:
            return np.array([0.0, 0.0, 0.0], dtype=np.float32)
        return pixels.mean(axis=0)

    def process(self, inputs, params):
        image = inputs.get('image')
        ref_mask = inputs.get('ref_mask')
        if image is None:
            return {'dist_map': None, 'mask': None, 'min_dist': 0.0}

        img = image.astype(np.float32)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        metric    = params.get('metric', 'L2')
        threshold = float(params.get('threshold', 0.20))
        cmap_name = params.get('colormap', 'Viridis')
        hex_ref   = params.get('ref_color', '#ff0000')

        # Reference vector
        ref = (self._ref_from_mask(img, ref_mask)
               if ref_mask is not None
               else self._hex_to_bgr(hex_ref))

        H, W = img.shape[:2]
        flat = img.reshape(-1, 3)          # (N, 3) float32

        if metric == 'L1':
            dist = np.sum(np.abs(flat - ref), axis=1) / (3.0 * 255.0)

        elif metric == 'L2':
            diff = flat - ref
            dist = np.sqrt(np.sum(diff * diff, axis=1)) / (np.sqrt(3.0) * 255.0)

        elif metric == 'L∞':
            dist = np.max(np.abs(flat - ref), axis=1) / 255.0

        elif metric == 'Cosine':
            norms = np.linalg.norm(flat, axis=1, keepdims=True) + 1e-8
            ref_norm = ref / (np.linalg.norm(ref) + 1e-8)
            cosine_sim = np.dot(flat / norms, ref_norm)
            dist = (1.0 - cosine_sim) / 2.0  # map [-1,1] → [0,1]

        else:  # Mahalanobis — use per-channel std from whole image as covariance diagonal
            std = flat.std(axis=0) + 1e-8
            diff = (flat - ref) / std
            dist = np.sqrt(np.sum(diff * diff, axis=1)) / np.sqrt(3.0)
            dist = np.clip(dist, 0.0, 1.0)

        dist = dist.astype(np.float32).reshape(H, W)
        dist_clipped = np.clip(dist, 0.0, 1.0)

        # Colormap
        gray8 = (dist_clipped * 255).astype(np.uint8)
        cv_cmap = self._CMAPS.get(cmap_name)
        if cv_cmap is not None:
            dist_map = cv2.applyColorMap(gray8, cv_cmap)
        else:
            dist_map = cv2.cvtColor(gray8, cv2.COLOR_GRAY2BGR)

        # Threshold mask
        binary_mask = ((dist_clipped <= threshold) * 255).astype(np.uint8)

        min_dist = float(dist_clipped.min())

        return {
            'dist_map': dist_map,
            'mask':     binary_mask,
            'min_dist': round(min_dist, 4),
        }
