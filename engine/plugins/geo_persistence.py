"""geo_persistence.py — Topological persistence of a scalar raster (threshold-free).

Computes the 0-dimensional persistent homology of the super-level set filtration of
a probability / index raster (e.g. a P(water) map) by a single-pass union-find sweep.

Each local extremum (a candidate water body) is born at its peak value and dies when
it merges into a more persistent neighbour at a saddle. Its *persistence* (a.k.a.
dynamics / extinction value) = peak - saddle measures how robustly it survives across
ALL thresholds — so a real lake (high persistence) separates from noise speckle (low
persistence, near the diagram diagonal) WITHOUT choosing a single threshold. The
significance cut is auto-detected as the largest gap in the sorted persistence
spectrum.

The water mask is then the union of the robust **h-domes** of height = cut: the
compact region around each peak of dynamic >= cut, reached without descending more
than `cut`. Every water body is effectively thresholded at its own topological level
(peak - cut), all derived from the one auto cut — never a hand-picked value.

Outputs:
  - persistence_map : compact saliency raster (dome height of the robust water bodies)
  - colormap        : colorized preview of the saliency map
  - mask            : threshold-free binary water mask (robust h-domes, 0/255)
  - diagram         : DataFrame of features [peak, saddle, persistence, y, x, significant]
  - stats           : summary dict (counts, auto cut, max persistence)
  - n_significant   : number of distinct water bodies extracted
"""
from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import base64

from scipy import ndimage
from skimage.morphology import reconstruction

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas always present in engine env
    pd = None


_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'jet':     cv2.COLORMAP_JET,
    'hot':     cv2.COLORMAP_HOT,
    'magma':   cv2.COLORMAP_MAGMA,
}

# Connectivity offsets for the union-find neighbour scan.
_NB4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_NB8 = _NB4 + ((-1, -1), (-1, 1), (1, -1), (1, 1))

_EPS = 1e-9


def _auto_gap_cut(persistences: np.ndarray) -> float:
    """Noise-floor exit: first significant jump in the ascending persistence spectrum.

    Scans low→high and returns the midpoint of the first gap that exceeds
    mean + 2σ of all gaps. This finds where the dense noise cluster ends and
    the first real signal begins, regardless of how many dominant features pile
    up at the top (which would fool a largest-gap-descending approach).

    Falls back to the midpoint of the largest gap when no jump qualifies.
    """
    if persistences.size == 0:
        return 0.0
    ps = np.sort(persistences)          # ascending: noise → signal
    if ps.size == 1:
        return float(ps[0]) * 0.5
    gaps = ps[1:] - ps[:-1]
    if ps.size == 2:
        return float((ps[0] + ps[1]) * 0.5)

    mean_g = float(gaps.mean())
    std_g = float(gaps.std())
    threshold = mean_g + 2.0 * std_g

    sig = np.nonzero(gaps > threshold)[0]
    if sig.size > 0:
        k = int(sig[0])                 # first (lowest) significant gap = noise floor exit
        return float((ps[k] + ps[k + 1]) * 0.5)

    k = int(np.argmax(gaps))            # fallback: largest gap midpoint
    return float((ps[k] + ps[k + 1]) * 0.5)


def _persistence_sweep(field: np.ndarray, gmin: float, nb):
    """Single-pass union-find over the super-level set filtration of `field`.

    Returns a list of features (peak, saddle, persistence, peak_flat_idx). Components
    that never die persist down to the global minimum `gmin`.
    """
    h, w = field.shape
    n = h * w
    flat = field.ravel()
    order = np.argsort(-flat, kind='stable')    # high value first

    parent = np.empty(n, np.int64)
    peak_val = np.empty(n, np.float64)
    peak_idx = np.empty(n, np.int64)
    activated = np.zeros(n, np.bool_)

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:                # path compression
            parent[x], x = root, parent[x]
        return root

    feats = []
    for idx in order:
        idx = int(idx)
        y, x = divmod(idx, w)
        v = flat[idx]

        roots = []
        for dy, dx in nb:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                j = ny * w + nx
                if activated[j]:
                    r = find(j)
                    if r not in roots:
                        roots.append(r)
        activated[idx] = True

        if not roots:
            parent[idx] = idx
            peak_val[idx] = v
            peak_idx[idx] = idx
            continue

        survivor = max(roots, key=lambda r: peak_val[r])
        parent[idx] = survivor
        for r in roots:
            if r == survivor:
                continue
            feats.append((float(peak_val[r]), float(v),
                          float(peak_val[r] - v), int(peak_idx[r])))
            parent[r] = survivor

    for r in {find(i) for i in range(n)}:
        feats.append((float(peak_val[r]), float(gmin),
                      float(peak_val[r] - gmin), int(peak_idx[r])))
    return feats


