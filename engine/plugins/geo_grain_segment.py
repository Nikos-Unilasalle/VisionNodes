from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='geo_grain_segment',
    label='Grain Segmentation',
    category='geology',
    icon='Layers',
    description="Segments mineral grains from thin section images using PPL+XPL gradient fusion and watershed.",
    inputs=[
        {'id': 'xpl', 'color': 'image', 'label': 'XPL'},
        {'id': 'ppl', 'color': 'image', 'label': 'PPL (optional)'},
    ],
    outputs=[
        {'id': 'overlay',    'color': 'image', 'label': 'Overlay'},
        {'id': 'labels',     'color': 'image', 'label': 'Labels'},
        {'id': 'markers',    'color': 'any',   'label': 'Markers (int32)'},
        {'id': 'boundaries', 'color': 'image', 'label': 'Boundaries'},
        {'id': 'opaques',    'color': 'image', 'label': 'Opaques'},
    ],
    params=[
        {'id': 'blur_radius',     'label': 'Blur Radius',          'type': 'int',   'default': 4,   'min': 1,   'max': 15},
        {'id': 'boundary_thresh', 'label': 'Boundary Threshold',  'type': 'int',   'default': 30,  'min': 5,   'max': 120},
        {'id': 'boundary_size',   'label': 'Boundary Kernel (px)','type': 'int',   'default': 5,   'min': 1,   'max': 21},
        {'id': 'opaque_thresh',   'label': 'Opaque Darkness',     'type': 'int',   'default': 35,  'min': 5,   'max': 100},
        {'id': 'opaque_min_px',   'label': 'Opaque Min (px)',     'type': 'int',   'default': 300, 'min': 50,  'max': 20000},
        {'id': 'min_grain_px',    'label': 'Min Grain (px)',      'type': 'int',   'default': 500, 'min': 50,  'max': 50000},
        {'id': 'fill_radius',     'label': 'Fill Radius (cracks)','type': 'int',   'default': 5,   'min': 0,   'max': 30},
        {'id': 'ppl_weight',      'label': 'PPL Weight',          'type': 'float', 'default': 0.4, 'min': 0.0, 'max': 1.0, 'step': 0.05},
    ]
)
class GeoGrainSegment(NodeProcessor):

    def _to_bgr(self, img):
        if img is None:
            return None
        if len(img.shape) == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img

    def _gray_blurred(self, img, ksize):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (ksize, ksize), 0)

    def process(self, inputs, params):
        xpl = self._to_bgr(inputs.get('xpl'))
        if xpl is None:
            return {}
        ppl = self._to_bgr(inputs.get('ppl'))

        blur_r       = int(params.get('blur_radius', 4))
        bnd_thresh   = int(params.get('boundary_thresh', 30))
        bnd_size     = int(params.get('boundary_size', 5))
        opaque_t     = int(params.get('opaque_thresh', 35))
        opaque_min   = int(params.get('opaque_min_px', 300))
        min_px       = int(params.get('min_grain_px', 500))
        fill_r       = int(params.get('fill_radius', 5))
        ppl_w        = float(params.get('ppl_weight', 0.4))

        ksize = blur_r * 2 + 1
        h, w = xpl.shape[:2]

        # ── 1. Opaque mineral detection ────────────────────────────────────
        # Opaques = large dark blobs (dark in BOTH channels if PPL available)
        xpl_gray = self._gray_blurred(xpl, ksize)
        dark_xpl = (xpl_gray < opaque_t).astype(np.uint8) * 255
        if ppl is not None:
            ppl_gray = self._gray_blurred(ppl, ksize)
            dark_ppl = (ppl_gray < opaque_t).astype(np.uint8) * 255
            dark_combined = cv2.bitwise_and(dark_xpl, dark_ppl)
        else:
            dark_combined = dark_xpl

        # Erode heavily: only large blobs survive → opaques
        k_big = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        opaque_core = cv2.erode(dark_combined, k_big)
        opaque_core = cv2.dilate(opaque_core, k_big)  # restore size

        # Keep only blobs above min area
        n, lbl, stats, _ = cv2.connectedComponentsWithStats(opaque_core)
        opaque_mask = np.zeros_like(opaque_core)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= opaque_min:
                opaque_mask[lbl == i] = 255

        # ── 2. Boundary detection via morphological gradient ──────────────
        # Morph gradient gives thick closed boundaries at every color transition
        bnd_k = bnd_size if bnd_size % 2 == 1 else bnd_size + 1
        k_bnd = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bnd_k, bnd_k))
        grad_xpl = cv2.morphologyEx(xpl_gray, cv2.MORPH_GRADIENT, k_bnd)

        if ppl is not None:
            grad_ppl = cv2.morphologyEx(ppl_gray, cv2.MORPH_GRADIENT, k_bnd)
            gradient = cv2.addWeighted(grad_xpl, 1.0 - ppl_w, grad_ppl, ppl_w, 0)
        else:
            gradient = grad_xpl

        gradient = cv2.normalize(gradient, None, 0, 255, cv2.NORM_MINMAX)
        _, boundary = cv2.threshold(gradient, bnd_thresh, 255, cv2.THRESH_BINARY)

        # ── 3. Interior = not-boundary, not-opaque ─────────────────────────
        not_boundary = cv2.bitwise_not(boundary)
        interior = cv2.bitwise_and(not_boundary, cv2.bitwise_not(opaque_mask))

        # Fill micro-fractures inside each grain WITHOUT merging adjacent grains:
        # operate per connected component (flood-fill holes within each blob)
        n, comp_lbl, stats, centroids = cv2.connectedComponentsWithStats(interior)
        clean = np.zeros_like(interior)
        markers = np.zeros((h, w), dtype=np.int32)
        markers[:] = 1   # default = background

        grain_id = 2
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < min_px:
                continue
            # Fill holes within this blob only
            blob = (comp_lbl == i).astype(np.uint8) * 255
            if fill_r > 0:
                k_fill = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (fill_r * 2 + 1, fill_r * 2 + 1))
                blob = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, k_fill)
                blob = cv2.bitwise_and(blob, cv2.bitwise_not(opaque_mask))

            clean = cv2.bitwise_or(clean, blob)

            # ONE seed per grain: erode blob to get safe interior core
            k_seed = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (max(3, fill_r), max(3, fill_r)))
            core = cv2.erode(blob, k_seed)
            if cv2.countNonZero(core) == 0:
                # Fallback: use centroid pixel as single-point seed
                cx, cy = int(centroids[i][0]), int(centroids[i][1])
                if 0 <= cy < h and 0 <= cx < w and interior[cy, cx] == 255:
                    markers[cy, cx] = grain_id
            else:
                markers[core > 0] = grain_id
            grain_id += 1

        markers[boundary == 255] = 0              # unknown zone
        markers[opaque_mask == 255] = 1           # opaques = background

        # ── 5. Watershed ───────────────────────────────────────────────────
        # seed_thresh no longer used (one-seed-per-component strategy)
        markers_ws = cv2.watershed(xpl.copy(), markers.copy())

        # ── 6. Colorize labels ─────────────────────────────────────────────
        labels_img = np.zeros((h, w, 3), dtype=np.uint8)
        for label in np.unique(markers_ws):
            if label <= 1:
                continue
            mask = markers_ws == label
            labels_img[mask] = [
                int((label * 67  + 40)  % 200 + 55),
                int((label * 137 + 80)  % 200 + 55),
                int((label * 197 + 120) % 200 + 55),
            ]
        labels_img[opaque_mask == 255] = [30, 30, 30]   # opaques = dark grey
        labels_img[markers_ws == -1] = [0, 0, 0]        # watershed lines = black

        # ── 7. Outputs ─────────────────────────────────────────────────────
        overlay = xpl.copy()
        overlay[markers_ws == -1] = [0, 0, 255]
        overlay[opaque_mask == 255] = [0, 0, 80]

        boundary_viz = cv2.cvtColor(boundary, cv2.COLOR_GRAY2BGR)
        opaque_viz = cv2.cvtColor(opaque_mask, cv2.COLOR_GRAY2BGR)

        return {
            'overlay':    overlay,
            'labels':     labels_img,
            'markers':    markers_ws,
            'boundaries': boundary_viz,
            'opaques':    opaque_viz,
        }
