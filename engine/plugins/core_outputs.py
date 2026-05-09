import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="output_display",
    label="Display",
    category="out",
    icon="Maximize",
    description="The output terminal displaying the final video stream.",
    inputs=[
        {"id": "main", "color": "image"},
        {"id": "mask_in", "color": "mask"},
        {"id": "flow_in", "color": "any"}
    ],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Side by Side", "Top / Bottom", "Picture in Picture", "Split Screen", "Blend"], "default": 0},
        {"id": "split_pos", "label": "Split / Tile %", "type": "scalar", "min": 0, "max": 100, "default": 50},
        {"id": "gap", "label": "Gap / Line (px)", "type": "scalar", "min": 0, "max": 50, "default": 2},
    ]
)
class DisplayOutput(NodeProcessor):
    def process(self, inputs, params):
        # 1. Collect all images
        images = []
        if inputs.get('main') is not None:
            images.append(inputs.get('main'))
        
        # Collect dynamic image inputs
        _reserved = {'main', 'mask_in', 'flow_in', 'raw_frame', 'image', 'data'}
        dyn_imgs = sorted((k, v) for k, v in inputs.items() if k not in _reserved and v is not None and isinstance(v, np.ndarray))
        for _, v in dyn_imgs:
            images.append(v)
        
        mask = inputs.get('mask_in')
        flow = inputs.get('flow_in')
        
        mode      = int(params.get('mode', 0))
        split_pos = int(params.get('split_pos', 50))
        gap       = int(params.get('gap', 2))

        def to_bgr(img):
            if img is None: return None
            if len(img.shape) == 2:
                return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif len(img.shape) == 3 and img.shape[2] == 4:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img

        # Determine base image
        res = None
        if not images:
            if flow is not None: res = to_bgr(flow)
            elif mask is not None: res = to_bgr(mask)
            else: res = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            if len(images) == 1:
                res = to_bgr(images[0])
            else:
                # Composition logic
                if mode == 0:  # Side by Side
                    h_max = max(img.shape[0] for img in images)
                    resized = []
                    for i, img in enumerate(images):
                        img = to_bgr(img)
                        w = int(img.shape[1] * h_max / img.shape[0]) if img.shape[0] > 0 else 1
                        r = cv2.resize(img, (max(1, w), h_max))
                        resized.append(r)
                        if gap > 0 and i < len(images) - 1:
                            resized.append(np.zeros((h_max, gap, 3), dtype=np.uint8))
                    res = np.concatenate(resized, axis=1)
                
                elif mode == 1: # Top / Bottom
                    w_max = max(img.shape[1] for img in images)
                    resized = []
                    for i, img in enumerate(images):
                        img = to_bgr(img)
                        h = int(img.shape[0] * w_max / img.shape[1]) if img.shape[1] > 0 else 1
                        r = cv2.resize(img, (w_max, max(1, h)))
                        resized.append(r)
                        if gap > 0 and i < len(images) - 1:
                            resized.append(np.zeros((gap, w_max, 3), dtype=np.uint8))
                    res = np.concatenate(resized, axis=0)
                
                elif mode == 4: # Blend (Fixed alpha since param is removed)
                    res = to_bgr(images[0]).copy()
                    alpha = 0.5
                    for i in range(1, len(images)):
                        next_img = to_bgr(images[i])
                        if next_img.shape[:2] != res.shape[:2]:
                            next_img = cv2.resize(next_img, (res.shape[1], res.shape[0]))
                        res = cv2.addWeighted(res, 1.0 - alpha, next_img, alpha, 0)
                
                else: # Fallback
                    h_max = max(img.shape[0] for img in images)
                    resized = [cv2.resize(to_bgr(img), (int(img.shape[1] * h_max / img.shape[0]), h_max)) for img in images]
                    res = np.concatenate(resized, axis=1)

        if res is None:
            return {"main": None}
        
        # Apply mask overlay
        if mask is not None:
            res_bgr = to_bgr(res) # Ensure we have 3 channels
            if mask.shape[:2] != res_bgr.shape[:2]:
                mask = cv2.resize(mask, (res_bgr.shape[1], res_bgr.shape[0]))
            
            m_bin = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            overlay = res_bgr.copy()
            overlay[m_bin > 0] = [0, 0, 255]
            res = cv2.addWeighted(overlay, 0.4, res_bgr, 0.6, 0)

        return {"main": res}
