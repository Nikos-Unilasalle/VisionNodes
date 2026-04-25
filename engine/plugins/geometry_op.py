import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="geom_perspective",
    label="Perspective Warp",
    category="geom",
    icon="Maximize",
    description="Straightens a distorted area into a flat rectangle using 4 reference points.",
    inputs=[{"id": "image", "color": "image"}, {"id": "src_pts", "color": "list"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "width", "label": "Out Width", "type": "scalar", "min": 100, "max": 2000, "default": 800},
        {"id": "height", "label": "Out Height", "type": "scalar", "min": 100, "max": 2000, "default": 600}
    ]
)
class PerspectiveWarpNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        src_pts = inputs.get('src_pts')
        if img is None or src_pts is None or len(src_pts) < 4: 
            return {"main": img}
        
        h, w = img.shape[:2]
        out_w = int(params.get('width', 800))
        out_h = int(params.get('height', 600))
        
        # Convert normalized points to pixels
        pts = []
        for p in src_pts[:4]:
            x, y = 0, 0
            if isinstance(p, dict):
                # Priority 1: Simple x,y
                if 'x' in p and 'y' in p:
                    x, y = p['x'], p['y']
                # Priority 2: Graphics structure (pts list)
                elif 'pts' in p and len(p['pts']) > 0:
                    pt_val = p['pts'][0]
                    x, y = pt_val[0], pt_val[1]
                # Priority 3: Center dict
                elif 'center' in p:
                    x, y = p['center'].get('x', 0), p['center'].get('y', 0)
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                x, y = p[0], p[1]
            
            pts.append([float(x) * w, float(y) * h])
            
        src_arr = np.array(pts, dtype=np.float32)
        dst_arr = np.array([
            [0, 0],
            [out_w, 0],
            [out_w, out_h],
            [0, out_h]
        ], dtype=np.float32)
        
        matrix = cv2.getPerspectiveTransform(src_arr, dst_arr)
        result = cv2.warpPerspective(img, matrix, (out_w, out_h))
        
        return {"main": result}

@vision_node(
    type_id="util_manual_points",
    label="Manual 4 Points",
    category="geom",
    icon="MousePointer",
    description="Allows manual definition of 4 reference points on the image for calculations.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "p1", "color": "dict"},
        {"id": "p2", "color": "dict"},
        {"id": "p3", "color": "dict"},
        {"id": "p4", "color": "dict"}
    ],
    outputs=[{"id": "points", "color": "list"}],
    params=[
        {"id": "x1", "label": "P1 X", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.1},
        {"id": "y1", "label": "P1 Y", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.1},
        {"id": "x2", "label": "P2 X", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.9},
        {"id": "y2", "label": "P2 Y", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.1},
        {"id": "x3", "label": "P3 X", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.9},
        {"id": "y3", "label": "P3 Y", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.9},
        {"id": "x4", "label": "P4 X", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.1},
        {"id": "y4", "label": "P4 Y", "type": "scalar", "min": 0, "max": 1, "step": 0.001, "default": 0.9}
    ]
)
class ManualPointsNode(NodeProcessor):
    def process(self, inputs, params):
        pts = []
        for i in range(1, 5):
            # Try to get from input first
            p_in = inputs.get(f'p{i}')
            x, y = None, None
            
            if p_in and isinstance(p_in, dict):
                # Handle everything: simple {x,y}, graphics {pts:[]}, or center {center:{x,y}}
                if 'x' in p_in and 'y' in p_in:
                    x, y = p_in['x'], p_in['y']
                elif 'pts' in p_in and len(p_in['pts']) > 0:
                    pt_val = p_in['pts'][0]
                    x, y = pt_val[0], pt_val[1]
                elif 'center' in p_in:
                    x, y = p_in['center'].get('x'), p_in['center'].get('y')
            
            # Fallback to params if input is missing or invalid
            if x is None: x = params.get(f'x{i}', 0.1)
            if y is None: y = params.get(f'y{i}', 0.1)
            
            pts.append({"x": float(x), "y": float(y)})
            
        return {"points": pts}

@vision_node(
    type_id="util_roi_polygon",
    label="ROI Polygon",
    category="geom",
    icon="Scaling",
    description="Interactive polygonal mask generator to define Regions of Interest.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "main",       "color": "image"},
        {"id": "mask",       "color": "mask"},
        {"id": "masked",     "color": "image"},
        {"id": "masked_inv", "color": "image"},
        {"id": "pts",        "color": "list"}
    ],
    params=[
        {"id": "points", "label": "Points", "type": "string", "default": "[]"},
        {"id": "filled", "label": "Filled", "type": "boolean", "default": True},
        {"id": "thickness", "label": "Thickness", "type": "scalar", "min": 1, "max": 20, "default": 2}
    ]
)
class ROIPolygonNode(NodeProcessor):
    def process(self, inputs, params):
        import json, base64
        img = inputs.get('image')
        h, w = (img.shape[0], img.shape[1]) if img is not None else (480, 640)
        
        points_str = params.get('points', '[]')
        try:
            pts_data = json.loads(points_str)
        except:
            pts_data = []
            
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Performance optimization: Send a small preview for the editor
        preview_b64 = None
        if img is not None:
            # We encode every ~6 frames to save bandwidth/CPU (assuming 30fps)
            if not hasattr(self, '_frame_count'): self._frame_count = 0
            self._frame_count += 1
            if self._frame_count % 6 == 0:
                try:
                    # Resize to something reasonable for background
                    ph, pw = 720, int(720 * (w/h))
                    pimg = cv2.resize(img, (pw, ph))
                    _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    preview_b64 = base64.b64encode(buf).decode('utf-8')
                    self._last_preview = preview_b64
                except: pass
            else:
                preview_b64 = getattr(self, '_last_preview', None)

        if len(pts_data) > 0:
            # Convert normalized points to pixel coordinates
            pts_array = []
            for p in pts_data:
                if isinstance(p, dict):
                    pts_array.append([float(p.get('x', 0)) * w, float(p.get('y', 0)) * h])
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    pts_array.append([float(p[0]) * w, float(p[1]) * h])
            
            pts = np.array(pts_array, np.int32)
            
            if len(pts) >= 3:
                if params.get('filled', True):
                    cv2.fillPoly(mask, [pts], 255)
                else:
                    cv2.polylines(mask, [pts], True, 255, int(params.get('thickness', 2)))
            elif len(pts) == 2:
                 cv2.line(mask, tuple(pts[0]), tuple(pts[1]), 255, int(params.get('thickness', 2)))
        
        if img is not None:
            masked     = cv2.bitwise_and(img, img, mask=mask)
            masked_inv = cv2.bitwise_and(img, img, mask=cv2.bitwise_not(mask))
        else:
            masked = masked_inv = None

        return {"main": img, "mask": mask, "masked": masked, "masked_inv": masked_inv, "pts": pts_data, "main_preview": preview_b64}
