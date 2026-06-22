"""
Active Contour (Snake) — deformable boundary segmentation.

Three energy-minimizing contour methods from scikit-image:
  • Classic Snake          — skimage active_contour (edge/line forces, tension/stiffness)
  • Morphological Chan-Vese — region-based level set, no edges needed
  • Morph. GAC (edges)      — geodesic active contour driven by image gradients

Initialisation (in priority order):
  1. **Init Points** from a Manual Points node — used as ordered contour vertices
     (classic snake) or as a seed blob (region methods).
  2. **Init Mask** input — used as the starting region / level set.
  3. Otherwise a centered Circle / Ellipse / Full-frame shape.

Heavy iterative solve → press **Run** (or enable **Live** for static images).
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np

try:
    from skimage.segmentation import (
        active_contour,
        morphological_chan_vese,
        morphological_geodesic_active_contour,
        inverse_gaussian_gradient,
    )
    from skimage.filters import gaussian
    _SKIMAGE_OK = True
except Exception:
    _SKIMAGE_OK = False


def _hex_to_bgr(hex_str, fallback=(85, 51, 255)):
    c = str(hex_str or '').strip()
    if not c.startswith('#'):
        c = '#' + c
    try:
        if len(c) == 7:
            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        elif len(c) == 4:
            r, g, b = int(c[1] * 2, 16), int(c[2] * 2, 16), int(c[3] * 2, 16)
        else:
            return fallback
        return (b, g, r)
    except Exception:
        return fallback


def _points_to_pixels(pts_in, w, h):
    out = []
    if not isinstance(pts_in, list):
        return out
    for p in pts_in:
        try:
            if isinstance(p, dict):
                if int(p.get('label', 1)) == 0:
                    continue  # ignore background points for init
                x, y = float(p.get('x', 0)), float(p.get('y', 0))
            else:
                x, y = float(p[0]), float(p[1])
        except Exception:
            continue
        px = x * w if 0.0 <= x <= 1.0 else x
        py = y * h if 0.0 <= y <= 1.0 else y
        out.append((px, py))
    return out


@vision_node(
    type_id='feat_active_contour',
    label='Active Contour (Snake)',
    category='segmentation',
    icon='PenTool',
    description=(
        "Deformable 'snake' segmentation: an initial contour relaxes onto object "
        "boundaries by minimizing internal (smoothness) + external (image) energy. "
        "Methods: classic Snake, Morphological Chan-Vese (region), and geodesic "
        "active contour (edges). Initialize with Manual Points, a mask, or a shape. "
        "Press Run (or enable Live)."
    ),
    resizable=True,
    min_width=240,
    min_height=220,
    colorable=True,
    inputs=[
        {'id': 'image',  'color': 'image', 'label': 'Image'},
        {'id': 'points', 'color': 'list',  'label': 'Init Points'},
        {'id': 'mask',   'color': 'mask',  'label': 'Init Mask (opt)'},
    ],
    outputs=[
        {'id': 'main',    'color': 'image',  'label': 'Overlay'},
        {'id': 'mask',    'color': 'mask',   'label': 'Region Mask'},
        {'id': 'contour', 'color': 'list',   'label': 'Contour'},
        {'id': 'count',   'color': 'scalar', 'label': 'Area (px)'},
    ],
    params=[
        {'id': 'method', 'label': 'Method', 'type': 'enum',
         'options': ['Classic Snake', 'Morph. Chan-Vese', 'Morph. GAC (edges)'],
         'default': 1},
        {'id': 'init_shape', 'label': 'Init (no points/mask)', 'type': 'enum',
         'options': ['Circle', 'Ellipse', 'Full frame'], 'default': 0},
        {'id': 'init_radius', 'label': 'Init Size (%)', 'type': 'number',
         'min': 5, 'max': 98, 'default': 45},
        {'id': 'iterations', 'label': 'Iterations', 'type': 'int',
         'min': 10, 'max': 600, 'default': 150},
        {'id': 'pre_blur', 'label': 'Pre-blur (sigma)', 'type': 'float',
         'min': 0.0, 'max': 8.0, 'default': 2.0},
        {'id': '_sec_forces', 'label': 'Contour Forces', 'type': 'section'},
        {'id': 'smoothing', 'label': 'Smoothing', 'type': 'int',
         'min': 0, 'max': 4, 'default': 1},
        {'id': 'alpha', 'label': 'Alpha (tension)', 'type': 'float',
         'min': 0.001, 'max': 0.5, 'default': 0.015},
        {'id': 'beta', 'label': 'Beta (stiffness)', 'type': 'float',
         'min': 0.1, 'max': 50.0, 'default': 10.0},
        {'id': 'w_edge', 'label': 'Edge Attraction', 'type': 'float',
         'min': -5.0, 'max': 5.0, 'default': 1.0},
        {'id': 'cv_lambda', 'label': 'CV In/Out Balance', 'type': 'float',
         'min': 0.25, 'max': 4.0, 'default': 1.0},
        {'id': 'balloon', 'label': 'GAC Balloon', 'type': 'float',
         'min': -2.0, 'max': 2.0, 'default': -1.0},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'contour_color', 'label': 'Contour Color', 'type': 'color', 'default': '#ff3355'},
        {'id': 'thickness', 'label': 'Thickness', 'type': 'int', 'min': 1, 'max': 6, 'default': 2},
        {'id': 'fill_opacity', 'label': 'Fill Opacity (%)', 'type': 'number',
         'min': 0, 'max': 100, 'default': 22},
        {'id': 'show_init', 'label': 'Show Init', 'type': 'bool', 'default': False},
        {'id': '_sec_control', 'label': 'Control', 'type': 'section'},
        {'id': 'live', 'label': 'Live (auto-run)', 'type': 'bool', 'default': False},
        {'id': 'run', 'label': 'Run', 'type': 'trigger', 'default': False},
    ],
)
class ActiveContourNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key = None
        self._cache_mask = None
        self._init_mask = None

    def _hint(self, img, text):
        if img is None:
            return {'main': None, 'mask': None, 'contour': [], 'count': 0}
        out = img.copy()
        if out.ndim == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        h = out.shape[0]
        cv2.rectangle(out, (0, h - 26), (200, h), (0, 0, 0), -1)
        cv2.putText(out, text, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (255, 255, 255), 1, cv2.LINE_AA)
        return {'main': out, 'mask': None, 'contour': [], 'count': 0}

    def _build_init_mask(self, init_pts, mask_in, params, w, h):
        """Return a binary uint8 (0/1) init level-set/region."""
        shape = int(params.get('init_shape', 0))
        rad_pct = float(params.get('init_radius', 45)) / 100.0
        m = np.zeros((h, w), np.uint8)

        if len(init_pts) >= 3:
            poly = np.array([[int(round(x)), int(round(y))] for x, y in init_pts], np.int32)
            cv2.fillPoly(m, [cv2.convexHull(poly)], 1)
            return m
        if mask_in is not None:
            mm = mask_in
            if mm.ndim == 3:
                mm = cv2.cvtColor(mm, cv2.COLOR_BGR2GRAY)
            if mm.shape[:2] != (h, w):
                mm = cv2.resize(mm, (w, h), interpolation=cv2.INTER_NEAREST)
            return (mm > 127).astype(np.uint8)

        cx, cy = w // 2, h // 2
        if shape == 0:    # circle
            r = int(min(w, h) * 0.5 * rad_pct)
            cv2.circle(m, (cx, cy), max(2, r), 1, -1)
        elif shape == 1:  # ellipse
            cv2.ellipse(m, (cx, cy), (int(w * 0.5 * rad_pct), int(h * 0.5 * rad_pct)),
                        0, 0, 360, 1, -1)
        else:             # full frame (inset by 2px so a boundary exists)
            m[2:h - 2, 2:w - 2] = 1
        return m

    def _init_snake_curve(self, init_pts, init_mask, w, h, n=220):
        """Ordered closed curve of (row, col) for the classic snake."""
        if len(init_pts) >= 3:
            poly = np.array([[x, y] for x, y in init_pts], np.float32)
            hull = cv2.convexHull(poly).reshape(-1, 2)
            xy = hull
        else:
            cs, _ = cv2.findContours(init_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not cs:
                return None
            xy = max(cs, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
        # Resample to n points along the closed polyline
        xy = np.vstack([xy, xy[0]])
        seg = np.sqrt(((np.diff(xy, axis=0)) ** 2).sum(1))
        cum = np.concatenate([[0], np.cumsum(seg)])
        total = cum[-1]
        if total <= 0:
            return None
        targets = np.linspace(0, total, n, endpoint=False)
        rx = np.interp(targets, cum, xy[:, 0])
        ry = np.interp(targets, cum, xy[:, 1])
        return np.stack([ry, rx], axis=1)  # (row, col)

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'mask': None, 'contour': [], 'count': 0}
        if not _SKIMAGE_OK:
            return self._hint(img, 'scikit-image missing')

        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        img = np.ascontiguousarray(img[:, :, :3].astype(np.uint8))
        h, w = img.shape[:2]

        pts_in = inputs.get('points')
        mask_in = inputs.get('mask')
        init_pts = _points_to_pixels(pts_in, w, h)

        method = int(params.get('method', 1))
        iters = max(10, int(params.get('iterations', 150)))
        sigma = float(params.get('pre_blur', 2.0))
        smoothing = int(params.get('smoothing', 1))
        live = bool(params.get('live', False))
        triggered = bool(params.get('run', False))

        mask_sig = None
        if mask_in is not None:
            try:
                mask_sig = int(np.asarray(mask_in)[::8, ::8].astype(np.uint8).sum())
            except Exception:
                mask_sig = None
        cache_key = (
            int(hash(img[::8, ::8].tobytes())), str(pts_in), mask_sig, method, iters,
            round(sigma, 2), smoothing, int(params.get('init_shape', 0)),
            round(float(params.get('init_radius', 45)), 1),
            round(float(params.get('alpha', 0.015)), 4),
            round(float(params.get('beta', 10.0)), 3),
            round(float(params.get('w_edge', 1.0)), 3),
            round(float(params.get('cv_lambda', 1.0)), 3),
            round(float(params.get('balloon', -1.0)), 3),
        )
        if cache_key == self._cache_key and self._cache_mask is not None and not triggered:
            return self._render(img, self._cache_mask, self._init_mask, params)

        if not (live or triggered):
            if self._cache_mask is not None:
                return self._render(img, self._cache_mask, self._init_mask, params)
            return self._hint(img, 'Press Run')

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        init_mask = self._build_init_mask(init_pts, mask_in, params, w, h)
        if init_mask.sum() < 4:
            return self._hint(img, 'Bad init region')

        self.report_progress(0.3, 'Snake: evolving contour…')
        result_mask = None
        try:
            if method == 0:  # Classic snake
                snake0 = self._init_snake_curve(init_pts, init_mask, w, h)
                if snake0 is None:
                    return self._hint(img, 'Need init contour')
                smooth = gaussian(gray, sigma) if sigma > 0 else gray
                snake = active_contour(
                    smooth, snake0,
                    alpha=float(params.get('alpha', 0.015)),
                    beta=float(params.get('beta', 10.0)),
                    w_edge=float(params.get('w_edge', 1.0)),
                    gamma=0.01,
                    max_num_iter=iters,
                    boundary_condition='periodic',
                )
                result_mask = np.zeros((h, w), np.uint8)
                poly = np.stack([snake[:, 1], snake[:, 0]], axis=1)  # (x, y)
                cv2.fillPoly(result_mask, [np.round(poly).astype(np.int32)], 255)

            elif method == 1:  # Morphological Chan-Vese
                smooth = gaussian(gray, sigma) if sigma > 0 else gray
                lam = float(params.get('cv_lambda', 1.0))
                ls = morphological_chan_vese(
                    smooth, num_iter=iters, init_level_set=init_mask,
                    smoothing=smoothing, lambda1=lam, lambda2=1.0,
                )
                result_mask = (ls.astype(np.uint8) * 255)

            else:  # Morphological GAC (edges)
                gimg = inverse_gaussian_gradient(gray, sigma=max(0.5, sigma), alpha=100.0)
                ls = morphological_geodesic_active_contour(
                    gimg, num_iter=iters, init_level_set=init_mask,
                    smoothing=smoothing, balloon=float(params.get('balloon', -1.0)),
                    threshold='auto',
                )
                result_mask = (ls.astype(np.uint8) * 255)
        except Exception as e:
            self.report_progress(1.0, '')
            return self._hint(img, f'Snake failed')
        self.report_progress(1.0, '')

        # Chan-Vese may invert (foreground = larger region); keep the region that
        # best overlaps the init seed.
        if method in (1, 2) and result_mask is not None:
            inside = ((result_mask > 0) & (init_mask > 0)).sum()
            outside = ((result_mask > 0) & (init_mask == 0)).sum()
            if outside > inside and (result_mask > 0).mean() > 0.5:
                result_mask = cv2.bitwise_not(result_mask)

        self._cache_key = cache_key
        self._cache_mask = result_mask
        self._init_mask = init_mask
        return self._render(img, result_mask, init_mask, params)

    def _render(self, img, mask, init_mask, params):
        h, w = img.shape[:2]
        if mask is None:
            return self._hint(img, 'No result')
        if mask.shape[:2] != (h, w):
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

        color = _hex_to_bgr(params.get('contour_color', '#ff3355'))
        thick = int(params.get('thickness', 2))
        fill = float(params.get('fill_opacity', 22)) / 100.0
        show_init = bool(params.get('show_init', False))

        out = img.copy()
        if fill > 0:
            tint = np.zeros_like(img)
            tint[:] = color
            sel = mask > 0
            out[sel] = cv2.addWeighted(img, 1 - fill, tint, fill, 0)[sel]

        if show_init and init_mask is not None:
            ic, _ = cv2.findContours((init_mask > 0).astype(np.uint8),
                                     cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(out, ic, -1, (160, 160, 160), 1, cv2.LINE_AA)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contours, -1, color, thick, cv2.LINE_AA)

        # Largest contour as normalized list output
        contour_list = []
        if contours:
            biggest = max(contours, key=cv2.contourArea).reshape(-1, 2)
            for (x, y) in biggest:
                contour_list.append({'x': float(x) / w, 'y': float(y) / h})

        return {
            'main': out,
            'mask': mask,
            'contour': contour_list,
            'count': int(np.count_nonzero(mask)),
        }
