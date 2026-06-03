import os
import hashlib
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification, is_cancelled, clear_cancel

_NOTIF_ID = 'copernicus_marine'

@vision_node(
    type_id='geo_copernicus_marine',
    label='Copernicus Marine Downloader',
    category='geography',
    icon='CloudDownload',
    description=(
        "Télécharge des grilles spatio-temporelles depuis Copernicus Marine Service (CMEMS). "
        "Utilise l'API de sous-ensemble (subset) pour récupérer les données directement au format NetCDF. "
        "Requiert les identifiants Copernicus Marine (username / password)."
    ),
    inputs=[
        {'id': 'bbox',       'color': 'string', 'label': 'BBox (str)'},
        {'id': 'date_start', 'color': 'string', 'label': 'Start Date'},
        {'id': 'date_end',   'color': 'string', 'label': 'End Date'},
    ],
    outputs=[
        {'id': 'grids',      'color': 'any',    'label': 'Grids (T x H x W)'},
        {'id': 'preview',    'color': 'image',  'label': 'Preview First Frame'},
        {'id': 'meta',       'color': 'dict',   'label': 'Meta'},
    ],
    params=[
        {'id': 'username',      'label': 'Username (Copernicus)',   'type': 'string', 'default': ''},
        {'id': 'password',      'label': 'Password (Copernicus)',   'type': 'string', 'default': ''},
        {'id': 'dataset_id',    'label': 'Dataset ID',              'type': 'string', 'default': 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m'},
        {'id': 'variable',      'label': 'Variable name',           'type': 'string', 'default': 'thetao'},
        {'id': 'date_start',    'label': 'Start Date (YYYY-MM-DD)', 'type': 'string', 'default': '2023-01-01'},
        {'id': 'date_end',      'label': 'End Date (YYYY-MM-DD)',   'type': 'string', 'default': '2023-01-07'},
        {'id': 'bbox',          'label': 'BBox (lon_min,lat_min,lon_max,lat_max)', 'type': 'string', 'default': '-53.5,4.5,-51.5,6.5'},
        {'id': 'depth_idx',     'label': 'Index Profondeur (4D)',   'type': 'int',    'default': 0, 'min': 0, 'max': 100},
        {'id': 'colormap',      'label': 'Palette Couleur',          'type': 'enum',   'options': ['Viridis', 'Plasma', 'Jet', 'Inferno'], 'default': 0},
        {'id': 'fetch',         'label': 'Télécharger',             'type': 'trigger', 'default': 0},
    ]
)
class GeoCopernicusMarineNode(NodeProcessor):
    def process(self, inputs, params):
        # Determine parameters (inputs override params if connected)
        bbox_val = inputs.get('bbox') or params.get('bbox')
        date_start = inputs.get('date_start') or params.get('date_start')
        date_end = inputs.get('date_end') or params.get('date_end')

        username = params.get('username', '').strip()
        password = params.get('password', '').strip()
        dataset_id = params.get('dataset_id', '').strip()
        variable = params.get('variable', '').strip()
        depth_idx = int(params.get('depth_idx', 0))
        colormap_idx = int(params.get('colormap', 0))

        if not dataset_id or not variable:
            send_notification("Copernicus Marine: Dataset ID et Variable requis", level='warning', notif_id=_NOTIF_ID)
            return {}

        if not bbox_val:
            send_notification("Copernicus Marine: Bounding box manquante", level='warning', notif_id=_NOTIF_ID)
            return {}

        # Parse bbox: 'lon_min,lat_min,lon_max,lat_max'
        try:
            coords = [float(x.strip()) for x in bbox_val.split(',')]
            if len(coords) != 4:
                raise ValueError("Format invalide")
            min_lon, min_lat, max_lon, max_lat = coords
        except Exception:
            send_notification(f"Copernicus Marine: BBox invalide '{bbox_val}'", level='error', notif_id=_NOTIF_ID)
            return {}

        if not self.ensure_packages(['copernicusmarine', 'xarray', 'netCDF4'], notif_id=_NOTIF_ID):
            return {}

        # Caching logic based on params hash
        cache_str = f"{dataset_id}_{variable}_{bbox_val}_{date_start}_{date_end}"
        cache_hash = hashlib.md5(cache_str.encode()).hexdigest()
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'copernicus_marine_cache')
        os.makedirs(cache_dir, exist_ok=True)
        nc_file_path = os.path.join(cache_dir, f"{cache_hash}.nc")

        if not os.path.exists(nc_file_path):
            if not username or not password:
                send_notification("Copernicus Marine: Identifiants (Username/Password) requis pour télécharger", level='error', notif_id=_NOTIF_ID)
                return {}

            send_notification(f"Copernicus Marine: Téléchargement en cours...", progress=0.1, notif_id=_NOTIF_ID)
            
            import copernicusmarine
            try:
                # Run subset download
                copernicusmarine.subset(
                    dataset_id=dataset_id,
                    username=username,
                    password=password,
                    variables=[variable],
                    minimum_longitude=min_lon,
                    maximum_longitude=max_lon,
                    minimum_latitude=min_lat,
                    maximum_latitude=max_lat,
                    start_datetime=f"{date_start}T00:00:00",
                    end_datetime=f"{date_end}T23:59:59",
                    output_filename=nc_file_path,
                    force_download=True
                )
                send_notification(f"Copernicus Marine: Téléchargement terminé !", progress=0.9, notif_id=_NOTIF_ID)
            except Exception as e:
                # Clean up incomplete file if any
                if os.path.exists(nc_file_path):
                    try:
                        os.remove(nc_file_path)
                    except:
                        pass
                send_notification(f"Copernicus Marine: Erreur de téléchargement: {e}", level='error', notif_id=_NOTIF_ID)
                return {}

        # Load file using xarray
        import xarray as xr
        try:
            ds = xr.open_dataset(nc_file_path)
        except Exception as e:
            send_notification(f"Copernicus Marine: Erreur d'ouverture du fichier NetCDF: {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        if variable not in ds.variables:
            send_notification(f"Copernicus Marine: Variable '{variable}' non trouvée dans le dataset", level='error', notif_id=_NOTIF_ID)
            return {}

        ds_var = ds[variable]

        # Select depth if 4D
        if 'depth' in ds_var.dims:
            depth_size = ds_var.sizes['depth']
            depth_idx = min(max(0, depth_idx), depth_size - 1)
            ds_var = ds_var.isel(depth=depth_idx)

        # Coordinate sorting/orientation
        if 'latitude' in ds_var.coords:
            ds_var = ds_var.sortby('latitude', ascending=True)
        if 'longitude' in ds_var.coords:
            ds_var = ds_var.sortby('longitude', ascending=True)

        # Check time dimension
        time_dim = None
        for dim in ['time', 't']:
            if dim in ds_var.dims:
                time_dim = dim
                break

        if time_dim is None:
            # 2D Grid case, expand to 3D with single step
            grids = ds_var.values[np.newaxis, :, :]
        else:
            grids = ds_var.values

        T, H, W = grids.shape

        # Build preview of first frame
        f_arr = grids[0]
        valid_mask = ~np.isnan(f_arr)
        valid_pixels = f_arr[valid_mask]

        if valid_pixels.size == 0:
            preview_img = np.zeros((H, W, 3), dtype=np.uint8)
        else:
            p2, p98 = np.percentile(valid_pixels, (2, 98))
            if p98 == p2:
                stretched = np.zeros_like(f_arr, dtype=np.uint8)
            else:
                stretched = np.clip((f_arr - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
            
            stretched[~valid_mask] = 0
            
            cmaps = [
                cv2.COLORMAP_VIRIDIS,
                cv2.COLORMAP_PLASMA,
                cv2.COLORMAP_JET,
                cv2.COLORMAP_INFERNO
            ]
            cmap = cmaps[min(colormap_idx, len(cmaps) - 1)]
            color_img = cv2.applyColorMap(stretched, cmap)
            color_img[~valid_mask] = [40, 40, 40]  # Land mask
            preview_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        meta = {
            'dataset_id': dataset_id,
            'variable': variable,
            'shape': list(grids.shape),
            'lon_min': float(ds_var.longitude.min()) if 'longitude' in ds_var.coords else min_lon,
            'lon_max': float(ds_var.longitude.max()) if 'longitude' in ds_var.coords else max_lon,
            'lat_min': float(ds_var.latitude.min()) if 'latitude' in ds_var.coords else min_lat,
            'lat_max': float(ds_var.latitude.max()) if 'latitude' in ds_var.coords else max_lat,
            'time_len': T,
        }

        # Keep dataset closed to allow cleanup/re-download
        ds.close()

        return {
            'grids': grids,
            'preview': preview_img,
            'meta': meta
        }
