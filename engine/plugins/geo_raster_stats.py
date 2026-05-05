from registry import vision_node, NodeProcessor
import numpy as np


def _extract_bands(val):
    if val is None:
        return None, 0
    if isinstance(val, dict) and 'bands' in val:
        return val['bands'], val['count']
    return None, 0


@vision_node(
    type_id='geo_band_stats',
    label='Band Statistics',
    category='geo',
    icon='BarChart',
    description="Per-band statistics (min, max, mean, std, median). Accepts matrix data or geotiff.",
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF'},
        {'id': 'data',    'color': 'any',     'label': 'Matrix'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Pass-through'},
        {'id': 'stats',   'color': 'dict',    'label': 'All Bands'},
        {'id': 'min',     'color': 'scalar'},
        {'id': 'max',     'color': 'scalar'},
        {'id': 'mean',    'color': 'scalar'},
        {'id': 'std',     'color': 'scalar'},
    ],
    params=[
        {'id': 'band',         'type': 'int',  'default': 1,    'min': 1, 'max': 20, 'label': 'Band'},
        {'id': 'ignore_zeros', 'type': 'bool', 'default': True,           'label': 'Ignore Zeros'},
    ]
)
class BandStatsNode(NodeProcessor):
    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        bands, count = _extract_bands(geo)
        if bands is None:
            geo2 = inputs.get('data')
            bands, count = _extract_bands(geo2)
            geo = geo2

        if bands is None:
            return {'geotiff': None, 'stats': None, 'min': None, 'max': None, 'mean': None, 'std': None}

        ignore_z   = bool(params.get('ignore_zeros', True))
        band_names = geo.get('band_names', [f'B{i+1}' for i in range(count)])

        all_stats = {}
        for i in range(count):
            b    = bands[i]
            mask = b != 0 if ignore_z else np.ones(b.shape, dtype=bool)
            vals = b[mask]
            if vals.size == 0:
                all_stats[band_names[i]] = {'min': 0, 'max': 0, 'mean': 0, 'std': 0, 'median': 0, 'count': 0}
            else:
                all_stats[band_names[i]] = {
                    'min':    float(np.min(vals)),
                    'max':    float(np.max(vals)),
                    'mean':   float(np.mean(vals)),
                    'std':    float(np.std(vals)),
                    'median': float(np.median(vals)),
                    'count':  int(vals.size),
                }

        sel      = min(int(params.get('band', 1)), count) - 1
        sel_name = band_names[sel]
        s        = all_stats[sel_name]

        return {
            'geotiff': geo,
            'stats':   all_stats,
            'min':     s['min'],
            'max':     s['max'],
            'mean':    s['mean'],
            'std':     s['std'],
        }
