"""
geo_glcm_features.py — GLCM texture feature maps for SAR/optical bands

Computes Gray-Level Co-occurrence Matrix (GLCM) texture features on a single
input band using a sliding window approach.  Outputs a multi-band geo dict
compatible with geo_band_stack.

Typical use (Sinnamary):
  VH channel from S1 → geo_glcm_features → stack with S1+S2 features →
  RF classifier benefits from: mangrove roughness ≠ equatorial forest texture.

GLCM properties available:
  contrast      — local intensity variation (high in mangrove canopy)
  dissimilarity — like contrast but linear distance weight
  homogeneity   — inverse of contrast (high in water / smooth surfaces)
  energy        — angular second moment (uniformity)
  correlation   — linear dependency (directional structure)

All four main angles (0°, 45°, 90°, 135°) are averaged to make features
rotation-invariant (important for satellite imagery).

Performance note: sliding-window GLCM is O(H×W×win²).  Use stride ≥ 2
for large images (>1500px) to keep processing time under ~30s.
"""
from __future__ import annotations
import sys
import time

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_glcm'

_ANGLES = [0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]


def _log(msg: str) -> None:
    print(f'[geo_glcm] {msg}', file=sys.stderr, flush=True)


def _quantize(band: np.ndarray, levels: int) -> np.ndarray:
    """Rescale float band to [0, levels-1] uint8/uint16."""
    b = band.astype(np.float32)
    lo, hi = np.nanpercentile(b, 2), np.nanpercentile(b, 98)
    if hi <= lo:
        return np.zeros_like(b, dtype=np.uint8)
    b = np.clip((b - lo) / (hi - lo), 0, 1)
    return (b * (levels - 1)).astype(np.uint8 if levels <= 256 else np.uint16)


def _glcm_map(
    img_q:      np.ndarray,
    win:        int,
    distances:  list[int],
    angles:     list[float],
    properties: list[str],
    levels:     int,
    stride:     int,
) -> np.ndarray:
    """Return (n_props, H, W) float32 texture map using sliding-window GLCM."""
    from skimage.feature import graycomatrix, graycoprops

    H, W  = img_q.shape
    pad   = win // 2
    img_p = np.pad(img_q, pad, mode='reflect')
    n_p   = len(properties)

    # Output: computed at stride positions, then resized to full resolution
    out_h = (H + stride - 1) // stride
    out_w = (W + stride - 1) // stride
    raw   = np.zeros((n_p, out_h, out_w), dtype=np.float32)

    t0 = time.time()
    total = out_h * out_w
    done  = 0

    for ri in range(out_h):
        r = ri * stride
        for ci in range(out_w):
            c = ci * stride
            patch = img_p[r: r + win, c: c + win]
            glcm  = graycomatrix(
                patch,
                distances=distances,
                angles=angles,
                levels=levels,
                symmetric=True,
                normed=True,
            )
            for pi, prop in enumerate(properties):
                raw[pi, ri, ci] = float(graycoprops(glcm, prop).mean())
            done += 1

        # progress every row
        elapsed = time.time() - t0
        pct = done / total
        eta = elapsed / pct * (1 - pct) if pct > 0 else 0
        send_notification(
            f'GLCM: {pct:.0%}  elapsed={elapsed:.0f}s  ETA={eta:.0f}s',
            progress=0.1 + pct * 0.85,
            notif_id=_NOTIF,
        )

    # Resize back to original resolution if stride > 1
    if stride > 1:
        result = np.zeros((n_p, H, W), dtype=np.float32)
        for pi in range(n_p):
            result[pi] = cv2.resize(raw[pi], (W, H), interpolation=cv2.INTER_LINEAR)
    else:
        result = raw

    elapsed = time.time() - t0
    _log(f'GLCM done in {elapsed:.1f}s  shape={result.shape}')
    return result


def _preview_band(arr: np.ndarray) -> np.ndarray:
    """Single band → normalized uint8 BGR for display."""
    lo, hi = arr.min(), arr.max()
    if hi <= lo:
        return np.zeros((*arr.shape, 3), dtype=np.uint8)
    norm = ((arr - lo) / (hi - lo) * 255).astype(np.uint8)
    return cv2.applyColorMap(norm, cv2.COLORMAP_VIRIDIS)


