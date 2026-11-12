import cv2
import numpy as np
from registry import vision_node, NodeProcessor

N_ANGLES = 720


def _binary(img, shape=None):
    m = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    if shape is not None and m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return (m > 0).astype(np.uint8)


def _centroid(m):
    mo = cv2.moments(m, True)
    if mo['m00'] == 0:
        return None
    return mo['m10'] / mo['m00'], mo['m01'] / mo['m00']


TORN_DEPTH = 0.12        # a ray this much shorter than the convex hull crosses a bite or a tear
ENVELOPE_PASSES = 3      # restore the outline, re-centre, repeat


def _filled(mask_or_pts, shape):
    out = np.zeros(shape, np.uint8)
    cv2.fillPoly(out, [np.round(mask_or_pts).astype(np.int32)], 1)
    return out


def intact_envelope(mask):
    """The outline the object would have without bites or torn sectors, filled.

    Rays much shorter than the convex hull's (a notch deeper than TORN_DEPTH) cross damage:
    their length is interpolated around the circle from the intact rays on both sides, so a
    torn sector is closed by an arc rather than by the hull's chord. The centre is then moved to
    the centroid of the restored outline and the restoration repeated."""
    mask = (np.asarray(mask) > 0).astype(np.uint8)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return mask
    hull = _filled(cv2.convexHull(max(cnts, key=cv2.contourArea))[:, 0, :], mask.shape)
    restored = hull
    th = (np.arange(N_ANGLES) + 0.5) / N_ANGLES * 2 * np.pi - np.pi
    for _ in range(ENVELOPE_PASSES):
        c = _centroid(restored)
        if c is None:
            return hull
        r_obj = _boundary_radius(mask, c[0], c[1], 0, False)
        r_hull = _boundary_radius(hull, c[0], c[1], 0, False)
        if r_obj is None or r_hull is None:
            return hull
        torn = r_obj < (1 - TORN_DEPTH) * r_hull
        if torn.all():
            return hull
        r = r_obj.copy()
        if torn.any():
            r[torn] = np.interp(np.flatnonzero(torn), np.flatnonzero(~torn), r_obj[~torn], period=N_ANGLES)
        restored = _filled(np.c_[c[0] + np.cos(th) * r, c[1] + np.sin(th) * r], mask.shape) | mask
    return restored


