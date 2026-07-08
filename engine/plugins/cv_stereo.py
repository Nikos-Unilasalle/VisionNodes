"""
Stereo Disparity node (cv_stereo)
=================================
Chapter 8 — camera geometry.
Computes a disparity map from a rectified stereo pair using StereoSGBM (or
the basic block matcher StereoBM) and renders it as a colored depth map.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_COLORMAPS = {
    'Jet': cv2.COLORMAP_JET,
    'Viridis': cv2.COLORMAP_VIRIDIS,
}


@vision_node(
    type_id='cv_stereo',
    label='Stereo Disparity',
    category='geometry',
    icon='Boxes',
    description="Estimate a disparity (depth) map from a rectified stereo pair "
                "using StereoSGBM or StereoBM, rendered as a colored map.",
    inputs=[
        {'id': 'left', 'label': 'Left', 'color': 'image'},
        {'id': 'right', 'label': 'Right', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',      'label': 'Disparity', 'color': 'image'},
        {'id': 'disp_min',  'label': 'Disparity Min (px)', 'color': 'scalar'},
        {'id': 'disp_max',  'label': 'Disparity Max (px)', 'color': 'scalar'},
        {'id': 'data',      'label': 'Params', 'color': 'dict'},
    ],
    params=[
        {'id': 'num_disparities', 'label': 'Num Disparities', 'type': 'int', 'min': 16, 'max': 256, 'default': 64},
        {'id': 'block_size', 'label': 'Block Size', 'type': 'int', 'min': 3, 'max': 15, 'default': 7},
        {'id': 'min_disparity', 'label': 'Min Disparity', 'type': 'int', 'min': 0, 'max': 64, 'default': 0},
        {'id': 'colormap', 'label': 'Colormap', 'type': 'enum', 'options': ['Jet', 'Viridis', 'Gray'], 'default': 'Jet'},
        {'id': 'use_sgbm', 'label': 'Use SGBM', 'type': 'bool', 'default': True},
    ],
)
class StereoDisparityNode(NodeProcessor):
    """Computes a colored disparity map from a stereo pair."""

    def process(self, inputs, params):
        left = inputs.get('left')
        right = inputs.get('right')
        if left is None or right is None:
            return {'main': None}

        # Match right to left dimensions if needed.
        if right.shape[:2] != left.shape[:2]:
            right = cv2.resize(right, (left.shape[1], left.shape[0]))

        gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if left.ndim == 3 else left
        gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY) if right.ndim == 3 else right

        # num_disparities must be a positive multiple of 16.
        num_disp = int(params.get('num_disparities', 64))
        num_disp = max(16, int(round(num_disp / 16.0)) * 16)

        # block_size must be odd.
        block_size = int(params.get('block_size', 7))
        block_size = max(3, min(15, block_size))
        if block_size % 2 == 0:
            block_size += 1

        min_disp = int(params.get('min_disparity', 0))
        use_sgbm = bool(params.get('use_sgbm', True))
        colormap = params.get('colormap', 'Jet')

        if use_sgbm:
            matcher = cv2.StereoSGBM_create(
                minDisparity=min_disp,
                numDisparities=num_disp,
                blockSize=block_size,
                P1=8 * block_size * block_size,
                P2=32 * block_size * block_size,
            )
        else:
            matcher = cv2.StereoBM_create(
                numDisparities=num_disp,
                blockSize=block_size,
            )

        disp = matcher.compute(gray_l, gray_r).astype(np.float32) / 16.0

        valid = disp[disp > min_disp]  # negative/zero = unmatched pixels, exclude from range
        disp_min = float(valid.min()) if valid.size else 0.0
        disp_max = float(valid.max()) if valid.size else 0.0

        disp_vis = cv2.normalize(disp, None, 0, 255, cv2.NORM_MINMAX)
        disp_vis = disp_vis.astype(np.uint8)

        if colormap == 'Gray':
            result = cv2.cvtColor(disp_vis, cv2.COLOR_GRAY2BGR)
        else:
            result = cv2.applyColorMap(disp_vis, _COLORMAPS.get(colormap, cv2.COLORMAP_JET))

        result = np.ascontiguousarray(result.astype(np.uint8))

        return {
            'main': result,
            'disp_min': round(disp_min, 2),
            'disp_max': round(disp_max, 2),
            'data': {
                'num_disparities': num_disp,
                'block_size': block_size,
            },
        }
