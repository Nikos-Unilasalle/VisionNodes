"""
GrabCut (Graph Cut) — interactive foreground extraction.

Classic min-cut / max-flow segmentation (Boykov-Kolmogorov) via cv2.grabCut.
Designed to be driven interactively by the **Manual Points** node:
    Manual Points ──points──► GrabCut
FG points (green / label 1) become foreground seeds, BG points (red / label 0)
become background seeds. A rectangle can also be derived automatically from the
FG points, taken as a centered box, or supplied as an init mask.

Like the SAM node, GrabCut is heavy, so it does NOT run every frame: press
**Run** (trigger) or enable **Live** for static images. Results are cached on
(image, seeds, params) and reused between frames.
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np


def _hex_to_bgr(hex_str, fallback=(85, 221, 34)):
    """'#22dd55' -> (B, G, R). fallback is already BGR."""
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


def _parse_points(pts_in, w, h):
    """Manual Points list ({x,y,label} normalized) -> two pixel lists (fg, bg)."""
    fg, bg = [], []
    if not isinstance(pts_in, list):
        return fg, bg
    for p in pts_in:
        try:
            if isinstance(p, dict):
                x, y = float(p.get('x', 0)), float(p.get('y', 0))
                label = int(p.get('label', 1))
            else:  # [x, y] or [x, y, label]
                x, y = float(p[0]), float(p[1])
                label = int(p[2]) if len(p) > 2 else 1
        except Exception:
            continue
        px = int(round(x * w)) if 0.0 <= x <= 1.0 else int(round(x))
        py = int(round(y * h)) if 0.0 <= y <= 1.0 else int(round(y))
        px = max(0, min(w - 1, px))
        py = max(0, min(h - 1, py))
        (fg if label == 1 else bg).append((px, py))
    return fg, bg


@vision_node(
    type_id='feat_grabcut',
    label='GrabCut (Graph Cut)',
    category='segmentation',
    icon='Scissors',
    description=(
        "Interactive foreground extraction using the GrabCut graph-cut (min-cut/max-flow) "
        "algorithm. Connect a Manual Points node: green points = keep (foreground), "
        "red points = remove (background). Init from a rectangle around the FG points, a "
        "centered box, free scribbles, or an input mask. Press Run (or enable Live)."
    ),
    resizable=True,
    min_width=240,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',  'color': 'image', 'label': 'Image'},
        {'id': 'points', 'color': 'list',  'label': 'Seeds (Manual Points)'},
        {'id': 'mask',   'color': 'mask',  'label': 'Init Mask (opt)'},
    ],
    outputs=[
        {'id': 'main',   'color': 'image',  'label': 'Overlay'},
        {'id': 'mask',   'color': 'mask',   'label': 'FG Mask'},
        {'id': 'cutout', 'color': 'image',  'label': 'Cutout'},
        {'id': 'count',  'color': 'scalar', 'label': 'FG Pixels'},
    ],
    params=[
        {'id': 'init_mode', 'label': 'Init Mode', 'type': 'enum',
         'options': ['Rect from FG points', 'Center rect', 'Scribbles (points)', 'From input mask'],
         'default': 0},
        {'id': 'rect_margin', 'label': 'Rect Margin (%)', 'type': 'number',
         'min': 0, 'max': 40, 'default': 8},
        {'id': 'center_rect', 'label': 'Center Rect (%)', 'type': 'number',
         'min': 10, 'max': 95, 'default': 70},
        {'id': 'brush', 'label': 'Scribble Brush (px)', 'type': 'number',
         'min': 1, 'max': 80, 'default': 14},
        {'id': 'iterations', 'label': 'Iterations', 'type': 'int',
         'min': 1, 'max': 15, 'default': 5},
        {'id': 'overlay_opacity', 'label': 'Overlay Opacity (%)', 'type': 'number',
         'min': 0, 'max': 100, 'default': 50},
        {'id': 'fg_color', 'label': 'FG Color', 'type': 'color', 'default': '#22dd55'},
        {'id': 'show_contour', 'label': 'Draw Contour', 'type': 'bool', 'default': True},
        {'id': 'cutout_bg', 'label': 'Cutout BG', 'type': 'enum',
         'options': ['Black', 'White', 'Transparent (alpha)'], 'default': 0},
        {'id': 'live', 'label': 'Live (auto-run)', 'type': 'bool', 'default': False},
        {'id': 'run', 'label': 'Run', 'type': 'trigger', 'default': False},
    ],
)
class GrabCutNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key = None
        self._cache_result = None

    # ── helpers ──────────────────────────────────────────────────────────
    def _hint(self, img, text):
        """Pass the image through with a small banner when not yet computed."""
        if img is None:
            return {'main': None, 'mask': None, 'cutout': None, 'count': 0}
        out = img.copy()
        if out.ndim == 2:
            out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        h = out.shape[0]
        cv2.rectangle(out, (0, h - 26), (190, h), (0, 0, 0), -1)
        cv2.putText(out, text, (8, h - 8), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (255, 255, 255), 1, cv2.LINE_AA)
        return {'main': out, 'mask': None, 'cutout': None, 'count': 0}

    def _rect_from_points(self, fg, w, h, margin_pct):
        if not fg:
            return None
        xs = [p[0] for p in fg]
        ys = [p[1] for p in fg]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        mx = int((x1 - x0 + 1) * margin_pct / 100.0) + 6
        my = int((y1 - y0 + 1) * margin_pct / 100.0) + 6
        x0 = max(0, x0 - mx); y0 = max(0, y0 - my)
        x1 = min(w - 1, x1 + mx); y1 = min(h - 1, y1 + my)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        return (x0, y0, x1 - x0, y1 - y0)

    # ── main ─────────────────────────────────────────────────────────────
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'mask': None, 'cutout': None, 'count': 0}

        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        img = np.ascontiguousarray(img[:, :, :3].astype(np.uint8))
        h, w = img.shape[:2]

        pts_in = inputs.get('points')
        mask_in = inputs.get('mask')

        init_mode = int(params.get('init_mode', 0))
        iterations = max(1, int(params.get('iterations', 5)))
        margin = float(params.get('rect_margin', 8))
        center_pct = float(params.get('center_rect', 70))
        brush = max(1, int(params.get('brush', 14)))
        live = bool(params.get('live', False))
        triggered = bool(params.get('run', False))

        # ── run gate + cache (GrabCut is too heavy for 30 fps) ──
        mask_sig = None
        if mask_in is not None:
            try:
                mask_sig = int(np.asarray(mask_in)[::8, ::8].astype(np.uint8).sum())
            except Exception:
                mask_sig = None
        cache_key = (
            int(hash(img[::8, ::8].tobytes())), str(pts_in), mask_sig,
            init_mode, iterations, round(margin, 2), round(center_pct, 2), brush,
        )
        if cache_key == self._cache_key and self._cache_result is not None and not triggered:
            return self._render(img, self._cache_result, params)

        if not (live or triggered):
            if self._cache_result is not None:
                return self._render(img, self._cache_result, params)
            return self._hint(img, 'Press Run')

        # ── build GrabCut mask / rect ──
        fg, bg = _parse_points(pts_in, w, h)
        gc_mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
        rect = None
        mode = cv2.GC_INIT_WITH_MASK

        if init_mode == 0:  # Rect from FG points
            rect = self._rect_from_points(fg, w, h, margin)
            if rect is None:  # fall back to centered box
                init_mode = 1
        if init_mode == 1 and rect is None:  # Center rect
            bw = int(w * center_pct / 100.0)
            bh = int(h * center_pct / 100.0)
            rect = ((w - bw) // 2, (h - bh) // 2, bw, bh)

        if rect is not None:
            x, y, rw, rh = rect
            gc_mask[:] = cv2.GC_BGD
            gc_mask[y:y + rh, x:x + rw] = cv2.GC_PR_FGD
            mode = cv2.GC_INIT_WITH_MASK

        if init_mode == 3 and mask_in is not None:  # From input mask
            m = mask_in
            if m.ndim == 3:
                m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
            if m.shape[:2] != (h, w):
                m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
            gc_mask[:] = cv2.GC_PR_BGD
            gc_mask[m > 127] = cv2.GC_PR_FGD

        # Scribbles always refine on top of whatever init we have (hard seeds)
        for (px, py) in fg:
            cv2.circle(gc_mask, (px, py), brush, int(cv2.GC_FGD), -1)
        for (px, py) in bg:
            cv2.circle(gc_mask, (px, py), brush, int(cv2.GC_BGD), -1)

        has_seed = np.any((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD))
        if not has_seed:
            return self._hint(img, 'Add FG seeds / rect')

        # ── run GrabCut ──
        self.report_progress(0.3, 'GrabCut: cutting graph…')
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(img, gc_mask, rect, bgd, fgd, iterations, mode)
        except Exception as e:
            self.report_progress(1.0, '')
            return self._hint(img, 'GrabCut failed')
        self.report_progress(1.0, '')

        fg_mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
                           255, 0).astype(np.uint8)

        self._cache_key = cache_key
        self._cache_result = fg_mask
        return self._render(img, fg_mask, params)

    # ── rendering (cheap, runs every frame so visuals stay live) ──────────
    def _render(self, img, fg_mask, params):
        h, w = img.shape[:2]
        if fg_mask.shape[:2] != (h, w):
            fg_mask = cv2.resize(fg_mask, (w, h), interpolation=cv2.INTER_NEAREST)

        opacity = float(params.get('overlay_opacity', 50)) / 100.0
        fg_color = _hex_to_bgr(params.get('fg_color', '#22dd55'))
        show_contour = bool(params.get('show_contour', True))
        cutout_bg = int(params.get('cutout_bg', 0))

        # Overlay
        overlay = img.copy()
        if opacity > 0:
            tint = np.zeros_like(img)
            tint[:] = fg_color
            sel = fg_mask > 0
            overlay[sel] = cv2.addWeighted(img, 1 - opacity, tint, opacity, 0)[sel]
        if show_contour:
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, fg_color, 2, cv2.LINE_AA)

        # Cutout
        if cutout_bg == 2:  # transparent (BGRA)
            cutout = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            cutout[:, :, 3] = fg_mask
        else:
            bg_val = 0 if cutout_bg == 0 else 255
            cutout = np.full_like(img, bg_val)
            sel = fg_mask > 0
            cutout[sel] = img[sel]

        return {
            'main': overlay,
            'mask': fg_mask,
            'cutout': cutout,
            'count': int(np.count_nonzero(fg_mask)),
        }
