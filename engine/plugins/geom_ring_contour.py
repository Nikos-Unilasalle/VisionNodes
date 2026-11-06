import cv2
import numpy as np
from registry import vision_node, NodeProcessor

N_ANGLES = 360
N_STEPS = 200
SIDES = ['Inside is darker', 'Inside is brighter']


def _gray(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return g.astype(np.float32)


def _binary(m, shape):
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return (m > 0).astype(np.uint8)


def _centroid(m):
    mo = cv2.moments(m, True)
    return (mo['m10'] / mo['m00'], mo['m01'] / mo['m00']) if mo['m00'] else None


def outline_radius(mask, cx, cy):
    """Outermost outline distance from (cx, cy) for N_ANGLES directions. Outline points on the
    image frame are dropped and interpolated over (a section cut by the frame stays round)."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    p = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64)
    h, w = mask.shape
    inner = (p[:, 0] > 1) & (p[:, 0] < w - 2) & (p[:, 1] > 1) & (p[:, 1] < h - 2)
    if inner.sum() >= 8:
        p = p[inner]
    a = np.arctan2(p[:, 1] - cy, p[:, 0] - cx)
    r = np.hypot(p[:, 0] - cx, p[:, 1] - cy)
    b = ((a + np.pi) / (2 * np.pi) * N_ANGLES).astype(int) % N_ANGLES
    rb = np.zeros(N_ANGLES)
    np.maximum.at(rb, b, r)
    e = rb == 0
    if e.all():
        return None
    if e.any():
        rb[e] = np.interp(np.where(e)[0], np.where(~e)[0], rb[~e], period=N_ANGLES)
    return rb


def best_ring(score, max_step):
    """Closed path through a polar score map (rows = angles, columns = radius steps) with the
    largest total score, moving at most `max_step` columns from one angle to the next. Dynamic
    programming over three turns; the middle turn is closed and free of start effects."""
    n, m = score.shape
    s3 = np.vstack([score] * 3)
    acc = s3[0].copy()
    back = np.zeros((3 * n, m), np.int32)
    cols = np.arange(m)
    for t in range(1, 3 * n):
        best = np.full(m, -np.inf)
        arg = np.zeros(m, np.int32)
        for d in range(-max_step, max_step + 1):
            sh = np.roll(acc, d)
            if d > 0:
                sh[:d] = -np.inf
            elif d < 0:
                sh[d:] = -np.inf
            better = sh > best
            best[better] = sh[better]
            arg[better] = (cols - d)[better]
        acc = best + s3[t]
        back[t] = arg
    path = np.zeros(3 * n, np.int32)
    path[-1] = int(np.argmax(acc))
    for t in range(3 * n - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path[n:2 * n]


@vision_node(
    type_id='geom_ring_contour',
    label='Ring Contour',
    category='segmentation',
    icon='CircleDashed',
    description=(
        "Finds the closed outline of an inner body inside a region — the stele in a root, the "
        "heartwood in a trunk, a nucleus in a cell, a pupil in an iris — as the place where the "
        "image changes most sharply between inside and outside, all the way round.\n\n"
        "The image is unrolled in polar coordinates around a first guess (Prior Mask); along every "
        "ray the contrast between inside and outside is measured, and a dynamic-programming search "
        "picks the closed path with the strongest total contrast, moving only a little from one "
        "degree to the next (Max Step), so a gap or a blurred sector is bridged by its neighbours. "
        "The search stays in a band around the prior outline (Band, × the prior radius) and inside "
        "the region. The centre is then moved to the centre of the outline found and the search "
        "repeated (Passes), so an off-centre body is followed.\n\n"
        "- Smoothing σ: scale of the contrast (a few cell sizes, to see tissues rather than walls).\n"
        "- Outputs: inside mask, outline, centre and mean radius, and the mean contrast along the "
        "outline (how clear the boundary was)."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'prior', 'color': 'mask', 'label': 'Prior Mask (first guess)'},
        {'id': 'region', 'color': 'mask', 'label': 'Region (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'mask', 'color': 'mask', 'label': 'Inside'},
        {'id': 'outline', 'color': 'mask'},
        {'id': 'center_x', 'color': 'scalar'},
        {'id': 'center_y', 'color': 'scalar'},
        {'id': 'mean_radius', 'color': 'scalar', 'label': 'Mean Radius (px)'},
        {'id': 'contrast', 'color': 'scalar', 'label': 'Edge Contrast'},
    ],
    params=[
        {'id': 'side', 'label': 'Inside Is', 'type': 'enum', 'options': SIDES, 'default': 0},
        {'id': 'sigma', 'label': 'Smoothing σ (px)', 'type': 'float', 'default': 8.0, 'min': 0, 'max': 50, 'step': 0.5},
        {'id': 'band_low', 'label': 'Band Inner (× prior radius)', 'type': 'float', 'default': 0.5, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'band_high', 'label': 'Band Outer (× prior radius)', 'type': 'float', 'default': 1.5, 'min': 1, 'max': 5, 'step': 0.05},
        {'id': 'max_step', 'label': 'Max Step (per degree)', 'type': 'int', 'default': 1, 'min': 1, 'max': 10},
        {'id': 'passes', 'label': 'Passes (re-centring)', 'type': 'int', 'default': 6, 'min': 1, 'max': 20},
    ],
)
class RingContourNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {'main': None, 'mask': None, 'outline': None, 'center_x': None, 'center_y': None,
                 'mean_radius': None, 'contrast': None}
        img, prior_in = inputs.get('image'), inputs.get('prior')
        if img is None or prior_in is None:
            return empty
        gray = _gray(img)
        h, w = gray.shape
        prior = _binary(prior_in, gray.shape)
        r_in = inputs.get('region')
        region = _binary(r_in, gray.shape) if r_in is not None else np.ones((h, w), np.uint8)
        prior &= region
        c = _centroid(prior)
        if c is None:
            return empty

        feat = 255 - gray if int(params.get('side', 0)) == 0 else gray
        sig = float(params.get('sigma', 8.0))
        if sig > 0:   # average over the region only, so the background does not bleed in
            rf = region.astype(np.float32)
            feat = cv2.GaussianBlur(feat * rf, (0, 0), sig) / np.maximum(cv2.GaussianBlur(rf, (0, 0), sig), 1e-3)
        lo_f, hi_f = float(params.get('band_low', 0.5)), float(params.get('band_high', 1.5))
        step = int(params.get('max_step', 1))
        th = np.linspace(-np.pi, np.pi, N_ANGLES, endpoint=False) + np.pi / N_ANGLES
        frac = np.linspace(0, 1, N_STEPS)

        cx, cy = c
        inside, pts, edge = prior, None, 0.0
        for _ in range(max(1, int(params.get('passes', 6)))):
            rp, rs = outline_radius(prior, cx, cy), outline_radius(region, cx, cy)
            if rp is None or rs is None:
                return empty
            r_lo = lo_f * rp
            r_hi = np.maximum(np.minimum(hi_f * rp, 0.95 * rs), r_lo + 2)
            rad = r_lo[:, None] + (r_hi - r_lo)[:, None] * frac[None]
            xs = (cx + np.cos(th)[:, None] * rad).astype(np.float32)
            ys = (cy + np.sin(th)[:, None] * rad).astype(np.float32)
            polar = cv2.remap(feat, xs, ys, cv2.INTER_LINEAR)
            score = -np.gradient(polar, axis=1)        # inside-feature drops going outward
            score /= max(float(score.std()), 1e-6)
            path = best_ring(score, step)
            r_path = rad[np.arange(N_ANGLES), path]
            pts = np.stack([cx + np.cos(th) * r_path, cy + np.sin(th) * r_path], 1)
            edge = float(score[np.arange(N_ANGLES), path].mean())
            inside = np.zeros((h, w), np.uint8)
            cv2.fillPoly(inside, [np.round(pts).astype(np.int32)], 1)
            inside &= region
            nc = _centroid(inside)
            if nc is None:
                return empty
            moved = np.hypot(nc[0] - cx, nc[1] - cy)
            cx, cy = nc
            prior = inside
            if moved < 1.0:
                break

        outline = np.zeros((h, w), np.uint8)
        cv2.polylines(outline, [np.round(pts).astype(np.int32)], True, 255, 2)
        outline[region == 0] = 0
        vis = cv2.cvtColor(np.clip(gray, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        cv2.polylines(vis, [np.round(pts).astype(np.int32)], True, (0, 0, 255), 2)
        cv2.drawMarker(vis, (int(round(cx)), int(round(cy))), (0, 0, 255), cv2.MARKER_CROSS, 16, 2)
        return {'main': vis, 'mask': inside * 255, 'outline': outline, 'center_x': float(cx),
                'center_y': float(cy), 'mean_radius': float(np.sqrt(inside.sum() / np.pi)),
                'contrast': edge}
