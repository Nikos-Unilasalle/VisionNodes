"""
geo_spectral_change.py — Bi-temporal spectral change detection on continuous index stacks.

Takes two geo_spectral_indices outputs (T0, T1) and:
  1. Computes delta rasters (T1 − T0) per band.
  2. Evaluates threshold rules on the deltas.
  3. Combines rules (AND / OR) → binary change mask.
  4. Filters small patches (min_pixels).

Typical orpaillage signature:
  rules   = "NDVI<-0.2,MNDWI>0.1"   (forest razed + turbid water appeared)
  combine = AND

Outputs:
  change_mask  (geotiff) : uint8 binary, 1 = change flagged
  delta_stack  (geotiff) : float32, one band per index (T1 − T0)
  preview      (image)   : R=|ΔNDVI drop|, B=ΔMNDWI rise → violet = orpaillage
  stats        (dict)    : n_pixels, area_ha, per-rule counts
  report       (image)   : bar chart
"""
from __future__ import annotations
import io
import re

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_spectral_change'

_MPL_DARK = {
    'figure.facecolor': '#161616',
    'axes.facecolor':   '#1e1e1e',
    'axes.edgecolor':   '#555555',
    'axes.labelcolor':  '#cccccc',
    'text.color':       '#cccccc',
    'xtick.color':      '#aaaaaa',
    'ytick.color':      '#aaaaaa',
    'grid.color':       '#333333',
    'grid.linestyle':   '--',
    'grid.linewidth':   0.5,
}

_RULE_RE = re.compile(r'^\s*(\w+)\s*(<=|>=|<|>)\s*([+-]?\d*\.?\d+)\s*$')


def _parse_rules(s: str) -> list[tuple[str, str, float]]:
    """'NDVI<-0.2,MNDWI>0.1' → [('NDVI','<',-0.2), ('MNDWI','>',0.1)]"""
    out = []
    for item in s.split(','):
        m = _RULE_RE.match(item.strip())
        if m:
            out.append((m.group(1), m.group(2), float(m.group(3))))
    return out


def _pixel_area_ha(transform) -> float:
    try:
        px_w = abs(float(transform.a))
        px_h = abs(float(transform.e))
        if px_w > 1.0 and px_h > 1.0:
            return (px_w * px_h) / 10_000.0
    except Exception:
        pass
    return float('nan')


def _morpho_filter(mask: np.ndarray, min_pixels: int) -> np.ndarray:
    if min_pixels <= 1:
        return mask
    mask_u8 = mask.astype(np.uint8)
    n_lbl, lbl, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    keep = np.zeros_like(mask, dtype=bool)
    for i in range(1, n_lbl):
        if stats[i, cv2.CC_STAT_AREA] >= min_pixels:
            keep[lbl == i] = True
    return keep


def _apply_op(delta: np.ndarray, op: str, threshold: float) -> np.ndarray:
    if op == '<':  return delta < threshold
    if op == '>':  return delta > threshold
    if op == '<=': return delta <= threshold
    if op == '>=': return delta >= threshold
    return np.zeros(delta.shape, dtype=bool)


def _render_report(
    rule_stats: list[tuple[str, int, float]],
    total_px:   int,
    dpi:        int,
) -> np.ndarray | None:
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    if not rule_stats:
        return None

    with plt.rc_context(_MPL_DARK):
        fig, ax = plt.subplots(figsize=(8, 0.6 + 0.45 * len(rule_stats)), dpi=dpi)
        labels = [r[0] for r in rule_stats]
        areas  = [r[2] if not np.isnan(r[2]) else r[1] for r in rule_stats]
        units  = 'ha' if not np.isnan(rule_stats[0][2]) else 'px'
        colors = ['#dd4444', '#4488ff', '#ffaa22', '#44cc88', '#cc44cc', '#88ccff']
        y_pos  = range(len(labels))
        bars   = ax.barh(list(y_pos), areas, color=colors[:len(labels)], edgecolor='#444')
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(labels, fontsize=10)
        ax.set_xlabel(f'Area ({units})', fontsize=9)
        ax.set_title(f'Spectral change  ({total_px:,} flagged px)', fontsize=10, pad=8)
        for bar, (_, n_px, area_ha) in zip(bars, rule_stats):
            v   = bar.get_width()
            txt = f'{area_ha:,.1f} ha  ({n_px:,} px)' if not np.isnan(area_ha) else f'{n_px:,} px'
            ax.text(v, bar.get_y() + bar.get_height() / 2, f' {txt}',
                    va='center', fontsize=9, color='#dddddd')
        ax.invert_yaxis()
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        arr = np.frombuffer(buf.getvalue(), dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)


