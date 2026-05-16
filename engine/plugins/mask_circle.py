import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='mask_circle',
    label='Circle Mask',
    category='mask',
    icon='Circle',
    description=(
        'Generates a circular (or elliptical) binary mask.\n\n'
        'Center and radius are expressed as % of image dimensions. '
        'Connect an image to inherit its size; otherwise set Width/Height manually.\n\n'
        'Feather > 0 produces a soft gradient edge (useful for vignette blending). '
        'Feather = 0 gives a hard binary circle.\n\n'
        'Use AND (Morphology / bitwise) with any mask to clip to a circular FOV.'
    ),
    resizable=True,
    min_width=220,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'image', 'label': 'Image (size ref, opt)', 'color': 'image'},
    ],
    outputs=[
        {'id': 'mask',   'label': 'Circle Mask',  'color': 'mask'},
        {'id': 'masked', 'label': 'Masked Image', 'color': 'mask'},
    ],
    params=[
        {'id': 'center_x', 'label': 'Center X (%)', 'type': 'float', 'default': 50.0, 'min': 0.0,  'max': 100.0},
        {'id': 'center_y', 'label': 'Center Y (%)', 'type': 'float', 'default': 50.0, 'min': 0.0,  'max': 100.0},
        {'id': 'radius_x', 'label': 'Radius X (%)', 'type': 'float', 'default': 45.0, 'min': 1.0,  'max': 100.0},
        {'id': 'radius_y', 'label': 'Radius Y (%)', 'type': 'float', 'default': 45.0, 'min': 1.0,  'max': 100.0},
        {'id': 'feather',  'label': 'Feather (px)',  'type': 'int',   'default': 0,    'min': 0,    'max': 200},
        {'id': 'invert',   'label': 'Invert',        'type': 'bool',  'default': False},
        {'id': 'img_w',    'label': 'Width (fallback)',  'type': 'int', 'default': 512, 'min': 1, 'max': 4096},
        {'id': 'img_h',    'label': 'Height (fallback)', 'type': 'int', 'default': 512, 'min': 1, 'max': 4096},
    ],
)
class CircleMaskNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')

        if img is not None:
            h, w = img.shape[:2]
        else:
            w = int(params.get('img_w', 512))
            h = int(params.get('img_h', 512))

        cx = float(params.get('center_x', 50.0)) / 100.0 * w
        cy = float(params.get('center_y', 50.0)) / 100.0 * h
        rx = max(1.0, float(params.get('radius_x', 45.0)) / 100.0 * w)
        ry = max(1.0, float(params.get('radius_y', 45.0)) / 100.0 * h)
        feather = int(params.get('feather', 0))
        invert  = bool(params.get('invert', False))

        # Normalised ellipse distance: 1.0 on boundary, <1 inside, >1 outside
        ys, xs = np.mgrid[0:h, 0:w]
        dist = np.sqrt(((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2).astype(np.float32)

        if feather > 0:
            # Feather band: [1 - f, 1] → alpha 1→0, outside → 0
            f = feather / min(rx, ry)  # feather width in normalised units
            alpha = np.clip((1.0 - dist) / f, 0.0, 1.0)
            mask_f32 = alpha * 255.0
        else:
            mask_f32 = np.where(dist <= 1.0, 255.0, 0.0)

        mask_u8 = mask_f32.astype(np.uint8)

        if invert:
            mask_u8 = cv2.bitwise_not(mask_u8)

        # Preview: overlay circle on source image or on gray canvas
        if img is not None:
            base = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            base = np.full((h, w, 3), 30, dtype=np.uint8)

        alpha3 = cv2.cvtColor(mask_u8, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
        preview = (base.astype(np.float32) * alpha3).astype(np.uint8)

        return {'mask': mask_u8, 'masked': preview}
