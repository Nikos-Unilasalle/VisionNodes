"""
Grain Size Histogram — interactive histogram + cumulative curve rendered directly in-node.
Accepts a 'regions' list from SAM Grain Stats (diameter_um / area_cal schema) or from
Region Properties (equivalent_diameter / area schema). All outputs are serializable.
"""
from registry import vision_node, NodeProcessor
import numpy as np

# Each metric lists the region keys it accepts, most specific first, so the node
# works with either producer without the graph author having to care.
_METRICS = (
    {'label': 'Equiv. Diameter', 'keys': ('diameter_um', 'equivalent_diameter'), 'dim': 'length'},
    {'label': 'Feret Max',       'keys': ('feret_max',),                         'dim': 'length'},
    {'label': 'Feret Min',       'keys': ('feret_min',),                         'dim': 'length'},
    {'label': 'Area',            'keys': ('area_cal', 'area'),                   'dim': 'area'},
)

_DEFAULT_UNITS = {'length': 'µm', 'area': 'µm²'}
_UNIT_KEYS = {'length': 'length_unit', 'area': 'area_unit'}


def _resolve_key(regions, candidates):
    """First candidate key that carries a usable value in at least one region."""
    for key in candidates:
        for r in regions:
            value = r.get(key)
            if value is None:
                continue
            try:
                if float(value) > 0:
                    return key
            except (TypeError, ValueError):
                continue
    return None


def _resolve_unit(regions, dim):
    """Unit advertised by the producer (Region Properties), else the µm default."""
    unit_key = _UNIT_KEYS[dim]
    for r in regions:
        unit = r.get(unit_key)
        if isinstance(unit, str) and unit.strip():
            return unit.strip()
    return _DEFAULT_UNITS[dim]


@vision_node(
    type_id='geo_grain_histogram',
    label='Grain Size Histogram',
    category='geology',
    icon='BarChart2',
    description=(
        "Interactive grain size histogram + cumulative frequency curve rendered inside the node.\n"
        "Connect 'Regions' from SAM Grain Stats or from Region Properties.\n\n"
        "Shows D10 / D50 / D90 percentiles, count, mean, and std directly in the chart.\n"
        "Units follow the upstream calibration (px when uncalibrated, µm otherwise)."
    ),
    inputs=[
        {'id': 'regions', 'color': 'list', 'label': 'Regions (Grain Stats / Region Props)'},
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
        if not 0 <= metric_idx < len(_METRICS):
            metric_idx = 0
        metric = _METRICS[metric_idx]
        n_bins = int(params.get('bins', 30))

        metric_key = _resolve_key(regions, metric['keys'])
        if metric_key is None:
            # Upstream node does not expose this measurement — say so instead of
            # rendering an empty chart the user cannot explain.
            return {**empty,
                    'label': metric['label'],
                    'unit':  _DEFAULT_UNITS[metric['dim']],
                    'error': f"'{metric['label']}' not available on these regions"}

        values = []
        for r in regions:
            raw = r.get(metric_key)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                values.append(value)
        if not values:
            return empty

        arr = np.array(values, dtype=np.float32)
        counts, edges = np.histogram(arr, bins=n_bins)
        bin_centers   = ((edges[:-1] + edges[1:]) / 2).tolist()
        total         = counts.sum()
        cumulative    = (np.cumsum(counts) / total * 100).tolist() if total > 0 else []

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
            'unit':  _resolve_unit(regions, metric['dim']),
            'label': metric['label'],
        }
