"""
raster_colorizer.py — Multi-band false-colour composite with per-band colour pickers.

Dynamic inputs: connect up to 8 bands (any type — geotiff dict or numpy array).
Each band maps in connection order to colour/label params (A → B → C …).

Per-band mode:
  Threshold — pixels > threshold get solid colour, rest = background (last-wins)
  Gradient  — pixel value (0→1) mapped linearly from color_min to color_max (last-wins)

Typical workflow:
    geo_change_classifier stable → A
    geo_change_classifier regrowth → B
    ...
    raster_colorizer → image_legend → output_display
"""
from __future__ import annotations
import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'raster_colorizer'
_SLOTS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']

_DEFAULTS: list[tuple[str, str]] = [
    ('Forêt stable',              '#226422'),
    ('Repousse / site abandonné', '#64C864'),
    ('Déboisement',               '#8C501E'),
    ('Eau turbide',               '#FF1400'),
    ('Band E',                    '#0050C8'),
    ('Band F',                    '#00C8C8'),
    ('Band G',                    '#C80078'),
    ('Band H',                    '#C8C800'),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_to_bgr(h: str) -> tuple[int, int, int]:
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def _extract_band(val: object) -> np.ndarray | None:
    """Extract a 2-D float32 band from a geotiff dict or numpy array."""
    if val is None:
        return None
    if isinstance(val, dict):
        raw = val.get('bands')
        if raw is None:
            return None
        arr = np.asarray(raw, dtype=np.float32)
        return arr[0] if arr.ndim == 3 else arr
    if isinstance(val, np.ndarray):
        arr = val.astype(np.float32)
        if arr.ndim == 3:
            arr = arr[:, :, 0] if arr.shape[2] < arr.shape[0] else arr[0]
        return arr
    return None


def _safe_bgr(hex_str: str, fallback: tuple[int, int, int] = (128, 128, 128)) -> tuple[int, int, int]:
    try:
        return _hex_to_bgr(str(hex_str))
    except Exception:
        return fallback


# ── Param list builder ────────────────────────────────────────────────────────

def _slot_params() -> list[dict]:
    out: list[dict] = []
    for i, slot in enumerate(_SLOTS):
        default_label, default_color = _DEFAULTS[i]
        out += [
            {
                'id': f'{slot}_mode', 'type': 'enum',
                'options': ['Threshold', 'Gradient'], 'default': 0,
                'label': f'Mode {slot.upper()}',
                'slot': slot,
            },
            {
                'id': f'{slot}_label', 'type': 'string',
                'default': default_label, 'label': f'Label {slot.upper()}',
                'slot': slot,
            },
            {
                'id': f'{slot}_color', 'type': 'color',
                'default': default_color, 'label': f'Color / Max {slot.upper()}',
                'slot': slot,
            },
            {
                'id': f'{slot}_threshold', 'type': 'float',
                'default': 0.5, 'min': 0.0, 'max': 1.0,
                'label': f'Threshold {slot.upper()}',
                'slot': slot,
                'show_if': {'param': f'{slot}_mode', 'value': 0},
            },
            {
                'id': f'{slot}_color_min', 'type': 'color',
                'default': '#000000', 'label': f'Color Min {slot.upper()}',
                'slot': slot,
                'show_if': {'param': f'{slot}_mode', 'value': 1},
            },
            {
                'id': f'{slot}_opacity', 'type': 'float',
                'default': 1.0, 'min': 0.0, 'max': 1.0, 'step': 0.05,
                'label': f'Opacity {slot.upper()}',
                'slot': slot,
            },
        ]
    return out


# ── Node ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='raster_colorizer',
    label='Raster Colorizer',
    category='geography',
    icon='Palette',
    description=(
        'Maps up to 8 dynamic band inputs to user-defined colours. '
        'Per-band mode: Threshold (solid colour above threshold) or '
        'Gradient (value mapped linearly between two colours). '
        'Last-wins compositing. Chain with image_legend for a legend overlay.'
    ),
    dynamic_inputs=True,
    inputs=[
        {'id': 'a', 'color': 'any', 'label': 'A'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Colorized image'},
    ],
    params=[
        {
            'id': 'background', 'type': 'color',
            'default': '#282828', 'label': 'Background',
        },
    ] + _slot_params(),
)
class RasterColorizerNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        _static = {'a', 'main'}

        # Build ordered (band, slot_index) list
        bands: list[tuple[np.ndarray, int]] = []

        # Static port a → index 0
        band_a = _extract_band(inputs.get('a'))
        if band_a is not None:
            bands.append((band_a, 0))

        # Dynamic ports → indices 1+
        dyn_items = sorted(
            [(k, v) for k, v in inputs.items() if k not in _static and v is not None],
            key=lambda x: x[0],
        )
        for i, (_, val) in enumerate(dyn_items):
            band = _extract_band(val)
            if band is not None:
                bands.append((band, i + 1))

        if not bands:
            send_notification('RasterColorizer: connect at least one band', notif_id=_NOTIF)
            return {}

        bg_bgr = _safe_bgr(str(params.get('background', '#282828')), (40, 40, 40))

        H, W = bands[0][0].shape
        canvas = np.full((H, W, 3), bg_bgr, dtype=np.uint8)

        for band, slot_idx in bands:
            slot = _SLOTS[slot_idx] if slot_idx < len(_SLOTS) else _SLOTS[-1]
            mode = int(params.get(f'{slot}_mode', 0))
            alpha = float(np.clip(params.get(f'{slot}_opacity', 1.0), 0.0, 1.0))

            if band.shape != (H, W):
                band = cv2.resize(band, (W, H), interpolation=cv2.INTER_NEAREST)

            # Normalise band to 0-1
            band_max = float(band.max())
            band_norm = band / band_max if band_max > 0 else band

            if mode == 0:
                # ── Threshold mode ──────────────────────────────────────────
                thr = float(params.get(f'{slot}_threshold', 0.5))
                bgr = _safe_bgr(str(params.get(f'{slot}_color', _DEFAULTS[slot_idx % 8][1])))
                sel = band_norm > thr
                if alpha >= 1.0:
                    canvas[sel] = bgr
                elif alpha > 0.0:
                    src = np.array(bgr, dtype=np.float32)
                    canvas[sel] = ((1.0 - alpha) * canvas[sel].astype(np.float32)
                                   + alpha * src).astype(np.uint8)

            else:
                # ── Gradient mode ───────────────────────────────────────────
                bgr_min = np.array(_safe_bgr(str(params.get(f'{slot}_color_min', '#000000'))),
                                   dtype=np.float32)
                bgr_max = np.array(_safe_bgr(str(params.get(f'{slot}_color', _DEFAULTS[slot_idx % 8][1]))),
                                   dtype=np.float32)
                t = np.clip(band_norm, 0.0, 1.0)[:, :, np.newaxis]        # (H, W, 1)
                grad = (bgr_min * (1.0 - t) + bgr_max * t).astype(np.float32)
                if alpha >= 1.0:
                    canvas[:] = grad.astype(np.uint8)
                elif alpha > 0.0:
                    canvas[:] = ((1.0 - alpha) * canvas.astype(np.float32)
                                 + alpha * grad).astype(np.uint8)

        return {'main': canvas}
