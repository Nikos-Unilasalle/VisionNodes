import cv2
import numpy as np
from registry import vision_node, NodeProcessor

K3 = np.ones((3, 3), np.uint8)


def _float_map(m):
    m = np.asarray(m)
    if m.ndim == 3:
        m = cv2.cvtColor(m.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    return m.astype(np.float32)


def _binary(m, shape):
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


def tessellate(wall, region, depth):
    """Watershed of the wall map from its h-minima (one basin per cell interior)."""
    from scipy import ndimage as ndi
    from skimage.morphology import h_minima
    from skimage.segmentation import watershed
    seeds = h_minima(wall, depth).astype(bool) & region
    return watershed(wall, ndi.label(seeds)[0], mask=region).astype(np.int32)


def edges_of(lab):
    """Pixels whose 3×3 neighbourhood holds another label (both sides of every boundary). The
    image frame counts as a boundary: a cell cut by the frame is not closed by a wall there."""
    lf = lab.astype(np.float32)
    lo = cv2.erode(lf, K3, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    hi = cv2.dilate(lf, K3, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return (lo != lf) | (hi != lf)


def outline_of(lab):
    """One-pixel boundaries: the side with the lower label, plus the outer rim."""
    lf = lab.astype(np.float32)
    return (lab > 0) & ((cv2.dilate(lf, K3) != lf) | (cv2.erode(lf, K3) == 0))


def closure(wall, lab, edge, level, ratio):
    """Share of each cell's boundary that lies on a real wall: stronger than `level` and than
    `ratio` × the cell's own interior minimum."""
    from scipy import ndimage as ndi
    n = int(lab.max())
    idx = np.arange(1, n + 1)
    floor = np.zeros(n + 1, np.float32)
    floor[1:] = ndi.minimum(wall, lab, idx)
    on_wall = edge & (wall > np.maximum(ratio * floor[lab], level))
    e_lab = np.where(edge, lab, 0)
    out = np.zeros(n + 1)
    out[1:] = ndi.sum(on_wall, e_lab, idx) / np.maximum(ndi.sum(edge, e_lab, idx), 1)
    return out


def hatch(shape, step=8):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return ((xx + yy) % step) == 0


@vision_node(
    type_id='seg_cell_tessellation',
    label='Cell Tessellation',
    category='segmentation',
    icon='Hexagon',
    description=(
        "Rebuilds every cell of a tissue (or grain of a rock, bubble of a foam) from a wall map "
        "where walls are high — typically the Ridge Filter output. Each cell interior is a basin "
        "of the map; the watershed splits the region along the wall crests, so cells tile the "
        "region with their real shape (territory = cell up to the middle of its walls).\n\n"
        "Every cell is then checked: it is RESOLVED only if a wall really closes it (Closure: "
        "share of its outline lying on a wall stronger than Wall Level and than Wall Ratio × "
        "its interior) and if its shape is compact (Solidity). In blurred areas, walls are "
        "missing, cells fail the test and the area is reported as UNRESOLVED (hatched in the "
        "view) instead of being filled with invented cells.\n\n"
        "- Seed Depth: how much a basin must dip below its rim to be a cell (lower = more, "
        "smaller cells).\n"
        "- Outputs: the resolved cells as a list (cx, cy, area, radius = equivalent radius, "
        "perimeter, solidity, score = closure), the label map, Resolved (cells including their "
        "walls), Cell Interiors (cells separated by a one-pixel gap, for blob tools), "
        "Unresolved (region − resolved), Outlines, and the label map of the resolved cells only."
    ),
    inputs=[
        {'id': 'walls', 'color': 'any', 'label': 'Wall Map (high = wall)'},
        {'id': 'mask', 'color': 'mask', 'label': 'Region (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'cells', 'color': 'list', 'label': 'Resolved Cells'},
        {'id': 'labels', 'color': 'markers', 'label': 'Label Map (all)'},
        {'id': 'resolved_labels', 'color': 'markers', 'label': 'Resolved Labels'},
        {'id': 'resolved', 'color': 'mask', 'label': 'Resolved'},
        {'id': 'interiors', 'color': 'mask', 'label': 'Cell Interiors'},
        {'id': 'unresolved', 'color': 'mask', 'label': 'Unresolved'},
        {'id': 'outlines', 'color': 'mask', 'label': 'Outlines'},
        {'id': 'count', 'color': 'scalar'},
        {'id': 'resolved_share', 'color': 'scalar', 'label': 'Resolved Share'},
    ],
    params=[
        {'id': 'smooth', 'label': 'Pre-smoothing σ (px)', 'type': 'float', 'default': 1.0, 'min': 0, 'max': 10, 'step': 0.5},
        {'id': 'depth', 'label': 'Seed Depth', 'type': 'float', 'default': 0.3, 'min': 0.01, 'max': 50, 'step': 0.05},
        {'id': 'wall_level', 'label': 'Wall Level', 'type': 'float', 'default': 0.7, 'min': 0, 'max': 255, 'step': 0.05},
        {'id': 'wall_ratio', 'label': 'Wall Ratio', 'type': 'float', 'default': 3.0, 'min': 1, 'max': 20, 'step': 0.5},
        {'id': 'min_closure', 'label': 'Min Closure', 'type': 'float', 'default': 0.8, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'min_solidity', 'label': 'Min Solidity', 'type': 'float', 'default': 0.85, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'min_area', 'label': 'Min Area (px)', 'type': 'int', 'default': 15, 'min': 1, 'max': 100000},
        {'id': 'max_area', 'label': 'Max Area (px, 0 = none)', 'type': 'int', 'default': 0, 'min': 0, 'max': 10000000},
    ],
)
class CellTessellationNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {'main': None, 'cells': [], 'labels': None, 'resolved_labels': None, 'resolved': None, 'interiors': None,
                 'unresolved': None, 'outlines': None, 'count': 0, 'resolved_share': None}
        w_in = inputs.get('walls')
        if not isinstance(w_in, np.ndarray):
            return empty
        wall = _float_map(w_in)
        h, w = wall.shape
        m_in = inputs.get('mask')
        region = _binary(m_in, wall.shape) if m_in is not None else np.ones((h, w), bool)
        if not region.any():
            return empty
        sm = float(params.get('smooth', 1.0))
        if sm > 0:
            wall = cv2.GaussianBlur(wall, (0, 0), sm)

        lab = tessellate(wall, region, float(params.get('depth', 0.3)))
        edge = edges_of(lab)
        clo = closure(wall, lab, edge, float(params.get('wall_level', 0.7)),
                      float(params.get('wall_ratio', 3.0)))

        from skimage.measure import regionprops
        min_clo, min_sol = float(params.get('min_closure', 0.8)), float(params.get('min_solidity', 0.85))
        a_min, a_max = int(params.get('min_area', 15)), int(params.get('max_area', 0))
        ok = np.zeros(int(lab.max()) + 1, bool)
        cells = []
        for p in regionprops(lab):
            l = p.label
            if clo[l] < min_clo or p.area < a_min or (a_max and p.area > a_max):
                continue
            if p.solidity < min_sol:
                continue
            ok[l] = True
            cy, cx = p.centroid
            cells.append({'cx': float(cx), 'cy': float(cy), 'area': float(p.area),
                          'radius': float(np.sqrt(p.area / np.pi)), 'perimeter': float(p.perimeter),
                          'solidity': float(p.solidity), 'score': float(clo[l]), 'label': int(l)})

        resolved = ok[lab]
        outline = outline_of(lab)
        interiors = resolved & ~outline
        unresolved = region & ~resolved
        res_outline = outline & resolved

        vis = np.full((h, w, 3), 255, np.uint8)
        vis[unresolved] = (236, 236, 236)
        vis[unresolved & hatch((h, w))] = (175, 175, 175)
        vis[outline & unresolved] = (215, 215, 215)
        vis[res_outline] = (40, 40, 40)
        u8 = lambda b: b.astype(np.uint8) * 255
        return {'main': vis, 'cells': cells, 'labels': lab, 'resolved_labels': np.where(resolved, lab, 0),
                'resolved': u8(resolved),
                'interiors': u8(interiors), 'unresolved': u8(unresolved), 'outlines': u8(res_outline),
                'count': len(cells), 'resolved_share': float(resolved.sum() / max(region.sum(), 1))}
