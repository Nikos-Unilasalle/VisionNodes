"""
geo_spectral_indices.py — Multi-index spectral calculator (replaces geo_spectral_index + geo_band_calc).

Computes any combination of built-in indices (NDVI, NDWI, EVI, MNDWI, NBR, BSI)
plus up to 2 custom expressions (B1…Bn notation) from a single geo dict input.

Outputs:
  stack    — multi-band geo dict, one band per enabled index (use directly in
             geo_rf_classifier, geo_band_stack, geo_ground_truth_sampler …)
  preview  — RGB false-color of the first three enabled bands
  ndvi / ndwi / evi / mndwi / nbr / bsi / custom1 / custom2
           — individual colormapped image for each named index (None if disabled)

Band naming convention in `stack`:
  The geo dict carries `band_names` = list of enabled index labels,
  in the order they appear in `bands`. Downstream nodes (geo_rf_classifier,
  geo_band_stack …) use this list to label feature importance charts.
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'spectral_indices'

_CV2_CMAPS: dict[str, int] = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'jet':     cv2.COLORMAP_JET,
    'hot':     cv2.COLORMAP_HOT,
    'rdylgn':  cv2.COLORMAP_RdYlGn if hasattr(cv2, 'COLORMAP_RdYlGn') else cv2.COLORMAP_VIRIDIS,
    'gray':    cv2.COLORMAP_BONE,
}
_CMAP_KEYS = list(_CV2_CMAPS.keys())

# Sensor preset band assignments {name: (nir, red, green, blue, swir)}
_SENSOR_PRESETS: dict[str, tuple[int, int, int, int, int]] = {
    'Manual':                 (4, 1, 2, 3, 5),
    'S2 (B04 B03 B02 B08 B11)': (4, 1, 2, 3, 5),   # B04=R B03=G B02=B B08=NIR B11=SWIR1
    'Landsat 8/9 (L2)':       (5, 4, 3, 2, 6),   # B05=NIR B04=R B03=G B02=B B06=SWIR1
    'SPOT-6/7':               (4, 3, 2, 1, 5),
}
_SENSOR_NAMES = list(_SENSOR_PRESETS.keys())


def _band(bands: np.ndarray, idx: int) -> np.ndarray:
    """Return band idx (1-based) as float32, or zeros if out of range."""
    i = max(0, int(idx) - 1)
    if i < bands.shape[0]:
        return bands[i].astype(np.float32)
    return np.zeros(bands.shape[1:], dtype=np.float32)


_DEN_MIN = np.float32(1e-6)


def _norm_index(a: np.ndarray, b: np.ndarray,
                valid_min: float | None = None) -> np.ndarray:
    """Normalised-difference index (a - b) / (a + b).

    Default (valid_min=None): legacy fast path (a - b) / (a + b + ε).

    With valid_min set, reproduces the reference water-mask guard: a pixel is
    NaN (cast no vote downstream) wherever either input band ≤ valid_min, the
    denominator |a + b| is below _DEN_MIN, or an input is non-finite. This stops
    the ratio from exploding or flipping sign on near-zero / slightly-negative
    reflectance (e.g. ACOLITE Rrs over dark water). Result clipped to [-1, 1].
    """
    if valid_min is None:
        return (a - b) / (a + b + 1e-8)
    den = a + b
    out = np.full(a.shape, np.nan, dtype=np.float32)
    ok = (np.isfinite(a) & np.isfinite(b) &
          (np.abs(den) > _DEN_MIN) &
          (a > np.float32(valid_min)) & (b > np.float32(valid_min)))
    out[ok] = ((a[ok] - b[ok]) / den[ok]).astype(np.float32, copy=False)
    np.clip(out, -1.0, 1.0, out=out)
    return out


def _colorize(arr: np.ndarray, cmap: int,
               vmin: float, vmax: float) -> np.ndarray:
    """Float array → BGR uint8 via colormap."""
    span = vmax - vmin if vmax != vmin else 1.0
    scaled = np.nan_to_num((arr - vmin) / span * 255.0, nan=0.0, posinf=255.0, neginf=0.0)
    norm = np.clip(scaled, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(norm, cmap)


def _rgb_preview(bands_list: list[np.ndarray],
                  cmap: int, vmin: float, vmax: float) -> np.ndarray:
    """RGB false-color from up to 3 bands (each float32)."""
    n = len(bands_list)
    if n == 0:
        return np.zeros((64, 64, 3), dtype=np.uint8)

    def _norm(b: np.ndarray) -> np.ndarray:
        span = vmax - vmin if vmax != vmin else 1.0
        scaled = np.nan_to_num((b - vmin) / span * 255.0, nan=0.0, posinf=255.0, neginf=0.0)
        return np.clip(scaled, 0, 255).astype(np.uint8)

    if n == 1:
        return cv2.applyColorMap(_norm(bands_list[0]), cmap)

    r = _norm(bands_list[0])
    g = _norm(bands_list[1])
    b = _norm(bands_list[2]) if n >= 3 else np.zeros_like(r)
    return cv2.merge([b, g, r])   # BGR


@vision_node(
    type_id='geo_spectral_indices',
    label='Spectral Indices',
    category='geography',
    icon='BarChart2',
    description=(
        "Multi-index spectral calculator. Select any combination of built-in indices "
        "(NDVI, NDWI, EVI, MNDWI, NBR, BSI) and/or write up to 2 custom expressions. "
        "Outputs a multi-band `stack` geo dict (use directly in geo_rf_classifier or "
        "geo_band_stack) plus individual colormapped images for each enabled index. "
        "Replace geo_spectral_index + geo_band_calc with this single node."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'Raster'}],
    outputs=[
        {'id': 'stack',   'color': 'geotiff', 'label': 'All enabled (stacked)'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview RGB (first 3)'},
        {'id': 'ndvi',    'color': 'image',   'label': 'NDVI'},
        {'id': 'ndwi',    'color': 'image',   'label': 'NDWI'},
        {'id': 'evi',     'color': 'image',   'label': 'EVI'},
        {'id': 'mndwi',   'color': 'image',   'label': 'MNDWI'},
        {'id': 'nbr',     'color': 'image',   'label': 'NBR'},
        {'id': 'bsi',     'color': 'image',   'label': 'BSI'},
        {'id': 'custom1', 'color': 'image',   'label': 'Custom 1'},
        {'id': 'custom2', 'color': 'image',   'label': 'Custom 2'},
    ],
    params=[
        {'id': '_sec_bands', 'type': 'section', 'label': 'Band Mapping'},
        {'id': 'sensor',     'type': 'enum',  'options': _SENSOR_NAMES, 'default': 0,
         'label': 'Sensor preset'},
        {'id': 'nir_band',   'type': 'int',   'default': 4, 'min': 1, 'max': 20, 'label': 'NIR band'},
        {'id': 'red_band',   'type': 'int',   'default': 1, 'min': 1, 'max': 20, 'label': 'Red band'},
        {'id': 'green_band', 'type': 'int',   'default': 2, 'min': 1, 'max': 20, 'label': 'Green band'},
        {'id': 'blue_band',  'type': 'int',   'default': 3, 'min': 1, 'max': 20, 'label': 'Blue band'},
        {'id': 'swir_band',  'type': 'int',   'default': 5, 'min': 1, 'max': 20, 'label': 'SWIR band'},
        {'id': '_sec_indices', 'type': 'section', 'label': 'Indices'},
        {'id': 'ndvi',  'type': 'bool', 'default': True,  'label': 'NDVI (Vegetation)'},
        {'id': 'ndwi',  'type': 'bool', 'default': False, 'label': 'NDWI (Water)'},
        {'id': 'evi',   'type': 'bool', 'default': False, 'label': 'EVI (Enhanced Veg.)'},
        {'id': 'mndwi', 'type': 'bool', 'default': False, 'label': 'MNDWI (Modified Water)'},
        {'id': 'nbr',   'type': 'bool', 'default': False, 'label': 'NBR (Burn Ratio)'},
        {'id': 'bsi',   'type': 'bool', 'default': False, 'label': 'BSI (Bare Soil)'},
        {'id': 'guard_invalid', 'type': 'bool', 'default': False,
         'label': 'Guard invalid pixels (ND indices → NaN below floor)'},
        {'id': 'valid_min', 'type': 'float', 'default': -0.002, 'min': -1.0, 'max': 1.0, 'step': 0.001,
         'label': 'Valid band floor', 'show_if': {'param': 'guard_invalid', 'value': True}},
        {'id': '_sec_custom', 'type': 'section', 'label': 'Custom Expressions'},
        {'id': 'expr1_enable', 'type': 'bool',   'default': False, 'label': 'Enable expr 1'},
        {'id': 'expr1_label',  'type': 'string', 'default': 'custom1', 'label': 'Name'},
        {'id': 'expr1',        'type': 'code',   'default': '(B4 - B3) / (B4 + B3 + 1e-8)',
         'label': 'Expression (B1…Bn, np, sqrt, log)'},
        {'id': 'expr2_enable', 'type': 'bool',   'default': False, 'label': 'Enable expr 2'},
        {'id': 'expr2_label',  'type': 'string', 'default': 'custom2', 'label': 'Name'},
        {'id': 'expr2',        'type': 'code',   'default': '', 'label': 'Expression'},
        {'id': '_sec_display', 'type': 'section', 'label': 'Display'},
        {'id': 'colormap',  'type': 'enum',  'options': _CMAP_KEYS, 'default': 0,
         'label': 'Colormap'},
        {'id': 'clamp_min', 'type': 'float', 'default': -1.0, 'min': -10.0, 'max': 0.0,
         'label': 'Clamp min'},
        {'id': 'clamp_max', 'type': 'float', 'default':  1.0, 'min':  0.0, 'max': 10.0,
         'label': 'Clamp max'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=280, min_height=200,
)
class SpectralIndicesNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            return {}

        bands = geo['bands']
        if bands.ndim == 2:
            bands = bands[np.newaxis]
        count = bands.shape[0]

        # ── Sensor preset overrides manual band assignments ───────────────────
        sensor_idx = int(params.get('sensor', 0))
        sensor_name = _SENSOR_NAMES[sensor_idx] if sensor_idx < len(_SENSOR_NAMES) else 'Manual'
        if sensor_name != 'Manual' and sensor_name in _SENSOR_PRESETS:
            nir_b, red_b, grn_b, blu_b, swir_b = _SENSOR_PRESETS[sensor_name]
        else:
            nir_b  = int(params.get('nir_band',   4))
            red_b  = int(params.get('red_band',   1))
            grn_b  = int(params.get('green_band', 2))
            blu_b  = int(params.get('blue_band',  3))
            swir_b = int(params.get('swir_band',  5))

        NIR  = _band(bands, nir_b)
        RED  = _band(bands, red_b)
        GRN  = _band(bands, grn_b)
        BLU  = _band(bands, blu_b)
        SWIR = _band(bands, swir_b)

        # ── Display settings ─────────────────────────────────────────────────
        cmap_raw = params.get('colormap', 0)
        if isinstance(cmap_raw, int):
            cmap_name = _CMAP_KEYS[cmap_raw] if cmap_raw < len(_CMAP_KEYS) else 'viridis'
        else:
            cmap_name = str(cmap_raw)
        cmap    = _CV2_CMAPS.get(cmap_name, cv2.COLORMAP_VIRIDIS)
        vmin    = float(params.get('clamp_min', -1.0))
        vmax    = float(params.get('clamp_max',  1.0))

        # Reference-script validity guard for normalised-difference indices: drop
        # near-zero / slightly-negative reflectance so the ratio cannot blow up or
        # flip sign (matters for ACOLITE Rrs). Disabled by default (legacy path).
        guard = bool(params.get('guard_invalid', False))
        valid_min = float(params.get('valid_min', -0.002)) if guard else None

        # ── Compute enabled preset indices ────────────────────────────────────
        enabled_arrays: list[np.ndarray] = []
        enabled_labels: list[str]        = []
        result: dict = {}

        def _add(key: str, arr: np.ndarray) -> None:
            enabled_arrays.append(arr)
            enabled_labels.append(key.upper())
            result[key] = _colorize(arr, cmap, vmin, vmax)

        if params.get('ndvi', True):
            _add('ndvi', _norm_index(NIR, RED, valid_min))

        if params.get('ndwi', False):
            _add('ndwi', _norm_index(GRN, NIR, valid_min))

        if params.get('evi', False):
            evi = 2.5 * (NIR - RED) / (NIR + 6.0 * RED - 7.5 * BLU + 1.0 + 1e-8)
            _add('evi', np.clip(evi, vmin, vmax))

        if params.get('mndwi', False):
            _add('mndwi', _norm_index(GRN, SWIR, valid_min))

        if params.get('nbr', False):
            _add('nbr', _norm_index(NIR, SWIR, valid_min))

        if params.get('bsi', False):
            # Bare Soil Index: (SWIR+RED - NIR+BLUE) / (SWIR+RED + NIR+BLUE)
            bsi = _norm_index(SWIR + RED, NIR + BLU)
            _add('bsi', bsi)

        # ── Custom expressions ────────────────────────────────────────────────
        _ns_base = {
            **{f'B{i+1}': bands[i].astype(np.float32) for i in range(count)},
            'NIR': NIR, 'RED': RED, 'GREEN': GRN, 'BLUE': BLU, 'SWIR': SWIR,
            'np': np, 'sqrt': np.sqrt, 'log': np.log,
            'abs': np.abs, 'exp': np.exp, 'clip': np.clip,
        }

        for idx, (en_key, lbl_key, expr_key, out_key) in enumerate([
            ('expr1_enable', 'expr1_label', 'expr1', 'custom1'),
            ('expr2_enable', 'expr2_label', 'expr2', 'custom2'),
        ]):
            if not params.get(en_key, False):
                continue
            expr = str(params.get(expr_key, '')).strip()
            if not expr:
                continue
            label = str(params.get(lbl_key, out_key)).strip() or out_key
            try:
                arr = np.asarray(
                    eval(expr, {'__builtins__': {}}, dict(_ns_base)),  # noqa: S307
                    dtype=np.float32,
                )
                arr = np.clip(arr, vmin, vmax)
                enabled_arrays.append(arr)
                enabled_labels.append(label)
                result[out_key] = _colorize(arr, cmap, vmin, vmax)
            except Exception as e:
                send_notification(
                    f'Spectral Indices: {out_key} expression error: {e}',
                    level='error', notif_id=_NOTIF,
                )

        # ── Fill disabled outputs with None ────────────────────────────────────
        for key in ('ndvi', 'ndwi', 'evi', 'mndwi', 'nbr', 'bsi', 'custom1', 'custom2'):
            result.setdefault(key, None)

        if not enabled_arrays:
            send_notification(
                'Spectral Indices: no index enabled — toggle at least one.',
                level='warning', notif_id=_NOTIF,
            )
            return result

        # ── Stack: multi-band geo dict ────────────────────────────────────────
        stacked = np.stack(enabled_arrays, axis=0)   # (N, H, W)
        stack_geo = {
            **geo,
            'bands':      stacked,
            'count':      stacked.shape[0],
            'band_names': enabled_labels,
            'dtype':      'float32',
        }
        result['stack'] = stack_geo

        # ── Preview RGB (first 3 enabled bands) ──────────────────────────────
        result['preview'] = _rgb_preview(enabled_arrays[:3], cmap, vmin, vmax)

        return result
