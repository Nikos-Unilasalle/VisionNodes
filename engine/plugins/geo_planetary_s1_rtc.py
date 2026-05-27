"""
geo_planetary_s1_rtc.py — Sentinel-1 Radiometric Terrain Corrected (RTC) backscatter
from Microsoft Planetary Computer STAC API.

Why this node exists
--------------------
For cloud-prone regions (French Guiana, equatorial Africa, monsoon Asia), Sentinel-2
optical scenes are scarce. Sentinel-1 SAR penetrates clouds and sees both water
surface (smooth → dark) and flooded vegetation (double-bounce → very bright),
making it essential for wetland / mangrove / flood mapping.

The RTC collection on Microsoft Planetary Computer ships SAR scenes already
preprocessed:
  - calibrated to sigma-0 (or gamma-0) linear power
  - orthorectified using a global DEM
  - radiometric terrain corrected to remove topographic distortion
  - stored as Cloud Optimized GeoTIFFs (COGs) with per-band assets (vv, vh)

This means we can skip the heavy ESA SNAP preprocessing chain and directly
read windowed COGs into rasterio. No authentication required.

Outputs
-------
  - geotiff  : multi-band GeoTIFF (VV, VH, [VV_VH_ratio])
  - preview  : false-color RGB (R=VV, G=VH, B=VV/VH) for QC
  - meta     : STAC metadata (acquisition dates, orbits, scene count)

Reference: https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc
"""
from __future__ import annotations
import os
import json
import hashlib
import tempfile
from pathlib import Path

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'planetary_s1_rtc'

_STAC_URL = 'https://planetarycomputer.microsoft.com/api/stac/v1'
_COLLECTION = 'sentinel-1-rtc'

