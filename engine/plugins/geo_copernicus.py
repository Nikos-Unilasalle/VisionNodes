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

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'copernicus'
_SECRETS_PATH = os.path.expanduser('~/.vnstudio/secrets.json')
_CDSE_BASE_URL = 'https://sh.dataspace.copernicus.eu'
_CDSE_TOKEN_URL = (
    'https://identity.dataspace.copernicus.eu'
    '/auth/realms/CDSE/protocol/openid-connect/token'
)

# ── Collection definitions ────────────────────────────────────────────────────

COLLECTIONS: dict[str, dict] = {
    'Sentinel-2 L2A': {
        'sh_id':        'SENTINEL2_L2A',
        'all_bands':    ['B01','B02','B03','B04','B05','B06','B07',
                         'B08','B8A','B09','B11','B12'],
        'default_bands':['B04','B03','B02','B08'],
        'rgb':          ['B04','B03','B02'],
        'units':        'REFLECTANCE',
        'has_cloud_filter': True,
    },
    'Sentinel-2 L1C': {
        'sh_id':        'SENTINEL2_L1C',
        'all_bands':    ['B01','B02','B03','B04','B05','B06','B07',
                         'B08','B8A','B09','B10','B11','B12'],
        'default_bands':['B04','B03','B02','B08'],
        'rgb':          ['B04','B03','B02'],
        'units':        'REFLECTANCE',
        'has_cloud_filter': True,
    },
    'Sentinel-1 GRD': {
        'sh_id':        'SENTINEL1_IW',
        'all_bands':    ['VV', 'VH'],
        'default_bands':['VV', 'VH'],
        'rgb':          ['VV', 'VH', 'VV'],
        'units':        'DB',
        'has_cloud_filter': False,
    },
    'Copernicus DEM': {
        'sh_id':        'DEM',
        'all_bands':    ['DEM'],
        'default_bands':['DEM'],
        'rgb':          ['DEM'],
        'units':        None,
        'has_cloud_filter': False,
    },
}

# ── Node definition ───────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_copernicus',
    label='Copernicus CDSE',
    category='geography',
    icon='Satellite',
    description=(
        "Download satellite imagery from the Copernicus Data Space Ecosystem (CDSE). "
        "Sentinel-2 L2A/L1C, Sentinel-1 GRD, Copernicus DEM. "
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
        {'id': 'fetch',         'type': 'trigger','default': 0,  'label': 'Fetch'},
    ],
    resizable=True, min_width=280, min_height=200,
)
class GeoCopernicusNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._prev_fetch    = False
        self._loading       = False
        self._cache_data    = None   # (geo_dict, preview_bgr, thumb_b64)
        self._thumb_dirty   = False
        self._auto_tried    = False

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
    ) -> bool:
        """Download one tile to tile_path as float32 GeoTIFF. Returns True on success."""
        try:
            from sentinelhub import (
                BBox, CRS, SentinelHubRequest, MimeType, DatasetId
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
                send_notification('Copernicus: empty response from API', level='warning', notif_id=_NOTIF)
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
            send_notification(f'Copernicus tile error: {e}', level='error', notif_id=_NOTIF)
            return False

    # ── Main fetch logic ──────────────────────────────────────────────────────

    def _do_fetch(self, params: dict, auto: bool = False) -> None:
        try:
            self._do_fetch_impl(params, auto=auto)
        except BaseException as e:
            send_notification(f'Copernicus: unexpected crash: {e}', level='error', notif_id=_NOTIF)
        finally:
            self._loading = False

    def _do_fetch_impl(self, params: dict, auto: bool = False) -> None:
        if not self.ensure_packages(
            ['sentinelhub', 'rasterio'],
            pip_names=['sentinelhub', 'rasterio'],
            notif_id=_NOTIF,
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
                level='error', notif_id=_NOTIF,
            )
            return

        # ── Parameters ─────────────────────────────────────────────────────────
        bbox_str    = str(params.get('bbox', '') or '').strip()
        if not bbox_str:
            send_notification('Copernicus: no bounding box — open editor to draw ROI',
                              level='warning', notif_id=_NOTIF)
            return

        try:
            parts = [float(v) for v in bbox_str.split(',')]
            if len(parts) != 4:
                raise ValueError('need 4 values')
            west, south, east, north = parts
        except Exception:
            send_notification(f'Copernicus: invalid bbox "{bbox_str}"',
                              level='error', notif_id=_NOTIF)
            return

        col_names   = list(COLLECTIONS.keys())
        col_idx     = int(params.get('collection', 0))
        col_name    = col_names[col_idx] if 0 <= col_idx < len(col_names) else col_names[0]
        col_cfg     = COLLECTIONS[col_name]

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
        try:
            base_col = getattr(DataCollection, col_cfg['sh_id'])
            data_collection = base_col.define_from(
                f'{col_cfg["sh_id"]}_CDSE',
                service_url=_CDSE_BASE_URL,
            )
        except AttributeError:
            # DEM and other collections may be looked up differently
            data_collection = DataCollection.define_byoc(col_cfg['sh_id'])

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
            progress=0.05, notif_id=_NOTIF,
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

                tile_num = row * tile_cols + col + 1
                send_notification(
                    f'Copernicus: downloading tile {tile_num}/{n_tiles} '
                    f'({col+1},{row+1})…',
                    progress=0.10 + 0.75 * (tile_num - 1) / n_tiles,
                    notif_id=_NOTIF,
                )

                success = self._download_tile(
                    sh_config, data_collection, evalscript,
                    t_west, t_south, t_east, t_north,
                    tile_w, tile_h,
                    date_start, date_end,
                    cloud_max, col_cfg['has_cloud_filter'],
                    tile_path,
                )
                if not success:
                    return

        if all_cached:
            send_notification('Copernicus: all tiles cached', progress=0.85, notif_id=_NOTIF)

        # ── Stitch tiles ──────────────────────────────────────────────────────
        if n_tiles == 1:
            final_path = tile_paths[0][2]
        else:
            send_notification('Copernicus: stitching tiles…', progress=0.87, notif_id=_NOTIF)
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
                    send_notification(f'Copernicus: stitch error: {e}', level='error', notif_id=_NOTIF)
                    return

        # ── Load final GeoTIFF ────────────────────────────────────────────────
        send_notification('Copernicus: loading result…', progress=0.92, notif_id=_NOTIF)
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
            send_notification(f'Copernicus: load error: {e}', level='error', notif_id=_NOTIF)
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
            progress=1.0, notif_id=_NOTIF,
        )

    # ── process ───────────────────────────────────────────────────────────────

    def process(self, inputs: dict, params: dict) -> dict:
        fetch = bool(params.get('fetch', False))
        rising = fetch and not self._prev_fetch
        self._prev_fetch = fetch

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
