"""
geo_change_classifier.py — Generic bi-temporal change classifier for remote sensing.

Compares a configurable spectral index between two dates (T0, T1) to detect
where a phenomenon is *persistent*, newly *gained*, or *lost*. Works for any
index-based study: vegetation (NDVI), water (NDWI/MNDWI), built-up (NDBI),
burn severity (NBR), snow (NDSI), etc.

How it works:
  - Primary index: pick a band, a threshold, and a direction ('>' or '<').
    A pixel is "present" when the index passes the threshold.
        present_T0 & present_T1  → persistent
        absent_T0  & present_T1  → gain   (appearance)
        present_T0 & absent_T1   → loss   (disappearance)
  - Secondary index (optional): a second band/threshold that, where it passes,
    overrides the transition classes with a separate "special" class
    (e.g. open water masked over a land-change map).
  - Validity masks (mask_t0 / mask_t1, 1 = valid, 0 = excluded) flag invalid
    pixels per date — clouds, shadows, bridges, urban artefacts, sensor gaps.

Outputs binary masks per class + an RGB preview. Chain with raster_colorizer
for custom false-colour rendering.

Example mappings:
    Forest loss study : primary = NDVI '>' → persistent=forest, gain=regrowth,
                        loss=deforestation; secondary = MNDWI '>' → water.
    Urban growth      : primary = NDBI '>' → persistent/new/removed built-up.
    Water dynamics    : primary = NDWI '>' → permanent/seasonal/dried water.
"""
from __future__ import annotations
import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_change_classifier'

# Default preview colours (BGR)
_PREVIEW_COLORS = {
    'persistent': (34,  100,  34),   # dark green
    'gain':       (100, 200, 100),   # light green
    'loss':       (30,   80, 140),   # orange-brown (BGR)
    'special':    (200, 120,  20),   # blue
    'excl_t0':    (180, 180, 180),   # light grey
    'excl_t1':    (100, 100, 100),   # dark grey
    'excl_both':  (60,   60,  60),   # near black
}


def _extract_band(val: object, idx: int = 0) -> np.ndarray | None:
    """Extract a 2-D float32 band from a geotiff dict or numpy array."""
    if val is None:
        return None
    if isinstance(val, dict):
        raw = val.get('bands')
        if raw is None:
            return None
        arr = np.asarray(raw, dtype=np.float32)
        if arr.ndim == 2:
            return arr if idx == 0 else None
        return arr[idx] if idx < arr.shape[0] else arr[0]
    if isinstance(val, np.ndarray):
        arr = val.astype(np.float32)
        if arr.ndim == 2:
            return arr if idx == 0 else None
        if arr.ndim == 3:
            if arr.shape[2] < arr.shape[0]:          # (H, W, C)
                return arr[:, :, idx] if idx < arr.shape[2] else arr[:, :, 0]
            return arr[idx] if idx < arr.shape[0] else arr[0]   # (C, H, W)
    return None


def _valid_mask(val: object, H: int, W: int) -> np.ndarray:
    """Return bool mask (H, W): True where pixel is valid (not excluded).
    Falls back to all-True if input is None or unreadable."""
    if val is None:
        return np.ones((H, W), dtype=bool)
    band = _extract_band(val, 0)
    if band is None:
        return np.ones((H, W), dtype=bool)
    if band.shape != (H, W):
        band = cv2.resize(band, (W, H), interpolation=cv2.INTER_NEAREST)
    return band > 0


def _present(band: np.ndarray, thr: float, direction: int) -> np.ndarray:
    """direction 0 → present where band > thr; 1 → present where band < thr."""
    return band < thr if direction == 1 else band > thr


