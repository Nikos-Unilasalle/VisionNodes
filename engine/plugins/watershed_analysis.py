import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_threshold_adv",
    label="Threshold (Advanced)",
    category="features",
    icon="Layers",
    description="Advanced thresholding including Otsu's method and relative percentage thresholds.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Binary", "Binary Inv", "Otsu", "Otsu Inv", "70% of Max"], "default": 0},
        {"id": "threshold", "label": "Value", "type": "scalar", "min": 0, "max": 255, "default": 127}
    ]
)
class AdvancedThresholdNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None, "mask": None}
        
        # Convert to gray if needed
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        mode = int(params.get('mode', 0))
        val = int(params.get('threshold', 127))
        
        res = None
        if mode == 0: # Binary
            _, res = cv2.threshold(gray, val, 255, cv2.THRESH_BINARY)
        elif mode == 1: # Binary Inv
            _, res = cv2.threshold(gray, val, 255, cv2.THRESH_BINARY_INV)
        elif mode == 2: # Otsu
            _, res = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif mode == 3: # Otsu Inv
            _, res = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        elif mode == 4: # Percentage of Max
            max_val = np.max(gray)
            if max_val > 0:
                _, res = cv2.threshold(gray, 0.7 * max_val, 255, cv2.THRESH_BINARY)
            else:
                res = np.zeros_like(gray)
        
        # Ensure output is uint8 for preview and subsequent nodes
        if res is not None:
            res = res.astype(np.uint8)
            
        return {"main": res, "mask": res}

@vision_node(
    type_id="feat_morphology_adv",
    label="Morphology (Advanced)",
    category="features",
    icon="Wind",
    description="Advanced morphological operations like Opening, Closing, and Gradient.",
    inputs=[{"id": "mask", "color": "any"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "operation", "label": "Operation", "type": "enum", "options": ["Opening", "Closing", "Gradient", "Top Hat", "Black Hat"], "default": 0},
        {"id": "shape", "label": "Kernel Shape", "type": "enum", "options": ["Rect", "Cross", "Ellipse"], "default": 0},
        {"id": "size", "label": "Kernel Size", "type": "scalar", "min": 1, "max": 31, "step": 2, "default": 5},
        {"id": "iterations", "label": "Iterations", "type": "scalar", "min": 1, "max": 10, "default": 1}
    ]
)
class AdvancedMorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"mask": None}
        
        # Ensure grayscale uint8
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = mask.astype(np.uint8)
            
        op_idx = int(params.get('operation', 0))
        ops = [cv2.MORPH_OPEN, cv2.MORPH_CLOSE, cv2.MORPH_GRADIENT, cv2.MORPH_TOPHAT, cv2.MORPH_BLACKHAT]
        op = ops[min(op_idx, len(ops)-1)]
        
        sh_idx = int(params.get('shape', 0))
        shapes = [cv2.MORPH_RECT, cv2.MORPH_CROSS, cv2.MORPH_ELLIPSE]
        shape = shapes[min(sh_idx, len(shapes)-1)]
        
        size = int(params.get('size', 5))
        if size < 1: size = 1
        kernel = cv2.getStructuringElement(shape, (size, size))
        
        iters = int(params.get('iterations', 1))
        
        res = cv2.morphologyEx(mask, op, kernel, iterations=iters)
        return {"mask": res}

@vision_node(
    type_id="feat_distance_transform",
    label="Distance Transform",
    category="features",
    icon="Maximize",
    description="Calculates the distance from each pixel to the nearest zero pixel (mask border).",
    inputs=[{"id": "mask", "color": "any"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "dist_map", "color": "any"}],
    params=[
        {"id": "dist_type", "label": "Dist Type", "type": "enum", "options": ["L2 (Euclidean)", "L1 (Manhattan)", "C (Chessboard)"], "default": 0},
        {"id": "mask_size", "label": "Mask Size", "type": "enum", "options": ["3", "5", "Precise"], "default": 1}
    ]
)
class DistanceTransformNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"main": None, "dist_map": None}
        
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = mask.astype(np.uint8)
            
        dist_types = [cv2.DIST_L2, cv2.DIST_L1, cv2.DIST_C]
        mask_sizes = [3, 5, 0] # 0 for DIST_MASK_PRECISE
        
        dt = dist_types[int(params.get('dist_type', 0))]
        ms = mask_sizes[int(params.get('mask_size', 1))]
        
        # Watershed logic usually uses L2 with 5x5 or Precise
        dist_map = cv2.distanceTransform(mask, dt, ms)
        
        # For visualization, normalize to 0-255
        vis = cv2.normalize(dist_map, None, 0, 255, cv2.NORM_MINMAX)
        return {"main": vis.astype(np.uint8), "dist_map": dist_map}

@vision_node(
    type_id="feat_connected_components",
    label="Markers (Connected)",
    category="features",
    icon="Database",
    description="Labels connected regions in a binary image. Each region gets a unique ID (Markers).",
    inputs=[{"id": "mask", "color": "any"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "markers", "color": "any"}, {"id": "count", "color": "scalar"}],
    params=[]
)
class ConnectedComponentsNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"main": None, "markers": None, "count": 0}
        
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = mask.astype(np.uint8)
            
        # connectedComponents returns num_labels and marker image (int32)
        count, markers = cv2.connectedComponents(mask)
        
        # Visualize markers (labels * step to see colors)
        vis = (markers.astype(np.float32) * (255 / max(1, count))).astype(np.uint8)
        color_vis = cv2.applyColorMap(vis, cv2.COLORMAP_JET)
        color_vis[markers == 0] = 0 # background stay black
        
        return {"main": color_vis, "markers": markers, "count": count - 1} # count - 1 to exclude background

@vision_node(
    type_id="feat_watershed",
    label="Watershed",
    category="features",
    icon="Target",
    description="Separates overlapping objects using marker-controlled watershed algorithm.",
    inputs=[{"id": "image", "color": "image"}, {"id": "markers", "color": "any"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "markers_out", "color": "any"}],
    params=[
        {"id": "draw_boundaries", "label": "Draw Boundaries", "type": "enum", "options": ["No", "Yes"], "default": 1}
    ]
)
class WatershedNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        markers = inputs.get('markers')
        if img is None or markers is None: return {"main": img, "markers_out": markers}
        
        # Ensure img is 3-channel BGR
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        # cv2.watershed expects int32 markers and BGR image
        # It modifies markers in-place
        markers_copy = markers.copy().astype(np.int32)
        res_markers = cv2.watershed(img, markers_copy)
        
        out_img = img.copy()
        if int(params.get('draw_boundaries', 1)) == 1:
            # markers == -1 are the boundaries
            out_img[res_markers == -1] = [0, 0, 255] # Red boundaries
            
        return {"main": out_img, "markers_out": res_markers}
