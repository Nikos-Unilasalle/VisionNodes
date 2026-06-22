"""
geo_wfs_loader.py — Generic OGC WFS vector loader + rasterizer.

Downloads ANY layer from a WFS service (GeoServer, MapServer, …), reprojects it
onto a reference raster grid, and burns it to a single-band geo dict. Generalises
geo_oam_loader (which is hardcoded to the GéoGuyane OAM service).

Burn modes:
  - constant         : every feature → default_value
  - field (numeric)  : burn the numeric value of burn_field
  - field + value_map: map a categorical burn_field through a JSON dict
                       (e.g. {"Pélites": 2, "Volcanisme basique": 3}); categories
                       absent from the map fall back to default_value.

Press Fetch to download (background thread). Result is cached on the reference
grid + parameter signature so re-runs are instant.
"""
from __future__ import annotations
import threading
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'wfs_loader'

_DEFAULT_WFS = 'https://www.guyane-sig.fr/geoserver/wfs'


@vision_node(
    type_id='geo_wfs_loader',
    label='WFS Loader',
    category='geography',
    icon='Globe',
    description=(
        "Generic OGC WFS vector loader. Downloads any layer (URL + typeName), "
        "reprojects onto the reference grid, and rasterizes to a geo dict. "
        "Supports constant, numeric-field, or categorical value-map burning. "
        "Press Fetch to download."
    ),
    inputs=[
        {'id': 'reference', 'color': 'geotiff', 'label': 'Reference raster (defines grid)'},
    ],
    outputs=[
        {'id': 'mask',    'color': 'mask',    'label': 'Binary mask (any feature=255)'},
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Burned values (geo dict)'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview (RGB)'},
        {'id': 'n_feat',  'color': 'scalar',  'label': 'Feature count'},
    ],
    params=[
        {'id': 'fetch', 'type': 'trigger', 'default': 0, 'label': 'Fetch'},
        {'id': 'wfs_url', 'type': 'string', 'default': _DEFAULT_WFS,
         'label': 'WFS service URL'},
        {'id': 'type_name', 'type': 'string', 'default': '',
         'label': 'Layer typeName (e.g. geologie:CARTE_...)'},
        {'id': 'bbox_filter', 'type': 'bool', 'default': True,
         'label': 'Restrict download to reference bbox'},
        {'id': '_sec_burn', 'label': 'Burn Config', 'type': 'section'},
        {'id': 'burn_field', 'type': 'string', 'default': '',
         'label': 'Attribute to burn (blank = constant)'},
        {'id': 'value_map', 'type': 'string', 'default': '',
         'label': 'Categorical map JSON {"cat": value, …} (optional)'},
        {'id': 'default_value', 'type': 'float', 'default': 1.0, 'min': 0.0, 'max': 1e6,
         'label': 'Default / constant burn value'},
        {'id': 'all_touched', 'type': 'bool', 'default': False,
         'label': 'All touched pixels'},
        {'id': '_sec_cache', 'label': 'Cache', 'type': 'section'},
        {'id': 'cache_dir', 'type': 'string', 'default': 'copernicus_cache',
         'label': 'Cache directory'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=300, min_height=220,
)
class WFSLoaderNode(NodeProcessor):

    def __init__(self) -> None:
        super().__init__()
        self._prev_fetch: int = 0
        self._loading: bool = False
        self._fetch_gen: int = 0
        self._raster_key: str | None = None
        self._raster_out: dict | None = None

    # ── WFS download (background thread) ──────────────────────────────────────
    def _do_download(self, url: str, cache_file: str, my_gen: int) -> None:
        try:
            import requests as _req
            send_notification('WFS Loader: téléchargement…', progress=0.1, notif_id=_NOTIF)
            resp = _req.get(url, timeout=300)
            resp.raise_for_status()
            with open(cache_file, 'wb') as f:
                f.write(resp.content)
            send_notification(
                f'WFS Loader: {len(resp.content) // 1024} KB reçus → {cache_file}',
                progress=0.4, notif_id=_NOTIF,
            )
        except Exception as exc:
            send_notification(f'WFS Loader: échec téléchargement — {exc}',
                              level='error', notif_id=_NOTIF)
        finally:
            if my_gen == self._fetch_gen:
                self._loading = False

    @staticmethod
    def _cache_name(type_name: str, cache_dir: str) -> str:
        import os
        safe = type_name.replace(':', '_').replace('/', '_') or 'wfs_layer'
        return os.path.join(cache_dir, f'wfs_{safe}.geojson')

    @staticmethod
    def _bbox_4326(ref_geo: dict):
        """Reference bounds in lon/lat (EPSG:4326) for the WFS BBOX filter."""
        transform = ref_geo.get('transform')
        crs = ref_geo.get('crs')
        bands = ref_geo['bands']
        H, W = (bands.shape[-2], bands.shape[-1]) if bands.ndim == 3 else bands.shape
        if transform is None or crs is None:
            return None
        try:
            xs = [transform.c, transform.c + transform.a * W]
            ys = [transform.f, transform.f + transform.e * H]
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            from pyproj import Transformer
            tr = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
            lon1, lat1 = tr.transform(minx, miny)
            lon2, lat2 = tr.transform(maxx, maxy)
            return (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
        except Exception:
            return None

    # ── Main process ──────────────────────────────────────────────────────────
    def process(self, inputs: dict, params: dict) -> dict:
        import os, hashlib, json

        ref_geo = inputs.get('reference')
        if not isinstance(ref_geo, dict) or 'bands' not in ref_geo:
            send_notification('WFS Loader: connecter un raster de référence', notif_id=_NOTIF)
            return {}

        ref_crs = ref_geo.get('crs')
        ref_transform = ref_geo.get('transform')
        if ref_crs is None or ref_transform is None:
            send_notification('WFS Loader: raster sans CRS/transform',
                              level='error', notif_id=_NOTIF)
            return {}

        wfs_url = str(params.get('wfs_url', _DEFAULT_WFS)).strip() or _DEFAULT_WFS
        type_name = str(params.get('type_name', '')).strip()
        cache_dir = str(params.get('cache_dir', 'copernicus_cache')).strip() or 'copernicus_cache'

        if not type_name:
            send_notification('WFS Loader: renseigner le typeName de la couche',
                              level='warning', notif_id=_NOTIF)
            return {}

        cache_file = self._cache_name(type_name, cache_dir)

        # ── Fetch trigger (rising edge) ───────────────────────────────────────
        fetch_val = params.get('fetch', 0)
        rising = fetch_val != self._prev_fetch and fetch_val not in (False, 0, None)
        self._prev_fetch = fetch_val

        if rising:
            os.makedirs(cache_dir, exist_ok=True)
            if os.path.isfile(cache_file):
                os.unlink(cache_file)
            self._raster_key = None
            self._raster_out = None
            self._loading = True
            self._fetch_gen += 1

            url = (
                f'{wfs_url}?service=WFS&version=2.0.0&request=GetFeature'
                f'&typeName={type_name}&outputFormat=application/json'
            )
            if bool(params.get('bbox_filter', True)):
                bbox = self._bbox_4326(ref_geo)
                if bbox is not None:
                    # WFS 2.0 BBOX: miny,minx,maxy,maxx with CRS urn (lat/lon order)
                    url += (f'&bbox={bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]},'
                            'urn:ogc:def:crs:EPSG::4326')
            threading.Thread(target=self._do_download,
                             args=(url, cache_file, self._fetch_gen), daemon=True).start()
            return {}

        if self._loading:
            send_notification('WFS Loader: téléchargement en cours…',
                              progress=0.2, notif_id=_NOTIF)
            return {}
        if not os.path.isfile(cache_file):
            send_notification(f'WFS Loader: cliquer Fetch pour télécharger {type_name}',
                              level='warning', notif_id=_NOTIF)
            return {}

        # ── Rasterization cache key ───────────────────────────────────────────
        burn_field = str(params.get('burn_field', '')).strip()
        value_map_raw = str(params.get('value_map', '')).strip()
        default_value = float(params.get('default_value', 1.0))
        all_touched = bool(params.get('all_touched', False))

        ref_b = ref_geo['bands']
        rkey = hashlib.md5((
            f'{ref_b.shape}:{cache_file}:{os.path.getmtime(cache_file):.0f}:'
            f'{burn_field}:{value_map_raw}:{default_value}:{all_touched}'
        ).encode()).hexdigest()
        if rkey == self._raster_key and self._raster_out is not None:
            return self._raster_out

        value_map: dict = {}
        if value_map_raw:
            try:
                value_map = {str(k): float(v) for k, v in json.loads(value_map_raw).items()}
            except Exception as exc:
                send_notification(f'WFS Loader: value_map JSON invalide — {exc}',
                                  level='error', notif_id=_NOTIF)
                return {}

        if not self.ensure_packages(
            ['fiona', 'rasterio', 'pyproj', 'shapely'],
            pip_names=['fiona', 'rasterio', 'pyproj', 'shapely'], notif_id=_NOTIF,
        ):
            return {}

        import fiona
        from rasterio.features import rasterize as _rasterize
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.ops import transform as shp_transform

        H, W = (ref_b.shape[-2], ref_b.shape[-1]) if ref_b.ndim == 3 else ref_b.shape

        try:
            with fiona.open(cache_file) as src:
                src_crs_str = src.crs_wkt if hasattr(src, 'crs_wkt') else str(src.crs)
                n_total = len(src)
                send_notification(f'WFS Loader: {n_total} features · reprojection…',
                                  progress=0.5, notif_id=_NOTIF)
                try:
                    transformer = Transformer.from_crs(src_crs_str, ref_crs, always_xy=True)
                    need_reproject = True
                except Exception:
                    need_reproject = False

                shapes_values: list[tuple] = []
                n_skipped = 0
                for feat in src:
                    props = feat.get('properties') or {}
                    geom = shape(feat['geometry']) if feat.get('geometry') else None
                    if geom is None or geom.is_empty:
                        n_skipped += 1
                        continue
                    if need_reproject:
                        try:
                            geom = shp_transform(transformer.transform, geom)
                        except Exception:
                            n_skipped += 1
                            continue

                    if not burn_field:
                        val = default_value
                    else:
                        raw = props.get(burn_field)
                        if value_map:
                            val = value_map.get(str(raw), default_value)
                        else:
                            try:
                                val = float(raw)
                            except (ValueError, TypeError):
                                val = default_value
                    shapes_values.append((geom.__geo_interface__, val))
        except Exception as exc:
            send_notification(f'WFS Loader: erreur lecture vecteur — {exc}',
                              level='error', notif_id=_NOTIF)
            return {}

        if not shapes_values:
            send_notification(f'WFS Loader: 0 features (ignorés: {n_skipped})',
                              level='warning', notif_id=_NOTIF)
            return {}

        send_notification(f'WFS Loader: rasterisation {len(shapes_values)} features…',
                          progress=0.75, notif_id=_NOTIF)
        burned = _rasterize(shapes_values, out_shape=(H, W), transform=ref_transform,
                            fill=0.0, dtype='float32', all_touched=all_touched)

        mask_u8 = (burned > 0).astype(np.uint8) * 255

        # Preview: normalized burned values (JET), background black
        vmax = float(burned.max())
        norm = (burned / vmax * 255.0).astype(np.uint8) if vmax > 0 else burned.astype(np.uint8)
        preview = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
        preview[burned == 0] = [0, 0, 0]

        out_geo = {**ref_geo, 'bands': burned[np.newaxis], 'count': 1, 'dtype': 'float32',
                   'band_names': [burn_field or 'burned'], '_bands': [burn_field or 'burned']}

        send_notification(
            f'WFS Loader: {len(shapes_values)} features → {int((burned > 0).sum()):,} px',
            progress=1.0, notif_id=_NOTIF)

        result = {
            'mask': mask_u8,
            'geotiff': out_geo,
            'preview': preview,
            'n_feat': float(len(shapes_values)),
        }
        self._raster_key = rkey
        self._raster_out = result
        return result
