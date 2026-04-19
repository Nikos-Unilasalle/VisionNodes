import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_matcher",
    label="Feature Matcher",
    category="features",
    icon="Link",
    description="Matches features between two sets of descriptors using BF or FLANN and draws matching lines.",
    inputs=[
        {"id": "des1", "color": "any"}, 
        {"id": "des2", "color": "any"},
        {"id": "kp1", "color": "list"}, 
        {"id": "kp2", "color": "list"},
        {"id": "img1", "color": "image"},
        {"id": "img2", "color": "image"}
    ],
    outputs=[{"id": "main", "color": "image"}, {"id": "matches_count", "color": "scalar"}],
    params=[
        {"id": "method", "label": "Method", "type": "enum", "options": ["Brute-Force", "FLANN"], "default": 0},
        {"id": "norm", "label": "Norm Type", "type": "enum", "options": ["L2 (SIFT)", "HAMMING (ORB)"], "default": 1},
        {"id": "ratio_test", "label": "Lowe's Ratio", "type": "scalar", "min": 0.1, "max": 1.0, "default": 0.75},
        {"id": "max_matches", "label": "Max Display", "type": "scalar", "min": 1, "max": 200, "default": 50}
    ]
)
class FeatureMatcherNode(NodeProcessor):
    def _to_cv_kp(self, kp_dicts, img_shape):
        if not kp_dicts: return []
        h, w = img_shape[:2]
        cv_kps = []
        for d in kp_dicts:
            # Reconstruct from our graphics format: pts: [[rel_x, rel_y]]
            rel_pts = d.get('pts', [[0, 0]])[0]
            px = rel_pts[0] * w
            py = rel_pts[1] * h
            cv_kps.append(cv2.KeyPoint(x=float(px), y=float(py), 
                                      size=float(d.get('size', 1.0)), 
                                      angle=float(d.get('angle', -1)),
                                      response=float(d.get('response', 0)),
                                      octave=int(d.get('octave', 0)),
                                      class_id=int(d.get('class_id', -1))))
        return cv_kps

    def process(self, inputs, params):
        des1 = inputs.get('des1')
        des2 = inputs.get('des2')
        kp1_dicts = inputs.get('kp1')
        kp2_dicts = inputs.get('kp2')
        img1 = inputs.get('img1')
        img2 = inputs.get('img2')
        
        if des1 is None or des2 is None or img1 is None or img2 is None:
            return {"main": img1 if img1 is not None else img2, "matches_count": 0}
            
        method = int(params.get('method', 0))
        norm_idx = int(params.get('norm', 1)) # Default to Hamming for ORB
        norm = cv2.NORM_L2 if norm_idx == 0 else cv2.NORM_HAMMING
        ratio = float(params.get('ratio_test', 0.75))
        max_m = int(params.get('max_matches', 50))
        
        matcher = None
        if method == 0: # BF
            matcher = cv2.BFMatcher(norm)
        else: # FLANN
            if norm == cv2.NORM_L2:
                index_params = dict(algorithm=1, trees=5)
            else:
                index_params = dict(algorithm=6, table_number=6, key_size=12, multi_probe_level=1)
            search_params = dict(checks=50)
            matcher = cv2.FlannBasedMatcher(index_params, search_params)
            
        try:
            matches = matcher.knnMatch(des1, des2, k=2)
            good = []
            for match_set in matches:
                if len(match_set) == 2:
                    m, n = match_set
                    if m.distance < ratio * n.distance:
                        good.append(m)
            
            # Draw Matches
            out_img = None
            if kp1_dicts and kp2_dicts:
                # Convert back to cv2.KeyPoint
                cv_kp1 = self._to_cv_kp(kp1_dicts, img1.shape)
                cv_kp2 = self._to_cv_kp(kp2_dicts, img2.shape)
                
                # Sort by distance and limit to max_display
                good = sorted(good, key = lambda x:x.distance)
                display_matches = good[:max_m]
                
                # Draw visual lines
                out_img = cv2.drawMatches(img1, cv_kp1, img2, cv_kp2, display_matches, None, 
                                        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            else:
                # Fallback: side-by-side if no keypoints
                h1, w1 = img1.shape[:2]
                h2, w2 = img2.shape[:2]
                out_img = np.zeros((max(h1, h2), w1 + w2, 3), dtype=np.uint8)
                out_img[:h1, :w1] = img1 if len(img1.shape)==3 else cv2.cvtColor(img1, cv2.COLOR_GRAY2BGR)
                out_img[:h2, w1:w1+w2] = img2 if len(img2.shape)==3 else cv2.cvtColor(img2, cv2.COLOR_GRAY2BGR)
            
            return {"main": out_img, "matches_count": len(good)}
        except Exception as e:
            print(f"Matching Error: {e}")
            # Ensure stable view by returning a combined side-by-side view even on error
            if img1 is not None and img2 is not None:
                h1, w1 = img1.shape[:2]
                h2, w2 = img2.shape[:2]
                err_img = np.zeros((max(h1, h2), w1 + w2, 3), dtype=np.uint8)
                err_img[:h1, :w1] = img1 if len(img1.shape)==3 else cv2.cvtColor(img1, cv2.COLOR_GRAY2BGR)
                err_img[:h2, w1:w1+w2] = img2 if len(img2.shape)==3 else cv2.cvtColor(img2, cv2.COLOR_GRAY2BGR)
                return {"main": err_img, "matches_count": 0}
            return {"main": img1, "matches_count": 0}
