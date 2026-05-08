import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_overlay',
    label='Draw Overlay',
    category='draw',
    icon='PenTool',
    description="Draws graphical elements (from Draw Text, trackers, etc.) over an image. Connect graphics to the 'data' inputs.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'data', 'color': 'any'},
        {'id': 'data_2', 'color': 'any'},
        {'id': 'data_3', 'color': 'any'},
        {'id': 'data_4', 'color': 'any'}
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
        col, thick = (0, 255, 0), 2
        
        # Scan ALL inputs for graphics data
        for key, data in inputs.items():
            if data is None or key == 'image': continue
            
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get('_type') == 'graphics':
                    self._draw_graphics(res, item, w, h, col, thick)
        
        return {"main": res}

    def _draw_graphics(self, img, data, w, h, default_col, default_thick):
        shape, pts, rel = data.get('shape', 'point'), data.get('pts', []), data.get('relative', True)
        
        # Color parsing
        color = default_col
        if 'color' in data and data['color'].startswith('#'):
            hex_col = data['color'].lstrip('#')
            if len(hex_col) == 6:
                r, g, b = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
                color = (b, g, r)
        
        thick = int(data.get('thickness', default_thick))
        fill = data.get('fill', False)
        
        # Scaling points
        scaled_pts = []
        for p in pts:
            if rel:
                scaled_pts.append((int(p[0] * w), int(p[1] * h)))
            else:
                scaled_pts.append((int(p[0]), int(p[1])))
                
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
            if fill:
                cv2.fillPoly(img, [pts_arr], color)
            cv2.polylines(img, [pts_arr], True, color, max(1, thick))
            if 'label' in data:
                cv2.putText(img, data['label'], (scaled_pts[0][0], scaled_pts[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                            
        elif shape == 'circle' and len(scaled_pts) > 0:
            rad = int(data.get('radius', 0.1) * w) if rel else int(data.get('radius', 10))
            cv2.circle(img, scaled_pts[0], rad, color, max(1, thick))
            if 'label' in data:
                cv2.putText(img, data['label'], (scaled_pts[0][0] - rad, scaled_pts[0][1] - rad - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                            
        elif shape == 'text' and len(scaled_pts) > 0:
            text = str(data.get('text', data.get('label', '')))
            scale = float(data.get('font_scale', 1.0))
            cv2.putText(img, text, scaled_pts[0], cv2.FONT_HERSHEY_SIMPLEX, scale, color, max(1, thick))
