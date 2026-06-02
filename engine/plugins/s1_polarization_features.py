"""
s1_polarization_features.py — Derived radar polarization features from
Sentinel-1 dual-pol (VV+VH) backscatter.

Why this node exists
--------------------
Raw VV and VH dB are useful but the literature consistently shows that
dual-pol *derived* indices carry the strongest signal for land-cover and
biomass discrimination:

  - RVI  (Radar Vegetation Index)        = 4·VH / (VV + VH)
  - Span (total received power)          = VV + VH
  - NRPB (Normalised Ratio between Pols) = (VV − VH) / (VV + VH)
  - PDI  (Polarisation Difference Index) = VV − VH
  - PRI  (Polarisation Ratio Index)      = VH / VV
  - DPSVI (Dual-Pol SAR Vegetation Index) = (VV² + VV·VH) / √2  (Periasamy 2018)

References
----------
- Trudel et al. 2012 — RVI mapping for vegetation
- Kim & van Zyl 2009 — RVI for soil moisture
- Mandal et al. 2020 — dual-pol descriptors for crop classification
- Proisy et al. 2018 — co/cross-pol contrast for French Guiana mangroves

Input contract
--------------
A canonical `geotiff` dict from `geo_copernicus` (S1 RTC backend) or any
compatible producer:
    {
      'bands':      np.ndarray,    # (B, H, W) float32
      'band_names': list[str],     # must contain 'vv' and 'vh'
      'transform':  Affine,
      'crs':        str,
      ...
    }

The optional `to_db` flag is read from `_dates` / source tags via
`meta.get('to_db')` when present; otherwise inferred from band magnitudes
(values < 0 → already in dB, values > 0 small → linear).

Output
------
A new geotiff dict where `bands` is stacked with the requested features.
"""
from __future__ import annotations
import os
from pathlib import Path

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 's1_pol_features'


# ── Math helpers (operate in LINEAR space, with NaN-safe semantics) ──────────

def _from_db(x: np.ndarray) -> np.ndarray:
    """dB → linear power."""
    return np.power(10.0, x / 10.0)


def _to_db(x: np.ndarray) -> np.ndarray:
    """Linear power → dB, NaN-safe."""
    with np.errstate(divide='ignore', invalid='ignore'):
        return 10.0 * np.log10(np.where(x > 0, x, np.nan))


