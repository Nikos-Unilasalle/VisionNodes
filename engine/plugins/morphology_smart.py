import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="filter_morphology_smart",
    label="Smart Morphology",
    category='mask',
    icon="Zap",
    description="Erodes small zones and dilates large zones based on area threshold. Useful for noise removal and strengthening main features.",
    inputs=[{"id": "mask", "color": "mask"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "area_thresh_pct", "label": "Area Threshold (%)", "type": "scalar", "min": 0.0, "max": 10.0, "default": 0.5},
        {"id": "amount", "label": "Amount (px)", "type": "scalar", "min": 1, "max": 51, "default": 3}
    ]
)
class SmartMorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"mask": None}
        
        # Ensure grayscale uint8
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = (mask > 127).astype(np.uint8) * 255
        
        h, w = mask.shape[:2]
        total_area = h * w
        if total_area == 0: return {"mask": mask}
        
        thresh_pct = float(params.get('area_thresh_pct', 0.5))
        amount = int(params.get('amount', 3))
        if amount < 1: amount = 1
        
        kernel = np.ones((amount, amount), np.uint8)
        
        # 1. Label components
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        
        small_mask = np.zeros_like(mask)
        large_mask = np.zeros_like(mask)
        
        for i in range(1, num):
            area = stats[i, cv2.CC_STAT_AREA]
            area_pct = (area / total_area) * 100.0
            
            if area_pct < thresh_pct:
                small_mask[labels == i] = 255
            else:
                large_mask[labels == i] = 255
        
        # 2. Apply operations
        res_small = cv2.erode(small_mask, kernel)
        res_large = cv2.dilate(large_mask, kernel)
        
        # 3. Combine
        res = cv2.bitwise_or(res_small, res_large)
        
        return {"mask": res}
