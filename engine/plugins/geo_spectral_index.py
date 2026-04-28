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
    description="Compute NDVI, NDWI, NBR or EVI from a multispectral GeoTIFF.",
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[
        {'id': 'colormap', 'color': 'image',   'label': 'Colormap'},
        {'id': 'raw',      'color': 'geotiff', 'label': 'Raw (-1…1)'},
    ],
    params=[
        {'id': 'index',      'type': 'enum', 'options': ['NDVI', 'NDWI', 'NBR', 'EVI'], 'default': 'NDVI', 'label': 'Index'},
        {'id': 'nir_band',   'type': 'int',  'default': 4, 'min': 1, 'max': 20, 'label': 'NIR Band'},
        {'id': 'red_band',   'type': 'int',  'default': 3, 'min': 1, 'max': 20, 'label': 'Red Band'},
        {'id': 'green_band', 'type': 'int',  'default': 2, 'min': 1, 'max': 20, 'label': 'Green Band'},
        {'id': 'blue_band',  'type': 'int',  'default': 1, 'min': 1, 'max': 20, 'label': 'Blue Band'},
        {'id': 'swir_band',  'type': 'int',  'default': 5, 'min': 1, 'max': 20, 'label': 'SWIR Band'},
        {'id': 'colormap',   'type': 'enum', 'options': list(_CV2_COLORMAPS.keys()), 'default': 'viridis', 'label': 'Colormap'},
    ]
)
class SpectralIndexNode(NodeProcessor):
    def _band(self, bands, param_val, count):
        idx = max(0, min(int(param_val), count) - 1)
        return bands[idx].astype(np.float32)

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'colormap': None, 'raw': None}

        bands      = geo['bands']
        count      = geo['count']
        index_name = params.get('index', 'NDVI')
        eps        = 1e-10

        nir   = self._band(bands, params.get('nir_band',   4), count)
        red   = self._band(bands, params.get('red_band',   3), count)
        green = self._band(bands, params.get('green_band', 2), count)
        blue  = self._band(bands, params.get('blue_band',  1), count)
        swir  = self._band(bands, params.get('swir_band',  5), count)

        if index_name == 'NDVI':
            result = (nir - red) / (nir + red + eps)
        elif index_name == 'NDWI':
            result = (green - nir) / (green + nir + eps)
        elif index_name == 'NBR':
            result = (nir - swir) / (nir + swir + eps)
        elif index_name == 'EVI':
            result = 2.5 * (nir - red) / (nir + 6.0 * red - 7.5 * blue + 1.0 + eps)
        else:
            result = np.zeros_like(nir)

        result     = np.clip(result, -1.0, 1.0)
        normalized = ((result + 1.0) / 2.0 * 255.0).astype(np.uint8)
        cmap       = _CV2_COLORMAPS.get(params.get('colormap', 'viridis'), cv2.COLORMAP_VIRIDIS)
        colored    = cv2.applyColorMap(normalized, cmap)
        raw_geo    = {**geo, 'bands': result[np.newaxis], 'count': 1, 'band_names': [index_name]}

        return {'colormap': colored, 'raw': raw_geo}
