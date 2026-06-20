import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_glcm',
    label='GLCM',
    category='measure',
    icon='Grid3x3',
    description=(
        "Grey-Level Co-occurrence Matrix + Haralick features (ch13 §13.2–13.3).\n\n"
        "Quantises the image to `levels`, builds P(i,j | d, θ) averaged over selected\n"
        "angles (rotation-invariant), then computes Haralick scalars:\n"
        "contrast, homogeneity, energy (ASM), entropy, correlation.\n\n"
        "Outputs a visualisation of the GLCM matrix and all five Haralick scalars."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',         'label': 'GLCM Heatmap',  'color': 'image'},
        {'id': 'contrast',     'label': 'Contrast',       'color': 'scalar'},
        {'id': 'homogeneity',  'label': 'Homogeneity',    'color': 'scalar'},
        {'id': 'energy',       'label': 'Energy (ASM)',   'color': 'scalar'},
        {'id': 'entropy',      'label': 'Entropy',        'color': 'scalar'},
        {'id': 'correlation',  'label': 'Correlation',    'color': 'scalar'},
    ],
    params=[
        {'id': 'distance',   'label': 'Displacement Steps', 'type': 'int',
         'default': 1, 'min': 1, 'max': 32},
        {'id': 'levels',     'label': 'Quantization Levels', 'type': 'enum',
         'options': ['8', '16', '32', '64'], 'default': 1},
        {'id': 'angles',     'label': 'Directions (Angles)', 'type': 'enum',
         'options': ['0° only', '0°+90°', '0°+45°+90°+135°'], 'default': 2},
        {'id': 'symmetric',  'label': 'Symmetric',           'type': 'bool', 'default': True},
    ]
)
class GLCMNode(NodeProcessor):

    @staticmethod
    def _build_glcm(gray_q, d, angles_rad, levels, symmetric):
        glcm = np.zeros((levels, levels), dtype=np.float64)
        h, w = gray_q.shape
        for theta in angles_rad:
            dx = int(round(d * np.cos(theta)))
            dy = int(round(d * np.sin(theta)))
            for y in range(h):
                for x in range(w):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        i, j = int(gray_q[y, x]), int(gray_q[ny, nx])
                        glcm[i, j] += 1
                        if symmetric:
                            glcm[j, i] += 1
        total = glcm.sum()
        if total > 0:
            glcm /= total
        return glcm

    @staticmethod
    def _haralick(P):
        L = P.shape[0]
        idx = np.arange(L)
        ii, jj = np.meshgrid(idx, idx, indexing='ij')

        contrast    = float(np.sum((ii - jj) ** 2 * P))
        homogeneity = float(np.sum(P / (1 + np.abs(ii - jj))))
        energy      = float(np.sum(P ** 2))
        nz = P[P > 0]
        entropy     = float(-np.sum(nz * np.log2(nz)))

        mu_i = float(np.sum(ii * P))
        mu_j = float(np.sum(jj * P))
        sig_i = float(np.sqrt(np.sum((ii - mu_i) ** 2 * P)))
        sig_j = float(np.sqrt(np.sum((jj - mu_j) ** 2 * P)))
        if sig_i > 1e-9 and sig_j > 1e-9:
            correlation = float(np.sum((ii - mu_i) * (jj - mu_j) * P) / (sig_i * sig_j))
        else:
            correlation = 0.0

        return contrast, homogeneity, energy, entropy, correlation

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'contrast': 0.0, 'homogeneity': 0.0,
                    'energy': 0.0, 'entropy': 0.0, 'correlation': 0.0}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()

        levels_map = [8, 16, 32, 64]
        levels     = levels_map[int(params.get('levels', 1))]
        d          = int(params.get('distance', 1))
        angles_idx = int(params.get('angles', 2))
        symmetric  = bool(params.get('symmetric', True))

        angles_sets = [
            [0.0],
            [0.0, np.pi / 2],
            [0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4],
        ]
        angles_rad = angles_sets[min(angles_idx, 2)]

        # quantise to [0, levels-1]
        gray_q = (gray.astype(np.float32) / 255.0 * (levels - 1)).astype(np.uint8)

        # limit to centre crop for speed (max 128×128 region)
        h, w = gray_q.shape
        crop = 128
        cy, cx = h // 2, w // 2
        roi = gray_q[max(0, cy - crop):cy + crop, max(0, cx - crop):cx + crop]

        glcm = self._build_glcm(roi, d, angles_rad, levels, symmetric)
        contrast, homogeneity, energy, entropy, correlation = self._haralick(glcm)

        # Visualise GLCM as heatmap
        vis_size = 256
        glcm_vis = (glcm / (glcm.max() + 1e-12) * 255).astype(np.uint8)
        glcm_vis = cv2.resize(glcm_vis, (vis_size, vis_size), interpolation=cv2.INTER_NEAREST)
        heatmap = cv2.applyColorMap(glcm_vis, cv2.COLORMAP_INFERNO)

        lines = [
            f'contrast={contrast:.3f}',
            f'homog={homogeneity:.3f}',
            f'energy={energy:.4f}',
            f'entropy={entropy:.3f}',
            f'corr={correlation:.3f}',
        ]
        for i, txt in enumerate(lines):
            cv2.putText(heatmap, txt, (4, 14 + i * 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        return {
            'main':        heatmap,
            'contrast':    round(contrast, 4),
            'homogeneity': round(homogeneity, 4),
            'energy':      round(energy, 6),
            'entropy':     round(entropy, 4),
            'correlation': round(correlation, 4),
        }
