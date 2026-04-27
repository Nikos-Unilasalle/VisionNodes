import numpy as np
from registry import NodeProcessor, vision_node


def canonical_corners(pts_raw):
    """Sort 4 corners into [TL, TR, BR, BL] order.
    Uses sum/diff method: TL=min(x+y), BR=max(x+y), TR=min(y-x), BL=max(y-x).
    This ensures perspective warp always produces right-side-up output.
    """
    if not pts_raw or len(pts_raw) < 4:
        return pts_raw
    pts = []
    for p in pts_raw[:4]:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append([float(p[0]), float(p[1])])
        elif isinstance(p, dict):
            pts.append([float(p.get('x', p.get('xmin', 0))), float(p.get('y', p.get('ymin', 0)))])
    if len(pts) < 4:
        return pts_raw
    a = np.array(pts)
    s = a.sum(axis=1)
    d = np.diff(a, axis=1).ravel()
    tl = pts[int(np.argmin(s))]
    br = pts[int(np.argmax(s))]
    tr = pts[int(np.argmin(d))]
    bl = pts[int(np.argmax(d))]
    return [tl, tr, br, bl]


@vision_node(
    type_id="list_region_select",
    label="Region Selector",
    category="data",
    icon="Filter",
    description="Filters and sorts a list of detection regions. Outputs the selected item and its canonical 4 corner pts (TL→TR→BR→BL) ready for perspective warp.",
    inputs=[{"id": "list_in", "color": "list"}],
    outputs=[
        {"id": "item",     "color": "dict",   "label": "Item"},
        {"id": "pts",      "color": "list",   "label": "4 Corners"},
        {"id": "list_out", "color": "list",   "label": "Filtered List"},
        {"id": "count",    "color": "scalar", "label": "Count"},
    ],
    params=[
        {"id": "sort_by",     "label": "Sort By",       "type": "enum",
         "options": ["Index", "Largest area", "Smallest area", "Best confidence"],
         "default": 1},
        {"id": "index",       "label": "Index",          "type": "scalar", "min": 0, "max": 100, "step": 1, "default": 0},
        {"id": "require_pts", "label": "Require 4 pts",  "type": "boolean", "default": True},
        {"id": "min_area",    "label": "Min Area (0-1)", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.0},
    ]
)
class RegionSelectorNode(NodeProcessor):
    def process(self, inputs, params):
        raw = inputs.get('list_in')
        if not isinstance(raw, list):
            return {"item": None, "pts": [], "list_out": [], "count": 0}

        require_pts = params.get('require_pts', True)
        min_area    = float(params.get('min_area', 0.0))

        # Filter
        items = []
        for it in raw:
            if not isinstance(it, dict):
                continue
            area = it.get('width', 0) * it.get('height', 0)
            if area < min_area:
                continue
            if require_pts and len(it.get('pts', [])) != 4:
                continue
            items.append(it)

        if not items:
            return {"item": None, "pts": [], "list_out": [], "count": 0}

        # Sort
        sort_by = int(params.get('sort_by', 1))
        if sort_by == 1:
            items.sort(key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
        elif sort_by == 2:
            items.sort(key=lambda x: x.get('width', 0) * x.get('height', 0))
        elif sort_by == 3:
            items.sort(key=lambda x: x.get('confidence', x.get('score', 0)), reverse=True)
        # sort_by==0 → keep original order, select by index

        idx = int(params.get('index', 0))
        idx = max(0, min(idx, len(items) - 1))
        selected = items[idx]

        # Canonical 4-corner pts (fixes upside-down warp)
        raw_pts = selected.get('pts', [])
        if len(raw_pts) == 4:
            pts_out = canonical_corners(raw_pts)
        else:
            # Build from AABB
            x0 = selected.get('xmin', 0);        y0 = selected.get('ymin', 0)
            x1 = x0 + selected.get('width', 0);  y1 = y0 + selected.get('height', 0)
            pts_out = canonical_corners([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])

        return {
            "item":     selected,
            "pts":      pts_out,
            "list_out": items,
            "count":    float(len(items)),
        }
