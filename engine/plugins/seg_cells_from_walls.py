import cv2
import numpy as np
from registry import vision_node, NodeProcessor

K3 = np.ones((3, 3), np.uint8)


def _binary(m, shape=None):
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if shape is not None and m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


def thin_walls(walls, region, min_size=15):
    """Walls reduced to their centre line, then given a uniform 3-px thickness: thick and thin
    walls cut the lumens the same way."""
    from skimage import morphology
    w = morphology.remove_small_objects(walls & region, max_size=min_size)
    return cv2.dilate(morphology.skeletonize(w).astype(np.uint8), K3) > 0


def lumens(walls, region, min_area, max_area, min_solidity):
    """Label map of the spaces enclosed by walls, kept when compact and of plausible size."""
    from scipy import ndimage as ndi
    from skimage import measure
    lum = cv2.morphologyEx((region & ~walls).astype(np.uint8), cv2.MORPH_OPEN,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))) > 0
    holes = ndi.binary_fill_holes(lum) & ~lum
    small, n = ndi.label(holes)
    if n:
        sizes = ndi.sum(holes, small, np.arange(1, n + 1))
        lum |= np.isin(small, np.where(sizes <= 40)[0] + 1)
    lab = measure.label(lum, connectivity=1)
    ok = np.zeros(lab.max() + 1, bool)
    for r in measure.regionprops(lab):
        ok[r.label] = min_area <= r.area < max_area and r.solidity > min_solidity
    return np.where(ok[lab], lab, 0).astype(np.int32)


def keep_bright(lab, gray, min_contrast):
    """Keeps the lumens that are brighter than the 2-px ring of wall around them by at least
    `min_contrast` grey levels (median vs median): a dark space between thick walls is no cell."""
    from scipy import ndimage as ndi
    from skimage import segmentation
    n = int(lab.max())
    if n == 0:
        return lab
    idx = np.arange(1, n + 1)
    ring = segmentation.expand_labels(lab, 2)
    ring[lab > 0] = 0
    inner = ndi.median(gray, lab, idx)
    outer = ndi.median(gray, ring, idx)
    ok = np.zeros(n + 1, bool)
    ok[1:] = (np.asarray(inner) - np.asarray(outer)) >= min_contrast
    return np.where(ok[lab], lab, 0)


def add_new(base, extra, overlap):
    """Objects of `extra` that overlap the objects of `base` by less than `overlap` of their own
    area are added (on free pixels only), with fresh labels."""
    from skimage import measure
    out = base.copy()
    nxt = int(out.max()) + 1
    for r in measure.regionprops(extra):
        sl = r.slice
        m = extra[sl] == r.label
        if (base[sl][m] > 0).mean() < overlap:
            out[sl][m & (out[sl] == 0)] = nxt
            nxt += 1
    return out


def outline_of(lab):
    lf = lab.astype(np.float32)
    return (lab > 0) & ((cv2.dilate(lf, K3) != lf) | (cv2.erode(lf, K3) == 0))


def hatch(shape, step=8):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return ((xx + yy) % step) == 0


