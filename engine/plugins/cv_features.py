import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_find_contours",
    label="Find Contours",
    category="features",
    icon="Target",
    description="Detects and extracts isolated shapes from a binary image (mask).",
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
    type_id="feat_contour_props",
    label="Contour Properties",
    category="features",
    icon="Info",
    description="Calculates geometric metrics (area, center, perimeter) of an isolated shape.",
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
    description="Adaptively improves local image contrast (CLAHE algorithm).",
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
    description="Smoothes the image while preserving edge sharpness and textures.",
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

@vision_node(
    type_id="feat_hough_circles",
    label="Hough Circles",
    category="features",
    icon="Target",
    description="Identifies perfect circular shapes using mathematical circle transforms.",
    inputs=[{"id": "image", "color": "any"}],
    outputs=[{"id": "circles_list", "color": "list"}],
    params=[
        {"id": "dp", "label": "DP", "type": "scalar", "min": 1, "max": 10, "default": 1.2},
        {"id": "min_dist", "label": "Min Dist", "type": "scalar", "min": 1, "max": 500, "default": 100},
        {"id": "param1", "label": "Canny High", "type": "scalar", "min": 1, "max": 500, "default": 100},
        {"id": "param2", "label": "Threshold", "type": "scalar", "min": 1, "max": 200, "default": 30},
        {"id": "min_r", "label": "Min Radius", "type": "scalar", "min": 0, "max": 500, "default": 0},
        {"id": "max_r", "label": "Max Radius", "type": "scalar", "min": 0, "max": 500, "default": 0}
    ]
)
class HoughCirclesNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"circles_list": []}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        dp = float(params.get('dp', 1.2))
        min_dist = float(params.get('min_dist', 100))
        p1 = float(params.get('param1', 100))
        p2 = float(params.get('param2', 30))
        min_r = int(params.get('min_r', 0))
        max_r = int(params.get('max_r', 0))
        
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp, min_dist, param1=p1, param2=p2, minRadius=min_r, maxRadius=max_r)
        
        results = []
        if circles is not None:
            h, w = gray.shape[:2]
            circles = np.uint16(np.around(circles))
            for i, c in enumerate(circles[0, :]):
                cx, cy, r = float(c[0]), float(c[1]), float(c[2])
                results.append({
                    "id": i,
                    "label": f"circle_{i}",
                    "_type": "graphics",
                    "shape": "circle",
                    "pts": [[cx / w, cy / h]],
                    "radius": r / w, # Store normalized radius based on width
                    "relative": True,
                    "color": "#ff0000"
                })
        return {"circles_list": results}

@vision_node(
    type_id="feat_hough_lines",
    label="Hough Lines",
    category="features",
    icon="Maximize",
    description="Detects straight line segments in the image (walls, joints, etc.).",
    inputs=[{"id": "image", "color": "any"}],
    outputs=[{"id": "lines_list", "color": "list"}],
    params=[
        {"id": "rho", "label": "Rho", "type": "scalar", "min": 1, "max": 10, "default": 1},
        {"id": "theta_deg", "label": "Theta (deg)", "type": "scalar", "min": 1, "max": 180, "default": 1},
        {"id": "threshold", "label": "Threshold", "type": "scalar", "min": 1, "max": 500, "default": 50},
        {"id": "min_len", "label": "Min Length", "type": "scalar", "min": 0, "max": 500, "default": 50},
        {"id": "max_gap", "label": "Max Gap", "type": "scalar", "min": 0, "max": 100, "default": 10}
    ]
)
class HoughLinesNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"lines_list": []}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        rho = float(params.get('rho', 1))
        theta = float(params.get('theta_deg', 1)) * np.pi / 180
        thresh = int(params.get('threshold', 50))
        min_len = float(params.get('min_len', 50))
        max_gap = float(params.get('max_gap', 10))
        
        lines = cv2.HoughLinesP(gray, rho, theta, thresh, minLineLength=min_len, maxLineGap=max_gap)
        
        results = []
        if lines is not None:
            h, w = gray.shape[:2]
            for i, line in enumerate(lines):
                x1, y1, x2, y2 = line[0]
                results.append({
                    "id": i,
                    "_type": "graphics",
                    "shape": "line",
                    "pts": [[float(x1/w), float(y1/h)], [float(x2/w), float(y2/h)]],
                    "relative": True,
                    "color": "#00ff00"
                })
        return {"lines_list": results}
