import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='util_mask_band',
    label='Mask Band',
    category='mask',
    icon='AlignCenter',
    description=(
        'Extracts a band (start% → end%) from an image and/or mask along H or V axis. '
        'Values outside the band are zeroed. Use to isolate longitudinal zones.'
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    params=[
        {'id': 'start_pct', 'label': 'Start %', 'type': 'float', 'default': 0,
         'min': 0, 'max': 100},
        {'id': 'end_pct',   'label': 'End %',   'type': 'float', 'default': 50,
         'min': 0, 'max': 100},
        {'id': 'axis', 'label': 'Axis', 'type': 'enum', 'default': 0,
         'options': ['Horizontal (rows)', 'Vertical (cols)']},
    ],
)
class MaskBandNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        mask  = inputs.get('mask')

        src = image if image is not None else mask
        if src is None:
            return {}

        H, W  = src.shape[:2]
        start = float(params.get('start_pct', 0))
        end   = float(params.get('end_pct',   50))
        axis  = int(params.get('axis', 0))

        if axis == 0:
            a = max(0, int(H * start / 100))
            b = max(a, min(H, int(H * end / 100)))
        else:
            a = max(0, int(W * start / 100))
            b = max(a, min(W, int(W * end / 100)))

        def extract(img):
            out = np.zeros_like(img)
            if axis == 0:
                out[a:b] = img[a:b]
            else:
                out[:, a:b] = img[:, a:b]
            return out

        return {
            'image': extract(image) if image is not None else None,
            'mask':  extract(mask)  if mask  is not None else None,
        }
