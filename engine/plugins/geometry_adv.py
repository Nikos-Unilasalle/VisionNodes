import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="geom_approx_poly",
    label="Approx. Polygon",
    category="geom",
    icon="Shapes",
    description="Simplifies a contour into a polygon with fewer vertices.",
    inputs=[{"id": "contour", "color": "dict"}],
    outputs=[{"id": "approx_contour", "color": "dict"}],
    params=[
        {"id": "epsilon_pct", "label": "Precision %", "type": "scalar", "min": 0, "max": 10, "default": 2},
        {"id": "closed", "label": "Closed", "type": "boolean", "default": True}
    ]
)
class ApproxPolyNode(NodeProcessor):
    def process(self, inputs, params):
        c_data = inputs.get('contour')
        if not c_data or 'pts' not in c_data: return {"approx_contour": None}
        
        # Convert normalized pts back to pixel-ish (doesn't matter as long as relative)
        # But for approxPolyDP it's better to have them as a numpy array.
        pts = np.array(c_data['pts'], dtype=np.float32)
        
        eps = float(params.get('epsilon_pct', 2)) / 100.0
        peri = cv2.arcLength(pts, True)
        approx_pts = cv2.approxPolyDP(pts, eps * peri, bool(params.get('closed', True)))
        
        new_c = c_data.copy()
        new_c['pts'] = approx_pts.reshape(-1, 2).tolist()
        return {"approx_contour": new_c}

@vision_node(
    type_id="geom_fit_shape",
    label="Fit Shape",
    category="geom",
    icon="Square",
    description="Calculates the bounding box or minimum area rectangle for a contour.",
    inputs=[{"id": "contour", "color": "dict"}],
    outputs=[{"id": "bbox", "color": "dict"}, {"id": "min_rect", "color": "dict"}],
    params=[
        {"id": "padding", "label": "Padding", "type": "scalar", "min": 0, "max": 0.1, "default": 0}
    ]
)
class FitShapeNode(NodeProcessor):
    def process(self, inputs, params):
        c_data = inputs.get('contour')
        if not c_data or 'pts' not in c_data: return {"bbox": None, "min_rect": None}
        
        pts = np.array(c_data['pts'], dtype=np.float32)
        
        # Bounding Box (straight)
        x, y, w, h = cv2.boundingRect(pts)
        bbox = {
            "xmin": x, "ymin": y, "width": w, "height": h,
            "label": "bbox", "_type": "graphics", "shape": "rect", 
            "pts": [[x, y], [x+w, y+h]], "color": "#ffffff", "relative": True
        }
        
        # Rotated Box
        rect = cv2.minAreaRect(pts)
        box = cv2.boxPoints(rect)
        min_rect = {
            "label": "min_rect", "_type": "graphics", "shape": "polygon",
            "pts": box.tolist(), "color": "#ff00ff", "relative": True
        }
        
        return {"bbox": bbox, "min_rect": min_rect}

@vision_node(
    type_id="geom_warp_affine",
    label="Warp Affine",
    category="geom",
    icon="Move",
    description="Applies a 2x3 affine transformation matrix to the image.",
    inputs=[{"id": "image", "color": "image"}, {"id": "matrix", "color": "any"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[]
)
class WarpAffineNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        m = inputs.get('matrix')
        if img is None or m is None: return {"main": img}
        
        h, w = img.shape[:2]
        res = cv2.warpAffine(img, np.array(m, dtype=np.float32), (w, h))
        return {"main": res}

@vision_node(
    type_id="geom_rotate_no_crop",
    label="Rotate (No Crop)",
    category="geom",
    icon="RotateCw",
    description="Rotates the image while expanding the canvas to keep all pixels visible.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "angle", "label": "Angle", "type": "scalar", "min": -180, "max": 180, "default": 0}
    ]
)
class RotateNoCropNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        
        angle = float(params.get('angle', 0))
        if angle == 0: return {"main": img}
        
        (h, w) = img.shape[:2]
        (cX, cY) = (w // 2, h // 2)
        
        M = cv2.getRotationMatrix2D((cX, cY), angle, 1.0)
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        
        nW = int((h * sin) + (w * cos))
        nH = int((h * cos) + (w * sin))
        
        M[0, 2] += (nW / 2) - cX
        M[1, 2] += (nH / 2) - cY
        
        return {"main": cv2.warpAffine(img, M, (nW, nH))}
