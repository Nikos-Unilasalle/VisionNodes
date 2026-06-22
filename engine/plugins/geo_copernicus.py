"""
geo_copernicus.py — Copernicus Data Space Ecosystem (CDSE) satellite imagery downloader.

Credentials: Client ID + Secret from https://shapps.dataspace.copernicus.eu/
Stored in ~/.vnstudio/secrets.json (same as GEE).

Tiling: large areas are split into tiles, downloaded in sequence, stitched.
Cache:  each request is cached as a local GeoTIFF (MD5 key on all params).
"""
import os
import sys
import json
import math
import hashlib
import threading
import base64
import tempfile
import contextlib
import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification, is_cancelled, clear_cancel, _notification_queue

_NOTIF = 'copernicus'
_SECRETS_PATH = os.path.expanduser('~/.vnstudio/secrets.json')
_CDSE_BASE_URL = 'https://sh.dataspace.copernicus.eu'
_CDSE_TOKEN_URL = (
    'https://identity.dataspace.copernicus.eu'
    '/auth/realms/CDSE/protocol/openid-connect/token'
)

# ── Collection definitions ────────────────────────────────────────────────────

COLLECTIONS: dict[str, dict] = {
    # ── SentinelHub backend (CDSE OAuth) ───────────────────────────────────
    'Sentinel-2 L2A': {
        'backend':      'sh',
        'sh_id':        'SENTINEL2_L2A',
        'all_bands':    ['B01','B02','B03','B04','B05','B06','B07',
                         'B08','B8A','B09','B11','B12','SCL'],
        'default_bands':['B04','B03','B02','B08'],
        'rgb':          ['B04','B03','B02'],
        'units':        'REFLECTANCE',
        'has_cloud_filter': True,
    },
    'Sentinel-2 L1C': {
        'backend':      'sh',
        'sh_id':        'SENTINEL2_L1C',
        'all_bands':    ['B01','B02','B03','B04','B05','B06','B07',
                         'B08','B8A','B09','B10','B11','B12'],
        'default_bands':['B04','B03','B02','B08'],
        'rgb':          ['B04','B03','B02'],
        'units':        'REFLECTANCE',
        'has_cloud_filter': True,
    },
    'Sentinel-1 GRD': {
        'backend':          'sh',
        'sh_id':            'SENTINEL1_IW',
        'all_bands':        ['VV', 'VH'],
        'default_bands':    ['VV', 'VH'],
        'rgb':              ['VV', 'VH', 'VV'],
        'units':            'LINEAR_POWER',  # SH rejects 'DB' as input unit
        'to_db':            True,            # convert to dB inside evalscript
        'has_cloud_filter': False,
        'mosaicking_order': 'mostRecent',    # leastCC unsupported for SAR
    },
    'Copernicus DEM GLO-30': {
        'backend':      'sh',
        'sh_id':        'DEM_COPERNICUS_30',
        'all_bands':    ['DEM'],
        'default_bands':['DEM'],
        'rgb':          ['DEM'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'Copernicus DEM GLO-90': {
        'backend':      'sh',
        'sh_id':        'DEM_COPERNICUS_90',
        'all_bands':    ['DEM'],
        'default_bands':['DEM'],
        'rgb':          ['DEM'],
        'units':        None,
        'has_cloud_filter': False,
    },
    # ── Microsoft Planetary Computer STAC backend (no auth) ───────────────
    'Sentinel-1 RTC (Planetary)': {
        'backend':      'stac',
        'stac_id':      'sentinel-1-rtc',
        'all_bands':    ['vv', 'vh', 'vv_vh_ratio'],
        'default_bands':['vv', 'vh', 'vv_vh_ratio'],
        'rgb':          ['vv', 'vh', 'vv_vh_ratio'],
        'units':        'DB',
        'has_cloud_filter': False,
        'asset_keys':   ['vv', 'vh'],          # STAC asset names
        'categorical':  False,
    },
    'ESA WorldCover (10m)': {
        'backend':      'stac',
        'stac_id':      'esa-worldcover',
        'all_bands':    ['lulc_class'],
        'default_bands':['lulc_class'],
        'rgb':          ['lulc_class'],
        'units':        None,
        'has_cloud_filter': False,
        'asset_keys':   ['map'],
        'categorical':  True,
        'class_palette':'worldcover',
        'ignore_date':  True,   # static product — only 2020/2021 on Planetary Computer
    },
    'io-lulc Annual': {
        'backend':      'stac',
        'stac_id':      'io-lulc-annual-v02',
        'all_bands':    ['lulc_class'],
        'default_bands':['lulc_class'],
        'rgb':          ['lulc_class'],
        'units':        None,
        'has_cloud_filter': False,
        'asset_keys':   ['data'],
        'categorical':  True,
        'class_palette':'io_lulc',
        'ignore_date':  True,   # covers 2017–2022 only — ignore user date range
    },
    # ── Free Planetary Computer collections (no auth, no processing units) ──
    'Sentinel-2 L2A (Planetary)': {
        'backend':      'stac',
        'stac_id':      'sentinel-2-l2a',
        'all_bands':    ['B01','B02','B03','B04','B05','B06','B07',
                         'B08','B8A','B09','B11','B12','SCL'],
        'default_bands':['B04','B03','B02','B08'],
        'rgb':          ['B04','B03','B02'],
        'units':        'REFLECTANCE',
        'has_cloud_filter': True,
        'asset_keys':   ['B04','B03','B02','B08','B11'],  # incl. SWIR for BSI/MNDWI/turbidity
        'categorical':  False,
    },
    'Copernicus DEM GLO-30 (Planetary)': {
        'backend':      'stac',
        'stac_id':      'cop-dem-glo-30',
        'all_bands':    ['data'],
        'default_bands':['data'],
        'rgb':          ['data'],
        'units':        None,
        'has_cloud_filter': False,
        'asset_keys':   ['data'],
        'categorical':  False,
        'ignore_date':  True,   # static product — no datetime filtering
    },
    'JRC Global Surface Water': {
        'backend':      'stac',
        'stac_id':      'jrc-gsw',
        'all_bands':    ['occurrence','seasonality','extent','transition','change','recurrence'],
        'default_bands':['occurrence'],
        'rgb':          ['occurrence'],
        'units':        None,
        'has_cloud_filter': False,
        'asset_keys':   ['occurrence'],
        'categorical':  False,
        'ignore_date':  True,   # static product — take latest item regardless of date
    },
    'Google Satellite': {
        'backend':      'basemap',
        'url_template': 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'Google Hybrid': {
        'backend':      'basemap',
        'url_template': 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'Google Roadmap': {
        'backend':      'basemap',
        'url_template': 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'Google Terrain': {
        'backend':      'basemap',
        'url_template': 'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'OpenStreetMap': {
        'backend':      'basemap',
        'url_template': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'Carto Positron': {
        'backend':      'basemap',
        'url_template': 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
    'Carto Dark Matter': {
        'backend':      'basemap',
        'url_template': 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'all_bands':    ['R', 'G', 'B'],
        'default_bands':['R', 'G', 'B'],
        'rgb':          ['R', 'G', 'B'],
        'units':        None,
        'has_cloud_filter': False,
    },
}


# ── STAC class palettes (BGR) for categorical previews ─────────────────────
_WORLDCOVER_PALETTE = {
    10: (0, 100, 0),       20: (34, 187, 255),    30: (76, 255, 255),
    40: (255, 150, 240),   50: (0, 0, 250),       60: (180, 180, 180),
    70: (240, 240, 240),   80: (200, 100, 0),     90: (160, 150, 0),
    95: (117, 207, 0),     100:(160, 230, 250),
}

_IO_LULC_PALETTE = {
    1:  (171, 91, 26),    2:  (33, 130, 53),    4:  (174, 196, 123),
    5:  (92, 219, 255),   7:  (30, 30, 194),    8:  (75, 113, 149),
    9:  (245, 245, 245),  10: (220, 200, 200),  11: (79, 175, 177),
}

_CLASS_PALETTES = {
    'worldcover': _WORLDCOVER_PALETTE,
    'io_lulc':    _IO_LULC_PALETTE,
}

# ── Node definition ───────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_copernicus',
    label='Copernicus CDSE',
    category='geography',
    icon='Satellite',
    description=(
        "Download satellite imagery from the Copernicus Data Space Ecosystem (CDSE). "
        "Sentinel-2 L2A/L1C, Sentinel-1 GRD, Copernicus DEM GLO-30/90 (elevation). "
        "Draw your area of interest in the map editor (hover → Open Editor). "
        "Credentials: Client ID + Secret from shapps.dataspace.copernicus.eu."
    ),
    inputs=[
        {'id': 'bbox',       'color': 'string', 'label': 'BBox (str)'},
        {'id': 'date_start', 'color': 'string', 'label': 'Start Date'},
        {'id': 'date_end',   'color': 'string', 'label': 'End Date'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview RGB'},
        {'id': 'meta',    'color': 'dict',     'label': 'Meta'},
    ],
    params=[
        {'id': 'client_id',     'type': 'string', 'default': '', 'label': 'Client ID (CDSE)'},
        {'id': 'client_secret', 'type': 'string', 'default': '', 'label': 'Client Secret'},
        {'id': '_sec_query', 'label': 'Query', 'type': 'section'},
        {'id': 'collection',    'type': 'enum',   'options': list(COLLECTIONS.keys()), 'default': 0, 'label': 'Collection'},
        {'id': 'date_start',    'type': 'string', 'default': '2024-01-01', 'label': 'Start Date'},
        {'id': 'date_end',      'type': 'string', 'default': '2024-06-01', 'label': 'End Date'},
        {'id': 'cloud_max',     'type': 'int',    'default': 20, 'min': 0, 'max': 100, 'label': 'Max Clouds % (SIMPLE only)'},
        {'id': 'mosaic_mode',   'type': 'enum',   'default': 0,
         'options': ['SIMPLE', 'CLOUD_FREE'],
         'label': 'Mosaic mode'},
        {'id': 'resolution',    'type': 'int',    'default': 10, 'min': 1, 'max': 1000, 'label': 'Resolution (m/px)'},
        {'id': 'bands',         'type': 'string', 'default': 'B04,B03,B02,B08', 'label': 'Bands (set via editor)'},
        {'id': 'bbox',          'type': 'string', 'default': '', 'label': 'Bounding Box (set via editor)'},
        {'id': '_sec_download', 'label': 'Download', 'type': 'section'},
        {'id': 'max_tile_px',   'type': 'int',    'default': 2500, 'min': 256, 'max': 5000, 'label': 'Max tile size (px)'},
        {'id': 'cache_dir',     'type': 'string', 'default': 'copernicus_cache', 'label': 'Cache Dir'},

        # ── STAC-only parameters (ignored for SentinelHub collections) ────
        {'id': '_sec_stac', 'label': 'STAC Options', 'type': 'section'},
        {'id': 'stac_polarization', 'type': 'enum', 'options': ['Both', 'VV', 'VH'],
         'default': 0, 'label': 'STAC: Polarization (S1-RTC)'},
        {'id': 'stac_orbit',        'type': 'enum', 'options': ['Any', 'Ascending', 'Descending'],
         'default': 0, 'label': 'STAC: Orbit (S1-RTC)'},
        {'id': 'stac_composite',    'type': 'enum',
         'options': ['median', 'mean', 'first', 'min', 'max'],
         'default': 0, 'label': 'STAC: Composite Method'},
        {'id': 'stac_to_db',        'type': 'bool', 'default': True,
         'label': 'STAC: SAR → dB (10·log10)'},
        {'id': 'stac_max_scenes',   'type': 'int',  'default': 12, 'min': 1, 'max': 500,
         'label': 'STAC: Max scenes for composite (8-12 typical, more = slower)'},
        {'id': 'stac_scene_timeout', 'type': 'int', 'default': 90, 'min': 10, 'max': 600,
         'label': 'STAC: Scene read timeout (s) — bump to 120+ for large AOI'},
        {'id': 'stac_min_ok',       'type': 'int',  'default': 3,  'min': 1, 'max': 100,
         'label': 'STAC: Min scenes OK to accept result (else retry)'},

        {'id': '_sec_control', 'label': 'Control', 'type': 'section'},
        {'id': 'fetch',         'type': 'trigger','default': 0,  'label': 'Fetch'},
    ],
    resizable=True, min_width=280, min_height=200,
)
class GeoCopernicusNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._prev_fetch      = 0
        self._loading         = False
        self._cache_data      = None   # (geo_dict, preview_bgr, thumb_b64)
        self._thumb_dirty     = False
        self._auto_tried      = False
        self._prev_dl_key     = None   # hash of download-relevant params
        self._generation      = 0      # bumped on every Fetch — older threads' writes ignored
        self._stop_event      = threading.Event()  # politely signal in-flight thread to stop
        # per-instance notif id so multiple Copernicus nodes don't share notifications
        self._notif_id        = f'copernicus_{id(self)}'

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _load_secrets() -> dict:
        try:
            if os.path.exists(_SECRETS_PATH):
                with open(_SECRETS_PATH) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @staticmethod
    def _save_secrets(data: dict) -> None:
        os.makedirs(os.path.dirname(_SECRETS_PATH), exist_ok=True)
        try:
            existing = GeoCopernicusNode._load_secrets()
            existing.update(data)
            with open(_SECRETS_PATH, 'w') as f:
                json.dump(existing, f)
        except Exception:
            pass

    @staticmethod
    def _stretch(band: np.ndarray) -> np.ndarray:
        valid = band[np.isfinite(band) & (band != 0)]
        if valid.size == 0:
            return np.zeros_like(band, dtype=np.uint8)
        p2, p98 = np.percentile(valid, (2, 98))
        if p98 == p2:
            return np.full_like(band, 128, dtype=np.uint8)
        return np.clip((band - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)

    @staticmethod
    def _make_evalscript(bands: list[str], units: str | None,
                         to_db: bool = False) -> str:
        band_json   = json.dumps(bands)
        n           = len(bands)
        if to_db:
            # SAR: convert linear power → dB, clamped at -30 dB floor to avoid -Inf
            sample_vals = ', '.join(
                f'(10.0 * Math.log(Math.max(sample.{b}, 1e-10)) / Math.LN10)'
                for b in bands
            )
        else:
            sample_vals = ', '.join(f'sample.{b}' for b in bands)
        if units:
            input_spec = f'{{bands: {band_json}, units: "{units}"}}'
        else:
            input_spec = f'{{bands: {band_json}}}'
        return (
            f'//VERSION=3\n'
            f'function setup() {{\n'
            f'  return {{input: [{input_spec}], output: {{bands: {n}, sampleType: "FLOAT32"}}}};\n'
            f'}}\n'
            f'function evaluatePixel(sample) {{\n'
            f'  return [{sample_vals}];\n'
            f'}}\n'
        )

    @staticmethod
    def _make_evalscript_cloud_free(bands: list[str], units: str | None) -> str:
        """ORBIT mosaicking evalscript: iterates all acquisitions, returns first
        cloud-free pixel based on SCL.

        SCL only supports DN units — it must be in a SEPARATE input entry from
        spectral bands that use REFLECTANCE.  Both entries are merged by the API
        into a single `samples` object, so s.SCL and s.B04 are both accessible.
        """
        out_bands   = [b for b in bands if b != 'SCL']
        n_out       = len(out_bands)
        # SCL only supports DN — cannot mix units in a single input entry.
        # Solution: request ALL bands (spectral + SCL) without units → DN for everything.
        # NDVI / MNDWI are ratios → scale-invariant, DN gives identical index values.
        all_input   = out_bands + (['SCL'] if 'SCL' not in bands else [])
        input_json  = json.dumps(all_input)
        sample_vals = ', '.join(f's.{b}' for b in out_bands)

        return (
            f'//VERSION=3\n'
            f'function setup() {{\n'
            f'  return {{\n'
            f'    input: [{{bands: {input_json}}}],\n'
            f'    output: {{bands: {n_out}, sampleType: "FLOAT32"}},\n'
            f'    mosaicking: "ORBIT"\n'
            f'  }};\n'
            f'}}\n'
            f'function evaluatePixel(samples) {{\n'
            f'  var BAD = [0,1,3,8,9,10,11];\n'
            f'  for (var i = 0; i < samples.length; i++) {{\n'
            f'    var s = samples[i];\n'
            f'    if (BAD.indexOf(Math.round(s.SCL)) === -1) {{\n'
            f'      return [{sample_vals}];\n'
            f'    }}\n'
            f'  }}\n'
            f'  return new Array({n_out}).fill(0.0);\n'
            f'}}\n'
        )

    @staticmethod
    def _cache_key(col_name: str, bbox: tuple, date_start: str, date_end: str,
                   bands: list[str], resolution: int,
                   tile_row: int, tile_col: int,
                   mosaic_mode: str = 'SIMPLE') -> str:
        s = (f'{col_name}|{bbox}|{date_start}|{date_end}|{"-".join(bands)}'
             f'|{resolution}|{tile_row}|{tile_col}|{mosaic_mode}')
        return hashlib.md5(s.encode()).hexdigest()[:14]

    # ── Tile download ─────────────────────────────────────────────────────────

    def _download_tile(
        self, sh_config, data_collection, evalscript: str,
        west: float, south: float, east: float, north: float,
        width: int, height: int,
        date_start: str, date_end: str,
        cloud_max: int, has_cloud: bool,
        tile_path: str,
        notif_id: str = _NOTIF,
        mosaic_mode: str = 'SIMPLE',
        mosaicking_order: str = 'leastCC',
    ) -> bool:
        """Download one tile to tile_path as float32 GeoTIFF. Returns True on success."""
        try:
            from sentinelhub import (
                BBox, CRS, SentinelHubRequest, MimeType
            )
            import rasterio
            from rasterio.transform import from_bounds

            bbox = BBox([west, south, east, north], crs=CRS.WGS84)

            cloud_free = (mosaic_mode == 'CLOUD_FREE')

            # leastCC (least cloud cover) is only valid for optical collections.
            # SAR (S1) and DEM have no cloud metadata → SentinelHub rejects leastCC.
            safe_order = mosaicking_order
            if not has_cloud and safe_order == 'leastCC':
                safe_order = 'mostRecent'

            input_data_kwargs: dict = {
                'data_collection': data_collection,
                'time_interval':   (date_start, date_end),
                'mosaicking_order': safe_order,
            }
            # For SIMPLE mode, apply cloud cover pre-filter to restrict API search.
            # For CLOUD_FREE mode, allow all acquisitions through (per-pixel SCL filter handles it).
            if has_cloud and not cloud_free:
                input_data_kwargs['other_args'] = {'dataFilter': {'maxCloudCoverage': cloud_max}}

            request = SentinelHubRequest(
                evalscript=evalscript,
                input_data=[SentinelHubRequest.input_data(**input_data_kwargs)],
                responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
                bbox=bbox,
                size=(width, height),
                config=sh_config,
            )

            result = request.get_data()
            if not result:
                send_notification('Copernicus: empty response from API', level='warning', notif_id=notif_id)
                return False

            arr = result[0]   # (H, W, N_bands) float32
            if arr.ndim == 2:
                arr = arr[:, :, np.newaxis]
            n_bands = arr.shape[2]

            transform = from_bounds(west, south, east, north, width, height)
            with rasterio.open(
                tile_path, 'w',
                driver='GTiff', compress='lzw',
                height=height, width=width,
                count=n_bands, dtype='float32',
                crs='EPSG:4326',
                transform=transform,
            ) as dst:
                for i in range(n_bands):
                    dst.write(arr[:, :, i], i + 1)

            return True

        except Exception as e:
            send_notification(f'Copernicus tile error: {e}', level='error', notif_id=notif_id)
            return False

    # ── Main fetch logic ──────────────────────────────────────────────────────

    def _do_fetch(self, params: dict, auto: bool = False, my_gen: int = 0) -> None:
        self._stop_event.clear()
        try:
            self._do_fetch_impl(params, auto=auto, my_gen=my_gen)
        except BaseException as e:
            if self._generation == my_gen:
                send_notification(f'Copernicus: unexpected crash: {e}', level='error', notif_id=self._notif_id)
        finally:
            # Only clear loading flag if WE are still the latest fetch.
            # If a newer Fetch has bumped _generation, leave _loading alone — the new thread owns it.
            if self._generation == my_gen:
                self._loading = False

    def _do_fetch_impl(self, params: dict, auto: bool = False, my_gen: int = 0) -> None:
        # ── Dispatch by collection backend ─────────────────────────────────────
        col_names   = list(COLLECTIONS.keys())
        col_idx     = int(params.get('collection', 0))
        col_name    = col_names[col_idx] if 0 <= col_idx < len(col_names) else col_names[0]
        col_cfg     = COLLECTIONS[col_name]
        backend     = col_cfg.get('backend', 'sh')

        if backend == 'stac':
            self._do_fetch_stac(params, col_name, col_cfg, auto=auto, my_gen=my_gen)
            return

        if backend == 'basemap':
            self._do_fetch_basemap(params, col_name, col_cfg, auto=auto, my_gen=my_gen)
            return

        if not self.ensure_packages(
            ['sentinelhub', 'rasterio'],
            pip_names=['sentinelhub', 'rasterio'],
            notif_id=self._notif_id,
        ):
            return

        from sentinelhub import SHConfig, DataCollection
        import rasterio
        from rasterio.merge import merge as rasterio_merge

        # ── Credentials ────────────────────────────────────────────────────────
        client_id     = str(params.get('client_id',     '') or '').strip()
        client_secret = str(params.get('client_secret', '') or '').strip()
        secrets       = self._load_secrets()

        if client_id:
            secrets['copernicus_client_id']     = client_id
            self._save_secrets({'copernicus_client_id': client_id,
                                'copernicus_client_secret': client_secret})
        else:
            client_id     = secrets.get('copernicus_client_id',     '')
            client_secret = secrets.get('copernicus_client_secret', '')

        if not client_id or not client_secret:
            send_notification(
                'Copernicus: missing credentials — enter Client ID and Client Secret',
                level='error', notif_id=self._notif_id,
            )
            return

        # ── Parameters ─────────────────────────────────────────────────────────
        bbox_str    = str(params.get('bbox', '') or '').strip()
        if not bbox_str:
            send_notification('Copernicus: no bounding box — open editor to draw ROI',
                              level='warning', notif_id=self._notif_id)
            return

        try:
            parts = [float(v) for v in bbox_str.split(',')]
            if len(parts) != 4:
                raise ValueError('need 4 values')
            west, south, east, north = parts
        except Exception:
            send_notification(f'Copernicus: invalid bbox "{bbox_str}"',
                              level='error', notif_id=self._notif_id)
            return

        date_start  = str(params.get('date_start', '2024-01-01'))
        date_end    = str(params.get('date_end',   '2024-06-01'))
        cloud_max   = int(params.get('cloud_max',  20))
        resolution  = max(1, int(params.get('resolution', 10)))
        max_tile_px = max(256, int(params.get('max_tile_px', 2500)))

        bands_str = str(params.get('bands', '') or '').strip()
        if bands_str:
            bands = [b.strip() for b in bands_str.split(',') if b.strip()]
        else:
            bands = col_cfg['default_bands']
        # Validate bands against collection
        valid = col_cfg['all_bands']
        bands = [b for b in bands if b in valid] or col_cfg['default_bands']

        raw_cache = str(params.get('cache_dir', 'copernicus_cache') or 'copernicus_cache').strip()
        _engine_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir   = raw_cache if os.path.isabs(raw_cache) else os.path.join(_engine_dir, raw_cache)
        os.makedirs(cache_dir, exist_ok=True)

        # ── Mosaic mode (parsed early — used by cache key below) ─────────────
        _mosaic_opts = ['SIMPLE', 'CLOUD_FREE']
        try:
            mosaic_mode = _mosaic_opts[int(params.get('mosaic_mode', 0))]
        except (ValueError, TypeError, IndexError):
            mosaic_mode = 'SIMPLE'
        if 'SCL' in bands and len(bands) == 1:
            mosaic_mode = 'SIMPLE'

        # Clear any leftover cancel flag from a previous operation
        clear_cancel(self._notif_id)

        if auto:
            # On auto-restore, only continue if a matching cache file can be found
            test_key = self._cache_key(col_name, (west, south, east, north),
                                       date_start, date_end, bands, resolution, 0, 0,
                                       mosaic_mode)
            test_path = os.path.join(cache_dir, f'{test_key}.tif')
            if not os.path.exists(test_path):
                return   # nothing cached — skip to avoid triggering auth on startup

        # ── SentinelHub config ────────────────────────────────────────────────
        sh_config = SHConfig()
        sh_config.sh_client_id     = client_id
        sh_config.sh_client_secret = client_secret
        sh_config.sh_base_url      = _CDSE_BASE_URL
        sh_config.sh_token_url     = _CDSE_TOKEN_URL

        # ── DataCollection ────────────────────────────────────────────────────
        sh_id = col_cfg['sh_id']
        try:
            base_col = getattr(DataCollection, sh_id)
            data_collection = base_col.define_from(
                f'{sh_id}_CDSE',
                service_url=_CDSE_BASE_URL,
            )
        except AttributeError:
            send_notification(
                f'Copernicus: unknown DataCollection "{sh_id}" — update sentinelhub library',
                level='error', notif_id=self._notif_id,
            )
            return

        # SCL has no reflectance units — drop units spec if SCL is in the band list
        units = None if 'SCL' in bands else col_cfg.get('units')

        if mosaic_mode == 'CLOUD_FREE' and col_cfg.get('has_cloud_filter'):
            evalscript = self._make_evalscript_cloud_free(bands, units)
        else:
            mosaic_mode = 'SIMPLE'
            evalscript  = self._make_evalscript(bands, units, to_db=col_cfg.get('to_db', False))

        # ── Compute grid ──────────────────────────────────────────────────────
        lat_c       = (south + north) / 2
        width_m     = abs(east - west) * 111320.0 * math.cos(math.radians(lat_c))
        height_m    = abs(north - south) * 111320.0
        total_w     = max(1, round(width_m  / resolution))
        total_h     = max(1, round(height_m / resolution))

        tile_cols   = max(1, math.ceil(total_w / max_tile_px))
        tile_rows   = max(1, math.ceil(total_h / max_tile_px))
        n_tiles     = tile_cols * tile_rows

        send_notification(
            f'Copernicus: {col_name} · {total_w}×{total_h} px '
            f'({tile_cols}×{tile_rows} tile{"s" if n_tiles > 1 else ""}) · '
            f'bands: {", ".join(bands)} · {mosaic_mode}',
            progress=0.05, notif_id=self._notif_id,
        )

        lon_step = (east - west) / tile_cols
        lat_step = (north - south) / tile_rows
        tile_w   = max(1, round(total_w / tile_cols))
        tile_h   = max(1, round(total_h / tile_rows))

        tile_paths: list[tuple[int, int, str]] = []  # (row, col, path)
        all_cached = True

        for row in range(tile_rows):
            for col in range(tile_cols):
                t_west  = west  + col * lon_step
                t_east  = west  + (col + 1) * lon_step
                t_south = south + row * lat_step
                t_north = south + (row + 1) * lat_step

                key       = self._cache_key(col_name, (west, south, east, north),
                                            date_start, date_end, bands, resolution, row, col,
                                            mosaic_mode)
                tile_path = os.path.join(cache_dir, f'{key}.tif')
                tile_paths.append((row, col, tile_path))

                if os.path.exists(tile_path):
                    continue

                all_cached = False
                if auto:
                    return  # don't trigger auth on auto-restore

                # Check cancellation before each tile download
                if (is_cancelled(self._notif_id) or self._stop_event.is_set()
                        or self._generation != my_gen):
                    send_notification('Copernicus: download cancelled', level='warning', notif_id=self._notif_id)
                    return

                tile_num = row * tile_cols + col + 1
                send_notification(
                    f'Copernicus: downloading tile {tile_num}/{n_tiles} '
                    f'({col+1},{row+1})…',
                    progress=0.10 + 0.75 * (tile_num - 1) / n_tiles,
                    notif_id=self._notif_id,
                )

                success = self._download_tile(
                    sh_config, data_collection, evalscript,
                    t_west, t_south, t_east, t_north,
                    tile_w, tile_h,
                    date_start, date_end,
                    cloud_max, col_cfg['has_cloud_filter'],
                    tile_path,
                    notif_id=self._notif_id,
                    mosaic_mode=mosaic_mode,
                    mosaicking_order=col_cfg.get('mosaicking_order', 'leastCC'),
                )
                if not success:
                    return

        if all_cached:
            send_notification('Copernicus: all tiles cached', progress=0.85, notif_id=self._notif_id)

        # ── Stitch tiles ──────────────────────────────────────────────────────
        if n_tiles == 1:
            final_path = tile_paths[0][2]
        else:
            send_notification('Copernicus: stitching tiles…', progress=0.87, notif_id=self._notif_id)
            stitch_key = hashlib.md5(
                f'{col_name}|{west},{south},{east},{north}|{date_start}|{date_end}|'
                f'{"-".join(bands)}|{resolution}|mosaic'.encode()
            ).hexdigest()[:14]
            final_path = os.path.join(cache_dir, f'{stitch_key}_mosaic.tif')

            if not os.path.exists(final_path):
                try:
                    with contextlib.ExitStack() as stack:
                        # Order: bottom-to-top rows (south first), left-to-right cols
                        paths_ordered = [
                            p for r, c, p in sorted(tile_paths, key=lambda t: (t[0], t[1]))
                            if os.path.exists(p)
                        ]
                        srcs = [stack.enter_context(rasterio.open(p)) for p in paths_ordered]
                        mosaic, transform = rasterio_merge(srcs)
                        profile = srcs[0].profile.copy()
                        profile.update({
                            'height': mosaic.shape[1],
                            'width':  mosaic.shape[2],
                            'transform': transform,
                        })
                        with rasterio.open(final_path, 'w', **profile) as dst:
                            dst.write(mosaic)
                except Exception as e:
                    send_notification(f'Copernicus: stitch error: {e}', level='error', notif_id=self._notif_id)
                    return

        # ── Load final GeoTIFF ────────────────────────────────────────────────
        send_notification('Copernicus: loading result…', progress=0.92, notif_id=self._notif_id)
        try:
            with rasterio.open(final_path) as src:
                band_arr = src.read().astype(np.float32)
                if src.nodata is not None:
                    band_arr[band_arr == src.nodata] = np.nan
                geo: dict = {
                    'bands':       band_arr,
                    'band_names':  bands[:src.count],
                    'count':       src.count,
                    'width':       src.width,
                    'height':      src.height,
                    'crs':         str(src.crs) if src.crs else None,
                    'transform':   src.transform,
                    'nodata':      src.nodata,
                    'dtype':       str(src.dtypes[0]),
                    'bounds': {
                        'west':  src.bounds.left,
                        'south': src.bounds.bottom,
                        'east':  src.bounds.right,
                        'north': src.bounds.top,
                    },
                    '_source':     col_name,
                    '_bands':      bands,
                    '_dates':      f'{date_start} → {date_end}',
                    '_cache_path': final_path,
                }
        except Exception as e:
            send_notification(f'Copernicus: load error: {e}', level='error', notif_id=self._notif_id)
            return

        # ── Build preview (RGB true color) ────────────────────────────────────
        rgb_def = col_cfg['rgb']
        count   = geo['count']
        bn      = geo['band_names']

        if len(rgb_def) == 3 and all(b in bn for b in rgb_def):
            ri, gi, bi_idx = bn.index(rgb_def[0]), bn.index(rgb_def[1]), bn.index(rgb_def[2])
        elif len(rgb_def) == 1:
            ri = gi = bi_idx = 0
        else:
            ri, gi, bi_idx = min(0, count-1), min(1, count-1), min(2, count-1)

        r_ch = np.nan_to_num(band_arr[ri])
        g_ch = np.nan_to_num(band_arr[gi])
        b_ch = np.nan_to_num(band_arr[bi_idx])
        preview = cv2.merge([self._stretch(b_ch), self._stretch(g_ch), self._stretch(r_ch)])

        h, w = preview.shape[:2]
        sc   = min(1.0, 120 / h)
        thumb = cv2.resize(preview, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        if self._generation != my_gen:
            return  # superseded by newer Fetch — discard results
        self._cache_data  = (geo, preview, thumb_b64)
        self._thumb_dirty = True
        send_notification(
            f'Copernicus: ready — {geo["count"]} bands, {geo["width"]}×{geo["height"]} px',
            progress=1.0, notif_id=self._notif_id,
        )
        # Wake static-graph engine, bust cache for this node type, so process() delivers results
        _notification_queue.put_nowait({'_wake_engine': True, '_node_type': 'geo_copernicus', '_notif_id': self._notif_id})

    # ── STAC backend (Microsoft Planetary Computer, no auth) ──────────────────

    def _do_fetch_stac(self, params: dict, col_name: str, col_cfg: dict,
                       auto: bool = False, my_gen: int = 0) -> None:
        """STAC fetch path for collections backed by Microsoft Planetary Computer.

        Reads the AOI via STAC + COG window reads (no SH OAuth), composites
        multiple scenes into a single multi-band raster, then writes the same
        `_cache_data` triple that the SH path produces, so `process()` returns
        an identical contract to downstream nodes.
        """
        if not self.ensure_packages(
            ['rasterio', 'pystac_client', 'planetary_computer', 'odc.stac'],
            pip_names=['rasterio', 'pystac-client', 'planetary-computer', 'odc-stac'],
            notif_id=self._notif_id,
        ):
            return

        import pystac_client
        import planetary_computer
        import rasterio
        import odc.stac

        # GDAL config dict — applied via rasterio.Env() inside each COG read
        # (os.environ is too late: GDAL is already initialised by the time this runs)
        # Timeouts tuned for S1-RTC AOI reads (~35MB compressed / asset over HTTPS):
        # connect=15s, full transfer=120s, 3 retries with 3s delay.
        _GDAL_COG_CFG = {
            'GDAL_HTTP_TIMEOUT':                  120,
            'GDAL_HTTP_CONNECTTIMEOUT':           15,
            'GDAL_HTTP_MAX_RETRY':                3,
            'GDAL_HTTP_RETRY_DELAY':              3,
            'GDAL_HTTP_LOW_SPEED_TIME':           30,       # drop conn if <1 byte/s for 30s
            'GDAL_HTTP_LOW_SPEED_LIMIT':          1024,     # min 1 KB/s expected
            'GDAL_DISABLE_READDIR_ON_OPEN':       'EMPTY_DIR',
            'GDAL_HTTP_MERGE_CONSECUTIVE_RANGES': 'YES',   # fewer HTTP round-trips
            'GDAL_HTTP_MULTIPLEX':                'YES',   # HTTP/2 multiplexing
            'CPL_VSIL_CURL_CHUNK_SIZE':           1048576,  # 1 MB chunks (7x speedup vs 10MB)
            'GDAL_CACHEMAX':                      512,      # MB GDAL block cache
        }

        # ── BBOX ──────────────────────────────────────────────────────────────
        bbox_str = str(params.get('bbox', '') or '').strip()
        if not bbox_str:
            send_notification('Copernicus: no bounding box — open editor to draw ROI',
                              level='warning', notif_id=self._notif_id)
            return
        try:
            west, south, east, north = (float(v) for v in bbox_str.split(','))
        except Exception:
            send_notification(f'Copernicus: invalid bbox "{bbox_str}"',
                              level='error', notif_id=self._notif_id)
            return

        date_start = str(params.get('date_start', '2024-01-01'))
        date_end   = str(params.get('date_end',   '2024-12-31'))
        resolution = max(1, int(params.get('resolution', 20)))
        cloud_max  = int(params.get('cloud_max', 20))

        # STAC-only params
        pol_opts   = ['Both', 'VV', 'VH']
        polariz    = pol_opts[int(params.get('stac_polarization', 0))]
        orb_opts   = ['Any', 'Ascending', 'Descending']
        orbit      = orb_opts[int(params.get('stac_orbit', 0))]
        comp_opts     = ['median', 'mean', 'first', 'min', 'max']
        composite     = comp_opts[int(params.get('stac_composite', 0))]
        to_db         = bool(params.get('stac_to_db', True))
        max_scenes    = max(1, int(params.get('stac_max_scenes', 30)))
        scene_timeout = max(10, int(params.get('stac_scene_timeout', 60)))
        min_ok        = max(1, int(params.get('stac_min_ok', 3)))

        # ── Cache path ────────────────────────────────────────────────────────
        raw_cache = str(params.get('cache_dir', 'copernicus_cache') or 'copernicus_cache').strip()
        _engine_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir   = raw_cache if os.path.isabs(raw_cache) else os.path.join(_engine_dir, raw_cache)
        os.makedirs(cache_dir, exist_ok=True)

        sig = json.dumps({
            'col': col_name, 'bbox': [west, south, east, north],
            'd0': date_start, 'd1': date_end,
            'res': resolution, 'pol': polariz, 'orb': orbit,
            'comp': composite, 'db': to_db, 'maxs': max_scenes,
            'assets': col_cfg.get('asset_keys'),  # bust cache when band set changes
        }, sort_keys=True)
        sig_key = hashlib.md5(sig.encode()).hexdigest()[:14]
        final_path = os.path.join(cache_dir, f'stac_{sig_key}.tif')

        if auto and not os.path.exists(final_path):
            return

        # ── Cache hit: load existing GeoTIFF, skip re-download ───────────────
        if os.path.exists(final_path):
            _log_early = lambda *a: print('[STAC]', *a, file=sys.stderr, flush=True)
            _log_early(f'cache hit → {final_path}')
            try:
                import rasterio as _rio
                with _rio.open(final_path) as _src:
                    arr_c      = _src.read().astype('float32')
                    dst_crs_c  = _src.crs
                    dst_tf_c   = _src.transform
                    out_h_c, out_w_c = _src.height, _src.width
                    bnames_c   = [_src.descriptions[i] or f'band_{i+1}'
                                  for i in range(_src.count)]
                    is_cat_c   = col_cfg.get('categorical', False)
                    nodata_c   = 0 if is_cat_c else float('nan')

                geo_c: dict = {
                    'bands':       arr_c,
                    'band_names':  bnames_c,
                    'count':       arr_c.shape[0],
                    'width':       out_w_c,
                    'height':      out_h_c,
                    'crs':         dst_crs_c,
                    'transform':   dst_tf_c,
                    'nodata':      nodata_c,
                    'dtype':       'uint8' if is_cat_c else 'float32',
                    'bounds':      {'west': west, 'south': south,
                                    'east': east, 'north': north},
                    '_source':     col_name,
                    '_bands':      bnames_c,
                    '_dates':      f'{date_start} → {date_end}',
                    '_cache_path': final_path,
                }
                preview_c = self._stac_preview(arr_c, bnames_c, col_cfg)
                h_c, w_c  = preview_c.shape[:2]
                sc_c      = min(1.0, 120 / h_c)
                import cv2 as _cv2, base64 as _b64
                thumb_c   = _cv2.resize(preview_c,
                                        (max(1, int(w_c * sc_c)),
                                         max(1, int(h_c * sc_c))))
                _, buf_c  = _cv2.imencode('.jpg', thumb_c,
                                          [_cv2.IMWRITE_JPEG_QUALITY, 60])
                thumb_b64_c = _b64.b64encode(buf_c).decode('utf-8')

                if self._generation != my_gen:
                    return  # superseded
                self._cache_data  = (geo_c, preview_c, thumb_b64_c)
                self._thumb_dirty = True
                send_notification(
                    f'Copernicus[STAC]: loaded from cache — '
                    f'{arr_c.shape[0]} band(s), {out_w_c}×{out_h_c} px',
                    progress=1.0, notif_id=self._notif_id,
                )
                _notification_queue.put_nowait({
                    '_wake_engine': True, '_node_type': 'geo_copernicus',
                    '_notif_id': self._notif_id,
                })
                return
            except Exception as _e:
                _log_early(f'cache load failed ({_e}) — re-fetching from STAC')
                # fall through to full download

        import traceback as _tb, time as _time

        def _log(*args):
            print('[STAC]', *args, file=sys.stderr, flush=True)

        _log(f'=== START {col_name} ===')
        _log(f'bbox={west:.3f},{south:.3f},{east:.3f},{north:.3f}  '
             f'dates={date_start}→{date_end}  res={resolution}m  '
             f'max_scenes={max_scenes}  timeout={scene_timeout}s')
        _log(f'GDAL_COG_CFG = {_GDAL_COG_CFG}')

        # ── STAC search ───────────────────────────────────────────────────────
        _log('Opening Planetary Computer catalog…')
        try:
            catalog = pystac_client.Client.open(
                'https://planetarycomputer.microsoft.com/api/stac/v1',
                modifier=planetary_computer.sign_inplace,
            )
            _log('Catalog OK')
        except Exception as e:
            _log(f'CATALOG OPEN FAILED: {e}')
            _tb.print_exc(file=sys.stderr)
            send_notification(f'Copernicus[STAC]: catalog open failed: {e}',
                              level='error', notif_id=self._notif_id)
            return

        send_notification(f'Copernicus[STAC]: querying {col_cfg["stac_id"]}…',
                          progress=0.1, notif_id=self._notif_id)
        _log(f'Searching collection={col_cfg["stac_id"]}…')
        try:
            dt_arg = None if col_cfg.get('ignore_date') else f'{date_start}/{date_end}'
            search = catalog.search(
                collections=[col_cfg['stac_id']],
                bbox=[west, south, east, north],
                datetime=dt_arg,
                limit=500,
            )
            items = list(search.items())
            _log(f'Search returned {len(items)} items')
        except Exception as e:
            _log(f'SEARCH FAILED: {e}')
            _tb.print_exc(file=sys.stderr)
            send_notification(f'Copernicus[STAC]: search failed: {e}',
                              level='error', notif_id=self._notif_id)
            return

        # Orbit filter for S1
        if orbit.lower() in ('ascending', 'descending'):
            items = [it for it in items
                     if str(it.properties.get('sat:orbit_state', '')).lower() == orbit.lower()]
            _log(f'After orbit filter ({orbit}): {len(items)} items')
        if not items:
            _log('ERROR: 0 items after filter')
            send_notification(f'Copernicus[STAC]: 0 scenes for bbox/date/orbit',
                              level='warning', notif_id=self._notif_id)
            return

        items = sorted(items, key=lambda i: i.datetime or 0)

        # Cloud filter for STAC collections that carry eo:cloud_cover metadata (e.g. S2 PC)
        if col_cfg.get('has_cloud_filter'):
            before = len(items)
            items = [
                it for it in items
                if float(it.properties.get('eo:cloud_cover', 0)) <= cloud_max
            ]
            _log(f'Cloud filter (eo:cloud_cover <= {cloud_max}%): {before} → {len(items)} items')
            if not items:
                send_notification(
                    f'Copernicus[STAC]: 0 scenes with cloud_cover ≤ {cloud_max}% — '
                    'try a wider date range or raise Max Clouds',
                    level='warning', notif_id=self._notif_id,
                )
                return

        # For LULC: take the latest scene only (categorical, no composite).
        if col_cfg.get('categorical'):
            items = [items[-1]]
        elif len(items) > max_scenes:
            idx = np.linspace(0, len(items) - 1, max_scenes).round().astype(int)
            items = [items[i] for i in idx]

        _log(f'Will read {len(items)} scenes')
        if items:
            first = items[0]
            _log(f'  First item: id={first.id}  dt={first.datetime}  '
                 f'assets={list(first.assets.keys())}')
            if first.assets:
                first_ak = list(first.assets.keys())[0]
                _log(f'  First asset href={first.assets[first_ak].href[:80]}…')

        # Pick asset keys based on polarization for S1
        all_assets = col_cfg['asset_keys']
        if col_cfg['stac_id'] == 'sentinel-1-rtc':
            if polariz == 'VV':
                asset_keys = ['vv']
            elif polariz == 'VH':
                asset_keys = ['vh']
            else:
                asset_keys = ['vv', 'vh']
        else:
            asset_keys = all_assets
        _log(f'asset_keys={asset_keys}')

        # ── Target CRS: pick UTM zone from bbox centroid (so resolution=m is honoured) ──
        lon_c   = 0.5 * (west + east)
        lat_c   = 0.5 * (south + north)
        utm_zone = int((lon_c + 180.0) / 6.0) + 1
        utm_epsg = (32600 if lat_c >= 0 else 32700) + utm_zone
        dst_crs  = f'EPSG:{utm_epsg}'
        is_cat   = col_cfg.get('categorical', False)
        _log(f'Target CRS: {dst_crs} (UTM zone {utm_zone}{"N" if lat_c>=0 else "S"}) '
             f'@ {resolution}m')

        # ── Load all scenes in parallel via odc.stac.load ─────────────────────
        # Battle-tested: handles overview selection, parallel COG reads, reprojection.
        # `chunks=None` = eager load (full materialization in current thread).
        # We accept that .compute() can't be cancelled mid-stream — the abandonment
        # strategy (generation guard before write) handles that case correctly.
        send_notification(
            f'Copernicus[STAC]: loading {len(items)} scene(s) via odc.stac…',
            progress=0.25, notif_id=self._notif_id,
        )
        t_load = time.time() if 'time' in dir() else 0.0
        try:
            import time as _t_mod
            t_load = _t_mod.time()
            with rasterio.Env(**_GDAL_COG_CFG):
                ds = odc.stac.load(
                    items,
                    bands=asset_keys,
                    bbox=(west, south, east, north),
                    resolution=resolution,
                    crs=dst_crs,
                    chunks={'x': 2048, 'y': 2048},    # Dask lazy loading (prevents OOM on large AOIs)
                    resampling='nearest' if is_cat else 'average',
                    fail_on_error=False,
                    dtype='float32' if not is_cat else 'uint8',
                    nodata=float('nan') if not is_cat else 0,
                )
            _log(f'odc.stac.load returned in {_t_mod.time()-t_load:.1f}s  '
                 f'vars={list(ds.data_vars)}  sizes={dict(ds.sizes)}')
        except Exception as e:
            import traceback as _tb_e
            _tb_e.print_exc(file=sys.stderr)
            send_notification(
                f'Copernicus[STAC]: odc.stac.load failed: {type(e).__name__}: {e}',
                level='error', notif_id=self._notif_id,
            )
            return

        # Cancel/supersession check before composite
        if (is_cancelled(self._notif_id) or self._stop_event.is_set()
                or self._generation != my_gen):
            _log('cancelled/superseded after odc load — discarding')
            return

        # Grab the geobox for output transform + size
        gbox          = ds.odc.geobox
        out_h, out_w  = gbox.height, gbox.width
        dst_transform = gbox.affine
        # Normalize CRS to EPSG string for rasterio compatibility
        try:
            dst_crs = f'EPSG:{gbox.crs.epsg}'
        except Exception:
            dst_crs = str(gbox.crs)
        _log(f'Output grid from odc: {out_w}x{out_h}px  crs={dst_crs}  '
             f'transform={dst_transform}')

        # ── Composite across time ─────────────────────────────────────────────
        send_notification(
            f'Copernicus[STAC]: compositing ({composite}) {len(items)} scene(s)…',
            progress=0.85, notif_id=self._notif_id,
        )
        compose_fns = {
            'median': lambda da: da.median(dim='time', skipna=True),
            'mean':   lambda da: da.mean(dim='time',   skipna=True),
            'first':  lambda da: da.isel(time=0),
            'min':    lambda da: da.min(dim='time',    skipna=True),
            'max':    lambda da: da.max(dim='time',    skipna=True),
        }
        compose_fn = compose_fns.get(composite, compose_fns['median'])

        out_bands: dict[str, np.ndarray] = {}
        for ak in asset_keys:
            band = compose_fn(ds[ak]).values  # → numpy
            # Treat zeros as nodata for SAR (S1-RTC fills out-of-swath with 0)
            if not is_cat:
                band = np.where(band <= 0, np.nan, band)
                if to_db:
                    with np.errstate(divide='ignore', invalid='ignore'):
                        band = 10.0 * np.log10(band)
                band = band.astype('float32')
            else:
                band = band.astype('uint8')
            out_bands[ak] = band

        # Sanity check: did we get any non-NaN data?
        valid_fraction = float(np.isfinite(next(iter(out_bands.values()))).mean()) if out_bands else 0.0
        _log(f'Composite valid_fraction (first band): {valid_fraction:.1%}')
        if valid_fraction < 0.001:
            send_notification(
                f'Copernicus[STAC]: composite is 0% valid for bbox. '
                f'Try wider date range or different orbit.',
                level='error', notif_id=self._notif_id,
            )
            return

        # VV/VH ratio for S1-RTC if both present
        band_names: list[str] = list(out_bands.keys())
        if 'vv' in out_bands and 'vh' in out_bands:
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio = (out_bands['vv'] - out_bands['vh']) if to_db else (
                    out_bands['vv'] /
                    np.where(out_bands['vh'] > 0, out_bands['vh'], np.nan))
            out_bands['vv_vh_ratio'] = ratio.astype('float32')
            band_names.append('vv_vh_ratio')

        # LULC: single band, name normalized
        if is_cat:
            single_key = asset_keys[0]
            out_bands = {'lulc_class': out_bands[single_key]}
            band_names = ['lulc_class']

        arr = np.stack([out_bands[b] for b in band_names], axis=0)
        dtype = 'uint8' if is_cat else 'float32'
        nodata_val = 0 if is_cat else float('nan')

        # ── Write final GeoTIFF ───────────────────────────────────────────────
        send_notification('Copernicus[STAC]: writing GeoTIFF…',
                          progress=0.88, notif_id=self._notif_id)
        with rasterio.open(
            final_path, 'w', driver='GTiff',
            height=out_h, width=out_w, count=arr.shape[0],
            dtype=dtype, crs=dst_crs, transform=dst_transform,
            compress='deflate', predictor=2, nodata=nodata_val,
        ) as dst:
            dst.write(arr)
            for i, n in enumerate(band_names, start=1):
                dst.set_band_description(i, n)
            dst.update_tags(
                source=f'planetary_computer:{col_cfg["stac_id"]}',
                composite=composite, polarization=polariz, orbit=orbit,
                to_db=str(to_db), n_scenes=str(len(items)),
                date_range=f'{date_start} → {date_end}',
                resolution_m=str(resolution),
            )

        # ── Build geo dict + preview matching SH-backend contract ─────────────
        geo: dict = {
            'bands':       arr.astype('float32'),
            'band_names':  band_names,
            'count':       arr.shape[0],
            'width':       out_w,
            'height':      out_h,
            'crs':         dst_crs,
            'transform':   dst_transform,
            'nodata':      nodata_val if not is_cat else 0,
            'dtype':       dtype,
            'bounds':      {'west': west, 'south': south, 'east': east, 'north': north},
            '_source':     col_name,
            '_bands':      band_names,
            '_dates':      f'{date_start} → {date_end}',
            '_cache_path': final_path,
        }

        preview = self._stac_preview(arr, band_names, col_cfg)
        # Thumbnail
        h, w = preview.shape[:2]
        sc   = min(1.0, 120 / h)
        thumb = cv2.resize(preview, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        if self._generation != my_gen:
            return  # superseded by newer Fetch — discard results
        self._cache_data  = (geo, preview, thumb_b64)
        self._thumb_dirty = True
        send_notification(
            f'Copernicus[STAC]: ready — {arr.shape[0]} band(s), {out_w}×{out_h} px',
            progress=1.0, notif_id=self._notif_id,
        )
        _notification_queue.put_nowait({
            '_wake_engine': True, '_node_type': 'geo_copernicus',
            '_notif_id': self._notif_id,
        })

    def _stac_preview(self, arr: np.ndarray, band_names: list[str],
                      col_cfg: dict) -> np.ndarray:
        """Build a preview from a STAC-fetched stack (RGB or categorical)."""
        if col_cfg.get('categorical'):
            palette_name = col_cfg.get('class_palette', 'worldcover')
            palette = _CLASS_PALETTES.get(palette_name, {})
            cat = arr[0].astype(np.int32)
            h, w = cat.shape
            rgb = np.zeros((h, w, 3), dtype=np.uint8)
            for code, bgr in palette.items():
                m = cat == code
                if m.any():
                    rgb[m] = bgr
            return rgb
        # Continuous: RGB(VV, VH, ratio) or first 3 bands stretched
        r = self._stretch(arr[0]) if arr.shape[0] >= 1 else np.zeros(arr.shape[1:], dtype=np.uint8)
        g = self._stretch(arr[1]) if arr.shape[0] >= 2 else r
        b = self._stretch(arr[2]) if arr.shape[0] >= 3 else r
        return cv2.merge([b, g, r])

    @staticmethod
    def _latlon_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
        lat_rad = math.radians(lat)
        n = 2.0 ** z
        xtile = int((lon + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile

    @staticmethod
    def _tile_bounds_3857(x: int, y: int, z: int) -> tuple[float, float, float, float]:
        origin_shift = 20037508.342789244
        n = 2.0 ** z
        tile_size = (2.0 * origin_shift) / n
        xmin = -origin_shift + x * tile_size
        xmax = xmin + tile_size
        ymax = origin_shift - y * tile_size
        ymin = ymax - tile_size
        return xmin, ymin, xmax, ymax

    def _do_fetch_basemap(self, params: dict, col_name: str, col_cfg: dict,
                          auto: bool = False, my_gen: int = 0) -> None:
        """Downloads, cache, stitch, and reprojects XYZ tiles (Google Maps / OSM / CartoDB)
        to target bbox in WGS84 EPSG:4326.
        """
        if not self.ensure_packages(
            ['rasterio'],
            pip_names=['rasterio'],
            notif_id=self._notif_id,
        ):
            return

        import rasterio
        from rasterio.warp import reproject, Resampling
        from rasterio.transform import from_bounds
        import urllib.request
        import urllib.error
        import time

        # ── BBOX ──────────────────────────────────────────────────────────────
        bbox_str = str(params.get('bbox', '') or '').strip()
        if not bbox_str:
            send_notification('Copernicus[Basemap]: no bounding box — open editor to draw ROI',
                               level='warning', notif_id=self._notif_id)
            return
        try:
            west, south, east, north = (float(v) for v in bbox_str.split(','))
        except Exception:
            send_notification(f'Copernicus[Basemap]: invalid bbox "{bbox_str}"',
                               level='error', notif_id=self._notif_id)
            return

        resolution = max(1, int(params.get('resolution', 10)))

        # ── Cache path ────────────────────────────────────────────────────────
        raw_cache = str(params.get('cache_dir', 'copernicus_cache') or 'copernicus_cache').strip()
        _engine_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir   = raw_cache if os.path.isabs(raw_cache) else os.path.join(_engine_dir, raw_cache)
        os.makedirs(cache_dir, exist_ok=True)

        sig = json.dumps({
            'col': col_name, 'bbox': [west, south, east, north],
            'res': resolution
        }, sort_keys=True)
        sig_key = hashlib.md5(sig.encode()).hexdigest()[:14]
        final_path = os.path.join(cache_dir, f'basemap_{sig_key}.tif')

        if auto and not os.path.exists(final_path):
            return

        # ── Cache hit: load existing GeoTIFF, skip re-download ───────────────
        if os.path.exists(final_path):
            try:
                with rasterio.open(final_path) as _src:
                    arr_c      = _src.read().astype('float32')
                    dst_crs_c  = _src.crs
                    dst_tf_c   = _src.transform
                    out_h_c, out_w_c = _src.height, _src.width
                    bnames_c   = [_src.descriptions[i] or f'band_{i+1}'
                                  for i in range(_src.count)]

                geo_c: dict = {
                    'bands':       arr_c,
                    'band_names':  bnames_c,
                    'count':       arr_c.shape[0],
                    'width':       out_w_c,
                    'height':      out_h_c,
                    'crs':         str(dst_crs_c) if dst_crs_c else 'EPSG:4326',
                    'transform':   dst_tf_c,
                    'nodata':      None,
                    'dtype':       'float32',
                    'bounds':      {'west': west, 'south': south,
                                    'east': east, 'north': north},
                    '_source':     col_name,
                    '_bands':      bnames_c,
                    '_dates':      'N/A',
                    '_cache_path': final_path,
                }
                
                r_ch_c = np.clip(arr_c[0], 0, 255).astype(np.uint8)
                g_ch_c = np.clip(arr_c[1], 0, 255).astype(np.uint8)
                b_ch_c = np.clip(arr_c[2], 0, 255).astype(np.uint8)
                preview_c = cv2.merge([b_ch_c, g_ch_c, r_ch_c])

                h_c, w_c  = preview_c.shape[:2]
                sc_c      = min(1.0, 120 / h_c)
                thumb_c   = cv2.resize(preview_c,
                                        (max(1, int(w_c * sc_c)),
                                         max(1, int(h_c * sc_c))))
                _, buf_c  = _cv2.imencode('.jpg', thumb_c,
                                          [_cv2.IMWRITE_JPEG_QUALITY, 60])
                thumb_b64_c = _b64.b64encode(buf_c).decode('utf-8')

                if self._generation != my_gen:
                    return  # superseded
                self._cache_data  = (geo_c, preview_c, thumb_b64_c)
                self._thumb_dirty = True
                send_notification(
                    f'Copernicus[Basemap]: loaded from cache — '
                    f'{arr_c.shape[0]} band(s), {out_w_c}×{out_h_c} px',
                    progress=1.0, notif_id=self._notif_id,
                )
                _notification_queue.put_nowait({
                    '_wake_engine': True, '_node_type': 'geo_copernicus',
                    '_notif_id': self._notif_id,
                })
                return
            except Exception:
                pass # fall through to download

        # ── Tile Coordinate Calculations ──────────────────────────────────────
        lat_c = (south + north) / 2.0
        val = (156543.03392 * math.cos(math.radians(lat_c))) / resolution
        z = max(0, min(20, round(math.log2(val))))

        x_min_t, y_min_t = self._latlon_to_tile(west, north, z)
        x_max_t, y_max_t = self._latlon_to_tile(east, south, z)

        x_start, x_end = min(x_min_t, x_max_t), max(x_min_t, x_max_t)
        y_start, y_end = min(y_min_t, y_max_t), max(y_min_t, y_max_t)

        # Apply safety limit and automatically adjust zoom to prevent downloading too many tiles
        n_limit = 2**z
        x_start = max(0, min(n_limit - 1, x_start))
        x_end = max(0, min(n_limit - 1, x_end))
        y_start = max(0, min(n_limit - 1, y_start))
        y_end = max(0, min(n_limit - 1, y_end))

        num_x = x_end - x_start + 1
        num_y = y_end - y_start + 1
        total_tiles = num_x * num_y

        while total_tiles > 150 and z > 0:
            z -= 1
            n_limit = 2**z
            x_min_t, y_min_t = self._latlon_to_tile(west, north, z)
            x_max_t, y_max_t = self._latlon_to_tile(east, south, z)
            x_start = max(0, min(n_limit - 1, min(x_min_t, x_max_t)))
            x_end = max(0, min(n_limit - 1, max(x_min_t, x_max_t)))
            y_start = max(0, min(n_limit - 1, min(y_min_t, y_max_t)))
            y_end = max(0, min(n_limit - 1, max(y_min_t, y_max_t)))
            num_x = x_end - x_start + 1
            num_y = y_end - y_start + 1
            total_tiles = num_x * num_y

        # Clear cancellation flag
        clear_cancel(self._notif_id)

        send_notification(
            f'Copernicus[Basemap]: {col_name} · zoom {z} · {total_tiles} tile{"s" if total_tiles > 1 else ""}',
            progress=0.05, notif_id=self._notif_id,
        )

        stitched_w = num_x * 256
        stitched_h = num_y * 256
        stitched = np.zeros((stitched_h, stitched_w, 3), dtype=np.uint8)

        tiles_cache_dir = os.path.join(cache_dir, 'tiles')
        os.makedirs(tiles_cache_dir, exist_ok=True)

        def download_tile_image(url: str, tile_cache_path: str) -> np.ndarray | None:
            if os.path.exists(tile_cache_path):
                try:
                    img = cv2.imread(tile_cache_path)
                    if img is not None and img.shape == (256, 256, 3):
                        return img
                except Exception:
                    pass

            os.makedirs(os.path.dirname(tile_cache_path), exist_ok=True)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = response.read()
                        with open(tile_cache_path, 'wb') as f:
                            f.write(data)
                        nparr = np.frombuffer(data, np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img is not None and img.shape == (256, 256, 3):
                            return img
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        break
                    time.sleep(0.5)
                except Exception:
                    time.sleep(0.5)
            return None

        # ── Download & Stitch tiles ───────────────────────────────────────────
        for i_y, y in enumerate(range(y_start, y_end + 1)):
            for i_x, x in enumerate(range(x_start, x_end + 1)):
                if (is_cancelled(self._notif_id) or self._stop_event.is_set()
                        or self._generation != my_gen):
                    send_notification('Copernicus[Basemap]: cancelled', level='warning', notif_id=self._notif_id)
                    return

                tile_num = i_y * num_x + i_x + 1
                send_notification(
                    f'Copernicus[Basemap]: downloading tile {tile_num}/{total_tiles}…',
                    progress=0.10 + 0.70 * tile_num / total_tiles,
                    notif_id=self._notif_id,
                )

                url = col_cfg['url_template'].format(x=x, y=y, z=z)
                escaped_provider = col_name.replace(' ', '_').lower()
                tile_cache_path = os.path.join(tiles_cache_dir, f'{escaped_provider}_{z}_{x}_{y}.png')

                tile_img = download_tile_image(url, tile_cache_path)
                if tile_img is None:
                    tile_img = np.full((256, 256, 3), 240, dtype=np.uint8)

                row_offset = i_y * 256
                col_offset = i_x * 256
                stitched[row_offset:row_offset+256, col_offset:col_offset+256] = tile_img

        # ── Stitch Bounds and Transform in EPSG:3857 ──────────────────────────
        xmin_start, _, _, _ = self._tile_bounds_3857(x_start, y_start, z)
        _, _, xmax_end, _ = self._tile_bounds_3857(x_end, y_start, z)
        _, ymin_end, _, _ = self._tile_bounds_3857(x_start, y_end, z)
        _, _, _, ymax_start = self._tile_bounds_3857(x_start, y_start, z)

        xmin_3857 = xmin_start
        xmax_3857 = xmax_end
        ymin_3857 = ymin_end
        ymax_3857 = ymax_start

        transform_3857 = from_bounds(xmin_3857, ymin_3857, xmax_3857, ymax_3857, stitched_w, stitched_h)

        # ── Target Grid in EPSG:4326 ──────────────────────────────────────────
        width_m = abs(east - west) * 111320.0 * math.cos(math.radians(lat_c))
        height_m = abs(north - south) * 111320.0
        total_w = max(1, round(width_m / resolution))
        total_h = max(1, round(height_m / resolution))

        dst_transform = from_bounds(west, south, east, north, total_w, total_h)

        # ── Reproject from EPSG:3857 to EPSG:4326 ──────────────────────────────
        send_notification('Copernicus[Basemap]: reprojecting to WGS84…', progress=0.85, notif_id=self._notif_id)

        # Convert stitched BGR to RGB and transpose to CHW
        src_rgb = cv2.cvtColor(stitched, cv2.COLOR_BGR2RGB)
        src_chw = src_rgb.transpose(2, 0, 1).astype(np.float32)

        dst_data = np.zeros((3, total_h, total_w), dtype=np.float32)

        reproject(
            source=src_chw,
            destination=dst_data,
            src_transform=transform_3857,
            src_crs='EPSG:3857',
            dst_transform=dst_transform,
            dst_crs='EPSG:4326',
            resampling=Resampling.bilinear
        )

        # ── Write final GeoTIFF ───────────────────────────────────────────────
        send_notification('Copernicus[Basemap]: writing GeoTIFF…', progress=0.90, notif_id=self._notif_id)
        with rasterio.open(
            final_path, 'w', driver='GTiff',
            height=total_h, width=total_w, count=3,
            dtype='float32', crs='EPSG:4326', transform=dst_transform,
            compress='lzw', nodata=None
        ) as dst:
            dst.write(dst_data)
            dst.set_band_description(1, 'R')
            dst.set_band_description(2, 'G')
            dst.set_band_description(3, 'B')
            dst.update_tags(
                source=col_name,
                zoom=str(z),
                resolution_m=str(resolution),
                bbox=bbox_str
            )

        # ── Build geo dict + preview ──────────────────────────────────────────
        geo: dict = {
            'bands':       dst_data,
            'band_names':  ['R', 'G', 'B'],
            'count':       3,
            'width':       total_w,
            'height':      total_h,
            'crs':         'EPSG:4326',
            'transform':   dst_transform,
            'nodata':      None,
            'dtype':       'float32',
            'bounds':      {'west': west, 'south': south, 'east': east, 'north': north},
            '_source':     col_name,
            '_bands':      ['R', 'G', 'B'],
            '_dates':      'N/A',
            '_cache_path': final_path,
        }

        r_ch = np.clip(dst_data[0], 0, 255).astype(np.uint8)
        g_ch = np.clip(dst_data[1], 0, 255).astype(np.uint8)
        b_ch = np.clip(dst_data[2], 0, 255).astype(np.uint8)
        preview = cv2.merge([b_ch, g_ch, r_ch])

        # Thumbnail
        h, w = preview.shape[:2]
        sc   = min(1.0, 120 / h)
        thumb = cv2.resize(preview, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        if self._generation != my_gen:
            return  # superseded by newer Fetch — discard results
        self._cache_data  = (geo, preview, thumb_b64)
        self._thumb_dirty = True
        send_notification(
            f'Copernicus[Basemap]: ready — 3 bands, {total_w}×{total_h} px',
            progress=1.0, notif_id=self._notif_id,
        )
        _notification_queue.put_nowait({
            '_wake_engine': True,
            '_node_type': 'geo_copernicus',
            '_notif_id': self._notif_id,
        })

    @staticmethod
    def _dl_params_key(params: dict) -> str:
        keys = ('bbox', 'date_start', 'date_end', 'bands', 'collection', 'resolution', 'cloud_max',
                'mosaic_mode', 'cache_dir', 'stac_polarization', 'stac_orbit', 'stac_composite',
                'stac_to_db', 'stac_max_scenes')
        s = json.dumps({k: params.get(k) for k in keys}, sort_keys=True)
        return hashlib.md5(s.encode()).hexdigest()

    # ── process ───────────────────────────────────────────────────────────────

    def process(self, inputs: dict, params: dict) -> dict:
        params = params.copy()
        if inputs.get('bbox') is not None:
            params['bbox'] = inputs['bbox']
        if inputs.get('date_start') is not None:
            params['date_start'] = inputs['date_start']
        if inputs.get('date_end') is not None:
            params['date_end'] = inputs['date_end']

        # Clear stale internal cache when download-relevant params change
        # (e.g. user duplicated node then changed bbox/dates without clicking Fetch)
        dl_key = self._dl_params_key(params)
        if dl_key != self._prev_dl_key:
            self._prev_dl_key = dl_key
            self._cache_data  = None
            self._auto_tried  = False

        fetch_val = params.get('fetch', 0)
        rising = fetch_val != self._prev_fetch and fetch_val not in (False, 0, None)
        self._prev_fetch = fetch_val

        if rising:
            # ABANDONMENT STRATEGY: always start fresh thread immediately.
            # Bump generation → any in-flight thread's writes become no-ops (guarded by gen check).
            # Set stop_event → it'll exit its scene loop at the next checkpoint.
            # The old thread continues running as a zombie daemon — harmless, dies naturally.
            self._generation += 1
            self._stop_event.set()
            my_gen = self._generation
            self._loading = True   # OWNS the loading flag now (old thread won't touch it)
            self._auto_tried = True
            threading.Thread(
                target=self._do_fetch, args=(params,),
                kwargs={'my_gen': my_gen}, daemon=True,
            ).start()

        elif self._cache_data is None and not self._loading and not self._auto_tried:
            # Auto-restore on graph load: try loading cached file once without auth
            self._auto_tried = True
            self._generation += 1
            my_gen = self._generation
            self._loading = True
            threading.Thread(
                target=self._do_fetch, args=(params,),
                kwargs={'auto': True, 'my_gen': my_gen}, daemon=True,
            ).start()

        if self._cache_data is None:
            return {'geotiff': None, 'preview': None, 'meta': None}

        geo, preview, thumb_b64 = self._cache_data
        meta = {
            'source':     geo.get('_source'),
            'bands':      geo.get('_bands'),
            'dates':      geo.get('_dates'),
            'crs':        geo['crs'],
            'band_count': geo['count'],
            'width':      geo['width'],
            'height':     geo['height'],
            'bounds':     geo.get('bounds'),
            'cache_path': geo.get('_cache_path'),
        }
        out_thumb = thumb_b64 if self._thumb_dirty else None
        self._thumb_dirty = False
        return {'geotiff': geo, 'preview': preview, 'meta': meta, '_thumb': out_thumb}
