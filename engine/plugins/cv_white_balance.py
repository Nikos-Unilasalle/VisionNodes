"""
White Balance Node
==================
Corrects the color cast of an image using classic photometric assumptions.

Methods:
  - Gray World : assumes the average of the scene is neutral gray. Each channel
                 is scaled so its mean matches the global gray mean.
  - White Patch: assumes the brightest pixels are white. Per channel, the value
                 at the given percentile is mapped to 255.
  - Manual     : interactive temperature/tint controls. 'temp' shifts red vs blue
                 (warm/cool), 'tint' shifts green vs magenta.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_white_balance',
    label='White Balance',
    category='color',
    icon='Sun',
    description=(
        "Correct color cast. Gray World scales channels to a common gray mean; "
        "White Patch maps the top-percentile brightness to white; Manual applies "
        "temperature (R/B) and tint (G/M) gains."
    ),
    inputs=[
        {'id': 'image', 'label': 'Input', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Balanced', 'color': 'image'},
        {'id': 'data', 'label': 'Data', 'color': 'dict'},
    ],
    params=[
        {'id': 'method', 'label': 'Method', 'type': 'enum',
         'options': ['Gray World', 'White Patch', 'Manual'], 'default': 'Gray World'},
        {'id': 'temp', 'label': 'Temperature', 'type': 'float',
         'min': -100.0, 'max': 100.0, 'default': 0.0},
        {'id': 'tint', 'label': 'Tint', 'type': 'float',
         'min': -100.0, 'max': 100.0, 'default': 0.0},
        {'id': 'percentile', 'label': 'White Percentile', 'type': 'float',
         'min': 90.0, 'max': 100.0, 'default': 99.0},
    ],
)
class WhiteBalanceNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        method = params.get('method', 'Gray World')

        # Work in float for the channel math. OpenCV order is B, G, R.
        f = img.astype(np.float32)
        b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]

        if method == 'Gray World':
            mean_b = float(b.mean()) + 1e-6
            mean_g = float(g.mean()) + 1e-6
            mean_r = float(r.mean()) + 1e-6
            gray = (mean_b + mean_g + mean_r) / 3.0
            gain_b = gray / mean_b
            gain_g = gray / mean_g
            gain_r = gray / mean_r

        elif method == 'White Patch':
            p = float(params.get('percentile', 99.0))
            p = max(90.0, min(100.0, p))
            ref_b = float(np.percentile(b, p)) + 1e-6
            ref_g = float(np.percentile(g, p)) + 1e-6
            ref_r = float(np.percentile(r, p)) + 1e-6
            gain_b = 255.0 / ref_b
            gain_g = 255.0 / ref_g
            gain_r = 255.0 / ref_r

        else:  # Manual
            temp = float(params.get('temp', 0.0)) / 100.0   # -1..1
            tint = float(params.get('tint', 0.0)) / 100.0   # -1..1
            # temp > 0 -> warmer: boost R, lower B.
            gain_r = 1.0 + 0.5 * temp
            gain_b = 1.0 - 0.5 * temp
            # tint > 0 -> magenta (boost R & B, lower G); tint < 0 -> green.
            gain_g = 1.0 - 0.5 * tint
            gain_r = gain_r * (1.0 + 0.25 * tint)
            gain_b = gain_b * (1.0 + 0.25 * tint)

        f[:, :, 0] = b * gain_b
        f[:, :, 1] = g * gain_g
        f[:, :, 2] = r * gain_r

        result = np.clip(f, 0, 255).astype(np.uint8)

        return {
            'main': result,
            'data': {
                'method': method,
                'channel_gains': [round(gain_b, 4), round(gain_g, 4), round(gain_r, 4)],
            },
        }
