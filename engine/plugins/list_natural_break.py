import numpy as np
from registry import vision_node, NodeProcessor


def _to_floats(values):
    if values is None:
        return np.array([], dtype=np.float64)
    arr = np.asarray(values, dtype=np.float64).ravel()
    return arr[np.isfinite(arr)]


def _otsu_split(sorted_vals):
    """Index k maximizing between-class variance for the split sorted_vals[:k] | sorted_vals[k:]."""
    n = len(sorted_vals)
    csum = np.cumsum(sorted_vals)
    total = csum[-1]
    k = np.arange(1, n)
    w0 = k / n
    w1 = 1.0 - w0
    m0 = csum[:-1] / k
    m1 = (total - csum[:-1]) / (n - k)
    between = w0 * w1 * (m0 - m1) ** 2
    return int(k[np.argmax(between)])


@vision_node(
    type_id='list_natural_break',
    label='List Natural Break',
    category='analyze',
    icon='SplitSquareHorizontal',
    description=(
        "Finds the natural break that best separates a list of numbers into two groups "
        "(Otsu's criterion in 1-D). Log scale suits sizes/areas. Typical use: split object "
        "areas into 'small' and 'large' without a hand-picked threshold, then feed the "
        "threshold to a Blob Filter."
    ),
    inputs=[{'id': 'values', 'color': 'list'}, {'id': 'min_value', 'color': 'scalar', 'label': 'Ignore Below'}],
    outputs=[
        {'id': 'threshold', 'color': 'scalar'},
        {'id': 'count_above', 'color': 'scalar', 'label': 'Count ≥'},
        {'id': 'count_below', 'color': 'scalar', 'label': 'Count <'},
        {'id': 'above', 'color': 'list'},
        {'id': 'below', 'color': 'list'},
    ],
    params=[
        {'id': 'log_scale', 'label': 'Log Scale', 'type': 'bool', 'default': True},
        {'id': 'min_value', 'label': 'Ignore Below', 'type': 'float', 'default': 0.0, 'min': 0},
    ],
)
class ListNaturalBreakNode(NodeProcessor):
    def process(self, inputs, params):
        vals = _to_floats(inputs.get('values'))
        vals = vals[vals >= float(params.get('min_value', 0.0))]
        use_log = bool(params.get('log_scale', True))
        if use_log:
            vals = vals[vals > 0]
        if vals.size == 0:
            return {'threshold': None, 'count_above': 0, 'count_below': 0, 'above': [], 'below': []}

        ordered = np.sort(vals)
        if ordered.size == 1 or ordered[0] == ordered[-1]:
            threshold = float(ordered[0])
        else:
            space = np.log(ordered) if use_log else ordered
            k = _otsu_split(space)
            mid = (space[k - 1] + space[k]) / 2.0
            threshold = float(np.exp(mid) if use_log else mid)

        above = ordered[ordered >= threshold]
        below = ordered[ordered < threshold]
        return {
            'threshold': threshold,
            'count_above': int(above.size),
            'count_below': int(below.size),
            'above': above.tolist(),
            'below': below.tolist(),
        }
