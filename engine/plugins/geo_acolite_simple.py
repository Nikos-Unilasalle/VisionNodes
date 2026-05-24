"""
geo_acolite_simple.py — Simplified atmospheric correction for Sentinel-2 water pixels.

Converts S2 L2A BOA reflectance → Remote Sensing Reflectance (Rrs, sr⁻¹) using:
  1. DN → float reflectance (÷10000 if values > 2)
  2. Dark Object Subtraction (DOS-1): subtract per-band 1st-percentile
     to remove residual path radiance not corrected by Sen2Cor
  3. Divide by π: BOA ρ → above-water Rrs [sr⁻¹]

This makes S2 L2A data compatible with GLORIA matchup datasets (Rrs units).
Not a full ACOLITE run, but sufficient for turbidity estimation demos.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'acolite'
_PI = np.float32(np.pi)


def _info_panel(lines: list, w: int = 460, h: int = 220, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 15
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:72], (8, 44 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.37, color, 1, cv2.LINE_AA)
    return img


def _band_histogram(bands: np.ndarray, band_names: list[str], w: int = 460, h: int = 200) -> np.ndarray:
    """Small per-band histogram overlay for quick QC."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        count = bands.shape[0]
        fig, axes = plt.subplots(1, count, figsize=(count * 1.4, 1.8),
                                  facecolor='#161616')
        if count == 1:
            axes = [axes]
        colors = ['#4488ff', '#44bb44', '#ff4444', '#bb44ff']
        for i, ax in enumerate(axes):
            flat = bands[i].ravel()
            flat = flat[np.isfinite(flat) & (flat > 0)]
            if flat.size > 0:
                ax.hist(flat, bins=40, color=colors[i % len(colors)], alpha=0.8)
            ax.set_title(band_names[i] if i < len(band_names) else f'B{i+1}',
                         fontsize=7, color='#cccccc', pad=2)
            ax.tick_params(colors='#888888', labelsize=5)
            ax.set_facecolor('#1e1e1e')
            for spine in ax.spines.values():
                spine.set_edgecolor('#444444')
        fig.tight_layout(pad=0.4)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=90, bbox_inches='tight', facecolor='#161616')
        buf.seek(0)
        arr = np.frombuffer(buf.read(), dtype=np.uint8)
        buf.close()
        plt.close(fig)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img if img is not None else np.zeros((h, w, 3), dtype=np.uint8)
    except Exception:
        return np.zeros((h, w, 3), dtype=np.uint8)


@vision_node(
    type_id='geo_acolite_simple',
    label='ACOLITE Correction (simplified)',
    category='geography',
    icon='Waves',
    description=(
        "Simplified atmospheric correction for Sentinel-2 water pixels. "
        "Converts S2 L2A BOA reflectance → Rrs (sr⁻¹) units compatible with GLORIA. "
        "Steps: (1) DN→float (÷10000 auto-detect), (2) Dark Object Subtraction "
        "per band (1st percentile), (3) divide by π → Rrs [sr⁻¹]. "
        "Not a full ACOLITE run but sufficient for turbidity estimation demos."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'S2 L2A BOA raster'},
    ],
    outputs=[
        {'id': 'geotiff',   'color': 'geotiff', 'label': 'Rrs raster [sr⁻¹]'},
        {'id': 'preview',   'color': 'image',   'label': 'Band histograms'},
        {'id': 'rrs_min',   'color': 'scalar',  'label': 'Rrs min (all bands)'},
        {'id': 'rrs_max',   'color': 'scalar',  'label': 'Rrs max (all bands)'},
    ],
    params=[
        {'id': 'auto_scale',    'label': 'Auto DN→float (÷10000 if max>2)',
         'type': 'bool', 'default': True},
        {'id': 'dos1',          'label': 'Dark Object Subtraction (DOS-1)',
         'type': 'bool', 'default': True},
        {'id': 'dos_percentile','label': 'DOS percentile (typ. 0.5–2)',
         'type': 'float', 'default': 1.0, 'min': 0.0, 'max': 10.0},
        {'id': 'to_rrs',        'label': 'Divide by π → Rrs [sr⁻¹]',
         'type': 'bool', 'default': True},
        {'id': 'clip_rrs_max',  'label': 'Clip Rrs max (0=off)',
         'type': 'float', 'default': 0.12, 'min': 0.0, 'max': 1.0},
        {'id': 'band_names',    'label': 'Band names (comma, blank=auto)',
         'type': 'string', 'default': 'Bleu,Vert,Rouge,NIR'},
    ],
    resizable=True, min_width=280, min_height=200,
)
class AcoliteSimpleNode(NodeProcessor):

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            return {}

        bands_in = geo['bands'].copy().astype(np.float32)
        if bands_in.ndim == 2:
            bands_in = bands_in[np.newaxis, :, :]
        count, H, W = bands_in.shape

        names_str = str(params.get('band_names', '')).strip()
        band_names = [n.strip() for n in names_str.split(',') if n.strip()]
        band_names = (band_names + [f'band_{i+1}' for i in range(len(band_names), count)])[:count]

        steps: list[str] = [f'Input: {H}x{W} px, {count} bands']

        # ── Step 1: DN → float reflectance
        if bool(params.get('auto_scale', True)):
            band_max = float(np.nanmax(bands_in))
            if band_max > 2.0:
                bands_in = bands_in / 10000.0
                steps.append(f'DN/10000 (max was {band_max:.0f})')
            else:
                steps.append(f'Already float (max={band_max:.4f})')

        # ── Step 2: DOS-1 per band
        if bool(params.get('dos1', True)):
            pct = float(params.get('dos_percentile', 1.0))
            for i in range(count):
                flat = bands_in[i].ravel()
                dark = float(np.nanpercentile(flat[flat > 0], pct)) if np.any(flat > 0) else 0.0
                bands_in[i] = np.clip(bands_in[i] - dark, 0.0, None)
            steps.append(f'DOS-1 (p{pct:.1f}% per band)')

        # ── Step 3: /pi → Rrs
        if bool(params.get('to_rrs', True)):
            bands_in = bands_in / _PI
            steps.append('/pi -> Rrs [sr-1]')

        # ── Clip Rrs max
        clip_max = float(params.get('clip_rrs_max', 0.12))
        if clip_max > 0.0:
            bands_in = np.clip(bands_in, 0.0, clip_max)
            steps.append(f'Clip [0, {clip_max}]')

        rrs_min = float(np.nanmin(bands_in))
        rrs_max = float(np.nanmax(bands_in))
        steps += [
            f'Rrs range: [{rrs_min:.5f}, {rrs_max:.5f}]',
            'Bands: ' + ', '.join(band_names),
            'GLORIA Rrs typical: [0.0001, 0.05]',
        ]

        send_notification(
            f'ACOLITE: Rrs [{rrs_min:.5f}, {rrs_max:.5f}] — {count} bands',
            progress=1.0, notif_id=_NOTIF,
        )

        geo_out = {
            'bands':     bands_in,
            'count':     count,
            'crs':       geo.get('crs'),
            'transform': geo.get('transform'),
        }

        info = _info_panel(steps, w=460, h=220, title='ACOLITE Correction (simplified)')
        hist = _band_histogram(bands_in, band_names)

        # Composite: info top, histogram bottom
        if hist.shape[1] != info.shape[1]:
            hist = cv2.resize(hist, (info.shape[1], hist.shape[0]))
        preview = np.vstack([info, hist])

        return {
            'geotiff': geo_out,
            'preview': preview,
            'rrs_min': rrs_min,
            'rrs_max': rrs_max,
        }
