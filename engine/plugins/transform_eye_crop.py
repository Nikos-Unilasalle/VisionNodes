from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

# MediaPipe Face Mesh landmark indices
_LEFT_INNER  = 133   # left eye inner corner
_LEFT_OUTER  = 33    # left eye outer corner
_LEFT_IRIS   = 468   # left iris center (requires iris model)
_RIGHT_INNER = 362   # right eye inner corner
_RIGHT_OUTER = 263   # right eye outer corner
_RIGHT_IRIS  = 473   # right iris center

@vision_node(
    type_id='transform_eye_crop',
    label='Eye Crop',
    category='track',
    icon='Eye',
    description="Crops and optionally aligns left and right eye regions from MediaPipe Face Tracker landmarks. Reusable for any eye-based classifier.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'face',  'color': 'dict'}
    ],
    outputs=[
        {'id': 'eye_left',  'color': 'image'},
        {'id': 'eye_right', 'color': 'image'},
        {'id': 'meta',      'color': 'dict'}
    ],
    params=[
        {'id': 'size',    'label': 'Size (px)',   'type': 'int',   'default': 64,  'min': 32,  'max': 256},
        {'id': 'padding', 'label': 'Padding',     'type': 'float', 'default': 0.4, 'min': 0.0, 'max': 1.5, 'step': 0.05},
        {'id': 'align',   'label': 'Align',        'type': 'bool',  'default': True}
    ]
)
class EyeCropNode(NodeProcessor):

    def _crop(self, image, lms, inner_id, outer_id, iris_id, size, padding, align):
        h, w = image.shape[:2]
        use_iris = iris_id < len(lms)

        p_inner = np.array([lms[inner_id]['x'] * w, lms[inner_id]['y'] * h])
        p_outer = np.array([lms[outer_id]['x'] * w, lms[outer_id]['y'] * h])

        if use_iris:
            center = np.array([lms[iris_id]['x'] * w, lms[iris_id]['y'] * h])
        else:
            center = (p_inner + p_outer) / 2.0

        eye_width = np.linalg.norm(p_outer - p_inner)
        half = eye_width * (0.5 + padding)

        angle = 0.0
        if align:
            dx, dy = p_outer - p_inner
            angle = np.degrees(np.arctan2(dy, dx))
            # Normalize to [-90, 90] — prevents 180° flip on left eye
            if angle > 90:   angle -= 180
            elif angle < -90: angle += 180

        if align and abs(angle) > 1.0:
            M = cv2.getRotationMatrix2D(tuple(center.astype(float)), angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h))
            cx, cy = int(center[0]), int(center[1])
        else:
            rotated = image
            cx, cy = int(center[0]), int(center[1])

        s = int(half)
        x1, y1 = max(0, cx - s), max(0, cy - s)
        x2, y2 = min(w, cx + s), min(h, cy + s)
        crop = rotated[y1:y2, x1:x2]

        if crop.size == 0:
            return np.zeros((size, size, 3), dtype=np.uint8), {}

        crop = cv2.resize(crop, (size, size))
        meta = {
            'cx': float(center[0]) / w, 'cy': float(center[1]) / h,
            'x1': x1 / w, 'y1': y1 / h, 'x2': x2 / w, 'y2': y2 / h,
            'angle': angle
        }
        return crop, meta

    def process(self, inputs, params):
        image = inputs.get('image')
        face  = inputs.get('face')
        size    = int(params.get('size', 64))
        padding = float(params.get('padding', 0.4))
        align   = int(params.get('align', 1))
        blank   = np.zeros((size, size, 3), dtype=np.uint8)

        if image is None or not isinstance(face, dict) or 'landmarks' not in face:
            return {'eye_left': blank, 'eye_right': blank, 'meta': {}}

        lms = face['landmarks']
        if len(lms) < 478:
            return {'eye_left': blank, 'eye_right': blank, 'meta': {}}

        left_crop,  left_meta  = self._crop(image, lms, _LEFT_INNER,  _LEFT_OUTER,  _LEFT_IRIS,  size, padding, align)
        right_crop, right_meta = self._crop(image, lms, _RIGHT_INNER, _RIGHT_OUTER, _RIGHT_IRIS, size, padding, align)

        meta = {'left': left_meta, 'right': right_meta, 'size': size}
        return {'eye_left': left_crop, 'eye_right': right_crop, 'meta': meta}
