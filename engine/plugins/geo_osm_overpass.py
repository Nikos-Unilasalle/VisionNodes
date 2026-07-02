"""
geo_osm_overpass.py — Fetch arbitrary OpenStreetMap features (Overpass API) and
rasterize them onto a reference geo grid.

Generic vector-from-OSM loader. The tag selector is free-form Overpass syntax, so
one node covers many use cases:
    ["bridge"]                 → all bridges (spans over water/roads/rail)
    ["natural"="water"]        → lakes, rivers, reservoirs
    ["waterway"]               → river/stream centerlines
    ["highway"]                → road network
    ["building"]               → building footprints
    ["landuse"="forest"]       → forest polygons

Nodes → points, ways → lines/polygons (closed rings), relations → best-effort
multipolygon members. Points and lines are buffered by `buffer_m` (meters, in the
reference CRS) so linear features become areas before rasterization.

Requires the reference raster to carry `crs`, `transform` and lon/lat `bounds`
(the canonical geo_copernicus / S2 dict). Buffering assumes a projected CRS
(UTM, metres) — the S2 grid qualifies.
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'osm_overpass'
_DEFAULT_URL = 'https://overpass-api.de/api/interpreter'


def _bounds_lonlat(geo: dict):
    """Return (west, south, east, north) in lon/lat from a geo dict."""
    b = geo.get('bounds')
    if isinstance(b, dict) and all(k in b for k in ('west', 'south', 'east', 'north')):
        return float(b['west']), float(b['south']), float(b['east']), float(b['north'])
    # Fallback: derive from transform + crs, reproject corners to EPSG:4326
    from pyproj import Transformer
    bands = geo['bands']
    H, W = (bands.shape[1:] if bands.ndim == 3 else bands.shape)
    T = tuple(geo['transform'])[:6]
    a, _, c, _, e, f = [float(v) for v in T]
    xs = [c, c + a * W]
    ys = [f, f + e * H]
    tr = Transformer.from_crs(geo['crs'], 'EPSG:4326', always_xy=True)
    lons, lats = tr.transform([xs[0], xs[1], xs[0], xs[1]], [ys[0], ys[0], ys[1], ys[1]])
    return min(lons), min(lats), max(lons), max(lats)


def _elements_to_geoms(elements: list):
    """Overpass JSON elements → list of shapely geometries (lon/lat)."""
    from shapely.geometry import Point, LineString, Polygon
    geoms = []
    for el in elements:
        t = el.get('type')
        if t == 'node' and 'lon' in el and 'lat' in el:
            geoms.append(Point(el['lon'], el['lat']))
        elif t in ('way', 'relation'):
            geom = el.get('geometry')
            if geom:  # 'out geom;' inlines coords on ways
                coords = [(g['lon'], g['lat']) for g in geom if 'lon' in g and 'lat' in g]
                if len(coords) >= 4 and coords[0] == coords[-1]:
                    try: geoms.append(Polygon(coords))
                    except Exception: geoms.append(LineString(coords))
                elif len(coords) >= 2:
                    geoms.append(LineString(coords))
            else:  # relation members carry their own geometry
                for m in el.get('members', []):
                    mg = m.get('geometry')
                    if not mg:
                        continue
                    coords = [(g['lon'], g['lat']) for g in mg if 'lon' in g and 'lat' in g]
                    if len(coords) >= 4 and coords[0] == coords[-1]:
                        try: geoms.append(Polygon(coords))
                        except Exception: geoms.append(LineString(coords))
                    elif len(coords) >= 2:
                        geoms.append(LineString(coords))
    return geoms


@vision_node(
    type_id='geo_osm_overpass',
    label='OSM Overpass Features',
    category='geography',
    icon='MapPin',
    description=(
        "Fetch OpenStreetMap features via the Overpass API using a free-form tag "
        "selector and rasterize them onto a reference geo grid. Points/lines are "
        "buffered to areas. Examples: [\"bridge\"], [\"natural\"=\"water\"], "
        "[\"highway\"], [\"building\"]. Outputs a binary mask on the reference grid."
    ),
    inputs=[
        {'id': 'reference', 'color': 'geotiff', 'label': 'Reference raster (defines grid + bbox)'},
    ],
    outputs=[
        {'id': 'mask',    'color': 'mask',    'label': 'Binary mask (features=255)'},
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Burned geo dict'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview'},
        {'id': 'n_feat',  'color': 'scalar',  'label': 'Features rasterized'},
    ],
    params=[
        {'id': '_sec_query', 'label': 'Query', 'type': 'section'},
        {'id': 'selector',     'type': 'string', 'default': '["bridge"]',
         'label': 'Overpass tag selector (raw)'},
        {'id': 'element_types', 'type': 'enum', 'default': 0,
         'options': [{'label': 'node+way+relation', 'value': 'nwr'},
                     {'label': 'node+way', 'value': 'nw'},
                     {'label': 'way only', 'value': 'way'},
                     {'label': 'node only', 'value': 'node'}],
         'label': 'Element types'},
        {'id': 'buffer_m',     'type': 'float',  'default': 15.0, 'min': 0.0, 'max': 1e5,
         'label': 'Buffer points/lines (m, ref CRS)'},
        {'id': '_sec_raster', 'label': 'Rasterization', 'type': 'section'},
        {'id': 'all_touched',  'type': 'bool',   'default': True,
         'label': 'All touched pixels'},
        {'id': '_sec_net', 'label': 'Network', 'type': 'section'},
        {'id': 'overpass_url', 'type': 'string', 'default': _DEFAULT_URL, 'label': 'Overpass endpoint'},
        {'id': 'timeout_s',    'type': 'int',    'default': 60, 'min': 5, 'max': 600, 'label': 'Timeout (s)'},
        {'id': 'fetch',        'type': 'trigger', 'default': 0, 'label': 'Fetch'},
        {'id': 'cache_dir',    'type': 'string', 'default': 'copernicus_cache', 'label': 'Cache dir'},
        {'id': 'node_note',    'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=300, min_height=200,
)
class OSMOverpassNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._cache_key: str | None = None
        self._cache_out: dict | None = None

    def process(self, inputs: dict, params: dict) -> dict:
        ref_geo = inputs.get('reference')
        if not isinstance(ref_geo, dict) or 'bands' not in ref_geo:
            send_notification('OSM Overpass: connect a reference raster', notif_id=_NOTIF)
            return {}
        ref_crs = ref_geo.get('crs')
        ref_transform = ref_geo.get('transform')
        if ref_crs is None or ref_transform is None:
            send_notification('OSM Overpass: reference has no CRS/transform', level='error', notif_id=_NOTIF)
            return {}

        selector = str(params.get('selector', '["bridge"]')).strip()
        el_type  = str(params.get('element_types', 'nwr') or 'nwr')
        buffer_m = float(params.get('buffer_m', 15.0))
        all_touched = bool(params.get('all_touched', True))
        url      = str(params.get('overpass_url', _DEFAULT_URL)).strip() or _DEFAULT_URL
        timeout  = int(params.get('timeout_s', 60))

        bands = ref_geo['bands']
        H, W = (bands.shape[1:] if bands.ndim == 3 else bands.shape)
        west, south, east, north = _bounds_lonlat(ref_geo)

        # Cache: re-query only when grid / bbox / query / fetch changes
        import hashlib, json as _json, os
        _key = hashlib.md5((
            f'{H}x{W}:{west:.5f},{south:.5f},{east:.5f},{north:.5f}:{selector}:{el_type}:'
            f'{buffer_m}:{all_touched}:{params.get("fetch", 0)}'
        ).encode()).hexdigest()
        if _key == self._cache_key and self._cache_out is not None:
            return self._cache_out

        if not self.ensure_packages(
            ['requests', 'rasterio', 'pyproj', 'shapely'],
            pip_names=['requests', 'rasterio', 'pyproj', 'shapely'], notif_id=_NOTIF,
        ):
            return {}

        import requests
        from rasterio.features import rasterize
        from pyproj import Transformer
        from shapely.ops import transform as shp_transform
        from shapely.geometry import Point, LineString

        raw_cache = str(params.get('cache_dir', 'copernicus_cache') or 'copernicus_cache').strip()
        _dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = raw_cache if os.path.isabs(raw_cache) else os.path.join(_dir, raw_cache)
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f'osm_{_key[:16]}.json')

        # ── Fetch (disk cache first) ──────────────────────────────────────────
        elements = None
        if os.path.isfile(cache_file):
            try:
                with open(cache_file) as fh:
                    elements = _json.load(fh).get('elements', [])
                send_notification(f'OSM Overpass: cache hit ({len(elements)} elements)',
                                  progress=0.4, notif_id=_NOTIF)
            except Exception:
                elements = None

        if elements is None:
            query = (f'[out:json][timeout:{timeout}];\n(\n  '
                     f'{el_type}{selector}({south},{west},{north},{east});\n);\nout geom;')
            send_notification(f'OSM Overpass: querying {selector}…', progress=0.2, notif_id=_NOTIF)
            try:
                resp = requests.post(
                    url, data={'data': query}, timeout=timeout + 15,
                    headers={'User-Agent': 'VNStudio-geo_osm_overpass/1.0 (research)',
                             'Accept': 'application/json'},
                )
                resp.raise_for_status()
                payload = resp.json()
                elements = payload.get('elements', [])
                with open(cache_file, 'w') as fh:
                    _json.dump({'elements': elements}, fh)
            except Exception as e:
                send_notification(f'OSM Overpass: query failed: {e}', level='error', notif_id=_NOTIF)
                return {}

        # ── Geometries → reproject → buffer → rasterize ───────────────────────
        geoms_ll = _elements_to_geoms(elements)
        if not geoms_ll:
            send_notification(f'OSM Overpass: 0 features for {selector} in bbox',
                              level='warning', notif_id=_NOTIF)
            return {}

        # Buffer in a METRIC crs (metres), then reproject to the reference grid.
        # The reference may be geographic (CDSE collection 0 = EPSG:4326) — buffering
        # buffer_m directly in degrees would flood the whole scene.
        from pyproj import CRS
        try:
            ref_is_geo = CRS.from_user_input(ref_crs).is_geographic
        except Exception:
            ref_is_geo = False
        if ref_is_geo:
            lon_c, lat_c = (west + east) / 2.0, (south + north) / 2.0
            zone = int((lon_c + 180.0) / 6.0) + 1
            metric_crs = f'EPSG:{(32600 if lat_c >= 0 else 32700) + zone}'
        else:
            metric_crs = ref_crs
        to_metric = Transformer.from_crs('EPSG:4326', metric_crs, always_xy=True)
        to_ref = None if metric_crs == ref_crs else Transformer.from_crs(metric_crs, ref_crs, always_xy=True)

        shapes_values = []
        for g in geoms_ll:
            try:
                gm = shp_transform(to_metric.transform, g)
                if buffer_m > 0 and isinstance(gm, (Point, LineString)):
                    gm = gm.buffer(buffer_m)
                gr = gm if to_ref is None else shp_transform(to_ref.transform, gm)
                if gr.is_empty:
                    continue
                shapes_values.append((gr.__geo_interface__, 1))
            except Exception:
                continue

        if not shapes_values:
            send_notification('OSM Overpass: features could not be projected', level='warning', notif_id=_NOTIF)
            return {}

        send_notification(f'OSM Overpass: rasterizing {len(shapes_values)} features…',
                          progress=0.8, notif_id=_NOTIF)
        burned = rasterize(
            shapes_values, out_shape=(H, W), transform=ref_transform,
            fill=0, dtype='uint8', all_touched=all_touched,
        )

        mask_u8 = (burned > 0).astype(np.uint8) * 255
        out_geo = {**ref_geo, 'bands': burned[np.newaxis].astype('float32'),
                   'count': 1, 'dtype': 'float32'}
        preview = np.zeros((H, W, 3), np.uint8)
        preview[..., 1] = mask_u8   # green ribbon (BGR: green channel)

        cov = float((burned > 0).mean())
        lvl = 'warning' if cov > 0.8 else 'info'
        send_notification(
            f'OSM Overpass: {len(shapes_values)} features → {int((burned>0).sum()):,} px '
            f'({cov:.1%} de la scene; metric_crs={metric_crs})'
            + ('  ⚠ couverture quasi totale — buffer_m trop grand ?' if cov > 0.8 else ''),
            level=lvl, progress=1.0, notif_id=_NOTIF,
        )
        result = {'mask': mask_u8, 'geotiff': out_geo, 'preview': preview,
                  'n_feat': float(len(shapes_values))}
        self._cache_key = _key
        self._cache_out = result
        return result
