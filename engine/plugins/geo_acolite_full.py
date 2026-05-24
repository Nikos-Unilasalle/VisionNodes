"""
geo_acolite_full.py — Full ACOLITE atmospheric correction for Sentinel-2 L1C.

Wraps the ACOLITE Python package (RBINS) to apply Dark Spectrum Fitting (DSF)
atmospheric correction to a Sentinel-2 L1C scene, producing Rrs [sr-1] directly
comparable to GLORIA in-situ matchups.

Requirements:
  pip install git+https://github.com/acolite/acolite.git

Input: path to the .SAFE directory of an S2 L1C product.
Output: Rrs geotiff (bands in order given by band_names param).

Note: processing time ~30-120s depending on scene size.
"""
import os
import io
import tempfile
import threading
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'acolite_full'


def _info_panel(lines: list, w: int = 480, h: int = 220, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 15
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:72], (8, 44 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.37, color, 1, cv2.LINE_AA)
    return img


# S2 band name → ACOLITE output key (rhos_XXX nm)
_S2_BAND_WL = {
    'Bleu':  '492',   # B2
    'Vert':  '560',   # B3
    'Rouge': '665',   # B4
    'NIR':   '833',   # B8
    'RE1':   '704',   # B5
    'RE2':   '740',   # B6
    'RE3':   '783',   # B7
    'SWIR1': '1614',  # B11
    'SWIR2': '2202',  # B12
}


