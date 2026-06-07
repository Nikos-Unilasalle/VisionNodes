"""
Box Selection — Pick a single box out of a boxes list.

Replaces the old box_0 / box_1 / box_2 fixed output ports of Grounding DINO.
Takes a boxes list (GDINO / YOLO / BBox Transform) and outputs ONE box dict,
chosen by index or by ranking (largest / smallest / highest score). Optionally
draws the picked box on a connected image for preview.
"""
from registry import vision_node, NodeProcessor
import cv2


@vision_node(
    type_id='box_selection',
    label='Box Selection',
    category='analysis',
    icon='SquareMousePointer',
    description=(
        "Select a single box from a boxes list. Pick by index, or by ranking "
        "(largest / smallest area, highest score). Outputs one box dict ready for "
        "SAM (single box mode) or Auto Cropper. Connect an image for preview."
    ),
    inputs=[
        {'id': 'boxes_list', 'color': 'list',  'label': 'Boxes List'},
        {'id': 'image',      'color': 'image', 'label': 'Image (preview)'},
    ],
    outputs=[
        {'id': 'box',   'color': 'dict',   'label': 'Selected Box'},
        {'id': 'main',  'color': 'image',  'label': 'Overlay'},
        {'id': 'index', 'color': 'scalar', 'label': 'Index'},
    ],
    params=[
        {'id': 'mode', 'label': 'Select By', 'type': 'enum',
         'options': ['Index', 'Largest Area', 'Smallest Area', 'Highest Score'],
         'default': 0},
        {'id': 'index', 'label': 'Index (0-based)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 9999},
        {'id': 'thickness', 'label': 'Outline Thickness', 'type': 'int',
         'default': 3, 'min': 1, 'max': 10},
    ],
    colorable=True,
)
class BoxSelectionNode(NodeProcessor):
    def _area(self, b: dict) -> float:
        return float(b.get('width', 0.0)) * float(b.get('height', 0.0))

    def process(self, inputs: dict, params: dict) -> dict:
        boxes = inputs.get('boxes_list')
        image = inputs.get('image')
        boxes = [b for b in boxes if isinstance(b, dict)] if isinstance(boxes, list) else []

        if not boxes:
            return {'box': None, 'main': image, 'index': -1.0}

        mode = int(params.get('mode', 0))
        if mode == 1:    # largest area
            sel = max(range(len(boxes)), key=lambda i: self._area(boxes[i]))
        elif mode == 2:  # smallest area
            sel = min(range(len(boxes)), key=lambda i: self._area(boxes[i]))
        elif mode == 3:  # highest score
            sel = max(range(len(boxes)), key=lambda i: float(boxes[i].get('score', 0.0)))
        else:            # index (clamped)
            sel = max(0, min(int(params.get('index', 0)), len(boxes) - 1))

        box = boxes[sel]

        overlay = None
        if image is not None and hasattr(image, 'shape'):
            overlay = image.copy()
            h, w = overlay.shape[:2]
            thick = int(params.get('thickness', 3))
            x1 = int(float(box.get('xmin', 0.0)) * w)
            y1 = int(float(box.get('ymin', 0.0)) * h)
            x2 = int((float(box.get('xmin', 0.0)) + float(box.get('width', 0.0))) * w)
            y2 = int((float(box.get('ymin', 0.0)) + float(box.get('height', 0.0))) * h)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 255), thick)

        return {'box': box, 'main': overlay, 'index': float(sel)}
