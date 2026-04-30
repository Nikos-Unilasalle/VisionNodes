import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_water_refine",
    label="Water Mask Refine",
    category=["geo", "mask"],
    icon="Waves",
    description="Refines a water binary mask: morphological closing to fill gaps, opening to remove noise, area filter to keep only significant water bodies.",
    inputs=[{"id": "mask", "color": "mask"}],
    outputs=[
        {"id": "mask",     "color": "mask"},
        {"id": "main",     "color": "image"},
        {"id": "contours", "color": "list"},
        {"id": "count",    "color": "scalar"}
    ],
    params=[
        {"id": "close_size", "label": "Close Kernel",   "type": "scalar", "min": 0, "max": 51,    "default": 7,   "step": 2},
        {"id": "open_size",  "label": "Open Kernel",    "type": "scalar", "min": 0, "max": 21,    "default": 3,   "step": 2},
        {"id": "min_area",   "label": "Min Area (px²)", "type": "scalar", "min": 0, "max": 100000,"default": 500, "step": 100}
    ]
)
class WaterRefineNode(NodeProcessor):
    def process(self, inputs, params):
        mask_in = inputs.get('mask') or inputs.get('image')
        if mask_in is None:
            return {"mask": None, "main": None, "contours": [], "count": 0.0}

        if len(mask_in.shape) == 3:
            mask_in = cv2.cvtColor(mask_in, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(mask_in, 127, 255, cv2.THRESH_BINARY)

        # Closing: fill internal gaps in water bodies
        cs = max(1, int(params.get('close_size', 7)))
        if cs > 1:
            if cs % 2 == 0: cs += 1
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cs, cs))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)

        # Opening: remove small noise patches
        os_ = max(1, int(params.get('open_size', 3)))
        if os_ > 1:
            if os_ % 2 == 0: os_ += 1
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (os_, os_))
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k)

        # Area filter: discard regions smaller than min_area
        min_area = int(params.get('min_area', 500))
        cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        clean = np.zeros_like(binary)
        kept  = [cnt for cnt in cnts if cv2.contourArea(cnt) >= min_area]
        if kept:
            cv2.drawContours(clean, kept, -1, 255, -1)

        h, w = clean.shape[:2]

        # Export contours as polygon graphics
        contours_out = []
        for cnt in kept:
            step = max(1, len(cnt) // 60)
            pts  = [[float(p[0][0]) / w, float(p[0][1]) / h] for p in cnt[::step]]
            contours_out.append({
                "_type": "graphics", "shape": "polygon",
                "pts": pts, "relative": True,
                "color": "#00aaff", "thickness": 2
            })

        # Visualization: water bodies in blue on dark background
        vis = np.zeros((h, w, 3), dtype=np.uint8)
        vis[clean > 0] = [200, 100, 0]  # BGR → teal-blue

        return {"mask": clean, "main": vis, "contours": contours_out, "count": float(len(kept))}
