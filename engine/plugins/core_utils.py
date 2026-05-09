import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="util_coord_to_mask",
    label="Coord To Mask",
    category="mask",
    icon="Layers",
    description="Transforms detection coordinates into a white mask.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "data", "color": "any"}
    ],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "width", "label": "Width (if no img)", "type": "int", "default": 640},
        {"id": "height", "label": "Height (if no img)", "type": "int", "default": 480}
    ]
)
class CoordToMaskNode(NodeProcessor):
    def process(self, inputs, params):
        img_ref, data = inputs.get('image'), inputs.get('data')
        w, h = (img_ref.shape[1], img_ref.shape[0]) if img_ref is not None else (int(params.get('width', 640)), int(params.get('height', 480)))
        mask = np.zeros((h, w), dtype=np.uint8)
        items = data if isinstance(data, list) else [data] if data else []
        for item in items:
            if not isinstance(item, dict): continue
            if 'landmarks' in item:
                lms = item['landmarks']
                pts = np.array([(int(lm['x'] * w), int(lm['y'] * h)) for lm in lms], np.int32)
                if len(pts) > 2:
                    cv2.fillPoly(mask, [cv2.convexHull(pts)], 255)
            elif 'pts' in item:
                pts = np.array([(int(p[0] * w), int(p[1] * h)) for p in item['pts']], np.int32)
                if len(pts) > 2:
                    cv2.fillPoly(mask, [pts], 255)
            elif 'xmin' in item:
                cv2.rectangle(mask,
                    (int(item['xmin'] * w), int(item['ymin'] * h)),
                    (int((item['xmin'] + item['width']) * w), int((item['ymin'] + item['height']) * h)),
                    255, -1)
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
        img_a = inputs.get('image_a', inputs.get('image'))
        img_b, mask = inputs.get('image_b'), inputs.get('mask')
        if img_a is None: return {"main": None}
        if img_b is None or mask is None: return {"main": img_a}
        if len(mask.shape) == 3: mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = cv2.resize(mask, (img_a.shape[1], img_a.shape[0]))
        mask_norm = np.expand_dims(mask, axis=2) / 255.0
        if len(img_a.shape) == 2 or img_a.shape[2] == 1: img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        if len(img_b.shape) == 2 or img_b.shape[2] == 1: img_b = cv2.cvtColor(img_b, cv2.COLOR_GRAY2BGR)
        blended = (img_a * (1.0 - mask_norm)) + (img_b * mask_norm)
        return {"main": blended.astype(np.uint8)}

@vision_node(
    type_id="data_inspector",
    label="Inspect Unit",
    category='visualize',
    icon="Eye",
    description="Displays the raw data content flowing through a link.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "data", "color": "any"}
    ],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "data_out", "color": "any"}
    ]
)
class InspectorNode(NodeProcessor):
    def process(self, inputs, params):
        return {
            "main": inputs.get('image'),
            "data_out": inputs.get('data')
        }


