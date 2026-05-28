"""
geo_shapefile_rasterizer.py — Rasterize a vector file onto a reference geo grid.

Loads any vector file supported by Fiona/GDAL (Shapefile .shp, GeoJSON,
GeoPackage .gpkg, etc.) and burns it onto the reference raster's grid.

Supports:
  - Binary mask (all features → 1)
  - Attribute burning (burn a numeric field value per feature)
  - Optional class label mapping

Typical uses:
  - Load GMW v3 mangrove extent shapefile → compare with RF classification
  - Load Sinnamary watershed polygon → crop statistics
  - Load SIGMINE orpaillage permits → overlay on classification map
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'shp_rasterizer'


@vision_node(
    type_id='geo_shapefile_rasterizer',
    label='Shapefile Rasterizer',
    category='geography',
    icon='MapPin',
    description=(
        "Rasterize a vector file (Shapefile, GeoJSON, GeoPackage) onto a reference "
        "geo dict grid. Outputs a binary mask and/or an attribute-burned geo dict. "
        "Use for: GMW v3 mangrove extent validation, watershed masking, orpaillage "
        "permit overlay (SIGMINE)."
    ),
    inputs=[
        {'id': 'reference', 'color': 'geotiff', 'label': 'Reference raster (defines grid)'},
    ],
    outputs=[
        {'id': 'mask',    'color': 'mask',    'label': 'Binary mask (features=255)'},
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Burned attribute geo dict'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview'},
        {'id': 'n_feat',  'color': 'scalar',  'label': 'Features burned'},
    ],
    params=[
        {'id': 'file_path',    'type': 'string', 'default': '',
         'label': 'Vector file path (.shp / .geojson / .gpkg)'},
        {'id': 'layer',        'type': 'string', 'default': '',
         'label': 'Layer name (GeoPackage, blank = first)'},
        {'id': 'burn_field',   'type': 'string', 'default': '',
         'label': 'Attribute field to burn (blank = burn value below)'},
        {'id': 'burn_value',   'type': 'float',  'default': 1.0,
         'min': 0, 'max': 1e9,
         'label': 'Burn value (when no field)'},
        {'id': 'all_touched',  'type': 'bool',   'default': False,
         'label': 'All touched pixels (rasterize touching cells)'},
        {'id': 'background',   'type': 'float',  'default': 0.0,
         'min': -1e9, 'max': 1e9,
         'label': 'Background (nodata) value'},
        {'id': 'node_note',    'type': 'string', 'default': '', 'label': 'Note'},
        {'id': 'cache_dir',    'type': 'string', 'default': 'copernicus_cache', 'label': 'Cache dir'},
    ],
    resizable=True, min_width=300, min_height=180,
)
class ShapefileRasterizerNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._cache_key: str | None = None
        self._cache_out: dict | None = None

    def process(self, inputs: dict, params: dict) -> dict:
        ref_geo = inputs.get('reference')
        if not isinstance(ref_geo, dict) or 'bands' not in ref_geo:
            send_notification('Shapefile Rasterizer: connect a reference raster', notif_id=_NOTIF)
            return {}

        file_path = str(params.get('file_path', '')).strip()
        if not file_path:
            send_notification('Shapefile Rasterizer: set file_path param', level='warning', notif_id=_NOTIF)
            return {}

        import os
        if not os.path.isfile(file_path):
            send_notification(f'Shapefile Rasterizer: file not found: {file_path}',
                              level='error', notif_id=_NOTIF)
            return {}

        # Cache key
        import hashlib, json as _json
        ref_b = ref_geo['bands']
        _key = hashlib.md5((
            f'{ref_b.shape}:{file_path}:{os.path.getmtime(file_path)}'
            + _json.dumps(params, sort_keys=True)
        ).encode()).hexdigest()
        if _key == self._cache_key and self._cache_out is not None:
            return self._cache_out

        if not self.ensure_packages(
            ['fiona', 'rasterio', 'pyproj', 'shapely'],
            pip_names=['fiona', 'rasterio', 'pyproj', 'shapely'],
            notif_id=_NOTIF,
        ):
            return {}

        import fiona
        import rasterio
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.ops import transform as shp_transform

        burn_field  = str(params.get('burn_field', '')).strip()
        burn_value  = float(params.get('burn_value', 1.0))
        all_touched = bool(params.get('all_touched', False))
        background  = float(params.get('background', 0.0))
        layer_name  = str(params.get('layer', '')).strip() or None

        # Reference grid dimensions
        ref_bands = ref_geo['bands']
        if ref_bands.ndim == 3:
            _, H, W = ref_bands.shape
        else:
            H, W = ref_bands.shape

        ref_crs       = ref_geo.get('crs')
        ref_transform = ref_geo.get('transform')

        if ref_crs is None or ref_transform is None:
            send_notification('Shapefile Rasterizer: reference has no CRS/transform',
                              level='error', notif_id=_NOTIF)
            return {}

        send_notification(f'Shapefile Rasterizer: reading {os.path.basename(file_path)}…',
                          progress=0.2, notif_id=_NOTIF)

        try:
            open_kwargs = {'layer': layer_name} if layer_name else {}
            with fiona.open(file_path, **open_kwargs) as src:
                src_crs_str = src.crs_wkt if hasattr(src, 'crs_wkt') else str(src.crs)
                n_features = len(src)
                send_notification(
                    f'Shapefile Rasterizer: {n_features} features, CRS={src_crs_str[:60]}…',
                    progress=0.35, notif_id=_NOTIF,
                )

                # Build reprojection transformer (src → ref)
                try:
                    transformer = Transformer.from_crs(
                        src_crs_str, ref_crs, always_xy=True,
                    )
                    need_reproject = True
                except Exception:
                    need_reproject = False

                shapes_values: list[tuple] = []
                n_burned = 0

                for feat in src:
                    geom = shape(feat['geometry'])
                    if geom is None or geom.is_empty:
                        continue
                    if need_reproject:
                        try:
                            geom = shp_transform(transformer.transform, geom)
                        except Exception:
                            continue
                    val = burn_value
                    if burn_field and feat.get('properties') and burn_field in feat['properties']:
                        try:
                            val = float(feat['properties'][burn_field] or burn_value)
                        except (TypeError, ValueError):
                            pass
                    shapes_values.append((geom.__geo_interface__, val))
                    n_burned += 1

            if not shapes_values:
                send_notification('Shapefile Rasterizer: 0 features could be rasterized',
                                  level='warning', notif_id=_NOTIF)
                return {}

            send_notification(f'Shapefile Rasterizer: rasterizing {n_burned} features…',
                              progress=0.7, notif_id=_NOTIF)

            burned = rasterize(
                shapes_values,
                out_shape=(H, W),
                transform=ref_transform,
                fill=background,
                dtype='float32',
                all_touched=all_touched,
            )

        except Exception as e:
            send_notification(f'Shapefile Rasterizer: error: {e}',
                              level='error', notif_id=_NOTIF)
            return {}

        # Build outputs
        mask_u8 = (burned > background).astype(np.uint8) * 255

        out_geo = {
            **ref_geo,
            'bands':  burned[np.newaxis],
            'count':  1,
            'dtype':  'float32',
        }

        # Preview: green overlay on gray background
        preview = cv2.cvtColor((burned > background).astype(np.uint8) * 200, cv2.COLOR_GRAY2BGR)
        preview[:, :, 0] = 0    # zero Blue
        preview[:, :, 2] = 0    # zero Red → green channel only

        send_notification(
            f'Shapefile Rasterizer: {n_burned} features → '
            f'{int((burned > background).sum()):,} pixels burned',
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
