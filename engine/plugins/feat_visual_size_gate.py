import base64
import cv2
import json
import math
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
    type_id='feat_visual_size_gate',
    label='Visual Size Gate',
    category='features',
    icon='Ruler',
    description=(
        'Filters a label map by area using a hand-drawn reference line.\n\n'
        'Draw a line across a typical object (e.g. one cell). '
        'The node estimates its area from the line length and a shape model, '
        'then keeps only regions whose area falls within ±Tolerance% of that reference.\n\n'
        'Shape models:\n'
        '  Circle  — ref = π·(d/2)²   (round cells, grains)\n'
        '  Square  — ref = d²          (rectangular objects)\n'
        '  Thin    — ref = π·(d/2)·(d/4)  (elongated, e.g. bacteria)\n\n'
        'Preview: green = accepted, red-dim = rejected, cyan line = reference.'
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'markers', 'label': 'Labels Map', 'color': 'any'},
        {'id': 'image',   'label': 'Image',       'color': 'image'},
    ],
    outputs=[
        {'id': 'mask_kept',   'label': 'Kept Mask',   'color': 'mask'},
        {'id': 'mask_rej',    'label': 'Rejected Mask', 'color': 'mask'},
        {'id': 'markers_out', 'label': 'Kept Labels', 'color': 'any'},
        {'id': 'markers_rej', 'label': 'Rejected Labels', 'color': 'any'},
        {'id': 'main',        'label': 'Preview',          'color': 'image'},
        {'id': 'count',       'label': 'Count',            'color': 'scalar'},
        {'id': 'ref_area',    'label': 'Ref Area (px²)',   'color': 'scalar'},
    ],
    params=[
        {'id': 'points',    'label': 'Reference Line', 'type': 'string', 'default': '[]'},
        {'id': 'shape',     'label': 'Shape Model',    'type': 'enum',
         'options': ['Circle', 'Square', 'Thin (rod)'], 'default': 0},
        {'id': 'tolerance',     'label': 'Tolerance (%)',      'type': 'float', 'default': 20.0, 'min': 0.0, 'max': 100.0},
        {'id': 'min_size',      'label': 'Min Size (px²)',     'type': 'int',   'default': 20, 'min': 1, 'max': 10000},
        {'id': 'auto_separate', 'label': 'Separate Objects',   'type': 'bool',  'default': True},
        {'id': 'separation',    'label': 'Separation Strength','type': 'float', 'default': 40.0, 'min': 5.0, 'max': 95.0},
        {'id': 'remap_ids',     'label': 'Remap IDs',          'type': 'bool',  'default': True},
    ],
)
class VisualSizeGateNode(NodeProcessor):
    def __init__(self):
        self._last_preview: str | None = None
        self._frame_count = 0

    def process(self, inputs, params):
        markers = inputs.get('markers')
        raw_img = inputs.get('image')
        img     = raw_img if isinstance(raw_img, np.ndarray) else None

        if markers is None:
            if img is not None:
                self._frame_count += 1
                if self._last_preview is None or self._frame_count % 6 == 0:
                    try:
                        disp = _to_uint8_bgr(img)
                        ph = min(360, disp.shape[0])
                        pw = int(ph * disp.shape[1] / disp.shape[0])
                        _, buf = cv2.imencode('.jpg', cv2.resize(disp, (pw, ph)), [cv2.IMWRITE_JPEG_QUALITY, 65])
                        self._last_preview = base64.b64encode(buf).decode('utf-8')
                    except Exception:
                        pass
            return {'markers_out': None, 'markers_rej': None, 'mask_kept': None, 'mask_rej': None, 'main': img,
                    'main_preview': self._last_preview, 'count': 0, 'ref_area': 0.0}

        m = markers.astype(np.int32)
        if m.ndim == 3:
            m = m[..., 0]
        h, w = m.shape[:2]

        # Auto-convert binary mask → instance labels
        _nonzero = np.unique(m)
        _nonzero = _nonzero[_nonzero > 0]
        if len(_nonzero) == 1:
            binary = (m > 0).astype(np.uint8)
            auto_sep = bool(params.get('auto_separate', True))
            d_max = 0.0
            if auto_sep and np.any(binary):
                dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
                d_max = float(dist.max())
            if auto_sep and d_max > 0:
                # Distance-transform watershed: separates touching objects
                sep_pct = float(params.get('separation', 40.0)) / 100.0
                _, sure_fg = cv2.threshold(dist, d_max * sep_pct, 255, cv2.THRESH_BINARY)
                sure_fg = sure_fg.astype(np.uint8)
                _, markers_ws = cv2.connectedComponents(sure_fg)
                markers_ws = (markers_ws + 1).astype(np.int32)
                markers_ws[(binary > 0) & (sure_fg == 0)] = 0  # unknown region
                bgr = _to_uint8_bgr(img).copy() if img is not None else np.zeros((h, w, 3), dtype=np.uint8)
                if bgr.shape[:2] != (h, w):
                    bgr = cv2.resize(bgr, (w, h))
                m = cv2.watershed(bgr, markers_ws)  # modifies bgr in-place (copy above protects img)
                m[m <= 1] = 0  # remove background (1) and borders (-1)
                m = m.astype(np.int32)
            else:
                _, m = cv2.connectedComponents(binary, connectivity=8)
                m = m.astype(np.int32)

        # --- Reference line → area estimate ---
        try:
            pts = json.loads(str(params.get('points', '[]')))
        except Exception:
            pts = []

        ref_area = 0.0
        p1 = p2 = None

        if len(pts) >= 2:
            p1 = (float(pts[0]['x']) * w, float(pts[0]['y']) * h)
            p2 = (float(pts[1]['x']) * w, float(pts[1]['y']) * h)
            d  = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if d > 0:
                shape = int(params.get('shape', 0))
                if shape == 0:
                    ref_area = math.pi * (d / 2.0) ** 2
                elif shape == 1:
                    ref_area = d * d
                else:
                    ref_area = math.pi * (d / 2.0) * (d / 4.0)

        tol      = float(params.get('tolerance', 20.0))
        min_size = int(params.get('min_size', 20))
        remap    = bool(params.get('remap_ids', True))

        if ref_area <= 0 or tol >= 100.0:
            min_area, max_area = 0.0, float('inf')
        else:
            t = tol / 100.0
            # Symmetric in log space: factor = 1/(1-t)
            # t=50% → [0.5×ref, 2×ref], t=90% → [0.1×ref, 10×ref]
            factor = 1.0 / (1.0 - t)
            min_area = ref_area / factor
            max_area = ref_area * factor

        # Apply min_size as hard floor — cannot be below noise threshold
        min_area = max(min_area, float(min_size))

        # --- Filter ---
        unique = np.unique(m)
        unique = unique[unique > 0]

        filtered  = np.zeros_like(m)
        rejected  = np.zeros_like(m)
        kept      = 0
        new_id    = 1
        rej_id    = 1
        all_areas = []

        for lid in unique:
            area = float(np.sum(m == lid))
            if area < min_size:
                continue  # silent noise discard
            all_areas.append(area)
            if min_area <= area <= max_area:
                filtered[m == lid] = new_id if remap else int(lid)
                if remap:
                    new_id += 1
                kept += 1
            else:
                rejected[m == lid] = rej_id if remap else int(lid)
                if remap:
                    rej_id += 1

        median_area = float(np.median(all_areas)) if all_areas else 0.0

        mask_kept = (filtered > 0).astype(np.uint8) * 255
        mask_rej  = (rejected > 0).astype(np.uint8) * 255

        # --- Preview ---
        if img is not None:
            base = _to_uint8_bgr(img)
            if base.shape[:2] != (h, w):
                base = cv2.resize(base, (w, h))
        else:
            base = np.zeros((h, w, 3), dtype=np.uint8)

        preview = base.copy()

        # Accepted: original colors intact
        # Rejected: dimmed + desaturated so accepted cells stand out naturally
        rejected_mask = mask_rej > 0
        if np.any(rejected_mask):
            preview[rejected_mask] = (preview[rejected_mask].astype(np.float32) * 0.25).clip(0, 255).astype(np.uint8)

        if p1 is not None and p2 is not None and ref_area > 0:
            ip1 = (int(round(p1[0])), int(round(p1[1])))
            ip2 = (int(round(p2[0])), int(round(p2[1])))
            cv2.line(preview, ip1, ip2, (0, 230, 255), 2, cv2.LINE_AA)
            cv2.circle(preview, ip1, 4, (0, 230, 255), -1)
            cv2.circle(preview, ip2, 4, (0, 230, 255), -1)
            mx, my = int((p1[0] + p2[0]) / 2), int((p1[1] + p2[1]) / 2)
            d = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            shape = int(params.get('shape', 0))
            if shape == 0:
                cv2.circle(preview, (mx, my), int(d / 2), (0, 230, 255), 1, cv2.LINE_AA)
            elif shape == 1:
                half = int(d / 2)
                cv2.rectangle(preview, (mx - half, my - half), (mx + half, my + half), (0, 230, 255), 1)
            label_y = max(18, my - int(d / 2) - 6)
            cv2.putText(preview, f'ref={int(ref_area)}  med={int(median_area)}  n={kept}',
                        (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 230, 255), 1, cv2.LINE_AA)
        else:
            cv2.putText(preview, 'Draw a line on a reference object',
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 180, 255), 1, cv2.LINE_AA)
            cv2.putText(preview, f'n={kept}  (no ref - passing all)',
                        (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (130, 130, 130), 1, cv2.LINE_AA)

        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                ph = min(360, preview.shape[0])
                pw = int(ph * preview.shape[1] / preview.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview, (pw, ph)), [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'markers_out':  filtered,
            'markers_rej':  rejected,
            'mask_kept':    mask_kept,
            'mask_rej':     mask_rej,
            'main':         preview,
            'main_preview': self._last_preview,
            'count':        kept,
            'ref_area':     round(ref_area, 1),
            'median_area':  round(median_area, 1),
        }
