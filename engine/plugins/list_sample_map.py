import numpy as np
from registry import vision_node, NodeProcessor


def _coord(item, key):
    try:
        v = float(item.get(key))
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


@vision_node(
    type_id='list_sample_map',
    label='List Sample Map',
    category='analyze',
    icon='Crosshair',
    description=(
        "Reads a value map (float field, image, label map…) at the position of every object "
        "of a list and stores it under a new key. Typical use: give each cell its coordinate "
        "in a custom frame (e.g. the elliptical ρ of Ellipse Propagation) before a Profile "
        "Zoning, or tag objects with the zone they sit in. Objects outside the map or on a "
        "NaN value are dropped (counted in Dropped)."
    ),
    inputs=[
        {'id': 'items', 'color': 'list', 'label': 'Objects'},
        {'id': 'map', 'color': 'any', 'label': 'Value Map'},
    ],
    outputs=[
        {'id': 'items', 'color': 'list', 'label': 'Objects + value'},
        {'id': 'values', 'color': 'list', 'label': 'Values'},
        {'id': 'dropped', 'color': 'scalar', 'label': 'Dropped'},
    ],
    params=[
        {'id': 'key', 'label': 'New Key', 'type': 'string', 'default': 'value'},
        {'id': 'x_key', 'label': 'X Key', 'type': 'string', 'default': 'cx'},
        {'id': 'y_key', 'label': 'Y Key', 'type': 'string', 'default': 'cy'},
    ],
)
class ListSampleMapNode(NodeProcessor):
    def process(self, inputs, params):
        items = inputs.get('items') or []
        field = inputs.get('map')
        if not isinstance(field, np.ndarray) or field.ndim not in (2, 3):
            return {'items': [], 'values': [], 'dropped': len(items)}
        if field.ndim == 3:
            field = field[..., 0]
        key = str(params.get('key', 'value') or 'value')
        kx, ky = str(params.get('x_key', 'cx')), str(params.get('y_key', 'cy'))
        h, w = field.shape

        out, values = [], []
        for it in items:
            if not isinstance(it, dict):
                continue
            x, y = _coord(it, kx), _coord(it, ky)
            if x is None or y is None:
                continue
            c, r = int(round(x)), int(round(y))
            if not (0 <= r < h and 0 <= c < w):
                continue
            v = float(field[r, c])
            if not np.isfinite(v):
                continue
            out.append({**it, key: v})
            values.append(v)
        return {'items': out, 'values': values, 'dropped': len(items) - len(out)}
