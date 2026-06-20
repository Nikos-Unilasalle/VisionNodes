import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_delta_e',
    label='Delta E',
    category='measure',
    icon='Diff',
    description=(
        "Perceptual colour difference between two images (ch7 §7.3).\n\n"
        "Converts both images to CIE L*a*b* and computes ΔE per pixel.\n\n"
        "CIE76 : ΔE = √( (ΔL*)² + (Δa*)² + (Δb*)² )\n"
        "CIE2000 : weighted formula that fixes blue-saturation over-estimation.\n\n"
        "Perceptual thresholds:\n"
        "  ΔE < 1     : imperceptible\n"
        "  ΔE 1–2     : visible to trained eye\n"
        "  ΔE 2–10    : noticeable at first glance\n"
        "  ΔE > 10    : clearly different\n\n"
        "Outputs: false-colour map + scalar statistics."
    ),
    inputs=[
        {'id': 'image_a', 'label': 'Image A', 'color': 'image'},
        {'id': 'image_b', 'label': 'Image B', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',    'label': 'ΔE map',       'color': 'image'},
        {'id': 'delta_e', 'label': 'ΔE mean',       'color': 'scalar'},
        {'id': 'de_max',  'label': 'ΔE max',        'color': 'scalar'},
        {'id': 'de_p95',  'label': 'ΔE 95th pct',  'color': 'scalar'},
    ],
    params=[
        {'id': 'formula',  'label': 'Formula', 'type': 'enum',
         'options': ['CIE76', 'CIE2000'], 'default': 'CIE2000'},
        {'id': 'colormap', 'label': 'Colormap', 'type': 'enum',
         'options': ['Viridis', 'Plasma', 'Hot', 'Jet'], 'default': 'Viridis'},
        {'id': 'de_max_disp', 'label': 'Display Max ΔE', 'type': 'float',
         'default': 10.0, 'min': 1.0, 'max': 100.0, 'step': 1.0},
    ]
)
class DeltaENode(NodeProcessor):

    @staticmethod
    def _to_lab(img: np.ndarray) -> np.ndarray:
        """BGR uint8 → float32 Lab (OpenCV scale: L 0-100, a/b ±127)."""
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2Lab).astype(np.float32)
        # OpenCV Lab encoding: L*=[0,100]→[0,255], a*=[-128,127]→[0,255], b* idem
        lab[:, :, 0] = lab[:, :, 0] * (100.0 / 255.0)
        lab[:, :, 1] = lab[:, :, 1] - 128.0
        lab[:, :, 2] = lab[:, :, 2] - 128.0
        return lab

    @staticmethod
    def _cie76(lab_a: np.ndarray, lab_b: np.ndarray) -> np.ndarray:
        diff = lab_b - lab_a
        return np.sqrt(np.sum(diff ** 2, axis=2))

    @staticmethod
    def _cie2000(lab_a: np.ndarray, lab_b: np.ndarray) -> np.ndarray:
        L1 = lab_a[:, :, 0]; a1 = lab_a[:, :, 1]; b1 = lab_a[:, :, 2]
        L2 = lab_b[:, :, 0]; a2 = lab_b[:, :, 1]; b2 = lab_b[:, :, 2]

        C1 = np.sqrt(a1 ** 2 + b1 ** 2)
        C2 = np.sqrt(a2 ** 2 + b2 ** 2)
        C_avg = (C1 + C2) / 2.0
        C_avg7 = C_avg ** 7
        G = 0.5 * (1.0 - np.sqrt(C_avg7 / (C_avg7 + 25.0 ** 7)))

        a1p = a1 * (1.0 + G)
        a2p = a2 * (1.0 + G)
        C1p = np.sqrt(a1p ** 2 + b1 ** 2)
        C2p = np.sqrt(a2p ** 2 + b2 ** 2)

        h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
        h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0

        dLp = L2 - L1
        dCp = C2p - C1p

        dh_raw = h2p - h1p
        dh_raw[dh_raw > 180]  -= 360.0
        dh_raw[dh_raw < -180] += 360.0
        zero_C = (C1p * C2p) < 1e-8
        dh_raw[zero_C] = 0.0
        dHp = 2.0 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh_raw / 2.0))

        Lp_avg = (L1 + L2) / 2.0
        Cp_avg = (C1p + C2p) / 2.0

        h_sum = h1p + h2p
        h_avg = np.where(
            zero_C,
            h_sum,
            np.where(
                np.abs(h1p - h2p) <= 180,
                h_sum / 2.0,
                np.where(h_sum < 360, (h_sum + 360) / 2.0, (h_sum - 360) / 2.0)
            )
        )

        h_avg_r = np.radians(h_avg)
        T = (1.0
             - 0.17 * np.cos(h_avg_r - np.radians(30))
             + 0.24 * np.cos(2 * h_avg_r)
             + 0.32 * np.cos(3 * h_avg_r + np.radians(6))
             - 0.20 * np.cos(4 * h_avg_r - np.radians(63)))

        SL = 1.0 + 0.015 * (Lp_avg - 50) ** 2 / np.sqrt(20 + (Lp_avg - 50) ** 2)
        SC = 1.0 + 0.045 * Cp_avg
        SH = 1.0 + 0.015 * Cp_avg * T

        Cp_avg7 = Cp_avg ** 7
        RC = 2.0 * np.sqrt(Cp_avg7 / (Cp_avg7 + 25.0 ** 7))
        d_theta = 30.0 * np.exp(-((h_avg - 275.0) / 25.0) ** 2)
        RT = -np.sin(np.radians(2 * d_theta)) * RC

        de = np.sqrt(
            (dLp / SL) ** 2 +
            (dCp / SC) ** 2 +
            (dHp / SH) ** 2 +
            RT * (dCp / SC) * (dHp / SH)
        )
        return de

    def process(self, inputs, params):
        img_a = inputs.get('image_a')
        img_b = inputs.get('image_b')
        if img_a is None or img_b is None:
            return {'main': None, 'delta_e': 0.0, 'de_max': 0.0, 'de_p95': 0.0}

        # Align sizes
        H = max(img_a.shape[0], img_b.shape[0])
        W = max(img_a.shape[1], img_b.shape[1])
        if img_a.shape[:2] != (H, W):
            img_a = cv2.resize(img_a, (W, H))
        if img_b.shape[:2] != (H, W):
            img_b = cv2.resize(img_b, (W, H))

        lab_a = self._to_lab(img_a)
        lab_b = self._to_lab(img_b)

        formula = params.get('formula', 'CIE2000')
        if formula == 'CIE76':
            de_map = self._cie76(lab_a, lab_b)
        else:
            de_map = self._cie2000(lab_a, lab_b)

        de_mean = float(np.mean(de_map))
        de_max  = float(np.max(de_map))
        de_p95  = float(np.percentile(de_map, 95))

        # Colourmap
        de_max_disp = float(params.get('de_max_disp', 10.0))
        de_norm = np.clip(de_map / max(de_max_disp, 1e-6), 0, 1)
        de_8 = (de_norm * 255).astype(np.uint8)

        cmap_idx = {'Viridis': cv2.COLORMAP_VIRIDIS,
                    'Plasma':  cv2.COLORMAP_PLASMA,
                    'Hot':     cv2.COLORMAP_HOT,
                    'Jet':     cv2.COLORMAP_JET}.get(
            params.get('colormap', 'Viridis'), cv2.COLORMAP_VIRIDIS)
        vis = cv2.applyColorMap(de_8, cmap_idx)

        label = f'{formula}  mean={de_mean:.2f}  max={de_max:.2f}  p95={de_p95:.2f}'
        cv2.putText(vis, label, (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(vis, f'scale: 0–{de_max_disp:.0f}', (8, H - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1, cv2.LINE_AA)

        return {
            'main':    vis,
            'delta_e': round(de_mean, 4),
            'de_max':  round(de_max,  4),
            'de_p95':  round(de_p95,  4),
        }
