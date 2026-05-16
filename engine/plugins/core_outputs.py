import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="output_display",
    label="Display",
    category='output',
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
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Side by Side", "Top / Bottom", "Grid", "Picture in Picture", "Split Screen", "Blend"], "default": 0},
        {"id": "grid_cols", "label": "Grid Columns", "type": "int", "min": 1, "max": 8, "default": 2},
        {"id": "split_pos", "label": "Split / Tile %", "type": "scalar", "min": 0, "max": 100, "default": 50},
        {"id": "gap", "label": "Gap / Line (px)", "type": "scalar", "min": 0, "max": 50, "default": 2},
        {"id": "alpha", "label": "Alpha (A)", "type": "float", "min": 0, "max": 1, "default": 0.5},
    ]
)
class DisplayOutput(NodeProcessor):
    def process(self, inputs, params):
        images = []
        # Main input is always first
        if inputs.get('main') is not None:
            images.append(inputs.get('main'))

        # Dynamic inputs (dyn-0, dyn-1, etc.)
        _reserved = {'main', 'mask_in', 'flow_in', 'raw_frame', 'image', 'data', 'in', 'value'}
        dyn_imgs = []
        for k, v in inputs.items():
            if k not in _reserved and v is not None and isinstance(v, np.ndarray):
                dyn_imgs.append((k, v))
        
        # Sort by key to maintain order (dyn-0, dyn-1...)
        dyn_imgs.sort(key=lambda x: x[0])
        for _, v in dyn_imgs:
            images.append(v)

        mask = inputs.get('mask_in')
        flow = inputs.get('flow_in')

        mode      = int(params.get('mode', 0))
        grid_cols = int(params.get('grid_cols', 2))
        split_pos = int(params.get('split_pos', 50))
        gap       = int(params.get('gap', 2))
        alpha     = float(params.get('alpha', 0.5))

        if not images:
            res = flow if flow is not None else mask
            if res is None:
                return {"main": None}
        else:
            def to_bgr(img):
                if img.dtype != np.uint8:
                    if img.dtype in (np.float32, np.float64):
                        img = (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8) if float(img.max()) <= 1.0 else np.clip(img, 0, 255).astype(np.uint8)
                    else:
                        img = np.clip(img, 0, 255).astype(np.uint8)
                if len(img.shape) == 2:
                    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                elif len(img.shape) == 3 and img.shape[2] == 4:
                    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img

            if len(images) == 1:
                res = to_bgr(images[0])
            else:
                if mode == 0:  # Side by Side
                    h_max = max(img.shape[0] for img in images)
                    resized = []
                    for i, img in enumerate(images):
                        img = to_bgr(img)
                        w = int(img.shape[1] * h_max / img.shape[0]) if img.shape[0] > 0 else 1
                        resized.append(cv2.resize(img, (max(1, w), h_max)))
                        if gap > 0 and i < len(images) - 1:
                            resized.append(np.zeros((h_max, gap, 3), dtype=np.uint8))
                    res = np.concatenate(resized, axis=1)

                elif mode == 1:  # Top / Bottom
                    w_max = max(img.shape[1] for img in images)
                    resized = []
                    for i, img in enumerate(images):
                        img = to_bgr(img)
                        h = int(img.shape[0] * w_max / img.shape[1]) if img.shape[1] > 0 else 1
                        resized.append(cv2.resize(img, (w_max, max(1, h))))
                        if gap > 0 and i < len(images) - 1:
                            resized.append(np.zeros((gap, w_max, 3), dtype=np.uint8))
                    res = np.concatenate(resized, axis=0)

                elif mode == 2:  # Grid
                    cols = max(1, grid_cols)
                    rows = (len(images) + cols - 1) // cols
                    # Normalize all to same size (based on first image)
                    ref_h, ref_w = images[0].shape[:2]
                    
                    grid_rows = []
                    for r in range(rows):
                        row_imgs = []
                        for c in range(cols):
                            idx = r * cols + c
                            if idx < len(images):
                                img = cv2.resize(to_bgr(images[idx]), (ref_w, ref_h))
                            else:
                                img = np.zeros((ref_h, ref_w, 3), dtype=np.uint8)
                            row_imgs.append(img)
                            if gap > 0 and c < cols - 1:
                                row_imgs.append(np.zeros((ref_h, gap, 3), dtype=np.uint8))
                        grid_rows.append(np.concatenate(row_imgs, axis=1))
                        if gap > 0 and r < rows - 1:
                            grid_rows.append(np.zeros((gap, grid_rows[0].shape[1], 3), dtype=np.uint8))
                    res = np.concatenate(grid_rows, axis=0)

                elif mode == 3:  # Picture in Picture
                    res = to_bgr(images[0]).copy()
                    h, w = res.shape[:2]
                    pip_size = split_pos / 100.0
                    ph, pw = int(h * pip_size), int(w * pip_size)
                    if len(images) > 1 and ph > 0 and pw > 0:
                        pip_img = cv2.resize(to_bgr(images[1]), (pw, ph))
                        res[h-ph-10:h-10, w-pw-10:w-10] = pip_img # Bottom right

                elif mode == 4:  # Split Screen
                    img1 = to_bgr(images[0])
                    img2 = to_bgr(images[1]) if len(images) > 1 else img1
                    h, w = img1.shape[:2]
                    img2 = cv2.resize(img2, (w, h))
                    split_w = int(w * split_pos / 100.0)
                    res = np.zeros_like(img1)
                    res[:, :split_w] = img1[:, :split_w]
                    res[:, split_w:] = img2[:, split_w:]
                    if gap > 0:
                        res[:, max(0, split_w-gap//2):min(w, split_w+gap//2)] = [255, 255, 255]

                elif mode == 5:  # Blend
                    res = to_bgr(images[0])
                    for i in range(1, len(images)):
                        next_img = cv2.resize(to_bgr(images[i]), (res.shape[1], res.shape[0]))
                        res = cv2.addWeighted(res, 1.0 - alpha, next_img, alpha, 0)
                else:
                    res = to_bgr(images[0])

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
