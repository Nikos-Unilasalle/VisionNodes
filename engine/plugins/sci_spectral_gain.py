from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_spectral_gain',
    label='Spectral Gain',
    category=['analysis', 'scientific'],
    icon='Sliders',
    description="3-band frequency equalizer on raw spectral magnitude. Boost or cut low/mid/high spatial frequencies. Connect FFT.magnitude_raw → SpectralGain → IFFT.magnitude_raw.",
    inputs=[
        {'id': 'magnitude_raw', 'color': 'data'}
    ],
    outputs=[
        {'id': 'magnitude_raw', 'color': 'data',  'label': 'Magnitude (raw)'},
        {'id': 'preview',       'color': 'image', 'label': 'Spectrum Preview'},
    ],
    params=[
        {'id': 'low_gain',       'label': 'Low Freq %',     'type': 'int', 'min': 0, 'max': 400, 'step': 1, 'default': 100},
        {'id': 'mid_gain',       'label': 'Mid Freq %',     'type': 'int', 'min': 0, 'max': 400, 'step': 1, 'default': 100},
        {'id': 'high_gain',      'label': 'High Freq %',    'type': 'int', 'min': 0, 'max': 400, 'step': 1, 'default': 100},
        {'id': 'low_mid_split',  'label': 'Low/Mid split %','type': 'int', 'min': 1, 'max': 98,  'step': 1, 'default': 15},
        {'id': 'mid_high_split', 'label': 'Mid/High split %','type': 'int','min': 2, 'max': 99,  'step': 1, 'default': 50},
    ]
)
class SpectralGainNode(NodeProcessor):
    def process(self, inputs, params):
        mag_raw = inputs.get('magnitude_raw')
        if mag_raw is None:
            return {'magnitude_raw': None, 'preview': None}

        channels = mag_raw.get('channels', [])
        is_color = mag_raw.get('is_color', False)
        if not channels:
            return {'magnitude_raw': None, 'preview': None}

        low_gain  = int(params.get('low_gain',  100)) / 100.0
        mid_gain  = int(params.get('mid_gain',  100)) / 100.0
        high_gain = int(params.get('high_gain', 100)) / 100.0
        lm = int(params.get('low_mid_split',  15)) / 100.0
        mh = int(params.get('mid_high_split', 50)) / 100.0
        if lm >= mh:
            mh = min(lm + 0.01, 1.0)

        rows, cols = channels[0].shape
        crow, ccol = rows // 2, cols // 2
        diag = np.sqrt(rows**2 + cols**2) / 2.0

        # Normalized radial distance from DC (center): 0 = DC, 1 = corner
        y_idx, x_idx = np.ogrid[:rows, :cols]
        dist = np.sqrt((x_idx - ccol)**2 + (y_idx - crow)**2) / diag

        # 3-band piecewise gain mask
        gain_map = np.where(dist <= lm, low_gain,
                   np.where(dist <= mh, mid_gain, high_gain))

        boosted = [ch * gain_map for ch in channels]

        # Spectrum preview: log-scale → colormap
        mag_vis = np.log(boosted[0] + 1) if boosted else None
        if mag_vis is not None:
            cv2.normalize(mag_vis, mag_vis, 0, 255, cv2.NORM_MINMAX)
            preview = cv2.applyColorMap(mag_vis.astype(np.uint8), cv2.COLORMAP_INFERNO)
        else:
            preview = None

        return {
            'magnitude_raw': {'channels': boosted, 'is_color': is_color},
            'preview': preview
        }
