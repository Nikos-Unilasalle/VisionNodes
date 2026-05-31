"""
geo_dem_slope.py — Slope (pente) derivation from a DEM GeoTIFF.

Uses Horn (1981) 3×3 weighted gradient — same algorithm as GDAL/ArcGIS.
Handles both geographic (EPSG:4326, degrees) and projected (UTM, meters) CRS.
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_slope'

_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'hot':     cv2.COLORMAP_HOT,
    'gray':    cv2.COLORMAP_BONE,
}

_UNITS = ['degrees', 'percent', 'radians']


def _pixel_size_meters(transform, crs_str: str, height: int) -> tuple[float, float]:
    """Return (cell_x_m, cell_y_m) pixel size in metres."""
    px = abs(float(transform.a))
    py = abs(float(transform.e))

    crs_lower = str(crs_str).lower()
    is_geographic = (
        'epsg:4326' in crs_lower
        or 'wgs 84' in crs_lower
        or 'wgs84' in crs_lower
        or ('geographiccrs' in crs_lower)
    )

    if is_geographic:
        # Degrees → metres using centre-of-raster latitude
        lat_origin = float(transform.f)
        lat_centre = lat_origin - py * (height / 2.0)
        cell_y_m   = py * 111320.0
        cell_x_m   = px * 111320.0 * abs(np.cos(np.radians(lat_centre)))
    else:
        cell_x_m = px
        cell_y_m = py

    return cell_x_m, cell_y_m


def _slope_horn(dem: np.ndarray, cell_x: float, cell_y: float,
                unit: str) -> np.ndarray:
    """Horn (1981) slope on a 2-D float32 DEM."""
    z = dem.astype(np.float64)

    # Pad with edge-replicate so borders are computed correctly
    z = np.pad(z, 1, mode='edge')

    # Horn weighted finite differences
    dzdx = (
        (z[:-2, 2:] + 2 * z[1:-1, 2:] + z[2:, 2:]) -
        (z[:-2, :-2] + 2 * z[1:-1, :-2] + z[2:, :-2])
    ) / (8.0 * cell_x)

    dzdy = (
        (z[2:, :-2] + 2 * z[2:, 1:-1] + z[2:, 2:]) -
        (z[:-2, :-2] + 2 * z[:-2, 1:-1] + z[:-2, 2:])
    ) / (8.0 * cell_y)

    rise = np.sqrt(dzdx ** 2 + dzdy ** 2)

    if unit == 'radians':
        return np.arctan(rise).astype(np.float32)
    if unit == 'percent':
        return (rise * 100.0).astype(np.float32)
    # degrees (default)
    return np.degrees(np.arctan(rise)).astype(np.float32)


@vision_node(
    type_id='geo_dem_slope',
    label='DEM Slope',
    category='geography',
    icon='TrendingUp',
    description=(
        "Compute slope (pente) from a DEM using the Horn (1981) 3×3 weighted gradient. "
        "Works with both geographic (EPSG:4326) and projected (UTM) DEMs. "
        "Output unit: degrees, percent rise, or radians."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'DEM'},
    ],
    outputs=[
        {'id': 'slope',    'color': 'geotiff', 'label': 'Slope'},
        {'id': 'colormap', 'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band',     'type': 'int',  'default': 1, 'min': 1, 'max': 32,
         'label': 'DEM band index'},
        {'id': 'unit',     'type': 'enum', 'options': _UNITS, 'default': 0,
         'label': 'Unit'},
        {'id': 'clamp_max', 'type': 'float', 'default': 90.0, 'min': 1.0, 'max': 10000.0,
         'label': 'Clamp max (for display)'},
        {'id': 'colormap', 'type': 'enum', 'options': list(_CV2_COLORMAPS.keys()),
         'default': 0, 'label': 'Colormap'},
    ],
)
class DemSlopeNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'slope': None, 'colormap': None}

        bands     = geo['bands']       # (N, H, W) float32
        transform = geo.get('transform')
        crs       = geo.get('crs', '')

        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(
                f'DEM Slope: band {band_idx + 1} out of range ({bands.shape[0]} band(s))',
                level='error', notif_id=_NOTIF,
            )
            return {'slope': None, 'colormap': None}

        dem = bands[band_idx]

        # Replace nodata / NaN with local mean before gradient so borders don't blow up
        nodata = geo.get('nodata')
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        valid_mean = float(np.nanmean(dem)) if np.any(np.isfinite(dem)) else 0.0
        dem = np.where(np.isfinite(dem), dem, valid_mean)

        if transform is None:
            send_notification('DEM Slope: no geotransform — pixel size unknown, assuming 30 m',
                              level='warning', notif_id=_NOTIF)
            cell_x, cell_y = 30.0, 30.0
        else:
            cell_x, cell_y = _pixel_size_meters(transform, crs, dem.shape[0])
            if cell_x < 1e-6 or cell_y < 1e-6:
                send_notification(f'DEM Slope: suspicious pixel size ({cell_x:.2f} m) — check CRS',
                                  level='warning', notif_id=_NOTIF)

        unit_opts = _UNITS
        unit_val  = params.get('unit', 0)
        if isinstance(unit_val, int):
            unit = unit_opts[unit_val] if unit_val < len(unit_opts) else 'degrees'
        else:
            unit = str(unit_val)

        slope = _slope_horn(dem, cell_x, cell_y, unit)

        slope_geo = {
            **geo,
            'bands':      slope[np.newaxis],
            'count':      1,
            'band_names': [f'slope_{unit}'],
            '_source':    'dem_slope',
            '_bands':     [f'slope_{unit}'],
        }

        clamp_max = float(params.get('clamp_max', 90.0))
        normalized = np.clip(slope / clamp_max, 0.0, 1.0)
        normalized = (normalized * 255).astype(np.uint8)

        cmap_val  = params.get('colormap', 0)
        cmap_keys = list(_CV2_COLORMAPS.keys())
        if isinstance(cmap_val, int):
            cmap_name = cmap_keys[cmap_val] if cmap_val < len(cmap_keys) else 'viridis'
        else:
            cmap_name = str(cmap_val)
        cmap = _CV2_COLORMAPS.get(cmap_name, cv2.COLORMAP_VIRIDIS)

        colored = cv2.applyColorMap(normalized, cmap)

        h, w = colored.shape[:2]
        sc   = min(1.0, 120 / h)
        thumb = cv2.resize(colored, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        return {'slope': slope_geo, 'colormap': colored, '_thumb': thumb_b64}
