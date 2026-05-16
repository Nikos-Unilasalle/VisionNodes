import base64
import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='fill_holes',
    label='Fill Holes',
    category='utility',
    icon='Disc',
    description=(
        'Fills internal holes in a binary mask.\n\n'
        'Useful for cells with central pallor (erythrocytes), '
        'hollow particles, or any ring-shaped objects where the '
        'interior void would otherwise displace distance transform peaks.\n\n'
        'Method "Contour Fill": fills by re-drawing external contours solid — '
        'fast, removes all internal holes regardless of size.\n'
        'Method "Flood Fill": floods from image border — preserves holes '
        'touching the border.\n'
        'Method "Size Filter": removes only holes smaller than max_hole_px.'
    ),
    resizable=True,
    min_width=240,
    min_height=160,
    colorable=True,
    inputs=[
        {'id': 'mask', 'label': 'Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Filled Mask', 'color': 'mask'},
    ],
    params=[
        {'id': 'method',      'label': 'Method',         'type': 'enum', 'options': ['Contour Fill', 'Flood Fill', 'Size Filter'], 'default': 0},
        {'id': 'max_hole_px', 'label': 'Max Hole (px²)', 'type': 'int',  'default': 500, 'min': 1, 'max': 50000},
    ],
)
class FillHolesNode(NodeProcessor):
    def __init__(self):
        self._last_preview: str | None = None
        self._frame_count = 0

    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'main': None}

        if len(mask.shape) == 3:
            gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            gray = mask.copy()
        binary = (gray > 127).astype(np.uint8) * 255

        method      = int(params.get('method', 0))
        max_hole_px = int(params.get('max_hole_px', 500))

        if method == 0:  # Contour Fill
            # RETR_EXTERNAL ignores inner holes → filling solid removes all voids
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            filled = np.zeros_like(binary)
            cv2.drawContours(filled, contours, -1, 255, -1)

        elif method == 1:  # Flood Fill from border
            # Flood the background from all 4 borders → invert → union with original
            h, w = binary.shape
            flooded = binary.copy()
            mask_ff = np.zeros((h + 2, w + 2), dtype=np.uint8)
            # Flood from each border pixel
            for x in range(w):
                if flooded[0, x] == 0:
                    cv2.floodFill(flooded, mask_ff, (x, 0), 128)
                if flooded[h - 1, x] == 0:
                    cv2.floodFill(flooded, mask_ff, (x, h - 1), 128)
            for y in range(h):
                if flooded[y, 0] == 0:
                    cv2.floodFill(flooded, mask_ff, (0, y), 128)
                if flooded[y, w - 1] == 0:
                    cv2.floodFill(flooded, mask_ff, (w - 1, y), 128)
            # Pixels still 0 = interior holes → fill them
            filled = binary.copy()
            filled[flooded == 0] = 255

        else:  # Size Filter — fill only holes smaller than max_hole_px
            # Invert, find small regions, fill them back
            inverted = cv2.bitwise_not(binary)
            n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inverted, connectivity=4)
            filled = binary.copy()
            for i in range(1, n_labels):
                area = int(stats[i, cv2.CC_STAT_AREA])
                if area <= max_hole_px:
                    filled[labels == i] = 255

        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                preview_bgr = cv2.cvtColor(filled, cv2.COLOR_GRAY2BGR)
                ph = min(360, preview_bgr.shape[0])
                pw = int(ph * preview_bgr.shape[1] / preview_bgr.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview_bgr, (pw, ph)),
                                     [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {'main': filled, 'main_preview': self._last_preview}
