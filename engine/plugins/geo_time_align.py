"""
geo_time_align.py — Two-date change-detection primitive.

Takes two GeoTIFFs (t0 = reference, t1 = later) covering overlapping areas
(possibly with different CRS / resolution / extent) and:

  1. Reprojects t1 onto t0's grid (rasterio.warp.reproject, configurable
     resampling).
  2. Aligns band order by name (intersection of band_names from both).
  3. Computes per-band differences (t1 − t0).
  4. Emits a binary change-mask = any |diff_i| > threshold_i.

Outputs are standard `geotiff` dicts so the downstream pipeline
(ml_*, geo_band_calc, geo_geotiff_writer) works unchanged.

Typical use cases:
  - LULC class change between two years (categorical diff)
  - SAR backscatter shift between monthly composites (forest loss, flooding)
  - Vegetation index drop between seasons (drought, fire, harvest)
  - Coastal-line migration (water mask diff)
"""
from __future__ import annotations
import os
from pathlib import Path

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'time_align'


def _ensure_packages() -> tuple[bool, str]:
    try:
        import rasterio  # noqa: F401
        from rasterio.warp import reproject  # noqa: F401
        return True, ''
    except ImportError as e:
        return False, f'missing package {e.name}'


def _info_panel(lines: list[str], title: str = '') -> np.ndarray:
    w, h = 460, 220
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX,
                0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    for i, line in enumerate(lines[:11]):
        cv2.putText(img, str(line)[:72], (8, 48 + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (185, 185, 185), 1, cv2.LINE_AA)
    return img


def _open(geo: dict):
    """Return (rasterio dataset, src_array, src_band_names).

    Accepts canonical geo_copernicus dict (`bands` + `_cache_path`) or legacy
    plugin format (`array` + `path`).
    """
    import rasterio
    path = geo.get('_cache_path') or geo.get('path')
    if path and os.path.exists(path):
        ds = rasterio.open(path)
        names = geo.get('band_names') or [f'b{i}' for i in range(1, ds.count + 1)]
        return ds, ds.read(), names
    # No path: fabricate dataset from in-memory array.
    arr = geo.get('bands')
    if arr is None:
        arr = geo.get('array')
    if arr is None:
        raise ValueError('geotiff missing both path/_cache_path and bands/array')
    arr = np.asarray(arr)
    return None, arr, geo.get('band_names', [f'b{i}' for i in range(arr.shape[0])])


def _stretch(arr: np.ndarray) -> np.ndarray:
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(valid, (2, 98))
    if hi <= lo:
        return np.full(arr.shape, 128, dtype=np.uint8)
    return np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)


