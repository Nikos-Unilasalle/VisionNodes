"""
geo_band_stack.py — Merge two geo dicts into a single multi-band raster.

Takes a PRIMARY and SECONDARY geo dict (possibly with different CRS,
resolution, extent) and:

  1. Reprojects the secondary onto the primary's pixel grid.
  2. Concatenates all bands → one geo dict (primary_bands + secondary_bands).

Typical use:
  - Fuse S1 polarization features (primary) with S2 spectral indices (secondary)
    → single feature stack for ml_* classifiers.
  - Stack a DEM layer onto an optical composite.
  - Combine two LULC products for cross-product analysis.

Output is a canonical geo dict compatible with all downstream geo_* and ml_*
nodes (geo_band_calc, geo_ground_truth_sampler, ml_random_forest, …).
"""
from __future__ import annotations
import os
from pathlib import Path

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'band_stack'


def _info_panel(lines: list[str], title: str = '') -> np.ndarray:
    w, h = 420, 160
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 18), cv2.FONT_HERSHEY_SIMPLEX,
                0.44, (200, 200, 200), 1, cv2.LINE_AA)
    for i, ln in enumerate(lines[:8]):
        cv2.putText(img, str(ln)[:65], (8, 44 + i * 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (170, 170, 170), 1, cv2.LINE_AA)
    return img


def _stretch(arr: np.ndarray) -> np.ndarray:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, (2, 98))
    if hi <= lo:
        return np.full(arr.shape, 128, dtype=np.uint8)
    return np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)


