from registry import vision_node, NodeProcessor
import cv2
import numpy as np


@vision_node(
    type_id='image_moments',
    label='Image Moments',
    category='measure',
    icon='Target',
    description=(
        "Computes spatial moments and Hu invariants for a single connected shape (ch2). "
        "Outputs raw moments M_pq, central moments μ_pq, normalized moments η_pq, "
        "centroid, orientation θ, anisotropy, and the 7 log-scaled Hu invariants φ₁–φ₇. "
        "Binary Mode ON → pure geometry (mask). Binary Mode OFF → intensity-weighted "
        "centroid (barycentre lumineux, sub-pixel localisation)."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
        {'id': 'mask',  'label': 'Mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Overlay', 'color': 'image'},
        {'id': 'data', 'label': 'Moments', 'color': 'dict'},
    ],
    params=[
        {'id': 'binary_mode',  'label': 'Binary Mode (geometry)',   'type': 'bool', 'default': True},
        {'id': 'source',       'label': 'Source',                   'type': 'enum',
         'options': ['Largest Contour', 'Whole Mask'], 'default': 'Largest Contour'},
        {'id': 'draw_overlay', 'label': 'Draw Overlay',             'type': 'bool', 'default': True},
        {'id': 'draw_ellipse', 'label': 'Draw Principal Axis',      'type': 'bool', 'default': False},
    ]
)
class ImageMomentsNode(NodeProcessor):

    @staticmethod
    def _to_binary(mask, image):
        if mask is not None:
            if mask.ndim == 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
            return binary.astype(np.uint8)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary.astype(np.uint8)

    @staticmethod
    def _to_gray_float(image):
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        return gray.astype(np.float32)

    @staticmethod
    def _hu_log(hu):
        """Sign-preserving log10 scaling of the 7 Hu moments (ch2 §2.7)."""
        out = []
        for v in hu.flatten():
            v = float(v)
            if v == 0.0:
                out.append(0.0)
            else:
                out.append(float(-np.sign(v) * np.log10(abs(v))))
        return out

    @staticmethod
    def _normalized_moments(m00, mu20, mu02, mu11):
        """η_pq = μ_pq / μ₀₀^γ, γ = (p+q)/2 + 1 (ch2 §2.4)."""
        if m00 == 0:
            return {'eta20': 0.0, 'eta02': 0.0, 'eta11': 0.0}
        m00_sq = float(m00) ** 2
        return {
            'eta20': round(mu20 / m00_sq, 6),
            'eta02': round(mu02 / m00_sq, 6),
            'eta11': round(mu11 / m00_sq, 6),
        }

    @staticmethod
    def _orientation_and_anisotropy(mu20, mu02, mu11):
        """θ = ½·arctan2(2μ₁₁, μ₂₀−μ₀₂), aniso = √((μ₂₀-μ₀₂)²+4μ₁₁²)/(μ₂₀+μ₀₂) (ch2 §2.5)."""
        theta = 0.5 * float(np.degrees(np.arctan2(2.0 * mu11, mu20 - mu02)))
        denom = mu20 + mu02
        if denom > 0:
            aniso = float(np.sqrt((mu20 - mu02) ** 2 + 4 * mu11 ** 2)) / denom
        else:
            aniso = 0.0
        return round(theta, 3), round(aniso, 4)

    def process(self, inputs, params):
        image = inputs.get('image')
        mask  = inputs.get('mask')
        if image is None:
            return {'main': None, 'data': None}

        binary_mode  = bool(params.get('binary_mode', True))
        source       = params.get('source', 'Largest Contour')
        draw_overlay = bool(params.get('draw_overlay', True))
        draw_ellipse = bool(params.get('draw_ellipse', False))

        binary  = self._to_binary(mask, image)
        contour = None

        if binary_mode:
            # Geometry-only: moments from binary mask or largest contour
            if source == 'Largest Contour':
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    contour = max(contours, key=cv2.contourArea)
                    moments = cv2.moments(contour)
                else:
                    moments = cv2.moments(binary, binaryImage=True)
            else:
                moments = cv2.moments(binary, binaryImage=True)
        else:
            # Intensity-weighted: use raw pixel values (ch2 §2.8)
            gray = self._to_gray_float(image)
            # Restrict to masked region if mask provided
            if mask is not None:
                region = gray.copy()
                region[binary == 0] = 0.0
                moments = cv2.moments(region.astype(np.float32), binaryImage=False)
            else:
                moments = cv2.moments(gray.astype(np.float32), binaryImage=False)

        m00 = float(moments['m00'])
        cx = float(moments['m10']) / m00 if m00 != 0 else 0.0
        cy = float(moments['m01']) / m00 if m00 != 0 else 0.0

        # Central moments μ_pq (ch2 §2.3)
        mu20 = float(moments.get('mu20', 0.0))
        mu02 = float(moments.get('mu02', 0.0))
        mu11 = float(moments.get('mu11', 0.0))
        mu30 = float(moments.get('mu30', 0.0))
        mu03 = float(moments.get('mu03', 0.0))

        # Normalized moments η_pq (ch2 §2.4)
        eta = self._normalized_moments(m00, mu20, mu02, mu11)

        # Orientation θ and anisotropy (ch2 §2.5)
        theta, aniso = self._orientation_and_anisotropy(mu20, mu02, mu11)

        # Equivalent ellipse semi-axes (ch2 §2.6): λ = eigenvalues of inertia
        if mu20 + mu02 > 0:
            term = float(np.sqrt((mu20 - mu02) ** 2 + 4 * mu11 ** 2))
            lam1 = (mu20 + mu02 + term) / 2.0
            lam2 = (mu20 + mu02 - term) / 2.0
            semi_major = round(2.0 * float(np.sqrt(max(lam1, 0))), 2)
            semi_minor = round(2.0 * float(np.sqrt(max(lam2, 0))), 2)
            eccentricity = round(float(np.sqrt(1.0 - lam2 / lam1)), 4) if lam1 > 0 and lam2 >= 0 else 0.0
        else:
            semi_major = semi_minor = eccentricity = 0.0

        # Hu moments φ₁–φ₇ (ch2 §2.7)
        hu     = cv2.HuMoments(moments)
        hu_log = self._hu_log(hu)

        # ── Overlay ──────────────────────────────────────────────────────────
        if image.ndim == 2:
            overlay = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            overlay = image.copy()

        if draw_overlay and m00 != 0:
            cxi, cyi = int(round(cx)), int(round(cy))
            if contour is not None:
                cv2.drawContours(overlay, [contour], -1, (0, 255, 255), 2)
            cv2.circle(overlay, (cxi, cyi), 6, (0, 0, 255), -1)
            cv2.line(overlay, (cxi - 14, cyi), (cxi + 14, cyi), (0, 0, 255), 2)
            cv2.line(overlay, (cxi, cyi - 14), (cxi, cyi + 14), (0, 0, 255), 2)
            cv2.putText(overlay, f"area={m00:.0f}", (cxi + 10, cyi - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2, cv2.LINE_AA)

        if draw_ellipse and m00 != 0 and semi_major > 1:
            cxi, cyi = int(round(cx)), int(round(cy))
            angle = -theta  # OpenCV angle convention
            axes  = (max(1, int(semi_major)), max(1, int(semi_minor)))
            cv2.ellipse(overlay, (cxi, cyi), axes, angle, 0, 360, (255, 180, 0), 1, cv2.LINE_AA)
            # Draw principal axis line
            rad = float(np.radians(theta))
            dx, dy = int(semi_major * np.cos(rad)), int(semi_major * np.sin(rad))
            cv2.line(overlay, (cxi - dx, cyi - dy), (cxi + dx, cyi + dy), (255, 180, 0), 2, cv2.LINE_AA)

        return {
            'main': overlay,
            'data': {
                # §2.1 — raw moments
                'M00': round(m00, 2),
                'M10': round(float(moments['m10']), 2),
                'M01': round(float(moments['m01']), 2),
                'M20': round(float(moments['m20']), 2),
                'M02': round(float(moments['m02']), 2),
                'M11': round(float(moments['m11']), 2),
                # §2.2 — centroid
                'centroid_x': round(cx, 2),
                'centroid_y': round(cy, 2),
                'area': round(m00, 2),
                # §2.3 — central moments
                'mu20': round(mu20, 4),
                'mu02': round(mu02, 4),
                'mu11': round(mu11, 4),
                'mu30': round(mu30, 4),
                'mu03': round(mu03, 4),
                # §2.4 — normalized moments
                'eta20': eta['eta20'],
                'eta02': eta['eta02'],
                'eta11': eta['eta11'],
                # §2.5 — orientation
                'theta_deg': theta,
                'anisotropy': aniso,
                # §2.6 — ellipse
                'semi_major': semi_major,
                'semi_minor': semi_minor,
                'eccentricity': eccentricity,
                # §2.7 — Hu invariants (log scale, φ₁–φ₇)
                'phi1': round(hu_log[0], 4),
                'phi2': round(hu_log[1], 4),
                'phi3': round(hu_log[2], 4),
                'phi4': round(hu_log[3], 4),
                'phi5': round(hu_log[4], 4),
                'phi6': round(hu_log[5], 4),
                'phi7': round(hu_log[6], 4),
            },
        }
