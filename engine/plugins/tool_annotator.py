from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import base64
import json

@vision_node(
    type_id='tool_annotator',
    label='Annotator',
    category='draw',
    icon='PenTool',
    description='Interactive annotation layer. Draw text, lines, and freehand strokes over an image using the built-in editor.',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'annotations',     'label': 'Annotations',    'type': 'string',  'default': '[]'},
        {'id': 'with_background', 'label': 'With Background', 'type': 'boolean', 'default': True},
    ],
    colorable=True,
)
class AnnotatorNode(NodeProcessor):
    def __init__(self):
        self._frame_count = 0
        self._last_preview = None

    def _encode_preview(self, img):
        try:
            h, w = img.shape[:2]
            pw = min(w, 480)
            ph = int(pw * h / w)
            pimg = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 70])
            self._last_preview = base64.b64encode(bytes(buf)).decode('utf-8')
        except Exception:
            pass

    def _parse_color(self, hex_str):
        try:
            h = str(hex_str).lstrip('#')
            if len(h) == 6:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return (b, g, r)
        except Exception:
            pass
        return (255, 255, 255)

    def process(self, inputs, params):
        img = inputs.get('image')
        with_bg = str(params.get('with_background', True)).lower() not in ('false', '0', 'no')

        try:
            annotations = json.loads(params.get('annotations', '[]') or '[]')
        except Exception:
            annotations = []

        if img is not None:
            h, w = img.shape[:2]
            if with_bg:
                canvas = img.copy()
                if len(canvas.shape) == 2:
                    canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
                elif canvas.shape[2] == 4:
                    canvas = cv2.cvtColor(canvas, cv2.COLOR_BGRA2BGR)
            else:
                canvas = np.zeros((h, w, 3), dtype=np.uint8)
        else:
            h, w = 480, 640
            canvas = np.zeros((h, w, 3), dtype=np.uint8)

        for ann in annotations:
            if not isinstance(ann, dict):
                continue
            tool = ann.get('tool', 'brush')
            color = self._parse_color(ann.get('color', '#ffffff'))
            size = max(1, int(ann.get('size', 3)))
            pts_rel = ann.get('pts', [])

            if tool == 'brush' and len(pts_rel) > 1:
                pts = [(int(p[0] * w), int(p[1] * h)) for p in pts_rel]
                for i in range(1, len(pts)):
                    cv2.line(canvas, pts[i - 1], pts[i], color, size, cv2.LINE_AA)

            elif tool == 'line' and len(pts_rel) >= 2:
                p1 = (int(pts_rel[0][0] * w), int(pts_rel[0][1] * h))
                p2 = (int(pts_rel[-1][0] * w), int(pts_rel[-1][1] * h))
                cv2.line(canvas, p1, p2, color, size, cv2.LINE_AA)

            elif tool == 'circle' and pts_rel:
                cx = int(pts_rel[0][0] * w)
                cy = int(pts_rel[0][1] * h)
                radius = max(1, int(size * min(w, h) / 100))
                cv2.circle(canvas, (cx, cy), radius, color, size, cv2.LINE_AA)

            elif tool == 'text' and pts_rel:
                pt = (int(pts_rel[0][0] * w), int(pts_rel[0][1] * h))
                text = str(ann.get('text', ''))
                font_scale = max(0.4, size * 0.15)
                thickness = max(1, size // 4)
                # Shadow for readability
                cv2.putText(canvas, text, (pt[0] + 1, pt[1] + 1),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
                cv2.putText(canvas, text, pt,
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)

        self._frame_count += 1
        if self._frame_count % 3 == 1:
            self._encode_preview(canvas)

        return {'main': canvas, 'main_preview': self._last_preview}
