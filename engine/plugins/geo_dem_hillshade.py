"""geo_dem_hillshade.py — Hillshade (ombrage) from DEM via Horn (1981) slope+aspect."""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_hillshade'


def _pixel_size_m(transform, crs_str: str, height: int) -> tuple[float, float]:
    px, py = abs(float(transform.a)), abs(float(transform.e))
    if any(k in str(crs_str).lower() for k in ('epsg:4326', 'wgs 84', 'wgs84')):
        lat_c  = float(transform.f) - py * (height / 2.0)
        return px * 111320.0 * abs(np.cos(np.radians(lat_c))), py * 111320.0
    return px, py


@vision_node(
    type_id='geo_dem_hillshade',
    label='DEM Hillshade',
    category='geography',
    icon='Sun',
    description=(
        "Shaded relief (ombrage) from a DEM via Lambertian reflectance. "
        "Combines Horn slope and aspect with a configurable sun position."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'DEM'}],
    outputs=[
        {'id': 'hillshade', 'color': 'geotiff', 'label': 'Hillshade'},
        {'id': 'preview',   'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band',     'type': 'int',   'default': 1,     'min': 1,   'max': 32,  'label': 'DEM band'},
        {'id': 'azimuth',  'type': 'float', 'default': 315.0, 'min': 0,   'max': 360, 'label': 'Sun azimuth (°, N=0)'},
        {'id': 'altitude', 'type': 'float', 'default': 45.0,  'min': 0,   'max': 90,  'label': 'Sun altitude (°)'},
        {'id': 'z_factor', 'type': 'float', 'default': 1.0,   'min': 0.1, 'max': 100, 'label': 'Z factor'},
    ],
)
class DemHillshadeNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'hillshade': None, 'preview': None}

        bands    = geo['bands']
        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(f'DEM Hillshade: band {band_idx+1} out of range',
                              level='error', notif_id=_NOTIF)
            return {'hillshade': None, 'preview': None}

        dem = bands[band_idx].copy().astype(np.float64)
        nodata = geo.get('nodata')
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        mean_v = float(np.nanmean(dem)) if np.any(np.isfinite(dem)) else 0.0
        dem    = np.where(np.isfinite(dem), dem, mean_v)

        transform = geo.get('transform')
        if transform is None:
            cx, cy = 30.0, 30.0
        else:
            cx, cy = _pixel_size_m(transform, geo.get('crs', ''), dem.shape[0])

        z   = float(params.get('z_factor', 1.0))
        dem = dem * z

        # Horn (1981) gradients
        pad  = np.pad(dem, 1, mode='edge')
        dzdx = ((pad[:-2,2:] + 2*pad[1:-1,2:] + pad[2:,2:]) -
                (pad[:-2,:-2] + 2*pad[1:-1,:-2] + pad[2:,:-2])) / (8.0 * cx)
        dzdy = ((pad[2:,:-2] + 2*pad[2:,1:-1] + pad[2:,2:]) -
                (pad[:-2,:-2] + 2*pad[:-2,1:-1] + pad[:-2,2:])) / (8.0 * cy)

        slope  = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        aspect = np.arctan2(-dzdx, dzdy) % (2 * np.pi)

        az     = np.radians(float(params.get('azimuth',  315.0)))
        alt    = np.radians(float(params.get('altitude',  45.0)))
        zenith = np.pi / 2.0 - alt

        hs = (np.cos(zenith) * np.cos(slope) +
              np.sin(zenith) * np.sin(slope) * np.cos(az - aspect))
        hs = np.clip(hs, 0.0, 1.0).astype(np.float32)

        hs_geo = {**geo, 'bands': hs[np.newaxis], 'count': 1,
                  'band_names': ['hillshade'], '_source': 'dem_hillshade',
                  '_bands': ['hillshade']}

        img8   = (hs * 255.0).astype(np.uint8)
        colored = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
        h, w   = colored.shape[:2]
        sc     = min(1.0, 120 / h)
        thumb  = cv2.resize(colored, (max(1, int(w*sc)), max(1, int(h*sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        tb64   = base64.b64encode(buf).decode()

        return {'hillshade': hs_geo, 'preview': colored, '_thumb': tb64}
