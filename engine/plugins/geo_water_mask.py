"""
geo_water_mask.py — Unified water mask node (NDWI or MNDWI).

NDWI  = (Green − NIR)  / (Green + NIR)   [McFeeters 1996]  — 4-band S2 stacks, no SWIR needed.
MNDWI = (Green − SWIR) / (Green + SWIR)  [Xu 2006]         — requires SWIR band, handles urban better.
"""
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'water_mask'


@vision_node(
    type_id='geo_water_mask',
    label='Water Mask',
    category='geography',
    icon='Waves',
    description=(
        "Compute a spectral water index (NDWI or MNDWI) from a multi-band raster, "
        "threshold to a binary water mask, and optionally erode edges. "
        "NDWI uses Green+NIR (no SWIR needed). MNDWI uses Green+SWIR (better in urban areas)."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'Multi-band raster'}],
    outputs=[
        {'id': 'mask',         'color': 'mask',   'label': 'Water mask (255=water)'},
        {'id': 'index_image',  'color': 'image',  'label': 'Index colormap'},
        {'id': 'water_pixels', 'color': 'scalar', 'label': 'Water pixel count'},
        {'id': 'water_pct',    'color': 'scalar', 'label': 'Water coverage %'},
        {'id': 'geotiff',      'color': 'geotiff','label': 'GeoTIFF pass-through'},
    ],
    params=[
        {'id': 'index',      'type': 'enum', 'options': ['NDWI', 'MNDWI'], 'default': 0,
         'label': 'Water index'},
        {'id': 'green_band', 'type': 'int',   'default': 2,   'min': 1, 'max': 20,
         'label': 'Green band (1-based)'},
        {'id': 'nir_band',   'type': 'int',   'default': 4,   'min': 1, 'max': 20,
         'label': 'NIR band (NDWI only)',  'show_if': {'index': 0}},
        {'id': 'swir_band',  'type': 'int',   'default': 4,   'min': 1, 'max': 20,
         'label': 'SWIR band (MNDWI only)', 'show_if': {'index': 1}},
        {'id': 'scl_band',   'type': 'int',   'default': 0,   'min': 0, 'max': 20,
         'label': 'SCL cloud band (0=off)', 'show_if': {'index': 1}},
        {'id': 'threshold',  'type': 'float', 'default': 0.05, 'min': -1.0, 'max': 1.0,
         'label': 'Threshold (>N = water)'},
        {'id': 'erode_px',   'type': 'int',   'default': 2,   'min': 0, 'max': 20,
         'label': 'Erode mask (px, 0=off)'},
    ],
    resizable=True, min_width=280, min_height=180,
)
class WaterMaskNode(NodeProcessor):

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            return {}

        bands = geo['bands'].astype(np.float32)
        if bands.ndim == 2:
            bands = bands[np.newaxis, :, :]
        count, H, W = bands.shape
        eps = 1e-8

        index = int(params.get('index', 0))  # 0=NDWI, 1=MNDWI
        g_idx = min(max(int(params.get('green_band', 2)), 1), count) - 1
        green = bands[g_idx]

        if index == 0:  # NDWI
            n_idx  = min(max(int(params.get('nir_band', 4)), 1), count) - 1
            other  = bands[n_idx]
            label  = f'NDWI  green=#{g_idx+1} nir=#{n_idx+1}'
            index_name = 'NDWI'
        else:           # MNDWI
            s_idx  = min(max(int(params.get('swir_band', 4)), 1), count) - 1
            other  = bands[s_idx]
            label  = f'MNDWI green=#{g_idx+1} swir=#{s_idx+1}'
            index_name = 'MNDWI'

        send_notification(f'Water mask: computing {index_name} ({W}×{H})…', progress=0.2, notif_id=_NOTIF)
        wi = (green - other) / (green + other + eps)

        thresh = float(params.get('threshold', 0.05))
        water  = (wi > thresh).astype(np.uint8)

        # SCL cloud exclusion (MNDWI only, classes 3=shadow, 8/9=cloud, 10=cirrus)
        if index == 1:
            scl_idx = int(params.get('scl_band', 0))
            if 0 < scl_idx <= count:
                send_notification('Water mask: excluding SCL clouds…', progress=0.5, notif_id=_NOTIF)
                scl = bands[scl_idx - 1].astype(np.uint8)
                water[np.isin(scl, [3, 8, 9, 10])] = 0

        erode_px = int(params.get('erode_px', 2))
        if erode_px > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (erode_px * 2 + 1, erode_px * 2 + 1))
            water  = cv2.erode(water, kernel, iterations=1)

        mask        = (water * 255).astype(np.uint8)
        water_count = int(np.count_nonzero(mask))
        water_pct   = water_count / (H * W) * 100.0

        # Colorized index map
        wi_u8   = ((wi + 1.0) / 2.0 * 255.0).clip(0, 255).astype(np.uint8)
        wi_color = cv2.applyColorMap(wi_u8, cv2.COLORMAP_OCEAN)
        contours, _ = cv2.findContours(water, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(wi_color, contours, -1, (0, 255, 255), 1)

        send_notification(
            f'Water mask ({index_name}): {water_pct:.1f}% water ({water_count:,} px)',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'mask':         mask,
            'index_image':  wi_color,
            'water_pixels': float(water_count),
            'water_pct':    water_pct,
            'geotiff':      geo,
        }
