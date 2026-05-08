import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="util_coord_to_mask",
    label="Coord To Mask",
    category='mask',
    icon="Target",
    description="Creates a circular dot in a binary mask at a specific coordinate.",
    inputs=[{"id": "coord", "color": "dict"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "radius", "label": "Radius", "type": "int", "default": 10},
        {"id": "width", "label": "Width", "type": "int", "default": 640},
        {"id": "height", "label": "Height", "type": "int", "default": 480}
    ]
)
class CoordToMaskNode(NodeProcessor):
    def process(self, inputs, params):
        c = inputs.get('coord')
        w, h = int(params.get('width', 640)), int(params.get('height', 480))
        mask = np.zeros((h, w), dtype=np.uint8)
        if c and isinstance(c, dict):
            cx, cy = int(c.get('x', 0) * w), int(c.get('y', 0) * h)
            cv2.circle(mask, (cx, cy), int(params.get('radius', 10)), 255, -1)
        return {"mask": mask}

@vision_node(
    type_id="util_mask_blend",
    label="Mask Blend",
    category='mask',
    icon="Layers",
    description="Combines two images using a binary mask as a transparency layer.",
    inputs=[
        {"id": "image_a", "color": "image"},
        {"id": "image_b", "color": "image"},
        {"id": "mask", "color": "mask"}
    ],
    outputs=[{"id": "main", "color": "image"}]
)
class MaskBlendNode(NodeProcessor):
    def process(self, inputs, params):
        ia, ib, m = inputs.get('image_a'), inputs.get('image_b'), inputs.get('mask')
        if ia is None or ib is None or m is None: return {"main": ia or ib}
        if m.shape[:2] != ia.shape[:2]: m = cv2.resize(m, (ia.shape[1], ia.shape[0]))
        if len(m.shape) == 2: m = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
        mask_norm = m.astype(float) / 255.0
        res = (ia.astype(float) * mask_norm + ib.astype(float) * (1.0 - mask_norm)).astype(np.uint8)
        return {"main": res}

@vision_node(
    type_id="util_inspector",
    label="Inspector",
    category='visualize',
    icon="Search",
    description="Debug tool to see the raw values of any data stream.",
    inputs=[{"id": "data", "color": "any"}],
    outputs=[{"id": "text", "color": "string"}]
)
class InspectorNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('data')
        txt = str(d)[:500]
        return {"text": txt, "main": txt, "display_text": txt, "data_out": d}

@vision_node(
    type_id="util_overlay",
    label="Visual Overlay",
    category='draw',
    icon="Layout",
    description="Overlays graphics (rects, circles, paths) onto an image. Connect any graphics-output node.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}]
)
class OverlayNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        out = img.copy()
        h, w = out.shape[:2]
        for key, val in inputs.items():
            if key == 'image': continue
            items = val if isinstance(val, list) else [val]
            for item in items:
                if not isinstance(item, dict) or item.get('_type') != 'graphics': continue
                color = item.get('color', '#00ff00').lstrip('#')
                bgr = (int(color[4:6], 16), int(color[2:4], 16), int(color[0:2], 16))
                shape = item.get('shape')
                pts = item.get('pts', [])
                if shape == 'rect' and len(pts) >= 2:
                    p1 = (int(pts[0][0]*w), int(pts[0][1]*h))
                    p2 = (int(pts[1][0]*w), int(pts[1][1]*h))
                    cv2.rectangle(out, p1, p2, bgr, 2)
                elif shape == 'circle' and len(pts) >= 1:
                    p = (int(pts[0][0]*w), int(pts[0][1]*h))
                    r = int(item.get('radius', 0.05) * w)
                    cv2.circle(out, p, r, bgr, 2)
                elif shape == 'polygon' and len(pts) > 0:
                    px = np.array([[int(p[0]*w), int(p[1]*h)] for p in pts], dtype=np.int32)
                    cv2.polylines(out, [px], True, bgr, 2)
                label = item.get('label')
                if label and len(pts) > 0:
                    cv2.putText(out, label, (int(pts[0][0]*w), int(pts[0][1]*h)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr, 1)
        return {"main": out}
