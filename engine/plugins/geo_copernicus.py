"""
geo_copernicus.py — Copernicus Data Space Ecosystem (CDSE) satellite imagery downloader.

Credentials: Client ID + Secret from https://shapps.dataspace.copernicus.eu/
Stored in ~/.vnstudio/secrets.json (same as GEE).

Tiling: large areas are split into tiles, downloaded in sequence, stitched.
Cache:  each request is cached as a local GeoTIFF (MD5 key on all params).
"""
import os
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
                         'B08','B8A','B09','B11','B12'],
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
        'backend':      'sh',
        'sh_id':        'SENTINEL1_IW',
        'all_bands':    ['VV', 'VH'],
        'default_bands':['VV', 'VH'],
        'rgb':          ['VV', 'VH', 'VV'],
        'units':        'DB',
        'has_cloud_filter': False,
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
    inputs=[],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview RGB'},
        {'id': 'meta',    'color': 'dict',     'label': 'Meta'},
    ],
    params=[
        {'id': 'client_id',     'type': 'string', 'default': '', 'label': 'Client ID (CDSE)'},
        {'id': 'client_secret', 'type': 'string', 'default': '', 'label': 'Client Secret'},
        {'id': 'collection',    'type': 'enum',   'options': list(COLLECTIONS.keys()), 'default': 0, 'label': 'Collection'},
        {'id': 'date_start',    'type': 'string', 'default': '2024-01-01', 'label': 'Start Date'},
        {'id': 'date_end',      'type': 'string', 'default': '2024-06-01', 'label': 'End Date'},
        {'id': 'cloud_max',     'type': 'int',    'default': 20, 'min': 0, 'max': 100, 'label': 'Max Clouds %'},
        {'id': 'resolution',    'type': 'int',    'default': 10, 'min': 1, 'max': 1000, 'label': 'Resolution (m/px)'},
        {'id': 'bands',         'type': 'string', 'default': 'B04,B03,B02,B08', 'label': 'Bands (set via editor)'},
        {'id': 'bbox',          'type': 'string', 'default': '', 'label': 'Bounding Box (set via editor)'},
        {'id': 'max_tile_px',   'type': 'int',    'default': 2500, 'min': 256, 'max': 5000, 'label': 'Max tile size (px)'},
        {'id': 'cache_dir',     'type': 'string', 'default': 'copernicus_cache', 'label': 'Cache Dir'},

        # ── STAC-only parameters (ignored for SentinelHub collections) ────
        {'id': 'stac_polarization', 'type': 'enum', 'options': ['Both', 'VV', 'VH'],
         'default': 0, 'label': 'STAC: Polarization (S1-RTC)'},
        {'id': 'stac_orbit',        'type': 'enum', 'options': ['Any', 'Ascending', 'Descending'],
         'default': 0, 'label': 'STAC: Orbit (S1-RTC)'},
        {'id': 'stac_composite',    'type': 'enum',
         'options': ['median', 'mean', 'first', 'min', 'max'],
         'default': 0, 'label': 'STAC: Composite Method'},
        {'id': 'stac_to_db',        'type': 'bool', 'default': True,
         'label': 'STAC: SAR → dB (10·log10)'},
        {'id': 'stac_max_scenes',   'type': 'int',  'default': 30, 'min': 1, 'max': 500,
         'label': 'STAC: Max scenes for composite'},
        {'id': 'stac_scene_timeout', 'type': 'int', 'default': 60, 'min': 10, 'max': 300,
         'label': 'STAC: Scene read timeout (s) — increase on slow connections'},
        {'id': 'stac_min_ok',       'type': 'int',  'default': 3,  'min': 1, 'max': 100,
         'label': 'STAC: Min scenes OK to accept result (else retry)'},

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
    def _make_evalscript(bands: list[str], units: str | None) -> str:
        band_json   = json.dumps(bands)
        n           = len(bands)
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
    def _cache_key(col_name: str, bbox: tuple, date_start: str, date_end: str,
                   bands: list[str], resolution: int,
                   tile_row: int, tile_col: int) -> str:
        s = f'{col_name}|{bbox}|{date_start}|{date_end}|{"-".join(bands)}|{resolution}|{tile_row}|{tile_col}'
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
    ) -> bool:
        """Download one tile to tile_path as float32 GeoTIFF. Returns True on success."""
        try:
            from sentinelhub import (
                BBox, CRS, SentinelHubRequest, MimeType
            )
            import rasterio
            from rasterio.transform import from_bounds

            bbox = BBox([west, south, east, north], crs=CRS.WGS84)

            # Build filter for cloud cover
            extra_filter = None
            if has_cloud:
                try:
                    from sentinelhub import filter_field_eq, filter_field_lt
                    extra_filter = filter_field_lt('eo:cloud_cover', cloud_max)
                except ImportError:
                    pass

            input_data_kwargs: dict = {
                'data_collection': data_collection,
                'time_interval':   (date_start, date_end),
                'mosaicking_order':'leastCC',
            }
            if extra_filter is not None:
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

    def _do_fetch(self, params: dict, auto: bool = False) -> None:
        try:
            self._do_fetch_impl(params, auto=auto)
        except BaseException as e:
            send_notification(f'Copernicus: unexpected crash: {e}', level='error', notif_id=self._notif_id)
        finally:
            self._loading = False

    def _do_fetch_impl(self, params: dict, auto: bool = False) -> None:
        # ── Dispatch by collection backend ─────────────────────────────────────
        col_names   = list(COLLECTIONS.keys())
        col_idx     = int(params.get('collection', 0))
        col_name    = col_names[col_idx] if 0 <= col_idx < len(col_names) else col_names[0]
        col_cfg     = COLLECTIONS[col_name]
        backend     = col_cfg.get('backend', 'sh')

        if backend == 'stac':
            self._do_fetch_stac(params, col_name, col_cfg, auto=auto)
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

        # Clear any leftover cancel flag from a previous operation
        clear_cancel(self._notif_id)

        if auto:
            # On auto-restore, only continue if a matching cache file can be found
            test_key = self._cache_key(col_name, (west, south, east, north),
                                       date_start, date_end, bands, resolution, 0, 0)
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

        evalscript = self._make_evalscript(bands, col_cfg.get('units'))

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
            f'bands: {", ".join(bands)}',
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
                                            date_start, date_end, bands, resolution, row, col)
                tile_path = os.path.join(cache_dir, f'{key}.tif')
                tile_paths.append((row, col, tile_path))

                if os.path.exists(tile_path):
                    continue

                all_cached = False
                if auto:
                    return  # don't trigger auth on auto-restore

                # Check cancellation before each tile download
                if is_cancelled(self._notif_id):
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
                       auto: bool = False) -> None:
        """STAC fetch path for collections backed by Microsoft Planetary Computer.

        Reads the AOI via STAC + COG window reads (no SH OAuth), composites
        multiple scenes into a single multi-band raster, then writes the same
        `_cache_data` triple that the SH path produces, so `process()` returns
        an identical contract to downstream nodes.
        """
        if not self.ensure_packages(
            ['rasterio', 'pystac_client', 'planetary_computer'],
            pip_names=['rasterio', 'pystac-client', 'planetary-computer'],
            notif_id=self._notif_id,
        ):
            return

        import pystac_client
        import planetary_computer
        import rasterio
        from rasterio.warp import transform_bounds, reproject, Resampling
        from rasterio.windows import from_bounds
        from rasterio.transform import Affine

        # GDAL config dict — applied via rasterio.Env() inside each COG read
        # (os.environ is too late: GDAL is already initialised by the time this runs)
        _GDAL_COG_CFG = {
            'GDAL_HTTP_TIMEOUT':            30,
            'GDAL_HTTP_CONNECTTIMEOUT':     10,
            'GDAL_HTTP_MAX_RETRY':          3,
            'GDAL_HTTP_RETRY_DELAY':        2,
            'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR',
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
        }, sort_keys=True)
        sig_key = hashlib.md5(sig.encode()).hexdigest()[:14]
        final_path = os.path.join(cache_dir, f'stac_{sig_key}.tif')

        if auto and not os.path.exists(final_path):
            return

        # ── STAC search ───────────────────────────────────────────────────────
        catalog = pystac_client.Client.open(
            'https://planetarycomputer.microsoft.com/api/stac/v1',
            modifier=planetary_computer.sign_inplace,
        )
        send_notification(f'Copernicus[STAC]: querying {col_cfg["stac_id"]}…',
                          progress=0.1, notif_id=self._notif_id)
        try:
            search = catalog.search(
                collections=[col_cfg['stac_id']],
                bbox=[west, south, east, north],
                datetime=f'{date_start}/{date_end}',
                limit=500,
            )
            items = list(search.items())
        except Exception as e:
            send_notification(f'Copernicus[STAC]: search failed: {e}',
                              level='error', notif_id=self._notif_id)
            return

        # Orbit filter for S1
        if orbit.lower() in ('ascending', 'descending'):
            items = [it for it in items
                     if str(it.properties.get('sat:orbit_state', '')).lower() == orbit.lower()]
        if not items:
            send_notification(f'Copernicus[STAC]: 0 scenes for bbox/date/orbit',
                              level='warning', notif_id=self._notif_id)
            return

        items = sorted(items, key=lambda i: i.datetime or 0)
        # For LULC: take the latest scene only (categorical, no composite).
        if col_cfg.get('categorical'):
            items = [items[-1]]
        elif len(items) > max_scenes:
            idx = np.linspace(0, len(items) - 1, max_scenes).round().astype(int)
            items = [items[i] for i in idx]

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

        # ── Compute target shape from bbox in metres ──────────────────────────
        lat_mid  = 0.5 * (south + north)
        phys_w_m = (east - west) * 111_320.0 * float(math.cos(math.radians(lat_mid)))
        phys_h_m = (north - south) * 110_540.0
        out_w    = max(1, int(round(phys_w_m / resolution)))
        out_h    = max(1, int(round(phys_h_m / resolution)))
        dst_transform = Affine(
            (east - west) / out_w, 0.0, west,
            0.0, -(north - south) / out_h, north,
        )
        dst_crs = 'EPSG:4326'

        # ── Read each item's chosen assets, reprojected to common grid ────────
        send_notification(
            f'Copernicus[STAC]: reading {len(items)} scene(s) '
            f'(timeout={scene_timeout}s/scene)…',
            progress=0.25, notif_id=self._notif_id,
        )

        stacks: dict[str, list[np.ndarray]] = {a: [] for a in asset_keys}
        is_cat   = col_cfg.get('categorical', False)
        resamp   = Resampling.nearest if is_cat else Resampling.average
        n_ok     = 0   # scenes with at least one asset read successfully
        n_timeout = 0
        n_error   = 0

        def _read_one(href: str) -> np.ndarray:
            """Windowed COG read + reproject for one asset.

            Only downloads the tiles that cover the target bbox — a COG
            scene can be hundreds of MB; windowed reads fetch only the
            relevant portion (typically a few MB), making each scene read
            finish in seconds instead of minutes.
            """
            from rasterio.warp import transform_bounds as _tb
            from rasterio.windows import from_bounds as _wfb

            with rasterio.Env(**_GDAL_COG_CFG):
                with rasterio.open(href) as _src:
                    nodata_val  = _src.nodata
                    src_crs     = _src.crs

                    # Transform target bbox → source CRS to get the window
                    try:
                        sx0, sy0, sx1, sy1 = _tb(dst_crs, src_crs,
                                                  west, south, east, north)
                    except Exception:
                        sx0, sy0, sx1, sy1 = west, south, east, north

                    # Clip to source raster extent (avoid out-of-bounds reads)
                    b = _src.bounds
                    sx0 = max(sx0, b.left);  sx1 = min(sx1, b.right)
                    sy0 = max(sy0, b.bottom); sy1 = min(sy1, b.top)

                    if sx0 >= sx1 or sy0 >= sy1:
                        # AOI doesn't overlap this scene
                        return np.full((out_h, out_w),
                                       np.nan if not is_cat else 0,
                                       dtype='float32')

                    win = _wfb(sx0, sy0, sx1, sy1, transform=_src.transform)
                    win_transform = _src.window_transform(win)

                    # Windowed read — only downloads the relevant COG tiles
                    src_arr = _src.read(
                        1, window=win, boundless=True,
                        fill_value=nodata_val if nodata_val is not None else 0,
                    ).astype('float32')

            # Reproject from in-memory window array
            _dst = np.full(
                (out_h, out_w),
                np.nan if not is_cat else 0,
                dtype='float32' if not is_cat else 'uint8',
            )
            reproject(
                source=src_arr,
                destination=_dst,
                src_transform=win_transform, src_crs=src_crs,
                dst_transform=dst_transform, dst_crs=dst_crs,
                resampling=resamp,
                src_nodata=nodata_val,
                dst_nodata=np.nan if not is_cat else 0,
            )
            return _dst

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout

        # 2 workers: if one thread stalls (future timed out but thread still running),
        # the next scene can start immediately rather than waiting in the queue.
        with ThreadPoolExecutor(max_workers=2) as _pool:
            for i, item in enumerate(items):

                # Honour user cancel
                if is_cancelled(self._notif_id):
                    send_notification('Copernicus[STAC]: cancelled by user',
                                      level='warning', notif_id=self._notif_id)
                    break

                scene_ok = False
                for ak in asset_keys:
                    if ak not in item.assets:
                        continue
                    href = item.assets[ak].href
                    try:
                        future = _pool.submit(_read_one, href)
                        dst = future.result(timeout=scene_timeout)
                        if not is_cat:
                            dst = np.where(dst <= 0, np.nan, dst)
                        stacks[ak].append(
                            dst.astype('float32') if not is_cat else dst
                        )
                        scene_ok = True
                    except _FutTimeout:
                        n_timeout += 1
                        future.cancel()
                        send_notification(
                            f'Copernicus[STAC]: scene {i+1} timed out after '
                            f'{scene_timeout}s — skipping',
                            level='warning', notif_id=self._notif_id,
                        )
                    except Exception as _e:
                        n_error += 1
                        send_notification(
                            f'Copernicus[STAC]: scene {i+1} asset {ak} failed: {_e}',
                            level='warning', notif_id=self._notif_id,
                        )

                if scene_ok:
                    n_ok += 1

                # Progress every scene
                send_notification(
                    f'Copernicus[STAC]: {i+1}/{len(items)} scenes  '
                    f'(ok={n_ok}  timeout={n_timeout}  err={n_error})',
                    progress=0.25 + 0.55 * (i + 1) / len(items),
                    notif_id=self._notif_id,
                )

        if n_ok == 0:
            send_notification(
                f'Copernicus[STAC]: 0/{len(items)} scenes succeeded '
                f'(timeouts={n_timeout}, errors={n_error}). '
                f'Check network / Planetary Computer availability.',
                level='error', notif_id=self._notif_id,
            )
            return
        if n_ok < min_ok:
            send_notification(
                f'Copernicus[STAC]: only {n_ok}/{len(items)} scenes ok '
                f'(timeouts={n_timeout}, errors={n_error}) — '
                f'below stac_min_ok={min_ok}, but producing output anyway.',
                level='warning', notif_id=self._notif_id,
            )
            # fall through — composite what we have

        if not any(stacks.values()):
            send_notification(
                f'Copernicus[STAC]: all bands empty for bbox. '
                f'scenes ok={n_ok}, timeouts={n_timeout}, errors={n_error}',
                level='error', notif_id=self._notif_id,
            )
            return

        # ── Composite (or single take for LULC) ───────────────────────────────
        def _reduce(arrs: list[np.ndarray]) -> np.ndarray:
            if not arrs:
                return np.full((out_h, out_w), np.nan, dtype='float32')
            if len(arrs) == 1 or is_cat:
                return arrs[-1]
            a = np.stack(arrs, axis=0)
            return {
                'median': np.nanmedian, 'mean': np.nanmean,
                'first':  lambda x, axis: x[0],
                'min':    np.nanmin,    'max':  np.nanmax,
            }.get(composite, np.nanmedian)(a, axis=0)

        out_bands: dict[str, np.ndarray] = {}
        for ak in asset_keys:
            band = _reduce(stacks[ak])
            if not is_cat and to_db:
                with np.errstate(divide='ignore', invalid='ignore'):
                    band = 10.0 * np.log10(band)
            out_bands[ak] = band.astype('uint8' if is_cat else 'float32')

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
    def _dl_params_key(params: dict) -> str:
        keys = ('bbox', 'date_start', 'date_end', 'bands', 'collection', 'resolution', 'cloud_max',
                'cache_dir', 'stac_polarization', 'stac_orbit', 'stac_composite', 'stac_to_db',
                'stac_max_scenes')
        s = json.dumps({k: params.get(k) for k in keys}, sort_keys=True)
        return hashlib.md5(s.encode()).hexdigest()

    # ── process ───────────────────────────────────────────────────────────────

    def process(self, inputs: dict, params: dict) -> dict:
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

        if rising and not self._loading:
            self._loading = True
            threading.Thread(target=self._do_fetch, args=(params,), daemon=True).start()

        if self._cache_data is None and not self._loading and not self._auto_tried:
            self._auto_tried = True
            self._loading = True
            threading.Thread(target=self._do_fetch, args=(params,),
                             kwargs={'auto': True}, daemon=True).start()

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
