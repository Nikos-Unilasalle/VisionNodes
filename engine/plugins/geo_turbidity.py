"""
Sentinel-2 marine turbidity pipeline nodes.

Pipeline order:
  geo_s2_loader → geo_dn_normalize → geo_water_mask_mndwi
  → geo_deglint → geo_turbidity_nechad → geo_geotiff_writer
"""

from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import base64


def _ck(geo, params, mask=None):
    """Cache key: identity of input bands array + frozen params + optional mask id."""
    return (id(geo['bands']), id(mask), str(sorted(params.items())))


_DISPLAY_MAX_PX = 1024

def _disp(img):
    """Downscale image for WebSocket display (max 1024px). Full-res stays in geotiff output."""
    if img is None:
        return img
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= _DISPLAY_MAX_PX:
        return img
    scale = _DISPLAY_MAX_PX / m
    return cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))),
                      interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# 1. DN → Reflectance
# ---------------------------------------------------------------------------

@vision_node(
    type_id='geo_dn_normalize',
    label='DN → Reflectance',
    category='geography',
    icon='Divide',
    description=(
        "Convert Sentinel-2 Digital Numbers to Bottom-of-Atmosphere reflectance "
        "by dividing by the quantification value (default 10 000 for L2A products)."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'Reflectance [0–1]'}],
    params=[
        {'id': 'quantification', 'type': 'int',   'default': 10000, 'min': 1, 'max': 65535,
         'label': 'Quantification Value'},
        {'id': 'offset',         'type': 'int',   'default': 0, 'min': -10000, 'max': 0,
         'label': 'DN Offset (PB≥4.0: −1000)'},
        {'id': 'clamp',          'type': 'bool',  'default': True, 'label': 'Clamp [0,1]'},
    ]
)
class DnNormalizeNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'geotiff': None}
        ck = _ck(geo, params)
        if ck == self._ck:
            return self._co

        q      = max(1, int(params.get('quantification', 10000)))
        offset = int(params.get('offset', 0))
        h, w   = geo['bands'].shape[1], geo['bands'].shape[2]
        send_notification(f'DN→Réflectance: (DN + {offset}) / {q}  ({w}×{h})…', progress=0.3, notif_id='dn_norm')
        bands = (geo['bands'].astype(np.float32) + offset) / q
        if params.get('clamp', True):
            bands = np.clip(bands, 0.0, 1.0)
        send_notification(f'DN→Réflectance: OK  B4 eau typique [{bands[1].mean():.4f}]', progress=1.0, notif_id='dn_norm')

        self._co = {'geotiff': {**geo, 'bands': bands, 'dtype': 'float32'}}
        self._ck = ck
        return self._co


# ---------------------------------------------------------------------------
# 2. Water Mask (MNDWI + erosion)
# ---------------------------------------------------------------------------

