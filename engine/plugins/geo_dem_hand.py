"""geo_dem_hand.py — Height Above Nearest Drainage (HAND).

For each cell: HAND = elevation − elevation of the nearest drainage cell
reachable by following the D8 flow path downstream.

Drainage network = cells where flow_acc ≥ drainage_threshold.
High HAND → far above drainage → low flood risk.
Low HAND  → close to drainage → high flood/mining risk.
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_hand'

_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'turbo':   cv2.COLORMAP_TURBO,
    'plasma':  cv2.COLORMAP_PLASMA,
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


def _hand(dem: np.ndarray, fdir: np.ndarray, acc: np.ndarray,
          threshold: float) -> np.ndarray:
    """HAND via D8 flow-path tracing (low→high propagation)."""
    h, w = dem.shape
    drainage = acc >= threshold

    dem_flat  = dem.ravel().astype(np.float64)
    fdir_flat = fdir.ravel()
    ref_flat  = np.full(h * w, np.nan, dtype=np.float64)

    # Seed drainage cells
    drain_idx          = np.where(drainage.ravel())[0]
    ref_flat[drain_idx] = dem_flat[drain_idx]

    # Process low → high: each cell inherits ref_elev from its (already-processed) downstream cell
    for idx in np.argsort(dem_flat):
        if not np.isnan(ref_flat[idx]):
            continue  # already seeded or assigned
        d = int(fdir_flat[idx])
        if d < 0:
            continue
        r, c   = divmod(int(idx), w)
        nr, nc = r + _D8[d][0], c + _D8[d][1]
        if 0 <= nr < h and 0 <= nc < w:
            down_i = nr * w + nc
            if not np.isnan(ref_flat[down_i]):
                ref_flat[idx] = ref_flat[down_i]

    ref_flat = np.where(np.isnan(ref_flat), dem_flat, ref_flat)
    hand = np.maximum(0.0, dem_flat - ref_flat).reshape(h, w).astype(np.float32)
    return hand

# ── Node ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_dem_hand',
    label='DEM HAND',
    category='geography',
    icon='ArrowDownToLine',
    description=(
        "Height Above Nearest Drainage: vertical distance from each cell to the nearest "
        "drainage cell reachable via D8 flow paths. "
        "Low HAND = close to drainage = flood-prone / likely gold-mining site. "
        "Optionally accepts pre-computed flow accumulation to skip re-computation."
    ),
    inputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'DEM'},
        {'id': 'flow_acc', 'color': 'geotiff', 'label': 'Flow Acc (optional)'},
    ],
    outputs=[
        {'id': 'hand',     'color': 'geotiff', 'label': 'HAND'},
        {'id': 'drainage', 'color': 'geotiff', 'label': 'Drainage mask'},
        {'id': 'colormap', 'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band',      'type': 'int',   'default': 1,    'min': 1,   'max': 32,
         'label': 'DEM band'},
        {'id': 'threshold', 'type': 'int',   'default': 1000, 'min': 10,  'max': 100000,
         'label': 'Drainage threshold (cells)'},
        {'id': 'clamp_max', 'type': 'float', 'default': 30.0, 'min': 1.0, 'max': 1000.0,
         'label': 'Clamp max HAND (m, display)'},
        {'id': 'colormap',  'type': 'enum',  'options': list(_CV2_COLORMAPS.keys()),
         'default': 0, 'label': 'Colormap'},
    ],
)
class DemHandNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'hand': None, 'drainage': None, 'colormap': None}

        bands    = geo['bands']
        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(f'DEM HAND: band {band_idx+1} out of range',
                              level='error', notif_id=_NOTIF)
            return {'hand': None, 'drainage': None, 'colormap': None}

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

        threshold = float(params.get('threshold', 1000))

        # ── Flow accumulation (use pre-computed if provided) ──────────────────
        acc_geo = inputs.get('flow_acc')
        if acc_geo is not None and acc_geo.get('bands') is not None:
            acc = acc_geo['bands'][0].astype(np.float64)
            if acc.shape == dem.shape:
                send_notification('DEM HAND: using provided flow accumulation',
                                  notif_id=_NOTIF)
                filled = _fill_pits(dem.astype(np.float32))
                fdir   = _d8_fdir(filled.astype(np.float64), cx, cy)
            else:
                acc = None
        else:
            acc = None

        if acc is None:
            send_notification('DEM HAND: computing flow accumulation…',
                              progress=0.2, notif_id=_NOTIF)
            filled = _fill_pits(dem.astype(np.float32))
            fdir   = _d8_fdir(filled.astype(np.float64), cx, cy)
            acc    = _flow_acc(fdir, filled).astype(np.float64)

        send_notification('DEM HAND: tracing flow paths…', progress=0.6, notif_id=_NOTIF)
        hand     = _hand(dem.astype(np.float32), fdir, acc.astype(np.float32), threshold)
        drainage = (acc >= threshold).astype(np.float32)

        hand_geo = {**geo, 'bands': hand[np.newaxis], 'count': 1,
                    'band_names': ['hand_m'], '_source': 'dem_hand', '_bands': ['hand_m']}
        drain_geo = {**geo, 'bands': drainage[np.newaxis], 'count': 1,
                     'band_names': ['drainage'], '_source': 'dem_hand', '_bands': ['drainage']}

        clamp    = float(params.get('clamp_max', 30.0))
        norm     = np.clip(hand / clamp, 0.0, 1.0)
        img8     = (norm * 255).astype(np.uint8)

        cmap_val  = params.get('colormap', 0)
        cmap_keys = list(_CV2_COLORMAPS.keys())
        cmap_name = cmap_keys[cmap_val] if isinstance(cmap_val, int) and cmap_val < len(cmap_keys) else 'viridis'
        colored = cv2.applyColorMap(img8, _CV2_COLORMAPS.get(cmap_name, cv2.COLORMAP_VIRIDIS))

        # Overlay drainage network in blue
        drain_overlay = (drainage > 0)
        colored[drain_overlay] = [200, 50, 0]  # BGR blue

        h, w   = colored.shape[:2]
        sc     = min(1.0, 120 / h)
        thumb  = cv2.resize(colored, (max(1, int(w*sc)), max(1, int(h*sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        tb64   = base64.b64encode(buf).decode()

        send_notification(
            f'DEM HAND: done — max {float(hand.max()):.1f}m, '
            f'drainage cells: {int(drainage.sum())}',
            progress=1.0, notif_id=_NOTIF)

        return {'hand': hand_geo, 'drainage': drain_geo, 'colormap': colored, '_thumb': tb64}
