"""geo_dem_tri.py — Terrain Ruggedness Index (Riley et al. 1999).

TRI = sqrt( sum_8( (z_center - z_neighbor)^2 ) )
High values = rough terrain. Low values = flat.
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_tri'

_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'hot':     cv2.COLORMAP_HOT,
    'gray':    cv2.COLORMAP_BONE,
}


@vision_node(
    type_id='geo_dem_tri',
    label='DEM TRI',
    category='geography',
    icon='Triangle',
    description=(
        "Terrain Ruggedness Index (Riley et al. 1999): sqrt of the summed squared "
        "elevation differences between a cell and its 8 neighbours. "
        "High TRI = rugged; low TRI = flat. Useful for detecting disturbed terrain."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'DEM'}],
    outputs=[
        {'id': 'tri',      'color': 'geotiff', 'label': 'TRI'},
        {'id': 'colormap', 'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band',      'type': 'int',   'default': 1,    'min': 1, 'max': 32,       'label': 'DEM band'},
        {'id': 'clamp_max', 'type': 'float', 'default': 50.0, 'min': 1, 'max': 10000.0, 'label': 'Clamp max (display)'},
        {'id': 'colormap',  'type': 'enum',  'options': list(_CV2_COLORMAPS.keys()),
         'default': 0, 'label': 'Colormap'},
    ],
)
class DemTriNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'tri': None, 'colormap': None}

        bands    = geo['bands']
        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(f'DEM TRI: band {band_idx+1} out of range',
                              level='error', notif_id=_NOTIF)
            return {'tri': None, 'colormap': None}

        dem = bands[band_idx].copy().astype(np.float64)
        nodata = geo.get('nodata')
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        mean_v = float(np.nanmean(dem)) if np.any(np.isfinite(dem)) else 0.0
        dem    = np.where(np.isfinite(dem), dem, mean_v)

        # Stack 8 neighbours in one go
        pad = np.pad(dem, 1, mode='edge')
        nbrs = np.stack([
            pad[:-2, :-2], pad[:-2, 1:-1], pad[:-2, 2:],
            pad[1:-1, :-2],                pad[1:-1, 2:],
            pad[2:,  :-2], pad[2:,  1:-1], pad[2:,  2:],
        ], axis=-1)  # (H, W, 8)

        tri = np.sqrt(np.sum((dem[..., np.newaxis] - nbrs) ** 2, axis=-1)).astype(np.float32)

        tri_geo = {**geo, 'bands': tri[np.newaxis], 'count': 1,
                   'band_names': ['tri'], '_source': 'dem_tri', '_bands': ['tri']}

        clamp_max = float(params.get('clamp_max', 50.0))
        norm = np.clip(tri / clamp_max, 0.0, 1.0)
        img8 = (norm * 255).astype(np.uint8)

        cmap_val  = params.get('colormap', 0)
        cmap_keys = list(_CV2_COLORMAPS.keys())
        cmap_name = cmap_keys[cmap_val] if isinstance(cmap_val, int) and cmap_val < len(cmap_keys) else 'viridis'
        colored = cv2.applyColorMap(img8, _CV2_COLORMAPS.get(cmap_name, cv2.COLORMAP_VIRIDIS))

        h, w   = colored.shape[:2]
        sc     = min(1.0, 120 / h)
        thumb  = cv2.resize(colored, (max(1, int(w*sc)), max(1, int(h*sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        tb64   = base64.b64encode(buf).decode()

        return {'tri': tri_geo, 'colormap': colored, '_thumb': tb64}