def _robust_domes(field: np.ndarray, cut: float, structure):
    """Union of h-domes of height `cut`: compact support of every peak whose dynamic
    reaches `cut`. Returns (saliency, mask_bool, n_components).

    saliency = dome height inside the robust domes (0 elsewhere).
    Used for the persistence saliency visualisation only — not the binary mask.
    """
    if cut <= _EPS:
        return np.zeros_like(field, np.float32), np.zeros(field.shape, bool), 0

    shifted = field - float(field.min())        # make non-negative for reconstruction
    seed = shifted - cut
    rec = reconstruction(seed, shifted, method='dilation')
    hdome = shifted - rec                        # >0 on every dome, capped at `cut`

    pos = hdome > _EPS
    lab, n = ndimage.label(pos, structure=structure)
    if n == 0:
        return np.zeros_like(field, np.float32), pos, 0

    comp_max = ndimage.maximum(hdome, lab, np.arange(1, n + 1))
    keep_ids = np.nonzero(comp_max >= cut * (1.0 - 1e-3))[0] + 1   # full-height domes only
    mask = np.isin(lab, keep_ids)
    n_bodies = int(keep_ids.size)
    saliency = np.where(mask, hdome, 0.0).astype(np.float32)
    return saliency, mask, n_bodies


def _topo_flood_fill(field: np.ndarray, feats: list, cut: float, structure) -> np.ndarray:
    """Per-body topological flood fill — the true threshold-free mask.

    For each significant basin (persistence >= cut), flood-fill the field from
    its peak down to its own saddle level.  Every body gets its OWN fill level:

        fill_level = max(saddle + EPS, cut)

    The `max(..., cut)` guard prevents the global feature (whose saddle equals
    the field minimum) from flooding the entire domain.

    Returns boolean mask = union of all per-body filled regions.
    This correctly captures elongated features (rivers, channels) where the
    h-dome approach only marks isolated peak spots.
    """
    h, w = field.shape
    combined = np.zeros((h, w), bool)
    for peak_v, saddle_v, pers, peak_flat in feats:
        if pers < cut - _EPS:
            continue
        py, px = divmod(int(peak_flat), w)
        # Per-body fill threshold: body's own saddle, but never below the cut.
        fill_level = max(float(saddle_v) + _EPS, float(cut))
        binary = field >= fill_level
        lab, _ = ndimage.label(binary, structure=structure)
        body_label = int(lab[py, px])
        if body_label > 0:
            combined |= (lab == body_label)
    return combined


