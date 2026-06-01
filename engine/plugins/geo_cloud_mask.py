"""
geo_cloud_mask.py — Cloud and invalid pixel masking for Sentinel-2.

Produces a binary valid-pixel mask (1=valid, 0=cloud/shadow/invalid) from:
  - SCL band (Sentinel-2 L2A Scene Classification Layer), and/or
  - Absolute NDVI threshold on a spectral index stack (dark pixels = cloud shadow)

Output mask can be fed directly into geo_spectral_change (valid_mask input).

SCL class codes (ESA):
  0  No data
  1  Saturated / defective
  2  Dark area (topographic shadow)
  3  Cloud shadow
  4  Vegetation
  5  Bare soil
  6  Water
  7  Unclassified
  8  Cloud medium probability
  9  Cloud high probability
  10 Thin cirrus
  11 Snow/ice
Default exclude: 0,1,2,3,8,9,10,11
"""
from __future__ import annotations

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_cloud_mask'

# Preview colors (BGR): valid=green, invalid=red, border=white
_COLOR_VALID   = (40,  160, 40)
_COLOR_INVALID = (40,   40, 180)


def _parse_ints(s: str) -> set[int]:
    out: set[int] = set()
    for item in s.split(','):
        item = item.strip()
        if item.lstrip('-').isdigit():
            out.add(int(item))
    return out


@vision_node(
    type_id='geo_cloud_mask',
    label='Cloud Mask',
    category='geography',
    icon='Cloud',
    description=(
        'Generates a valid-pixel mask (1=valid, 0=cloud/shadow/invalid) for '
        'Sentinel-2 imagery. Combines SCL band exclusion (classes 0,1,2,3,8,9,10,11 '
        'by default) with an optional absolute NDVI floor (rejects cloud shadows '
        'where NDVI is abnormally low). Output feeds geo_spectral_change valid_mask.'
    ),
    inputs=[
        {'id': 'scl',      'color': 'geotiff', 'label': 'SCL band (Sentinel-2 L2A, optional)'},
        {'id': 'spectral', 'color': 'geotiff', 'label': 'Spectral indices stack (for NDVI floor, optional)'},
    ],
    outputs=[
        {'id': 'mask',    'color': 'geotiff', 'label': 'Valid mask (uint8, 1=valid)'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview (green=valid, red=masked)'},
    ],
    params=[
        {'id': 'scl_exclude', 'type': 'string', 'default': '0,1,2,3,8,9,10,11',
         'label': 'SCL classes to exclude (comma-sep)'},
        {'id': 'ndvi_band',   'type': 'string', 'default': 'NDVI',
         'label': 'NDVI band name in spectral stack'},
        {'id': 'ndvi_min',    'type': 'float',  'default': 0.0, 'min': -1.0, 'max': 1.0,
         'label': 'NDVI floor (pixels below = invalid, 0 = disabled)'},
        {'id': 'dilate_px',   'type': 'int',    'default': 3, 'min': 0, 'max': 30,
         'label': 'Dilate invalid regions (px) — captures cloud edges'},
        {'id': 'node_note',   'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=280, min_height=160,
)
class GeoCloudMaskNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        scl_geo      = inputs.get('scl')
        spectral_geo = inputs.get('spectral')

        if scl_geo is None and spectral_geo is None:
            send_notification('CloudMask: connect SCL and/or spectral stack', notif_id=_NOTIF)
            return {}

        # Determine output shape from whichever input is available
        ref = scl_geo if scl_geo is not None else spectral_geo
        ref_bands = np.asarray(ref['bands'])
        if ref_bands.ndim == 3:
            _, H, W = ref_bands.shape
        else:
            H, W = ref_bands.shape

        transform = ref.get('transform')
        crs       = ref.get('crs')

        # Start fully valid
        valid = np.ones((H, W), dtype=bool)
        invalid_scl   = np.zeros((H, W), dtype=bool)
        invalid_ndvi  = np.zeros((H, W), dtype=bool)

        # SCL exclusion
        if scl_geo is not None and scl_geo.get('bands') is not None:
            scl_arr = np.asarray(scl_geo['bands'])
            if scl_arr.ndim == 3: scl_arr = scl_arr[0]
            if scl_arr.shape != (H, W):
                send_notification('CloudMask: SCL shape mismatch — ignored',
                                  level='warn', notif_id=_NOTIF)
            else:
                exclude_classes = _parse_ints(str(params.get('scl_exclude', '0,1,2,3,8,9,10,11')))
                for cls in exclude_classes:
                    invalid_scl |= (scl_arr == cls)

        # NDVI floor
        ndvi_min = float(params.get('ndvi_min', 0.0))
        if spectral_geo is not None and spectral_geo.get('bands') is not None and ndvi_min != 0.0:
            sp_bands = np.asarray(spectral_geo['bands'], dtype=np.float32)
            if sp_bands.ndim == 2: sp_bands = sp_bands[np.newaxis]
            band_names: list[str] = spectral_geo.get('band_names') or []
            ndvi_band_name = str(params.get('ndvi_band', 'NDVI'))
            if ndvi_band_name in band_names:
                bidx = band_names.index(ndvi_band_name)
                if sp_bands.shape[1:] == (H, W):
                    invalid_ndvi = sp_bands[bidx] < ndvi_min
                else:
                    send_notification('CloudMask: spectral shape mismatch — NDVI floor skipped',
                                      level='warn', notif_id=_NOTIF)
            else:
                send_notification(f'CloudMask: band "{ndvi_band_name}" not found in spectral stack',
                                  level='warn', notif_id=_NOTIF)

        invalid = invalid_scl | invalid_ndvi

        # Dilate invalid mask to capture cloud edges
        dilate_px = int(params.get('dilate_px', 3))
        if dilate_px > 0 and invalid.any():
            kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1,) * 2)
            invalid = cv2.dilate(invalid.astype(np.uint8), kernel).astype(bool)

        valid = ~invalid

        n_valid   = int(valid.sum())
        n_total   = H * W
        pct_valid = 100.0 * n_valid / n_total if n_total > 0 else 0.0

        # Preview
        preview = np.zeros((H, W, 3), dtype=np.uint8)
        preview[valid]   = _COLOR_VALID
        preview[~valid]  = _COLOR_INVALID

        send_notification(
            f'CloudMask: {pct_valid:.1f}% valid  ({n_valid:,}/{n_total:,} px)'
            + (f'  SCL excluded={int(invalid_scl.sum()):,}' if scl_geo is not None else '')
            + (f'  NDVI<{ndvi_min}={int(invalid_ndvi.sum()):,}' if ndvi_min != 0.0 else ''),
            progress=1.0, notif_id=_NOTIF,
        )

        mask_geotiff = {
            'bands':      valid.astype(np.uint8)[np.newaxis],
            'transform':  transform,
            'crs':        crs,
            'band_names': ['valid_mask'],
        }

        return {'mask': mask_geotiff, 'preview': preview}
