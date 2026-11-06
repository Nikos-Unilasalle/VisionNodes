import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _binary(m, shape):
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


@vision_node(
    type_id='seg_isolated_objects',
    label='Isolated Objects',
    category='segmentation',
    icon='CircleDot',
    description=(
        "Picks, among labelled objects (cells, grains, colonies), those that stand alone: larger "
        "than most objects of the region, round, and surrounded mostly by space where no other "
        "object was found — e.g. a few large round cells set in a dark, dense tissue, a large "
        "grain in a fine matrix, a colony far from the others.\n\n"
        "- Size: area ≥ Size Factor × the median area of the objects of the region.\n"
        "- Isolation: share of a ring around the object (Ring Width px) that holds no object "
        "(and lies inside the region, or inside Free Space Counts In when connected).\n"
        "- Roundness: 4π·area / perimeter².\n"
        "Only objects whose centre lies in the Region are considered. Outputs the selected objects "
        "(whole), the others, and the selected list."
    ),
    inputs=[
        {'id': 'labels', 'color': 'markers', 'label': 'Object Labels'},
        {'id': 'region', 'color': 'mask', 'label': 'Region (opt.)'},
        {'id': 'occupied', 'color': 'mask', 'label': 'Also Occupied (opt.)'},
        {'id': 'tissue', 'color': 'mask', 'label': 'Free Space Counts In (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'mask', 'color': 'mask', 'label': 'Selected'},
        {'id': 'others', 'color': 'mask', 'label': 'Other Objects'},
        {'id': 'items', 'color': 'list', 'label': 'Selected List'},
        {'id': 'count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'size_factor', 'label': 'Size Factor (× median)', 'type': 'float', 'default': 1.2, 'min': 0, 'max': 20, 'step': 0.1},
        {'id': 'ring', 'label': 'Ring Width (px)', 'type': 'int', 'default': 6, 'min': 1, 'max': 100},
        {'id': 'min_free', 'label': 'Min Isolation (0–1)', 'type': 'float', 'default': 0.5, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'min_round', 'label': 'Min Roundness (0–1)', 'type': 'float', 'default': 0.7, 'min': 0, 'max': 1, 'step': 0.05},
    ],
)
class IsolatedObjectsNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {'main': None, 'mask': None, 'others': None, 'items': [], 'count': 0}
        lab = inputs.get('labels')
        if not isinstance(lab, np.ndarray):
            return empty
        from scipy import ndimage as ndi
        from skimage import measure, segmentation
        lab = np.clip(lab, 0, None).astype(np.int32)
        h, w = lab.shape
        r_in = inputs.get('region')
        region = _binary(r_in, (h, w)) if r_in is not None else np.ones((h, w), bool)
        occ = lab > 0
        o_in = inputs.get('occupied')
        if o_in is not None:
            occ |= _binary(o_in, (h, w))

        props = [p for p in measure.regionprops(lab)
                 if region[min(int(p.centroid[0]), h - 1), min(int(p.centroid[1]), w - 1)]]
        if not props:
            return {**empty, 'others': np.zeros((h, w), np.uint8)}
        ids = np.array([p.label for p in props])
        area = np.array([p.area for p in props], float)
        rnd = np.array([4 * np.pi * p.area / max(p.perimeter, 1) ** 2 for p in props])
        sub = np.where(np.isin(lab, ids), lab, 0)
        ring = segmentation.expand_labels(sub, int(params.get('ring', 6)))
        ring[sub > 0] = 0
        t_in = inputs.get('tissue')
        tissue = _binary(t_in, (h, w)) if t_in is not None else region
        with np.errstate(invalid='ignore', divide='ignore'):   # an object with no ring pixel
            free = np.nan_to_num(np.asarray(ndi.mean(~occ & tissue, ring, ids), float))

        sel = (area >= float(params.get('size_factor', 1.2)) * np.median(area)) \
            & (free >= float(params.get('min_free', 0.5))) & (rnd >= float(params.get('min_round', 0.7)))
        chosen = ids[sel]
        mask = np.isin(lab, chosen)
        others = np.isin(lab, ids[~sel])
        items = [{'cx': float(p.centroid[1]), 'cy': float(p.centroid[0]), 'area': float(p.area),
                  'radius': float(np.sqrt(p.area / np.pi)), 'isolation': float(f), 'roundness': float(r),
                  'label': int(p.label)} for p, f, r, s in zip(props, free, rnd, sel) if s]
        vis = np.zeros((h, w, 3), np.uint8)
        vis[others] = (120, 120, 120)
        vis[mask] = (0, 0, 255)
        u8 = lambda b: b.astype(np.uint8) * 255
        return {'main': vis, 'mask': u8(mask), 'others': u8(others), 'items': items, 'count': int(sel.sum())}
