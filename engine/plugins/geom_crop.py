from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import base64
import json

@vision_node(
    type_id='geom_crop',
    label='Crop',
    category='geometry',
    icon='Crop',
    description=(
        'Crops a rectangular region from the image. '
        'Three modes — auto-selected by what is connected:\n'
        '• Manual: drag the interactive rect (no bbox input).\n'
        '• BBox: crop from a single detection dict {xmin, ymin, width, height}.\n'
        '• BBox List: crop from a list of dicts; use the Index slider to navigate.'
    ),
    inputs=[
        {'id': 'image',     'color': 'image', 'label': 'Image'},
        {'id': 'bbox',      'color': 'dict',  'label': 'BBox'},
        {'id': 'bbox_list', 'color': 'any',   'label': 'BBox List'},
    ],
    outputs=[
        {'id': 'main',   'color': 'image',  'label': 'Cropped'},
        {'id': 'width',  'color': 'scalar', 'label': 'Width'},
        {'id': 'height', 'color': 'scalar', 'label': 'Height'},
        {'id': 'box',    'color': 'dict',   'label': 'BBox Used'},
    ],
    params=[
        {'id': 'rect',
         'label': 'Rect (manual mode)',
         'type': 'string',
         'default': '{"x":0.1,"y":0.1,"w":0.8,"h":0.8}'},
        {'id': 'padding',
         'label': 'Padding (%)',
         'type': 'int', 'min': 0, 'max': 100, 'default': 10},
        {'id': 'bbox_index',
         'label': 'BBox Index',
         'type': 'int', 'min': 0, 'max': 999, 'default': 0},
    ],
    colorable=True,
)
class CropNode(NodeProcessor):
    def __init__(self):
        self._frame_count = 0
        self._last_preview = None

    # ------------------------------------------------------------------ #
    # helpers                                                              #
    # ------------------------------------------------------------------ #

    def _encode_preview(self, img: np.ndarray) -> None:
        try:
            h, w = img.shape[:2]
            pw = min(w, 480)
            ph = int(pw * h / w)
            pimg = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 65])
            self._last_preview = base64.b64encode(bytes(buf)).decode('utf-8')
        except Exception:
            pass

    def _apply_bbox(
        self,
        img: np.ndarray,
        bbox: dict,
        padding_pct: float,
    ) -> tuple[np.ndarray, int, int, dict]:
        """Crop img using a normalised bbox dict {xmin, ymin, width, height}."""
        h, w = img.shape[:2]
        pad = padding_pct / 100.0
        half = pad / 2.0

        x1 = max(0, int((bbox['xmin'] - half) * w))
        y1 = max(0, int((bbox['ymin'] - half) * h))
        x2 = min(w, int((bbox['xmin'] + bbox['width'] + half) * w))
        y2 = min(h, int((bbox['ymin'] + bbox['height'] + half) * h))

        if x2 <= x1 or y2 <= y1:
            return img, w, h, bbox

        cropped = img[y1:y2, x1:x2]
        ch, cw = cropped.shape[:2]
        used_box = {
            'xmin':   x1 / w, 'ymin':   y1 / h,
            'width':  cw / w, 'height': ch / h,
        }
        return cropped, cw, ch, used_box

    def _apply_manual_rect(
        self,
        img: np.ndarray,
        rect_json: str,
    ) -> tuple[np.ndarray, int, int, dict]:
        """Crop img using the interactive rect param (normalised fractions)."""
        try:
            rect = json.loads(rect_json)
        except Exception:
            rect = {'x': 0.1, 'y': 0.1, 'w': 0.8, 'h': 0.8}

        h, w = img.shape[:2]
        rx = float(rect.get('x', 0.1))
        ry = float(rect.get('y', 0.1))
        rw = float(rect.get('w', 0.8))
        rh = float(rect.get('h', 0.8))

        x1 = int(max(0, rx * w))
        y1 = int(max(0, ry * h))
        x2 = int(min(w, (rx + rw) * w))
        y2 = int(min(h, (ry + rh) * h))

        if x2 <= x1 or y2 <= y1:
            return img, w, h, {'xmin': rx, 'ymin': ry, 'width': rw, 'height': rh}

        cropped = img[y1:y2, x1:x2]
        ch, cw = cropped.shape[:2]
        used_box = {'xmin': rx, 'ymin': ry, 'width': rw, 'height': rh}
        return cropped, cw, ch, used_box

    # ------------------------------------------------------------------ #
    # process                                                              #
    # ------------------------------------------------------------------ #

    def process(self, inputs: dict, params: dict) -> dict:
        img = inputs.get('image')
        if img is None:
            return {
                'main': None,
                'main_preview': self._last_preview,
                'width': 0, 'height': 0, 'box': None,
            }

        bbox_list = inputs.get('bbox_list')
        bbox      = inputs.get('bbox')
        padding   = float(params.get('padding', 10))
        index     = int(params.get('bbox_index', 0))

        # ── mode: bbox list ──────────────────────────────────────────── #
        if isinstance(bbox_list, list) and bbox_list:
            clamped = max(0, min(index, len(bbox_list) - 1))
            item = bbox_list[clamped]
            if isinstance(item, dict) and 'xmin' in item:
                cropped, cw, ch, used_box = self._apply_bbox(img, item, padding)
            else:
                cropped, cw, ch = img, img.shape[1], img.shape[0]
                used_box = None

        # ── mode: single bbox ────────────────────────────────────────── #
        elif isinstance(bbox, dict) and 'xmin' in bbox:
            cropped, cw, ch, used_box = self._apply_bbox(img, bbox, padding)

        # ── mode: manual rect ────────────────────────────────────────── #
        else:
            rect_json = params.get('rect', '{"x":0.1,"y":0.1,"w":0.8,"h":0.8}')
            cropped, cw, ch, used_box = self._apply_manual_rect(img, rect_json)

        self._frame_count += 1
        if self._frame_count % 3 == 1:
            self._encode_preview(img)

        return {
            'main':          cropped,
            'main_preview':  self._last_preview,
            'width':         cw,
            'height':        ch,
            'box':           used_box,
        }
