"""
BBox Transform — Resize and filter bounding boxes.

Takes a boxes list (or a single box dict) in the normalized format produced by
Grounding DINO / YOLO ({id, label, score, xmin, ymin, width, height, pts, …}) and:
  • Enlarges or shrinks every box (by percent of box size, or by pixels per side).
  • Filters boxes by size (area as % of image, area in px², or width/height in px).

Pixel modes need the image dimensions → connect the source image to the 'image'
port. Percent-of-image area filtering works without an image (boxes are normalized).
Outputs a clean boxes list ready for SAM / DINOv2 / Calepinage.
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np


@vision_node(
    type_id='bbox_transform',
    label='BBox Transform',
    category='analysis',
    icon='Scaling',
    description=(
        "Resize (enlarge/reduce) and size-filter bounding boxes. Accepts a boxes "
        "list or a single box dict (Grounding DINO / YOLO format). Resize by percent "
        "of box size or by pixels per side; filter by area (% of image or px²) or by "
        "width/height in px. Connect the source image for pixel-based modes."
    ),
    inputs=[
        {'id': 'boxes_list', 'color': 'list',  'label': 'Boxes List'},
        {'id': 'box',        'color': 'dict',  'label': 'Single Box (optional)'},
        {'id': 'image',      'color': 'image', 'label': 'Image (for px modes)'},
    ],
    outputs=[
        {'id': 'boxes_list', 'color': 'list',   'label': 'Boxes List'},
        {'id': 'main',       'color': 'image',  'label': 'Overlay'},
        {'id': 'count',      'color': 'scalar', 'label': 'Count'},
    ],
    params=[
        {'id': 'resize_mode',  'label': 'Resize Mode', 'type': 'enum',
         'options': ['Percent (% of box)', 'Pixels (per side)'], 'default': 0},
        {'id': 'resize_amount', 'label': 'Resize Amount (+grow / -shrink)', 'type': 'float',
         'default': 0.0, 'min': -100.0, 'max': 500.0, 'step': 1.0},
        {'id': 'clamp',        'label': 'Clamp to Image Bounds', 'type': 'bool', 'default': True},
        {'id': 'filter_mode',  'label': 'Size Filter', 'type': 'enum',
         'options': ['None', 'Area % of image', 'Area px²', 'Width & Height px'], 'default': 0},
        {'id': 'min_size',     'label': 'Min Size', 'type': 'float',
         'default': 0.0, 'min': 0.0, 'max': 1000000.0, 'step': 1.0},
        {'id': 'max_size',     'label': 'Max Size (0 = no max)', 'type': 'float',
         'default': 0.0, 'min': 0.0, 'max': 1000000.0, 'step': 1.0},
        {'id': 'draw',         'label': 'Draw Overlay', 'type': 'bool', 'default': True},
    ],
    colorable=True,
)
class BBoxTransformNode(NodeProcessor):

    def _collect_boxes(self, inputs: dict) -> list:
        """Merge boxes_list + single box into one list of dicts."""
        out = []
        bl = inputs.get('boxes_list')
        if isinstance(bl, list):
            out.extend(b for b in bl if isinstance(b, dict))
        single = inputs.get('box')
        if isinstance(single, dict):
            out.append(single)
        return out

    def _resize_box(self, box: dict, mode: int, amount: float,
                    w: int, h: int) -> dict:
        """Return a new box dict resized. Coords are normalized [0,1]."""
        x = float(box.get('xmin', 0.0))
        y = float(box.get('ymin', 0.0))
        bw = float(box.get('width', 0.0))
        bh = float(box.get('height', 0.0))
        cx = x + bw / 2.0
        cy = y + bh / 2.0

        if mode == 0:  # percent of box size
            factor = 1.0 + amount / 100.0
            factor = max(0.0, factor)
            nw = bw * factor
            nh = bh * factor
        else:          # pixels per side (needs image dims)
            dx = (amount / w) if w else 0.0
            dy = (amount / h) if h else 0.0
            nw = max(0.0, bw + 2.0 * dx)
            nh = max(0.0, bh + 2.0 * dy)

        nx = cx - nw / 2.0
        ny = cy - nh / 2.0

        new_box = dict(box)
        new_box['xmin'] = nx
        new_box['ymin'] = ny
        new_box['width'] = nw
        new_box['height'] = nh
        return new_box

    def _clamp_box(self, box: dict) -> dict:
        x = max(0.0, float(box['xmin']))
        y = max(0.0, float(box['ymin']))
        x2 = min(1.0, float(box['xmin']) + float(box['width']))
        y2 = min(1.0, float(box['ymin']) + float(box['height']))
        nb = dict(box)
        nb['xmin'] = x
        nb['ymin'] = y
        nb['width'] = max(0.0, x2 - x)
        nb['height'] = max(0.0, y2 - y)
        return nb

    def _sync_pts(self, box: dict) -> dict:
        """Rebuild the 'pts' field (rect corners) to match xmin/ymin/width/height."""
        if 'pts' not in box:
            return box
        x = float(box['xmin']); y = float(box['ymin'])
        nb = dict(box)
        nb['pts'] = [[x, y], [x + float(box['width']), y + float(box['height'])]]
        return nb

    def _passes_filter(self, box: dict, mode: int, mn: float, mx: float,
                       w: int, h: int) -> bool:
        bw = float(box.get('width', 0.0))
        bh = float(box.get('height', 0.0))
        if mode == 1:    # area % of image (boxes normalized → fraction*100)
            val = bw * bh * 100.0
            metrics = [val]
        elif mode == 2:  # area px²
            if not (w and h):
                return True
            metrics = [bw * w * bh * h]
        elif mode == 3:  # width & height px (both must pass)
            if not (w and h):
                return True
            metrics = [bw * w, bh * h]
        else:
            return True
        for m in metrics:
            if m < mn:
                return False
            if mx > 0 and m > mx:
                return False
        return True

    def process(self, inputs: dict, params: dict) -> dict:
        boxes = self._collect_boxes(inputs)
        image = inputs.get('image')
        w = h = 0
        if image is not None and hasattr(image, 'shape'):
            h, w = image.shape[:2]

        resize_mode  = int(params.get('resize_mode', 0))
        resize_amt   = float(params.get('resize_amount', 0.0))
        do_clamp     = bool(params.get('clamp', True))
        filter_mode  = int(params.get('filter_mode', 0))
        mn           = float(params.get('min_size', 0.0))
        mx           = float(params.get('max_size', 0.0))
        draw         = bool(params.get('draw', True))

        out_boxes = []
        for box in boxes:
            nb = box
            if resize_amt != 0.0:
                nb = self._resize_box(nb, resize_mode, resize_amt, w, h)
            if do_clamp:
                nb = self._clamp_box(nb)
            nb = self._sync_pts(nb)
            if not self._passes_filter(nb, filter_mode, mn, mx, w, h):
                continue
            out_boxes.append(nb)

        # Re-index ids so downstream (SAM/Calepinage) stays contiguous
        for i, b in enumerate(out_boxes):
            b['id'] = i

        # Overlay
        overlay = None
        if image is not None and hasattr(image, 'shape'):
            overlay = image.copy()
            if draw:
                for i, b in enumerate(out_boxes):
                    x1 = int(float(b['xmin']) * w)
                    y1 = int(float(b['ymin']) * h)
                    x2 = int((float(b['xmin']) + float(b['width'])) * w)
                    y2 = int((float(b['ymin']) + float(b['height'])) * h)
                    color = (
                        int((i * 67  + 40) % 200 + 55),
                        int((i * 137 + 80) % 200 + 55),
                        int((i * 197 + 120) % 200 + 55),
                    )
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)

        return {
            'boxes_list': out_boxes,
            'main':       overlay,
            'count':      float(len(out_boxes)),
        }
