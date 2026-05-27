"""
geo_planetary_lulc.py — Annual land-use/land-cover from Microsoft Planetary
Computer (no authentication, 10 m resolution).

Two collections, complementary:

  - **esa-worldcover**       2020 + 2021. Single global model, 11 classes
                             INCLUDING explicit `Mangroves` (95) and
                             `Herbaceous wetland` (90). Best ground truth
                             for mangrove extent at 10 m.

  - **io-lulc-annual-v02**   Impact Observatory / Esri, 2017–2024 annual.
                             11 classes including `Flooded vegetation` (4),
                             `Water` (1), `Built area` (7), `Bare ground` (8).
                             Best for *change detection* and *orpaillage*
                             (forest → bare ground inside Amazon).

The node fetches a single representative year (latest scene within the date
range) and returns a categorical raster + per-class colormap legend.
"""
from __future__ import annotations
import os
import json
import hashlib
from pathlib import Path

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'planetary_lulc'
_STAC_URL = 'https://planetarycomputer.microsoft.com/api/stac/v1'

# ── Class definitions and palettes ───────────────────────────────────────────

WORLDCOVER_CLASSES = {
    10: ('Tree cover',          (0,   100, 0)),
    20: ('Shrubland',           (255, 187, 34)),
    30: ('Grassland',           (255, 255, 76)),
    40: ('Cropland',            (240, 150, 255)),
    50: ('Built-up',            (250, 0,   0)),
    60: ('Bare/sparse',         (180, 180, 180)),
    70: ('Snow and ice',        (240, 240, 240)),
    80: ('Permanent water',     (0,   100, 200)),
    90: ('Herbaceous wetland',  (0,   150, 160)),
    95: ('Mangroves',           (0,   207, 117)),
    100:('Moss and lichen',     (250, 230, 160)),
}

IO_LULC_CLASSES = {
    1:  ('Water',                 (26,  91,  171)),
    2:  ('Trees',                 (53,  130, 33)),
    4:  ('Flooded vegetation',    (123, 196, 174)),
    5:  ('Crops',                 (255, 219, 92)),
    7:  ('Built area',            (194, 30,  30)),
    8:  ('Bare ground',           (149, 113, 75)),
    9:  ('Snow/Ice',              (245, 245, 245)),
    10: ('Clouds',                (200, 200, 220)),
    11: ('Rangeland',             (177, 175, 79)),
}

