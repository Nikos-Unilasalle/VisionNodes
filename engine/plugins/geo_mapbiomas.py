"""
geo_mapbiomas.py — MapBiomas Annual Land Use / Land Cover (independent validation layer)

Fetches MapBiomas LULC for a bounding box and year via the MapBiomas STAC
catalog (https://stac.mapbiomas.org/). Falls back to Brazil Data Cube STAC.
Outputs a 1-band geo dict (uint8 class values) for cross-validation against
an RF classifier trained on WorldCover labels.

MapBiomas Amazônia covers French Guiana (pan-Amazon perimeter).

Key classes — Amazônia collection:
  3  = Forest Formation
  6  = Flooded Forest
  11 = Wetland / Herbaceous
  25 = Other Non-Vegetated / Bare
  30 = Mining / Orpaillage       ← WorldCover 60
  33 = Permanent Water           ← WorldCover 80
  41 = Mangrove                  ← WorldCover 95

Typical use:
  geo_mapbiomas → geo_map_agreement (with RF classmap) → Cohen's kappa / Fig 6
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

# BGR palette for OpenCV preview
_PALETTE_BGR: dict[int, tuple[int, int, int]] = {
    3:  (34,  139, 34),    # Forest Formation  — green
    6:  (0,   100, 0),     # Flooded Forest    — dark green
    11: (209, 206, 0),     # Wetland           — teal (BGR)
    25: (140, 180, 210),   # Non-vegetated     — tan
    30: (43,  90,  139),   # Mining            — brown
    33: (255, 30,  30),    # Water             — blue (BGR)
    41: (20,  60,  0),     # Mangrove          — very dark green
}

# STAC endpoints tried in order
_STAC_URLS: list[str] = [
    'https://stac.mapbiomas.org/',
    'https://brazildatacube.dpi.inpe.br/stac/',
]

# Collection ID candidates per collection index
_COLLECTION_CANDIDATES: list[list[str]] = [
    [   # 0 — Amazônia (French Guiana)
        'mapbiomas-amazon',
        'mapbiomas-amazonia',
        'annual-mapping-collection-9.0-amazonia',
        'annual-mapping-collection-8.0-amazonia',
    ],
    [   # 1 — Brasil
        'mapbiomas-brazil',
        'mapbiomas-brasil',
        'annual-mapping-collection-9.0-brazil',
        'annual-mapping-collection-8.0-brazil',
        'mapbiomas',
    ],
]

# Common asset key names that hold the classification layer
_ASSET_KEYS: list[str] = [
    'classification', 'lulc', 'data', 'lccs_class', 'map', 'visual',
]


def _log(msg: str) -> None:
    print(f'[geo_mapbiomas] {msg}', file=sys.stderr, flush=True)


def _colorize(arr: np.ndarray) -> np.ndarray:
    """Convert class array (H, W) → BGR preview (H, W, 3)."""
    rgb = np.zeros((*arr.shape, 3), dtype=np.uint8)
    for cls_val, bgr in _PALETTE_BGR.items():
        rgb[arr == cls_val] = bgr
    return rgb


def _read_cog(
    href: str,
    bbox: tuple[float, float, float, float],
    resolution: int,
) -> np.ndarray | None:
    """Windowed COG read with overview selection + reproject to EPSG:4326."""
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

                src_bbox  = transform_bounds(target_crs, src.crs, *bbox)
                win       = src.window(*src_bbox)
                win_h     = max(1, int(win.height))
                win_w     = max(1, int(win.width))
                win_tf    = src.window_transform(win)

                _log(f'  window={win_w}×{win_h}  out={out_w}×{out_h}')

                # nearest-neighbor mandatory for categorical data
                data = src.read(
                    1,
                    window=win,
                    out_shape=(out_h, out_w),
                    resampling=Resampling.nearest,
                    boundless=True,
                    fill_value=0,
                )
                # adjust transform for resampled read
                row_scale = win_h / out_h
                col_scale = win_w / out_w
                win_tf_scaled = Affine(
                    win_tf.a * col_scale, win_tf.b, win_tf.c,
                    win_tf.d, win_tf.e * row_scale, win_tf.f,
                )
                src_crs = src.crs

        dst    = np.zeros((out_h, out_w), dtype=data.dtype)
        dst_tf = from_bounds(lon_min, lat_min, lon_max, lat_max, out_w, out_h)
        reproject(
            source=data, destination=dst,
            src_transform=win_tf_scaled, src_crs=src_crs,
            dst_transform=dst_tf, dst_crs=target_crs,
            resampling=Resampling.nearest,
        )
        elapsed = time.time() - t0
        valid   = int(np.sum(dst > 0))
        _log(f'  done in {elapsed:.1f}s  valid_px={valid}')
        return dst

    except Exception as e:
        _log(f'  COG read error: {e}')
        return None


def _fetch_href(collection_idx: int, year: int, bbox: list[float]) -> str | None:
    """Query MapBiomas STAC. Return first matching asset href."""
    try:
        from pystac_client import Client
    except ImportError:
        _log('pystac-client not installed — pip install pystac-client')
        return None

    candidates = _COLLECTION_CANDIDATES[collection_idx]

    for stac_url in _STAC_URLS:
        _log(f'trying STAC {stac_url}')
        try:
            client = Client.open(stac_url)
        except Exception as e:
            _log(f'  open failed: {e}')
            continue

        for coll_id in candidates:
            try:
                results = client.search(
                    collections=[coll_id],
                    bbox=bbox,
                    datetime=f'{year}-01-01/{year}-12-31',
                    max_items=5,
                )
                items = list(results.items())
                if not items:
                    _log(f'  {coll_id}: 0 items')
                    continue
                item = items[0]
                _log(f'  item {item.id} in {coll_id}  assets={list(item.assets)}')

                # try known asset keys first
                for key in _ASSET_KEYS:
                    if key in item.assets:
                        href = item.assets[key].href
                        _log(f'  asset={key}  href={href[:100]}')
                        return href

                # fall back to first available asset
                first_key = next(iter(item.assets))
                href = item.assets[first_key].href
                _log(f'  asset={first_key} (fallback)  href={href[:100]}')
                return href

            except Exception as e:
                _log(f'  {coll_id}: {e}')

    return None


@vision_node(
    type_id='geo_mapbiomas',
    label='MapBiomas LULC',
    category='remote sensing',
    icon='Map',
    description=(
        'Fetches MapBiomas Annual Land Use / Land Cover for a bounding box and year '
        'via the MapBiomas STAC catalog. Outputs a 1-band geo dict (uint8 class values) '
        'suitable for cross-validation against RF classifiers trained on WorldCover labels. '
        'MapBiomas Amazônia (collection 0) covers French Guiana. '
        'Key classes: 3=Forest, 6=Flooded Forest, 11=Wetland, 25=Bare/Non-veg, '
        '30=Mining/Orpaillage, 33=Water, 41=Mangrove.'
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
            'id': 'collection', 'type': 'enum',
            'default': 0,
            'options': ['Amazônia (French Guiana)', 'Brasil'],
            'label': 'MapBiomas collection',
        },
        {
            'id': 'resolution', 'type': 'int',
            'default': 30, 'min': 10, 'max': 100,
            'label': 'Output resolution (m)',
        },
        {
            'id': 'timeout', 'type': 'int',
            'default': 120, 'min': 30, 'max': 600,
            'label': 'COG read timeout (s)',
        },
        {'id': 'fetch',     'type': 'trigger', 'default': 0, 'label': 'Fetch'},
        {'id': 'node_note', 'type': 'string',  'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GeoMapBiomasNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        from rasterio.transform import from_bounds

        # ── Parse params ────────────────────────────────────────────────────
        bbox_str   = str(params.get('bbox', '-53.30,4.40,-52.60,5.50')).strip()
        year       = int(params.get('year', 2023))
        coll_idx   = int(params.get('collection', 0))
        resolution = max(10, int(params.get('resolution', 30)))
        timeout    = max(30, int(params.get('timeout', 120)))

        try:
            parts = [float(x.strip()) for x in bbox_str.split(',')]
            if len(parts) != 4:
                raise ValueError('need 4 values')
            lon_min, lat_min, lon_max, lat_max = parts
        except Exception:
            send_notification(
                'MapBiomas: invalid bbox — expected lon_min,lat_min,lon_max,lat_max',
                level='error', notif_id=_NOTIF,
            )
            return {}

        bbox = (lon_min, lat_min, lon_max, lat_max)
        _log(f'bbox={bbox}  year={year}  collection={coll_idx}  res={resolution}m')

        # ── STAC search ──────────────────────────────────────────────────────
        send_notification('MapBiomas: searching STAC catalog…', notif_id=_NOTIF)
        href = _fetch_href(coll_idx, year, list(bbox))

        if href is None:
            send_notification(
                'MapBiomas: STAC search failed — see engine console for details. '
                'Try adjusting year or collection.',
                level='error', notif_id=_NOTIF,
            )
            return {}

        # ── COG read ─────────────────────────────────────────────────────────
        send_notification('MapBiomas: reading COG tile…', notif_id=_NOTIF)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_read_cog, href, bbox, resolution)
            try:
                arr = future.result(timeout=timeout)
            except FuturesTimeout:
                send_notification(
                    f'MapBiomas: COG read timed out after {timeout}s — try increasing timeout',
                    level='error', notif_id=_NOTIF,
                )
                return {}

        if arr is None or arr.size == 0:
            send_notification('MapBiomas: COG read failed', level='error', notif_id=_NOTIF)
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
            'band_names': ['mapbiomas_class'],
        }

        preview = _colorize(arr)

        # ── Summary notification ────────────────────────────────────────────
        classes, counts = np.unique(arr[arr > 0], return_counts=True)
        summary = ' · '.join(f'{int(c)}={int(n):,}px' for c, n in zip(classes, counts))
        _log(f'classes: {summary}')

        send_notification(
            f'MapBiomas {year}: {out_w}×{out_h}px  {summary}',
            progress=1.0, notif_id=_NOTIF,
        )

        return {'geotiff': geo, 'preview': preview}
