import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="feat_find_contours",
    label="Find Contours",
    category='segmentation',
    icon="Target",
    description="Detects and extracts isolated shapes from a binary image (mask).",
    inputs=[{"id": "mask", "color": "any"}],
    outputs=[{"id": "contours_list", "color": "contours"}, {"id": "count", "color": "scalar"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["External", "List", "CComp", "Tree"], "default": 0},
        {"id": "method", "label": "Method", "type": "enum", "options": ["None", "Simple", "TC89_L1", "TC89_KCOS"], "default": 1},
        {"id": "min_area", "label": "Min Area",        "type": "scalar", "min": 0, "max": 100000, "default": 100},
        {"id": "max_area", "label": "Max Area (0=off)", "type": "scalar", "min": 0, "max": 100000, "default": 0},
        {"id": "epsilon",  "label": "Simplification (Epsilon px)", "type": "float", "min": 0.0, "max": 50.0, "step": 0.5, "default": 0.0}
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
        epsilon = float(params.get('epsilon', 0.0))

        contours, _ = cv2.findContours(mask, mode, method)

        h, w = mask.shape[:2]
        results = []
        rank = 0
        for i, cnt in enumerate(contours):
            # Polygonal simplification (Douglas–Peucker): smooths jagged edges,
            # which lifts perimeter-based circularity while leaving overall
            # roundness (max-diameter based) largely untouched (ch1 §1.9).
            if epsilon > 0:
                cnt = cv2.approxPolyDP(cnt, epsilon, True)

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
    category='segmentation',
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
    category='image',
    icon="Maximize",
    description="Adaptive local contrast enhancement (CLAHE). Choose the color "
                "space to operate in, dose the effect, and optionally restrict it "
                "to a mask region. 'Auto Clip' derives the clip limit from local "
                "contrast; the 'luma' output exposes the equalized luminance channel.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "mask", "color": "mask"},
    ],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "luma", "color": "image"},
    ],
    params=[
        {"id": "auto_clip", "label": "Auto Clip", "type": "bool", "default": False},
        {"id": "clip_limit", "label": "Clip Limit", "type": "float",
         "min": 0.5, "max": 40, "step": 0.5, "default": 2},
        {"id": "grid_size", "label": "Tile Grid Size", "type": "scalar",
         "min": 1, "max": 32, "default": 8},
        {"id": "color_space", "label": "Operate On", "type": "enum",
         "options": ["LAB (luminance)", "YCrCb (luma)", "HSV (value)",
                     "Per-channel RGB", "Grayscale out"], "default": 0},
        {"id": "strength", "label": "Strength (blend)", "type": "float",
         "min": 0, "max": 1, "step": 0.05, "default": 1},
    ]
)
class ClaheNode(NodeProcessor):
    def _luma_proxy(self, img, mode):
        """Single-channel image CLAHE will actually operate on, used both for
        the auto-clip heuristic and as the 'luma' output."""
        if img.ndim == 2:
            return img
        if mode == 2:  # HSV value
            return cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 2]
        if mode == 1:  # YCrCb luma
            return cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)[:, :, 0]
        if mode == 0:  # LAB lightness
            return cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[:, :, 0]
        # per-channel / grayscale-out: perceptual gray is the meaningful proxy
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _auto_clip(luma):
        """Flat / low-contrast images get a stronger clip limit; contrasty ones
        get a gentle one. Tuned so std~20 -> ~8, std~70 -> ~2.3, clamped [1, 16]."""
        std = float(luma.std())
        return float(np.clip(160.0 / max(std, 1.0), 1.0, 16.0))

    def _equalize(self, img, clahe, mode):
        """Returns (result, equalized_luma). result matches input channels."""
        if img.ndim == 2:  # Grayscale input
            out = clahe.apply(img)
            return out, out

        if mode == 4:  # Grayscale output
            cl = clahe.apply(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            return cv2.cvtColor(cl, cv2.COLOR_GRAY2BGR), cl
        if mode == 3:  # Per-channel RGB (stronger, can shift hues)
            b, g, r = cv2.split(img)
            res = cv2.merge((clahe.apply(b), clahe.apply(g), clahe.apply(r)))
            return res, cv2.cvtColor(res, cv2.COLOR_BGR2GRAY)
        if mode == 1:  # YCrCb — equalize luma
            y, cr, cb = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb))
            cl = clahe.apply(y)
            return cv2.cvtColor(cv2.merge((cl, cr, cb)), cv2.COLOR_YCrCb2BGR), cl
        if mode == 2:  # HSV — equalize value
            h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
            cl = clahe.apply(v)
            return cv2.cvtColor(cv2.merge((h, s, cl)), cv2.COLOR_HSV2BGR), cl
        # LAB (default) — equalize lightness, preserves color best
        l, a, b = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2LAB))
        cl = clahe.apply(l)
        return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR), cl

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None, "luma": None}

        grid = max(1, int(params.get('grid_size', 8)))
        mode = int(params.get('color_space', 0))
        strength = min(1.0, max(0.0, float(params.get('strength', 1.0))))

        if bool(params.get('auto_clip', False)):
            clip = self._auto_clip(self._luma_proxy(img, mode))
        else:
            clip = max(0.01, float(params.get('clip_limit', 2.0)))

        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
        result, luma = self._equalize(img, clahe, mode)

        # Grayscale-out mode promotes a 2D input to BGR; align the original.
        base = img
        if result.ndim == 3 and base.ndim == 2:
            base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)

        # Dose the effect: blend the enhanced result back with the original.
        if strength < 1.0:
            result = cv2.addWeighted(result, strength, base, 1.0 - strength, 0)

        # Optional mask: enhance only inside the mask, soft-composited.
        mask = inputs.get('mask')
        if mask is not None:
            if mask.ndim == 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            if mask.shape[:2] != base.shape[:2]:
                mask = cv2.resize(mask, (base.shape[1], base.shape[0]), interpolation=cv2.INTER_NEAREST)
            alpha = mask.astype(np.float32) / 255.0
            ca = alpha[:, :, None] if base.ndim == 3 else alpha
            result = (result.astype(np.float32) * ca + base.astype(np.float32) * (1.0 - ca)).astype(base.dtype)

        return {"main": result, "luma": luma}

