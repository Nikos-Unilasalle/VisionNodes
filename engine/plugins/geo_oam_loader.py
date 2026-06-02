"""
geo_oam_loader.py — OAM ground truth rasterizer.

Downloads mining deforestation polygons from GéoGuyane WFS service or a local
GeoPackage, and rasterizes them onto a reference geo dict grid.

Dataset: "Surfaces exploitées par l'activité minière en Guyane"
Licence: Ouverte V2.0 (libre réutilisation)
CRS: EPSG:2972 (RGFG95 / UTM 22N)
Coverage: 1990 → year n-1 (annual update)
Source: https://catalogue.geoguyane.fr/...d25a319f-1c86-42be-8e59-c97e92e7e910

Schema (table oam_surf_expl_aaaa_s):
  id_do     : OAM unique ID
  date_expl : start year of exploitation (char 4)
  area      : area in hectares
  type_expl : ALLUVIONNAIRE / PRIMAIRE / CAMPEMENT / PISTE / AUTRE
  crois_clan: 1=Legal 2=Illegal 3=Hors titre
  date_ref  : reference image date
  source_2  : satellite source (S2, SPOT5, …)
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'oam_loader'

_WFS_BASE = (
    'https://datacarto.geoguyane.fr/wfs/'
    '98cbd31c-d435-403e-b286-9c882b5101d9'
)
_LAYERS = {
    'WFS 2023': 'ms:oam_surf_expl_2023_s',
    'WFS 2022': 'ms:oam_surf_expl_2022_s',
}

_LEGALITY_CODES = {'All': None, 'Illegal (2)': 2, 'Legal (1)': 1, 'Hors titre (3)': 3}
_TYPE_CODES = {
    'All': None,
    'Alluvionnaire': 'ALLUVIONNAIRE',
    'Primaire': 'PRIMAIRE',
    'Campement': 'CAMPEMENT',
    'Piste': 'PISTE',
    'Autre': 'AUTRE',
}
_TYPE_INT = {'ALLUVIONNAIRE': 1, 'PRIMAIRE': 2, 'CAMPEMENT': 3, 'PISTE': 4, 'AUTRE': 5}

# Preview palette: legal=green, illegal=red, hors titre=orange, other=gray
_CLASS_COLORS_BGR = {1: (40, 180, 40), 2: (40, 40, 220), 3: (30, 140, 230)}


@vision_node(
    type_id='geo_oam_loader',
    label='OAM Ground Truth',
    category='geography',
    icon='ShieldAlert',
    description=(
        "Loads OAM (Observatoire de l'Activité Minière) deforestation polygons "
        "from GéoGuyane WFS or a local GeoPackage. Rasterizes onto the reference "
        "grid. Outputs: binary mask, class map (legal/illegal/hors-titre), "
        "exploitation type map, age map (years since date_expl), and RGB preview."
    ),
    inputs=[
        {'id': 'reference', 'color': 'geotiff', 'label': 'Reference raster (defines grid)'},
    ],
    outputs=[
        {'id': 'mask',      'color': 'mask',    'label': 'Binary mask (any impact=255)'},
        {'id': 'geotiff',   'color': 'geotiff', 'label': 'Burned values (geo dict)'},
        {'id': 'preview',   'color': 'image',   'label': 'Preview (green=legal, red=illegal)'},
        {'id': 'n_feat',    'color': 'scalar',  'label': 'Feature count'},
    ],
    params=[
        {'id': 'source', 'type': 'enum', 'default': 'WFS 2023',
         'options': ['WFS 2023', 'WFS 2022', 'Local GeoPackage'],
         'label': 'Data source'},
        {'id': 'file_path', 'type': 'string', 'default': '',
         'label': 'Local .gpkg path (when source=Local)',
         'show_if': {'source': 'Local GeoPackage'}},
        {'id': 'layer_name', 'type': 'string', 'default': '',
         'label': 'Layer name (blank=first layer)',
         'show_if': {'source': 'Local GeoPackage'}},
        {'id': 'output_field', 'type': 'enum', 'default': 'class (crois_clan)',
         'options': ['binary', 'class (crois_clan)', 'type (type_expl)', 'age (years)'],
         'label': 'Burn field'},
        {'id': 'legality', 'type': 'enum', 'default': 'All',
         'options': list(_LEGALITY_CODES.keys()),
         'label': 'Legality filter'},
        {'id': 'mining_type', 'type': 'enum', 'default': 'All',
         'options': list(_TYPE_CODES.keys()),
         'label': 'Mining type filter'},
        {'id': 'year_min', 'type': 'int', 'default': 2000, 'min': 1990, 'max': 2030,
         'label': 'Year min (date_expl)'},
        {'id': 'year_max', 'type': 'int', 'default': 2025, 'min': 1990, 'max': 2030,
         'label': 'Year max (date_expl)'},
        {'id': 'all_touched', 'type': 'bool', 'default': False,
         'label': 'All touched pixels'},
        {'id': 'cache_dir', 'type': 'string', 'default': 'copernicus_cache',
         'label': 'Cache directory'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=300, min_height=200,
)
class OAMLoaderNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._cache_key: str | None = None
        self._cache_out: dict | None = None

    def process(self, inputs: dict, params: dict) -> dict:
        ref_geo = inputs.get('reference')
        if not isinstance(ref_geo, dict) or 'bands' not in ref_geo:
            send_notification('OAM Loader: connect a reference raster', notif_id=_NOTIF)
            return {}

        ref_crs       = ref_geo.get('crs')
        ref_transform = ref_geo.get('transform')
        if ref_crs is None or ref_transform is None:
            send_notification('OAM Loader: reference has no CRS/transform',
                              level='error', notif_id=_NOTIF)
            return {}

        source       = str(params.get('source', 'WFS 2023'))
        output_field = str(params.get('output_field', 'class (crois_clan)'))
        legality_key = str(params.get('legality', 'All'))
        type_key     = str(params.get('mining_type', 'All'))
        year_min     = int(params.get('year_min', 2000))
        year_max     = int(params.get('year_max', 2025))
        all_touched  = bool(params.get('all_touched', False))
        cache_dir    = str(params.get('cache_dir', 'copernicus_cache')).strip() or 'copernicus_cache'

        import hashlib, json as _json
        ref_bands = ref_geo['bands']
        _key = hashlib.md5((
            f'{ref_bands.shape}:{source}:{output_field}:{legality_key}:'
            f'{type_key}:{year_min}:{year_max}:{all_touched}'
            + (str(params.get('file_path', '')) if source == 'Local GeoPackage' else '')
        ).encode()).hexdigest()
        if _key == self._cache_key and self._cache_out is not None:
            return self._cache_out

        if not self.ensure_packages(
            ['fiona', 'rasterio', 'pyproj', 'shapely', 'requests'],
            pip_names=['fiona', 'rasterio', 'pyproj', 'shapely', 'requests'],
            notif_id=_NOTIF,
        ):
            return {}

        import os, tempfile
        import fiona
        import rasterio
        from rasterio.features import rasterize
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.ops import transform as shp_transform

        ref_b = ref_geo['bands']
        H, W = (ref_b.shape[-2], ref_b.shape[-1]) if ref_b.ndim == 3 else ref_b.shape

        legality_filter = _LEGALITY_CODES.get(legality_key)
        type_filter     = _TYPE_CODES.get(type_key)

        # -- Resolve vector source --
        tmp_file: str | None = None
        fiona_path: str
        fiona_layer: str | None = None

        if source in _LAYERS:
            import requests as _req
            layer_name = _LAYERS[source]
            year_tag = source.split()[-1]
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f'oam_{year_tag}.gml')

            if not os.path.isfile(cache_file):
                url = (
                    f'{_WFS_BASE}?service=WFS&version=2.0.0&request=GetFeature'
                    f'&typeName={layer_name}'
                )
                send_notification(f'OAM Loader: downloading {source} from WFS…',
                                  progress=0.1, notif_id=_NOTIF)
                try:
                    resp = _req.get(url, timeout=120)
                    resp.raise_for_status()
                    with open(cache_file, 'wb') as f:
                        f.write(resp.content)
                    send_notification(f'OAM Loader: cached {len(resp.content)//1024} KB → {cache_file}',
                                      progress=0.3, notif_id=_NOTIF)
                except Exception as e:
                    send_notification(f'OAM Loader: WFS download failed: {e}',
                                      level='error', notif_id=_NOTIF)
                    return {}
            else:
                send_notification(f'OAM Loader: using cached {source}',
                                  progress=0.3, notif_id=_NOTIF)
            fiona_path = cache_file

        else:
            fiona_path = str(params.get('file_path', '')).strip()
            layer_raw  = str(params.get('layer_name', '')).strip()
            fiona_layer = layer_raw or None
            if not fiona_path:
                send_notification('OAM Loader: set file_path for Local GeoPackage',
                                  level='warning', notif_id=_NOTIF)
                return {}
            if not os.path.isfile(fiona_path):
                send_notification(f'OAM Loader: file not found: {fiona_path}',
                                  level='error', notif_id=_NOTIF)
                return {}
            send_notification(f'OAM Loader: reading {os.path.basename(fiona_path)}…',
                              progress=0.3, notif_id=_NOTIF)

        import datetime
        current_year = datetime.datetime.now().year

        try:
            open_kwargs: dict = {}
            if fiona_layer:
                open_kwargs['layer'] = fiona_layer

            with fiona.open(fiona_path, **open_kwargs) as src:
                src_crs_str = src.crs_wkt if hasattr(src, 'crs_wkt') else str(src.crs)
                n_total = len(src)
                send_notification(
                    f'OAM Loader: {n_total} total features, CRS={src_crs_str[:50]}…',
                    progress=0.45, notif_id=_NOTIF,
                )

                try:
                    transformer = Transformer.from_crs(src_crs_str, ref_crs, always_xy=True)
                    need_reproject = True
                except Exception:
                    need_reproject = False

                shapes_values: list[tuple] = []
                n_skipped = 0

                for feat in src:
                    props = feat.get('properties') or {}

                    # Year filter
                    raw_year = props.get('date_expl')
                    try:
                        feat_year = int(str(raw_year)[:4]) if raw_year else 0
                    except (ValueError, TypeError):
                        feat_year = 0
                    if feat_year and (feat_year < year_min or feat_year > year_max):
                        n_skipped += 1
                        continue

                    # Legality filter
                    if legality_filter is not None:
                        clan = props.get('crois_clan')
                        try:
                            clan_int = int(clan) if clan is not None else None
                        except (ValueError, TypeError):
                            clan_int = None
                        if clan_int != legality_filter:
                            n_skipped += 1
                            continue

                    # Mining type filter
                    if type_filter is not None:
                        feat_type = str(props.get('type_expl') or '').upper()
                        if feat_type != type_filter:
                            n_skipped += 1
                            continue

                    geom = shape(feat['geometry'])
                    if geom is None or geom.is_empty:
                        n_skipped += 1
                        continue
                    if need_reproject:
                        try:
                            geom = shp_transform(transformer.transform, geom)
                        except Exception:
                            n_skipped += 1
                            continue

                    # Burn value
                    if output_field == 'binary':
                        val = 1.0
                    elif output_field == 'class (crois_clan)':
                        try:
                            val = float(int(props.get('crois_clan') or 0))
                        except (ValueError, TypeError):
                            val = 0.0
                    elif output_field == 'type (type_expl)':
                        feat_type_str = str(props.get('type_expl') or '').upper()
                        val = float(_TYPE_INT.get(feat_type_str, 0))
                    elif output_field == 'age (years)':
                        val = float(current_year - feat_year) if feat_year else 0.0
                    else:
                        val = 1.0

                    shapes_values.append((geom.__geo_interface__, val))

        except Exception as e:
            send_notification(f'OAM Loader: error reading vector: {e}',
                              level='error', notif_id=_NOTIF)
            return {}

        if tmp_file and os.path.isfile(tmp_file):
            os.unlink(tmp_file)

        n_burned = len(shapes_values)
        if not shapes_values:
            send_notification(
                f'OAM Loader: 0 features after filters (skipped {n_skipped})',
                level='warning', notif_id=_NOTIF,
            )
            return {}

        send_notification(f'OAM Loader: rasterizing {n_burned} features…',
                          progress=0.7, notif_id=_NOTIF)

        from rasterio.features import rasterize as _rasterize
        burned = _rasterize(
            shapes_values,
            out_shape=(H, W),
            transform=ref_transform,
            fill=0.0,
            dtype='float32',
            all_touched=all_touched,
        )

        mask_u8 = (burned > 0).astype(np.uint8) * 255

        # RGB preview: class-colored overlay
        preview = np.zeros((H, W, 3), dtype=np.uint8)
        if output_field == 'class (crois_clan)':
            for code, bgr in _CLASS_COLORS_BGR.items():
                m = burned == float(code)
                preview[m] = bgr
        else:
            preview[burned > 0] = (40, 200, 40)

        out_geo = {
            **ref_geo,
            'bands': burned[np.newaxis],
            'count': 1,
            'dtype': 'float32',
        }

        send_notification(
            f'OAM Loader: {n_burned} features → '
            f'{int((burned > 0).sum()):,} pixels  |  skipped {n_skipped}',
            progress=1.0, notif_id=_NOTIF,
        )

        result = {
            'mask':    mask_u8,
            'geotiff': out_geo,
            'preview': preview,
            'n_feat':  float(n_burned),
        }
        self._cache_key = _key
        self._cache_out = result
        return result
