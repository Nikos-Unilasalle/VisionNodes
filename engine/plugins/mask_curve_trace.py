"""
Curve Trace — reduces a binary mask to a single-valued pixel curve.

Generic: any mask where one axis maps to a single value on the other
(a digitized chart line, a segmented ridge, a thresholded sensor trace…).
Pair with Color Mask (RGB Distance) upstream to trace a colored line in an image.
"""
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'mask_curve_trace'

_AGGREGATORS = {
    0: lambda hits: float(np.median(hits)),   # Median
    1: lambda hits: float(np.mean(hits)),     # Mean
    2: lambda hits: float(hits.min()),        # Topmost / Leftmost
    3: lambda hits: float(hits.max()),        # Bottommost / Rightmost
}


@vision_node(
    type_id='sci_curve_trace',
    label='Curve Trace',
    category='measure',
    icon='Activity',
    description="Reduces a binary mask to an ordered list of points, one per scanline, by aggregating "
                "foreground pixels along each column (or row). Turns a traced line/edge mask into a point set.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'points', 'color': 'points'}],
    params=[
        {'id': 'axis',       'label': 'Scan Axis',  'type': 'enum', 'options': ['Columns (vertical scan)', 'Rows (horizontal scan)'], 'default': 0},
        {'id': 'aggregate',  'label': 'Aggregate',  'type': 'enum', 'options': ['Median', 'Mean', 'Topmost/Leftmost', 'Bottommost/Rightmost'], 'default': 0},
    ]
)
class CurveTraceNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None or not isinstance(mask, np.ndarray) or mask.ndim != 2:
            send_notification("Curve Trace: no mask connected", level='warning', notif_id=_NOTIF)
            return {'points': []}

        axis   = int(params.get('axis', 0))
        agg_fn = _AGGREGATORS.get(int(params.get('aggregate', 0)), _AGGREGATORS[0])
        scan   = mask if axis == 0 else mask.T

        points = []
        for i in range(scan.shape[1]):
            hits = np.nonzero(scan[:, i])[0]
            if hits.size == 0:
                continue
            value = agg_fn(hits)
            points.append({'x': float(i), 'y': value} if axis == 0 else {'x': value, 'y': float(i)})

        if not points:
            send_notification("Curve Trace: mask is empty, no points extracted", level='warning', notif_id=_NOTIF)

        return {'points': points}
