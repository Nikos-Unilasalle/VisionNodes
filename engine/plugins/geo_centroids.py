import os
import cv2
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_centroids'


@vision_node(
    type_id='geo_centroids',
    label='Geo Centroids',
    category='geography',
    icon='MapPin',
    description=(
        "Extracts geographic centroids of connected components in a binary mask, "
        "reprojecting coordinates to WGS84 (longitude, latitude)."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Binary Mask Raster'},
    ],
    outputs=[
        {'id': 'table',    'color': 'data', 'label': 'Centroids DataFrame'},
        {'id': 'out_list', 'color': 'list', 'label': 'Centroids List'},
        {'id': 'preview',  'color': 'image', 'label': 'Centroids Preview'},
    ],
    params=[
        {'id': 'min_area', 'type': 'int', 'default': 2, 'min': 1, 'max': 10000,
         'label': 'Min Area (pixels)'},
        {'id': 'max_area', 'type': 'int', 'default': 5000, 'min': 1, 'max': 1000000,
         'label': 'Max Area (pixels)'},
    ],
    resizable=True, min_width=300, min_height=200
)
class GeoCentroidsNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        if not self.ensure_packages(['pandas', 'rasterio'], notif_id=_NOTIF):
            return {}
        import pandas as pd
        import rasterio.warp

        geo = inputs.get('geotiff')
        if geo is None:
            return {'table': None, 'out_list': None, 'preview': None}

        bands     = np.asarray(geo['bands'], dtype=np.float32)
        transform = geo.get('transform')
        crs       = geo.get('crs')

        if bands.size == 0 or transform is None:
            return {'table': None, 'out_list': None, 'preview': None}

        # Use first band as binary mask
        mask = bands[0] if bands.ndim == 3 else bands
        H, W = mask.shape

        min_area = int(params.get('min_area', 2))
        max_area = int(params.get('max_area', 5000))

        # Convert to binary uint8 (0 or 255)
        # Handle possible NaNs or non-standard values by clamping to 0-255
        mask_clean = np.nan_to_num(mask, nan=0.0)
        _, binary = cv2.threshold(mask_clean.astype(np.uint8), 127, 255, cv2.THRESH_BINARY)

        # Label connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary)

        results = []
        x_proj_list = []
        y_proj_list = []

        idx_counter = 1
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if min_area <= area <= max_area:
                cx_px, cy_px = centroids[i]
                
                # Transform pixel coordinate (col, row) to projected local coordinate (x, y)
                # Affine transform formula:
                # x = a * col + b * row + c
                # y = d * col + e * row + f
                x_proj = transform.a * cx_px + transform.b * cy_px + transform.c
                y_proj = transform.d * cx_px + transform.e * cy_px + transform.f

                results.append({
                    'id': idx_counter,
                    'area_px': float(area),
                    'x_proj': x_proj,
                    'y_proj': y_proj,
                    'cx_px': cx_px,
                    'cy_px': cy_px
                })
                x_proj_list.append(x_proj)
                y_proj_list.append(y_proj)
                idx_counter += 1

        # Reproject projected local coordinates to WGS84 (EPSG:4326)
        longitudes = []
        latitudes = []
        if len(x_proj_list) > 0:
            if crs is not None and str(crs).upper() != 'EPSG:4326':
                try:
                    longitudes, latitudes = rasterio.warp.transform(
                        src_crs=crs,
                        dst_crs='EPSG:4326',
                        xs=x_proj_list,
                        ys=y_proj_list
                    )
                except Exception as e:
                    send_notification(f"Geo Centroids: projection error: {e}", level='warn', notif_id=_NOTIF)
                    longitudes = x_proj_list
                    latitudes = y_proj_list
            else:
                longitudes = x_proj_list
                latitudes = y_proj_list

        # Add coordinates to the dictionary list
        out_list = []
        for j, res in enumerate(results):
            res['longitude'] = longitudes[j]
            res['latitude'] = latitudes[j]
            out_list.append({
                'id': res['id'],
                'area_px': res['area_px'],
                'x_proj': res['x_proj'],
                'y_proj': res['y_proj'],
                'longitude': res['longitude'],
                'latitude': res['latitude']
            })

        df = pd.DataFrame(out_list)

        # ── Preview Visualisation ──────────────────────────────────────────────
        # Create a BGR image to draw annotations on
        preview = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        # Draw red circle and text label on each centroid
        for res in results:
            cx, cy = int(round(res['cx_px'])), int(round(res['cy_px']))
            cv2.circle(preview, (cx, cy), 4, (0, 0, 255), -1)
            cv2.circle(preview, (cx, cy), 8, (0, 255, 255), 1)
            cv2.putText(preview, f"#{res['id']}", (cx + 8, cy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)

        # Resize to standard size for frontend preview without losing clarity
        max_dim = 720
        ph, pw = preview.shape[:2]
        if max(ph, pw) > max_dim:
            sc = max_dim / max(ph, pw)
            preview = cv2.resize(preview, (int(pw * sc), int(ph * sc)),
                                 interpolation=cv2.INTER_AREA)

        msg = f"Detected {len(out_list)} centroid clusters."
        send_notification(f"Geo Centroids: {msg}", progress=1.0, notif_id=_NOTIF)

        return {
            'table': df,
            'out_list': out_list,
            'preview': preview
        }
