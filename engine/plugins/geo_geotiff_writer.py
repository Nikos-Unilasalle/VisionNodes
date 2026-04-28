from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import os

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


@vision_node(
    type_id='geo_geotiff_writer',
    label='GeoTIFF Writer',
    category='geo',
    icon='Save',
    description="Save a GeoTIFF stream to disk with geographic metadata (CRS, transform).",
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[],
    params=[
        {'id': 'save',        'type': 'trigger', 'default': 0,            'label': 'Save'},
        {'id': 'file_path',   'type': 'string',  'default': 'output.tif', 'label': 'File Path'},
        {'id': 'compression', 'type': 'enum',    'options': ['lzw', 'deflate', 'none'], 'default': 'lzw', 'label': 'Compression'},
    ]
)
class GeoTIFFWriterNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._prev_save = False

    def process(self, inputs, params):
        save        = bool(params.get('save', False))
        rising_edge = save and not self._prev_save
        self._prev_save = save
        if not rising_edge:
            return {}

        if not RASTERIO_AVAILABLE:
            send_notification('rasterio missing: pip install rasterio', level='error', notif_id='geo_writer')
            return {}

        geo = inputs.get('geotiff')
        if geo is None:
            send_notification('GeoTIFF Writer: no input data', level='error', notif_id='geo_writer')
            return {}

        path     = params.get('file_path', 'output.tif').strip() or 'output.tif'
        compress = params.get('compression', 'lzw')
        bands    = geo['bands']
        count, height, width = bands.shape

        profile = {
            'driver': 'GTiff',
            'dtype':  'float32',
            'width':  width,
            'height': height,
            'count':  count,
        }
        if geo.get('crs'):
            profile['crs'] = geo['crs']
        if geo.get('transform'):
            profile['transform'] = geo['transform']
        if compress != 'none':
            profile['compress'] = compress

        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with rasterio.open(path, 'w', **profile) as dst:
                dst.write(bands.astype(np.float32))
            send_notification(f'GeoTIFF saved: {os.path.basename(path)}', progress=1.0, notif_id='geo_writer')
        except Exception as e:
            send_notification(f'GeoTIFF write error: {e}', level='error', notif_id='geo_writer')

        return {}