@vision_node(
    type_id="feat_bilateral",
    label="Bilateral Filter",
    category='image',
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
    category='segmentation',
    icon="Target",
    description=(
        "Identifies perfect circular shapes in the image.\n\n"
        "Parameters:\n"
        "- DP: Inverse ratio of accumulator resolution (1.0 = full, 1.2 = recommended).\n"
        "- Min Dist: Minimum distance between centers of detected circles.\n"
        "- Canny High: Upper threshold for internal edge detection.\n"
        "- Threshold: Center accumulator threshold (lower = more circles, but more noise).\n"
        "- Min/Max Radius: Bounds for detected circle size in pixels."
    ),
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "mask",  "color": "mask"}
    ],
    outputs=[
        {"id": "main",         "color": "image"},
        {"id": "mask",         "color": "mask"},
        {"id": "labels_map",   "color": "markers", "label": "Labels"},
        {"id": "circles_list", "color": "list"},
        {"id": "count",        "color": "scalar"}
    ],
    params=[
        {"id": "dp",        "label": "DP",          "type": "scalar", "min": 1.0, "max": 10.0, "default": 1.2},
        {"id": "min_dist",  "label": "Min Dist",    "type": "scalar", "min": 1.0, "max": 1000.0, "default": 100.0},
        {"id": "param1",    "label": "Canny High",  "type": "scalar", "min": 1.0, "max": 500.0, "default": 100.0},
        {"id": "param2",    "label": "Threshold",   "type": "scalar", "min": 1.0, "max": 500.0, "default": 30.0},
        {"id": "min_r",     "label": "Min Radius",  "type": "scalar", "min": 0, "max": 2000, "default": 0},
        {"id": "max_r",     "label": "Max Radius",  "type": "scalar", "min": 0, "max": 2000, "default": 0},
        {"id": "viz_color", "label": "Viz Color",   "type": "color", "default": "#00FF00"},
        {"id": "thickness", "label": "Thickness",   "type": "scalar", "min": -1, "max": 20, "default": 2}
    ]
)
class HoughCirclesNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        mask_in = inputs.get('mask')
        
        # Decide source image
        if image is not None:
            source = image
        elif mask_in is not None:
            source = mask_in
        else:
            return {"main": None, "mask": None, "circles_list": [], "count": 0}
            
        h, w = source.shape[:2]
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY) if len(source.shape) == 3 else source
        
        if image is not None and mask_in is not None:
            # Restricted detection: apply mask to image
            if mask_in.shape[:2] != (h, w):
                mask_in = cv2.resize(mask_in, (w, h), interpolation=cv2.INTER_NEAREST)
            gray = cv2.bitwise_and(gray, gray, mask=mask_in)
        
        dp = float(params.get('dp', 1.2))
        min_dist = float(params.get('min_dist', 100.0))
        p1 = float(params.get('param1', 100.0))
        p2 = float(params.get('param2', 30.0))
        min_r = int(params.get('min_r', 0))
        max_r = int(params.get('max_r', 0))
        
        color_hex = str(params.get('viz_color', '#00FF00')).lstrip('#')
        bgr = tuple(int(color_hex[i:i+2], 16) for i in (4, 2, 0))
        thick = int(params.get('thickness', 2))
        
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp, min_dist, param1=p1, param2=p2, minRadius=min_r, maxRadius=max_r)
        
        results = []
        out_img = source.copy()
        if len(out_img.shape) == 2:
            out_img = cv2.cvtColor(out_img, cv2.COLOR_GRAY2BGR)
        mask = np.zeros((h, w), dtype=np.uint8)
        labels_map = np.zeros((h, w), dtype=np.int32)
        
        if circles is not None:
            circles = np.around(circles[0, :]).astype(np.int32)
            for i, c in enumerate(circles):
                cx, cy, r = int(c[0]), int(c[1]), int(c[2])
                
                # Draw on image
                cv2.circle(out_img, (cx, cy), r, bgr, thick)
                # Draw on mask
                cv2.circle(mask, (cx, cy), r, 255, -1) 
                # Draw on labels_map (unique ID)
                cv2.circle(labels_map, (cx, cy), r, i + 1, -1)
                
                results.append({
                    "id": i + 1,
                    "label": f"circle_{i+1}",
                    "_type": "graphics",
                    "shape": "circle",
                    "pts": [[float(cx / w), float(cy / h)]],
                    "radius": float(r),
                    "radius_rel": float(r / w),
                    "area": float(np.pi * (r ** 2)),
                    "relative": True,
                    "color": f"#{color_hex}"
                })
                
        return {
            "main": out_img,
            "mask": mask,
            "labels_map": labels_map,
            "circles_list": results,
            "count": float(len(results))
        }

