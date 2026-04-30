import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="util_compose",
    label="Compose",
    category="data",
    icon="Layout",
    description="Combines two images: side-by-side, split view, blend, difference, or checkerboard.",
    inputs=[{"id": "image_a", "color": "image"}, {"id": "image_b", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum",
         "options": ["Side by Side", "Top / Bottom", "Split H", "Split V", "Alpha Blend", "Difference", "Checkerboard"],
         "default": 0},
        {"id": "split_pos", "label": "Split / Tile %", "type": "scalar", "min": 1, "max": 99, "default": 50},
        {"id": "gap",       "label": "Gap / Line (px)", "type": "scalar", "min": 0, "max": 40, "default": 2},
        {"id": "alpha",     "label": "Alpha (A)",       "type": "scalar", "min": 0.0, "max": 1.0, "default": 0.5},
    ]
)
class ComposeNode(NodeProcessor):
    def process(self, inputs, params):
        a = inputs.get('image_a')
        if a is None: a = inputs.get('image')
        b = inputs.get('image_b')
        if a is None: return {"main": b}
        if b is None: return {"main": a}

        def to_bgr(img):
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img.astype(np.uint8)

        a, b = to_bgr(a), to_bgr(b)
        ha, wa = a.shape[:2]

        mode      = int(params.get('mode', 0))
        split     = int(params.get('split_pos', 50))
        gap       = int(params.get('gap', 2))
        alpha     = float(params.get('alpha', 0.5))

        if mode == 0:  # Side by Side
            hb = ha
            wb = int(b.shape[1] * hb / b.shape[0]) if b.shape[0] > 0 else b.shape[1]
            b_r = cv2.resize(b, (wb, hb))
            if gap > 0:
                bar = np.zeros((ha, gap, 3), dtype=np.uint8)
                out = np.concatenate([a, bar, b_r], axis=1)
            else:
                out = np.concatenate([a, b_r], axis=1)

        elif mode == 1:  # Top / Bottom
            wb = wa
            hb = int(b.shape[0] * wb / b.shape[1]) if b.shape[1] > 0 else b.shape[0]
            b_r = cv2.resize(b, (wb, hb))
            if gap > 0:
                bar = np.zeros((gap, wa, 3), dtype=np.uint8)
                out = np.concatenate([a, bar, b_r], axis=0)
            else:
                out = np.concatenate([a, b_r], axis=0)

        elif mode == 2:  # Split H (left A / right B)
            b_r = cv2.resize(b, (wa, ha))
            out = a.copy()
            sx = max(0, min(wa - 1, int(wa * split / 100)))
            out[:, sx:] = b_r[:, sx:]
            if gap > 0:
                h = max(1, gap)
                x0 = max(0, sx - h // 2)
                x1 = min(wa, x0 + h)
                out[:, x0:x1] = (220, 220, 220)

        elif mode == 3:  # Split V (top A / bottom B)
            b_r = cv2.resize(b, (wa, ha))
            out = a.copy()
            sy = max(0, min(ha - 1, int(ha * split / 100)))
            out[sy:, :] = b_r[sy:, :]
            if gap > 0:
                h = max(1, gap)
                y0 = max(0, sy - h // 2)
                y1 = min(ha, y0 + h)
                out[y0:y1, :] = (220, 220, 220)

        elif mode == 4:  # Alpha Blend
            b_r = cv2.resize(b, (wa, ha))
            out = cv2.addWeighted(a, alpha, b_r, 1.0 - alpha, 0)

        elif mode == 5:  # Difference
            b_r = cv2.resize(b, (wa, ha))
            diff = cv2.absdiff(a, b_r)
            out = cv2.convertScaleAbs(diff, alpha=2.0)

        elif mode == 6:  # Checkerboard
            b_r = cv2.resize(b, (wa, ha))
            tile = max(4, int(min(wa, ha) * split / 100))
            out = a.copy()
            for y in range(0, ha, tile):
                for x in range(0, wa, tile):
                    if ((y // tile) + (x // tile)) % 2 == 1:
                        out[y:y + tile, x:x + tile] = b_r[y:y + tile, x:x + tile]
        else:
            out = a

        return {"main": out}
