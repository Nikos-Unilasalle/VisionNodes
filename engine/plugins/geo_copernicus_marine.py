import os
import json
import hashlib
import threading
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification, is_cancelled, clear_cancel, _notification_queue

_NOTIF_ID = 'copernicus_marine'
_SECRETS_PATH = os.path.expanduser('~/.vnstudio/secrets.json')

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
        {'id': '_sec_credentials', 'label': 'Credentials', 'type': 'section'},
        {'id': 'username',      'label': 'Username (Copernicus)',   'type': 'string', 'default': ''},
        {'id': 'password',      'label': 'Password (Copernicus)',   'type': 'string', 'default': ''},
        {'id': '_sec_dataset', 'label': 'Dataset', 'type': 'section'},
        {'id': 'dataset_id',    'label': 'Dataset ID',              'type': 'string', 'default': 'cmems_mod_glo_phy_anfc_0.083deg_PT1D-m'},
        {'id': 'variable',      'label': 'Variable name',           'type': 'string', 'default': 'thetao'},
        {'id': 'date_start',    'label': 'Start Date (YYYY-MM-DD)', 'type': 'string', 'default': '2023-01-01'},
        {'id': 'date_end',      'label': 'End Date (YYYY-MM-DD)',   'type': 'string', 'default': '2023-01-07'},
        {'id': 'bbox',          'label': 'BBox (lon_min,lat_min,lon_max,lat_max)', 'type': 'string', 'default': '-53.5,4.5,-51.5,6.5'},
        {'id': 'min_depth',     'label': 'Profondeur Min (m)',      'type': 'float',  'default': 0.0},
        {'id': 'max_depth',     'label': 'Profondeur Max (m)',      'type': 'float',  'default': 0.0},
        {'id': 'depth_idx',     'label': 'Index Profondeur (4D)',   'type': 'int',    'default': 0, 'min': 0, 'max': 100},
        {'id': 'service',       'label': 'Service / Protocole',     'type': 'enum',   'options': ['auto', 'arco-geo-series', 'arco-time-series', 'opendap', 'motu'], 'default': 0},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'colormap',      'label': 'Palette Couleur',          'type': 'enum',   'options': ['Viridis', 'Plasma', 'Jet', 'Inferno'], 'default': 0},
        {'id': '_sec_control', 'label': 'Cache & Control', 'type': 'section'},
        {'id': 'cache_dir',     'label': 'Dossier Cache',           'type': 'string', 'default': 'copernicus_marine_cache'},
        {'id': 'fetch',         'label': 'Télécharger',             'type': 'trigger', 'default': 0},
    ]
)
class GeoCopernicusMarineNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._prev_fetch      = 0
        self._loading         = False
        self._cache_data      = None   # (grids, meta)
        self._auto_tried      = False
        self._prev_dl_key     = None   # hash of download-relevant params
        self._generation      = 0      # bumped on every Fetch — older threads' writes ignored
        self._stop_event      = threading.Event()  # signal in-flight thread to stop
        self._notif_id        = f'copernicus_marine_{id(self)}'

    @staticmethod
    def _load_secrets() -> dict:
        try:
            if os.path.exists(_SECRETS_PATH):
                with open(_SECRETS_PATH) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @staticmethod
    def _save_secrets(data: dict) -> None:
        os.makedirs(os.path.dirname(_SECRETS_PATH), exist_ok=True)
        try:
            existing = GeoCopernicusMarineNode._load_secrets()
            existing.update(data)
            with open(_SECRETS_PATH, 'w') as f:
                json.dump(existing, f)
        except Exception:
            pass

    @staticmethod
    def _dl_params_key(params: dict) -> str:
        # depth_idx sélectionne la couche APRÈS téléchargement → hors clé
        # pour éviter de réinitialiser _auto_tried à chaque frame quand
        # depth_idx est piloté par un scalar_input externe.
        keys = ('dataset_id', 'variable', 'bbox', 'date_start', 'date_end',
                'min_depth', 'max_depth', 'service', 'cache_dir')
        s = json.dumps({k: params.get(k) for k in keys}, sort_keys=True)
        return hashlib.md5(s.encode()).hexdigest()

    def process(self, inputs, params):
        # Determine parameters (inputs override params if connected)
        params = params.copy()
        if inputs.get('bbox') is not None:
            params['bbox'] = inputs['bbox']
        if inputs.get('date_start') is not None:
            params['date_start'] = inputs['date_start']
        if inputs.get('date_end') is not None:
            params['date_end'] = inputs['date_end']

        dl_key = self._dl_params_key(params)
        if dl_key != self._prev_dl_key:
            self._prev_dl_key = dl_key
            self._cache_data  = None
            self._auto_tried  = False

        fetch_val = params.get('fetch', 0)
        rising = fetch_val != self._prev_fetch and fetch_val not in (False, 0, None)
        self._prev_fetch = fetch_val

        if rising:
            self._generation += 1
            self._stop_event.set()
            my_gen = self._generation
            self._loading = True
            self._auto_tried = True
            threading.Thread(
                target=self._do_fetch, args=(params,),
                kwargs={'my_gen': my_gen}, daemon=True,
            ).start()

        elif self._cache_data is None and not self._loading and not self._auto_tried:
            self._auto_tried = True
            self._generation += 1
            my_gen = self._generation
            self._loading = True
            threading.Thread(
                target=self._do_fetch, args=(params,),
                kwargs={'auto': True, 'my_gen': my_gen}, daemon=True,
            ).start()

        if self._cache_data is None:
            return {'grids': None, 'preview': None, 'meta': None}

        grids, meta = self._cache_data
        colormap_idx = int(params.get('colormap', 0))
        T, H, W = grids.shape
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
                stretched = np.clip((f_arr - p2) / (p98 - p2) * 255, 0, 255)
                stretched[~valid_mask] = 0
                stretched = stretched.astype(np.uint8)
            cmaps = [cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_PLASMA, cv2.COLORMAP_JET, cv2.COLORMAP_INFERNO]
            cmap = cmaps[min(colormap_idx, len(cmaps) - 1)]
            color_img = cv2.applyColorMap(stretched, cmap)
            color_img[~valid_mask] = [40, 40, 40]
            preview_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        return {
            'grids': grids,
            'preview': preview_img,
            'meta': meta
        }

    def _do_fetch(self, params: dict, auto: bool = False, my_gen: int = 0) -> None:
        self._stop_event.clear()
        try:
            self._do_fetch_impl(params, auto=auto, my_gen=my_gen)
        except BaseException as e:
            if self._generation == my_gen:
                send_notification(f"Copernicus Marine: unexpected crash: {e}", level='error', notif_id=self._notif_id)
        finally:
            if self._generation == my_gen:
                self._loading = False

    def _do_fetch_impl(self, params: dict, auto: bool = False, my_gen: int = 0) -> None:
        username = params.get('username', '').strip()
        password = params.get('password', '').strip()
        secrets = self._load_secrets()

        if username:
            self._save_secrets({
                'copernicus_marine_username': username,
                'copernicus_marine_password': password
            })
        else:
            username = secrets.get('copernicus_marine_username', '')
            password = secrets.get('copernicus_marine_password', '')

        dataset_id = str(params.get('dataset_id') or '').strip()
        variable   = str(params.get('variable')   or '').strip()
        bbox_val = params.get('bbox', '').strip()
        date_start = params.get('date_start', '').strip()
        date_end = params.get('date_end', '').strip()
        min_depth = float(params.get('min_depth', 0.0))
        max_depth = float(params.get('max_depth', 0.0))
        depth_idx = int(params.get('depth_idx', 0))
        service_idx = int(params.get('service', 0))
        raw_cache = str(params.get('cache_dir', 'copernicus_marine_cache') or 'copernicus_marine_cache').strip()

        if not dataset_id or not variable:
            if not auto:
                send_notification("Copernicus Marine: Dataset ID et Variable requis", level='warning', notif_id=self._notif_id)
            return

        if not bbox_val:
            if not auto:
                send_notification("Copernicus Marine: Bounding box manquante", level='warning', notif_id=self._notif_id)
            return

        # Parse bbox: 'lon_min,lat_min,lon_max,lat_max'
        try:
            coords = [float(x.strip()) for x in bbox_val.split(',')]
            if len(coords) != 4:
                raise ValueError("Format invalide")
            min_lon, min_lat, max_lon, max_lat = coords
        except Exception:
            if not auto:
                send_notification(f"Copernicus Marine: BBox invalide '{bbox_val}'", level='error', notif_id=self._notif_id)
            return

        # Caching logic based on params hash
        cache_str = f"{dataset_id}_{variable}_{bbox_val}_{date_start}_{date_end}_{min_depth}_{max_depth}_{service_idx}"
        cache_hash = hashlib.md5(cache_str.encode()).hexdigest()
        _engine_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = raw_cache if os.path.isabs(raw_cache) else os.path.join(_engine_dir, raw_cache)
        os.makedirs(cache_dir, exist_ok=True)
        nc_file_path = os.path.join(cache_dir, f"{cache_hash}.nc")

        if auto:
            if not os.path.exists(nc_file_path):
                return

        if not os.path.exists(nc_file_path):
            if not username or not password:
                send_notification("Copernicus Marine: Identifiants (Username/Password) requis pour télécharger", level='error', notif_id=self._notif_id)
                return

            if not self.ensure_packages(['copernicusmarine', 'xarray', 'netCDF4'], notif_id=self._notif_id):
                return

            send_notification(f"Copernicus Marine: Téléchargement en cours...", progress=0.1, notif_id=self._notif_id)
            
            if self._generation != my_gen or is_cancelled(self._notif_id):
                return

            import copernicusmarine
            try:
                # Prepare subset arguments
                subset_kwargs = {
                    'dataset_id': dataset_id,
                    'username': username,
                    'password': password,
                    'variables': [variable],
                    'minimum_longitude': min_lon,
                    'maximum_longitude': max_lon,
                    'minimum_latitude': min_lat,
                    'maximum_latitude': max_lat,
                    'start_datetime': f"{date_start}T00:00:00",
                    'end_datetime': f"{date_end}T23:59:59",
                    'output_filename': nc_file_path,
                    'overwrite': True
                }

                if min_depth != 0.0 or max_depth != 0.0:
                    subset_kwargs['minimum_depth'] = min_depth
                    subset_kwargs['maximum_depth'] = max_depth

                service_opts = ['auto', 'arco-geo-series', 'arco-time-series', 'opendap', 'motu']
                service_val = service_opts[min(service_idx, len(service_opts) - 1)]
                if service_val != 'auto':
                    subset_kwargs['service'] = service_val

                # Run subset download
                copernicusmarine.subset(**subset_kwargs)
                if self._generation != my_gen or is_cancelled(self._notif_id):
                    if os.path.exists(nc_file_path):
                        os.remove(nc_file_path)
                    return
                send_notification(f"Copernicus Marine: Téléchargement terminé !", progress=0.9, notif_id=self._notif_id)
            except Exception as e:
                # Clean up incomplete file if any
                if os.path.exists(nc_file_path):
                    try:
                        os.remove(nc_file_path)
                    except:
                        pass
                send_notification(f"Copernicus Marine: Erreur de téléchargement: {e}", level='error', notif_id=self._notif_id)
                return

        if not self.ensure_packages(['xarray', 'netCDF4'], notif_id=self._notif_id):
            return

        # Load file using xarray
        import xarray as xr
        try:
            ds = xr.open_dataset(nc_file_path)
        except Exception as e:
            send_notification(f"Copernicus Marine: Erreur d'ouverture du fichier NetCDF: {e}", level='error', notif_id=self._notif_id)
            return

        if variable not in ds.variables:
            send_notification(f"Copernicus Marine: Variable '{variable}' non trouvée dans le dataset", level='error', notif_id=self._notif_id)
            ds.close()
            return

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

        meta = {
            'dataset_id': dataset_id,
            'variable': variable,
            'shape': list(grids.shape),
            'lon_min': float(ds_var.longitude.min()) if 'longitude' in ds_var.coords else min_lon,
            'lon_max': float(ds_var.longitude.max()) if 'longitude' in ds_var.coords else max_lon,
            'lat_min': float(ds_var.latitude.min()) if 'latitude' in ds_var.coords else min_lat,
            'lat_max': float(ds_var.latitude.max()) if 'latitude' in ds_var.coords else max_lat,
            'time_len': T,
            'cache_path': nc_file_path,
        }

        # Keep dataset closed to allow cleanup/re-download
        ds.close()

        if self._generation != my_gen or is_cancelled(self._notif_id):
            return

        self._cache_data = (grids, meta)
        send_notification(f"Copernicus Marine: Prêt !", progress=1.0, notif_id=self._notif_id)

        # Wake static-graph engine
        _notification_queue.put_nowait({
            '_wake_engine': True,
            '_node_type': 'geo_copernicus_marine',
            '_notif_id': self._notif_id
        })