@vision_node(
    type_id="feat_filter_contours",
    label="Filter Contours",
    category='segmentation',
    icon="Filter",
    description="Filters a contour list by elongation (long/short axis ratio) and/or area. Use min_elongation > 1 to keep only elongated shapes like rivers. Connect an image to preview the kept contours.",
    inputs=[
        {"id": "contours", "color": "contours"},
        {"id": "image",    "color": "image", "label": "Image (preview)"}
    ],
    outputs=[
        {"id": "contours_list", "color": "contours"},
        {"id": "main",          "color": "image", "label": "Overlay"},
        {"id": "count",         "color": "scalar"}
    ],
    params=[
        {"id": "max_circularity", "label": "Max Circularity (0=off)", "type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
        {"id": "min_circularity", "label": "Min Circularity (0=off)", "type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
        {"id": "min_elongation",  "label": "Min Elongation (1=off)",  "type": "float", "default": 1.0, "min": 1.0, "max": 100.0, "step": 0.5},
        {"id": "max_elongation",  "label": "Max Elongation (0=off)",  "type": "float", "default": 0.0, "min": 0.0, "max": 100.0, "step": 0.5},
        {"id": "min_area",        "label": "Min Area (0=off)",        "type": "float", "default": 0.0, "min": 0.0, "max": 100000},
        {"id": "max_area",        "label": "Max Area (0=off)",        "type": "float", "default": 0.0, "min": 0.0, "max": 100000},
        {"id": "show_rejected",   "label": "Show Rejected (red)",     "type": "bool",  "default": True},
        {"id": "fill",            "label": "Fill Kept",               "type": "bool",  "default": False},
        {"id": "thickness",       "label": "Outline Thickness",       "type": "int",   "default": 2, "min": 1, "max": 8},
    ]
)
class FilterContoursNode(NodeProcessor):
    def _keep(self, c: dict, params: dict) -> bool:
        max_circ = float(params.get('max_circularity', 0.0))
        min_circ = float(params.get('min_circularity', 0.0))
        min_elo  = float(params.get('min_elongation', 1.0))
        max_elo  = float(params.get('max_elongation', 0.0))
        min_area = float(params.get('min_area', 0.0))
        max_area = float(params.get('max_area', 0.0))
        circ = float(c.get('circularity', 1.0))
        elo  = float(c.get('elongation', 1.0))
        area = float(c.get('area', 0.0))
        if max_circ > 0.0 and circ > max_circ:
            return False
        if min_circ > 0.0 and circ < min_circ:
            return False
        if min_elo > 1.0 and elo < min_elo:
            return False
        if max_elo > 0.0 and elo > max_elo:
            return False
        if min_area > 0.0 and area < min_area:
            return False
        if max_area > 0.0 and area > max_area:
            return False
        return True

    def _to_px(self, c: dict, w: int, h: int):
        pts_raw = c.get('pts')
        if not pts_raw or len(pts_raw) < 3:
            return None
        if c.get('relative', True):
            px = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts_raw], dtype=np.int32)
        else:
            px = np.array([[int(p[0]), int(p[1])] for p in pts_raw], dtype=np.int32)
        return px

    def process(self, inputs, params):
        contours = inputs.get('contours') or []
        image    = inputs.get('image')

        results  = []
        rejected = []
        for c in contours:
            if not isinstance(c, dict):
                continue
            (results if self._keep(c, params) else rejected).append(c)

        # Build preview overlay if an image is connected
        overlay = None
        if image is not None and hasattr(image, 'shape'):
            overlay = image.copy()
            if overlay.ndim == 2:
                overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2BGR)
            h, w = overlay.shape[:2]
            thick = int(params.get('thickness', 2))
            do_fill = bool(params.get('fill', False))

            if bool(params.get('show_rejected', True)):
                for c in rejected:
                    px = self._to_px(c, w, h)
                    if px is not None:
                        cv2.polylines(overlay, [px], True, (60, 60, 200), 1)

            for c in results:
                px = self._to_px(c, w, h)
                if px is None:
                    continue
                color_hex = str(c.get('color', '#00ff00')).lstrip('#')
                try:
                    bgr = tuple(int(color_hex[i:i+2], 16) for i in (4, 2, 0))
                except Exception:
                    bgr = (0, 255, 0)
                if do_fill:
                    layer = overlay.copy()
                    cv2.fillPoly(layer, [px], bgr)
                    overlay = cv2.addWeighted(overlay, 0.6, layer, 0.4, 0)
                cv2.polylines(overlay, [px], True, bgr, thick)

        return {"contours_list": results, "main": overlay, "count": len(results)}


@vision_node(
    type_id="feat_fill_contours",
    label="Fill Contours",
    category='segmentation',
    icon="Pentagon",
    description="Fills all contours from a list into a binary mask (union). Connect contours_list from Find Contours.",
    inputs=[
        {"id": "contours", "color": "contours"},
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
    category='segmentation',
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
