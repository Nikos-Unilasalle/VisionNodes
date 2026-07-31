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
        'Center is expressed as % of image width/height. Radii are expressed as % of the '
        'SHORTER image side, so equal X and Y radii always give a true circle, whatever '
        'the aspect ratio. Set them differently to get an ellipse.\n\n'
        'Connect an image to inherit its size; otherwise set Width/Height manually.\n\n'
        'Feather > 0 softens the edge inwards over that many pixels. '
        'Feather = 0 gives a hard binary circle.\n\n'
        'Combine with Mask Operations to cut a disc out of another mask.'
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
        # 'masked' carries the source image with the mask applied — a colour image,
        # not a mask. It was declared 'mask', which made every downstream connection
        # from it wrong. No template used it, so this is safe to correct.
        {'id': 'masked', 'label': 'Masked Image', 'color': 'image'},
    ],
    params=[
        {'id': '_sec_geometry', 'label': 'Geometry', 'type': 'section'},
        {'id': 'center_x', 'label': 'Center X (%)', 'type': 'float', 'default': 50.0, 'min': 0.0,  'max': 100.0},
        {'id': 'center_y', 'label': 'Center Y (%)', 'type': 'float', 'default': 50.0, 'min': 0.0,  'max': 100.0},
        {'id': 'radius_x', 'label': 'Radius X (% short side)', 'type': 'float', 'default': 45.0, 'min': 1.0,  'max': 100.0},
        {'id': 'radius_y', 'label': 'Radius Y (% short side)', 'type': 'float', 'default': 45.0, 'min': 1.0,  'max': 100.0},
        {'id': 'feather',  'label': 'Feather (px)',  'type': 'int',   'default': 0,    'min': 0,    'max': 200},
        {'id': 'invert',   'label': 'Invert',        'type': 'bool',  'default': False},
        {'id': '_sec_fallback', 'label': 'Fallback Size', 'type': 'section'},
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
        # Both radii reference the SHORTER side. Referencing width for X and height
        # for Y turned every circle into an ellipse on any non-square image.
        ref = float(min(w, h))
        rx = max(1.0, float(params.get('radius_x', 45.0)) / 100.0 * ref)
        ry = max(1.0, float(params.get('radius_y', 45.0)) / 100.0 * ref)
        feather = int(params.get('feather', 0))
        invert  = bool(params.get('invert', False))

        # Rasterise with cv2.ellipse rather than evaluating a distance field over a
        # full-image np.mgrid: the grid allocated two int64 arrays the size of the
        # image on every engine cycle (~140 MB and 50 ms on a 4 MP frame), which is
        # what made the whole canvas crawl.
        mask_u8 = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(mask_u8, (int(round(cx)), int(round(cy))),
                    (int(round(rx)), int(round(ry))), 0, 0, 360, 255, -1)

        if feather > 0:
            # Distance to the outside, in pixels: 0 on the boundary, growing inwards.
            # Normalising by the feather width reproduces the old soft band, and does
            # it uniformly along both axes instead of favouring the minor one.
            dist_in = cv2.distanceTransform(mask_u8, cv2.DIST_L2, 3)
            mask_u8 = np.clip(dist_in * (255.0 / feather), 0.0, 255.0).astype(np.uint8)

        if invert:
            mask_u8 = cv2.bitwise_not(mask_u8)

        # Preview: source image (or a dark canvas) seen through the mask
        if img is not None:
            base = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            base = np.full((h, w, 3), 30, dtype=np.uint8)

        if feather > 0:
            alpha3 = cv2.cvtColor(mask_u8, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
            preview = (base.astype(np.float32) * alpha3).astype(np.uint8)
        else:
            # Binary mask: bitwise_and is exact here and avoids two float32 copies.
            preview = cv2.bitwise_and(base, base, mask=mask_u8)

        return {'mask': mask_u8, 'masked': preview}
