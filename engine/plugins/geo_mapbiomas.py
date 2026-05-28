"""
geo_mapbiomas.py — Independent LULC reference for cross-validation

Two data sources tried in order:

  1. MapBiomas Amazônia (GCS public COG, 30 m Landsat-based)
     Has specific Mangrove class (41) — best match for our use case.
     Key classes: 3=Forest, 6=Flooded Forest, 11=Wetland, 25=Bare,
                  30=Mining/Orpaillage, 33=Water, 41=Mangrove

  2. IO-LULC Annual v02 — Impact Observatory (Planetary Computer, 10 m S2-based)
     Fallback when MapBiomas GCS unreachable. No dedicated Mangrove class;
     class 4 (Flooded vegetation) covers mangroves + wetlands.
     Key classes: 1=Water, 2=Trees, 4=Flooded veg, 7=Built, 8=Bare, 11=Rangeland

Both are fully independent of ESA WorldCover (different sensor, algorithm, org).

Typical use:
  geo_mapbiomas → geo_map_agreement (with RF classmap) → Cohen's κ / Fig 6
"""
from __future__ import annotations
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_mapbiomas'

# ── GDAL / HTTP settings ─────────────────────────────────────────────────────
_GDAL_COG_CFG: dict[str, object] = {
    'GDAL_HTTP_TIMEOUT': 30,
    'GDAL_HTTP_CONNECTTIMEOUT': 10,
    'GDAL_HTTP_MAX_RETRY': 3,
    'GDAL_HTTP_RETRY_DELAY': 2,
    'GDAL_DISABLE_READDIR_ON_OPEN': 'EMPTY_DIR',
    'GDAL_HTTP_MERGE_CONSECUTIVE_RANGES': 'YES',
    'GDAL_HTTP_MULTIPLEX': 'YES',
    'CPL_VSIL_CURL_CHUNK_SIZE': 10485760,
    'GDAL_CACHEMAX': 512,
}

# BGR palette — MapBiomas classes
_PALETTE_MB: dict[int, tuple[int, int, int]] = {
    3:  (34,  139, 34),    # Forest Formation  — green
    6:  (0,   100, 0),     # Flooded Forest    — dark green
    11: (209, 206, 0),     # Wetland           — teal/BGR
    25: (140, 180, 210),   # Non-vegetated     — tan
    30: (43,  90,  139),   # Mining            — brown
    33: (255, 30,  30),    # Water             — blue/BGR
    41: (20,  60,  0),     # Mangrove          — very dark green
}

# BGR palette — IO-LULC classes
_PALETTE_IO: dict[int, tuple[int, int, int]] = {
    1:  (255, 30,  30),    # Water             — blue/BGR
    2:  (34,  139, 34),    # Trees             — green
    4:  (0,   160, 120),   # Flooded veg       — teal
    5:  (200, 200, 100),   # Crops             — yellow
    7:  (120, 120, 180),   # Built             — gray-blue
    8:  (140, 180, 210),   # Bare              — tan
    9:  (240, 250, 255),   # Snow              — white
    11: (180, 200, 120),   # Rangeland         — pale green
}

# ── MapBiomas GCS URL patterns (Amazônia, descending collection priority) ────
_MB_GCS_AMAZONIA = [
    'https://storage.googleapis.com/mapbiomas-public/amazonia/collection-9/lclu/coverage/amazonia_coverage_{year}.tif',
    'https://storage.googleapis.com/mapbiomas-public/amazonia/collection-8/lclu/coverage/amazonia_coverage_{year}.tif',
    'https://storage.googleapis.com/mapbiomas-public/initiatives/amazonia/collection_9/classification/{year}/amazonia_coverage_{year}.tif',
    'https://storage.googleapis.com/mapbiomas-public/brasil/collection-9/lclu/coverage/brasil_coverage_{year}.tif',
]

# ── Planetary Computer STAC (IO-LULC fallback) ───────────────────────────────
_PC_STAC        = 'https://planetarycomputer.microsoft.com/api/stac/v1'
_IO_LULC_COLL   = 'io-lulc-annual-v02'


def _log(msg: str) -> None:
    print(f'[geo_mapbiomas] {msg}', file=sys.stderr, flush=True)


def _colorize(arr: np.ndarray, palette: dict[int, tuple[int, int, int]]) -> np.ndarray:
    rgb = np.zeros((*arr.shape, 3), dtype=np.uint8)
    for cls_val, bgr in palette.items():
        rgb[arr == cls_val] = bgr
    return rgb


