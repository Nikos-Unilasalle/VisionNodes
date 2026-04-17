import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_find_contours",
    label="Find Contours",
    category="features",
    icon="Target",
    inputs=[{"id": "mask", "color": "any"}],
    outputs=[{"id": "contours_list", "color": "list"}, {"id": "count", "color": "scalar"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["External", "List", "CComp", "Tree"], "default": 0},
        {"id": "method", "label": "Method", "type": "enum", "options": ["None", "Simple", "TC89_L1", "TC89_KCOS"], "default": 1},
        {"id": "min_area", "label": "Min Area", "type": "scalar", "min": 0, "max": 10000, "default": 100}
    ]
)
class FindContoursNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"contours_list": [], "count": 0}
        
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            
        modes = [cv2.RETR_EXTERNAL, cv2.RETR_LIST, cv2.RETR_CCOMP, cv2.RETR_TREE]
        methods = [cv2.CHAIN_APPROX_NONE, cv2.CHAIN_APPROX_SIMPLE, cv2.CHAIN_APPROX_TC89_L1, cv2.CHAIN_APPROX_TC89_KCOS]
        
        mode = modes[int(params.get('mode', 0))]
        method = methods[int(params.get('method', 1))]
        min_area = float(params.get('min_area', 100))
        
        contours, _ = cv2.findContours(mask, mode, method)
        
        h, w = mask.shape[:2]
        results = []
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < min_area: continue
            
            # Normalize points for UI (0-1)
            pts = []
            for pt in cnt:
                pts.append([float(pt[0][0] / w), float(pt[0][1] / h)])
            
            # Prepare for Overlay node
            m = cv2.moments(cnt)
            cx, cy = 0, 0
            if m["m00"] != 0:
                cx, cy = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])

            results.append({
                "id": i,
                "label": f"id_{i}",
                "_type": "graphics",
                "shape": "polygon",
                "pts": pts,
                "area": area,
                "center": {"x": cx/w, "y": cy/h},
                "relative": True,
                "color": "#00ff00"
            })
            
        return {"contours_list": results, "count": len(results)}

@vision_node(
    type_id="feat_contour_info",
    label="Contour Properties",
    category="features",
    icon="Info",
    inputs=[{"id": "contour", "color": "dict"}],
    outputs=[
        {"id": "area", "color": "scalar"},
        {"id": "center_x", "color": "scalar"},
        {"id": "center_y", "color": "scalar"}
    ]
)
class ContourInfoNode(NodeProcessor):
    def process(self, inputs, params):
        c = inputs.get('contour')
        if not c or not isinstance(c, dict): 
            return {"area": 0, "center_x": 0, "center_y": 0}
        
        return {
            "area": c.get("area", 0),
            "center_x": c.get("center", {}).get("x", 0),
            "center_y": c.get("center", {}).get("y", 0)
        }

@vision_node(
    type_id="feat_clahe",
    label="CLAHE (Contrast)",
    category="features",
    icon="Maximize",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "clip_limit", "label": "Clip Limit", "type": "scalar", "min": 1, "max": 10, "default": 2},
        {"id": "grid_size", "label": "Grid Size", "type": "scalar", "min": 1, "max": 16, "default": 8}
    ]
)
class ClaheNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        
        clip = float(params.get('clip_limit', 2.0))
        grid = int(params.get('grid_size', 8))
        
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
        
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            return {"main": cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)}
        else:
            return {"main": clahe.apply(img)}

@vision_node(
    type_id="feat_bilateral",
    label="Bilateral Filter",
    category="features",
    icon="Wind",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "diameter", "label": "Diameter", "type": "scalar", "min": 1, "max": 25, "default": 9},
        {"id": "sigma_color", "label": "Sigma Color", "type": "scalar", "min": 1, "max": 150, "default": 75},
        {"id": "sigma_space", "label": "Sigma Space", "type": "scalar", "min": 1, "max": 150, "default": 75}
    ]
)
class BilateralFilterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        
        d = int(params.get('diameter', 9))
        sc = float(params.get('sigma_color', 75))
        ss = float(params.get('sigma_space', 75))
        
        return {"main": cv2.bilateralFilter(img, d, sc, ss)}
