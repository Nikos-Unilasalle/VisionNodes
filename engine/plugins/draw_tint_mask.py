import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='draw_tint_mask',
    label='Tint Mask',
    category='draw',
    icon='Palette',
    description=(
        'Colorizes a region defined by a binary mask over a base image. '
        'The masked area is blended with the chosen color at the given alpha. '
        'Chain multiple Tint Mask nodes to colorize independent zones.'
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
    ],
    params=[
        {'id': 'color', 'label': 'Color', 'type': 'color', 'default': '#00ff88'},
        {'id': 'alpha', 'label': 'Alpha', 'type': 'float',
         'default': 0.5, 'min': 0.0, 'max': 1.0},
    ],
    colorable=True,
)
class TintMaskNode(NodeProcessor):
    def _parse_color(self, hex_str):
        try:
            h = str(hex_str).lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (b, g, r)  # BGR
        except Exception:
            return (0, 255, 136)

    def process(self, inputs, params):
        image = inputs.get('image')
        mask  = inputs.get('mask')

        if image is None:
            return {}

        col   = self._parse_color(params.get('color', '#00ff88'))
        alpha = float(params.get('alpha', 0.5))

        if len(image.shape) == 2:
            vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            vis = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        else:
            vis = image.copy()

        if mask is None:
            return {'main': vis}

        mg = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(mg, 127, 255, cv2.THRESH_BINARY)
        m = binary > 0

        tinted = vis.copy().astype(np.float32)
        for c, cv_val in enumerate(col):
            tinted[:, :, c] = np.where(m,
                tinted[:, :, c] * (1.0 - alpha) + cv_val * alpha,
                tinted[:, :, c])

        return {'main': np.clip(tinted, 0, 255).astype(np.uint8)}
