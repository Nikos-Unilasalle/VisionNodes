"""
geo_distance_to_class.py — Calculates the Euclidean distance in meters to a target classification class.
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='geo_distance_to_class',
    label='Distance to Class',
    category='geography',
    icon='Maximize',
    description=(
        "Calculates the Euclidean distance in meters from each pixel to the nearest "
        "pixel of a target classification class (e.g., LULC water or forest)."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Classification Raster'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Distance Raster (m)'},
        {'id': 'preview', 'color': 'image',   'label': 'Distance Preview'},
    ],
    params=[
        {'id': 'target_class', 'type': 'int',   'default': 1, 'min': 0, 'max': 255,
         'label': 'Target Class ID'},
        {'id': 'pixel_size_m', 'type': 'float', 'default': 10.0, 'min': 0.1, 'max': 1000.0,
         'label': 'Pixel Resolution (m)'},
        {'id': 'max_dist_m',   'type': 'float', 'default': 1000.0, 'min': 1.0, 'max': 100000.0,
         'label': 'Max Dist for Preview (m)'},
    ],
    resizable=True, min_width=300, min_height=180,
)
class DistanceToClassNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None or not isinstance(geo, dict) or 'bands' not in geo:
            return {'geotiff': None, 'preview': None}

        bands = geo['bands']
        target_class = int(params.get('target_class', 1))
        pixel_size_m = float(params.get('pixel_size_m', 10.0))
        max_dist_m = float(params.get('max_dist_m', 1000.0))

        if bands.ndim == 3:
            grid = bands[0]
        else:
            grid = bands

        # Identify target pixels
        target_mask = (grid == target_class).astype(np.uint8)

        if not np.any(target_mask):
            # If target class is absent from the raster, assign a fallback high distance
            dist_meters = np.full_like(grid, 99999.0, dtype=np.float32)
        else:
            # cv2.distanceTransform calculates distance from each pixel to the nearest 0 pixel.
            # Thus, we set target pixels to 0 and all other pixels to 1.
            land_mask = (grid != target_class).astype(np.uint8)
            dist_pixels = cv2.distanceTransform(land_mask, cv2.DIST_L2, 5)
            dist_meters = dist_pixels * pixel_size_m

        # Build output geotiff
        out_geo = {
            **geo,
            'bands': dist_meters[np.newaxis] if bands.ndim == 3 else dist_meters,
            'count': 1,
            'band_names': [f'distance_to_class_{target_class}'],
            'dtype': 'float32',
        }

        # Preview: normalize distance map using Viridis color palette
        # We invert normalized so that closer distances are brighter / green-yellow, and far is purple.
        normalized = (dist_meters / max_dist_m * 255.0).clip(0, 255).astype(np.uint8)
        preview = cv2.applyColorMap(255 - normalized, cv2.COLORMAP_VIRIDIS)

        return {
            'geotiff': out_geo,
            'preview': preview,
        }
