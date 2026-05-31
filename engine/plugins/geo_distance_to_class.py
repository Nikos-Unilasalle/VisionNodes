"""
geo_distance_to_class.py — Euclidean distance (metres) to a target class or threshold.

Two modes (param `mode`):
  Exact class   — target pixels where value == target_class  (classification rasters)
  Threshold ≥   — target pixels where value >= threshold_value (continuous bands, e.g. JRC occurrence)
  Threshold ≤   — target pixels where value <= threshold_value

Threshold mode lets you drive the cutoff from a slider without a separate band_calc node.
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
        "Euclidean distance in metres from each pixel to the nearest target pixel. "
        "Exact class mode: matches pixels where value == Target Class ID. "
        "Threshold mode: matches pixels where value >= (or <=) Threshold Value — "
        "useful for continuous bands such as JRC occurrence (0–100)."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Raster'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Distance Raster (m)'},
        {'id': 'preview', 'color': 'image',   'label': 'Distance Preview'},
    ],
    params=[
        {
            'id': 'mode', 'type': 'enum',
            'options': ['Exact class', 'Threshold ≥', 'Threshold ≤'],
            'default': 0,
            'label': 'Mode',
        },
        {
            'id': 'target_class', 'type': 'int', 'default': 1, 'min': 0, 'max': 65535,
            'label': 'Target Class ID',
            'show_if': {'param': 'mode', 'value': 0},
        },
        {
            'id': 'threshold_value', 'type': 'float', 'default': 30.0,
            'min': -1e6, 'max': 1e6,
            'label': 'Threshold Value',
            'show_if': {'param': 'mode', 'value': 1},
        },
        {
            'id': 'threshold_value_le', 'type': 'float', 'default': 0.5,
            'min': -1e6, 'max': 1e6,
            'label': 'Threshold Value',
            'show_if': {'param': 'mode', 'value': 2},
        },
        {
            'id': 'pixel_size_m', 'type': 'float', 'default': 10.0,
            'min': 0.1, 'max': 1000.0,
            'label': 'Pixel Resolution (m)',
        },
        {
            'id': 'max_dist_m', 'type': 'float', 'default': 1000.0,
            'min': 1.0, 'max': 100000.0,
            'label': 'Max Dist for Preview (m)',
        },
    ],
    resizable=True, min_width=300, min_height=180,
)
class DistanceToClassNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None or not isinstance(geo, dict) or 'bands' not in geo:
            return {'geotiff': None, 'preview': None}

        bands        = geo['bands']
        mode         = int(params.get('mode', 0))
        target_class = int(params.get('target_class', 1))
        thr_ge       = float(params.get('threshold_value', 30.0))
        thr_le       = float(params.get('threshold_value_le', 0.5))
        pixel_size_m = float(params.get('pixel_size_m', 10.0))
        max_dist_m   = float(params.get('max_dist_m', 1000.0))

        grid = bands[0] if bands.ndim == 3 else bands

        if mode == 0:
            target_mask = (grid == target_class).astype(np.uint8)
            label = f'distance_to_class_{target_class}'
        elif mode == 1:
            target_mask = (grid >= thr_ge).astype(np.uint8)
            label = f'distance_to_gte_{thr_ge}'
        else:
            target_mask = (grid <= thr_le).astype(np.uint8)
            label = f'distance_to_lte_{thr_le}'

        if not np.any(target_mask):
            dist_meters = np.full_like(grid, 99999.0, dtype=np.float32)
        else:
            land_mask   = 1 - target_mask
            dist_pixels = cv2.distanceTransform(land_mask, cv2.DIST_L2, 5)
            dist_meters = dist_pixels * pixel_size_m

        out_geo = {
            **geo,
            'bands':      dist_meters[np.newaxis] if bands.ndim == 3 else dist_meters,
            'count':      1,
            'band_names': [label],
            'dtype':      'float32',
        }

        normalized = (dist_meters / max_dist_m * 255.0).clip(0, 255).astype(np.uint8)
        preview    = cv2.applyColorMap(255 - normalized, cv2.COLORMAP_VIRIDIS)

        return {'geotiff': out_geo, 'preview': preview}
