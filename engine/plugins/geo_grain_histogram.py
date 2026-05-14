"""
Grain Size Histogram — interactive histogram + cumulative curve rendered directly in-node.
Takes 'regions' list from sam_grain_stats. All outputs are serializable (no image array).
"""
from registry import vision_node, NodeProcessor
import numpy as np

_METRICS = ['diameter_um', 'feret_max', 'feret_min', 'area_cal']
_LABELS  = ['Equiv. Diameter', 'Feret Max', 'Feret Min', 'Area']
_UNITS   = ['µm', 'µm', 'µm', 'µm²']


@vision_node(
    type_id='geo_grain_histogram',
    label='Grain Size Histogram',
    category='geology',
    icon='BarChart2',
    description=(
        "Interactive grain size histogram + cumulative frequency curve rendered inside the node.\n"
        "Connect 'Regions' from SAM Grain Stats.\n\n"
        "Shows D10 / D50 / D90 percentiles, count, mean, and std directly in the chart."
    ),
    inputs=[
        {'id': 'regions', 'color': 'list', 'label': 'Regions (SAM Grain Stats)'},
    ],
    outputs=[],
    params=[
        {'id': 'bins',   'label': 'Bins',   'type': 'int',  'default': 30, 'min': 5, 'max': 100},
        {'id': 'metric', 'label': 'Metric', 'type': 'enum',
         'options': ['Equiv. Diameter', 'Feret Max', 'Feret Min', 'Area'], 'default': 0},
    ],
    resizable=True, min_width=240, min_height=180,
)
class GeoGrainHistogramNode(NodeProcessor):

    def process(self, inputs, params):
        empty = {'bins': [], 'counts': [], 'cumulative': [], 'count': 0}
        regions = inputs.get('regions') or []
        if not regions:
            return empty

        metric_idx = int(params.get('metric', 0))
        n_bins     = int(params.get('bins', 30))
        metric_key = _METRICS[metric_idx]
        label      = _LABELS[metric_idx]
        unit       = _UNITS[metric_idx]

        values = [float(r[metric_key]) for r in regions
                  if r.get(metric_key) is not None and float(r[metric_key]) > 0]
        if not values:
            return empty

        arr = np.array(values, dtype=np.float32)
        counts, edges = np.histogram(arr, bins=n_bins)
        bin_centers   = ((edges[:-1] + edges[1:]) / 2).tolist()
        cumulative    = (np.cumsum(counts) / counts.sum() * 100).tolist()

        return {
            'bins':       [round(b, 2) for b in bin_centers],
            'counts':     counts.tolist(),
            'cumulative': [round(c, 1) for c in cumulative],
            'd10':  round(float(np.percentile(arr, 10)), 2),
            'd50':  round(float(np.percentile(arr, 50)), 2),
            'd90':  round(float(np.percentile(arr, 90)), 2),
            'count': len(values),
            'mean':  round(float(np.mean(arr)), 2),
            'std':   round(float(np.std(arr)), 2),
            'unit':  unit,
            'label': label,
        }
