"""
Distortion Correction node (cv_undistort)
==========================================
Chapter 8 — camera geometry.
Builds a pinhole camera matrix from a relative focal length and the image
principal point, then removes radial/tangential lens distortion with
cv2.undistort.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_undistort',
    label='Distortion Correction',
    category='geometry',
    icon='Frame',
    description="Remove radial/tangential lens distortion using a pinhole "
                "camera model built from focal length and distortion coefficients.",
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Undistorted', 'color': 'image'},
        {'id': 'data', 'label': 'Calibration', 'color': 'dict'},
    ],
    params=[
        {'id': 'focal', 'label': 'Focal (xW)', 'type': 'float', 'min': 0.3, 'max': 3.0, 'default': 1.0},
        {'id': 'k1', 'label': 'k1 (radial)', 'type': 'float', 'min': -1.0, 'max': 1.0, 'default': 0.0},
        {'id': 'k2', 'label': 'k2 (radial)', 'type': 'float', 'min': -1.0, 'max': 1.0, 'default': 0.0},
        {'id': 'p1', 'label': 'p1 (tangential)', 'type': 'float', 'min': -0.1, 'max': 0.1, 'default': 0.0},
        {'id': 'p2', 'label': 'p2 (tangential)', 'type': 'float', 'min': -0.1, 'max': 0.1, 'default': 0.0},
        {'id': 'k3', 'label': 'k3 (radial)', 'type': 'float', 'min': -1.0, 'max': 1.0, 'default': 0.0},
        {'id': 'crop_valid', 'label': 'Crop Valid ROI', 'type': 'bool', 'default': False},
    ],
)
class UndistortNode(NodeProcessor):
    """Removes lens distortion from an image."""

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}

        h, w = img.shape[:2]

        focal = float(params.get('focal', 1.0))
        k1 = float(params.get('k1', 0.0))
        k2 = float(params.get('k2', 0.0))
        p1 = float(params.get('p1', 0.0))
        p2 = float(params.get('p2', 0.0))
        k3 = float(params.get('k3', 0.0))
        crop_valid = bool(params.get('crop_valid', False))

        fx = fy = focal * w
        cx = w / 2.0
        cy = h / 2.0
        camera_matrix = np.array([
            [fx, 0.0, cx],
            [0.0, fy, cy],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)
        dist_coeffs = np.array([k1, k2, p1, p2, k3], dtype=np.float64)

        if crop_valid:
            new_k, roi = cv2.getOptimalNewCameraMatrix(
                camera_matrix, dist_coeffs, (w, h), 1, (w, h))
            result = cv2.undistort(img, camera_matrix, dist_coeffs, None, new_k)
            x, y, rw, rh = roi
            if rw > 0 and rh > 0:
                result = result[y:y + rh, x:x + rw]
        else:
            result = cv2.undistort(img, camera_matrix, dist_coeffs)

        result = np.ascontiguousarray(result.astype(np.uint8))

        return {
            'main': result,
            'data': {
                'camera_matrix': camera_matrix.tolist(),
                'dist_coeffs': dist_coeffs.tolist(),
            },
        }
