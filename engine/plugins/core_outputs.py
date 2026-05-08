import cv2
import numpy as np
import base64
from registry import vision_node, NodeProcessor

def _small(img, max_px=640):
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_px:
        return img
    s = max_px / m
    return cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)


def _encode(img):
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 72])
    return base64.b64encode(buf).decode('utf-8')


@vision_node(
    type_id="output_display",
    label="Display Output",
    category='out',
    icon="Monitor",
    description="Final visualization node. Renders the image stream to the UI. Dynamic ports accepted.",
    inputs=[
        {"id": "main", "color": "image"}, 
        {"id": "mask_in", "color": "mask"},
        {"id": "flow_in", "color": "flow"}
    ],
    outputs=[{"id": "main", "color": "image"}]
)
class DisplayOutput(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._ck = None
        self._co = None

    def process(self, inputs, params):
        # Support both 'mask' (old) and 'mask_in' (new)
        mask = inputs.get('mask_in', inputs.get('mask'))
        flow = inputs.get('flow_in')

        # Collect all image inputs (including dynamic ports)
        img_inputs: dict[str, np.ndarray] = {}
        for k, v in inputs.items():
            if k in ('raw_frame', 'mask', 'mask_in', 'flow_in'):
                continue
            if isinstance(v, np.ndarray) and len(v.shape) >= 2:
                img_inputs[k] = v

        # Cache check
        ck = tuple(id(v) for v in list(img_inputs.values()) + [mask, flow])
        if ck == self._ck and self._co is not None:
            return self._co

        # Base image
        main = img_inputs.get('main')
        if main is None:
            if img_inputs:
                main = next(iter(img_inputs.values()))
            else:
                main = np.zeros((480, 640, 3), dtype=np.uint8)
        
        if len(main.shape) == 2:
            main = cv2.cvtColor(main, cv2.COLOR_GRAY2BGR)
        else:
            main = main.copy()

        # Render output dictionary
        out: dict = {}
        
        # Overlay mask on main if present
        res = main
        if mask is not None:
            if mask.shape[:2] != res.shape[:2]:
                mask = cv2.resize(mask, (res.shape[1], res.shape[0]))
            m_bin = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            overlay = res.copy()
            overlay[m_bin > 0] = [0, 0, 255] # Red overlay
            res = cv2.addWeighted(overlay, 0.4, res, 0.6, 0)
            out['_tab_mask'] = _encode(_small(mask))

        if flow is not None:
            out['_tab_flow'] = _encode(_small(flow))

        out['main'] = res
        
        # Tabs for all dynamic images
        for k, v in img_inputs.items():
            out[f'_tab_{k}'] = _encode(_small(v))

        if 'main' not in out:
            out['_tab_main'] = _encode(_small(main))

        self._ck = ck
        self._co = out
        return self._co
