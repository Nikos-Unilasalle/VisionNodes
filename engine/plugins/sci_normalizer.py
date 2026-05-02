import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_MODES = ['Min-Max → [0,255]', 'Min-Max → [0,1]', 'Z-Score (±3σ)', 'Percentile Clip']

@vision_node(
    type_id='sci_normalizer',
    label='Image Normalizer',
    category=['analysis', 'scientific'],
    icon='Sliders',
    description="Normalize image or data array. Min-Max, Z-Score, or percentile stretch. Essential preprocessing for scientific imaging.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Normalized (uint8)'},
        {'id': 'data', 'color': 'data',  'label': 'Normalized (float 0-1)'},
    ],
    params=[
        {'id': 'mode',   'label': 'Mode',       'type': 'enum',  'options': _MODES, 'default': 0},
        {'id': 'p_low',  'label': 'Low %tile',  'type': 'float', 'default': 2.0,  'min': 0.0,  'max': 49.9},
        {'id': 'p_high', 'label': 'High %tile', 'type': 'float', 'default': 98.0, 'min': 50.1, 'max': 100.0},
    ]
)
class NormalizerNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'data': None}

        mode = int(params.get('mode', 0))
        src  = img.astype(np.float32)

        if mode in (0, 1):  # Min-Max
            lo, hi = float(src.min()), float(src.max())
            norm = np.zeros_like(src) if hi == lo else (src - lo) / (hi - lo)
        elif mode == 2:     # Z-Score clipped to ±3σ → [0,1]
            mean, std = float(src.mean()), float(src.std())
            if std < 1e-8:
                norm = np.zeros_like(src)
            else:
                norm = np.clip((src - mean) / std / 6.0 + 0.5, 0.0, 1.0)
        else:               # Percentile Clip
            lo = float(np.percentile(src, float(params.get('p_low',  2.0))))
            hi = float(np.percentile(src, float(params.get('p_high', 98.0))))
            norm = np.zeros_like(src) if hi <= lo else np.clip((src - lo) / (hi - lo), 0.0, 1.0)

        out_uint8 = (norm * 255).clip(0, 255).astype(np.uint8)
        return {'main': out_uint8, 'data': norm}