def _safe_divide(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    """num / den with den<=0 → NaN."""
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(np.isfinite(den) & (den > 0), num / den, np.nan)


def compute_features(vv_lin: np.ndarray, vh_lin: np.ndarray,
                     which: dict[str, bool]) -> dict[str, np.ndarray]:
    """Compute requested features in linear space. Returns dict {name: array}."""
    out: dict[str, np.ndarray] = {}
    span = vv_lin + vh_lin
    diff = vv_lin - vh_lin

    if which.get('rvi'):
        # RVI = 4·VH / (VV + VH), range ~[0, 1.33]; 0 = open water, ~1 = dense vegetation
        out['rvi'] = _safe_divide(4.0 * vh_lin, span)

    if which.get('span'):
        # Total received power (linear)
        out['span'] = span.astype(np.float32)

    if which.get('span_db'):
        out['span_db'] = _to_db(span).astype(np.float32)

    if which.get('nrpb'):
        # Normalised ratio: (VV - VH)/(VV + VH), range [-1, 1]
        out['nrpb'] = _safe_divide(diff, span)

    if which.get('pdi'):
        # Polarization difference in dB (VV_dB - VH_dB)
        out['pdi_db'] = (_to_db(vv_lin) - _to_db(vh_lin)).astype(np.float32)

    if which.get('pri'):
        # Polarization ratio VH/VV (linear)
        out['pri'] = _safe_divide(vh_lin, vv_lin)

    if which.get('dpsvi'):
        # Dual-Polarization SAR Vegetation Index (Periasamy 2018 simplification):
        # DPSVI = (VV·VV + VV·VH) / sqrt(2)
        # Sensitive to canopy density, robust to soil moisture confounds.
        out['dpsvi'] = ((vv_lin * vv_lin + vv_lin * vh_lin) / np.sqrt(2)).astype(np.float32)

    return out


# ── Node ─────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='s1_polarization_features',
    label='S1 Polarization Features',
    category='geography',
    icon='Activity',
    description=(
        "Compute dual-pol radar features from Sentinel-1 VV+VH: RVI, Span, "
        "NRPB, PDI, PRI, DOP. Operates in linear power internally (handles dB "
        "input automatically). Appends features to the input GeoTIFF and "
        "writes a new file."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'S1 GeoTIFF (VV, VH)'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Enriched GeoTIFF'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview'},
        {'id': 'meta',    'color': 'dict',    'label': 'Meta'},
    ],
    params=[
        {'id': 'rvi',     'type': 'bool', 'default': True,  'label': 'RVI (4·VH/(VV+VH))'},
        {'id': 'span',    'type': 'bool', 'default': True,  'label': 'Span (linear VV+VH)'},
        {'id': 'span_db', 'type': 'bool', 'default': False, 'label': 'Span (dB)'},
        {'id': 'nrpb',    'type': 'bool', 'default': True,  'label': 'NRPB ((VV−VH)/(VV+VH))'},
        {'id': 'pdi',     'type': 'bool', 'default': True,  'label': 'PDI (VV−VH, dB)'},
        {'id': 'pri',     'type': 'bool', 'default': False, 'label': 'PRI (VH/VV)'},
        {'id': 'dpsvi',   'type': 'bool', 'default': False, 'label': 'DPSVI (canopy density)'},
        {'id': 'output_db', 'type': 'bool', 'default': True,
         'label': 'Output VV/VH in dB (matches input if absent)'},
        {'id': 'cache_dir', 'type': 'string', 'default': 'planetary_cache',
         'label': 'Cache Dir'},
    ],
    resizable=True, min_width=280, min_height=200,
)
class S1PolarizationFeaturesNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._result: dict | None = None
        self._sig: str | None = None

    @staticmethod
    def _info_panel(lines: list[str], title: str = '') -> np.ndarray:
        w, h = 460, 240
        img = np.full((h, w, 3), 22, dtype=np.uint8)
        cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
        cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX,
                    0.46, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
        for i, line in enumerate(lines[:12]):
            cv2.putText(img, str(line)[:72], (8, 48 + i * 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (185, 185, 185), 1, cv2.LINE_AA)
        return img

    @staticmethod
    def _stretch(arr: np.ndarray) -> np.ndarray:
        valid = arr[np.isfinite(arr)]
        if valid.size == 0:
            return np.zeros(arr.shape, dtype=np.uint8)
        lo, hi = np.percentile(valid, (2, 98))
        if hi <= lo:
            return np.full(arr.shape, 128, dtype=np.uint8)
        return np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)

    def _preview(self, bands: dict[str, np.ndarray]) -> np.ndarray:
        """Pick first three derived features for false color, fall back gracefully."""
        order_pref = ['rvi', 'nrpb', 'pdi_db', 'span_db', 'dpsvi', 'pri']
        picks = [n for n in order_pref if n in bands][:3]
        if len(picks) < 3:
            return self._info_panel(['Enable at least three features for RGB preview.',
                                     f'available: {list(bands.keys())}'],
                                    title='S1 Pol Features')
        r = self._stretch(bands[picks[0]])
        g = self._stretch(bands[picks[1]])
        b = self._stretch(bands[picks[2]])
        rgb = np.stack([b, g, r], axis=-1)
        # Annotate which band is which
        h, w = rgb.shape[:2]
        if w >= 240:
            cv2.rectangle(rgb, (4, 4), (235, 60), (0, 0, 0), -1)
            for i, name in enumerate(picks):
                color = [(40, 40, 220), (40, 220, 40), (220, 40, 40)][i]
                cv2.putText(rgb, f'{"RGB"[i]}: {name}', (8, 22 + i * 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
        return rgb

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            self._result = None
            return {'preview': self._info_panel(
                ['Connect a Sentinel-1 GeoTIFF (VV + VH).'],
                title='S1 Polarization Features',
            )}

        band_names = [n.lower() for n in geo.get('band_names', [])]
        # Accept either canonical `bands` (geo_copernicus) or legacy `array`.
        arr = geo.get('bands')
        if arr is None:
            arr = geo.get('array')
        if arr is None:
            return {'preview': self._info_panel(
                ['Input geotiff has no `bands` (or `array`) field.'],
                title='error')}

        if 'vv' not in band_names or 'vh' not in band_names:
            return {'preview': self._info_panel(
                [f'Need VV and VH; got: {band_names}'],
                title='S1 Pol Features — missing bands')}

        in_meta = geo.get('meta', {}) or {}
        # `to_db` flag may live in meta (legacy) or be inferred from values
        in_db = str(in_meta.get('to_db', '')).lower() == 'true'
        if 'to_db' not in in_meta:
            # Infer: dB values are typically in [-40, 30], linear power < ~1
            vv_idx = band_names.index('vv')
            sample = arr[vv_idx]
            sample = sample[np.isfinite(sample)]
            if sample.size > 0:
                in_db = float(np.percentile(sample, 5)) < 0

        vv_band = arr[band_names.index('vv')].astype(np.float32)
        vh_band = arr[band_names.index('vh')].astype(np.float32)

        # Always compute in linear; convert back at the end if requested.
        vv_lin = _from_db(vv_band) if in_db else vv_band
        vh_lin = _from_db(vh_band) if in_db else vh_band

        which = {
            'rvi':     bool(params.get('rvi', True)),
            'span':    bool(params.get('span', True)),
            'span_db': bool(params.get('span_db', False)),
            'nrpb':    bool(params.get('nrpb', True)),
            'pdi':     bool(params.get('pdi', True)),
            'pri':     bool(params.get('pri', False)),
            'dpsvi':   bool(params.get('dpsvi', False)),
        }

        # Cache: compute signature so repeated identical calls are free.
        sig = (
            geo.get('path', ''),
            tuple(sorted(which.items())),
            bool(params.get('output_db', True)),
        )
        if self._result is not None and self._sig == sig:
            return self._result

        try:
            feats = compute_features(vv_lin, vh_lin, which)
        except Exception as e:
            send_notification(f'S1 Pol: compute failed: {e}',
                              level='error', notif_id=_NOTIF)
            return {'preview': self._info_panel([f'Compute error: {e}'],
                                                title='error')}

        # Re-stack: keep input bands first, append features.
        output_db = bool(params.get('output_db', True))
        out_bands: dict[str, np.ndarray] = {}
        # original bands (respect output_db preference for VV/VH)
        for name in band_names:
            band = arr[band_names.index(name)].astype(np.float32)
            if name in ('vv', 'vh'):
                if output_db and not in_db:
                    band = _to_db(band)
                elif (not output_db) and in_db:
                    band = _from_db(band)
            out_bands[name] = band
        # appended features
        for name, b in feats.items():
            out_bands[name] = b.astype(np.float32)

        final_names = list(out_bands.keys())
        final_arr = np.stack([out_bands[n] for n in final_names], axis=0)

        # Write next to the input file
        out_path = self._write_geotiff(geo, final_arr, final_names, output_db, params)

        meta_out = dict(in_meta)
        meta_out.update({
            'band_names': ','.join(final_names),
            'features_added': ','.join(feats.keys()),
            'to_db': str(output_db),
        })

        self._sig = sig
        # Build canonical geotiff dict (matches geo_copernicus output schema)
        # so downstream nodes consume `bands` directly.
        out_geo = dict(geo)  # carry over crs/transform/bounds/width/height
        out_geo.update({
            'bands':       final_arr,
            'band_names':  final_names,
            'count':       final_arr.shape[0],
            'meta':        meta_out,
            '_cache_path': out_path or geo.get('_cache_path') or geo.get('path'),
            '_bands':      final_names,
        })
        self._result = {
            'geotiff': out_geo,
            'preview': self._preview(feats),
            'meta': {
                'source': 's1_polarization_features',
                'input_bands': band_names,
                'added': list(feats.keys()),
                'output_db_vv_vh': output_db,
                'path': out_path,
            },
        }
        send_notification(
            f'S1 Pol: added {len(feats)} features → {len(final_names)} bands',
            progress=1.0, notif_id=_NOTIF,
        )
        return self._result

    @staticmethod
    def _write_geotiff(geo: dict, arr: np.ndarray, band_names: list[str],
                       output_db: bool, params: dict) -> str | None:
        """Persist the enriched stack next to the input file. Best-effort."""
        try:
            import rasterio
        except ImportError:
            return None
        src_path = geo.get('path')
        if not src_path or not os.path.exists(src_path):
            return None
        try:
            with rasterio.open(src_path) as src:
                profile = src.profile.copy()
            profile.update(count=arr.shape[0], dtype='float32',
                           compress='deflate', predictor=2,
                           nodata=float('nan'))
            cache_dir = params.get('cache_dir', 'planetary_cache')
            d = Path(cache_dir) if os.path.isabs(cache_dir) else (
                Path(src_path).parent / cache_dir
            ) if cache_dir == 'planetary_cache' else Path(cache_dir)
            d.mkdir(parents=True, exist_ok=True)
            stem = Path(src_path).stem
            out = d / f'{stem}_pol_features.tif'
            with rasterio.open(out, 'w', **profile) as dst:
                dst.write(arr)
                for i, name in enumerate(band_names, start=1):
                    dst.set_band_description(i, name)
                dst.update_tags(
                    band_names=','.join(band_names),
                    output_db=str(output_db),
                )
            return str(out)
        except Exception:
            return None
