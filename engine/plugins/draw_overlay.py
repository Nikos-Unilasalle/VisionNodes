import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_overlay',
    label='Draw Overlay',
    category='draw',
    icon='PenTool',
    description="Draws graphical elements and AI detections over an image. Supports dynamic multi-inputs.",
    dynamic_inputs=True,
    inputs=[
        {'id': 'image', 'color': 'image'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}]
)
class DrawOverlayNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image', inputs.get('main', inputs.get('raw_frame')))
        if img is None: return {"main": None}
        res = img.copy()
        if len(res.shape) == 2: res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)
        h, w = res.shape[:2]
        
        # Default styling
        default_col, default_thick = (0, 255, 0), 2
        
        # Scan ALL inputs (including dynamic ports)
        for key, data in inputs.items():
            if data is None or key == 'image': continue
            
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item is None: continue
                
                # CASE 1: Explicit graphics objects (_type: 'graphics')
                if isinstance(item, dict) and item.get('_type') == 'graphics':
                    self._draw_graphics(res, item, w, h, default_col, default_thick)
                
                # CASE 2: Raw Point List (Contours / Polygons)
                elif isinstance(item, list) and len(item) > 0:
                    pts_arr = []
                    for p in item:
                        if isinstance(p, (list, tuple, np.ndarray)) and len(p) >= 2:
                            pts_arr.append([int(p[0] * w), int(p[1] * h)])
                    
                    if len(pts_arr) > 2:
                        pts_np = np.array(pts_arr, np.int32).reshape((-1, 1, 2))
                        # Use a color based on the input key or index to distinguish contours
                        idx = items.index(item)
                        color = [
                            int((idx * 67 + 40) % 200 + 55),
                            int((idx * 137 + 80) % 200 + 55),
                            int((idx * 197 + 120) % 200 + 55)
                        ]
                        cv2.polylines(res, [pts_np], True, color, default_thick)
                    elif len(pts_arr) > 0:
                        for p in pts_arr:
                            cv2.circle(res, tuple(p), 2, default_col, -1)

                # CASE 3: Raw AI Detection (xmin, ymin, ...)
                elif isinstance(item, dict) and 'xmin' in item and 'ymin' in item:
                    x1 = int(item['xmin'] * w)
                    y1 = int(item['ymin'] * h)
                    if 'width' in item and 'height' in item:
                        x2 = x1 + int(item['width'] * w)
                        y2 = y1 + int(item['height'] * h)
                    elif 'xmax' in item and 'ymax' in item:
                        x2 = int(item['xmax'] * w)
                        y2 = int(item['ymax'] * h)
                    else:
                        continue
                    
                    # Style from item or default
                    color = self._parse_color(item.get('color', '#00ff00'))
                    thick = int(item.get('thickness', default_thick))
                    
                    cv2.rectangle(res, (x1, y1), (x2, y2), color, thick)
                    
                    # Label
                    label = item.get('label', item.get('class', ''))
                    conf = item.get('confidence', item.get('score'))
                    if conf is not None: label += f" {float(conf):.2f}"
                    if label:
                        cv2.putText(res, label, (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                                    
                # CASE 4: Landmarks
                elif isinstance(item, dict) and 'landmarks' in item:
                    color = self._parse_color(item.get('color', '#0000ff'))
                    for lm in item['landmarks']:
                        lx, ly = int(lm['x'] * w), int(lm['y'] * h)
                        cv2.circle(res, (lx, ly), 2, color, -1)
        
        return {"main": res}

    def _parse_color(self, color_str):
        if isinstance(color_str, (list, tuple)) and len(color_str) == 3:
            return color_str
        if isinstance(color_str, str) and color_str.startswith('#'):
            hex_col = color_str.lstrip('#')
            if len(hex_col) == 6:
                r, g, b = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
                return (b, g, r)
        return (0, 255, 0)

    def _draw_graphics(self, img, data, w, h, default_col, default_thick):
        shape, pts, rel = data.get('shape', 'point'), data.get('pts', []), data.get('relative', True)
        color = self._parse_color(data.get('color', default_col))
        thick = int(data.get('thickness', default_thick))
        fill = data.get('fill', False)
        
        scaled_pts = []
        for p in pts:
            if rel: scaled_pts.append((int(p[0] * w), int(p[1] * h)))
            else: scaled_pts.append((int(p[0]), int(p[1])))
                
        if not scaled_pts and shape != 'text': return

        if shape == 'point' and len(scaled_pts) > 0:
            cv2.circle(img, scaled_pts[0], max(1, thick), color, -1)
        elif shape == 'line' and len(scaled_pts) >= 2:
            cv2.line(img, scaled_pts[0], scaled_pts[1], color, max(1, thick))
        elif shape == 'rect' and len(scaled_pts) >= 2:
            cv2.rectangle(img, scaled_pts[0], scaled_pts[1], color, -1 if fill else max(1, thick))
            if 'label' in data:
                cv2.putText(img, data['label'], (scaled_pts[0][0], scaled_pts[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif shape == 'polygon' and len(scaled_pts) > 2:
            pts_arr = np.array(scaled_pts, np.int32).reshape((-1, 1, 2))
            if fill: cv2.fillPoly(img, [pts_arr], color)
            cv2.polylines(img, [pts_arr], True, color, max(1, thick))
            if 'label' in data:
                cv2.putText(img, data['label'], (scaled_pts[0][0], scaled_pts[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif shape == 'circle' and len(scaled_pts) > 0:
            rad = int(data.get('radius_rel', data.get('radius', 0.1)) * w) if rel else int(data.get('radius', 10))
            cv2.circle(img, scaled_pts[0], rad, color, max(1, thick))
            if 'label' in data:
                cv2.putText(img, data['label'], (scaled_pts[0][0] - rad, scaled_pts[0][1] - rad - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        elif shape == 'text' and len(scaled_pts) > 0:
            text = str(data.get('text', data.get('label', '')))
            scale = float(data.get('font_scale', 1.0))
            cv2.putText(img, text, scaled_pts[0], cv2.FONT_HERSHEY_SIMPLEX, scale, color, max(1, thick))
