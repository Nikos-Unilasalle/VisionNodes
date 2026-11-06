from collections import defaultdict

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

N_RAYS = 24
INNER_FRACS = (0.15, 0.35, 0.55)


def _gray(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return g.astype(np.float32)


def _bilinear(img, xs, ys):
    """Bilinear sampling at float coordinates (any number of points, unlike cv2.remap)."""
    h, w = img.shape
    xs = np.clip(xs, 0, w - 1.001)
    ys = np.clip(ys, 0, h - 1.001)
    x0, y0 = xs.astype(np.int32), ys.astype(np.int32)
    fx, fy = xs - x0, ys - y0
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bot = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return top * (1 - fy) + bot * fy


def _circles_px(items, w, h):
    """(x, y, r) rows in pixels from a Hough-style list (relative 'pts' + pixel 'radius') or cx/cy."""
    rows = []
    for c in items or []:
        if not isinstance(c, dict) or c.get('radius') is None:
            continue
        if 'cx' in c and 'cy' in c:
            x, y = float(c['cx']), float(c['cy'])
        elif c.get('pts'):
            x, y = c['pts'][0]
            if c.get('relative', True):
                x, y = x * w, y * h
        else:
            continue
        rows.append((x, y, float(c['radius'])))
    return np.array(rows, np.float32).reshape(-1, 3)


def _non_overlapping(c, order, spacing):
    """Greedy suppression in score order: drop a circle whose centre is closer than
    spacing × (r1 + r2) to an already kept one."""
    cell = max(8.0, float(c[:, 2].max()) * 2.0 * spacing) if len(c) else 8.0
    grid, kept = defaultdict(list), []
    for i in order:
        x, y, r = c[i]
        gx, gy = int(x // cell), int(y // cell)
        clash = any(np.hypot(x - c[j, 0], y - c[j, 1]) < spacing * (r + c[j, 2])
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid[(gx + dx, gy + dy)])
        if not clash:
            kept.append(i)
            grid[(gx, gy)].append(i)
    return np.array(kept, int)


@vision_node(
    type_id='feat_circle_verify',
    label='Circle Verify',
    category='segmentation',
    icon='CircleCheck',
    description=(
        "Keeps only the Hough circle candidates that really look like a closed round object, "
        "and gives each one a confidence score. Hough Circles is tuned loose (many candidates, "
        "several radius bands); this node checks every candidate on the image:\n"
        "- Rim: along each of 24 rays, a thin rim darker than BOTH the interior and the outside "
        "(a wall between two lumens, not a mere gradient).\n"
        "- Coverage: the fraction of rays where that rim is found (closed outline).\n"
        "- Clean interior: no internal wall crossing the circle.\n"
        "Overlapping survivors are suppressed, best score first. Up to three candidate lists "
        "can be merged (one per radius band). Typical uses: cells, pores, bubbles, beads."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'circles', 'color': 'list', 'label': 'Candidates'},
        {'id': 'circles_2', 'color': 'list', 'label': 'Candidates 2'},
        {'id': 'circles_3', 'color': 'list', 'label': 'Candidates 3'},
        {'id': 'mask', 'color': 'mask', 'label': 'Keep Inside (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'circles_list', 'color': 'list', 'label': 'Verified Circles'},
        {'id': 'mask', 'color': 'mask'},
        {'id': 'labels_map', 'color': 'markers', 'label': 'Labels'},
        {'id': 'radii', 'color': 'list'},
        {'id': 'count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'polarity', 'label': 'Object', 'type': 'enum', 'default': 0,
         'options': ['Bright inside, dark rim', 'Dark inside, bright rim']},
        {'id': 'min_contrast', 'label': 'Min Rim Contrast', 'type': 'float', 'default': 6.0, 'min': 0, 'max': 100, 'step': 0.5},
        {'id': 'min_coverage', 'label': 'Min Rim Coverage', 'type': 'float', 'default': 0.65, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'rim_tolerance', 'label': 'Rim Search ± (× r)', 'type': 'float', 'default': 0.22, 'min': 0.05, 'max': 0.5, 'step': 0.01},
        {'id': 'spacing', 'label': 'Min Spacing (× r1+r2)', 'type': 'float', 'default': 0.85, 'min': 0.3, 'max': 1.2, 'step': 0.05},
        {'id': 'high_score', 'label': 'High Confidence Score', 'type': 'float', 'default': 1.2, 'min': 0, 'max': 5, 'step': 0.1},
        {'id': 'thickness', 'label': 'Thickness', 'type': 'int', 'default': 1, 'min': 1, 'max': 6},
    ],
)
class CircleVerifyNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {'main': None, 'circles_list': [], 'mask': None, 'labels_map': None, 'radii': [], 'count': 0}
        image = inputs.get('image')
        if image is None:
            return empty
        h, w = image.shape[:2]
        c = np.concatenate([_circles_px(inputs.get(k), w, h) for k in ('circles', 'circles_2', 'circles_3')])
        c = c[c[:, 2] >= 1.5] if len(c) else c

        g = cv2.GaussianBlur(_gray(image), (0, 0), 0.7)
        if int(params.get('polarity', 0)) == 1:
            g = 255.0 - g
        out = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        mask = np.zeros((h, w), np.uint8)
        labels = np.zeros((h, w), np.int32)
        if not len(c):
            return {**empty, 'main': out, 'mask': mask, 'labels_map': labels}

        ang = np.linspace(0, 2 * np.pi, N_RAYS, endpoint=False)
        ca, sa = np.cos(ang), np.sin(ang)
        X, Y, R = c[:, 0:1], c[:, 1:2], c[:, 2:3]

        def sample(f):
            rad = R * f
            return _bilinear(g, X + rad * ca, Y + rad * sa)

        interior = np.concatenate([sample(f) for f in INNER_FRACS], 1)
        level = np.median(interior, 1, keepdims=True)
        tol = float(params.get('rim_tolerance', 0.22))
        fracs = np.linspace(1 - tol, 1 + tol, 7)
        rings = np.stack([sample(f) for f in fracs], 2)
        rim = rings.min(2)
        rim_f = fracs[rings.argmin(2)]
        outside = _bilinear(g, X + (R * rim_f + 2.5) * ca, Y + (R * rim_f + 2.5) * sa)

        cmin = float(params.get('min_contrast', 6.0))
        c_in, c_out = level - rim, outside - rim
        coverage = ((c_in > 0.66 * cmin) & (c_out > 0.33 * cmin)).mean(1)
        contrast = np.median(c_in, 1)
        dip = level[:, 0] - interior.min(1)  # internal wall → dark dip inside the circle
        score = coverage * np.clip(contrast / (dip + 4.0), 0, 4)

        ok = (coverage >= float(params.get('min_coverage', 0.65))) & (contrast > cmin) & (dip < 0.7 * contrast + 3)
        ok &= (X[:, 0] >= 0) & (X[:, 0] < w) & (Y[:, 0] >= 0) & (Y[:, 0] < h)
        m_in = inputs.get('mask')
        if m_in is not None:
            m = m_in if m_in.ndim == 2 else cv2.cvtColor(m_in, cv2.COLOR_BGR2GRAY)
            if m.shape != (h, w):
                m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
            xi = np.clip(X[:, 0].astype(int), 0, w - 1)
            yi = np.clip(Y[:, 0].astype(int), 0, h - 1)
            ok &= m[yi, xi] > 0

        idx = np.where(ok)[0]
        idx = idx[np.argsort(-score[idx], kind='stable')]
        kept = _non_overlapping(c, idx, float(params.get('spacing', 0.85)))

        high = float(params.get('high_score', 1.2))
        thick = int(params.get('thickness', 1))
        results = []
        for n, i in enumerate(kept, start=1):
            x, y, r = (float(v) for v in c[i])
            ctr, rad = (int(round(x)), int(round(y))), int(round(r))
            cv2.circle(mask, ctr, rad, 255, -1)
            cv2.circle(labels, ctr, rad, n, -1)
            cv2.circle(out, ctr, rad, (0, 0, 255) if score[i] >= high else (0, 170, 255), thick)
            results.append({
                'id': n, 'label': f'circle_{n}', '_type': 'graphics', 'shape': 'circle',
                'pts': [[x / w, y / h]], 'relative': True, 'cx': x, 'cy': y,
                'radius': r, 'radius_rel': r / w, 'area': float(np.pi * r * r),
                'score': float(score[i]), 'coverage': float(coverage[i]), 'contrast': float(contrast[i]),
                'color': '#FF0000' if score[i] >= high else '#FFAA00',
            })
        return {'main': out, 'circles_list': results, 'mask': mask, 'labels_map': labels,
                'radii': [d['radius'] for d in results], 'count': len(results)}
