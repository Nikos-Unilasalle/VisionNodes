import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_gamma',
    label='Gamma Correct',
    category='color',
    icon='Sun',
    description=(
        "Applies a gamma power-law to image intensities (ch7 §7.6).\n\n"
        "I_out = I_in ^ gamma   (values normalised to [0, 1])\n\n"
        "gamma < 1  →  brightens midtones (e.g. 0.45 = sRGB encode)\n"
        "gamma = 1  →  identity\n"
        "gamma > 1  →  darkens midtones (e.g. 2.2 = sRGB linearise)\n\n"
        "Use 'Linearise (÷ 2.2)' to decode sRGB before linear-space "
        "operations (blur, colour arithmetic, luminance computation)."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Corrected', 'color': 'image'},
    ],
    params=[
        {'id': 'gamma',     'label': 'Gamma (γ)', 'type': 'float',
         'default': 2.2, 'min': 0.1, 'max': 5.0, 'step': 0.05},
        {'id': 'linearise', 'label': 'Linearise (÷ γ)', 'type': 'bool',
         'default': True},
    ]
)
class GammaCorrectNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        gamma = float(params.get('gamma', 2.2))
        gamma = max(gamma, 0.01)
        linearise = bool(params.get('linearise', True))

        # Normalise to [0,1] float
        f = img.astype(np.float32) / 255.0

        if linearise:
            # Decode: undo stored gamma to recover linear light
            out = np.power(np.clip(f, 0, 1), gamma)
        else:
            # Encode: apply gamma (compress dynamic range)
            out = np.power(np.clip(f, 0, 1), 1.0 / gamma)

        return {'main': (out * 255).clip(0, 255).astype(np.uint8)}
