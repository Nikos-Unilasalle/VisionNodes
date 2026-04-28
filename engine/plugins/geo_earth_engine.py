from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import os
import hashlib
import math
import threading
import base64
import zipfile
import tempfile
import shutil
import cv2

try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

try:
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

COLLECTIONS = {
    'Sentinel-2 SR': {
        'ee_id': 'COPERNICUS/S2_SR_HARMONIZED',
        'bands':    ['B2', 'B3', 'B4', 'B8', 'B11', 'B12'],
        'rgb':      ['B4', 'B3', 'B2'],
        'rgb_nir':  ['B4', 'B3', 'B2', 'B8'],
        'cloud_prop': 'CLOUDY_PIXEL_PERCENTAGE',
        'scale': 10,
    },
    'Landsat-8 SR': {
        'ee_id': 'LANDSAT/LC08/C02/T1_L2',
        'bands':    ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
        'rgb':      ['SR_B4', 'SR_B3', 'SR_B2'],
        'rgb_nir':  ['SR_B4', 'SR_B3', 'SR_B2', 'SR_B5'],
        'cloud_prop': 'CLOUD_COVER',
        'scale': 30,
    },
    'MODIS Terra': {
        'ee_id': 'MODIS/006/MOD09GA',
        'bands':    ['sur_refl_b01', 'sur_refl_b02', 'sur_refl_b03', 'sur_refl_b04', 'sur_refl_b06', 'sur_refl_b07'],
        'rgb':      ['sur_refl_b01', 'sur_refl_b04', 'sur_refl_b03'],
        'rgb_nir':  ['sur_refl_b01', 'sur_refl_b04', 'sur_refl_b03', 'sur_refl_b02'],
        'cloud_prop': None,
        'scale': 500,
    },
}