@vision_node(
    type_id='geo_persistence',
    label='Topological Persistence',
    category='geography',
    icon='Mountain',
    description=(
        'Threshold-free feature extraction by 0-D persistent homology of a scalar '
        'raster (e.g. a P(water) map). Each blob is scored by its topological '
        'persistence (peak - merge saddle); the significance cut is auto-detected '
        'from the largest gap in the persistence spectrum. Accepts a GeoTIFF or a '
        'plain image (e.g. the MC probability map straight from the Frame '
        'Accumulator). Outputs a persistence saliency map, a threshold-free mask '
        '(robust h-domes), and the diagram.'
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Scalar raster'},
        {'id': 'image',   'color': 'image',   'label': 'Image (e.g. MC probability)'},
    ],
    outputs=[
        {'id': 'persistence_map', 'color': 'geotiff', 'label': 'Persistence map'},
        {'id': 'colormap',        'color': 'image',   'label': 'Colormap'},
        {'id': 'mask',            'color': 'mask',    'label': 'Mask (threshold-free)'},
        {'id': 'diagram',         'color': 'data',    'label': 'Persistence diagram'},
        {'id': 'stats',           'color': 'dict',    'label': 'Stats'},
        {'id': 'n_significant',   'color': 'scalar',  'label': 'N water bodies'},
    ],
    params=[
        {'id': 'band', 'type': 'int', 'default': 1, 'min': 1, 'max': 20, 'label': 'Band'},
        {'id': 'feature', 'type': 'enum', 'options': ['maxima (bright)', 'minima (dark)'],
         'default': 'maxima (bright)', 'label': 'Feature'},
        {'id': 'connectivity', 'type': 'enum', 'options': ['8', '4'],
         'default': '8', 'label': 'Connectivity'},
        {'id': 'min_persistence', 'type': 'float', 'default': 0.0, 'min': 0.0, 'max': 1e9,
         'label': 'Min persistence (0 = auto gap)'},
        {'id': 'max_pixels', 'type': 'int', 'default': 500000, 'min': 10000, 'max': 20000000,
         'label': 'Max pixels (downsample guard)'},
        {'id': 'closing_iterations', 'type': 'int', 'default': 3, 'min': 0, 'max': 20,
         'label': 'Closing iterations (0 = off)'},
        {'id': 'colormap', 'type': 'enum', 'options': list(_CV2_COLORMAPS.keys()),
         'default': 'magma', 'label': 'Colormap'},
    ],
)
class TopologicalPersistenceNode(NodeProcessor):
    def process(self, inputs: dict, params: dict) -> dict:
        empty = {'persistence_map': None, 'colormap': None, 'mask': None,
                 'diagram': None, 'stats': None, 'n_significant': None}

        # Accept a GeoTIFF (preferred, keeps georeferencing) OR a plain image — the MC
        # probability map leaves the Frame Accumulator as a uint8 image, not a geotiff.
        geo = inputs.get('geotiff')
        nodata = None
        if isinstance(geo, dict) and 'bands' in geo:
            bands = geo['bands']
            count = int(geo.get('count', len(bands)))
            sel = min(max(int(params.get('band', 1)), 1), count) - 1
            field0 = np.asarray(bands[sel], dtype=np.float64)
            nodata = geo.get('nodata')
        else:
            img = inputs.get('image')
            if img is None:
                return empty
            arr = np.asarray(img)
            if arr.ndim == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.shape[2] == 3 else arr[..., 0]
            field0 = arr.astype(np.float64)
            if field0.max() > 1.1:            # uint8 0-255 probability -> [0,1]
                field0 = field0 / 255.0
            geo = {'crs': None, 'transform': None, 'nodata': None}

        full_h, full_w = field0.shape

        # Clean non-finite / nodata to the field minimum so they spawn no feature.
        finite = np.isfinite(field0)
        if not finite.any():
            send_notification('Topological Persistence: input has no finite values',
                              level='error', notif_id='geo_persistence')
            return empty
        valid = finite.copy()
        if nodata is not None:
            valid &= (field0 != nodata)
        if not valid.any():
            valid = finite
        fmin_valid = float(field0[valid].min())
        field0 = np.where(valid, field0, fmin_valid)

        minima = str(params.get('feature', 'maxima (bright)')).startswith('minima')
        if minima:
            field0 = -field0                     # super-level sets of -P = sub-level of P

        # Downsample guard — basin persistence is scale-tolerant.
        max_px = int(params.get('max_pixels', 500000))
        field = field0
        scale = 1.0
        if full_h * full_w > max_px:
            scale = float(np.sqrt(max_px / (full_h * full_w)))
            new_w = max(2, int(round(full_w * scale)))
            new_h = max(2, int(round(full_h * scale)))
            field = cv2.resize(field0.astype(np.float32), (new_w, new_h),
                               interpolation=cv2.INTER_AREA).astype(np.float64)
            send_notification(
                f'Topological Persistence: downsampled {full_w}x{full_h} -> {new_w}x{new_h} '
                f'(max_pixels={max_px})', level='info', notif_id='geo_persistence')

        h, w = field.shape
        gmin = float(field.min())
        conn8 = str(params.get('connectivity', '8')) == '8'
        nb = _NB8 if conn8 else _NB4
        structure = np.ones((3, 3), bool) if conn8 else None  # None => 4-conn in ndimage

        # --- persistence diagram (union-find) ---
        feats = _persistence_sweep(field, gmin, nb)
        all_pers = np.array([f[2] for f in feats], dtype=np.float64)
        all_pers = all_pers[all_pers > _EPS]

        manual = float(params.get('min_persistence', 0.0))
        cut = manual if manual > 0.0 else _auto_gap_cut(all_pers)

        # --- saliency (h-domes) — compact visualisation of peak dynamics ---
        saliency, _, _ = _robust_domes(field, cut, structure)

        # --- binary mask: per-body topological flood fill ---
        # Each significant body is filled down to its own saddle (no global threshold).
        flood_bool = _topo_flood_fill(field, feats, cut, structure)
        # Fill enclosed holes (e.g. small oxbow lakes whose ring is fully closed).
        # Uses 4-conn background (scipy default) — more aggressive than 8-conn.
        # Does NOT help for open C/U-shaped meanders; those require a correct
        # probability field (turbid water NIR gate not too strict).
        flood_bool = ndimage.binary_fill_holes(flood_bool)
        closing_iter = int(params.get('closing_iterations', 3))
        if closing_iter > 0:
            flood_bool = ndimage.binary_closing(flood_bool, structure=structure,
                                                iterations=closing_iter)
        mask = flood_bool.astype(np.uint8) * 255
        n_bodies = int(np.count_nonzero(np.array([f[2] for f in feats]) >= cut - _EPS))

        if scale != 1.0:
            saliency = cv2.resize(saliency, (full_w, full_h), interpolation=cv2.INTER_NEAREST)
            mask = cv2.resize(mask, (full_w, full_h), interpolation=cv2.INTER_NEAREST)

        # Persistence-saliency geotiff (preserve georeferencing).
        pmap_geo = {**geo, 'bands': saliency[np.newaxis].astype(np.float32),
                    'count': 1, 'band_names': ['persistence'], 'dtype': 'float32'}

        # Colormap preview — saliency tinted, flood-fill mask applied as alpha.
        smax = float(saliency.max()) if saliency.size else 0.0
        norm = (saliency / smax * 255.0).astype(np.uint8) if smax > 0 else np.zeros_like(saliency, np.uint8)
        cmap = _CV2_COLORMAPS.get(params.get('colormap', 'magma'), cv2.COLORMAP_MAGMA)
        colored = cv2.applyColorMap(norm, cmap)
        colored[mask == 0] = (0, 0, 0)           # black outside water bodies

        # Persistence diagram DataFrame (in the raster's own units).
        diagram = None
        n_sig_feats = int(np.count_nonzero(all_pers >= cut)) if all_pers.size else 0
        if pd is not None and feats:
            inv = (1.0 / scale) if scale != 1.0 else 1.0
            rows = []
            for peak_v, saddle_v, pers, pk in feats:
                py, px = divmod(int(pk), w)
                bp = -peak_v if minima else peak_v
                bs = -saddle_v if minima else saddle_v
                rows.append({
                    'peak': round(bp, 6), 'saddle': round(bs, 6),
                    'persistence': round(pers, 6),
                    'y': int(py * inv), 'x': int(px * inv),
                    'significant': bool(pers >= cut),
                })
            rows.sort(key=lambda r: -r['persistence'])
            diagram = pd.DataFrame(rows)

        stats = {
            'n_water_bodies': int(n_bodies),
            'n_significant_features': n_sig_feats,
            'n_features_total': int(all_pers.size),
            'persistence_cut': round(float(cut), 6),
            'cut_mode': 'manual' if manual > 0.0 else 'auto-gap',
            'max_persistence': round(float(all_pers.max()), 6) if all_pers.size else 0.0,
            'water_pixels': int(np.count_nonzero(mask)),
            'water_pct': round(float(np.count_nonzero(mask)) / mask.size * 100.0, 4),
            'working_resolution': [int(h), int(w)],
        }

        sc = 120.0 / colored.shape[0]
        thumb_img = cv2.resize(colored, (max(1, int(colored.shape[1] * sc)), 120))
        ok, buf = cv2.imencode('.jpg', thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb = base64.b64encode(buf).decode('utf-8') if ok else None

        return {
            'persistence_map': pmap_geo,
            'colormap': colored,
            'mask': mask,
            'diagram': diagram,
            'stats': stats,
            'n_significant': int(n_bodies),
            '_thumb': thumb,
        }
