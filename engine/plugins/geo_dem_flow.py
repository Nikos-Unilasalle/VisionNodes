"""geo_dem_flow.py — D8 flow direction + flow accumulation from a DEM.

Algorithm: Priority-Flood + ε depression filling (Barnes et al. 2014) → steepest
descent D8 → flow accumulation in cells (high→low topological order).

The ε-gradient fill guarantees every cell has a strictly descending path to the
DEM border, so no flat/sink cells stall the flow network — essential on
low-relief DEMs (e.g. coastal plains) where naive pit filling leaves plateaus
that fragment the drainage and cap accumulation far below true values.
"""
import heapq

import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'dem_flow'

# ── Shared D8 hydrology helpers ───────────────────────────────────────────────

# Direction encoding: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
_D8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def _pix_m(transform, crs_str: str, height: int) -> tuple[float, float]:
    px, py = abs(float(transform.a)), abs(float(transform.e))
    if any(k in str(crs_str).lower() for k in ('epsg:4326', 'wgs 84', 'wgs84')):
        lat_c = float(transform.f) - py * (height / 2.0)
        return px * 111320.0 * abs(np.cos(np.radians(lat_c))), py * 111320.0
    return px, py


def _priority_flood_eps(dem: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """Priority-Flood + ε depression filling (Barnes, Lehman & Mulla 2014).

    Floods the DEM inward from its border using a min-priority queue. Each cell
    is raised to at least its lowest already-processed neighbour plus ``eps``,
    yielding a hydrologically-conditioned surface with a strictly descending path
    from every cell to the border — no flats, no internal sinks. ``eps`` is kept
    tiny (1e-4 m) so cumulative rise across long flats stays negligible relative
    to real relief.
    """
    h, w   = dem.shape
    out    = dem.astype(np.float64).copy()
    closed = np.zeros((h, w), dtype=bool)
    heap: list[tuple[float, int, int]] = []

    # Seed the queue with all border cells (the natural outlets).
    for r in range(h):
        for c in (0, w - 1):
            if not closed[r, c]:
                closed[r, c] = True
                heapq.heappush(heap, (out[r, c], r, c))
    for c in range(w):
        for r in (0, h - 1):
            if not closed[r, c]:
                closed[r, c] = True
                heapq.heappush(heap, (out[r, c], r, c))

    while heap:
        e, r, c = heapq.heappop(heap)
        for dr, dc in _D8:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not closed[nr, nc]:
                closed[nr, nc] = True
                ne = out[nr, nc]
                if ne <= e:
                    ne = e + eps          # impose strictly increasing inward gradient
                out[nr, nc] = ne
                heapq.heappush(heap, (ne, nr, nc))
    return out


def _d8_fdir(dem: np.ndarray, cx: float, cy: float) -> np.ndarray:
    """D8 flow direction (0–7 = N,NE,E,SE,S,SW,W,NW). -1 = flat/sink."""
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
    """D8 flow accumulation (in cells). Processes cells high→low."""
    h, w      = dem.shape
    acc       = np.ones(h * w, dtype=np.float32)
    fdir_flat = fdir.ravel()
    for idx in np.argsort(dem.ravel())[::-1]:   # high → low
        d = int(fdir_flat[idx])
        if d < 0:
            continue
        r, c   = divmod(int(idx), w)
        nr, nc = r + _D8[d][0], c + _D8[d][1]
        if 0 <= nr < h and 0 <= nc < w:
            acc[nr * w + nc] += acc[idx]
    return acc.reshape(h, w)

# ── Flow accumulation colormap (log scale, blue=high) ─────────────────────────

def _acc_preview(acc: np.ndarray) -> np.ndarray:
    log_acc = np.log1p(acc)
    span    = log_acc.max() - log_acc.min()
    if span < 1e-6:
        return np.zeros((*acc.shape, 3), dtype=np.uint8)
    norm = ((log_acc - log_acc.min()) / span * 255).astype(np.uint8)
    return cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)

# ── Node ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_dem_flow',
    label='DEM Flow',
    category='geography',
    icon='Droplets',
    description=(
        "D8 flow direction and flow accumulation from a DEM. "
        "Pit-filling pre-processing ensures continuous drainage network. "
        "Flow accumulation = number of upstream cells draining into each cell."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'DEM'}],
    outputs=[
        {'id': 'flow_acc',  'color': 'geotiff', 'label': 'Flow Acc'},
        {'id': 'flow_dir',  'color': 'geotiff', 'label': 'Flow Dir'},
        {'id': 'preview',   'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'band', 'type': 'int', 'default': 1, 'min': 1, 'max': 32, 'label': 'DEM band'},
    ],
)
class DemFlowNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if geo is None:
            return {'flow_acc': None, 'flow_dir': None, 'preview': None}

        bands    = geo['bands']
        band_idx = max(0, int(params.get('band', 1)) - 1)
        if band_idx >= bands.shape[0]:
            send_notification(f'DEM Flow: band {band_idx+1} out of range',
                              level='error', notif_id=_NOTIF)
            return {'flow_acc': None, 'flow_dir': None, 'preview': None}

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

        send_notification('DEM Flow: filling depressions (priority-flood)…',
                          progress=0.1, notif_id=_NOTIF)
        filled = _priority_flood_eps(dem)

        send_notification('DEM Flow: computing flow direction…', progress=0.4, notif_id=_NOTIF)
        fdir = _d8_fdir(filled.astype(np.float64), cx, cy)

        send_notification('DEM Flow: computing flow accumulation…', progress=0.6, notif_id=_NOTIF)
        acc = _flow_acc(fdir, filled)

        acc_geo  = {**geo, 'bands': acc[np.newaxis], 'count': 1,
                    'band_names': ['flow_acc'], '_source': 'dem_flow', '_bands': ['flow_acc']}
        fdir_geo = {**geo, 'bands': fdir[np.newaxis].astype(np.float32), 'count': 1,
                    'band_names': ['flow_dir'], '_source': 'dem_flow', '_bands': ['flow_dir']}

        colored = _acc_preview(acc)
        h, w    = colored.shape[:2]
        sc      = min(1.0, 120 / h)
        thumb   = cv2.resize(colored, (max(1, int(w*sc)), max(1, int(h*sc))))
        _, buf  = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        tb64    = base64.b64encode(buf).decode()

        send_notification(
            f'DEM Flow: done — max acc {int(acc.max())} cells', progress=1.0, notif_id=_NOTIF)

        return {'flow_acc': acc_geo, 'flow_dir': fdir_geo, 'preview': colored, '_thumb': tb64}