# ── Node ─────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_time_align',
    label='Time Align + Change',
    category='geography',
    icon='Diff',
    description=(
        "Align two GeoTIFFs of the same area at different dates (t0 = reference, "
        "t1 = later) with possibly different CRS/resolution/extent. Reprojects t1 "
        "onto t0's grid, computes per-band differences and a binary change-mask. "
        "Generic primitive — works with LULC, SAR, optical, vegetation indices."
    ),
    inputs=[
        {'id': 't0_geotiff', 'color': 'geotiff', 'label': 't₀ (reference)'},
        {'id': 't1_geotiff', 'color': 'geotiff', 'label': 't₁ (later)'},
    ],
    outputs=[
        {'id': 'aligned_t1',  'color': 'geotiff', 'label': 'Aligned t₁'},
        {'id': 'diff',        'color': 'geotiff', 'label': 'Diff (t₁ − t₀)'},
        {'id': 'change_mask', 'color': 'mask',    'label': 'Change Mask'},
        {'id': 'preview',     'color': 'image',   'label': 'Preview (R=t1 G=t0 B=diff)'},
        {'id': 'meta',        'color': 'dict',    'label': 'Meta'},
    ],
    params=[
        {'id': 'resampling',     'type': 'enum',
         'options': ['nearest', 'bilinear', 'cubic', 'average', 'mode'],
         'default': 0,
         'label': 'Resampling (use nearest for categorical, bilinear/cubic for continuous)'},
        {'id': 'change_threshold', 'type': 'float', 'default': 1.0, 'min': 0.0, 'max': 1e6,
         'label': 'Change threshold (per-band |Δ|)'},
        {'id': 'preview_band',   'type': 'string', 'default': '',
         'label': 'Preview band name (blank = first)'},
        {'id': 'cache_dir',      'type': 'string', 'default': 'planetary_cache',
         'label': 'Cache dir'},
    ],
    resizable=True, min_width=300, min_height=220,
)
class GeoTimeAlignNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._sig = None
        self._result: dict | None = None

    def _make_signature(self, t0: dict, t1: dict, params: dict) -> str:
        return '|'.join([
            str(t0.get('path', id(t0))),
            str(t1.get('path', id(t1))),
            str(int(params.get('resampling', 0))),
            str(float(params.get('change_threshold', 1.0))),
        ])

    def process(self, inputs, params):
        t0 = inputs.get('t0_geotiff')
        t1 = inputs.get('t1_geotiff')
        if t0 is None or t1 is None:
            return {'preview': _info_panel(
                ['Connect both t₀ and t₁ GeoTIFFs.'], title='Time Align')}

        ok, msg = _ensure_packages()
        if not ok:
            send_notification(f'TimeAlign: {msg}', level='error', notif_id=_NOTIF)
            return {'preview': _info_panel([msg], title='error')}

        sig = self._make_signature(t0, t1, params)
        if self._sig == sig and self._result is not None:
            return self._result

        try:
            import rasterio
            from rasterio.warp import reproject, Resampling

            ds0, arr0, names0 = _open(t0)
            ds1, arr1, names1 = _open(t1)
        except Exception as e:
            send_notification(f'TimeAlign: read failed: {e}',
                              level='error', notif_id=_NOTIF)
            return {'preview': _info_panel([f'read error: {e}'], title='error')}

        if ds0 is None:
            send_notification('TimeAlign: t₀ has no path on disk — cannot reproject',
                              level='error', notif_id=_NOTIF)
            return {'preview': _info_panel(['t₀ has no on-disk path. '
                                            'Cannot reproject without CRS/transform.'],
                                           title='error')}

        try:
            # ── Band intersection ────────────────────────────────────────────
            common = [n for n in names0 if n in names1]
            if not common:
                send_notification(
                    f'TimeAlign: no shared band names. t0={names0}, t1={names1}',
                    level='warn', notif_id=_NOTIF,
                )
                # fall back to positional matching with min(count)
                k = min(arr0.shape[0], arr1.shape[0])
                common = [f'b{i}' for i in range(k)]
                arr0_sel = arr0[:k]
                arr1_sel = arr1[:k]
                names_used_t1 = [f'b{i}' for i in range(k)]
            else:
                arr0_sel = np.stack([arr0[names0.index(n)] for n in common], axis=0)
                arr1_sel = np.stack([arr1[names1.index(n)] for n in common], axis=0)
                names_used_t1 = common

            # ── Reproject t1 → t0's grid ─────────────────────────────────────
            resamp_opts = ['nearest', 'bilinear', 'cubic', 'average', 'mode']
            resamp_name = resamp_opts[int(params.get('resampling', 0))]
            resamp = getattr(Resampling, resamp_name)

            send_notification('TimeAlign: reprojecting t₁ → t₀ grid…',
                              progress=0.4, notif_id=_NOTIF)

            H, W = arr0_sel.shape[1], arr0_sel.shape[2]
            aligned_t1 = np.full((arr1_sel.shape[0], H, W), np.nan, dtype=np.float32)

            if ds1 is None:
                # In-memory t1 with no CRS — assume identical grid, crop/pad.
                hh, ww = min(arr1_sel.shape[1], H), min(arr1_sel.shape[2], W)
                aligned_t1[:, :hh, :ww] = arr1_sel[:, :hh, :ww]
            else:
                for i in range(arr1_sel.shape[0]):
                    src = arr1_sel[i].astype(np.float32)
                    dst = np.full((H, W), np.nan, dtype=np.float32)
                    reproject(
                        source=src, destination=dst,
                        src_transform=ds1.transform, src_crs=ds1.crs,
                        dst_transform=ds0.transform, dst_crs=ds0.crs,
                        resampling=resamp,
                        src_nodata=np.nan, dst_nodata=np.nan,
                    )
                    aligned_t1[i] = dst

            # ── Per-band diff & change mask ──────────────────────────────────
            arr0_f = arr0_sel.astype(np.float32)
            diff = aligned_t1 - arr0_f
            thr = float(params.get('change_threshold', 1.0))
            absdiff = np.abs(diff)
            with np.errstate(invalid='ignore'):
                any_change = np.any(np.where(np.isfinite(absdiff), absdiff > thr, False), axis=0)
            change_mask = any_change.astype(np.uint8) * 255

            # ── Persist aligned + diff GeoTIFFs ──────────────────────────────
            cache_dir = params.get('cache_dir', 'planetary_cache')
            d = Path(cache_dir) if os.path.isabs(cache_dir) else (
                Path(t0.get('path', __file__)).parent / cache_dir
            )
            d.mkdir(parents=True, exist_ok=True)
            stem = Path(t0.get('path', 'tmem')).stem
            aligned_path = str(d / f'{stem}_t1_aligned.tif')
            diff_path    = str(d / f'{stem}_diff.tif')

            profile = ds0.profile.copy()
            profile.update(count=aligned_t1.shape[0], dtype='float32',
                           compress='deflate', predictor=2, nodata=float('nan'))

            with rasterio.open(aligned_path, 'w', **profile) as dst:
                dst.write(aligned_t1)
                for i, n in enumerate(common, start=1):
                    dst.set_band_description(i, n)

            with rasterio.open(diff_path, 'w', **profile) as dst:
                dst.write(diff)
                for i, n in enumerate(common, start=1):
                    dst.set_band_description(i, f'{n}_diff')

            # ── Preview: R=t1, G=t0, B=|diff| on chosen band ────────────────
            pb_name = (params.get('preview_band') or common[0]).strip()
            if pb_name not in common:
                pb_name = common[0]
            idx = common.index(pb_name)
            r = _stretch(aligned_t1[idx])
            g = _stretch(arr0_f[idx])
            b = _stretch(np.abs(diff[idx]))
            preview = np.stack([b, g, r], axis=-1)
            # Overlay change mask boundary
            edges = cv2.Canny(change_mask, 50, 150)
            preview[edges > 0] = (0, 255, 255)
            # Resize preview if huge
            max_dim = 720
            h, w = preview.shape[:2]
            if max(h, w) > max_dim:
                s = max_dim / max(h, w)
                preview = cv2.resize(preview, (int(w * s), int(h * s)),
                                     interpolation=cv2.INTER_AREA)

            change_pct = 100.0 * float(change_mask.sum()) / change_mask.size / 255.0

            meta = {
                'source':       'geo_time_align',
                't0_path':      t0.get('_cache_path') or t0.get('path'),
                't1_path':      t1.get('_cache_path') or t1.get('path'),
                'common_bands': common,
                'resampling':   resamp_name,
                'change_threshold': thr,
                'change_pct':   round(change_pct, 4),
                'aligned_path': aligned_path,
                'diff_path':    diff_path,
            }

            # Build canonical geo_copernicus-compatible geotiff dicts so they
            # chain cleanly into ml_*, geo_band_calc, geo_ground_truth_sampler.
            def _geo(arr: np.ndarray, names: list[str], path: str) -> dict:
                base = dict(t0)
                base.update({
                    'bands':       arr.astype(np.float32),
                    'band_names':  names,
                    'count':       arr.shape[0],
                    '_cache_path': path,
                    '_bands':      names,
                    'meta':        meta,
                })
                return base

            geotiff_aligned = _geo(aligned_t1, common, aligned_path)
            geotiff_diff    = _geo(diff, [f'{n}_diff' for n in common], diff_path)

            self._sig = sig
            self._result = {
                'aligned_t1':  geotiff_aligned,
                'diff':        geotiff_diff,
                'change_mask': change_mask,
                'preview':     preview,
                'meta':        meta,
            }
            send_notification(
                f'TimeAlign: {len(common)} bands aligned, change={change_pct:.2f}%',
                progress=1.0, notif_id=_NOTIF,
            )
            return self._result
        finally:
            if ds0 is not None:
                ds0.close()
            if ds1 is not None:
                ds1.close()
