"""
geo_transition_map.py — Bi-temporal class transition detection

Compares two classification maps (T0 and T1, same grid) and highlights
specific class transitions of interest (e.g. Trees→Bare = deforestation).

Typical use (Guyane deforestation analysis):
  classmap_2018 ──┐
                  ├─→ geo_transition_map ──→ transition raster + stats + report
  classmap_2024 ──┘
       params:    transitions = "10>60,95>60"
                  transition_labels = "10>60=Deforestation,95>60=Mangrove loss"

Outputs:
  transitions (geotiff)  : uint8 raster, 0 = no change tracked, 1..N = transition codes
  preview (image)        : RGB visualization (grey = persistent class, color = transitions)
  stats (dict)           : per-transition pixel count + area_ha + percentage
  report (image)         : bar chart of areas per transition (dark theme)

Resolution caveat: pixel area assumes input transform is in metres (UTM). For EPSG:4326
the area_ha column falls back to NaN (lat/lon degrees can't be converted without lat).
"""
from __future__ import annotations
import io

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_transition_map'

# BGR colors for up to 6 tracked transitions (high-contrast set)
_TRANS_COLORS_BGR = [
    (0,   0,   220),   # red       — first transition (default: deforestation)
    (0,   140, 255),   # orange    — second
    (0,   220, 220),   # yellow    — third
    (100, 200, 0),     # green     — fourth (e.g. regrowth)
    (220, 100, 0),     # blue      — fifth
    (180, 100, 200),   # magenta   — sixth
]
_PERSIST_COLOR    = (60, 60, 60)      # dark grey — pixels that didn't change to a tracked class
_OUT_OF_DOMAIN    = (20, 20, 20)      # near-black — pixels where one input is missing/zero

_MPL_DARK = {
    'figure.facecolor':  '#161616',
    'axes.facecolor':    '#1e1e1e',
    'axes.edgecolor':    '#555555',
    'axes.labelcolor':   '#cccccc',
    'text.color':        '#cccccc',
    'xtick.color':       '#aaaaaa',
    'ytick.color':       '#aaaaaa',
    'grid.color':        '#333333',
    'grid.linestyle':    '--',
    'grid.linewidth':    0.5,
}


def _parse_transitions(s: str) -> list[tuple[int, int]]:
    """'10>60,95>60' → [(10, 60), (95, 60)]"""
    out: list[tuple[int, int]] = []
    for item in s.split(','):
        item = item.strip()
        if '>' in item:
            a, b = item.split('>', 1)
            try:
                out.append((int(a.strip()), int(b.strip())))
            except ValueError:
                pass
    return out


def _parse_labels(s: str) -> dict[str, str]:
    """'10>60=Deforestation,95>60=Mangrove loss' → {'10>60': 'Deforestation', …}"""
    out: dict[str, str] = {}
    for item in s.split(','):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def _pixel_area_ha(transform) -> float:
    """Compute pixel area in hectares from an Affine transform.

    Assumes transform units are metres (i.e. UTM projection). Returns NaN for
    EPSG:4326 / degree-based grids since proper area requires latitude.
    """
    try:
        # rasterio.Affine: a = pixel width (x), e = pixel height (y, usually negative)
        px_w = abs(float(transform.a))
        px_h = abs(float(transform.e))
        # Heuristic: degrees are <1, metres are >>1
        if px_w > 1.0 and px_h > 1.0:
            return (px_w * px_h) / 10_000.0  # m² → ha
    except Exception:
        pass
    return float('nan')


def _morpho_filter(mask: np.ndarray, min_pixels: int) -> np.ndarray:
    """Remove connected components smaller than min_pixels."""
    if min_pixels <= 1:
        return mask
    mask_u8 = mask.astype(np.uint8)
    n_lbl, lbl, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    keep = np.zeros_like(mask, dtype=bool)
    # Skip background (label 0)
    for i in range(1, n_lbl):
        if stats[i, cv2.CC_STAT_AREA] >= min_pixels:
            keep[lbl == i] = True
    return keep