# ── Node ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_change_classifier',
    label='Change Classifier',
    category='geography',
    icon='Layers',
    description=(
        'Generic bi-temporal change classifier. Compares a configurable spectral '
        'index between two dates (T0, T1) to flag where a phenomenon is persistent, '
        'newly gained, or lost. Works for any index study — NDVI, NDWI, NDBI, NBR… '
        'Optional secondary index adds a "special" override class (e.g. water). '
        'Validity masks (1=valid, 0=excluded) filter clouds, shadows, artefacts. '
        'Outputs binary masks per class + RGB preview. Chain with raster_colorizer.'
    ),
    inputs=[
        {'id': 't0',      'color': 'geotiff', 'label': 'Stack T0'},
        {'id': 't1',      'color': 'geotiff', 'label': 'Stack T1'},
        {'id': 'mask_t0', 'color': 'any',     'label': 'Validity mask T0 (optional, 1=valid)'},
        {'id': 'mask_t1', 'color': 'any',     'label': 'Validity mask T1 (optional, 1=valid)'},
    ],
    outputs=[
        {'id': 'persistent', 'color': 'mask', 'label': 'Persistent'},
        {'id': 'gain',       'color': 'mask', 'label': 'Gain'},
        {'id': 'loss',       'color': 'mask', 'label': 'Loss'},
        {'id': 'special',    'color': 'mask', 'label': 'Special (2nd index)'},
        {'id': 'excl_t0',    'color': 'mask', 'label': 'Excluded T0 only'},
        {'id': 'excl_t1',    'color': 'mask', 'label': 'Excluded T1 only'},
        {'id': 'excl_both',  'color': 'mask', 'label': 'Excluded both'},
        {'id': 'preview',    'color': 'image','label': 'Preview RGB'},
    ],
    params=[
        # ── Primary index ──────────────────────────────────────────────────
        {'id': 'primary_band', 'type': 'int', 'default': 0, 'min': 0, 'max': 15,
         'label': 'Primary index band'},
        {'id': 'primary_thr',  'type': 'float', 'default': 0.12, 'min': -1.0, 'max': 1.0, 'step': 0.01,
         'label': 'Primary threshold'},
        {'id': 'primary_dir',  'type': 'enum', 'options': ['Present if >', 'Present if <'],
         'default': 0, 'label': 'Primary direction'},
        # ── Secondary (special) index ──────────────────────────────────────
        {'id': 'secondary_enable', 'type': 'bool', 'default': False,
         'label': 'Enable secondary index'},
        {'id': 'secondary_band', 'type': 'int', 'default': 1, 'min': 0, 'max': 15,
         'label': 'Secondary index band',
         'show_if': {'param': 'secondary_enable', 'value': True}},
        {'id': 'secondary_thr',  'type': 'float', 'default': 0.0, 'min': -1.0, 'max': 1.0, 'step': 0.01,
         'label': 'Secondary threshold',
         'show_if': {'param': 'secondary_enable', 'value': True}},
        {'id': 'secondary_dir',  'type': 'enum', 'options': ['Special if >', 'Special if <'],
         'default': 0, 'label': 'Secondary direction',
         'show_if': {'param': 'secondary_enable', 'value': True}},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
)
class GeoChangeClassifier(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        t0_raw = inputs.get('t0')
        t1_raw = inputs.get('t1')

        if t0_raw is None or t1_raw is None:
            send_notification('ChangeClassifier: connect t0 and t1 stacks', notif_id=_NOTIF)
            return {}

        p_band = int(params.get('primary_band', 0))
        p_thr  = float(params.get('primary_thr', 0.12))
        p_dir  = int(params.get('primary_dir', 0))

        idx_t0 = _extract_band(t0_raw, p_band)
        idx_t1 = _extract_band(t1_raw, p_band)

        if idx_t0 is None or idx_t1 is None:
            send_notification('ChangeClassifier: could not read primary band', notif_id=_NOTIF)
            return {}

        H, W = idx_t0.shape

        def _resize(arr: np.ndarray) -> np.ndarray:
            return arr if arr.shape == (H, W) else cv2.resize(arr, (W, H), interpolation=cv2.INTER_LINEAR)

        idx_t1 = _resize(idx_t1)

        # Validity masks (True = valid pixel)
        v0 = _valid_mask(inputs.get('mask_t0'), H, W)
        v1 = _valid_mask(inputs.get('mask_t1'), H, W)

        # ── Secondary (special) override class ────────────────────────────────
        special = np.zeros((H, W), dtype=bool)
        if bool(params.get('secondary_enable', False)):
            s_band = int(params.get('secondary_band', 1))
            s_thr  = float(params.get('secondary_thr', 0.0))
            s_dir  = int(params.get('secondary_dir', 0))
            sec_t1 = _extract_band(t1_raw, s_band)
            if sec_t1 is not None:
                special = _present(_resize(sec_t1), s_thr, s_dir)

        # ── Primary transitions ───────────────────────────────────────────────
        present_t0 = _present(idx_t0, p_thr, p_dir)
        present_t1 = _present(idx_t1, p_thr, p_dir)

        land = ~special  # special overrides land transitions
        mask_persistent = present_t0  & present_t1  & land
        mask_gain       = ~present_t0 & present_t1  & land
        mask_loss       = present_t0  & ~present_t1 & land
        mask_special    = special

        # Excluded pixels — override every land/special class
        mask_excl_t0   = ~v0 &  v1
        mask_excl_t1   =  v0 & ~v1
        mask_excl_both = ~v0 & ~v1

        def _to_mask(arr: np.ndarray) -> np.ndarray:
            return arr.astype(np.uint8) * 255

        # ── Preview RGB ───────────────────────────────────────────────────────
        preview = np.full((H, W, 3), 40, dtype=np.uint8)
        preview[mask_persistent] = _PREVIEW_COLORS['persistent']
        preview[mask_gain]       = _PREVIEW_COLORS['gain']
        preview[mask_loss]       = _PREVIEW_COLORS['loss']
        preview[mask_special]    = _PREVIEW_COLORS['special']
        preview[mask_excl_t0]    = _PREVIEW_COLORS['excl_t0']
        preview[mask_excl_t1]    = _PREVIEW_COLORS['excl_t1']
        preview[mask_excl_both]  = _PREVIEW_COLORS['excl_both']

        return {
            'persistent': _to_mask(mask_persistent),
            'gain':       _to_mask(mask_gain),
            'loss':       _to_mask(mask_loss),
            'special':    _to_mask(mask_special),
            'excl_t0':    _to_mask(mask_excl_t0),
            'excl_t1':    _to_mask(mask_excl_t1),
            'excl_both':  _to_mask(mask_excl_both),
            'preview':    preview,
        }