def _boundary_radius(mask, cx, cy, smooth, ignore_border):
    """Distance from the centre to the mask outline, for N_ANGLES directions (outermost point).
    With ignore_border, outline points on the image frame are dropped and the radius is
    interpolated across them (an object cut by the frame keeps its round shape)."""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64)
    if ignore_border:
        h, w = mask.shape
        inner = (pts[:, 0] > 1) & (pts[:, 0] < w - 2) & (pts[:, 1] > 1) & (pts[:, 1] < h - 2)
        if inner.sum() >= 8:
            pts = pts[inner]
    ang = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
    rad = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    bins = ((ang + np.pi) / (2 * np.pi) * N_ANGLES).astype(int) % N_ANGLES
    rb = np.zeros(N_ANGLES)
    np.maximum.at(rb, bins, rad)
    empty = rb == 0
    if empty.all():
        return None
    if empty.any():
        rb[empty] = np.interp(np.where(empty)[0], np.where(~empty)[0], rb[~empty], period=N_ANGLES)
    k = max(1, int(round(smooth / 360 * N_ANGLES))) | 1
    if k > 1:
        rb = np.convolve(np.r_[rb[-(k // 2):], rb, rb[:k // 2]], np.ones(k) / k, 'valid')
    return rb


def _angle_bin(theta):
    return ((theta + np.pi) / (2 * np.pi) * N_ANGLES).astype(int) % N_ANGLES


def _item_xy(item, w, h):
    if 'cx' in item and 'cy' in item:
        return float(item['cx']), float(item['cy'])
    if item.get('pts'):
        x, y = item['pts'][0]
        return (x * w, y * h) if item.get('relative', True) else (float(x), float(y))
    if 'x' in item and 'y' in item:
        return float(item['x']), float(item['y'])
    return None


@vision_node(
    type_id='geom_radial_coords',
    label='Radial Coordinates',
    category='measure',
    icon='Radar',
    description=(
        "Normalised radial position ρ inside a roughly round object: ρ = 0 at the centre, "
        "ρ = 1 on the outline, measured along each ray (so an oval or a lopsided shape still "
        "spans 0 → 1 in every direction). Where the object is cut by the image frame, the "
        "outline is interpolated across the cut. The centre is the centroid of the mask, or of the "
        "Centre Mask when one is connected (e.g. the stele, a nucleus, a tree pith).\n\n"
        "Outputs a position map (float, −1 outside the mask) and, when a list of objects is "
        "connected, adds 'rho', 'theta' (degrees) and 'dist_px' to each object. Use it to study "
        "how a property changes from the centre to the edge (cell size across a root, ring "
        "width in wood, colony density in a dish).\n\n"
        "- Restore Torn Outline: rays much shorter than the convex hull's cross a bite or a torn "
        "sector; the outline there is interpolated around the circle from the intact sides and "
        "the centre taken on the restored shape, so the damage neither pulls the centre away nor "
        "shortens the rays that cross it (ρ keeps its value on the intact object). The position "
        "map stays −1 outside the mask itself."
    ),
    inputs=[
        {'id': 'mask', 'color': 'mask', 'label': 'Object Mask'},
        {'id': 'center_mask', 'color': 'mask', 'label': 'Centre Mask (opt.)'},
        {'id': 'items', 'color': 'list', 'label': 'Objects (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'position', 'color': 'any', 'label': 'ρ Map (float)'},
        {'id': 'items', 'color': 'list', 'label': 'Objects + ρ'},
        {'id': 'center_x', 'color': 'scalar'},
        {'id': 'center_y', 'color': 'scalar'},
        {'id': 'mean_radius', 'color': 'scalar', 'label': 'Mean Radius (px)'},
    ],
    params=[
        {'id': 'smooth', 'label': 'Outline Smoothing (°)', 'type': 'float', 'default': 3.0, 'min': 0, 'max': 45, 'step': 0.5},
        {'id': 'ignore_border', 'label': 'Image Frame Is Not an Edge', 'type': 'bool', 'default': True},
        {'id': 'envelope', 'label': 'Restore Torn Outline', 'type': 'bool', 'default': False},
    ],
)
class RadialCoordinatesNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {'main': None, 'position': None, 'items': [], 'center_x': None, 'center_y': None,
                 'mean_radius': None}
        m_in = inputs.get('mask')
        if m_in is None:
            return empty
        mask = _binary(m_in)
        h, w = mask.shape
        c_in = inputs.get('center_mask')
        center = _centroid(_binary(c_in, mask.shape)) if c_in is not None else None
        reference = intact_envelope(mask) if bool(params.get('envelope', False)) else mask
        center = center or _centroid(reference)
        if center is None:
            return empty
        cx, cy = center
        rb = _boundary_radius(reference, cx, cy, float(params.get('smooth', 3.0)),
                              bool(params.get('ignore_border', True)))
        if rb is None:
            return empty

        yy, xx = np.mgrid[0:h, 0:w]
        theta = np.arctan2(yy - cy, xx - cx)
        rho = np.hypot(xx - cx, yy - cy) / np.maximum(rb[_angle_bin(theta)], 1e-6)
        position = np.where(mask > 0, np.minimum(rho, 1.0), -1.0).astype(np.float32)

        items = []
        for it in inputs.get('items') or []:
            xy = _item_xy(it, w, h) if isinstance(it, dict) else None
            if xy is None:
                continue
            t = np.arctan2(xy[1] - cy, xy[0] - cx)
            d = float(np.hypot(xy[0] - cx, xy[1] - cy))
            items.append({**it, 'rho': float(d / max(rb[_angle_bin(np.array(t))], 1e-6)),
                          'theta': float(np.degrees(t)), 'dist_px': d})

        vis = cv2.applyColorMap((np.clip(position, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
        vis[mask == 0] = 0
        for f in (0.25, 0.5, 0.75):
            iso = ((position >= f) & (position > 0)).astype(np.uint8)
            cnts, _ = cv2.findContours(iso, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(vis, cnts, -1, (255, 255, 255), 1)
        cv2.drawMarker(vis, (int(round(cx)), int(round(cy))), (255, 255, 255), cv2.MARKER_CROSS, 16, 2)
        return {'main': vis, 'position': position, 'items': items, 'center_x': float(cx),
                'center_y': float(cy), 'mean_radius': float(rb.mean())}
