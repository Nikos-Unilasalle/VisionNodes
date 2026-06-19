"""
Mean Shift Segmentation Node
============================
Edge-preserving smoothing / segmentation via cv2.pyrMeanShiftFiltering.
Pixels are clustered in the joint spatial+color domain, flattening regions
into uniform color patches while keeping edges sharp.

Parameters:
  - spatial_radius (sp): size of the spatial window.
  - color_radius   (sr): size of the color window.
  - max_level         : levels of the Gaussian pyramid for segmentation.

Performance: pyrMeanShiftFiltering is slow on large frames. To stay usable in a
30fps pipeline, frames whose largest side exceeds 640px are downscaled before
filtering and the result is upscaled back to the original size.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_MAX_SIDE = 640


@vision_node(
    type_id='cv_mean_shift',
    label='Mean Shift Segmentation',
    category='segmentation',
    icon='Layers',
    description=(
        "Mean-shift segmentation (cv2.pyrMeanShiftFiltering). Edge-preserving "
        "smoothing that clusters pixels in spatial+color space into flat regions. "
        "Frames larger than 640px are downscaled before filtering then upscaled "
        "back (the filter is slow on big images)."
    ),
    inputs=[
        {'id': 'image', 'label': 'Input', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Segmented', 'color': 'image'},
        {'id': 'data', 'label': 'Data', 'color': 'dict'},
    ],
    params=[
        {'id': 'spatial_radius', 'label': 'Spatial Radius', 'type': 'int',
         'min': 1, 'max': 50, 'default': 10},
        {'id': 'color_radius', 'label': 'Color Radius', 'type': 'int',
         'min': 1, 'max': 100, 'default': 30},
        {'id': 'max_level', 'label': 'Max Level', 'type': 'int',
         'min': 0, 'max': 5, 'default': 1},
    ],
)
class MeanShiftNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        sp = int(params.get('spatial_radius', 10))
        sr = int(params.get('color_radius', 30))
        max_level = int(params.get('max_level', 1))

        h, w = img.shape[:2]
        # pyrMeanShiftFiltering needs a 3-channel 8-bit image.
        src = img if (img.ndim == 3 and img.shape[2] == 3) else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if src.dtype != np.uint8:
            src = np.clip(src, 0, 255).astype(np.uint8)

        scale = 1.0
        work = src
        longest = max(h, w)
        if longest > _MAX_SIDE:
            scale = _MAX_SIDE / float(longest)
            work = cv2.resize(src, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                              interpolation=cv2.INTER_AREA)

        seg = cv2.pyrMeanShiftFiltering(work, sp, sr, maxLevel=max_level)

        if scale != 1.0:
            seg = cv2.resize(seg, (w, h), interpolation=cv2.INTER_NEAREST)

        # Approximate number of distinct colors in the segmented result.
        flat = seg.reshape(-1, seg.shape[2])
        n_unique = int(np.unique(flat, axis=0).shape[0])

        return {
            'main': seg,
            'data': {
                'sp': sp,
                'sr': sr,
                'n_unique_colors': n_unique,
            },
        }