@vision_node(
    type_id='geo_glcm_features',
    label='GLCM Texture',
    category='remote sensing',
    icon='Grid3x3',
    description=(
        'Computes GLCM texture features (contrast, homogeneity, energy, correlation, '
        'dissimilarity) on a single input band using a sliding window. '
        'Outputs a multi-band geo dict for stacking with geo_band_stack. '
        'Designed for VH SAR band to distinguish mangrove canopy roughness from '
        'equatorial forest. Angles 0/45/90/135° averaged → rotation-invariant. '
        'Use stride ≥ 2 for large images to reduce computation time.'
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Input geo dict (uses band_index)'},
    ],
    outputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'Texture bands geo dict'},
        {'id': 'preview',  'color': 'image',   'label': 'Preview (first texture band)'},
    ],
    params=[
        {
            'id': 'band_index', 'type': 'int',
            'default': 0, 'min': 0, 'max': 31,
            'label': 'Band index to process (0 = first band)',
        },
        {
            'id': 'window_size', 'type': 'int',
            'default': 9, 'min': 3, 'max': 31,
            'label': 'Window size (pixels, odd number)',
        },
        {
            'id': 'stride', 'type': 'int',
            'default': 2, 'min': 1, 'max': 8,
            'label': 'Stride (1=full res, 2=2× faster, 4=4× faster)',
        },
        {
            'id': 'levels', 'type': 'int',
            'default': 64, 'min': 8, 'max': 256,
            'label': 'Quantization levels (fewer = faster)',
        },
        {
            'id': 'distances', 'type': 'string',
            'default': '1,2',
            'label': 'GLCM distances (comma-sep ints)',
        },
        {
            'id': 'contrast',      'type': 'bool', 'default': True,  'label': 'Contrast' },
        {
            'id': 'homogeneity',   'type': 'bool', 'default': True,  'label': 'Homogeneity' },
        {
            'id': 'energy',        'type': 'bool', 'default': True,  'label': 'Energy' },
        {
            'id': 'correlation',   'type': 'bool', 'default': True,  'label': 'Correlation' },
        {
            'id': 'dissimilarity', 'type': 'bool', 'default': False, 'label': 'Dissimilarity' },
        {
            'id': 'band_suffix',   'type': 'string', 'default': 'VH',
            'label': 'Band name suffix (e.g. VH → contrast_VH, …)' },
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GeoGLCMFeaturesNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        if not self.ensure_packages(
            ['skimage'], pip_names=['scikit-image'], notif_id=_NOTIF,
        ):
            return {}

        from rasterio.transform import from_bounds

        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or geo.get('bands') is None:
            send_notification('GLCM: connect a geo dict input', notif_id=_NOTIF)
            return {}

        # ── Parse params ─────────────────────────────────────────────────────
        band_idx   = int(params.get('band_index', 0))
        win        = int(params.get('window_size', 9))
        win        = win if win % 2 == 1 else win + 1   # ensure odd
        stride     = max(1, int(params.get('stride', 2)))
        levels     = max(8, min(256, int(params.get('levels', 64))))
        dist_str   = str(params.get('distances', '1,2')).strip()
        suffix     = str(params.get('band_suffix', 'VH')).strip()

        properties: list[str] = []
        prop_map = {
            'contrast':      params.get('contrast',      True),
            'homogeneity':   params.get('homogeneity',   True),
            'energy':        params.get('energy',        True),
            'correlation':   params.get('correlation',   True),
            'dissimilarity': params.get('dissimilarity', False),
        }
        for name, enabled in prop_map.items():
            if enabled:
                properties.append(name)

        if not properties:
            send_notification('GLCM: enable at least one property', notif_id=_NOTIF)
            return {}

        try:
            distances = [max(1, int(d.strip())) for d in dist_str.split(',') if d.strip()]
        except ValueError:
            distances = [1, 2]

        # ── Extract band ─────────────────────────────────────────────────────
        bands = geo['bands']
        if bands.ndim == 2:
            bands = bands[np.newaxis]
        C = bands.shape[0]
        if band_idx >= C:
            send_notification(
                f'GLCM: band_index={band_idx} out of range (stack has {C} bands)',
                level='error', notif_id=_NOTIF,
            )
            return {}

        band_2d = bands[band_idx].astype(np.float32)
        H, W    = band_2d.shape

        _log(f'band={band_idx}  size={W}×{H}  win={win}  stride={stride}  '
             f'levels={levels}  props={properties}')

        send_notification(
            f'GLCM: computing {len(properties)} features on {W}×{H} band '
            f'(win={win}, stride={stride})…',
            progress=0.05, notif_id=_NOTIF,
        )

        # ── Quantize ─────────────────────────────────────────────────────────
        img_q = _quantize(band_2d, levels)

        # ── Compute texture map ───────────────────────────────────────────────
        try:
            texture = _glcm_map(
                img_q, win, distances, _ANGLES, properties, levels, stride,
            )
        except Exception as e:
            send_notification(f'GLCM: error: {e}', level='error', notif_id=_NOTIF)
            return {}

        # ── Build geo dict ────────────────────────────────────────────────────
        band_names = [f'{prop}_{suffix}' for prop in properties]

        # Preserve spatial reference from input
        src_tf  = geo.get('transform')
        src_crs = geo.get('crs', 'EPSG:4326')

        out_geo: dict = {
            'bands':      texture.astype(np.float32),
            'crs':        src_crs,
            'transform':  src_tf,
            'count':      len(properties),
            'height':     H,
            'width':      W,
            'dtype':      'float32',
            'band_names': band_names,
        }

        preview = _preview_band(texture[0])

        send_notification(
            f'GLCM: {len(properties)} bands → {", ".join(band_names)}',
            progress=1.0, notif_id=_NOTIF,
        )

        return {'geotiff': out_geo, 'preview': preview}
