import os
import glob
import numpy as np
import cv2
import base64
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'netcdf_reader'

@vision_node(
    type_id='geo_netcdf_reader',
    label='NetCDF Grid Reader',
    category='geography',
    icon='Globe',
    description=(
        "Lit un fichier NetCDF (.nc) ou un dossier de fichiers NetCDF. "
        "Extrait une variable sous forme de tenseur 3D (Temps x Lat x Lon)."
    ),
    inputs=[],
    outputs=[
        {'id': 'grids',       'color': 'any',    'label': 'Grids (T x H x W)'},
        {'id': 'preview',     'color': 'image',  'label': 'Aperçu (1ère frame)'},
        {'id': 'meta',        'color': 'dict',   'label': 'Meta'},
    ],
    params=[
        {'id': 'path',         'label': 'Chemin (Fichier ou Dossier)',    'type': 'string', 'default': ''},
        {'id': 'variable',     'label': 'Variable (vide = auto)',         'type': 'string', 'default': ''},
        {'id': 'depth_idx',    'label': 'Index Profondeur (si 4D)',      'type': 'int',    'default': 0, 'min': 0, 'max': 500},
        {'id': 'lat_range',    'label': 'Plage Latitudes (ex: -40,-30)', 'type': 'string', 'default': ''},
        {'id': 'lon_range',    'label': 'Plage Longitudes (ex: -40,-30)','type': 'string', 'default': ''},
        {'id': 'colormap',     'label': 'Palette Couleur',                'type': 'enum',   'options': ['Viridis', 'Plasma', 'Jet', 'Inferno', 'Rainbow'], 'default': 0},
    ]
)
class NetCDFGridReaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_path = None
        self._cache_data = None
        self._pending_thumb = None

    def _apply_colormap(self, grid, colormap_idx):
        # Drop NaNs for stretching
        valid = grid[~np.isnan(grid)]
        if valid.size == 0:
            return np.zeros((grid.shape[0], grid.shape[1], 3), dtype=np.uint8)
        
        p2, p98 = np.percentile(valid, (2, 98))
        if p98 == p2:
            stretched = np.zeros_like(grid, dtype=np.uint8)
        else:
            stretched = np.clip((grid - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
        
        # Handle NaNs in the final image (render as dark grey/black)
        mask_nan = np.isnan(grid)
        stretched[mask_nan] = 0

        cmaps = [
            cv2.COLORMAP_VIRIDIS,
            cv2.COLORMAP_PLASMA,
            cv2.COLORMAP_JET,
            cv2.COLORMAP_INFERNO,
            cv2.COLORMAP_RAINBOW
        ]
        cmap = cmaps[min(colormap_idx, len(cmaps) - 1)]
        color_img = cv2.applyColorMap(stretched, cmap)
        
        # Draw NaN mask in dark grey (e.g. land)
        color_img[mask_nan] = [40, 40, 40]
        return color_img

    def process(self, inputs, params):
        if not self.ensure_packages(['xarray', 'netCDF4'], pip_names=['xarray', 'netcdf4'], notif_id=_NOTIF_ID):
            return {'grids': None, 'preview': None, 'meta': None}

        import xarray as xr

        path = params.get('path', '').strip()
        if not path or not os.path.exists(path):
            return {'grids': None, 'preview': None, 'meta': None}

        var_name = params.get('variable', '').strip()
        depth_idx = int(params.get('depth_idx', 0))
        lat_range_str = params.get('lat_range', '').strip()
        lon_range_str = params.get('lon_range', '').strip()
        colormap_idx = int(params.get('colormap', 0))

        # Check cache
        cache_key = (path, var_name, depth_idx, lat_range_str, lon_range_str)
        if cache_key != self._cache_path or self._cache_data is None:
            try:
                # 1. Identify files
                if os.path.isdir(path):
                    files = sorted(glob.glob(os.path.join(path, "*.nc")))
                    if not files:
                        send_notification("NetCDF Reader: Aucun fichier .nc trouvé dans le dossier", level='warning', notif_id=_NOTIF_ID)
                        return {'grids': None, 'preview': None, 'meta': None}
                    
                    send_notification(f"NetCDF: Chargement de {len(files)} fichiers...", progress=0.2, notif_id=_NOTIF_ID)
                    # Open multiple datasets and combine along time
                    ds = xr.open_mfdataset(files, combine='by_coords')
                else:
                    send_notification(f"NetCDF: Chargement du fichier {os.path.basename(path)}...", progress=0.2, notif_id=_NOTIF_ID)
                    ds = xr.open_dataset(path)

                # 2. Variable selection
                all_vars = [v for v in ds.data_vars]
                if not var_name:
                    # Auto select the first variable with >= 3 dims
                    candidates = [v for v in all_vars if len(ds[v].dims) >= 3]
                    if candidates:
                        var_name = candidates[0]
                    elif all_vars:
                        var_name = all_vars[0]
                    else:
                        send_notification("NetCDF Reader: Aucune variable trouvée dans le dataset", level='error', notif_id=_NOTIF_ID)
                        return {'grids': None, 'preview': None, 'meta': None}

                if var_name not in ds.data_vars:
                    send_notification(f"NetCDF Reader: Variable '{var_name}' introuvable. Variables dispo: {all_vars}", level='error', notif_id=_NOTIF_ID)
                    return {'grids': None, 'preview': None, 'meta': None}

                da = ds[var_name]

                # 3. Detect dimensions
                lat_dim, lon_dim, time_dim, depth_dim = None, None, None, None
                for dim in da.dims:
                    dim_lower = dim.lower()
                    if 'lat' in dim_lower or 'y' == dim_lower:
                        lat_dim = dim
                    elif 'lon' in dim_lower or 'x' == dim_lower:
                        lon_dim = dim
                    elif 'time' in dim_lower or 't' == dim_lower:
                        time_dim = dim
                    elif 'depth' in dim_lower or 'z' == dim_lower or 'level' in dim_lower:
                        depth_dim = dim

                # Fallback to order if not detected
                if not lat_dim or not lon_dim:
                    send_notification("NetCDF Reader: Dimensions de latitude/longitude non détectées", level='error', notif_id=_NOTIF_ID)
                    return {'grids': None, 'preview': None, 'meta': None}

                # 4. Slice spatial bounding box
                slice_dict = {}
                if lat_range_str and lat_dim in da.coords:
                    try:
                        lmin, lmax = map(float, lat_range_str.split(','))
                        # Handle ascending or descending coordinate axis
                        coord_vals = da[lat_dim].values
                        if coord_vals[0] > coord_vals[-1]:
                            slice_dict[lat_dim] = slice(lmax, lmin)
                        else:
                            slice_dict[lat_dim] = slice(lmin, lmax)
                    except Exception:
                        send_notification("NetCDF Reader: Format Plage Latitude invalide (attendu: min,max)", level='warning', notif_id=_NOTIF_ID)

                if lon_range_str and lon_dim in da.coords:
                    try:
                        lmin, lmax = map(float, lon_range_str.split(','))
                        coord_vals = da[lon_dim].values
                        if coord_vals[0] > coord_vals[-1]:
                            slice_dict[lon_dim] = slice(lmax, lmin)
                        else:
                            slice_dict[lon_dim] = slice(lmin, lmax)
                    except Exception:
                        send_notification("NetCDF Reader: Format Plage Longitude invalide (attendu: min,max)", level='warning', notif_id=_NOTIF_ID)

                if slice_dict:
                    da = da.sel(**slice_dict)

                # 5. Handle depth index for 4D datasets
                if depth_dim and depth_dim in da.dims:
                    if da.sizes[depth_dim] > 1:
                        d_idx = min(depth_idx, da.sizes[depth_dim] - 1)
                        da = da.isel({depth_dim: d_idx})
                    else:
                        da = da.squeeze(dim=depth_dim)

                # 6. Extract values (Ensure we end up with T x H x W shape)
                # Reorder dims if necessary to (time, lat, lon)
                target_dims = []
                if time_dim and time_dim in da.dims:
                    target_dims.append(time_dim)
                target_dims.extend([lat_dim, lon_dim])
                
                # Squeeze any remaining single-dimension coords
                da = da.transpose(*target_dims)
                grids = da.values.astype(float)

                # If no time dimension, add dummy dimension of size 1
                if len(grids.shape) == 2:
                    grids = np.expand_dims(grids, axis=0)

                # Save metadata
                meta = {
                    'variable_selected': var_name,
                    'shape': list(grids.shape),
                    'latitude_dim': lat_dim,
                    'longitude_dim': lon_dim,
                    'time_dim': time_dim,
                    'variables_available': all_vars,
                }
                if lat_dim in da.coords:
                    meta['lat_min'] = float(da[lat_dim].min())
                    meta['lat_max'] = float(da[lat_dim].max())
                if lon_dim in da.coords:
                    meta['lon_min'] = float(da[lon_dim].min())
                    meta['lon_max'] = float(da[lon_dim].max())

                self._cache_data = {
                    'grids': grids,
                    'meta': meta
                }
                self._cache_path = cache_key
                self._pending_thumb = True
                send_notification(f"NetCDF: {grids.shape[0]} frames de taille {grids.shape[1]}x{grids.shape[2]} chargées.", progress=1.0, notif_id=_NOTIF_ID)

            except Exception as e:
                send_notification(f"NetCDF Reader error: {e}", level='error', notif_id=_NOTIF_ID)
                return {'grids': None, 'preview': None, 'meta': None}

        grids = self._cache_data['grids']
        meta = self._cache_data['meta']

        # Generate preview (Frame 0)
        first_frame = grids[0]
        preview = self._apply_colormap(first_frame, colormap_idx)

        # Base64 thumbnail for flow preview
        out_thumb = None
        if self._pending_thumb:
            h, w = preview.shape[:2]
            sc = 120 / h if h > 0 else 1.0
            thumb_img = cv2.resize(preview, (max(1, int(w * sc)), 120))
            _, buf = cv2.imencode('.jpg', thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
            out_thumb = base64.b64encode(buf).decode('utf-8')
            self._pending_thumb = None

        return {
            'grids': grids,
            'preview': preview,
            'meta': meta,
            '_thumb': out_thumb
        }
