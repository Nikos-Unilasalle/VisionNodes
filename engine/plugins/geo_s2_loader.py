from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import os
import glob
import base64

try:
    import rasterio
    from rasterio.enums import Resampling
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


def _stretch(band):
    valid = band[band > 0]
    if valid.size == 0:
        return np.zeros_like(band, dtype=np.uint8)
    p2, p98 = np.percentile(valid, (2, 98))
    if p98 <= p2:
        return np.full_like(band, 128, dtype=np.uint8)
    return np.clip((band - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)


def _load_band(path, target_shape=None):
    """Load single-band file (JP2/TIF). Resample to target_shape if given."""
    with rasterio.open(path) as src:
        transform = src.transform
        crs       = src.crs
        nodata    = src.nodata
        if target_shape is None:
            data = src.read(1).astype(np.float32)
        else:
            out_h, out_w = target_shape
            data = src.read(
                1,
                out_shape=(out_h, out_w),
                resampling=Resampling.bilinear
            ).astype(np.float32)
    if nodata is not None:
        data[data == nodata] = 0
    return data, transform, crs


def _find_band(root_dir, band_id, resolution):
    """Find a Sentinel-2 band file.

    Supports:
    - IMG_DATA/R10m/*_B03_10m.jp2
    - IMG_DATA/*_B03_10m.jp2  (flat structure)
    - SAFE root or any parent folder (recursive up to 6 levels)
    """
    band  = band_id.upper()   # 'B03', 'B11', etc.
    res   = resolution         # '10m', '20m'
    exts  = ('jp2', 'tif', 'tiff')

    # Ordered search: specific subfolder first (fastest), then flat, then recursive
    patterns = []
    for ext in exts:
        patterns += [
            os.path.join(root_dir, f'R{res}', f'*_{band}_{res}.{ext}'),
            os.path.join(root_dir, f'*_{band}_{res}.{ext}'),
            os.path.join(root_dir, '**', f'R{res}', f'*_{band}_{res}.{ext}'),
            os.path.join(root_dir, '**', f'*_{band}_{res}.{ext}'),
        ]

    for pat in patterns:
        hits = glob.glob(pat, recursive=True)
        if hits:
            # Prefer shortest path (most specific match)
            return sorted(hits, key=len)[0]
    return None


def _auto_detect_bands(img_data_dir):
    """Scan IMG_DATA (or SAFE root) and return discovered band paths."""
    return {
        'b3_path':  _find_band(img_data_dir, 'B03', '10m'),
        'b4_path':  _find_band(img_data_dir, 'B04', '10m'),
        'b8_path':  _find_band(img_data_dir, 'B08', '10m'),
        'b11_path': _find_band(img_data_dir, 'B11', '20m'),
        'b2_path':  _find_band(img_data_dir, 'B02', '10m'),
        'scl_path': _find_band(img_data_dir, 'SCL', '20m'),
    }


@vision_node(
    type_id='geo_s2_loader',
    label='Sentinel-2 Loader',
    category='geography',
    icon='Satellite',
    description=(
        "Load Sentinel-2 bands for turbidity analysis (B03, B04, B08, B11, optional B02). "
        "Auto mode: point img_data_path to the IMG_DATA folder (or SAFE root) — "
        "band files are discovered automatically. "
        "Individual path fields override auto-detected values. "
        "B11 (20m) is resampled to 10m via bilinear interpolation."
    ),
    inputs=[],
    outputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'Bands (B3,B4,B8,B11)'},
        {'id': 'preview',  'color': 'image',   'label': 'Preview RGB'},
        {'id': 'meta',     'color': 'dict',     'label': 'Meta'},
    ],
    params=[
        {'id': 'img_data_path', 'type': 'string', 'default': '', 'label': '📁 IMG_DATA (auto-detect)'},
        {'id': 'b3_path',       'type': 'string', 'default': '', 'label': 'B3 Green override'},
        {'id': 'b4_path',       'type': 'string', 'default': '', 'label': 'B4 Red override'},
        {'id': 'b8_path',       'type': 'string', 'default': '', 'label': 'B8 NIR override'},
        {'id': 'b11_path',      'type': 'string', 'default': '', 'label': 'B11 SWIR override'},
        {'id': 'b2_path',       'type': 'string', 'default': '', 'label': 'B2 Blue override (opt)'},
        {'id': 'scl_path',      'type': 'string', 'default': '', 'label': 'SCL Cloud mask override (opt)'},
    ]
)
class Sentinel2LoaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key  = None
        self._cache_data = None

    def process(self, inputs, params):
        if not RASTERIO_AVAILABLE:
            send_notification('rasterio missing: pip install rasterio', level='error', notif_id='s2_loader')
            return {'geotiff': None, 'preview': None, 'meta': None}

        # --- Resolve paths: auto-detect then apply manual overrides ---
        img_data_dir = params.get('img_data_path', '').strip()
        auto = {}
        if img_data_dir and os.path.isdir(img_data_dir):
            send_notification('S2: scan IMG_DATA…', progress=0.02, notif_id='s2_loader')
            auto = _auto_detect_bands(img_data_dir)
            found_names = [k.replace('_path', '').upper() for k, v in auto.items() if v]
            missing_auto = [k.replace('_path', '').upper() for k, v in auto.items()
                            if not v and k != 'b2_path']
            if missing_auto:
                send_notification(
                    f'S2 auto: introuvable: {missing_auto}', level='warn', notif_id='s2_loader'
                )
            else:
                send_notification(
                    f'S2 auto: {len(found_names)} bandes trouvées → {found_names}',
                    progress=0.04, notif_id='s2_loader'
                )

        # Manual params override auto-detected values
        paths = {
            k: params.get(k, '').strip() or auto.get(k) or ''
            for k in ('b3_path', 'b4_path', 'b8_path', 'b11_path', 'b2_path', 'scl_path')
        }

        # Validate required bands
        required_keys = ('b3_path', 'b4_path', 'b8_path', 'b11_path')
        missing = [k for k in required_keys if not paths[k] or not os.path.exists(paths[k])]
        if missing:
            if any(paths[k] for k in required_keys):
                send_notification(
                    f'S2: fichiers manquants: {[k.replace("_path","").upper() for k in missing]}',
                    level='warn', notif_id='s2_loader'
                )
            return {'geotiff': None, 'preview': None, 'meta': None}

        # Cache check
        cache_key = tuple(paths[k] for k in sorted(paths))
        if cache_key == self._cache_key:
            geo = self._cache_data
        else:
            try:
                send_notification('S2: lecture B3…', progress=0.05, notif_id='s2_loader')

                with rasterio.open(paths['b3_path']) as src:
                    ref_h, ref_w = src.height, src.width
                    ref_transform = src.transform
                    ref_crs = src.crs

                b3, _, _ = _load_band(paths['b3_path'])
                send_notification(f'S2: B3 OK ({ref_w}×{ref_h}) — lecture B4…', progress=0.25, notif_id='s2_loader')
                b4, _, _ = _load_band(paths['b4_path'], (ref_h, ref_w))
                send_notification('S2: B4 OK — lecture B8…', progress=0.45, notif_id='s2_loader')
                b8, _, _ = _load_band(paths['b8_path'], (ref_h, ref_w))
                send_notification('S2: B8 OK — lecture B11 (20m→10m)…', progress=0.65, notif_id='s2_loader')
                b11, _, _ = _load_band(paths['b11_path'], (ref_h, ref_w))
                send_notification('S2: B11 OK — empilement…', progress=0.82, notif_id='s2_loader')

                band_arrays = [b3, b4, b8, b11]
                band_names  = ['B3', 'B4', 'B8', 'B11']

                if paths['b2_path'] and os.path.exists(paths['b2_path']):
                    send_notification('S2: lecture B2…', progress=0.88, notif_id='s2_loader')
                    b2, _, _ = _load_band(paths['b2_path'], (ref_h, ref_w))
                    band_arrays.append(b2)
                    band_names.append('B2')

                if paths['scl_path'] and os.path.exists(paths['scl_path']):
                    send_notification('S2: lecture SCL (masque nuages)…', progress=0.93, notif_id='s2_loader')
                    scl, _, _ = _load_band(paths['scl_path'], (ref_h, ref_w))
                    band_arrays.append(scl)
                    band_names.append('SCL')

                bands = np.stack(band_arrays, axis=0)

                geo = {
                    'bands':      bands,
                    'band_names': band_names,
                    'crs':        str(ref_crs) if ref_crs else None,
                    'transform':  ref_transform,
                    'nodata':     0,
                    'count':      len(band_names),
                    'width':      ref_w,
                    'height':     ref_h,
                    'dtype':      'float32',
                    'bounds':     None,
                }
                self._cache_key  = cache_key
                self._cache_data = geo
                send_notification(
                    f'S2: {len(band_names)} bandes @ {ref_w}×{ref_h} px',
                    progress=1.0, notif_id='s2_loader'
                )
            except Exception as e:
                send_notification(f'S2 Loader: {e}', level='error', notif_id='s2_loader')
                return {'geotiff': None, 'preview': None, 'meta': None}

        b     = geo['bands']
        r_vis = _stretch(b[1])
        g_vis = _stretch(b[0])
        b_vis = _stretch(b[4]) if b.shape[0] > 4 else _stretch(b[0])
        preview = cv2.merge([b_vis, g_vis, r_vis])

        h, w = preview.shape[:2]
        sc   = 120 / h
        thumb = cv2.resize(preview, (max(1, int(w * sc)), 120))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        meta = {
            'band_names':   geo['band_names'],
            'band_count':   geo['count'],
            'width':        geo['width'],
            'height':       geo['height'],
            'crs':          geo['crs'],
            'dtype':        geo['dtype'],
            'b3_path':      paths['b3_path'],
            'b4_path':      paths['b4_path'],
            'b8_path':      paths['b8_path'],
            'b11_path':     paths['b11_path'],
        }

        return {'geotiff': geo, 'preview': preview, 'meta': meta, '_thumb': thumb_b64}