def _read_cog(
    href: str,
    bbox: tuple[float, float, float, float],
    resolution: int,
) -> np.ndarray | None:
    """Windowed COG read → reproject to EPSG:4326. Nearest-neighbor (categorical)."""
    import rasterio
    from rasterio.crs import CRS
    from rasterio.warp import reproject, Resampling, transform_bounds
    from rasterio.transform import from_bounds, Affine

    lon_min, lat_min, lon_max, lat_max = bbox
    target_crs = CRS.from_epsg(4326)
    deg_per_px  = resolution / 111_320
    out_w = max(1, int(round((lon_max - lon_min) / deg_per_px)))
    out_h = max(1, int(round((lat_max - lat_min) / deg_per_px)))

    t0 = time.time()
    try:
        with rasterio.Env(**_GDAL_COG_CFG):
            with rasterio.open(href) as src:
                _log(f'  opened CRS={src.crs}  size={src.width}×{src.height}')
                src_bbox = transform_bounds(target_crs, src.crs, *bbox)
                win      = src.window(*src_bbox)
                win_h    = max(1, int(win.height))
                win_w    = max(1, int(win.width))
                win_tf   = src.window_transform(win)

                _log(f'  window={win_w}×{win_h}  out={out_w}×{out_h}')
                data = src.read(
                    1, window=win,
                    out_shape=(out_h, out_w),
                    resampling=Resampling.nearest,
                    boundless=True, fill_value=0,
                )
                row_scale = win_h / out_h
                col_scale = win_w / out_w
                win_tf_s  = Affine(
                    win_tf.a * col_scale, win_tf.b, win_tf.c,
                    win_tf.d, win_tf.e * row_scale, win_tf.f,
                )
                src_crs = src.crs

        dst    = np.zeros((out_h, out_w), dtype=data.dtype)
        dst_tf = from_bounds(lon_min, lat_min, lon_max, lat_max, out_w, out_h)
        reproject(
            source=data, destination=dst,
            src_transform=win_tf_s, src_crs=src_crs,
            dst_transform=dst_tf, dst_crs=target_crs,
            resampling=Resampling.nearest,
        )
        elapsed = time.time() - t0
        _log(f'  done in {elapsed:.1f}s  valid_px={int(np.sum(dst > 0))}')
        return dst

    except Exception as e:
        _log(f'  COG read error: {e}')
        return None


def _try_mapbiomas_gcs(year: int, bbox: tuple, resolution: int, timeout: int) -> tuple[np.ndarray | None, str]:
    """Try MapBiomas GCS COG URLs. Returns (array, source_label)."""
    for pattern in _MB_GCS_AMAZONIA:
        href = pattern.format(year=year)
        _log(f'MapBiomas GCS: {href}')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_read_cog, href, bbox, resolution)
            try:
                arr = future.result(timeout=timeout)
                if arr is not None and arr.size > 0 and np.any(arr > 0):
                    _log(f'MapBiomas GCS succeeded: {href}')
                    return arr, 'MapBiomas Amazônia (GCS)'
            except FuturesTimeout:
                _log(f'  timeout after {timeout}s')
    return None, ''


def _try_io_lulc(year: int, bbox: tuple, resolution: int, timeout: int) -> tuple[np.ndarray | None, str]:
    """Fetch IO-LULC Annual v02 from Planetary Computer. Tries all items until valid data found."""
    try:
        from pystac_client import Client
        import planetary_computer as pc
    except ImportError:
        _log('pystac-client or planetary-computer not installed')
        return None, ''

    _log(f'IO-LULC: querying Planetary Computer  year={year}')
    try:
        client = Client.open(_PC_STAC, modifier=pc.sign_inplace)
        results = client.search(
            collections=[_IO_LULC_COLL],
            bbox=list(bbox),
            datetime=f'{year}-01-01/{year}-12-31',
            max_items=10,   # more items — each covers one UTM zone tile
        )
        items = list(results.items())
        _log(f'IO-LULC: {len(items)} items found')
        if not items:
            return None, ''

        # STAC returns all tiles whose bbox overlaps the query — each item is one UTM zone.
        # French Guiana (lon ~-53) = UTM zone 22N. Loop until valid_px > 0.
        for item in items:
            _log(f'  item={item.id}  assets={list(item.assets)}')
            for key in ('data', 'supercell', 'rendered_preview'):
                if key in item.assets:
                    href = item.assets[key].href
                    break
            else:
                href = item.assets[next(iter(item.assets))].href

            _log(f'  asset href={href[:100]}')
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_read_cog, href, bbox, resolution)
                try:
                    arr = future.result(timeout=timeout)
                    if arr is not None and np.any(arr > 0):
                        _log(f'  valid tile: {item.id}')
                        return arr, 'IO-LULC Annual v02 (Planetary Computer)'
                    _log(f'  valid_px=0 — skipping tile {item.id}')
                except FuturesTimeout:
                    _log(f'  timeout after {timeout}s on tile {item.id}')

    except Exception as e:
        _log(f'IO-LULC error: {e}')

    return None, ''


