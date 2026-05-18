import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='util_split_half',
    label='Split Half',
    category='mask',
    icon='Columns2',
    description=(
        'Splits an image and/or mask into two halves along H or V axis at a given % position. '
        'Values outside each half are zeroed (spatial positions preserved). '
        'Useful for medial/lateral or anterior/posterior asymmetry analysis.'
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'first_image',  'color': 'image'},
        {'id': 'second_image', 'color': 'image'},
        {'id': 'first_mask',   'color': 'mask'},
        {'id': 'second_mask',  'color': 'mask'},
    ],
    params=[
        {'id': 'axis', 'label': 'Axis', 'type': 'enum', 'default': 1,
         'options': ['Horizontal (top / bottom)', 'Vertical (left / right)']},
        {'id': 'position', 'label': 'Split %', 'type': 'float',
         'default': 50, 'min': 0, 'max': 100},
    ],
)
class SplitHalfNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        mask  = inputs.get('mask')

        src = image if image is not None else mask
        if src is None:
            return {}

        H, W  = src.shape[:2]
        axis  = int(params.get('axis', 1))
        pos   = float(params.get('position', 50))

        if axis == 0:   # Horizontal → top / bottom
            split = max(0, min(H, int(H * pos / 100)))
            def first_fn(img):
                out = np.zeros_like(img); out[:split] = img[:split]; return out
            def second_fn(img):
                out = np.zeros_like(img); out[split:] = img[split:]; return out
        else:           # Vertical → left / right
            split = max(0, min(W, int(W * pos / 100)))
            def first_fn(img):
                out = np.zeros_like(img); out[:, :split] = img[:, :split]; return out
            def second_fn(img):
                out = np.zeros_like(img); out[:, split:] = img[:, split:]; return out

        fi = first_fn(image)  if image is not None else None
        si = second_fn(image) if image is not None else None
        fm = first_fn(mask)   if mask  is not None else None
        sm = second_fn(mask)  if mask  is not None else None

        return {
            'first_image':  fi,
            'second_image': si,
            'first_mask':   fm,
            'second_mask':  sm,
        }
