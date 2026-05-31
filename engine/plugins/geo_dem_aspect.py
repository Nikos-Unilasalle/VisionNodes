"""
geo_dem_aspect.py — Aspect (exposition) derivation from a DEM GeoTIFF.

Uses Horn (1981) 3×3 weighted gradient — same algorithm as GDAL/ArcGIS.
Output: azimuth 0–360° clockwise from North (flat areas → -1 or NaN).
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_aspect'

_UNITS = ['degrees_north', 'radians']


def _pixel_size_meters(transform, crs_str: str, height: int) -> tuple[float, float]:
    px = abs(float(transform.a))
    py = abs(float(transform.e))
    crs_lower = str(crs_str).lower()
    is_geographic = (
        'epsg:4326' in crs_lower
        or 'wgs 84' in crs_lower
        or 'wgs84' in crs_lower
    )
    if is_geographic:
        lat_origin = float(transform.f)
        lat_centre = lat_origin - py * (height / 2.0)
        cell_y_m   = py * 111320.0
        cell_x_m   = px * 111320.0 * abs(np.cos(np.radians(lat_centre)))
    else:
        cell_x_m = px
        cell_y_m = py
    return cell_x_m, cell_y_m


def _aspect_horn(dem: np.ndarray, cell_x: float, cell_y: float,
                 unit: str, flat_value: float = -1.0) -> np.ndarray:
    """Horn (1981) aspect on a 2-D float32 DEM.

    Returns azimuth clockwise from North (0–360°) or 0–2π radians.
    Flat areas (zero gradient) get `flat_value`.
    """
    z = dem.astype(np.float64)
    z = np.pad(z, 1, mode='edge')

    dzdx = (
        (z[:-2, 2:] + 2 * z[1:-1, 2:] + z[2:, 2:]) -
        (z[:-2, :-2] + 2 * z[1:-1, :-2] + z[2:, :-2])
    ) / (8.0 * cell_x)

    dzdy = (
        (z[2:, :-2] + 2 * z[2:, 1:-1] + z[2:, 2:]) -
        (z[:-2, :-2] + 2 * z[:-2, 1:-1] + z[:-2, 2:])
    ) / (8.0 * cell_y)

    # Downslope bearing in compass (0=N, 90=E, 180=S, 270=W), clockwise.
    # atan2(East_down, North_down) = atan2(-dzdx, dzdy) because:
    #   dzdx > 0 → upslope east → downslope west → E_down = -dzdx
    #   dzdy > 0 → south-row higher → downslope north → N_down = dzdy
    aspect_rad = np.arctan2(-dzdx, dzdy)
    aspect_360 = np.degrees(aspect_rad) % 360.0

    # Flat areas: gradient magnitude ≈ 0
    flat_mask = (np.abs(dzdx) < 1e-10) & (np.abs(dzdy) < 1e-10)
    aspect_360 = np.where(flat_mask, flat_value, aspect_360)

    if unit == 'radians':
        result = np.where(flat_mask, flat_value, np.radians(aspect_360))
    else:
        result = aspect_360

    return result.astype(np.float32)


def _aspect_to_hsv_image(aspect: np.ndarray) -> np.ndarray:
    """Encode aspect as HSV color wheel (hue = direction, value = 1 for valid, 0 for flat)."""
    flat_mask = aspect < 0
    hue = np.where(flat_mask, 0.0, aspect / 360.0 * 179.0).astype(np.uint8)
    sat = np.where(flat_mask, 0,   200).astype(np.uint8)
    val = np.where(flat_mask, 40,  255).astype(np.uint8)
    hsv = cv2.merge([hue, sat, val])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


@vision_node(
    type_id='geo_dem_aspect',
    label='DEM Aspect',
    category='geography',
    icon='Compass',
    description=(
        "Compute aspect (exposition) from a DEM using the Horn (1981) 3×3 weighted gradient. "
        "Output: azimuth 0–360° clockwise from North (flat areas = -1). "
        "Preview uses a color wheel: N=red, E=cyan, S=teal, W=yellow."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'DEM'},
    ],
    outputs=[
        {'id': 'aspect',   'color': 'geotiff', 'label': 'Aspect'},
        {'id': 'colormap', 'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band',       'type': 'int',  'default': 1, 'min': 1, 'max': 32,
         'label': 'DEM band index'},
        {'id': 'unit',       'type': 'enum', 'options': _UNITS, 'default': 0,
         'label': 'Unit'},
        {'id': 'flat_value', 'type': 'float', 'default': -1.0, 'min': -1.0, 'max': 0.0,
         'label': 'Flat area value'},
    ],
)
class DemAspectNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'aspect': None, 'colormap': None}

        bands     = geo['bands']
        transform = geo.get('transform')
        crs       = geo.get('crs', '')

        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(
                f'DEM Aspect: band {band_idx + 1} out of range ({bands.shape[0]} band(s))',
                level='error', notif_id=_NOTIF,
            )
            return {'aspect': None, 'colormap': None}

        dem = bands[band_idx].copy()

        nodata = geo.get('nodata')
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        valid_mean = float(np.nanmean(dem)) if np.any(np.isfinite(dem)) else 0.0
        dem = np.where(np.isfinite(dem), dem, valid_mean)

        if transform is None:
            send_notification('DEM Aspect: no geotransform — assuming 30 m pixels',
                              level='warning', notif_id=_NOTIF)
            cell_x, cell_y = 30.0, 30.0
        else:
            cell_x, cell_y = _pixel_size_meters(transform, crs, dem.shape[0])

        unit_opts = _UNITS
        unit_val  = params.get('unit', 0)
        unit = unit_opts[unit_val] if isinstance(unit_val, int) and unit_val < len(unit_opts) else str(unit_val)

        flat_value = float(params.get('flat_value', -1.0))

        aspect = _aspect_horn(dem, cell_x, cell_y, unit, flat_value)

        aspect_geo = {
            **geo,
            'bands':      aspect[np.newaxis],
            'count':      1,
            'band_names': [f'aspect_{unit}'],
            '_source':    'dem_aspect',
            '_bands':     [f'aspect_{unit}'],
        }

        colored = _aspect_to_hsv_image(aspect)

        h, w = colored.shape[:2]
        sc   = min(1.0, 120 / h)
        thumb = cv2.resize(colored, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        return {'aspect': aspect_geo, 'colormap': colored, '_thumb': thumb_b64}
