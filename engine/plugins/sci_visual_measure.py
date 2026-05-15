import base64
import cv2
import json
import math
import numpy as np
from registry import vision_node, NodeProcessor

def _to_uint8_bgr(img) -> np.ndarray:
    if not isinstance(img, np.ndarray):
        return np.zeros((64, 64, 3), dtype=np.uint8)
    if img.dtype != np.uint8:
        if img.dtype in (np.float32, np.float64):
            img = (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8) if float(img.max()) <= 1.0 \
                  else np.clip(img, 0, 255).astype(np.uint8)
        else:
            img = np.clip(img, 0, 255).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

@vision_node(
    type_id='sci_visual_measure',
    label='Visual Measure',
    category='math',
    icon='Ruler',
    description=(
        'Measures the physical length and angle of a hand-drawn line.\n\n'
        'Connect a Calibration factor to get real-world units, or leave unconnected for pixels.'
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',  'label': 'Image',   'color': 'image'},
        {'id': 'factor', 'label': 'Px/Unit', 'color': 'scalar'},
        {'id': 'unit',   'label': 'Unit',    'color': 'scalar'},
    ],
    outputs=[
        {'id': 'main',   'label': 'Preview', 'color': 'image'},
        {'id': 'length', 'label': 'Length',  'color': 'scalar'},
        {'id': 'angle',  'label': 'Angle (°)', 'color': 'scalar'},
    ],
    params=[
        {'id': 'points', 'label': 'Measure Line', 'type': 'string', 'default': '[]'},
        {'id': 'unit',   'label': 'Unit Name',    'type': 'string', 'default': 'px'},
        {'id': 'angle_ref', 'label': '0° is',     'type': 'enum', 'options': ['Horizontal (Right)', 'Vertical (Up)'], 'default': 0},
    ],
)
class VisualMeasureNode(NodeProcessor):
    def __init__(self):
        self._last_preview: str | None = None
        self._frame_count = 0

    def process(self, inputs, params):
        raw_img = inputs.get('image')
        img = raw_img if isinstance(raw_img, np.ndarray) else None
        
        try:
            factor = float(inputs.get('factor', 1.0))
        except (TypeError, ValueError):
            factor = 1.0
            
        if factor <= 0:
            factor = 1.0

        if img is None:
            return {'main': None, 'length': 0.0, 'angle': 0.0, 'main_preview': None}

        h, w = img.shape[:2]
        
        try:
            pts = json.loads(str(params.get('points', '[]')))
        except Exception:
            pts = []

        length = 0.0
        angle = 0.0
        
        preview = _to_uint8_bgr(img).copy()

        if inputs.get('factor') is None:
            unit = 'px'
            factor = 1.0
        else:
            calib_unit = inputs.get('unit')
            unit = str(calib_unit) if calib_unit is not None else params.get('unit', 'px')

        if len(pts) >= 2:
            p1 = (float(pts[0]['x']) * w, float(pts[0]['y']) * h)
            p2 = (float(pts[1]['x']) * w, float(pts[1]['y']) * h)
            
            dx1 = p2[0] - p1[0]
            dy1 = p2[1] - p1[1]
            dist1 = math.hypot(dx1, dy1)
            
            if len(pts) >= 3:
                p3 = (float(pts[2]['x']) * w, float(pts[2]['y']) * h)
                dx2 = p3[0] - p2[0]
                dy2 = p3[1] - p2[1]
                dist2 = math.hypot(dx2, dy2)
                
                length = (dist1 + dist2) / factor
                
                # Interior angle between (p2->p1) and (p2->p3)
                v1x, v1y = p1[0] - p2[0], p1[1] - p2[1]
                v2x, v2y = p3[0] - p2[0], p3[1] - p2[1]
                dot = v1x * v2x + v1y * v2y
                cross = v1x * v2y - v1y * v2x
                angle = math.degrees(math.atan2(abs(cross), dot))
                
                # Drawing
                ip1 = (int(round(p1[0])), int(round(p1[1])))
                ip2 = (int(round(p2[0])), int(round(p2[1])))
                ip3 = (int(round(p3[0])), int(round(p3[1])))
                
                cv2.line(preview, ip1, ip2, (0, 230, 255), 2, cv2.LINE_AA)
                cv2.line(preview, ip2, ip3, (0, 230, 255), 2, cv2.LINE_AA)
                cv2.circle(preview, ip1, 4, (0, 230, 255), -1)
                cv2.circle(preview, ip2, 4, (0, 230, 255), -1)
                cv2.circle(preview, ip3, 4, (0, 230, 255), -1)
                
                mx, my = ip2[0], ip2[1]
                label_y = max(20, my - 18)
                text = f'L: {length:.2f} {unit}  A: {angle:.1f}°'
                
            else:
                length = dist1 / factor
                
                angle_ref = int(params.get('angle_ref', 0))
                if angle_ref == 0:
                    # 0° is horizontal right (dx > 0, dy = 0)
                    angle = math.degrees(math.atan2(-dy1, dx1))
                else:
                    # 0° is vertical up (dx = 0, dy < 0)
                    angle = math.degrees(math.atan2(dx1, -dy1))
                    
                if angle < 0:
                    angle += 360.0

                # Drawing
                ip1 = (int(round(p1[0])), int(round(p1[1])))
                ip2 = (int(round(p2[0])), int(round(p2[1])))
                cv2.line(preview, ip1, ip2, (0, 230, 255), 2, cv2.LINE_AA)
                cv2.circle(preview, ip1, 4, (0, 230, 255), -1)
                cv2.circle(preview, ip2, 4, (0, 230, 255), -1)
                
                mx, my = int((p1[0] + p2[0]) / 2), int((p1[1] + p2[1]) / 2)
                label_y = max(20, my - 12)
                text = f'L: {length:.2f} {unit}'
            
            font_scale = 0.7
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0]
            tx = mx - text_size[0] // 2
            pad = 5
            cv2.rectangle(preview, (tx - pad, label_y - text_size[1] - pad), (tx + text_size[0] + pad, label_y + pad), (0, 0, 0), -1)
            cv2.putText(preview, text, (tx, label_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 230, 255), 2, cv2.LINE_AA)
        else:
            cv2.putText(preview, 'Draw 2 pts for line, 3 pts for angle',
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 180, 255), 1, cv2.LINE_AA)

        self._frame_count += 1
        if self._last_preview is None or self._frame_count % 6 == 0:
            try:
                ph = min(360, preview.shape[0])
                pw = int(ph * preview.shape[1] / preview.shape[0])
                _, buf = cv2.imencode('.jpg', cv2.resize(preview, (pw, ph)), [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        return {
            'main': preview,
            'main_preview': self._last_preview,
            'length': round(length, 3),
            'angle': round(angle, 2),
        }
