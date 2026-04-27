from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import base64
import json

@vision_node(
    type_id='geom_crop_rect',
    label='Crop',
    category='geom',
    icon='Crop',
    description="Crops a rectangular region from the image. Define the region interactively using the built-in editor.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main',   'color': 'image'},
        {'id': 'width',  'color': 'scalar'},
        {'id': 'height', 'color': 'scalar'},
    ],
    params=[
        {'id': 'rect', 'label': 'Rect', 'type': 'string',
         'default': '{"x":0.1,"y":0.1,"w":0.8,"h":0.8}'},
    ],
    colorable=True,
)
class CropRectNode(NodeProcessor):
    def __init__(self):
        self._frame_count = 0
        self._last_preview = None

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'width': 0, 'height': 0}

        try:
            rect = json.loads(params.get('rect', '{"x":0.1,"y":0.1,"w":0.8,"h":0.8}'))
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
            return {'main': img, 'width': w, 'height': h}

        cropped = img[y1:y2, x1:x2]
        ch, cw = cropped.shape[:2]

        self._frame_count += 1
        if self._frame_count % 6 == 0:
            try:
                ph = 360
                pw = int(360 * w / h)
                pimg = cv2.resize(img, (pw, ph))
                _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 60])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'main': cropped,
            'width': cw,
            'height': ch,
            'main_preview': self._last_preview,
        }
