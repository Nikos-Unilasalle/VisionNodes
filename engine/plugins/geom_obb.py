import cv2
import numpy as np
import base64
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='geom_obb',
    label='Oriented Bounding Box',
    category='geom',
    icon='RotateCw',
    description='Computes minimum-area oriented bounding box from mask contours and outputs a deskewed auto-rotated crop.',
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',         'color': 'image'},
        {'id': 'rotated',      'color': 'image'},
        {'id': 'rotated_mask', 'color': 'mask'},
        {'id': 'angle',        'color': 'scalar'},
    ],
    params=[
        {'id': 'draw_obb',  'label': 'Draw OBB',    'type': 'bool',  'default': True},
        {'id': 'color',     'label': 'Color',        'type': 'color', 'default': '#00ff88'},
        {'id': 'thickness', 'label': 'Thickness',    'type': 'int',   'default': 2, 'min': 1, 'max': 20},
        {'id': 'target',    'label': 'Target',       'type': 'enum',  'default': 'largest',
         'options': ['largest', 'all', 'combined']},
        {'id': 'auto_crop', 'label': 'Crop to OBB', 'type': 'bool',  'default': True},
    ],
    colorable=True,
)
class GeomOBBNode(NodeProcessor):
    def __init__(self):
        self._frame_count = 0
        self._last_preview = None

    def _parse_color(self, hex_str):
        try:
            h = str(hex_str).lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (b, g, r)
        except Exception:
            return (0, 255, 136)

    def _encode_preview(self, img):
        try:
            h, w = img.shape[:2]
            pw = min(w, 480)
            ph = int(pw * h / w)
            pimg = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 75])
            self._last_preview = base64.b64encode(bytes(buf)).decode('utf-8')
        except Exception:
            pass

    def _to_bgr(self, img):
        if len(img.shape) == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 4:
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img.copy()

    def _warp_crop(self, img, cx_p, cy_p, angle, w_rect, h_rect, pad,
                   interp=cv2.INTER_LINEAR):
        padded = cv2.copyMakeBorder(img, pad, pad, pad, pad,
                                    cv2.BORDER_CONSTANT, value=0)
        Hp, Wp = padded.shape[:2]
        M = cv2.getRotationMatrix2D((cx_p, cy_p), angle, 1.0)
        warped = cv2.warpAffine(padded, M, (Wp, Hp),
                                flags=interp, borderMode=cv2.BORDER_CONSTANT)
        x0 = max(0, int(cx_p - w_rect / 2))
        y0 = max(0, int(cy_p - h_rect / 2))
        x1 = min(Wp, int(cx_p + w_rect / 2))
        y1 = min(Hp, int(cy_p + h_rect / 2))
        if x1 > x0 and y1 > y0:
            return warped[y0:y1, x0:x1]
        return warped

    def process(self, inputs, params):
        image = inputs.get('image')
        mask  = inputs.get('mask')

        if image is None:
            return {}

        vis = self._to_bgr(image)
        H, W = vis.shape[:2]

        draw_obb  = str(params.get('draw_obb',  True)).lower() not in ('false', '0', 'no')
        auto_crop = str(params.get('auto_crop', True)).lower() not in ('false', '0', 'no')
        color     = self._parse_color(params.get('color', '#00ff88'))
        thickness = max(1, int(params.get('thickness', 2)))
        target    = params.get('target', 'largest')

        # Binary source for OBB detection (prefer mask)
        if mask is not None:
            src = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv2.cvtColor(vis, cv2.COLOR_BGR2GRAY)
            _, src = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(src, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        empty_result = {
            'main': vis, 'rotated': vis,
            'rotated_mask': src, 'angle': 0.0,
            'main_preview': self._last_preview,
        }

        if not contours:
            self._encode_preview(vis)
            return empty_result

        if target == 'largest':
            groups = [max(contours, key=cv2.contourArea)]
        elif target == 'combined':
            groups = [np.vstack(contours)]
        else:
            groups = list(contours)

        last_rect = None
        for cnt in groups:
            rect = cv2.minAreaRect(cnt)
            last_rect = rect
            if draw_obb:
                box = np.int32(cv2.boxPoints(rect))
                cv2.polylines(vis, [box], True, color, thickness, cv2.LINE_AA)

        if last_rect is None:
            self._encode_preview(vis)
            return empty_result

        cx, cy = last_rect[0]
        w_rect, h_rect = last_rect[1]
        angle = last_rect[2]

        # Normalize: long axis horizontal
        if w_rect < h_rect:
            angle += 90.0
            w_rect, h_rect = h_rect, w_rect

        rotated_out      = vis.copy()
        rotated_mask_out = src.copy()

        if auto_crop and w_rect > 0 and h_rect > 0:
            pad   = int(max(W, H) * 0.75)
            cx_p  = cx + pad
            cy_p  = cy + pad

            rotated_out = self._warp_crop(
                vis, cx_p, cy_p, angle, w_rect, h_rect, pad, cv2.INTER_LINEAR)

            # Rotate mask with nearest-neighbour to keep binary values
            rotated_mask_out = self._warp_crop(
                src, cx_p, cy_p, angle, w_rect, h_rect, pad, cv2.INTER_NEAREST)

        self._frame_count += 1
        if self._frame_count % 3 == 1:
            self._encode_preview(vis)

        return {
            'main':         vis,
            'rotated':      rotated_out,
            'rotated_mask': rotated_mask_out,
            'angle':        float(angle),
            'main_preview': self._last_preview,
        }