@vision_node(
    type_id='geo_mapbiomas',
    label='MapBiomas / IO-LULC',
    category='remote sensing',
    icon='Map',
    description=(
        'Independent LULC reference map for cross-validating RF classifiers trained on WorldCover. '
        'Tries MapBiomas Amazônia (GCS COG, 30 m, Mangrove class 41) first. '
        'Falls back to IO-LULC Annual v02 via Planetary Computer (10 m S2-based, '
        'class 4 = Flooded vegetation covers mangroves). '
        'Both sources are independent of ESA WorldCover. '
        'Connect to geo_map_agreement for Cohen\'s kappa (Fig 6).'
    ),
    inputs=[],
    outputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'LULC geo dict (1 band, class values)'},
        {'id': 'preview',  'color': 'image',   'label': 'Colorized LULC preview'},
    ],
    params=[
        {
            'id': 'bbox', 'type': 'string',
            'default': '-53.30,4.40,-52.60,5.50',
            'label': 'Bounding box (lon_min,lat_min,lon_max,lat_max)',
        },
        {
            'id': 'year', 'type': 'int',
            'default': 2023, 'min': 2015, 'max': 2024,
            'label': 'Year',
        },
        {
            'id': 'source', 'type': 'enum',
            'default': 0,
            'options': ['MapBiomas then IO-LULC (auto)', 'MapBiomas only', 'IO-LULC only'],
            'label': 'Data source',
        },
        {
            'id': 'resolution', 'type': 'int',
            'default': 30, 'min': 10, 'max': 100,
            'label': 'Output resolution (m)',
        },
        {
            'id': 'timeout', 'type': 'int',
            'default': 90, 'min': 30, 'max': 600,
            'label': 'COG read timeout per attempt (s)',
        },
        {'id': 'fetch',     'type': 'trigger', 'default': 0, 'label': 'Fetch'},
        {'id': 'node_note', 'type': 'string',  'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GeoMapBiomasNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        from rasterio.transform import from_bounds

        # ── Parse params ─────────────────────────────────────────────────────
        bbox_str   = str(params.get('bbox', '-53.30,4.40,-52.60,5.50')).strip()
        year       = int(params.get('year', 2023))
        source_idx = int(params.get('source', 0))
        resolution = max(10, int(params.get('resolution', 30)))
        timeout    = max(30, int(params.get('timeout', 90)))

        try:
            parts = [float(x.strip()) for x in bbox_str.split(',')]
            if len(parts) != 4:
                raise ValueError('need 4 values')
            bbox: tuple[float, float, float, float] = tuple(parts)  # type: ignore[assignment]
        except Exception:
            send_notification(
                'MapBiomas: invalid bbox — expected lon_min,lat_min,lon_max,lat_max',
                level='error', notif_id=_NOTIF,
            )
            return {}

        lon_min, lat_min, lon_max, lat_max = bbox
        _log(f'bbox={bbox}  year={year}  source={source_idx}  res={resolution}m')

        arr: np.ndarray | None = None
        source_label = ''
        palette = _PALETTE_MB

        # ── Try sources in order ─────────────────────────────────────────────
        if source_idx in (0, 1):   # MapBiomas GCS
            send_notification('Trying MapBiomas GCS COG…', notif_id=_NOTIF)
            arr, source_label = _try_mapbiomas_gcs(year, bbox, resolution, timeout)
            palette = _PALETTE_MB

        if arr is None and source_idx in (0, 2):   # IO-LULC fallback / only
            if source_idx == 0:
                send_notification(
                    'MapBiomas GCS unavailable — falling back to IO-LULC (Planetary Computer)…',
                    notif_id=_NOTIF,
                )
            else:
                send_notification('Fetching IO-LULC from Planetary Computer…', notif_id=_NOTIF)
            arr, source_label = _try_io_lulc(year, bbox, resolution, timeout)
            palette = _PALETTE_IO

        if arr is None or arr.size == 0:
            send_notification(
                'MapBiomas/IO-LULC: all sources failed — check engine console',
                level='error', notif_id=_NOTIF,
            )
            return {}

        # ── Build geo dict ───────────────────────────────────────────────────
        out_h, out_w = arr.shape
        transform    = from_bounds(lon_min, lat_min, lon_max, lat_max, out_w, out_h)

        geo: dict = {
            'bands':      arr[np.newaxis].astype(np.uint8),
            'crs':        'EPSG:4326',
            'transform':  transform,
            'count':      1,
            'height':     out_h,
            'width':      out_w,
            'dtype':      'uint8',
            'band_names': ['lulc_class'],
        }

        preview = _colorize(arr, palette)

        classes, counts = np.unique(arr[arr > 0], return_counts=True)
        summary = ' · '.join(f'cls{int(c)}={int(n):,}px' for c, n in zip(classes, counts))
        _log(f'{source_label}: {summary}')

        send_notification(
            f'{source_label}: {out_w}×{out_h}px  {summary}',
            progress=1.0, notif_id=_NOTIF,
        )

        return {'geotiff': geo, 'preview': preview}
