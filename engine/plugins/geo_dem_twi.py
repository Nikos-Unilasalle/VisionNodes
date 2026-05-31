"""geo_dem_twi.py — Topographic Wetness Index = ln(a / tan(β)).

a = flow accumulation × cell_area (m²)  (contributing area per unit contour width)
β = slope in radians (Horn 1981)

High TWI → humid, flat, convergent zones.
Low  TWI → dry, steep, divergent zones.
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_twi'

_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'blues':   cv2.COLORMAP_WINTER,
}

# ── Shared D8 hydrology helpers (inlined — plugins cannot cross-import) ───────

_D8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def _pix_m(transform, crs_str: str, height: int) -> tuple[float, float]:
    px, py = abs(float(transform.a)), abs(float(transform.e))
    if any(k in str(crs_str).lower() for k in ('epsg:4326', 'wgs 84', 'wgs84')):
        lat_c = float(transform.f) - py * (height / 2.0)
        return px * 111320.0 * abs(np.cos(np.radians(lat_c))), py * 111320.0
    return px, py


def _fill_pits(dem: np.ndarray, iters: int = 30) -> np.ndarray:
    filled = dem.copy()
    for _ in range(iters):
        pad   = np.pad(filled, 1, mode='edge')
        nbrs  = np.stack([pad[:-2,:-2], pad[:-2,1:-1], pad[:-2,2:],
                          pad[1:-1,:-2],               pad[1:-1,2:],
                          pad[2:,:-2],  pad[2:,1:-1],  pad[2:,2:]], axis=-1)
        min_n = nbrs.min(axis=-1)
        prev  = filled.copy()
        filled = np.where(filled < min_n, min_n + 1e-4, filled)
        if np.allclose(filled, prev, atol=1e-6):
            break
    return filled


def _d8_fdir(dem: np.ndarray, cx: float, cy: float) -> np.ndarray:
    h, w  = dem.shape
    diag  = float(np.hypot(cx, cy))
    dists = [cy, diag, cx, diag, cy, diag, cx, diag]
    pad   = np.pad(dem, 1, mode='edge')
    best  = np.zeros((h, w), dtype=np.float32)
    fdir  = np.full((h, w), -1, dtype=np.int8)
    for i, (dr, dc) in enumerate(_D8):
        nbr   = pad[1+dr:h+1+dr, 1+dc:w+1+dc]
        slope = (dem - nbr) / dists[i]
        mask  = slope > best
        best  = np.where(mask, slope, best)
        fdir  = np.where(mask, i, fdir).astype(np.int8)
    return fdir


def _flow_acc(fdir: np.ndarray, dem: np.ndarray) -> np.ndarray:
    h, w      = dem.shape
    acc       = np.ones(h * w, dtype=np.float32)
    fdir_flat = fdir.ravel()
    for idx in np.argsort(dem.ravel())[::-1]:
        d = int(fdir_flat[idx])
        if d < 0:
            continue
        r, c   = divmod(int(idx), w)
        nr, nc = r + _D8[d][0], c + _D8[d][1]
        if 0 <= nr < h and 0 <= nc < w:
            acc[nr * w + nc] += acc[idx]
    return acc.reshape(h, w)

# ── Node ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_dem_twi',
    label='DEM TWI',
    category='geography',
    icon='Waves',
    description=(
        "Topographic Wetness Index: ln(a / tan(β)). "
        "a = specific catchment area (flow acc × cell area, m²/m). "
        "β = slope in radians (Horn 1981). "
        "High TWI → flat convergent zones prone to waterlogging."
    ),
    inputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'DEM'},
        {'id': 'flow_acc', 'color': 'geotiff', 'label': 'Flow Acc (optional)'},
    ],
    outputs=[
        {'id': 'twi',      'color': 'geotiff', 'label': 'TWI'},
        {'id': 'colormap', 'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band',      'type': 'int',  'default': 1,   'min': 1, 'max': 32,
         'label': 'DEM band'},
        {'id': 'clamp_max', 'type': 'float', 'default': 20.0, 'min': 5, 'max': 40,
         'label': 'Clamp max TWI (display)'},
        {'id': 'colormap',  'type': 'enum', 'options': list(_CV2_COLORMAPS.keys()),
         'default': 0, 'label': 'Colormap'},
    ],
)
class DemTwiNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'twi': None, 'colormap': None}

        bands    = geo['bands']
        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(f'DEM TWI: band {band_idx+1} out of range',
                              level='error', notif_id=_NOTIF)
            return {'twi': None, 'colormap': None}

        dem = bands[band_idx].copy().astype(np.float64)
        nodata = geo.get('nodata')
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        mean_v = float(np.nanmean(dem)) if np.any(np.isfinite(dem)) else 0.0
        dem    = np.where(np.isfinite(dem), dem, mean_v)

        transform = geo.get('transform')
        if transform is None:
            cx, cy = 30.0, 30.0
        else:
            cx, cy = _pix_m(transform, geo.get('crs', ''), dem.shape[0])
        cell_area = cx * cy  # m²

        # ── Slope (Horn) ──────────────────────────────────────────────────────
        pad  = np.pad(dem, 1, mode='edge')
        dzdx = ((pad[:-2,2:] + 2*pad[1:-1,2:] + pad[2:,2:]) -
                (pad[:-2,:-2] + 2*pad[1:-1,:-2] + pad[2:,:-2])) / (8.0 * cx)
        dzdy = ((pad[2:,:-2] + 2*pad[2:,1:-1] + pad[2:,2:]) -
                (pad[:-2,:-2] + 2*pad[:-2,1:-1] + pad[:-2,2:])) / (8.0 * cy)
        slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))

        # ── Flow accumulation (use pre-computed if provided) ──────────────────
        acc_geo = inputs.get('flow_acc')
        if acc_geo is not None and acc_geo.get('bands') is not None:
            acc = acc_geo['bands'][0].astype(np.float64)
            if acc.shape != dem.shape:
                acc = None
            else:
                send_notification('DEM TWI: using provided flow accumulation',
                                  notif_id=_NOTIF)
        else:
            acc = None

        if acc is None:
            send_notification('DEM TWI: computing flow accumulation…',
                              progress=0.2, notif_id=_NOTIF)
            filled = _fill_pits(dem.astype(np.float32))
            fdir   = _d8_fdir(filled.astype(np.float64), cx, cy)
            acc    = _flow_acc(fdir, filled).astype(np.float64)

        # ── TWI = ln(a / tan(β)) ──────────────────────────────────────────────
        # a = specific catchment area = (acc * cell_area) / contour_length
        # Simplified: a = acc * cell_area  (Beven & Kirkby 1979 approx)
        a       = acc * cell_area
        tan_b   = np.tan(slope_rad)
        tan_b   = np.maximum(tan_b, np.tan(np.radians(0.001)))  # avoid div/0 on flat areas

        twi = np.log(a / tan_b).astype(np.float32)

        twi_geo = {**geo, 'bands': twi[np.newaxis], 'count': 1,
                   'band_names': ['twi'], '_source': 'dem_twi', '_bands': ['twi']}

        clamp = float(params.get('clamp_max', 20.0))
        twi_min = float(twi.min())
        span    = max(clamp - twi_min, 1.0)
        norm    = np.clip((twi - twi_min) / span, 0.0, 1.0)
        img8    = (norm * 255).astype(np.uint8)

        cmap_val  = params.get('colormap', 0)
        cmap_keys = list(_CV2_COLORMAPS.keys())
        cmap_name = cmap_keys[cmap_val] if isinstance(cmap_val, int) and cmap_val < len(cmap_keys) else 'viridis'
        colored = cv2.applyColorMap(img8, _CV2_COLORMAPS.get(cmap_name, cv2.COLORMAP_VIRIDIS))

        h, w   = colored.shape[:2]
        sc     = min(1.0, 120 / h)
        thumb  = cv2.resize(colored, (max(1, int(w*sc)), max(1, int(h*sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        tb64   = base64.b64encode(buf).decode()

        send_notification(
            f'DEM TWI: done — range [{twi_min:.1f}, {float(twi.max()):.1f}]',
            progress=1.0, notif_id=_NOTIF)

        return {'twi': twi_geo, 'colormap': colored, '_thumb': tb64}