@vision_node(
    type_id='seg_cells_from_walls',
    label='Cells from Walls',
    category='segmentation',
    icon='Grid2x2',
    description=(
        "Finds cells (grains, bubbles…) as the spaces enclosed by walls in one or two wall masks. "
        "Each wall mask is first thinned to its centre line and given a uniform thickness, so "
        "thick and thin walls cut the same way; the enclosed spaces (lumens) are kept when "
        "compact (Solidity) and of plausible size. Two detectors fail in different places: the "
        "objects of Walls 2 that do not overlap those of Walls 1 are added.\n\n"
        "Existing Cells (opt.): a label map of cells already trusted (e.g. Cell Tessellation → "
        "Resolved Labels). They are kept as they are and only new cells are added around them — "
        "useful where the first method is too strict (small dark cells, cells next to vessels).\n\n"
        "Lumen test (Image connected, Min Lumen Contrast > 0): a lumen must be brighter than "
        "the wall around it — dark spaces between thick walls are left out.\n\n"
        "Each new cell takes its lumen plus a Footprint margin (part of its wall), so that its area "
        "is comparable with wall-to-wall cells. Outputs are the same as Cell Tessellation."
    ),
    inputs=[
        {'id': 'walls', 'color': 'mask', 'label': 'Walls 1'},
        {'id': 'walls_2', 'color': 'mask', 'label': 'Walls 2 (opt.)'},
        {'id': 'region', 'color': 'mask', 'label': 'Region (opt.)'},
        {'id': 'existing', 'color': 'markers', 'label': 'Existing Cells (opt.)'},
        {'id': 'exclude', 'color': 'mask', 'label': 'Exclude (opt.)'},
        {'id': 'image', 'color': 'image', 'label': 'Image (opt., lumen test)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'cells', 'color': 'list', 'label': 'Cells'},
        {'id': 'labels', 'color': 'markers', 'label': 'Cell Labels'},
        {'id': 'resolved', 'color': 'mask', 'label': 'Resolved'},
        {'id': 'interiors', 'color': 'mask', 'label': 'Cell Interiors'},
        {'id': 'unresolved', 'color': 'mask', 'label': 'Unresolved'},
        {'id': 'outlines', 'color': 'mask', 'label': 'Outlines'},
        {'id': 'count', 'color': 'scalar'},
        {'id': 'added', 'color': 'scalar', 'label': 'Cells Added'},
        {'id': 'resolved_share', 'color': 'scalar', 'label': 'Resolved Share'},
    ],
    params=[
        {'id': 'min_area', 'label': 'Min Lumen Area (px)', 'type': 'int', 'default': 12, 'min': 1, 'max': 100000},
        {'id': 'max_area', 'label': 'Max Lumen Area (px)', 'type': 'int', 'default': 6000, 'min': 10, 'max': 10000000},
        {'id': 'min_solidity', 'label': 'Min Solidity', 'type': 'float', 'default': 0.82, 'min': 0, 'max': 1, 'step': 0.02},
        {'id': 'overlap', 'label': 'Max Overlap to Add', 'type': 'float', 'default': 0.10, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'footprint', 'label': 'Footprint Margin (px)', 'type': 'int', 'default': 2, 'min': 0, 'max': 10},
        {'id': 'min_contrast', 'label': 'Min Lumen Contrast (grey levels)', 'type': 'float', 'default': 0, 'min': 0, 'max': 100, 'step': 1},
    ],
)
class CellsFromWallsNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {'main': None, 'cells': [], 'labels': None, 'resolved': None, 'interiors': None,
                 'unresolved': None, 'outlines': None, 'count': 0, 'added': 0, 'resolved_share': None}
        w1 = inputs.get('walls')
        if w1 is None:
            return empty
        from skimage import measure, segmentation
        wall1 = _binary(w1)
        h, w = wall1.shape
        r_in = inputs.get('region')
        region = _binary(r_in, (h, w)) if r_in is not None else np.ones((h, w), bool)
        ex = inputs.get('exclude')
        if ex is not None:
            region = region & ~_binary(ex, (h, w))
        if not region.any():
            return empty
        a_min, a_max = int(params.get('min_area', 12)), int(params.get('max_area', 6000))
        sol, ov = float(params.get('min_solidity', 0.82)), float(params.get('overlap', 0.10))

        found = lumens(thin_walls(wall1, region), region, a_min, a_max, sol)
        w2 = inputs.get('walls_2')
        if w2 is not None:
            found = add_new(found, lumens(thin_walls(_binary(w2, (h, w)), region), region, a_min, a_max, sol), ov)
        img = inputs.get('image')
        c_min = float(params.get('min_contrast', 0))
        if img is not None and c_min > 0:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
            if g.shape != (h, w):
                g = cv2.resize(g, (w, h))
            found = keep_bright(found, g.astype(np.float32), c_min)
        fp = int(params.get('footprint', 2))
        if fp > 0:
            found = segmentation.expand_labels(found, fp) * region

        base = inputs.get('existing')
        if isinstance(base, np.ndarray) and base.shape[:2] == (h, w):
            base = np.where(region, np.clip(base, 0, None), 0).astype(np.int32)
            n_base = len(np.unique(base)) - (1 if (base == 0).any() else 0)
            lab = add_new(base, found, ov)
        else:
            n_base = 0
            lab = found

        cells = []
        for p in measure.regionprops(lab):
            cy, cx = p.centroid
            cells.append({'cx': float(cx), 'cy': float(cy), 'area': float(p.area),
                          'radius': float(np.sqrt(p.area / np.pi)), 'perimeter': float(p.perimeter),
                          'solidity': float(p.solidity), 'score': 1.0, 'label': int(p.label)})
        resolved = lab > 0
        outline = outline_of(lab)
        unresolved = region & ~resolved
        vis = np.full((h, w, 3), 255, np.uint8)
        vis[unresolved] = (236, 236, 236)
        vis[unresolved & hatch((h, w))] = (175, 175, 175)
        vis[outline] = (40, 40, 40)
        u8 = lambda b: b.astype(np.uint8) * 255
        return {'main': vis, 'cells': cells, 'labels': lab, 'resolved': u8(resolved),
                'interiors': u8(resolved & ~outline), 'unresolved': u8(unresolved), 'outlines': u8(outline),
                'count': len(cells), 'added': len(cells) - n_base,
                'resolved_share': float(resolved.sum() / max(region.sum(), 1))}