@vision_node(
    type_id='geo_earth_engine',
    label='Earth Engine',
    category='src',
    icon='Map',
    description="Download satellite imagery from Google Earth Engine. Sentinel-2, Landsat-8, MODIS. Automatic local cache.",
    inputs=[],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview'},
        {'id': 'meta',    'color': 'dict',     'label': 'Meta'},
    ],
    params=[
        {'id': 'fetch',       'type': 'trigger', 'default': 0,               'label': 'Fetch'},
        {'id': 'gcp_project', 'type': 'string',  'default': '',              'label': 'GCP Project ID'},
        {'id': 'collection',  'type': 'enum',    'options': list(COLLECTIONS.keys()), 'default': 'Sentinel-2 SR', 'label': 'Collection'},
        {'id': 'location',    'type': 'string',  'default': 'Paris, France', 'label': 'Location or "lat,lon"'},
        {'id': 'date_start',  'type': 'string',  'default': '2024-01-01',    'label': 'Start Date'},
        {'id': 'date_end',    'type': 'string',  'default': '2024-06-01',    'label': 'End Date'},
        {'id': 'cloud_max',   'type': 'int',     'default': 20, 'min': 0, 'max': 100,  'label': 'Max Clouds %'},
        {'id': 'size_km',     'type': 'int',     'default': 10, 'min': 1, 'max': 100,  'label': 'ROI Size (km)'},
        {'id': 'scale_m',     'type': 'int',     'default': 30, 'min': 10, 'max': 1000,'label': 'Resolution (m/px)'},
        {'id': 'band_preset', 'type': 'enum',    'options': ['RGB', 'RGB+NIR', 'All'], 'default': 'RGB', 'label': 'Bands'},
        {'id': 'custom_bands','type': 'string',  'default': '',              'label': 'Bands (e.g. B8 — overrides preset)'},
        {'id': 'cache_dir',   'type': 'string',  'default': 'gee_cache',     'label': 'Cache Dir'},
    ]
)
class EarthEngineSourceNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._prev_fetch = False
        self._loading = False
        self._cache_data = None
        self._thumb_dirty = False
        self._ee_initialized = False

    # ------------------------------------------------------------------ helpers

    def _geocode(self, location):
        location = location.strip()
        parts = location.split(',')
        if len(parts) == 2:
            try:
                return float(parts[0].strip()), float(parts[1].strip())
            except ValueError:
                pass
        if not GEOPY_AVAILABLE:
            raise ValueError('Format "lat,lon" requis (geopy non installé)')
        try:
            geo = Nominatim(user_agent='vnstudio_gee').geocode(location, timeout=10)
            if geo:
                return geo.latitude, geo.longitude
            raise ValueError(f'Lieu introuvable: {location}')
        except Exception as e:
            raise ValueError(f'Geocoding: {e}')

    def _bbox(self, lat, lon, size_km):
        half_lat = (size_km / 2.0) / 111.0
        half_lon = (size_km / 2.0) / (111.0 * math.cos(math.radians(lat)))
        return lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat

    def _init_ee(self, gcp_project):
        if self._ee_initialized:
            return True
        try:
            ee.Initialize(project=gcp_project or None)
            self._ee_initialized = True
            return True
        except Exception:
            pass
        try:
            send_notification('GEE: authenticating — opening browser…', notif_id='gee_auth')
            ee.Authenticate()
            ee.Initialize(project=gcp_project or None)
            self._ee_initialized = True
            send_notification('GEE: authenticated', progress=1.0, notif_id='gee_auth')
            return True
        except Exception as e:
            send_notification(f'GEE auth failed: {e}', level='error', notif_id='gee_auth')
            return False

    def _stretch(self, band):
        valid = band[band != 0]
        if valid.size == 0:
            return np.zeros_like(band, dtype=np.uint8)
        p2, p98 = np.percentile(valid, (2, 98))
        if p98 == p2:
            return np.zeros_like(band, dtype=np.uint8)
        return np.clip((band - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------ fetch

    def _do_fetch(self, params):
        try:
            self._do_fetch_impl(params)
        except BaseException as e:
            send_notification(f'GEE: unexpected crash: {e}', level='error', notif_id='gee')
        finally:
            self._loading = False

    def _do_fetch_impl(self, params):
        if not EE_AVAILABLE:
            send_notification('earthengine-api missing: pip install earthengine-api', level='error', notif_id='gee')
            return
        if not RASTERIO_AVAILABLE:
            send_notification('rasterio missing: pip install rasterio', level='error', notif_id='gee')
            return

        gcp_project   = params.get('gcp_project', '').strip()
        col_name      = params.get('collection', 'Sentinel-2 SR')
        location      = params.get('location', 'Paris, France')
        date_start    = params.get('date_start', '2024-01-01')
        date_end      = params.get('date_end',   '2024-06-01')
        cloud_max     = int(params.get('cloud_max', 20))
        size_km       = int(params.get('size_km', 10))
        scale_m       = int(params.get('scale_m', 30))
        band_preset   = params.get('band_preset', 'RGB')
        custom_bands_str = (params.get('custom_bands', '') or '').strip()
        raw_cache     = (params.get('cache_dir', '') or '').strip()
        cache_dir     = raw_cache if os.path.isabs(raw_cache) else os.path.join(_ENGINE_DIR, raw_cache or 'gee_cache')
        col_cfg       = COLLECTIONS.get(col_name, COLLECTIONS['Sentinel-2 SR'])

        # Band selection — custom_bands takes priority if non-empty
        if custom_bands_str:
            selected_bands = [b.strip() for b in custom_bands_str.split(',') if b.strip()]
        elif band_preset == 'RGB':
            selected_bands = col_cfg.get('rgb',     col_cfg['bands'][:3])
        elif band_preset == 'RGB+NIR':
            selected_bands = col_cfg.get('rgb_nir', col_cfg['bands'][:4])
        else:  # 'All'
            selected_bands = col_cfg['bands']

        try:
            lat, lon = self._geocode(location)
        except ValueError as e:
            send_notification(str(e), level='error', notif_id='gee')
            return

        # Cache path — keyed on all relevant params including band selection
        bands_key = '_'.join(selected_bands)
        key_str  = f'{col_name}_{lat:.4f}_{lon:.4f}_{size_km}_{scale_m}_{date_start}_{date_end}_{cloud_max}_{bands_key}'
        key_hash = hashlib.md5(key_str.encode()).hexdigest()[:12]
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f'{key_hash}.tif')

        if os.path.exists(cache_path):
            send_notification(f'GEE: cache hit ({key_hash}.tif)', notif_id='gee')
        else:
            if not self._init_ee(gcp_project):
                return

            all_band_names = ', '.join(col_cfg['bands'])
            send_notification(
                f'GEE: fetching {col_name} — {location} | available bands: {all_band_names}',
                progress=0.1, notif_id='gee'
            )

            # Pixel grid from bbox + scale
            west, south, east, north = self._bbox(lat, lon, size_km)
            lat_c = (south + north) / 2
            scale_lon_deg = scale_m / (111320.0 * math.cos(math.radians(lat_c)))
            scale_lat_deg = scale_m / 111320.0
            width  = max(1, round((east - west)   / scale_lon_deg))
            height = max(1, round((north - south) / scale_lat_deg))

            # computePixels hard limit: 50,331,648 bytes (48 MiB)
            # Use 8 bytes/value (float64 worst case) + 10% safety margin for GEE overhead
            MAX_REQUEST_BYTES = 50_331_648
            n_bands = len(selected_bands)
            max_pixels = int(MAX_REQUEST_BYTES * 0.90) // (n_bands * 8)
            if width * height > max_pixels:
                factor = math.sqrt(width * height / max_pixels)
                width  = max(1, int(width  / factor))   # int = floor, never rounds up
                height = max(1, int(height / factor))
                # Trim one row if still slightly over due to int arithmetic
                while width * height > max_pixels and height > 1:
                    height -= 1
                send_notification(
                    f'GEE: image reduced to {width}×{height} px '
                    f'({width * height * n_bands * 8 / 1024 / 1024:.1f}MB worst-case). '
                    f'Increase scale_m to avoid reduction.',
                    notif_id='gee'
                )
            est_mb = width * height * n_bands * 8 / 1024 / 1024

            try:
                bbox = ee.Geometry.Rectangle([west, south, east, north])
                col = ee.ImageCollection(col_cfg['ee_id']) \
                    .filterDate(date_start, date_end) \
                    .filterBounds(bbox)

                if col_cfg['cloud_prop']:
                    col = col.filter(ee.Filter.lt(col_cfg['cloud_prop'], cloud_max))

                n_images = col.size().getInfo()
                if n_images == 0:
                    send_notification(
                        f'GEE: no images found for {location} between {date_start} and {date_end}. '
                        f'Check dates or increase cloud_max.',
                        level='error', notif_id='gee'
                    )
                    return
                send_notification(f'GEE: {n_images} images — median composite…', progress=0.2, notif_id='gee')

                image = col.median().select(selected_bands)

                send_notification(
                    f'GEE: computePixels {width}×{height} px — {len(selected_bands)} bandes '
                    f'[{", ".join(selected_bands)}] (~{est_mb:.1f}MB worst-case)…',
                    progress=0.35, notif_id='gee'
                )

                raw = ee.data.computePixels({
                    'expression': image,
                    'fileFormat': 'GEO_TIFF',
                    'bandIds':    selected_bands,
                    'grid': {
                        'dimensions': {'width': width, 'height': height},
                        'affineTransform': {
                            'scaleX':     scale_lon_deg,
                            'shearX':     0,
                            'translateX': west,
                            'shearY':     0,
                            'scaleY':    -scale_lat_deg,
                            'translateY': north,
                        },
                        'crsCode': 'EPSG:4326',
                    },
                })

                with open(cache_path, 'wb') as f:
                    f.write(raw)

            except Exception as e:
                msg = str(e)
                if 'request size' in msg.lower() or 'too large' in msg.lower():
                    # EE rejected despite our pre-check — halve and retry once
                    width  = max(1, width  // 2)
                    height = max(1, height // 2)
                    send_notification(
                        f'GEE: size limit exceeded, retrying at {width}×{height}…',
                        notif_id='gee'
                    )
                    try:
                        raw = ee.data.computePixels({
                            'expression': image,
                            'fileFormat': 'GEO_TIFF',
                            'bandIds':    selected_bands,
                            'grid': {
                                'dimensions': {'width': width, 'height': height},
                                'affineTransform': {
                                    'scaleX':     scale_lon_deg,
                                    'shearX':     0,
                                    'translateX': west,
                                    'shearY':     0,
                                    'scaleY':    -scale_lat_deg,
                                    'translateY': north,
                                },
                                'crsCode': 'EPSG:4326',
                            },
                        })
                        with open(cache_path, 'wb') as f:
                            f.write(raw)
                    except Exception as e2:
                        send_notification(f'GEE: retry failed: {e2}', level='error', notif_id='gee')
                        return
                elif 'quota' in msg.lower():
                    send_notification(
                        f'GEE: quota exceeded — try again later. ({e})',
                        level='error', notif_id='gee'
                    )
                    return
                else:
                    send_notification(f'GEE error: {e}', level='error', notif_id='gee')
                    return

        # Load from disk — handle ZIP (GEE sometimes wraps multi-band TIFFs in ZIP)
        try:
            tif_to_open = cache_path
            tmp_dir = None

            if zipfile.is_zipfile(cache_path):
                send_notification('GEE: extracting ZIP…', progress=0.92, notif_id='gee')
                tmp_dir = tempfile.mkdtemp(prefix='gee_unzip_')
                with zipfile.ZipFile(cache_path, 'r') as zf:
                    zf.extractall(tmp_dir)
                tif_files = sorted(
                    [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith('.tif')]
                )
                if not tif_files:
                    raise ValueError('ZIP téléchargé ne contient pas de fichiers .tif')
                if len(tif_files) == 1:
                    tif_to_open = tif_files[0]
                else:
                    # Multiple single-band TIFs — merge into one multi-band
                    merged_path = os.path.join(tmp_dir, 'merged.tif')
                    srcs = [rasterio.open(f) for f in tif_files]
                    profile = srcs[0].profile.copy()
                    profile.update(count=len(srcs))
                    with rasterio.open(merged_path, 'w', **profile) as dst:
                        for i, s in enumerate(srcs, 1):
                            dst.write(s.read(1), i)
                    for s in srcs:
                        s.close()
                    tif_to_open = merged_path

            with rasterio.open(tif_to_open) as src:
                est_mb_load = src.width * src.height * src.count * 4 / 1024 / 1024
                if est_mb_load > 512:
                    send_notification(
                        f'GEE: image too large to load ({est_mb_load:.0f}MB). '
                        f'Increase scale_m or reduce size_km.',
                        level='error', notif_id='gee'
                    )
                    if tmp_dir:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    return
                bands = src.read().astype(np.float32)
                if src.nodata is not None:
                    bands[bands == src.nodata] = 0
                actual_band_names = selected_bands[:src.count]
                geo = {
                    'bands':      bands,
                    'band_names': actual_band_names,
                    'crs':        str(src.crs) if src.crs else None,
                    'transform':  src.transform,
                    'nodata':     src.nodata,
                    'count':      src.count,
                    'width':      src.width,
                    'height':     src.height,
                    'dtype':      str(src.dtypes[0]),
                    'bounds': {
                        'west':  src.bounds.left,
                        'south': src.bounds.bottom,
                        'east':  src.bounds.right,
                        'north': src.bounds.top,
                    },
                    '_source':     col_name,
                    '_location':   location,
                    '_dates':      f'{date_start} → {date_end}',
                    '_cache_path': cache_path,
                }

            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

            # True-color preview — find R/G/B by band name, fallback to index order
            count = geo['count']
            band_names = geo['band_names']
            rgb_def = col_cfg.get('rgb', [])

            if len(rgb_def) == 3 and all(b in band_names for b in rgb_def):
                ri = band_names.index(rgb_def[0])
                gi = band_names.index(rgb_def[1])
                bi = band_names.index(rgb_def[2])
            else:
                ri, gi, bi = min(0, count-1), min(1, count-1), min(2, count-1)

            r = self._stretch(bands[ri])
            g = self._stretch(bands[gi])
            b = self._stretch(bands[bi])
            preview = cv2.merge([b, g, r])


            h, w = preview.shape[:2]
            sc = 120 / h
            thumb = cv2.resize(preview, (max(1, int(w * sc)), 120))
            _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
            _thumb = base64.b64encode(buf).decode('utf-8')

            self._cache_data = (geo, preview, _thumb)
            self._thumb_dirty = True
            send_notification(
                f'GEE: ready — {count} bands, {geo["width"]}×{geo["height"]} px',
                progress=1.0, notif_id='gee'
            )

        except Exception as e:
            send_notification(f'GEE: cache read error: {e}', level='error', notif_id='gee')

    # ------------------------------------------------------------------ process

    def process(self, inputs, params):
        fetch = bool(params.get('fetch', False))
        rising_edge = fetch and not self._prev_fetch
        self._prev_fetch = fetch

        if rising_edge and not self._loading:
            self._loading = True
            threading.Thread(target=self._do_fetch, args=(params,), daemon=True).start()

        if self._cache_data is None:
            return {'geotiff': None, 'preview': None, 'meta': None}

        geo, preview, _thumb = self._cache_data
        meta = {
            'source':     geo.get('_source'),
            'location':   geo.get('_location'),
            'dates':      geo.get('_dates'),
            'crs':        geo['crs'],
            'band_count': geo['count'],
            'width':      geo['width'],
            'height':     geo['height'],
            'cache_path': geo.get('_cache_path'),
            'band_names': geo['band_names'],
        }
        out_thumb = _thumb if self._thumb_dirty else None
        self._thumb_dirty = False
        return {'geotiff': geo, 'preview': preview, 'meta': meta, '_thumb': out_thumb}
