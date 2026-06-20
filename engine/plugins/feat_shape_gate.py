import base64
import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _to_uint8_bgr(img) -> np.ndarray:
    if not isinstance(img, np.ndarray):
        return np.zeros((64, 64, 3), dtype=np.uint8)
    if img.dtype != np.uint8:
        if img.dtype in (np.float32, np.float64):
            img = (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8) if float(img.max()) <= 1.0 \
                  else np.clip(img, 0, 255).astype(np.uint8)
        else:
            img = np.clip(img, 0, 255).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


@vision_node(
    type_id='feat_shape_gate',
    label='Shape Gate',
    category='segmentation',
    icon='Circle',
    description=(
        'Filters connected regions by shape descriptors (ch1 — Décrire une forme).\n\n'
        'Circularity C = 4π·A/P²: 1.0=perfect circle, drops when elongated OR edge rough.\n'
        'Aspect Ratio (elongation) E = L_max/L_min from oriented bbox: 1.0=square, high=elongated.\n'
        'Solidity S = A/A_convex: 1.0=fully convex, drops when concavities/fusions present.\n'
        'Convexity Cv = P_convex/P: 1.0=smooth hull, drops when edge is rough/jagged.\n'
        'Eccentricity e = √(1-λ₂/λ₁): 0=circle, →1=needle, mass-weighted.\n'
        'Roundness Rd = 4A/(π·L_max²): 1.0=circle, insensitive to edge roughness.\n\n'
        'All active filters are AND-combined. Disable any to use only the others.\n'
        'Preview: natural colors=kept, dimmed=rejected, bounding box colored.'
    ),
    resizable=True,
    min_width=240,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'mask',  'label': 'Mask',  'color': 'mask'},
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'mask_kept', 'label': 'Kept Mask',     'color': 'mask'},
        {'id': 'mask_rej',  'label': 'Rejected Mask', 'color': 'mask'},
        {'id': 'main',      'label': 'Preview',       'color': 'image'},
        {'id': 'count',     'label': 'Count',         'color': 'scalar'},
    ],
    params=[
        # ── Size (always visible) ─────────────────────────────────────────────
        {'id': 'min_size', 'label': 'Min Size (px²)', 'type': 'int',
         'default': 20, 'min': 1, 'max': 50000},

        # ── Section: Bord (contour quality) ──────────────────────────────────
        {'id': '_sec_bord', 'label': 'Bord', 'type': 'section'},

        {'id': 'use_circularity', 'label': 'Circularity  C = 4πA/P²', 'type': 'bool',
         'default': True},
        {'id': 'min_circularity', 'label': 'Min C',  'type': 'float',
         'default': 0.35, 'min': 0.0, 'max': 1.0, 'step': 0.05},

        {'id': 'use_convexity',   'label': 'Convexity  Cv = P_cvx/P', 'type': 'bool',
         'default': False},
        {'id': 'min_convexity',   'label': 'Min Cv', 'type': 'float',
         'default': 0.80, 'min': 0.0, 'max': 1.0, 'step': 0.05},

        # ── Section: Forme (global shape) ─────────────────────────────────────
        {'id': '_sec_forme', 'label': 'Forme', 'type': 'section'},

        {'id': 'use_roundness',   'label': 'Roundness  Rd = 4A/πL²',  'type': 'bool',
         'default': False},
        {'id': 'min_roundness',   'label': 'Min Rd', 'type': 'float',
         'default': 0.60, 'min': 0.0, 'max': 1.0, 'step': 0.05},

        {'id': 'use_solidity',    'label': 'Solidity  S = A/A_cvx',   'type': 'bool',
         'default': False},
        {'id': 'min_solidity',    'label': 'Min S',  'type': 'float',
         'default': 0.80, 'min': 0.0, 'max': 1.0, 'step': 0.05},

        # ── Section: Élongation (elongation) ──────────────────────────────────
        {'id': '_sec_elon', 'label': 'Élongation', 'type': 'section'},

        {'id': 'use_aspect',       'label': 'Aspect Ratio  E = L/l',  'type': 'bool',
         'default': False},
        {'id': 'max_aspect',       'label': 'Max E',  'type': 'float',
         'default': 3.0, 'min': 1.0, 'max': 50.0, 'step': 0.5},

        {'id': 'use_eccentricity', 'label': 'Eccentricity  e = √(1−λ₂/λ₁)', 'type': 'bool',
         'default': False},
        {'id': 'max_eccentricity', 'label': 'Max e',  'type': 'float',
         'default': 0.90, 'min': 0.0, 'max': 1.0, 'step': 0.05},
    ],
)
class ShapeGateNode(NodeProcessor):
    def __init__(self):
        self._last_preview: str | None = None
        self._frame_count = 0

    def process(self, inputs, params):
        mask_in = inputs.get('mask')
        raw_img = inputs.get('image')
        img = raw_img if isinstance(raw_img, np.ndarray) else None

        def _passthrough():
            return {
                'mask_kept': None, 'mask_rej': None,
                'main': img, 'main_preview': self._last_preview, 'count': 0,
            }

        if mask_in is None or not isinstance(mask_in, np.ndarray):
            return _passthrough()

        m = mask_in
        if m.ndim == 3:
            m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.shape[2] == 3 else m[..., 0]
        binary = (m > 0).astype(np.uint8)

        h, w = binary.shape[:2]

        use_circ  = bool(params.get('use_circularity',  True))
        min_circ  = float(params.get('min_circularity', 0.35))
        use_ar    = bool(params.get('use_aspect',       False))
        max_ar    = float(params.get('max_aspect',      3.0))
        use_sol   = bool(params.get('use_solidity',     False))
        min_sol   = float(params.get('min_solidity',    0.80))
        use_conv  = bool(params.get('use_convexity',    False))
        min_conv  = float(params.get('min_convexity',   0.80))
        use_ecc   = bool(params.get('use_eccentricity', False))
        max_ecc   = float(params.get('max_eccentricity',0.90))
        use_round = bool(params.get('use_roundness',    False))
        min_round = float(params.get('min_roundness',   0.60))
        min_size  = int(params.get('min_size', 20))

        n_labels, labels = cv2.connectedComponents(binary, connectivity=8)

        mask_kept = np.zeros((h, w), dtype=np.uint8)
        mask_rej  = np.zeros((h, w), dtype=np.uint8)

        component_info = []
        kept = 0

        for lbl in range(1, n_labels):
            comp = (labels == lbl).astype(np.uint8)
            area = float(np.sum(comp))
            if area < min_size:
                continue

            cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            cnt = cnts[0]

            perim = float(cv2.arcLength(cnt, True))

            # Circularity: C = 4π·A/P² (ch1 §1.1)
            circ = min(1.0, (4.0 * np.pi * area) / (perim ** 2)) if perim > 0 else 0.0

            # Aspect ratio from oriented bbox: E = L_max/L_min (ch1 §1.2)
            rect = cv2.minAreaRect(cnt)
            ww, hh = rect[1]
            ar = round(max(ww, hh) / min(ww, hh), 3) if min(ww, hh) > 0 else 1.0

            # Convex hull — shared by solidity and convexity
            hull     = cv2.convexHull(cnt)
            hull_area  = float(cv2.contourArea(hull))
            hull_perim = float(cv2.arcLength(hull, True))

            # Solidity: S = A/A_convex (ch1 §1.4)
            solidity = round(area / hull_area, 3) if hull_area > 0 else 1.0

            # Convexity: Cv = P_convex/P (ch1 §1.5)
            convexity = round(hull_perim / perim, 3) if perim > 0 else 1.0

            # Eccentricity from moments: e = √(1-λ₂/λ₁) (ch1 §1.3)
            M = cv2.moments(cnt)
            if M['m00'] > 0:
                mu20 = M['mu20']
                mu02 = M['mu02']
                mu11 = M['mu11']
                term = np.sqrt((mu20 - mu02) ** 2 + 4 * mu11 ** 2)
                lam1 = (mu20 + mu02 + term) / 2
                lam2 = (mu20 + mu02 - term) / 2
                eccentricity = round(float(np.sqrt(1.0 - lam2 / lam1)), 3) if lam1 > 0 and lam2 >= 0 else 0.0
            else:
                eccentricity = 0.0

            # Roundness: Rd = 4A/(π·L_max²) (ch1 §1.9)
            lmax = float(max(ww, hh))
            roundness = round(4.0 * area / (np.pi * lmax ** 2), 3) if lmax > 0 else 0.0

            passes = (
                (not use_circ  or circ  >= min_circ)  and
                (not use_ar    or ar    <= max_ar)     and
                (not use_sol   or solidity  >= min_sol)  and
                (not use_conv  or convexity >= min_conv) and
                (not use_ecc   or eccentricity <= max_ecc) and
                (not use_round or roundness >= min_round)
            )

            pixel_mask = comp.astype(bool)
            if passes:
                mask_kept[pixel_mask] = 255
                kept += 1
            else:
                mask_rej[pixel_mask] = 255

            bx, by, bw, bh = cv2.boundingRect(cnt)
            component_info.append((bx, by, bw, bh, passes, circ, ar, solidity, convexity, eccentricity, roundness))

        # ── Preview ──
        if img is not None:
            base = _to_uint8_bgr(img)
            if base.shape[:2] != (h, w):
                base = cv2.resize(base, (w, h))
        else:
            base = np.zeros((h, w, 3), dtype=np.uint8)
            base[mask_kept > 0] = (60, 200, 60)
            base[mask_rej  > 0] = (60,  60, 200)

        preview = base.copy()

        rej_px = mask_rej > 0
        if np.any(rej_px):
            preview[rej_px] = (preview[rej_px].astype(np.float32) * 0.25).clip(0, 255).astype(np.uint8)

        for (bx, by, bw, bh, passes, circ, ar, sol, conv, ecc, rnd) in component_info:
            color = (0, 220, 80) if passes else (60, 60, 255)
            cv2.rectangle(preview, (bx, by), (bx + bw, by + bh), color, 1)

            # Build compact metric label from active filters
            parts = []
            if use_circ:  parts.append(f'C={circ:.2f}')
            if use_ar:    parts.append(f'E={ar:.1f}')
            if use_sol:   parts.append(f'S={sol:.2f}')
            if use_conv:  parts.append(f'Cv={conv:.2f}')
            if use_ecc:   parts.append(f'e={ecc:.2f}')
            if use_round: parts.append(f'Rd={rnd:.2f}')
            if parts:
                cv2.putText(
                    preview, ' '.join(parts),
                    (bx, max(by - 4, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1, cv2.LINE_AA,
                )

        cv2.putText(
            preview, f'kept: {kept}',
            (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
        )

        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                ph = min(360, preview.shape[0])
                pw = int(ph * preview.shape[1] / preview.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview, (pw, ph)),
                                     [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'mask_kept':    mask_kept,
            'mask_rej':     mask_rej,
            'main':         preview,
            'main_preview': self._last_preview,
            'count':        float(kept),
        }
