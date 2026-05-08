import cv2
import numpy as np
import base64
from registry import vision_node, NodeProcessor

def _small(img, max_px=640):
    if img is None: return None
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_px:
        return img
    s = max_px / m
    return cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)


def _encode(img):
    if img is None: return None
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return base64.b64encode(buf).decode('utf-8')


@vision_node(
    type_id="output_display",
    label="Display Output",
    category='out',
    icon="Monitor",
    description="Final visualization node. Renders multiple image streams side-by-side or composed. Dynamic ports accepted.",
    inputs=[
        {"id": "main", "color": "image"}, 
        {"id": "mask_in", "color": "mask"},
        {"id": "flow_in", "color": "flow"}
    ],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Side by Side", "Top / Bottom", "Picture in Picture", "Split Screen", "Blend"], "default": 0},
        {"id": "gap", "label": "Gap (px)", "type": "scalar", "min": 0, "max": 50, "default": 2},
        {"id": "alpha", "label": "Alpha (Blend)", "type": "float", "min": 0, "max": 1, "default": 0.5},
    ]
)
class DisplayOutput(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        # 1. Collect all images
        images = []
        if inputs.get('main') is not None:
            images.append(inputs.get('main'))
        
        # Collect dynamic image inputs
        _reserved = {'main', 'mask_in', 'flow_in', 'raw_frame', 'image', 'data'}
        dyn_imgs = sorted((k, v) for k, v in inputs.items() if k not in _reserved and isinstance(v, np.ndarray))
        for _, v in dyn_imgs:
            images.append(v)
        
        mask = inputs.get('mask_in')
        flow = inputs.get('flow_in')
        
        mode  = int(params.get('mode', 0))
        gap   = int(params.get('gap', 2))
        alpha = float(params.get('alpha', 0.5))

        # Cache check
        ck = tuple(id(v) for v in images + [mask, flow])
        if ck == self._ck and self._co is not None:
            return self._co

        def to_bgr(img):
            if len(img.shape) == 2:
                return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif len(img.shape) == 3 and img.shape[2] == 4:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img

        # Determine composite image
        res = None
        if not images:
            if flow is not None: res = to_bgr(flow)
            elif mask is not None: res = to_bgr(mask)
            else: res = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            if len(images) == 1:
                res = to_bgr(images[0]).copy()
            else:
                # Side by Side
                if mode == 0:
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
                
                # Top / Bottom
                elif mode == 1:
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
                
                # Blend
                elif mode == 4:
                    res = to_bgr(images[0]).copy()
                    for i in range(1, len(images)):
                        next_img = to_bgr(images[i])
                        if next_img.shape[:2] != res.shape[:2]:
                            next_img = cv2.resize(next_img, (res.shape[1], res.shape[0]))
                        res = cv2.addWeighted(res, 1.0 - alpha, next_img, alpha, 0)
                
                # Fallback
                else:
                    h_max = max(img.shape[0] for img in images)
                    resized = [cv2.resize(to_bgr(img), (int(img.shape[1] * h_max / img.shape[0]), h_max)) for img in images]
                    res = np.concatenate(resized, axis=1)

        # Apply mask overlay on the FINAL composite if mask exists
        if mask is not None:
            if mask.shape[:2] != res.shape[:2]:
                mask = cv2.resize(mask, (res.shape[1], res.shape[0]))
            m_bin = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            overlay = res.copy()
            overlay[m_bin > 0] = [0, 0, 255] # Red overlay
            res = cv2.addWeighted(overlay, 0.4, res, 0.6, 0)

        # Encode for UI
        # We still keep _tab_main for the node preview
        out = {
            'main': res,
            '_tab_main': _encode(_small(res))
        }

        self._ck = ck
        self._co = out
        return self._co