@vision_node(
    type_id='geo_water_mask_mndwi',
    label='Water Mask (MNDWI)',
    category='geography',
    icon='Waves',
    description=(
        "Compute MNDWI = (Green − SWIR) / (Green + SWIR), threshold to isolate water, "
        "then erode edges to remove mixed land/sea pixels. "
        "Band indices reference the geotiff band order (1-based). "
        "For geo_s2_loader output: Green=B3→band 1, SWIR=B11→band 4."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[
        {'id': 'mask',    'color': 'mask',   'label': 'Water Mask'},
        {'id': 'mndwi',   'color': 'image',  'label': 'MNDWI Map'},
        {'id': 'geotiff', 'color': 'geotiff','label': 'GeoTIFF (pass-through)'},
    ],
    params=[
        {'id': 'green_band', 'type': 'int',   'default': 1,   'min': 1, 'max': 20, 'label': 'Green Band (B3)'},
        {'id': 'swir_band',  'type': 'int',   'default': 4,   'min': 1, 'max': 20, 'label': 'SWIR Band (B11)'},
        {'id': 'threshold',  'type': 'float', 'default': 0.0, 'min': -1.0, 'max': 1.0, 'label': 'Threshold (>N = water)'},
        {'id': 'erode_size', 'type': 'int',   'default': 3,   'min': 0, 'max': 15,  'label': 'Erode Kernel (px)'},
        {'id': 'scl_band',   'type': 'int',   'default': 0,   'min': 0, 'max': 20,  'label': 'SCL Band index (0=off)'},
    ]
)
class WaterMaskMndwiNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'mask': None, 'mndwi': None, 'geotiff': None}
        ck = _ck(geo, params)
        if ck == self._ck:
            return self._co

        bands = geo['bands']
        count = geo['count']
        eps   = 1e-10
        h, w  = bands.shape[1], bands.shape[2]

        send_notification(f'Masque eau: calcul MNDWI ({w}×{h})…', progress=0.2, notif_id='water_mask')

        g_idx = min(max(int(params.get('green_band', 1)), 1), count) - 1
        s_idx = min(max(int(params.get('swir_band',  4)), 1), count) - 1

        green = bands[g_idx].astype(np.float32)
        swir  = bands[s_idx].astype(np.float32)

        mndwi = (green - swir) / (green + swir + eps)
        send_notification('Masque eau: seuillage…', progress=0.5, notif_id='water_mask')

        thresh    = float(params.get('threshold', 0.0))
        water_bin = (mndwi > thresh).astype(np.uint8)

        erode_sz = int(params.get('erode_size', 3))
        if erode_sz > 0:
            send_notification(f'Masque eau: érosion morphologique {erode_sz}×{erode_sz}…', progress=0.7, notif_id='water_mask')
            kernel    = cv2.getStructuringElement(cv2.MORPH_RECT, (erode_sz, erode_sz))
            water_bin = cv2.erode(water_bin, kernel, iterations=1)

        # SCL cloud masking (classes 3=shadow, 8=cloud med, 9=cloud high, 10=cirrus)
        scl_idx = int(params.get('scl_band', 0))
        if scl_idx > 0 and scl_idx <= count:
            send_notification('Masque eau: exclusion nuages SCL…', progress=0.8, notif_id='water_mask')
            scl = bands[scl_idx - 1].astype(np.uint8)
            cloud_px = np.isin(scl, [3, 8, 9, 10])
            water_bin[cloud_px] = 0
            n_cloud = int(cloud_px.sum())
            send_notification(f'Masque eau: {n_cloud:,} px nuages exclus', progress=0.85, notif_id='water_mask')

        mask       = water_bin * 255
        water_pct  = float(np.count_nonzero(mask)) / mask.size * 100.0
        send_notification(f'Masque eau: OK — {water_pct:.1f}% eau valide', progress=0.9, notif_id='water_mask')

        # Colorized MNDWI map (blue=water, land=grey)
        mndwi_u8    = ((mndwi + 1.0) / 2.0 * 255.0).clip(0, 255).astype(np.uint8)
        mndwi_color = cv2.applyColorMap(mndwi_u8, cv2.COLORMAP_OCEAN)
        send_notification('Masque eau: OK', progress=1.0, notif_id='water_mask')

        self._co = {'mask': mask, 'mndwi': _disp(mndwi_color), 'geotiff': geo}
        self._ck = ck
        return self._co


# ---------------------------------------------------------------------------
# 3. Deglint Correction
# ---------------------------------------------------------------------------