# Default cache directory under the project; same convention as geo_copernicus.
_CACHE_ROOT = Path(__file__).parent / 'planetary_cache'
_CACHE_ROOT.mkdir(exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_packages() -> tuple[bool, str]:
    """Lazy import — surface a helpful message if the user hasn't installed."""
    try:
        import rasterio  # noqa: F401
        import pystac_client  # noqa: F401
        import planetary_computer  # noqa: F401
        return True, ''
    except ImportError as e:
        return False, (
            f"missing package ({e.name}). "
            "Install with: pip install pystac-client planetary-computer rasterio"
        )


def _params_hash(params: dict) -> str:
    """Stable hash of the parameters that affect the downloaded raster."""
    keys = ('bbox', 'date_start', 'date_end', 'polarization', 'orbit',
            'composite', 'resolution', 'to_db')
    payload = json.dumps({k: params.get(k) for k in keys}, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()[:14]


def _parse_bbox(bbox_str: str) -> list[float] | None:
    """Parse 'lon_min,lat_min,lon_max,lat_max' → [4 floats]."""
    if not bbox_str:
        return None
    try:
        vals = [float(x.strip()) for x in bbox_str.split(',')]
        if len(vals) != 4:
            return None
        lon_min, lat_min, lon_max, lat_max = vals
        if lon_min >= lon_max or lat_min >= lat_max:
            return None
        return [lon_min, lat_min, lon_max, lat_max]
    except ValueError:
        return None


def _stretch_to_uint8(arr: np.ndarray, p_lo: float = 2, p_hi: float = 98) -> np.ndarray:
    """Percentile stretch a float band to uint8 for preview."""
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros(arr.shape, dtype=np.uint8)
    lo, hi = np.percentile(valid, (p_lo, p_hi))
    if hi <= lo:
        return np.full(arr.shape, 128, dtype=np.uint8)
    out = np.clip((arr - lo) / (hi - lo) * 255, 0, 255)
    return np.nan_to_num(out, nan=0).astype(np.uint8)


def _info_panel(lines: list[str], w: int = 420, h: int = 220, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX,
                0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 16
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:70], (8, 48 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
    return img


# ── STAC query + COG read ────────────────────────────────────────────────────

def _search_items(bbox: list[float], date_start: str, date_end: str,
                  orbit_filter: str) -> list:
    """Return STAC items, optionally filtered by orbit direction."""
    import pystac_client
    import planetary_computer

    catalog = pystac_client.Client.open(_STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(
        collections=[_COLLECTION],
        bbox=bbox,
        datetime=f'{date_start}/{date_end}',
        limit=500,
    )
    items = list(search.items())

    of = (orbit_filter or 'Any').lower()
    if of in ('ascending', 'descending'):
        items = [i for i in items
                 if str(i.properties.get('sat:orbit_state', '')).lower() == of]
    return items


def _read_window(item, bbox: list[float], polarization: str, resolution: int) -> dict:
    """Read a single STAC item's VV/VH bands windowed to bbox at target resolution."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    from rasterio.enums import Resampling

    out: dict[str, np.ndarray] = {}
    asset_ids = []
    if 'V' in polarization.upper() or polarization == 'Both':
        asset_ids = ['vv', 'vh']
    elif polarization == 'VV':
        asset_ids = ['vv']
    elif polarization == 'VH':
        asset_ids = ['vh']
    else:
        asset_ids = ['vv', 'vh']

    transform = None
    crs = None
    height_out = width_out = None

    for asset_id in asset_ids:
        if asset_id not in item.assets:
            continue
        href = item.assets[asset_id].href
        with rasterio.open(href) as ds:
            dst_bounds = transform_bounds('EPSG:4326', ds.crs, *bbox, densify_pts=21)
            window = from_bounds(*dst_bounds, transform=ds.transform)
            window = window.round_offsets().round_lengths()
            if window.width <= 0 or window.height <= 0:
                continue

            # Compute target dimensions to honor `resolution` (meters/pixel) if possible.
            native_res = abs(ds.transform.a)
            scale = max(1.0, resolution / native_res) if native_res > 0 else 1.0
            out_h = max(1, int(window.height / scale))
            out_w = max(1, int(window.width / scale))

            arr = ds.read(
                1,
                window=window,
                out_shape=(out_h, out_w),
                resampling=Resampling.average,
                masked=False,
            ).astype(np.float32)

            # 0 = nodata in S1-RTC linear power; convert to NaN so composites ignore it.
            arr = np.where(arr <= 0, np.nan, arr)

            out[asset_id] = arr
            if transform is None:
                transform = rasterio.windows.transform(window, ds.transform)
                # Scale transform to match the resampled output.
                transform = transform * transform.scale(
                    window.width / out_w, window.height / out_h
                )
                crs = ds.crs
                height_out, width_out = out_h, out_w
    return {'bands': out, 'transform': transform, 'crs': crs,
            'shape': (height_out, width_out)} if out else {}


def _composite(stack: list[np.ndarray], method: str) -> np.ndarray:
    """Reduce a stack along axis 0 with NaN-aware operator."""
    arr = np.stack(stack, axis=0)
    if method == 'median':
        return np.nanmedian(arr, axis=0)
    if method == 'mean':
        return np.nanmean(arr, axis=0)
    if method == 'min':
        return np.nanmin(arr, axis=0)
    if method == 'max':
        return np.nanmax(arr, axis=0)
    return arr[0]


# ── Main node ────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_planetary_s1_rtc',
    label='Sentinel-1 RTC (Planetary)',
    category='geography',
    icon='Radio',
    description=(
        "Fetch Sentinel-1 RTC (Radiometric Terrain Corrected) SAR backscatter from "
        "Microsoft Planetary Computer. No authentication required. Returns calibrated "
        "VV/VH bands as a multi-band GeoTIFF — ideal for cloud-prone regions where "
        "Sentinel-2 alone is insufficient (wetlands, mangroves, equatorial forests)."
    ),
    inputs=[],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF (VV, VH)'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview RGB'},
        {'id': 'meta',    'color': 'dict',    'label': 'Meta'},
    ],
    params=[
        {'id': 'bbox',          'type': 'string', 'default': '-53.30,4.40,-52.60,5.50',
         'label': 'BBOX (lon_min,lat_min,lon_max,lat_max)'},
        {'id': 'date_start',    'type': 'string', 'default': '2023-01-01', 'label': 'Start Date'},
        {'id': 'date_end',      'type': 'string', 'default': '2023-12-31', 'label': 'End Date'},
        {'id': 'polarization',  'type': 'enum',   'options': ['Both', 'VV', 'VH'],
         'default': 0, 'label': 'Polarization'},
        {'id': 'orbit',         'type': 'enum',   'options': ['Any', 'Ascending', 'Descending'],
         'default': 0, 'label': 'Orbit'},
        {'id': 'composite',     'type': 'enum',   'options': ['median', 'mean', 'first', 'min', 'max'],
         'default': 0, 'label': 'Composite Method'},
        {'id': 'resolution',    'type': 'int',    'default': 20, 'min': 10, 'max': 1000,
         'label': 'Resolution (m/px)'},
        {'id': 'to_db',         'type': 'bool',   'default': True, 'label': 'Convert to dB (10·log10)'},
        {'id': 'max_scenes',    'type': 'int',    'default': 30, 'min': 1, 'max': 500,
         'label': 'Max scenes for composite'},
        {'id': 'cache_dir',     'type': 'string', 'default': 'planetary_cache', 'label': 'Cache Dir'},
        {'id': 'fetch',         'type': 'trigger','default': 0, 'label': 'Fetch'},
    ],
    resizable=True, min_width=300, min_height=220,
)
class GeoPlanetaryS1RTCNode(NodeProcessor):
    """Sentinel-1 RTC fetcher backed by Microsoft Planetary Computer."""

    def __init__(self):
        super().__init__()
        self._prev_fetch = 0
        self._result: dict | None = None
        self._notif_id = f'planetary_s1_rtc_{id(self)}'

    # ── Idle preview ─────────────────────────────────────────────────────────
    def _idle_preview(self, msg: str = '') -> dict:
        bbox = _parse_bbox('default')  # placeholder
        return {'preview': _info_panel(
            ['Click Fetch to download S1 RTC.', msg] if msg
            else ['Click Fetch to download S1 RTC.'],
            title='Sentinel-1 RTC (Planetary Computer)',
        )}

    # ── Cache layer ──────────────────────────────────────────────────────────
    def _cache_path(self, params: dict) -> Path:
        sub = params.get('cache_dir', 'planetary_cache')
        d = Path(sub) if os.path.isabs(sub) else (Path(__file__).parent / sub)
        d.mkdir(parents=True, exist_ok=True)
        return d / f's1rtc_{_params_hash(params)}.tif'

    # ── Main process ─────────────────────────────────────────────────────────
    def process(self, inputs, params):
        run_val = params.get('fetch', 0)
        rising = run_val != self._prev_fetch and run_val not in (False, 0, None)
        self._prev_fetch = run_val

        if not rising and self._result is not None:
            return self._result
        if not rising:
            return self._idle_preview()

        ok, msg = _ensure_packages()
        if not ok:
            send_notification(f'S1 RTC: {msg}', level='error', notif_id=self._notif_id)
            return {'preview': _info_panel([msg], title='S1 RTC — missing deps')}

        bbox = _parse_bbox(params.get('bbox', ''))
        if bbox is None:
            send_notification('S1 RTC: invalid BBOX', level='error', notif_id=self._notif_id)
            return {'preview': _info_panel(
                ['Invalid BBOX. Expected "lon_min,lat_min,lon_max,lat_max"'],
                title='S1 RTC — error')}

        # ── Cache hit ────────────────────────────────────────────────────────
        cache_file = self._cache_path(params)
        if cache_file.exists():
            try:
                import rasterio
                with rasterio.open(cache_file) as ds:
                    arr = ds.read()
                    meta_tags = ds.tags()
                self._result = self._build_outputs(arr, str(cache_file), meta_tags, from_cache=True)
                send_notification(
                    f'S1 RTC: loaded from cache ({arr.shape})',
                    progress=1.0, notif_id=self._notif_id,
                )
                return self._result
            except Exception as e:
                send_notification(f'S1 RTC: cache read failed: {e}',
                                  level='warn', notif_id=self._notif_id)

        # ── STAC search ──────────────────────────────────────────────────────
        date_start = str(params.get('date_start', '2023-01-01'))
        date_end = str(params.get('date_end', '2023-12-31'))
        orbit_opts = ['Any', 'Ascending', 'Descending']
        orbit = orbit_opts[int(params.get('orbit', 0))]
        send_notification('S1 RTC: querying STAC…', progress=0.1, notif_id=self._notif_id)
        try:
            items = _search_items(bbox, date_start, date_end, orbit)
        except Exception as e:
            send_notification(f'S1 RTC: STAC query failed: {e}',
                              level='error', notif_id=self._notif_id)
            return {'preview': _info_panel([f'STAC error: {e}'], title='S1 RTC — error')}

        if not items:
            send_notification('S1 RTC: 0 scenes match', level='warn', notif_id=self._notif_id)
            return {'preview': _info_panel(
                [f'No S1 RTC scenes for bbox + dates + orbit={orbit}.'],
                title='S1 RTC — empty')}

        max_scenes = int(params.get('max_scenes', 30))
        # Sort by date ascending and pick at most max_scenes spread across the window.
        items = sorted(items, key=lambda it: it.datetime)
        if len(items) > max_scenes:
            idx = np.linspace(0, len(items) - 1, max_scenes).round().astype(int)
            items = [items[i] for i in idx]

        send_notification(
            f'S1 RTC: reading {len(items)} scenes…',
            progress=0.25, notif_id=self._notif_id,
        )

        # ── Read each item windowed ──────────────────────────────────────────
        pol_opts = ['Both', 'VV', 'VH']
        polarization = pol_opts[int(params.get('polarization', 0))]
        resolution = int(params.get('resolution', 20))

        stacks: dict[str, list[np.ndarray]] = {}
        transform = crs = None
        shape = None
        scene_dates: list[str] = []

        for i, item in enumerate(items):
            try:
                sub = _read_window(item, bbox, polarization, resolution)
            except Exception as e:
                send_notification(f'S1 RTC: scene {i} read failed: {e}',
                                  level='warn', notif_id=self._notif_id)
                continue
            if not sub or not sub.get('bands'):
                continue
            if shape is None:
                shape = sub['shape']
                transform = sub['transform']
                crs = sub['crs']
            for pol, arr in sub['bands'].items():
                # Crop / pad to first scene's shape to keep the stack rectangular.
                if arr.shape != shape:
                    h, w = shape
                    cropped = np.full((h, w), np.nan, dtype=np.float32)
                    hh, ww = min(arr.shape[0], h), min(arr.shape[1], w)
                    cropped[:hh, :ww] = arr[:hh, :ww]
                    arr = cropped
                stacks.setdefault(pol, []).append(arr)
            scene_dates.append(str(item.datetime)[:10])
            if (i + 1) % 5 == 0:
                send_notification(
                    f'S1 RTC: read {i + 1}/{len(items)} scenes',
                    progress=0.25 + 0.5 * (i + 1) / len(items),
                    notif_id=self._notif_id,
                )

        if not stacks:
            send_notification('S1 RTC: all scenes empty for bbox',
                              level='error', notif_id=self._notif_id)
            return {'preview': _info_panel(
                ['All scenes returned empty windows for bbox.'],
                title='S1 RTC — empty')}

        # ── Composite ────────────────────────────────────────────────────────
        comp_opts = ['median', 'mean', 'first', 'min', 'max']
        composite = comp_opts[int(params.get('composite', 0))]
        to_db = bool(params.get('to_db', True))

        out_bands: dict[str, np.ndarray] = {}
        for pol, stack in stacks.items():
            band = _composite(stack, composite)
            if to_db:
                with np.errstate(divide='ignore', invalid='ignore'):
                    band = 10.0 * np.log10(band)
            out_bands[pol] = band.astype(np.float32)

        # VV/VH ratio (computed before dB if both present) — added regardless of to_db
        if 'vv' in out_bands and 'vh' in out_bands:
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio = (out_bands['vv'] - out_bands['vh']) if to_db else (
                    out_bands['vv'] / np.where(out_bands['vh'] > 0, out_bands['vh'], np.nan))
            out_bands['vv_vh_ratio'] = ratio.astype(np.float32)

        # ── Write GeoTIFF ────────────────────────────────────────────────────
        import rasterio
        band_order = [b for b in ('vv', 'vh', 'vv_vh_ratio') if b in out_bands]
        arr = np.stack([out_bands[b] for b in band_order], axis=0)
        H, W = arr.shape[1], arr.shape[2]

        meta_tags = {
            'band_names': ','.join(band_order),
            'composite': composite,
            'polarization': polarization,
            'orbit': orbit,
            'to_db': str(to_db),
            'n_scenes': str(len(scene_dates)),
            'date_start': scene_dates[0] if scene_dates else date_start,
            'date_end': scene_dates[-1] if scene_dates else date_end,
            'resolution_m': str(resolution),
        }

        send_notification('S1 RTC: writing GeoTIFF…', progress=0.85, notif_id=self._notif_id)
        with rasterio.open(
            cache_file, 'w',
            driver='GTiff',
            height=H, width=W, count=arr.shape[0],
            dtype='float32',
            crs=crs, transform=transform,
            compress='deflate', predictor=2, nodata=float('nan'),
        ) as dst:
            dst.write(arr)
            for i, name in enumerate(band_order, start=1):
                dst.set_band_description(i, name)
            dst.update_tags(**meta_tags)

        self._result = self._build_outputs(arr, str(cache_file), meta_tags, from_cache=False)
        send_notification(
            f'S1 RTC: {len(scene_dates)} scenes → {band_order} ({H}×{W})',
            progress=1.0, notif_id=self._notif_id,
        )
        return self._result

    # ── Output builder (shared cache hit / fresh fetch) ──────────────────────
    def _build_outputs(self, arr: np.ndarray, path: str, meta_tags: dict,
                       from_cache: bool) -> dict:
        band_names = meta_tags.get('band_names', '').split(',')
        # Preview: false-color RGB (R=VV, G=VH, B=ratio)
        preview = self._make_preview(arr, band_names)

        # Compose the standard VNStudio geotiff dict (mirrors geo_copernicus output)
        geotiff = {
            'path': path,
            'array': arr,
            'band_names': band_names,
            'transform': None,   # consumers re-open via rasterio if needed
            'crs': None,
            'meta': meta_tags,
        }
        return {
            'geotiff': geotiff,
            'preview': preview,
            'meta': {
                'source': 'sentinel-1-rtc (Planetary Computer)',
                'cached': from_cache,
                'path': path,
                **meta_tags,
            },
        }

    @staticmethod
    def _make_preview(arr: np.ndarray, band_names: list[str]) -> np.ndarray:
        """RGB false color: R=VV, G=VH, B=ratio (or VV again if no ratio)."""
        def grab(name: str) -> np.ndarray:
            if name in band_names:
                return arr[band_names.index(name)]
            return arr[0]

        r = _stretch_to_uint8(grab('vv'))
        g = _stretch_to_uint8(grab('vh'))
        b = _stretch_to_uint8(grab('vv_vh_ratio')) if 'vv_vh_ratio' in band_names \
            else _stretch_to_uint8(grab('vv'))

        rgb = np.stack([b, g, r], axis=-1)   # OpenCV uses BGR for cv2.imwrite/imshow
        # Resize to a sensible preview size if huge
        max_dim = 720
        h, w = rgb.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_AREA)
        return rgb