def _build_preview(
    code_map:     np.ndarray,
    n_trans:      int,
    valid_mask:   np.ndarray,
) -> np.ndarray:
    """code_map: 0=persistent, 1..N=transition_idx, 255=out of domain."""
    h, w = code_map.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)
    # Default = persistent
    out[:] = _PERSIST_COLOR
    # Out of domain (one input is 0/nan)
    out[~valid_mask] = _OUT_OF_DOMAIN
    # Each transition colored
    for i in range(1, n_trans + 1):
        m = code_map == i
        if m.any():
            out[m] = _TRANS_COLORS_BGR[(i - 1) % len(_TRANS_COLORS_BGR)]
    return out


def _render_bar_report(
    rows:       list[tuple[str, int, float]],   # (label, n_px, area_ha)
    total_valid: int,
    dpi:        int,
) -> np.ndarray | None:
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    if not rows:
        return None

    with plt.rc_context(_MPL_DARK):
        fig, ax = plt.subplots(figsize=(8, 0.6 + 0.45 * len(rows)), dpi=dpi)
        labels = [r[0] for r in rows]
        areas  = [r[2] if not np.isnan(r[2]) else r[1] for r in rows]   # ha or px fallback
        units  = 'hectares' if not np.isnan(rows[0][2]) else 'pixels'
        colors = [
            '#%02x%02x%02x' % (
                _TRANS_COLORS_BGR[i % len(_TRANS_COLORS_BGR)][2],
                _TRANS_COLORS_BGR[i % len(_TRANS_COLORS_BGR)][1],
                _TRANS_COLORS_BGR[i % len(_TRANS_COLORS_BGR)][0],
            )
            for i in range(len(rows))
        ]
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, areas, color=colors, edgecolor='#444')
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(labels, fontsize=10)
        ax.set_xlabel(f'Area ({units})', fontsize=9)
        ax.set_title(f'Tracked transitions  (over {total_valid:,} valid px)',
                     fontsize=10, pad=8)

        # Annotate
        for bar, (_, n_px, area_ha) in zip(bars, rows):
            v = bar.get_width()
            txt = (f'{area_ha:,.1f} ha  ({n_px:,} px)'
                   if not np.isnan(area_ha) else f'{n_px:,} px')
            ax.text(v, bar.get_y() + bar.get_height() / 2,
                    f' {txt}', va='center', fontsize=9, color='#dddddd')

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
    type_id='geo_transition_map',
    label='Transition Map',
    category='remote sensing',
    icon='ArrowRightLeft',
    description=(
        'Bi-temporal class transition detection. Takes two classification maps (T0, T1) '
        'on the same grid and highlights user-specified transitions (e.g. "10>60" = '
        'Trees→Bare = deforestation). Outputs: transition raster (uint8 codes), '
        'colored RGB preview, per-transition stats, and a bar chart report. '
        'Designed for deforestation / orpaillage analysis: train RF on 2024, predict '
        '2018 with geo_rf_predict, feed both classmaps here.'
    ),
    inputs=[
        {'id': 'classmap_a', 'color': 'geotiff', 'label': 'Classmap T0 (earlier)'},
        {'id': 'classmap_b', 'color': 'geotiff', 'label': 'Classmap T1 (later)'},
    ],
    outputs=[
        {'id': 'transitions', 'color': 'geotiff', 'label': 'Transition raster (uint8 codes)'},
        {'id': 'preview',     'color': 'image',   'label': 'Colored RGB preview'},
        {'id': 'stats',       'color': 'dict',    'label': 'Per-transition statistics'},
        {'id': 'report',      'color': 'image',   'label': 'Bar chart (hectares per transition)'},
    ],
    params=[
        {'id': 'transitions', 'type': 'string',
         'default': '10>60,95>60,10>80',
         'label': 'Transitions to track (src>dst,…)'},
        {'id': 'transition_labels', 'type': 'string',
         'default': '10>60=Deforestation,95>60=Mangrove loss,10>80=Flooded',
         'label': 'Human-readable labels (src>dst=Name,…)'},
        {'id': 'min_pixels', 'type': 'int', 'default': 5, 'min': 1, 'max': 1000,
         'label': 'Min connected pixels (noise filter)'},
        {'id': 'dpi', 'type': 'int', 'default': 110, 'min': 72, 'max': 300,
         'label': 'Report DPI'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GeoTransitionMapNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        a = inputs.get('classmap_a')
        b = inputs.get('classmap_b')
        if not isinstance(a, dict) or a.get('bands') is None:
            send_notification('Transition: connect classmap_a (T0)', notif_id=_NOTIF)
            return {}
        if not isinstance(b, dict) or b.get('bands') is None:
            send_notification('Transition: connect classmap_b (T1)', notif_id=_NOTIF)
            return {}

        arr_a = a['bands'][0] if a['bands'].ndim == 3 else a['bands']
        arr_b = b['bands'][0] if b['bands'].ndim == 3 else b['bands']

        # Shape check
        if arr_a.shape != arr_b.shape:
            send_notification(
                f'Transition: shape mismatch — a={arr_a.shape} vs b={arr_b.shape}. '
                f'Reproject one to the other grid first.',
                level='error', notif_id=_NOTIF,
            )
            return {}

        arr_a_i = arr_a.astype(np.int32)
        arr_b_i = arr_b.astype(np.int32)

        # Parse params
        trans_list  = _parse_transitions(str(params.get('transitions', '10>60')))
        if not trans_list:
            send_notification('Transition: no valid transitions in params', notif_id=_NOTIF)
            return {}
        labels_map  = _parse_labels(str(params.get('transition_labels', '')))
        min_pixels  = max(1, int(params.get('min_pixels', 5)))
        dpi         = max(72, int(params.get('dpi', 110)))

        # Domain mask = pixels valid in BOTH inputs (non-zero, non-nan)
        valid_mask = (
            (arr_a_i > 0) & (arr_b_i > 0)
            & np.isfinite(arr_a) & np.isfinite(arr_b)
        )
        n_valid = int(valid_mask.sum())

        H, W = arr_a.shape
        code_map = np.zeros((H, W), dtype=np.uint8)

        # Pixel area (ha)
        tf = a.get('transform') if a.get('transform') is not None else b.get('transform')
        px_ha = _pixel_area_ha(tf) if tf is not None else float('nan')

        # Apply transitions in order; later ones overwrite earlier where overlapping
        stats: dict = {'pixel_area_ha': px_ha, 'n_valid_px': n_valid, 'transitions': []}
        report_rows: list[tuple[str, int, float]] = []

        for idx, (src, dst) in enumerate(trans_list, start=1):
            mask = valid_mask & (arr_a_i == src) & (arr_b_i == dst)
            mask = _morpho_filter(mask, min_pixels)
            n_px = int(mask.sum())
            area_ha = n_px * px_ha if not np.isnan(px_ha) else float('nan')
            code_map[mask] = idx

            key   = f'{src}>{dst}'
            label = labels_map.get(key, key)
            stats['transitions'].append({
                'code':     idx,
                'src':      src,
                'dst':      dst,
                'key':      key,
                'label':    label,
                'n_pixels': n_px,
                'area_ha':  area_ha,
                'percent':  (n_px / n_valid * 100.0) if n_valid > 0 else 0.0,
            })
            report_rows.append((label, n_px, area_ha))

            send_notification(
                f'Transition {key} ({label}): {n_px:,} px'
                + (f' = {area_ha:,.1f} ha' if not np.isnan(area_ha) else ''),
                progress=0.2 + 0.6 * idx / len(trans_list),
                notif_id=_NOTIF,
            )

        # ── Build preview ─────────────────────────────────────────────────────
        preview = _build_preview(code_map, len(trans_list), valid_mask)

        # ── Build geo dict ────────────────────────────────────────────────────
        out_geo = {
            'bands':      code_map[np.newaxis],
            'crs':        a.get('crs'),
            'transform':  a.get('transform'),
            'count':      1,
            'height':     H,
            'width':      W,
            'dtype':      'uint8',
            'band_names': ['transition_code'],
            'preview':    preview,
            '_codes':     [t['label'] for t in stats['transitions']],
        }

        # ── Render bar report ─────────────────────────────────────────────────
        report_img = _render_bar_report(report_rows, n_valid, dpi)
        if report_img is None:
            # Fallback: tiny grey placeholder
            report_img = np.full((100, 400, 3), 30, dtype=np.uint8)

        send_notification(
            f'Transition: done — {len(trans_list)} tracked, '
            f'{sum(t["n_pixels"] for t in stats["transitions"]):,} affected px',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'transitions': out_geo,
            'preview':     preview,
            'stats':       stats,
            'report':      report_img,
        }
