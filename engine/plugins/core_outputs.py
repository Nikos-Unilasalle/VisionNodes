import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="output_display",
    label="Display",
    category="out",
    icon="Maximize",
    description="The output terminal displaying the final video stream.",
    dynamic_inputs=True,
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
        {"id": "alpha", "label": "Alpha (A)", "type": "float", "min": 0, "max": 1, "default": 0.5},
    ]
)
class DisplayOutput(NodeProcessor):
    def process(self, inputs, params):
        images = []
        if inputs.get('main') is not None:
            images.append(inputs.get('main'))

        _reserved = {'main', 'mask_in', 'flow_in', 'raw_frame', 'image', 'data'}
        dyn_imgs = sorted((k, v) for k, v in inputs.items() if k not in _reserved and v is not None)
        for _, v in dyn_imgs:
            images.append(v)

        mask = inputs.get('mask_in')
        flow = inputs.get('flow_in')

        mode      = int(params.get('mode', 0))
        split_pos = int(params.get('split_pos', 50))
        gap       = int(params.get('gap', 2))
        alpha     = float(params.get('alpha', 0.5))

        if not images:
            res = flow if flow is not None else mask
        else:
            if len(images) == 1:
                res = images[0]
            else:
                def to_bgr(img):
                    if len(img.shape) == 2:
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                    elif len(img.shape) == 3 and img.shape[2] == 4:
                        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    return img

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

                elif mode == 1:  # Top / Bottom
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

                elif mode == 4:  # Blend (Sequential)
                    res = to_bgr(images[0])
                    for i in range(1, len(images)):
                        next_img = to_bgr(images[i])
                        if next_img.shape[:2] != res.shape[:2]:
                            next_img = cv2.resize(next_img, (res.shape[1], res.shape[0]))
                        res = cv2.addWeighted(res, 1.0 - alpha, next_img, alpha, 0)

                else:  # Fallback → Side by Side
                    h_max = max(img.shape[0] for img in images)
                    resized = [cv2.resize(to_bgr(img), (int(img.shape[1] * h_max / img.shape[0]), h_max)) for img in images]
                    res = np.concatenate(resized, axis=1)

        if res is None:
            return {"main": None}

        if len(res.shape) == 2:
            res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)

        if mask is not None:
            if mask.shape[:2] != res.shape[:2]:
                mask = cv2.resize(mask, (res.shape[1], res.shape[0]))
            overlay = res.copy()
            m_bin = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            overlay[m_bin > 0] = [0, 0, 255]
            res = cv2.addWeighted(overlay, 0.4, res, 0.6, 0)

        return {"main": res}