@vision_node(
    type_id='geo_band_stack',
    label='Band Stack',
    category='geography',
    icon='Layers',
    description=(
        "Merge two geo dicts into one multi-band raster. "
        "Reprojects the secondary onto the primary's pixel grid (configurable resampling). "
        "Useful for fusing S1 SAR features with S2 spectral indices before classification."
    ),
    inputs=[
        {'id': 'primary',   'color': 'geotiff', 'label': 'Primary (reference grid)'},
        {'id': 'secondary', 'color': 'geotiff', 'label': 'Secondary (reprojected)'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Fused stack'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview (RGB false-color)'},
        {'id': 'meta',    'color': 'dict',    'label': 'Meta'},
    ],
    params=[
        {'id': 'resampling', 'type': 'enum',
         'options': ['bilinear', 'nearest', 'cubic', 'average'],
         'default': 0,
         'label': 'Resampling method (bilinear for continuous, nearest for categorical)'},
        {'id': 'prefix_secondary', 'type': 'bool', 'default': False,
         'label': 'Prefix secondary band names with "sec_" to avoid collisions'},
        {'id': 'cache_dir', 'type': 'string', 'default': 'copernicus_cache',
         'label': 'Cache dir'},
    ],
    resizable=True, min_width=300, min_height=200,
)
class GeoBandStackNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._sig: str | None = None
        self._result: dict | None = None

    def _signature(self, primary: dict, secondary: dict, params: dict) -> str:
        return '|'.join([
            str(primary.get('_cache_path', id(primary))),
            str(secondary.get('_cache_path', id(secondary))),
            str(params.get('resampling', 0)),
            str(params.get('prefix_secondary', False)),
        ])

    def process(self, inputs: dict, params: dict) -> dict:
        primary   = inputs.get('primary')
        secondary = inputs.get('secondary')

        if primary is None or secondary is None:
            return {'preview': _info_panel(
                ['Connect both Primary and Secondary geo inputs.'],
                title='Band Stack')}

        sig = self._signature(primary, secondary, params)
        if sig == self._sig and self._result is not None:
            return self._result

        try:
            import rasterio
            from rasterio.warp import reproject, Resampling
        except ImportError:
            msg = 'rasterio not installed'
            send_notification(f'BandStack: {msg}', level='error', notif_id=_NOTIF)
            return {'preview': _info_panel([msg], title='error')}

        arr_p = np.asarray(primary['bands'],   dtype=np.float32)
        arr_s = np.asarray(secondary['bands'], dtype=np.float32)
        names_p: list[str] = list(primary.get('band_names',
                                               [f'p{i+1}' for i in range(arr_p.shape[0])]))
        names_s: list[str] = list(secondary.get('band_names',
                                                 [f's{i+1}' for i in range(arr_s.shape[0])]))

        resamp_opts = ['bilinear', 'nearest', 'cubic', 'average']
        resamp_name = resamp_opts[int(params.get('resampling', 0))]
        resamp = getattr(Resampling, resamp_name)

        # ── Open on-disk datasets for proper CRS/transform info ─────────────
        path_p = primary.get('_cache_path')  or primary.get('path')
        path_s = secondary.get('_cache_path') or secondary.get('path')

        H, W = arr_p.shape[1], arr_p.shape[2]

        if path_p and path_s and os.path.exists(path_p) and os.path.exists(path_s):
            send_notification('BandStack: reprojecting secondary → primary grid…',
                              progress=0.3, notif_id=_NOTIF)
            with rasterio.open(path_p) as ds_p, rasterio.open(path_s) as ds_s:
                aligned_s = np.full((arr_s.shape[0], H, W), np.nan, dtype=np.float32)
                for i in range(arr_s.shape[0]):
                    reproject(
                        source=arr_s[i], destination=aligned_s[i],
                        src_transform=ds_s.transform, src_crs=ds_s.crs,
                        dst_transform=ds_p.transform, dst_crs=ds_p.crs,
                        resampling=resamp,
                        src_nodata=np.nan, dst_nodata=np.nan,
                    )
        else:
            # In-memory: assume same grid, crop/pad to match primary shape
            send_notification('BandStack: no on-disk paths — assuming same grid (crop/pad)',
                              level='warn', notif_id=_NOTIF)
            hh = min(arr_s.shape[1], H)
            ww = min(arr_s.shape[2], W)
            aligned_s = np.full((arr_s.shape[0], H, W), np.nan, dtype=np.float32)
            aligned_s[:, :hh, :ww] = arr_s[:, :hh, :ww]

        # ── Prefix secondary band names if requested ─────────────────────────
        if params.get('prefix_secondary', False):
            names_s = [f'sec_{n}' for n in names_s]

        # ── Deduplicate band names ────────────────────────────────────────────
        existing = set(names_p)
        deduped_s: list[str] = []
        for n in names_s:
            if n in existing:
                n = f'sec_{n}'
            deduped_s.append(n)
            existing.add(n)

        fused = np.concatenate([arr_p, aligned_s], axis=0)
        fused_names = names_p + deduped_s

        # ── Preview: false-color RGB from bands 0/1/2 of fused stack ────────
        r8 = _stretch(fused[0]) if fused.shape[0] > 0 else np.zeros((H, W), np.uint8)
        g8 = _stretch(fused[1]) if fused.shape[0] > 1 else r8
        b8 = _stretch(fused[2]) if fused.shape[0] > 2 else g8
        preview = np.stack([b8, g8, r8], axis=-1)
        max_dim = 720
        ph, pw = preview.shape[:2]
        if max(ph, pw) > max_dim:
            sc = max_dim / max(ph, pw)
            preview = cv2.resize(preview, (int(pw * sc), int(ph * sc)),
                                 interpolation=cv2.INTER_AREA)

        meta = {
            'source':          'geo_band_stack',
            'primary_path':    path_p,
            'secondary_path':  path_s,
            'primary_bands':   names_p,
            'secondary_bands': deduped_s,
            'total_bands':     len(fused_names),
            'resampling':      resamp_name,
        }

        out_geo = {
            **primary,                 # inherit CRS, transform, bounds from primary
            'bands':      fused,
            'band_names': fused_names,
            'count':      fused.shape[0],
        }

        send_notification(
            f'BandStack: {len(names_p)} + {len(deduped_s)} = {len(fused_names)} bands',
            progress=1.0, notif_id=_NOTIF,
        )

        self._sig = sig
        self._result = {'geotiff': out_geo, 'preview': preview, 'meta': meta}
        return self._result
