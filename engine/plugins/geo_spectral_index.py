from registry import vision_node, NodeProcessor
import numpy as np
import cv2


_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'jet':     cv2.COLORMAP_JET,
    'hot':     cv2.COLORMAP_HOT,
}


@vision_node(
    type_id='geo_spectral_index',
    label='Spectral Index',
    category='geo',
    icon='BarChart2',
    description=(
        "Indices: \n"
        "• NDVI (Veg): (NIR−Red)/(NIR+Red)\n"
        "• NDWI (Water): (Green−NIR)/(Green+NIR)\n"
        "• NBR (Burn): (NIR−SWIR)/(NIR+SWIR)\n"
        "• EVI (Enh. Veg): 2.5*(NIR−Red)/(NIR+6*Red−7.5*Blue+1)"
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[
        {'id': 'colormap', 'color': 'image',   'label': 'Colormap'},
        {'id': 'raw',      'color': 'geotiff', 'label': 'Raw (-1…1)'},
    ],
    params=[
        {'id': 'sensor',     'type': 'enum', 'options': ['Manual', 'S2/L8 (RGB+NIR)', 'S2 (All Bands)', 'L8 (All Bands)'], 'default': 'Manual', 'label': 'Sensor'},
        {'id': 'index',      'type': 'enum', 'options': ['NDVI (Vegetation)', 'NDWI (Water)', 'NBR (Burn)', 'EVI (Enhanced Vegetation)', 'Manual (Custom)'], 'default': 'NDVI (Vegetation)', 'label': 'Preset'},
        {'id': 'nir_band',   'type': 'int',  'default': 4, 'min': 1, 'max': 20, 'label': 'NIR Band'},
        {'id': 'red_band',   'type': 'int',  'default': 1, 'min': 1, 'max': 20, 'label': 'Red Band'},
        {'id': 'green_band', 'type': 'int',  'default': 2, 'min': 1, 'max': 20, 'label': 'Green Band'},
        {'id': 'blue_band',  'type': 'int',  'default': 3, 'min': 1, 'max': 20, 'label': 'Blue Band'},
        {'id': 'swir_band',  'type': 'int',  'default': 5, 'min': 1, 'max': 20, 'label': 'SWIR Band'},
        {'id': 'colormap',   'type': 'enum', 'options': list(_CV2_COLORMAPS.keys()), 'default': 'viridis', 'label': 'Colormap'},
    ]
)
class SpectralIndexNode(NodeProcessor):
    _PRESETS = {
        'S2/L8 (RGB+NIR)': {'nir': 4, 'red': 1, 'green': 2, 'blue': 3, 'swir': 5},
        'S2 (All Bands)':  {'nir': 4, 'red': 3, 'green': 2, 'blue': 1, 'swir': 5},
        'L8 (All Bands)':  {'nir': 4, 'red': 3, 'green': 2, 'blue': 1, 'swir': 5},
    }

    def _band(self, bands, param_val, count):
        idx = max(0, min(int(param_val), count) - 1)
        return bands[idx].astype(np.float32)

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'colormap': None, 'raw': None}

        bands       = geo['bands']
        count       = geo['count']
        index_name  = params.get('index',  'NDVI')
        eps         = 1e-10

        # Always use slider values - The UI handles presets by updating these sliders
        nir_idx   = params.get('nir_band',   4)
        red_idx   = params.get('red_band',   1)
        green_idx = params.get('green_band', 2)
        blue_idx  = params.get('blue_band',  3)
        swir_idx  = params.get('swir_band',  5)

        nir   = self._band(bands, nir_idx,   count)
        red   = self._band(bands, red_idx,   count)
        green = self._band(bands, green_idx, count)
        blue  = self._band(bands, blue_idx,  count)
        swir  = self._band(bands, swir_idx,  count)

        # Handle index selection (by name or index)
        def is_idx(val, target, idx):
            if isinstance(val, int): return val == idx
            return str(val).startswith(target)

        if is_idx(index_name, 'NDVI', 0) or is_idx(index_name, 'Manual', 4):
            result = (nir - red) / (nir + red + eps)
        elif is_idx(index_name, 'NDWI', 1):
            result = (green - nir) / (green + nir + eps)
        elif is_idx(index_name, 'NBR', 2):
            result = (nir - swir) / (nir + swir + eps)
        elif is_idx(index_name, 'EVI', 3):
            result = 2.5 * (nir - red) / (nir + 6.0 * red - 7.5 * blue + 1.0 + eps)
        else:
            result = np.zeros_like(nir)

        result     = np.clip(result, -1.0, 1.0)
        normalized = ((result + 1.0) / 2.0 * 255.0).astype(np.uint8)
        cmap_val = params.get('colormap', 'viridis')
        if isinstance(cmap_val, int):
            cmap_keys = list(_CV2_COLORMAPS.keys())
            cmap_name = cmap_keys[cmap_val] if cmap_val < len(cmap_keys) else 'viridis'
        else:
            cmap_name = cmap_val

        cmap = _CV2_COLORMAPS.get(cmap_name, cv2.COLORMAP_VIRIDIS)
        colored    = cv2.applyColorMap(normalized, cmap)
        raw_geo    = {**geo, 'bands': result[np.newaxis], 'count': 1, 'band_names': [index_name]}

        return {'colormap': colored, 'raw': raw_geo}
