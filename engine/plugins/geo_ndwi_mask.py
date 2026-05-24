"""
geo_ndwi_mask.py — Compute NDWI-based water mask from a multi-band geotiff.

NDWI = (Green - NIR) / (Green + NIR)   [McFeeters 1996]
Works with any 4-band S2-style raster (Bleu, Vert, Rouge, NIR).
Outputs binary water mask (255=water, 0=land/nodata).
"""
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'ndwi_mask'


def _info_panel(lines: list, w: int = 420, h: int = 160, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
    for i, line in enumerate(lines[:(h - 36) // 15]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:64], (8, 44 + i * 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.37, color, 1, cv2.LINE_AA)
    return img


@vision_node(
    type_id='geo_ndwi_mask',
    label='Water Mask (NDWI)',
    category='geography',
    icon='Waves',
    description=(
        "Compute NDWI = (Green − NIR) / (Green + NIR) from a multi-band raster. "
        "Works with 4-band 10m S2 stacks (no SWIR needed). "
        "Pixels above threshold are classified as water. "
        "Band indices are 1-based (default: Green=2, NIR=4 for Bleu/Vert/Rouge/NIR stack)."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Multi-band raster'},
    ],
    outputs=[
        {'id': 'mask',         'color': 'mask',   'label': 'Water mask (255=water)'},
        {'id': 'ndwi_image',   'color': 'image',  'label': 'NDWI colormap'},
        {'id': 'water_pixels', 'color': 'scalar', 'label': 'Water pixel count'},
        {'id': 'water_pct',    'color': 'scalar', 'label': 'Water coverage %'},
    ],
    params=[
        {'id': 'green_band', 'label': 'Green band index (1-based)', 'type': 'int',   'default': 2, 'min': 1, 'max': 20},
        {'id': 'nir_band',   'label': 'NIR band index (1-based)',   'type': 'int',   'default': 4, 'min': 1, 'max': 20},
        {'id': 'threshold',  'label': 'NDWI threshold (>N = water)','type': 'float', 'default': 0.05, 'min': -1.0, 'max': 1.0},
        {'id': 'erode_px',   'label': 'Erode mask (px, 0=off)',     'type': 'int',   'default': 2, 'min': 0, 'max': 20},
    ],
    resizable=True, min_width=260, min_height=180,
)
class NdwiMaskNode(NodeProcessor):

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            return {}

        bands = geo['bands'].astype(np.float32)
        if bands.ndim == 2:
            bands = bands[np.newaxis, :, :]
        count, H, W = bands.shape

        g_idx = min(max(int(params.get('green_band', 2)), 1), count) - 1
        n_idx = min(max(int(params.get('nir_band',   4)), 1), count) - 1

        green = bands[g_idx]
        nir   = bands[n_idx]

        eps   = 1e-8
        ndwi  = (green - nir) / (green + nir + eps)

        thresh = float(params.get('threshold', 0.05))
        water  = (ndwi > thresh).astype(np.uint8)

        erode_px = int(params.get('erode_px', 2))
        if erode_px > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (erode_px * 2 + 1, erode_px * 2 + 1))
            water  = cv2.erode(water, kernel, iterations=1)

        mask = (water * 255).astype(np.uint8)

        water_count = int(np.count_nonzero(mask))
        water_pct   = water_count / (H * W) * 100.0

        # Colorized NDWI map
        ndwi_norm = ((ndwi + 1.0) / 2.0 * 255.0).clip(0, 255).astype(np.uint8)
        ndwi_color = cv2.applyColorMap(ndwi_norm, cv2.COLORMAP_OCEAN)
        # Overlay water mask boundary
        contours, _ = cv2.findContours(water, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(ndwi_color, contours, -1, (0, 255, 255), 1)

        lines = [
            f'NDWI (Green-NIR)/(Green+NIR)',
            f'Bands: green=#{g_idx+1}, NIR=#{n_idx+1}',
            f'Threshold: > {thresh:.3f}',
            f'Water pixels: {water_count:,} / {H*W:,}',
            f'Coverage: {water_pct:.1f}%',
            f'Erode: {erode_px}px',
        ]
        info = _info_panel(lines, w=ndwi_color.shape[1], h=160, title='Water Mask (NDWI)')
        preview = np.vstack([ndwi_color, info])

        send_notification(
            f'NDWI mask: {water_pct:.1f}% water ({water_count:,} px)',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'mask':         mask,
            'ndwi_image':   preview,
            'water_pixels': float(water_count),
            'water_pct':    water_pct,
        }
