import cv2
import numpy as np
from registry import NodeProcessor, vision_node

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
        {"id": "min_area", "label": "Min Area",        "type": "scalar", "min": 0, "max": 100000, "default": 100},
        {"id": "max_area", "label": "Max Area (0=off)", "type": "scalar", "min": 0, "max": 100000, "default": 0}
    ]
)
class FindContoursNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"contours_list": [], "count": 0}

        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

        if mask.dtype != np.uint8:
            if mask.max() <= 1.0:
                mask = (mask * 255).clip(0, 255).astype(np.uint8)
            else:
                mask = mask.clip(0, 255).astype(np.uint8)

        modes = [cv2.RETR_EXTERNAL, cv2.RETR_LIST, cv2.RETR_CCOMP, cv2.RETR_TREE]
        methods = [cv2.CHAIN_APPROX_NONE, cv2.CHAIN_APPROX_SIMPLE, cv2.CHAIN_APPROX_TC89_L1, cv2.CHAIN_APPROX_TC89_KCOS]

        mode = modes[int(params.get('mode', 0))]
        method = methods[int(params.get('method', 1))]
        min_area = float(params.get('min_area', 100))
        max_area = float(params.get('max_area', 0))

        contours, _ = cv2.findContours(mask, mode, method)

        h, w = mask.shape[:2]
        results = []
        rank = 0
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < min_area: continue
            if max_area > 0 and area > max_area: continue

            pts = [[float(pt[0][0] / w), float(pt[0][1] / h)] for pt in cnt]

            m = cv2.moments(cnt)
            cx, cy = 0, 0
            if m["m00"] != 0:
                cx, cy = int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])

            rect = cv2.minAreaRect(cnt)
            rw, rh = rect[1]
            elongation = (max(rw, rh) / min(rw, rh)) if min(rw, rh) > 0 else 1.0
            angle = float(rect[2])

            perimeter = cv2.arcLength(cnt, True)
            circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 1.0

            hue = int((rank * 47) % 180)
            bgr = cv2.cvtColor(np.array([[[hue, 220, 230]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0][0]
            color = '#{:02x}{:02x}{:02x}'.format(int(bgr[2]), int(bgr[1]), int(bgr[0]))

            results.append({
                "id": rank,
                "label": f"#{rank}",
                "_type": "graphics",
                "shape": "polygon",
                "pts": pts,
                "area": area,
                "elongation": round(elongation, 3),
                "circularity": round(circularity, 4),
                "angle": round(angle, 2),
                "center": {"x": cx/w, "y": cy/h},
                "relative": True,
                "color": color
            })
            rank += 1
            
        return {"contours_list": results, "count": len(results)}

@vision_node(
    type_id="feat_contour_props",
    label="Contour Properties",
    category="features",
    icon="Info",
    description="Calculates geometric metrics (area, center, perimeter) of an isolated shape.",
    inputs=[{"id": "contour", "color": "dict"}],
    outputs=[
        {"id": "area",        "color": "scalar"},
        {"id": "circularity", "color": "scalar"},
        {"id": "elongation",  "color": "scalar"},
        {"id": "center_x",    "color": "scalar"},
        {"id": "center_y",    "color": "scalar"}
    ]
)
class ContourInfoNode(NodeProcessor):
    def process(self, inputs, params):
        c = inputs.get('contour')
        if not c or not isinstance(c, dict):
            return {"area": 0, "circularity": 0, "elongation": 1, "center_x": 0, "center_y": 0}
        return {
            "area":        c.get("area", 0),
            "circularity": c.get("circularity", 0),
            "elongation":  c.get("elongation", 1),
            "center_x":    c.get("center", {}).get("x", 0),
            "center_y":    c.get("center", {}).get("y", 0)
        }

@vision_node(
    type_id="feat_clahe",
    label="CLAHE (Contrast)",
    category="cv",
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
    category="cv",
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
    type_id="feat_filter_contours",
    label="Filter Contours",
    category="features",
    icon="Filter",
    description="Filters a contour list by elongation (long/short axis ratio) and/or area. Use min_elongation > 1 to keep only elongated shapes like rivers.",
    inputs=[{"id": "contours", "color": "list"}],
    outputs=[
        {"id": "contours_list", "color": "list"},
        {"id": "count",         "color": "scalar"}
    ],
    params=[
        {"id": "max_circularity", "label": "Max Circularity (0=off)", "type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
        {"id": "min_circularity", "label": "Min Circularity (0=off)", "type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
        {"id": "min_elongation",  "label": "Min Elongation (1=off)",  "type": "float", "default": 1.0, "min": 1.0, "max": 100.0, "step": 0.5},
        {"id": "max_elongation",  "label": "Max Elongation (0=off)",  "type": "float", "default": 0.0, "min": 0.0, "max": 100.0, "step": 0.5},
        {"id": "min_area",        "label": "Min Area (0=off)",        "type": "float", "default": 0.0, "min": 0.0, "max": 100000},
        {"id": "max_area",        "label": "Max Area (0=off)",        "type": "float", "default": 0.0, "min": 0.0, "max": 100000},
    ]
)
class FilterContoursNode(NodeProcessor):
    def process(self, inputs, params):
        contours = inputs.get('contours') or []
        max_circ = float(params.get('max_circularity', 0.0))
        min_circ = float(params.get('min_circularity', 0.0))
        min_elo  = float(params.get('min_elongation', 1.0))
        max_elo  = float(params.get('max_elongation', 0.0))
        min_area = float(params.get('min_area', 0.0))
        max_area = float(params.get('max_area', 0.0))

        results = []
        for c in contours:
            if not isinstance(c, dict):
                continue
            circ = float(c.get('circularity', 1.0))
            elo  = float(c.get('elongation', 1.0))
            area = float(c.get('area', 0.0))
            if max_circ > 0.0 and circ > max_circ:
                continue
            if min_circ > 0.0 and circ < min_circ:
                continue
            if min_elo > 1.0 and elo < min_elo:
                continue
            if max_elo > 0.0 and elo > max_elo:
                continue
            if min_area > 0.0 and area < min_area:
                continue
            if max_area > 0.0 and area > max_area:
                continue
            results.append(c)

        return {"contours_list": results, "count": len(results)}


@vision_node(
    type_id="feat_fill_contours",
    label="Fill Contours",
    category="features",
    icon="Pentagon",
    description="Fills all contours from a list into a binary mask (union). Connect contours_list from Find Contours.",
    inputs=[
        {"id": "contours", "color": "list"},
        {"id": "image",    "color": "image"}
    ],
    outputs=[
        {"id": "mask",  "color": "mask"},
        {"id": "main",  "color": "image"}
    ],
    params=[
        {"id": "width",  "label": "Width (fallback)",  "type": "int", "default": 512, "min": 1, "max": 4096},
        {"id": "height", "label": "Height (fallback)", "type": "int", "default": 512, "min": 1, "max": 4096}
    ]
)
class FillContoursNode(NodeProcessor):
    def process(self, inputs, params):
        contours = inputs.get('contours') or []
        img = inputs.get('image')

        if img is not None:
            h, w = img.shape[:2]
            out = img.copy()
            if len(out.shape) == 2:
                out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        else:
            w = int(params.get('width', 512))
            h = int(params.get('height', 512))
            out = np.zeros((h, w, 3), dtype=np.uint8)

        mask = np.zeros((h, w), dtype=np.uint8)

        for c in contours:
            if not isinstance(c, dict) or 'pts' not in c:
                continue
            rel = c.get('relative', True)
            pts_raw = c['pts']
            if rel:
                px = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts_raw], dtype=np.int32)
            else:
                px = np.array([[int(p[0]), int(p[1])] for p in pts_raw], dtype=np.int32)
            if len(px) < 3:
                continue
            cv2.fillPoly(mask, [px], 255)
            color_hex = c.get('color', '#00ff00').lstrip('#')
            bgr = tuple(int(color_hex[i:i+2], 16) for i in (4, 2, 0))
            cv2.fillPoly(out, [px], bgr)

        return {"mask": mask, "main": out}


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
