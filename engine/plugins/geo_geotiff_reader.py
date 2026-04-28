from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import os
import base64

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


@vision_node(
    type_id='geo_geotiff_reader',
    label='GeoTIFF Reader',
    category='src',
    icon='Globe',
    description="Read a local GeoTIFF file. Supports multispectral imagery (Sentinel-2, Landsat, etc.)",
    inputs=[],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview'},
        {'id': 'meta',    'color': 'dict',     'label': 'Meta'},
    ],
    params=[
        {'id': 'file_path', 'type': 'string', 'default': '',  'label': 'File Path'},
        {'id': 'r_band',    'type': 'int',    'default': 1,   'min': 1, 'max': 20, 'label': 'Preview R'},
        {'id': 'g_band',    'type': 'int',    'default': 2,   'min': 1, 'max': 20, 'label': 'Preview G'},
        {'id': 'b_band',    'type': 'int',    'default': 3,   'min': 1, 'max': 20, 'label': 'Preview B'},
    ]
)
class GeoTIFFReaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_path  = None
        self._cache_data  = None
        self._pending_thumb = None

    def _stretch_band(self, band):
        valid = band[band != 0]
        if valid.size == 0:
            return np.zeros_like(band, dtype=np.uint8)
        p2, p98 = np.percentile(valid, (2, 98))
        if p98 == p2:
            return np.full_like(band, 128, dtype=np.uint8)
        return np.clip((band - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)

    def process(self, inputs, params):
        if not RASTERIO_AVAILABLE:
            send_notification('rasterio missing: pip install rasterio', level='error', notif_id='geo_reader')
            return {'geotiff': None, 'preview': None, 'meta': None}

        path = params.get('file_path', '').strip()
        if not path or not os.path.exists(path):
            return {'geotiff': None, 'preview': None, 'meta': None}

        if path != self._cache_path:
            try:
                send_notification(f'GeoTIFF: loading {os.path.basename(path)}…', progress=0.1, notif_id='geo_reader')
                with rasterio.open(path) as src:
                    bands = src.read().astype(np.float32)
                    if src.nodata is not None:
                        bands[bands == src.nodata] = 0
                    self._cache_data = {
                        'bands':      bands,
                        'band_names': [f'B{i + 1}' for i in range(src.count)],
                        'crs':        str(src.crs) if src.crs else None,
                        'transform':  src.transform,
                        'nodata':     src.nodata,
                        'count':      src.count,
                        'width':      src.width,
                        'height':     src.height,
                        'dtype':      str(src.dtypes[0]),
                        'bounds': {
                            'west':  src.bounds.left,
                            'south': src.bounds.bottom,
                            'east':  src.bounds.right,
                            'north': src.bounds.top,
                        },
                    }
                self._cache_path    = path
                self._pending_thumb = True
                send_notification(
                    f'GeoTIFF: {self._cache_data["count"]} bands, '
                    f'{self._cache_data["width"]}×{self._cache_data["height"]}',
                    progress=1.0, notif_id='geo_reader'
                )
            except Exception as e:
                send_notification(f'GeoTIFF read error: {e}', level='error', notif_id='geo_reader')
                return {'geotiff': None, 'preview': None, 'meta': None}

        geo   = self._cache_data
        bands = geo['bands']
        count = geo['count']

        r_idx = min(int(params.get('r_band', 1)), count) - 1
        g_idx = min(int(params.get('g_band', min(2, count))), count) - 1
        b_idx = min(int(params.get('b_band', min(3, count))), count) - 1

        r = self._stretch_band(bands[r_idx])
        g = self._stretch_band(bands[g_idx])
        b = self._stretch_band(bands[b_idx])
        preview = cv2.merge([b, g, r])

        out_thumb = None
        if self._pending_thumb:
            h, w = preview.shape[:2]
            sc   = 120 / h
            thumb_img = cv2.resize(preview, (max(1, int(w * sc)), 120))
            _, buf    = cv2.imencode('.jpg', thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
            out_thumb = base64.b64encode(buf).decode('utf-8')
            self._pending_thumb = None

        meta = {
            'crs':        geo['crs'],
            'band_count': count,
            'width':      geo['width'],
            'height':     geo['height'],
            'dtype':      geo['dtype'],
            'bounds':     geo['bounds'],
            'band_names': geo['band_names'],
        }

        return {'geotiff': geo, 'preview': preview, 'meta': meta, '_thumb': out_thumb}