@vision_node(
    type_id='geo_spectral_change',
    label='Spectral Change',
    category='geography',
    icon='TrendingDown',
    description=(
        'Bi-temporal spectral change detection on continuous index stacks (from '
        'geo_spectral_indices). Computes delta (T1−T0) per band, applies threshold '
        'rules, combines into a binary change mask. '
        'Orpaillage signature: rules="NDVI<-0.2,MNDWI>0.1" (vegetation collapse + '
        'turbid water appeared). Preview: R=|ΔNDVI drop|, B=ΔMNDWI rise → violet=orpaillage.'
    ),
    inputs=[
        {'id': 'spectral_t0',    'color': 'geotiff', 'label': 'Spectral indices T0 (earlier)'},
        {'id': 'spectral_t1',    'color': 'geotiff', 'label': 'Spectral indices T1 (later)'},
        {'id': 'valid_mask_t0',  'color': 'geotiff', 'label': 'Cloud mask T0 (1=valid, optional)'},
        {'id': 'valid_mask_t1',  'color': 'geotiff', 'label': 'Cloud mask T1 (1=valid, optional)'},
    ],
    outputs=[
        {'id': 'change_mask', 'color': 'geotiff', 'label': 'Change mask (uint8 binary)'},
        {'id': 'delta_stack', 'color': 'geotiff', 'label': 'Delta raster (T1−T0, float32)'},
        {'id': 'preview',     'color': 'image',   'label': 'Preview (R=drop B=rise)'},
        {'id': 'stats',       'color': 'dict',    'label': 'Statistics'},
        {'id': 'report',      'color': 'image',   'label': 'Bar chart report'},
    ],
    params=[
        {'id': 'rules',      'type': 'string', 'default': 'NDVI<-0.2,MNDWI>0.1',
         'label': 'Rules  band op threshold  (comma-sep)'},
        {'id': 'combine',    'type': 'enum',   'default': 'AND', 'options': ['AND', 'OR'],
         'label': 'Combine rules'},
        {'id': 'min_pixels', 'type': 'int',    'default': 5, 'min': 1, 'max': 1000,
         'label': 'Min connected pixels (noise filter)'},
        {'id': 'dpi',        'type': 'int',    'default': 110, 'min': 72, 'max': 300,
         'label': 'Report DPI'},
        {'id': 'node_note',  'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GeoSpectralChangeNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        t0 = inputs.get('spectral_t0')
        t1 = inputs.get('spectral_t1')

        if not isinstance(t0, dict) or t0.get('bands') is None:
            send_notification('SpectralChange: connect spectral_t0', notif_id=_NOTIF)
            return {}
        if not isinstance(t1, dict) or t1.get('bands') is None:
            send_notification('SpectralChange: connect spectral_t1', notif_id=_NOTIF)
            return {}

        bands0 = np.asarray(t0['bands'], dtype=np.float32)
        bands1 = np.asarray(t1['bands'], dtype=np.float32)

        if bands0.ndim == 2: bands0 = bands0[np.newaxis]
        if bands1.ndim == 2: bands1 = bands1[np.newaxis]

        names0: list[str] = t0.get('band_names') or [f'B{i+1}' for i in range(bands0.shape[0])]
        names1: list[str] = t1.get('band_names') or [f'B{i+1}' for i in range(bands1.shape[0])]

        if bands0.shape != bands1.shape:
            send_notification(
                f'SpectralChange: shape mismatch {bands0.shape} vs {bands1.shape} — '
                'reproject one stack to the other grid first.',
                level='error', notif_id=_NOTIF,
            )
            return {}

        transform = t1.get('transform') or t0.get('transform')
        crs       = t1.get('crs')       or t0.get('crs')

        delta = bands1 - bands0          # (C, H, W) float32
        _, H, W = delta.shape

        # Parse rules and evaluate
        rules_raw = str(params.get('rules', 'NDVI<-0.2,MNDWI>0.1'))
        parsed    = _parse_rules(rules_raw)
        combine   = str(params.get('combine', 'AND')).upper()

        if not parsed:
            send_notification('SpectralChange: no valid rules — format: NDVI<-0.2,MNDWI>0.1',
                              level='warn', notif_id=_NOTIF)
            return {}

        rule_masks:  list[np.ndarray] = []
        rule_labels: list[str]        = []
        rule_parsed: list[tuple[str, str, float]] = []

        for band_name, op, thr in parsed:
            if band_name in names0:
                bidx = names0.index(band_name)
            elif band_name in names1:
                bidx = names1.index(band_name)
            else:
                send_notification(f'SpectralChange: band "{band_name}" not in stack — skip',
                                  level='warn', notif_id=_NOTIF)
                continue
            rule_masks.append(_apply_op(delta[bidx], op, thr))
            rule_labels.append(f'Δ{band_name}{op}{thr}')
            rule_parsed.append((band_name, op, thr))

        if not rule_masks:
            send_notification('SpectralChange: no rules matched available bands',
                              level='error', notif_id=_NOTIF)
            return {}

        if combine == 'AND':
            combined = rule_masks[0].copy()
            for m in rule_masks[1:]:
                combined &= m
        else:
            combined = rule_masks[0].copy()
            for m in rule_masks[1:]:
                combined |= m

        # Apply cloud masks (T0 AND T1 must both be valid)
        for vm_key in ('valid_mask_t0', 'valid_mask_t1'):
            vm = inputs.get(vm_key)
            if not isinstance(vm, dict) or vm.get('bands') is None:
                continue
            vm_arr = np.asarray(vm['bands'], dtype=np.uint8)
            if vm_arr.ndim == 3: vm_arr = vm_arr[0]
            if vm_arr.shape == (H, W):
                combined = combined & (vm_arr > 0)
            else:
                send_notification(f'SpectralChange: {vm_key} shape mismatch — ignored',
                                  level='warn', notif_id=_NOTIF)

        min_pixels = int(params.get('min_pixels', 5))
        combined   = _morpho_filter(combined, min_pixels)

        px_area_ha = _pixel_area_ha(transform)
        n_flagged  = int(combined.sum())
        area_ha    = n_flagged * px_area_ha if not np.isnan(px_area_ha) else float('nan')

        rule_stats: list[tuple[str, int, float]] = []
        for lbl, rm in zip(rule_labels, rule_masks):
            n = int((rm & combined).sum()) if combine == 'AND' else int(rm.sum())
            rule_stats.append((lbl, n, n * px_area_ha if not np.isnan(px_area_ha) else float('nan')))

        stats = {
            'n_pixels': n_flagged,
            'area_ha':  round(area_ha, 2) if not np.isnan(area_ha) else None,
            'rules':    {
                lbl: {'n_pixels': n, 'area_ha': round(a, 2) if not np.isnan(a) else None}
                for lbl, n, a in rule_stats
            },
        }

        # Preview: dark background, R=|drop| B=rise so orpaillage = violet
        preview = np.zeros((H, W, 3), dtype=np.uint8)
        bg = delta[0]
        bg_norm = ((bg - bg.min()) / (float(bg.max() - bg.min()) + 1e-9) * 60).clip(0, 60).astype(np.uint8)
        preview[:, :, 0] = bg_norm
        preview[:, :, 1] = bg_norm
        preview[:, :, 2] = bg_norm

        for (band_name, op, _thr), rm in zip(rule_parsed, rule_masks):
            if band_name in names0:
                bidx = names0.index(band_name)
            elif band_name in names1:
                bidx = names1.index(band_name)
            else:
                continue
            d = delta[bidx]
            if op in ('<', '<='):   # drop → red channel (BGR[2])
                intensity = (np.clip(-d / max(float(-d.min()), 1e-9), 0, 1) * 220).astype(np.uint8)
                preview[:, :, 2] = np.maximum(preview[:, :, 2], intensity)
            else:                   # rise → blue channel (BGR[0])
                intensity = (np.clip(d / max(float(d.max()), 1e-9), 0, 1) * 220).astype(np.uint8)
                preview[:, :, 0] = np.maximum(preview[:, :, 0], intensity)

        # White contours around flagged regions
        contours, _ = cv2.findContours(combined.astype(np.uint8),
                                       cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(preview, contours, -1, (255, 255, 255), 1)

        change_geotiff = {
            'bands':      combined.astype(np.uint8)[np.newaxis],
            'transform':  transform,
            'crs':        crs,
            'band_names': ['change'],
        }
        delta_geotiff = {
            'bands':      delta,
            'transform':  transform,
            'crs':        crs,
            'band_names': names0[:delta.shape[0]],
        }

        report = _render_report(rule_stats, n_flagged, int(params.get('dpi', 110)))

        send_notification(
            f'SpectralChange: {n_flagged:,} px flagged'
            + (f'  ({area_ha:.1f} ha)' if not np.isnan(area_ha) else '')
            + f'  [{combine}]',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'change_mask': change_geotiff,
            'delta_stack': delta_geotiff,
            'preview':     preview,
            'stats':       stats,
            'report':      report,
        }
