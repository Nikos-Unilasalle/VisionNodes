from registry import vision_node, NodeProcessor
import numpy as np
import cv2


@vision_node(
    type_id='geo_band_selector',
    label='Band Selector',
    category='geo',
    icon='Layers',
    description="Select 3 bands from a GeoTIFF and produce an RGB image for standard CV pipelines.",
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[{'id': 'image', 'color': 'image'}],
    params=[
        {'id': 'r_band',    'type': 'int',  'default': 1,    'min': 1, 'max': 20, 'label': 'R Band'},
        {'id': 'g_band',    'type': 'int',  'default': 2,    'min': 1, 'max': 20, 'label': 'G Band'},
        {'id': 'b_band',    'type': 'int',  'default': 3,    'min': 1, 'max': 20, 'label': 'B Band'},
        {'id': 'stretch',   'type': 'bool', 'default': True,           'label': 'Auto Stretch'},
        {'id': 'percentile','type': 'int',  'default': 2,    'min': 0, 'max': 10, 'label': 'Stretch %'},
    ]
)
class BandSelectorNode(NodeProcessor):
    def _stretch(self, band, pct):
        valid = band[band != 0]
        if valid.size == 0:
            return np.zeros_like(band, dtype=np.uint8)
        p_lo, p_hi = np.percentile(valid, (pct, 100 - pct))
        if p_hi == p_lo:
            return np.zeros_like(band, dtype=np.uint8)
        return np.clip((band - p_lo) / (p_hi - p_lo) * 255, 0, 255).astype(np.uint8)

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'image': None}

        bands   = geo['bands']
        count   = geo['count']
        stretch = bool(params.get('stretch', True))
        pct     = int(params.get('percentile', 2))

        r_idx = min(int(params.get('r_band', 1)), count) - 1
        g_idx = min(int(params.get('g_band', min(2, count))), count) - 1
        b_idx = min(int(params.get('b_band', min(3, count))), count) - 1

        if stretch:
            r = self._stretch(bands[r_idx], pct)
            g = self._stretch(bands[g_idx], pct)
            b = self._stretch(bands[b_idx], pct)
        else:
            r = np.clip(bands[r_idx] / 65535.0 * 255, 0, 255).astype(np.uint8)
            g = np.clip(bands[g_idx] / 65535.0 * 255, 0, 255).astype(np.uint8)
            b = np.clip(bands[b_idx] / 65535.0 * 255, 0, 255).astype(np.uint8)

        return {'image': cv2.merge([b, g, r])}