COLLECTION_DEFS = {
    'esa-worldcover':       {'classes': WORLDCOVER_CLASSES, 'asset': 'map'},
    'io-lulc-annual-v02':   {'classes': IO_LULC_CLASSES,    'asset': 'data'},
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_packages() -> tuple[bool, str]:
    try:
        import rasterio  # noqa: F401
        import pystac_client  # noqa: F401
        import planetary_computer  # noqa: F401
        return True, ''
    except ImportError as e:
        return False, f'missing package {e.name} (pip install pystac-client planetary-computer rasterio)'


def _parse_bbox(s: str) -> list[float] | None:
    try:
        vals = [float(x.strip()) for x in s.split(',')]
        if len(vals) != 4:
            return None
        if vals[0] >= vals[2] or vals[1] >= vals[3]:
            return None
        return vals
    except (ValueError, AttributeError):
        return None


def _params_hash(params: dict) -> str:
    keys = ('bbox', 'date_start', 'date_end', 'collection', 'resolution')
    return hashlib.md5(
        json.dumps({k: params.get(k) for k in keys}, sort_keys=True).encode()
    ).hexdigest()[:14]


def _render_legend(classes_present: dict[int, int],
                   class_defs: dict[int, tuple[str, tuple[int, int, int]]],
                   total: int) -> np.ndarray:
    """Render a class legend showing label, color swatch, and area share."""
    items = [(v, class_defs[v][0], class_defs[v][1], n)
             for v, n in classes_present.items() if v in class_defs]
    items.sort(key=lambda x: -x[3])  # most-frequent first

    w = 460
    line_h = 22
    h = max(60, 40 + line_h * len(items))
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, 'Land Cover Classes', (8, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)

    for i, (code, name, (r, g, b), n) in enumerate(items):
        y = 38 + i * line_h
        cv2.rectangle(img, (8, y - 12), (28, y + 2), (b, g, r), -1)   # BGR
        cv2.rectangle(img, (8, y - 12), (28, y + 2), (200, 200, 200), 1)
        pct = 100.0 * n / total if total > 0 else 0.0
        cv2.putText(img, f'{name} ({code})  {pct:5.2f}%', (36, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 210), 1, cv2.LINE_AA)
    return img


def _colorize(class_raster: np.ndarray,
              class_defs: dict[int, tuple[str, tuple[int, int, int]]]) -> np.ndarray:
    """Map integer class IDs → BGR image (OpenCV convention)."""
    h, w = class_raster.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for code, (_name, (r, g, b)) in class_defs.items():
        mask = class_raster == code
        if mask.any():
            rgb[mask] = (b, g, r)
    return rgb


# ── Node ─────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_planetary_lulc',
    label='LULC (Planetary)',
    category='geography',
    icon='Map',
    description=(
        "Annual land-use/land-cover from Microsoft Planetary Computer (no auth). "
        "ESA WorldCover (10 m, 2020-2021) is the best choice for mangrove + "
        "wetland ground truth — it has an explicit `Mangroves` class. "
        "io-lulc-annual-v02 (10 m, 2017-2024) is better for change detection: "
        "track `Bare ground` inside forested zones to detect orpaillage."
    ),
    inputs=[],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'LULC GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Colorized Preview'},
        {'id': 'legend',  'color': 'image',   'label': 'Class Legend'},
        {'id': 'meta',    'color': 'dict',    'label': 'Meta'},
    ],
    params=[
        {'id': 'bbox',          'type': 'string', 'default': '-53.30,4.40,-52.60,5.50',
         'label': 'BBOX (lon_min,lat_min,lon_max,lat_max)'},
        {'id': 'collection',    'type': 'enum',
         'options': list(COLLECTION_DEFS.keys()), 'default': 0, 'label': 'Collection'},
        {'id': 'date_start',    'type': 'string', 'default': '2021-01-01', 'label': 'Start Date'},
        {'id': 'date_end',      'type': 'string', 'default': '2021-12-31', 'label': 'End Date'},
        {'id': 'resolution',    'type': 'int',    'default': 10, 'min': 10, 'max': 500,
         'label': 'Resolution (m/px)'},
        {'id': 'cache_dir',     'type': 'string', 'default': 'planetary_cache', 'label': 'Cache Dir'},
        {'id': 'fetch',         'type': 'trigger','default': 0, 'label': 'Fetch'},
    ],
    resizable=True, min_width=300, min_height=220,
)
class GeoPlanetaryLULCNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._prev_fetch = 0
        self._result: dict | None = None
        self._notif_id = f'planetary_lulc_{id(self)}'

    def _cache_path(self, params: dict) -> Path:
        sub = params.get('cache_dir', 'planetary_cache')
        d = Path(sub) if os.path.isabs(sub) else (Path(__file__).parent / sub)
        d.mkdir(parents=True, exist_ok=True)
        return d / f'lulc_{_params_hash(params)}.tif'

    def _idle(self, msg: str = '') -> dict:
        img = np.full((220, 420, 3), 22, dtype=np.uint8)
        cv2.putText(img, 'LULC (Planetary)', (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        for i, line in enumerate(['Click Fetch to download.', msg] if msg else
                                  ['Click Fetch to download.']):
            cv2.putText(img, line, (12, 60 + i * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (185, 185, 185), 1, cv2.LINE_AA)
        return {'preview': img}

    def process(self, inputs, params):
        run_val = params.get('fetch', 0)
        rising = run_val != self._prev_fetch and run_val not in (False, 0, None)
        self._prev_fetch = run_val

        if not rising and self._result is not None:
            return self._result
        if not rising:
            return self._idle()

        ok, msg = _ensure_packages()
        if not ok:
            send_notification(f'LULC: {msg}', level='error', notif_id=self._notif_id)
            return self._idle(msg)

        bbox = _parse_bbox(params.get('bbox', ''))
        if bbox is None:
            send_notification('LULC: invalid bbox', level='error', notif_id=self._notif_id)
            return self._idle('Invalid bbox.')

        coll_opts = list(COLLECTION_DEFS.keys())
        collection = coll_opts[int(params.get('collection', 0))]
        class_defs = COLLECTION_DEFS[collection]['classes']
        asset_id   = COLLECTION_DEFS[collection]['asset']

        date_start = str(params.get('date_start', '2021-01-01'))
        date_end   = str(params.get('date_end', '2021-12-31'))
        resolution = int(params.get('resolution', 10))

        cache_file = self._cache_path(params)
        if cache_file.exists():
            try:
                import rasterio
                with rasterio.open(cache_file) as ds:
                    arr = ds.read(1)
                    tags = ds.tags()
                self._result = self._build_outputs(
                    arr, str(cache_file), tags, class_defs, collection, from_cache=True
                )
                send_notification('LULC: loaded from cache',
                                  progress=1.0, notif_id=self._notif_id)
                return self._result
            except Exception:
                pass

        # ── STAC query ───────────────────────────────────────────────────────
        import pystac_client
        import planetary_computer
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds
        from rasterio.enums import Resampling

        catalog = pystac_client.Client.open(
            _STAC_URL, modifier=planetary_computer.sign_inplace,
        )
        send_notification(f'LULC: querying {collection}…', progress=0.1,
                          notif_id=self._notif_id)
        try:
            search = catalog.search(
                collections=[collection],
                bbox=bbox,
                datetime=f'{date_start}/{date_end}',
                limit=200,
            )
            items = sorted(search.items(), key=lambda i: i.datetime or 0)
        except Exception as e:
            send_notification(f'LULC: query failed: {e}',
                              level='error', notif_id=self._notif_id)
            return self._idle(f'STAC error: {e}')

        if not items:
            send_notification('LULC: 0 items for bbox/date',
                              level='warn', notif_id=self._notif_id)
            return self._idle('No LULC scenes in bbox/date window.')

        item = items[-1]  # most-recent scene
        if asset_id not in item.assets:
            # fall back to first asset whose key looks like a classification map
            cands = [k for k in item.assets if 'map' in k.lower() or 'data' in k.lower()]
            if not cands:
                return self._idle(f'asset `{asset_id}` not found in item.')
            asset_id = cands[0]

        href = item.assets[asset_id].href

        # ── Read windowed ───────────────────────────────────────────────────
        send_notification('LULC: reading window…', progress=0.5, notif_id=self._notif_id)
        # Target shape derived from BBOX extent (always in meters) — robust to
        # both projected and geographic source CRS.
        lon_min, lat_min, lon_max, lat_max = bbox
        lat_mid = 0.5 * (lat_min + lat_max)
        phys_w_m = (lon_max - lon_min) * 111_320.0 * float(np.cos(np.radians(lat_mid)))
        phys_h_m = (lat_max - lat_min) * 110_540.0
        out_w = max(1, int(round(phys_w_m / resolution)))
        out_h = max(1, int(round(phys_h_m / resolution)))
        try:
            with rasterio.open(href) as ds:
                dst_bounds = transform_bounds('EPSG:4326', ds.crs, *bbox, densify_pts=21)
                win = from_bounds(*dst_bounds, transform=ds.transform).round_offsets().round_lengths()
                if win.width <= 0 or win.height <= 0:
                    return self._idle('bbox falls outside scene footprint.')
                arr = ds.read(
                    1, window=win, out_shape=(out_h, out_w),
                    resampling=Resampling.nearest,    # categorical → nearest only
                    masked=False,
                ).astype(np.uint8)
                transform = rasterio.windows.transform(win, ds.transform) * \
                            rasterio.transform.Affine.scale(win.width / out_w,
                                                            win.height / out_h)
                crs = ds.crs
        except Exception as e:
            send_notification(f'LULC: read failed: {e}',
                              level='error', notif_id=self._notif_id)
            return self._idle(f'read error: {e}')

        # ── Persist ──────────────────────────────────────────────────────────
        tags = {
            'collection': collection,
            'scene_date': str(item.datetime),
            'classes':    json.dumps({str(k): v[0] for k, v in class_defs.items()}),
        }
        with rasterio.open(
            cache_file, 'w', driver='GTiff',
            height=arr.shape[0], width=arr.shape[1], count=1,
            dtype='uint8', crs=crs, transform=transform,
            compress='deflate', predictor=2, nodata=0,
        ) as dst:
            dst.write(arr, 1)
            dst.update_tags(**tags)

        self._result = self._build_outputs(
            arr, str(cache_file), tags, class_defs, collection, from_cache=False,
        )
        unique = len(np.unique(arr))
        scene_date = item.datetime.date() if item.datetime else 'unknown-date'
        send_notification(
            f'LULC: {collection} {scene_date} ({arr.shape}, {unique} classes)',
            progress=1.0, notif_id=self._notif_id,
        )
        return self._result

    def _build_outputs(self, arr: np.ndarray, path: str, tags: dict,
                       class_defs: dict, collection: str, from_cache: bool) -> dict:
        # Histogram per class
        vals, counts = np.unique(arr, return_counts=True)
        classes_present = {int(v): int(c) for v, c in zip(vals, counts)
                           if int(v) in class_defs}
        total = int(arr.size)

        preview = _colorize(arr, class_defs)
        # Resize preview if huge
        max_dim = 720
        h, w = preview.shape[:2]
        if max(h, w) > max_dim:
            s = max_dim / max(h, w)
            preview = cv2.resize(preview, (int(w * s), int(h * s)),
                                 interpolation=cv2.INTER_NEAREST)

        legend = _render_legend(classes_present, class_defs, total)

        geotiff = {
            'path': path,
            'array': arr[np.newaxis, ...],   # (1, H, W) to mirror multi-band contract
            'band_names': ['lulc_class'],
            'meta': tags,
        }
        return {
            'geotiff': geotiff,
            'preview': preview,
            'legend':  legend,
            'meta': {
                'source':     f'planetary_computer:{collection}',
                'cached':     from_cache,
                'path':       path,
                'collection': collection,
                'classes_present': {
                    class_defs[c][0]: round(100.0 * n / total, 3)
                    for c, n in sorted(classes_present.items(), key=lambda x: -x[1])
                },
            },
        }
