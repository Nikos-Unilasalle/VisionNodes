import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_orb",
    label="ORB Detector",
    category="features",
    icon="Zap",
    description="Detects keypoints and computes ORB descriptors (fast and efficient).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "keypoints", "color": "list"}, {"id": "descriptors", "color": "any"}],
    params=[
        {"id": "n_features", "label": "Max Features", "type": "scalar", "min": 10, "max": 5000, "default": 500},
        {"id": "scale_factor", "label": "Scale Factor", "type": "scalar", "min": 1.1, "max": 2.0, "default": 1.2},
        {"id": "n_levels", "label": "Levels", "type": "scalar", "min": 1, "max": 16, "default": 8}
    ]
)
class OrbDetectorNode(NodeProcessor):
    def __init__(self):
        self.orb = None
        self.last_params = {}

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"keypoints": [], "descriptors": None}
        
        n_feat = int(params.get('n_features', 500))
        scale = float(params.get('scale_factor', 1.2))
        levels = int(params.get('n_levels', 8))
        
        current_params = (n_feat, scale, levels)
        if self.orb is None or current_params != self.last_params:
            self.orb = cv2.ORB_create(nfeatures=n_feat, scaleFactor=scale, nlevels=levels)
            self.last_params = current_params
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        kp, des = self.orb.detectAndCompute(gray, None)
        
        h, w = gray.shape[:2]
        pts = []
        for k in kp:
            pts.append({
                "_type": "graphics", "shape": "point",
                "pts": [[float(k.pt[0]/w), float(k.pt[1]/h)]],
                "size": k.size, "angle": k.angle, "response": k.response,
                "relative": True, "color": "#00ffff"
            })
            
        return {"keypoints": pts, "descriptors": des}

@vision_node(
    type_id="feat_sift",
    label="SIFT Detector",
    category="features",
    icon="Zap",
    description="Detects high-quality scale-invariant keypoints (SIFT algorithm).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "keypoints", "color": "list"}, {"id": "descriptors", "color": "any"}],
    params=[
        {"id": "n_features", "label": "Max Features", "type": "scalar", "min": 0, "max": 5000, "default": 0},
        {"id": "contrast_thresh", "label": "Contrast Thr", "type": "scalar", "min": 0, "max": 0.5, "default": 0.04}
    ]
)
class SiftDetectorNode(NodeProcessor):
    def __init__(self):
        self.sift = None
        self.last_params = {}

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"keypoints": [], "descriptors": None}
        
        n_feat = int(params.get('n_features', 0))
        thresh = float(params.get('contrast_thresh', 0.04))
        
        current_params = (n_feat, thresh)
        if self.sift is None or current_params != self.last_params:
            self.sift = cv2.SIFT_create(nfeatures=n_feat, contrastThreshold=thresh)
            self.last_params = current_params
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        kp, des = self.sift.detectAndCompute(gray, None)
        
        h, w = gray.shape[:2]
        pts = []
        for k in kp:
            pts.append({
                "_type": "graphics", "shape": "point",
                "pts": [[float(k.pt[0]/w), float(k.pt[1]/h)]],
                "relative": True, "color": "#ffff00"
            })
            
        return {"keypoints": pts, "descriptors": des}

@vision_node(
    type_id="feat_fast",
    label="FAST Corners",
    category="features",
    icon="Zap",
    description="Rapid corner detection optimized for real-time performance.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "keypoints", "color": "list"}],
    params=[
        {"id": "threshold", "label": "Threshold", "type": "scalar", "min": 1, "max": 100, "default": 10},
        {"id": "nonmax", "label": "Non-max Suppr.", "type": "boolean", "default": True}
    ]
)
class FastDetectorNode(NodeProcessor):
    def __init__(self):
        self.fast = None
        self.last_params = {}

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"keypoints": []}
        
        thresh = int(params.get('threshold', 10))
        nonmax = bool(params.get('nonmax', True))
        
        current_params = (thresh, nonmax)
        if self.fast is None or current_params != self.last_params:
            self.fast = cv2.FastFeatureDetector_create(threshold=thresh, nonmaxSuppression=nonmax)
            self.last_params = current_params
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        kp = self.fast.detect(gray, None)
        
        h, w = gray.shape[:2]
        pts = [{"_type": "graphics", "shape": "point", "pts": [[float(k.pt[0]/w), float(k.pt[1]/h)]], "relative": True, "color": "#00ff00"} for k in kp]
        return {"keypoints": pts}

@vision_node(
    type_id="feat_harris",
    label="Harris Corners",
    category="features",
    icon="LayoutGrid",
    description="Detects corner points using the Harris mathematical operator.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}],
    params=[
        {"id": "block_size", "label": "Block Size", "type": "scalar", "min": 2, "max": 10, "default": 2},
        {"id": "ksize", "label": "Sobel K", "type": "scalar", "min": 1, "max": 31, "default": 3},
        {"id": "k", "label": "Harris K", "type": "scalar", "min": 0, "max": 0.1, "default": 0.04},
        {"id": "threshold", "label": "Threshold", "type": "scalar", "min": 0, "max": 0.2, "default": 0.01}
    ]
)
class HarrisCornerNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None, "mask": None}
        
        res = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        gray = np.float32(gray)
        
        bs = int(params.get('block_size', 2))
        ks = int(params.get('ksize', 3))
        if ks % 2 == 0: ks += 1
        k = float(params.get('k', 0.04))
        thresh = float(params.get('threshold', 0.01))
        
        dst = cv2.cornerHarris(gray, bs, ks, k)
        # Result is dilated for marking the corners
        dst = cv2.dilate(dst, None)
        
        mask = np.zeros(gray.shape, dtype=np.uint8)
        mask[dst > thresh * dst.max()] = 255
        res[dst > thresh * dst.max()] = [0, 0, 255]
        
        return {"main": res, "mask": mask}
