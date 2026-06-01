"""
geotiff_to_mask.py — Extract one band from a GeoTIFF dict as a plain binary mask.

Useful when a geo node (geo_cloud_mask, geo_ndwi_mask, geo_mask…) produces a
GeoTIFF output but a downstream node expects a non-georeferenced mask array.

Output is uint8 (0 / 255), compatible with mask_ops, util_mask_band, etc.
"""
from __future__ import annotations
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geotiff_to_mask'


@vision_node(
    type_id='geotiff_to_mask',
    label='GeoTIFF → Mask',
    category='geography',
    icon='Layers',
    description=(
        'Extracts one band from a GeoTIFF dict and returns it as a plain binary '
        'mask (uint8 0/255). Use to bridge geo nodes (geo_cloud_mask, geo_ndwi_mask…) '
        'to standard mask nodes (mask_ops, util_mask_band, invert_mask…).'
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF'},
    ],
    outputs=[
        {'id': 'mask', 'color': 'mask', 'label': 'Binary mask (0/255)'},
    ],
    params=[
        {'id': 'band_index', 'type': 'int',   'default': 0, 'min': 0, 'max': 31,
         'label': 'Band index'},
        {'id': 'threshold',  'type': 'float', 'default': 0.5, 'min': 0.0, 'max': 1.0,
         'label': 'Threshold (values > threshold → 255)'},
        {'id': 'node_note',  'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=200, min_height=120,
)
class GeoTiffToMaskNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')

        if not isinstance(geo, dict) or geo.get('bands') is None:
            send_notification('GeoTIFF→Mask: connect a GeoTIFF', notif_id=_NOTIF)
            return {}

        bands = np.asarray(geo['bands'], dtype=np.float32)
        if bands.ndim == 2:
            bands = bands[np.newaxis]

        band_idx = int(params.get('band_index', 0))
        if band_idx >= bands.shape[0]:
            send_notification(
                f'GeoTIFF→Mask: band_index {band_idx} out of range '
                f'(stack has {bands.shape[0]} band(s)) — using band 0',
                level='warn', notif_id=_NOTIF,
            )
            band_idx = 0

        band = bands[band_idx]
        threshold = float(params.get('threshold', 0.5))

        mask = ((band > threshold).astype(np.uint8)) * 255
        return {'mask': mask}