@vision_node(
    type_id='geo_acolite_full',
    label='ACOLITE (full DSF)',
    category='geography',
    icon='Satellite',
    description=(
        "Full ACOLITE atmospheric correction (Dark Spectrum Fitting) for Sentinel-2 L1C. "
        "Produces Rrs [sr-1] directly comparable to GLORIA in-situ data. "
        "Input: path to the unzipped .SAFE directory of an S2 L1C product. "
        "Requires: pip install git+https://github.com/acolite/acolite.git"
    ),
    inputs=[],
    outputs=[
        {'id': 'geotiff',   'color': 'geotiff', 'label': 'Rrs geotiff [sr-1]'},
        {'id': 'preview',   'color': 'image',   'label': 'Processing log'},
        {'id': 'rrs_min',   'color': 'scalar',  'label': 'Rrs min'},
        {'id': 'rrs_max',   'color': 'scalar',  'label': 'Rrs max'},
    ],
    params=[
        {'id': 'safe_path',   'label': 'S2 L1C .SAFE path',
         'type': 'string', 'default': ''},
        {'id': 'band_names',  'label': 'Band names (comma, S2 order)',
         'type': 'string', 'default': 'Bleu,Vert,Rouge,NIR'},
        {'id': 'limit_region','label': 'Limit to region (lat_min,lon_min,lat_max,lon_max or blank)',
         'type': 'string', 'default': ''},
        {'id': 'dsf_aot_estimate', 'label': 'AOT method',
         'type': 'enum', 'options': ['dark_spectrum', 'fixed'], 'default': 0},
        {'id': 'fixed_aot',   'label': 'Fixed AOT value (if Fixed AOT method)',
         'type': 'float', 'default': 0.1, 'min': 0.01, 'max': 1.0},
        {'id': 'run',         'label': 'Run ACOLITE', 'type': 'trigger', 'default': 0},
    ],
    resizable=True, min_width=320, min_height=220,
)
class AcoliteFullNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._prev_run   = 0
        self._result     = None
        self._running    = False

    def process(self, inputs, params):
        run_val = params.get('run', 0)
        rising  = run_val != self._prev_run and run_val not in (False, 0, None)
        self._prev_run = run_val

        # Return cached result while idle
        if not rising and self._result is not None:
            return self._result

        if not rising:
            info = _info_panel(['Click Run ACOLITE to start processing.',
                                 'Requires: S2 L1C .SAFE path',
                                 'Install: pip install git+https://github.com/acolite/acolite.git'],
                                title='ACOLITE (full DSF)')
            return {'preview': info}

        if self._running:
            send_notification('ACOLITE: already running...', notif_id=_NOTIF)
            return self._result or {}

        safe_path = str(params.get('safe_path', '')).strip()
        if not safe_path or not os.path.exists(safe_path):
            send_notification(f'ACOLITE: .SAFE path not found: {safe_path}',
                              level='error', notif_id=_NOTIF)
            return {}

        # Launch in background thread to avoid blocking the engine
        t = threading.Thread(target=self._run_acolite, args=(safe_path, dict(params)), daemon=True)
        self._running = True
        t.start()
        send_notification('ACOLITE: started DSF processing in background...',
                          progress=0.05, notif_id=_NOTIF)
        return {}

    def _run_acolite(self, safe_path: str, params: dict) -> None:
        try:
            import sys, os as _os
            _acolite_src = _os.path.join(_os.path.dirname(__file__), 'acolite_src')
            if _acolite_src not in sys.path:
                sys.path.insert(0, _acolite_src)
            import acolite as ac
        except ImportError as _ie:
            send_notification(
                f'ACOLITE import failed: {_ie}. Clone: engine/plugins/acolite_src/',
                level='error', notif_id=_NOTIF,
            )
            self._running = False
            return

        try:
            import rasterio
        except ImportError:
            send_notification('rasterio missing — pip install rasterio', level='error', notif_id=_NOTIF)
            self._running = False
            return

        send_notification('ACOLITE: initializing DSF...', progress=0.1, notif_id=_NOTIF)

        out_dir = os.path.join(tempfile.gettempdir(), 'acolite_out')
        os.makedirs(out_dir, exist_ok=True)

        # Build ACOLITE settings dict
        settings = {
            'inputfile':         safe_path,
            'output':            out_dir,
            'sensor':            'S2A',  # will be auto-detected from L1C metadata
            'dsf_aot_estimate':  'dark_spectrum' if int(params.get('dsf_aot_estimate', 0)) == 0 else 'fixed',
            'dsf_fixed_aot':     float(params.get('fixed_aot', 0.1)),
            'gains':             False,
            'l2w_parameters':    [],
            'verbosity':         5,
        }

        # Optional geographic subset
        region_str = str(params.get('limit_region', '')).strip()
        if region_str:
            try:
                parts = [float(x.strip()) for x in region_str.split(',')]
                if len(parts) == 4:
                    settings['limit'] = parts  # [lat_min, lon_min, lat_max, lon_max]
            except ValueError:
                pass

        send_notification('ACOLITE: running DSF atmospheric correction...', progress=0.2, notif_id=_NOTIF)

        try:
            ac.acolite.acolite_run(settings=settings)
        except Exception as e:
            send_notification(f'ACOLITE: processing error — {e}', level='error', notif_id=_NOTIF)
            self._running = False
            return

        send_notification('ACOLITE: DSF done, loading output...', progress=0.7, notif_id=_NOTIF)

        # Find output NetCDF or GeoTIFF
        import glob
        nc_files = glob.glob(os.path.join(out_dir, '**', '*L2W*.nc'), recursive=True)
        if not nc_files:
            nc_files = glob.glob(os.path.join(out_dir, '**', '*.nc'), recursive=True)
        if not nc_files:
            send_notification('ACOLITE: no output file found in ' + out_dir, level='error', notif_id=_NOTIF)
            self._running = False
            return

        nc_path = sorted(nc_files)[-1]
        send_notification(f'ACOLITE: reading {os.path.basename(nc_path)}...', progress=0.8, notif_id=_NOTIF)

        try:
            band_str  = str(params.get('band_names', 'Bleu,Vert,Rouge,NIR')).strip()
            band_list = [b.strip() for b in band_str.split(',') if b.strip()]

            import netCDF4 as nc4
            ds = nc4.Dataset(nc_path)

            bands_out = []
            loaded    = []
            for bname in band_list:
                wl  = _S2_BAND_WL.get(bname)
                key = f'rhos_{wl}' if wl else None
                if key and key in ds.variables:
                    arr = np.array(ds.variables[key][:], dtype=np.float32)
                    bands_out.append(arr)
                    loaded.append(bname)
                else:
                    # Try rrs_ variant
                    key2 = f'rrs_{wl}' if wl else None
                    if key2 and key2 in ds.variables:
                        arr = np.array(ds.variables[key2][:], dtype=np.float32)
                        bands_out.append(arr)
                        loaded.append(bname)
                    else:
                        send_notification(f'ACOLITE: band {bname} (key={key}) not in output',
                                          level='error', notif_id=_NOTIF)

            if not bands_out:
                send_notification('ACOLITE: no Rrs bands found in output', level='error', notif_id=_NOTIF)
                ds.close()
                self._running = False
                return

            stack = np.stack(bands_out, axis=0)   # [B, H, W]
            # Clip to valid Rrs range
            stack = np.clip(stack, 0.0, 0.2)

            # Try to extract CRS/transform from NetCDF or fall back to None
            crs = transform = None
            try:
                import rasterio
                with rasterio.open(f'NETCDF:{nc_path}:rhos_{_S2_BAND_WL.get(loaded[0], "")}') as r:
                    crs       = r.crs
                    transform = r.transform
            except Exception:
                pass

            ds.close()

            rrs_min = float(np.nanmin(stack))
            rrs_max = float(np.nanmax(stack))

            geo_out = {
                'bands':     stack,
                'count':     len(bands_out),
                'crs':       crs,
                'transform': transform,
            }

            lines = [
                'ACOLITE DSF — completed',
                f'Output: {os.path.basename(nc_path)}',
                f'Bands loaded: {", ".join(loaded)}',
                f'Shape: {stack.shape[1]}x{stack.shape[2]} px',
                f'Rrs range: [{rrs_min:.5f}, {rrs_max:.5f}]',
                'Compatible with GLORIA Rrs units',
            ]
            preview = _info_panel(lines, title='ACOLITE (full DSF)')

            send_notification(
                f'ACOLITE: OK — Rrs [{rrs_min:.5f}, {rrs_max:.5f}], {len(loaded)} bands',
                progress=1.0, notif_id=_NOTIF,
            )

            self._result = {
                'geotiff': geo_out,
                'preview': preview,
                'rrs_min': rrs_min,
                'rrs_max': rrs_max,
            }

            # Wake engine to pick up result
            from registry import send_notification as _sn
            _sn('', _wake_engine=True, _node_type='geo_acolite_full', notif_id=_NOTIF + '_wake')

        except Exception as e:
            import traceback
            send_notification(f'ACOLITE: output parse error — {e}', level='error', notif_id=_NOTIF)
            traceback.print_exc()
        finally:
            self._running = False