@vision_node(
    type_id='geo_deglint',
    label='Deglint',
    category='geography',
    icon='Sparkles',
    description=(
        "Remove sun-glint from visible bands using NIR as a glint proxy. "
        "NIR is fully absorbed by pure water — any residual signal is glint. "
        "Mode Auto: computes per-band regression coefficient k over dark water pixels. "
        "Mode Fixed: uses the k param directly. "
        "Formula: corrected = max(0, visible − k × (NIR − NIR_min))."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff'},
        {'id': 'mask',    'color': 'mask',   'label': 'Water Mask (opt)'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Deglinted'},
        {'id': 'preview', 'color': 'image',   'label': 'Preview'},
    ],
    params=[
        {'id': 'nir_band',   'type': 'int',   'default': 3,    'min': 1, 'max': 20, 'label': 'NIR Band (B8)'},
        {'id': 'vis_bands',  'type': 'string','default': '1,2', 'label': 'Visible Bands (B3,B4) comma list'},
        {'id': 'mode',       'type': 'enum',  'options': ['Auto (regression)', 'Fixed k'], 'default': 'Auto (regression)', 'label': 'Mode'},
        {'id': 'k_fixed',    'type': 'float', 'default': 1.0,  'min': 0.0, 'max': 5.0, 'label': 'k (Fixed mode)'},
        {'id': 'percentile', 'type': 'int',   'default': 10,   'min': 1, 'max': 50, 'label': 'Dark water percentile (Auto)'},
    ]
)
class DeglintNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        geo  = inputs.get('geotiff')
        if geo is None:
            return {'geotiff': None, 'preview': None}
        mask = inputs.get('mask')
        ck   = _ck(geo, params, mask)
        if ck == self._ck:
            return self._co

        bands  = geo['bands'].copy().astype(np.float32)
        count  = geo['count']
        h, w   = bands.shape[1], bands.shape[2]

        send_notification(f'Déglint: analyse NIR ({w}×{h})…', progress=0.1, notif_id='deglint')

        nir_idx = min(max(int(params.get('nir_band', 3)), 1), count) - 1
        nir     = bands[nir_idx]

        try:
            vis_indices = [min(max(int(x.strip()), 1), count) - 1
                           for x in str(params.get('vis_bands', '1,2')).split(',') if x.strip()]
        except ValueError:
            vis_indices = [0, 1]

        # Build pixel selection: water mask if available, else all pixels
        if mask is not None:
            m = mask[:nir.shape[0], :nir.shape[1]]
            if m.ndim == 3:
                m = m[:, :, 0]
            water_pixels = (m > 127)
        else:
            water_pixels = np.ones(nir.shape, dtype=bool)

        mode     = params.get('mode', 'Auto (regression)')
        use_auto = isinstance(mode, int) and mode == 0 or (isinstance(mode, str) and 'Auto' in mode)

        send_notification('Déglint: calcul NIR min (pixels eau profonde)…', progress=0.3, notif_id='deglint')
        nir_min = float(np.percentile(nir[water_pixels], int(params.get('percentile', 10))))
        nir_adj = np.maximum(0.0, nir - nir_min)

        for i, v_idx in enumerate(vis_indices):
            vis     = bands[v_idx]
            b_label = f'bande {v_idx + 1}'
            if use_auto:
                send_notification(f'Déglint: régression NIR↔{b_label}…', progress=0.4 + i * 0.2, notif_id='deglint')
                nir_flat = nir[water_pixels].ravel()
                vis_flat = vis[water_pixels].ravel()
                if len(nir_flat) > 10 and nir_flat.std() > 1e-8:
                    k = float(np.cov(vis_flat, nir_flat)[0, 1] / (nir_flat.var() + 1e-10))
                    k = max(0.0, k)
                else:
                    k = 1.0
                send_notification(f'Déglint: {b_label} k={k:.3f} — correction…', progress=0.5 + i * 0.2, notif_id='deglint')
            else:
                k = float(params.get('k_fixed', 1.0))
                send_notification(f'Déglint: {b_label} k={k:.2f} (fixe)…', progress=0.5 + i * 0.2, notif_id='deglint')
            bands[v_idx] = np.maximum(0.0, vis - k * nir_adj)

        send_notification('Déglint: rendu aperçu…', progress=0.9, notif_id='deglint')

        def _stretch(b):
            p2, p98 = np.percentile(b[b > 0], (2, 98)) if np.any(b > 0) else (0, 1)
            return np.clip((b - p2) / max(p98 - p2, 1e-8) * 255, 0, 255).astype(np.uint8)

        r = _stretch(bands[min(1, count - 1)])
        g = _stretch(bands[0])
        preview = cv2.merge([g, g, r])

        send_notification('Déglint: OK', progress=1.0, notif_id='deglint')
        self._co = {'geotiff': {**geo, 'bands': bands}, 'preview': _disp(preview)}
        self._ck = ck
        return self._co


# ---------------------------------------------------------------------------
# 4. Nechad / Dogliotti Turbidity
# ---------------------------------------------------------------------------

# Nechad 2010 calibration constants for Sentinel-2 equivalent bands
_PRESETS = {
    'Nechad 2010 – Red (B4, 665nm)':  {'A': 228.1,  'B': 0.1641, 'C': 0.1724},
    'Nechad 2010 – NIR (B8, 865nm)':  {'A': 3078.9, 'B': 0.1568, 'C': 0.2115},
    'Dogliotti 2015 – Red (B4)':       {'A': 228.1,  'B': 0.1641, 'C': 0.1724},
    'Custom':                          {'A': 228.1,  'B': 0.1641, 'C': 0.1724},
}
_PRESET_NAMES = list(_PRESETS.keys())


def _turbidity_ntu_lut():
    """Custom LUT (256, 3) BGR: deep blue (0 NTU) → cyan (5) → yellow (15) → brown (50+)."""
    lut = np.zeros((256, 3), dtype=np.uint8)
    # stops: (index_0_255, [B, G, R])
    stops = [
        (0,   [120,  20,   5]),   # deep blue
        (51,  [160, 140,  10]),   # cyan-green
        (128, [ 40, 210, 200]),   # yellow-green
        (204, [ 20, 100, 180]),   # amber
        (255, [ 10,  40, 100]),   # dark brown
    ]
    for i in range(256):
        for j in range(len(stops) - 1):
            v0, c0 = stops[j]
            v1, c1 = stops[j + 1]
            if v0 <= i <= v1:
                t = (i - v0) / max(v1 - v0, 1)
                lut[i] = [int(c0[k] + t * (c1[k] - c0[k])) for k in range(3)]
                break
    return lut


_TURB_LUT = _turbidity_ntu_lut()


@vision_node(
    type_id='geo_turbidity_nechad',
    label='Turbidity (Nechad)',
    category='geography',
    icon='Droplets',
    description=(
        "Apply Nechad (2010) bio-optical model to convert water-leaving reflectance to NTU. "
        "Formula: T = (A × ρw) / (1 − ρw/C) + B. "
        "ρw is the reflectance of the selected band (B4 red or B8 NIR). "
        "Connect the water mask to restrict processing to ocean pixels. "
        "A, B, C constants are sensor/band specific — use presets or set Custom."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff'},
        {'id': 'mask',    'color': 'mask',   'label': 'Water Mask (opt)'},
    ],
    outputs=[
        {'id': 'turbidity', 'color': 'geotiff', 'label': 'Turbidity (NTU)'},
        {'id': 'colormap',  'color': 'image',   'label': 'Colormap (NTU)'},
        {'id': 'stats',     'color': 'dict',    'label': 'Stats (NTU)'},
    ],
    params=[
        {'id': 'preset',   'type': 'enum',  'options': _PRESET_NAMES, 'default': _PRESET_NAMES[0], 'label': 'Preset'},
        {'id': 'red_band', 'type': 'int',   'default': 2,    'min': 1, 'max': 20,  'label': 'Band index (B4=2 for S2 loader)'},
        {'id': 'A',        'type': 'float', 'default': 228.1, 'min': 0.0, 'max': 10000.0, 'label': 'A (Custom)'},
        {'id': 'B',        'type': 'float', 'default': 0.1641, 'min': 0.0, 'max': 10.0,   'label': 'B (Custom)'},
        {'id': 'C',        'type': 'float', 'default': 0.1724, 'min': 0.001, 'max': 1.0,  'label': 'C (Custom)'},
        {'id': 'max_ntu',  'type': 'float', 'default': 50.0,  'min': 1.0, 'max': 1000.0, 'label': 'Max NTU (colormap ceiling)'},
        {'id': 'gaussian', 'type': 'int',   'default': 3,    'min': 0, 'max': 15, 'label': 'Gaussian smooth (px, 0=off)'},
    ]
)
class TurbidityNechadNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        geo  = inputs.get('geotiff')
        if geo is None:
            return {'turbidity': None, 'colormap': None, 'stats': None}
        mask = inputs.get('mask')
        ck   = _ck(geo, params, mask)
        if ck == self._ck:
            return self._co

        bands = geo['bands'].astype(np.float32)
        count = geo['count']
        h_img, w_img = bands.shape[1], bands.shape[2]

        send_notification(f'Nechad: lecture bandes ({w_img}×{h_img})…', progress=0.05, notif_id='turbidity')

        # Resolve calibration constants
        preset_name = params.get('preset', _PRESET_NAMES[0])
        if isinstance(preset_name, int):
            preset_name = _PRESET_NAMES[min(preset_name, len(_PRESET_NAMES) - 1)]

        if 'Custom' in str(preset_name):
            A = float(params.get('A', 228.1))
            B = float(params.get('B', 0.1641))
            C = float(params.get('C', 0.1724))
        else:
            consts = _PRESETS.get(preset_name, _PRESETS[_PRESET_NAMES[0]])
            A, B, C = consts['A'], consts['B'], consts['C']

        send_notification(f'Nechad: modèle {preset_name}  A={A} B={B} C={C}…', progress=0.15, notif_id='turbidity')

        b_idx = min(max(int(params.get('red_band', 2)), 1), count) - 1
        rho_w = bands[b_idx].copy()
        rho_w = np.clip(rho_w, 0.0, C * 0.999)

        send_notification('Nechad: calcul NTU = (A×ρw)/(1−ρw/C) + B…', progress=0.35, notif_id='turbidity')
        turb = (A * rho_w) / (1.0 - rho_w / C) + B
        turb = np.maximum(0.0, turb)

        # Land mask
        if mask is not None:
            m = mask[:turb.shape[0], :turb.shape[1]]
            if m.ndim == 3:
                m = m[:, :, 0]
            land_mask = ~(m > 127)
        else:
            land_mask = np.zeros(turb.shape, dtype=bool)

        # Smoothing
        smooth_px = int(params.get('gaussian', 3))
        if smooth_px > 1:
            ksize = smooth_px | 1
            send_notification(f'Nechad: lissage gaussien {ksize}×{ksize}…', progress=0.55, notif_id='turbidity')
            turb = cv2.GaussianBlur(turb, (ksize, ksize), 0)

        send_notification('Nechad: statistiques eau…', progress=0.70, notif_id='turbidity')
        water_vals = turb[~land_mask]
        stats = {}
        if water_vals.size > 0:
            stats = {
                'mean_ntu':   float(np.mean(water_vals)),
                'median_ntu': float(np.median(water_vals)),
                'p90_ntu':    float(np.percentile(water_vals, 90)),
                'max_ntu':    float(np.max(water_vals)),
                'water_px':   int(water_vals.size),
            }

        send_notification('Nechad: application colormap NTU…', progress=0.82, notif_id='turbidity')
        max_ntu   = float(params.get('max_ntu', 50.0))
        turb_disp = turb.copy()
        turb_disp[land_mask] = 0.0
        normalized = (turb_disp / max_ntu * 255.0).clip(0, 255).astype(np.uint8)
        colormap   = _TURB_LUT[normalized]
        colormap   = colormap.copy()
        colormap[land_mask] = [10, 10, 10]

        send_notification('Nechad: génération miniature…', progress=0.92, notif_id='turbidity')
        h, w = colormap.shape[:2]
        sc   = 120 / h
        thumb = cv2.resize(colormap, (max(1, int(w * sc)), 120))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        mean_str = f'{stats["mean_ntu"]:.1f}' if stats else '—'
        send_notification(f'Nechad: OK — moyenne {mean_str} NTU ({water_vals.size:,} px eau)', progress=1.0, notif_id='turbidity')

        turb_geo = {
            **geo,
            'bands':      turb[np.newaxis].astype(np.float32),
            'count':      1,
            'band_names': ['turbidity_NTU'],
            'dtype':      'float32',
        }

        self._co = {
            'turbidity': turb_geo,
            'colormap':  _disp(colormap),
            'stats':     stats,
            '_thumb':    thumb_b64,
        }
        self._ck = ck
        return self._co


# ---------------------------------------------------------------------------
# 5. Turbidity Statistics
# ---------------------------------------------------------------------------

# WFD-inspired turbidity classes (NTU boundaries, BGR colors)
_TURB_CLASSES = [
    ('Cristal (0–1)',      0,    1,   (180, 120,  10)),  # gold
    ('Clair (1–5)',        1,    5,   (200, 180,   0)),  # cyan-yellow
    ('Légèrement turbide', 5,   15,   (120, 200,  40)),  # green-yellow
    ('Turbide',           15,   50,   ( 20, 140, 200)),  # orange
    ('Très turbide',      50,  200,   ( 10,  60, 180)),  # dark orange
    ('Extrêmement turbide',200, 1e9,  ( 10,  20, 140)),  # dark red
]


def _render_stats_card(stats, w=380, h=300):
    """Render a colored stats panel as BGR image for node thumbnail."""
    bg    = np.full((h, w, 3), (18, 18, 28), dtype=np.uint8)
    WHITE = (230, 230, 230)
    GRAY  = (130, 130, 130)
    CYAN  = (200, 200,  40)

    font  = cv2.FONT_HERSHEY_SIMPLEX
    fontS = cv2.FONT_HERSHEY_PLAIN

    # Header
    cv2.rectangle(bg, (0, 0), (w, 28), (35, 28, 20), -1)
    cv2.putText(bg, 'TURBIDITE  NTU', (8, 19), font, 0.48, CYAN, 1, cv2.LINE_AA)
    area  = stats.get('area_km2', 0)
    cv2.putText(bg, f'{area:.1f} km2', (w - 85, 19), fontS, 1.0, GRAY, 1)

    # Key metrics with colored bars
    metrics = [
        ('Moyenne',  stats.get('mean',   0), (120, 180,  80)),
        ('Mediane',  stats.get('median', 0), (100, 160,  60)),
        ('P90',      stats.get('p90',    0), ( 40, 140, 200)),
        ('Max',      stats.get('max',    0), ( 20,  60, 180)),
    ]
    max_val = max((m[1] for m in metrics), default=1.0) or 1.0
    bar_area_w = w - 130

    y = 42
    for label, val, color in metrics:
        cv2.putText(bg, label, (8, y + 10), fontS, 1.0, GRAY, 1)
        bar_len = int(val / max_val * bar_area_w)
        cv2.rectangle(bg, (90, y), (90 + bar_len, y + 13), color, -1)
        cv2.rectangle(bg, (90, y), (90 + bar_area_w, y + 13), (60, 60, 60), 1)
        cv2.putText(bg, f'{val:.1f}', (96 + bar_len, y + 11), fontS, 0.95, WHITE, 1)
        y += 20

    # Separator
    cv2.line(bg, (8, y + 4), (w - 8, y + 4), (50, 50, 60), 1)
    y += 14

    # Classes
    cv2.putText(bg, 'CLASSES', (8, y + 8), fontS, 0.9, GRAY, 1)
    y += 16

    classes = stats.get('classes', {})
    total_px = sum(v.get('pixels', 0) for v in classes.values()) or 1

    for cls_label, lo, hi, bgr in _TURB_CLASSES:
        cls_data = classes.get(cls_label)
        if cls_data is None:
            continue
        pct = cls_data.get('pct', 0)
        if pct < 0.5:
            continue

        # color dot
        cv2.circle(bg, (14, y + 5), 5, bgr, -1)
        # short label
        short = cls_label.split('(')[0].strip()[:18]
        cv2.putText(bg, short, (24, y + 10), fontS, 0.85, WHITE, 1)
        # bar
        bar_x = 200
        bar_len = int(pct / 100 * (w - bar_x - 12))
        cv2.rectangle(bg, (bar_x, y), (bar_x + bar_len, y + 11), bgr, -1)
        cv2.putText(bg, f'{pct:.1f}%', (bar_x + bar_len + 4, y + 10), fontS, 0.85, GRAY, 1)
        y += 16
        if y > h - 10:
            break

    return bg


def _turb_histogram(vals, max_ntu, bins=64, w=480, h=220):
    """Render a NTU histogram as BGR image."""
    img   = np.full((h, w, 3), 20, dtype=np.uint8)
    if vals.size == 0:
        return img

    cap    = min(float(np.percentile(vals, 99.5)), max_ntu)
    edges  = np.linspace(0, cap, bins + 1)
    counts, _ = np.histogram(vals, bins=edges)
    if counts.max() == 0:
        return img

    bar_w  = max(1, (w - 40) // bins)
    scale  = (h - 40) / counts.max()

    for i, c in enumerate(counts):
        x0  = 20 + i * bar_w
        y0  = h - 20 - int(c * scale)
        ntu = (edges[i] + edges[i + 1]) / 2
        # pick color from turbidity class
        color = (40, 120, 180)
        for _, lo, hi, col in _TURB_CLASSES:
            if lo <= ntu < hi:
                color = col
                break
        cv2.rectangle(img, (x0, y0), (x0 + bar_w - 1, h - 20), color, -1)

    # axes
    cv2.line(img, (20, 20), (20, h - 20), (180, 180, 180), 1)
    cv2.line(img, (20, h - 20), (w - 10, h - 20), (180, 180, 180), 1)

    # x labels
    for v in [0, cap * 0.25, cap * 0.5, cap * 0.75, cap]:
        x = int(20 + (v / cap) * (w - 40))
        cv2.putText(img, f'{v:.0f}', (max(0, x - 12), h - 5),
                    cv2.FONT_HERSHEY_PLAIN, 0.8, (180, 180, 180), 1)

    cv2.putText(img, 'NTU', (w // 2 - 10, h - 1),
                cv2.FONT_HERSHEY_PLAIN, 0.9, (220, 220, 220), 1)
    return img


@vision_node(
    type_id='geo_turbidity_stats',
    label='Turbidity Statistics',
    category='geography',
    icon='BarChart2',
    description=(
        "Full statistical analysis of a turbidity (NTU) map. "
        "Outputs percentile profile, classification by WFD turbidity class, "
        "surface area per class (km²), NTU histogram and class map. "
        "Connect turbidity geotiff from geo_turbidity_nechad + water mask."
    ),
    inputs=[
        {'id': 'turbidity', 'color': 'geotiff', 'label': 'Turbidity (NTU)'},
        {'id': 'mask',      'color': 'mask',    'label': 'Water Mask (opt)'},
    ],
    outputs=[
        {'id': 'stats',     'color': 'dict',   'label': 'Stats (NTU)'},
        {'id': 'histogram', 'color': 'image',  'label': 'Histogram'},
        {'id': 'class_map', 'color': 'image',  'label': 'Class Map'},
        {'id': 'mean_ntu',  'color': 'scalar', 'label': 'Mean NTU'},
        {'id': 'area_km2',  'color': 'scalar', 'label': 'Water Area (km²)'},
    ],
    params=[
        {'id': 'pixel_m',  'type': 'int',   'default': 10,    'min': 1,    'max': 1000,
         'label': 'Pixel size (m) — S2: 10'},
        {'id': 'max_ntu',  'type': 'float', 'default': 200.0, 'min': 1.0,  'max': 5000.0,
         'label': 'Max NTU (outlier clip)'},
        {'id': 'hist_max', 'type': 'float', 'default': 100.0, 'min': 1.0,  'max': 2000.0,
         'label': 'Histogram X max (NTU)'},
    ]
)
class TurbidityStatsNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        geo  = inputs.get('turbidity')
        if geo is None:
            return {'stats': None, 'histogram': None, 'class_map': None,
                    'mean_ntu': 0.0, 'area_km2': 0.0}
        mask = inputs.get('mask')
        ck   = _ck(geo, params, mask)
        if ck == self._ck:
            return self._co

        turb  = geo['bands'][0].astype(np.float32)
        h_img, w_img = turb.shape

        send_notification(f'Turb Stats: analyse ({w_img}×{h_img})…', progress=0.1, notif_id='turb_stats')

        # Water pixels only
        if mask is not None:
            m = mask[:h_img, :w_img]
            if m.ndim == 3:
                m = m[:, :, 0]
            water = (m > 127)
        else:
            water = (turb > 0)

        vals = turb[water]

        # Clip outliers before stats (keeps area/count on full water mask)
        max_ntu = float(params.get('max_ntu', 200.0))
        vals = vals[vals <= max_ntu]

        # Pixel area
        px_m      = max(1, int(params.get('pixel_m', 10)))
        px_area   = (px_m * px_m) / 1e6   # km²
        area_km2  = float(vals.size * px_area)

        send_notification('Turb Stats: percentiles…', progress=0.3, notif_id='turb_stats')

        if vals.size == 0:
            self._co = {'stats': {}, 'histogram': None, 'class_map': None,
                        'mean_ntu': 0.0, 'area_km2': 0.0}
            self._ck = ck
            return self._co

        stats = {
            'count':      int(vals.size),
            'area_km2':   round(area_km2, 3),
            'mean':       round(float(np.mean(vals)),   3),
            'median':     round(float(np.median(vals)), 3),
            'std':        round(float(np.std(vals)),    3),
            'p10':        round(float(np.percentile(vals, 10)),  3),
            'p25':        round(float(np.percentile(vals, 25)),  3),
            'p75':        round(float(np.percentile(vals, 75)),  3),
            'p90':        round(float(np.percentile(vals, 90)),  3),
            'p95':        round(float(np.percentile(vals, 95)),  3),
            'max':        round(float(np.max(vals)),    3),
        }

        send_notification('Turb Stats: classification WFD…', progress=0.55, notif_id='turb_stats')

        # Classification per class
        classes = {}
        for label, lo, hi, _ in _TURB_CLASSES:
            px = int(np.sum((vals >= lo) & (vals < hi)))
            classes[label] = {
                'pixels':   px,
                'area_km2': round(px * px_area, 4),
                'pct':      round(px / vals.size * 100, 2),
            }
        stats['classes'] = classes

        send_notification('Turb Stats: rendu histogram…', progress=0.70, notif_id='turb_stats')

        hist_max = float(params.get('hist_max', 100.0))
        histogram = _turb_histogram(vals, hist_max)

        send_notification('Turb Stats: rendu class map…', progress=0.85, notif_id='turb_stats')

        # Class map: color each water pixel by turbidity class
        class_img = np.zeros((h_img, w_img, 3), dtype=np.uint8)
        for _, lo, hi, bgr in _TURB_CLASSES:
            px_mask = water & (turb >= lo) & (turb < hi)
            class_img[px_mask] = bgr

        mean_ntu = stats['mean']
        dominant = max(classes.items(), key=lambda x: x[1]['pixels'])[0]
        send_notification(
            f'Turb Stats: OK — moy {mean_ntu:.1f} NTU | {area_km2:.1f} km² | dominant: {dominant}',
            progress=1.0, notif_id='turb_stats'
        )

        card = _render_stats_card(stats)
        _, buf = cv2.imencode('.jpg', card, [cv2.IMWRITE_JPEG_QUALITY, 85])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        self._co = {
            'stats':     stats,
            'histogram': histogram,
            'class_map': _disp(class_img),
            'mean_ntu':  mean_ntu,
            'area_km2':  area_km2,
            '_thumb':    thumb_b64,
        }
        self._ck = ck
        return self._co
