import os
import cv2
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_circle'


def _stretch(arr: np.ndarray) -> np.ndarray:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, (2, 98))
    if hi <= lo:
        return np.full(arr.shape, 128, dtype=np.uint8)
    return np.clip((arr - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)


@vision_node(
    type_id='geo_circle',
    label='Geo Circle',
    category='geography',
    icon='Circle',
    description=(
        "Draws circles at geographic coordinates (latitude, longitude) onto a GeoTIFF "
        "and its preview. Supports drawing single circles via parameters, or multiple "
        "circles from an input table (DataFrame)."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Base GeoTIFF'},
        {'id': 'table',   'color': 'data',    'label': 'DataFrame (Optional)', 'required': False},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Output GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Annotated Preview'},
    ],
    params=[
        {'id': 'latitude',     'type': 'float',  'default': 4.8,      'label': 'Latitude (Single)'},
        {'id': 'longitude',    'type': 'float',  'default': -53.0,    'label': 'Longitude (Single)'},
        {'id': 'radius',       'type': 'float',  'default': 500.0,    'label': 'Radius'},
        {'id': 'radius_unit',  'type': 'enum',   'options': ['meters', 'pixels'], 'default': 0, 'label': 'Radius Unit'},
        {'id': 'color',        'type': 'color',  'default': '#FF0000', 'label': 'Color'},
        {'id': 'thickness',    'type': 'int',    'default': 2, 'min': -1, 'max': 100, 'label': 'Thickness (-1 for fill)'},
        {'id': 'fill',         'type': 'bool',   'default': False,    'label': 'Fill Circle'},
        {'id': 'lat_col',      'type': 'string', 'default': 'latitude',  'label': 'Latitude column'},
        {'id': 'lon_col',      'type': 'string', 'default': 'longitude', 'label': 'Longitude column'},
        {'id': 'burn_mode',    'type': 'enum',   'options': ['new_band', 'first_band', 'all_bands'], 'default': 0,
         'label': 'Burn Mode (how to update raster bands)'},
    ],
    resizable=True, min_width=300, min_height=220
)
class GeoCircleNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        if not self.ensure_packages(['pandas', 'rasterio'], notif_id=_NOTIF):
            return {}
        import pandas as pd
        import rasterio.warp

        geo = inputs.get('geotiff')
        df  = inputs.get('table')

        if geo is None:
            return {'geotiff': None, 'preview': None}

        bands     = np.asarray(geo['bands'], dtype=np.float32)
        transform = geo.get('transform')
        crs       = geo.get('crs')

        if bands.size == 0 or transform is None:
            return {'geotiff': geo, 'preview': None}

        H, W = bands.shape[1], bands.shape[2] if bands.ndim == 3 else bands.shape

        # Resolve inverse transform for pixel mapping
        try:
            inv = ~transform
        except Exception:
            # Manual fallback inverse calculation
            a, b, c = transform.a, transform.b, transform.c
            d, e, f = transform.d, transform.e, transform.f
            det = a * e - b * d
            if abs(det) < 1e-15:
                send_notification('Geo Circle: degenerate transform', level='error', notif_id=_NOTIF)
                return {'geotiff': geo, 'preview': None}
            inv = type('MockInverse', (), {
                'a': e / det, 'b': -b / det, 'c': (b * f - e * c) / det,
                'd': -d / det, 'e': a / det, 'f': (d * c - a * f) / det
            })()

        # Parse radius unit & value
        radius = float(params.get('radius', 500.0))
        radius_unit = int(params.get('radius_unit', 0))

        # We need a reference latitude to compute meters-to-degrees mapping in case of WGS84
        ref_lat = float(params.get('latitude', 4.8))
        if df is not None:
            lat_col = str(params.get('lat_col', 'latitude')).strip()
            if lat_col in df.columns and len(df) > 0:
                ref_lat = float(df[lat_col].iloc[0])

        is_wgs84 = (crs is not None and '4326' in str(crs))
        if is_wgs84:
            lat_rad = np.radians(ref_lat)
            pixel_size_x = abs(transform.a) * 111320.0 * np.cos(lat_rad)
            pixel_size_y = abs(transform.e) * 110540.0
            pixel_size_m = (pixel_size_x + pixel_size_y) / 2.0
        else:
            pixel_size_m = abs(transform.a)

        if radius_unit == 0:  # meters
            r_px = int(round(radius / max(1e-6, pixel_size_m)))
        else:  # pixels
            r_px = int(round(radius))
        r_px = max(1, r_px)

        burn_mode = int(params.get('burn_mode', 0))
        fill_opt = bool(params.get('fill', False))
        thickness_val = -1 if fill_opt else int(params.get('thickness', 2))

        # Setup drawing layers
        if burn_mode == 0:  # new_band
            draw_layer = np.zeros((H, W), dtype=np.float32)
            out_bands = bands.copy()
        else:
            out_bands = bands.copy()

        # Parse hex color
        color_str = str(params.get('color', '#FF0000')).lstrip('#')
        if len(color_str) == 6:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
        else:
            r, g, b = 255, 0, 0
        bgr_color = (b, g, r)

        # Collect points
        points_to_draw = []
        if df is not None:
            lat_col = str(params.get('lat_col', 'latitude')).strip()
            lon_col = str(params.get('lon_col', 'longitude')).strip()
            if lat_col in df.columns and lon_col in df.columns:
                lats = df[lat_col].values
                lons = df[lon_col].values
                for pt_lat, pt_lon in zip(lats, lons):
                    points_to_draw.append((float(pt_lat), float(pt_lon)))
            else:
                send_notification(f"Geo Circle: columns '{lat_col}'/'{lon_col}' not found. Using param single coordinate.", level='warn', notif_id=_NOTIF)
                points_to_draw.append((float(params.get('latitude', 4.8)), float(params.get('longitude', -53.0))))
        else:
            points_to_draw.append((float(params.get('latitude', 4.8)), float(params.get('longitude', -53.0))))

        # Resolve preview rendering
        preview_in = inputs.get('preview')
        if preview_in is not None:
            preview = preview_in.copy()
        elif geo.get('preview') is not None:
            preview = geo['preview'].copy()
        else:
            if bands.ndim == 3 and bands.shape[0] >= 3:
                r8 = _stretch(bands[0])
                g8 = _stretch(bands[1])
                b8 = _stretch(bands[2])
                preview = np.stack([b8, g8, r8], axis=-1)
            elif bands.ndim == 3:
                b0_norm = _stretch(bands[0])
                preview = cv2.cvtColor(b0_norm, cv2.COLOR_GRAY2BGR)
            else:
                b0_norm = _stretch(bands)
                preview = cv2.cvtColor(b0_norm, cv2.COLOR_GRAY2BGR)

        ph, pw = preview.shape[:2]
        scale_x = pw / W
        scale_y = ph / H

        # Batch project WGS84 (lon, lat) to local CRS coordinates
        longitudes_to_proj = [pt[1] for pt in points_to_draw]
        latitudes_to_proj = [pt[0] for pt in points_to_draw]

        if crs is not None and str(crs).upper() != 'EPSG:4326':
            try:
                xs, ys = rasterio.warp.transform('EPSG:4326', crs, longitudes_to_proj, latitudes_to_proj)
            except Exception as e:
                send_notification(f"Geo Circle: batch projection error: {e}", level='error', notif_id=_NOTIF)
                xs, ys = longitudes_to_proj, latitudes_to_proj
        else:
            xs, ys = longitudes_to_proj, latitudes_to_proj

        # Draw each circle
        for k, (x_p, y_p) in enumerate(zip(xs, ys)):
            col_f = inv.a * x_p + inv.b * y_p + inv.c
            row_f = inv.d * x_p + inv.e * y_p + inv.f
            col, row = int(round(col_f)), int(round(row_f))

            # Burn on raster bands
            if burn_mode == 0:  # new_band
                cv2.circle(draw_layer, (col, row), r_px, 255.0, thickness_val)
            elif burn_mode == 1:  # first_band
                if out_bands.ndim == 3:
                    cv2.circle(out_bands[0], (col, row), r_px, 255.0, thickness_val)
                else:
                    cv2.circle(out_bands, (col, row), r_px, 255.0, thickness_val)
            else:  # all_bands
                if out_bands.ndim == 3:
                    for b_idx in range(out_bands.shape[0]):
                        cv2.circle(out_bands[b_idx], (col, row), r_px, 255.0, thickness_val)
                else:
                    cv2.circle(out_bands, (col, row), r_px, 255.0, thickness_val)

            # Draw on BGR preview
            col_pv = int(round(col * scale_x))
            row_pv = int(round(row * scale_y))
            r_pv = int(round(r_px * (scale_x + scale_y) / 2.0))
            r_pv = max(1, r_pv)
            cv2.circle(preview, (col_pv, row_pv), r_pv, bgr_color, thickness_val)

        # Re-pack outputs
        if burn_mode == 0:  # new_band
            if bands.ndim == 3:
                out_bands = np.concatenate([bands, draw_layer[np.newaxis]], axis=0)
            else:
                out_bands = np.stack([bands, draw_layer], axis=0)
            orig_names = list(geo.get('band_names', [f'b{i+1}' for i in range(bands.shape[0] if bands.ndim == 3 else 1)]))
            out_names = orig_names + ['geo_circle']
        else:
            out_names = geo.get('band_names')

        out_geo = {
            **geo,
            'bands': out_bands,
            'count': out_bands.shape[0] if out_bands.ndim == 3 else 1,
            'band_names': out_names
        }

        send_notification(f"Geo Circle: Plotted {len(points_to_draw)} circles.", progress=1.0, notif_id=_NOTIF)

        return {
            'geotiff': out_geo,
            'preview': preview
        }
