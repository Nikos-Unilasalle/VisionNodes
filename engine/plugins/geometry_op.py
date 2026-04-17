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
        # Expecting src_pts to be a list of 4 dicts with x, y or list of [x, y]
        pts = []
        for p in src_pts[:4]:
            if isinstance(p, dict):
                x, y = p.get('x', 0), p.get('y', 0)
                if 'center' in p: x, y = p['center']['x'], p['center']['y']
            else:
                x, y = p[0], p[1]
            pts.append([x * w, y * h])
            
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
    inputs=[{"id": "image", "color": "image"}],
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
        pts = [
            {"x": float(params.get('x1', 0.1)), "y": float(params.get('y1', 0.1))},
            {"x": float(params.get('x2', 0.9)), "y": float(params.get('y2', 0.1))},
            {"x": float(params.get('x3', 0.9)), "y": float(params.get('y3', 0.9))},
            {"x": float(params.get('x4', 0.1)), "y": float(params.get('y4', 0.9))}
        ]
        return {"points": pts}
