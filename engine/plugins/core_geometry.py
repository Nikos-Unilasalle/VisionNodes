import cv2
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="geom_flip",
    label="Flip",
    category='geom',
    icon="Move",
    description="Inverts the image horizontally or vertically.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[{"id": "flip_mode", "label": "Flip (0=V, 1=H, -1=Both)", "type": "int", "default": 1}]
)
class FlipNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        return {"main": cv2.flip(img, int(params.get('flip_mode', 1)))}

@vision_node(
    type_id="geom_resize",
    label="Resize",
    category='geom',
    icon="Scaling",
    description="Changes the image dimensions.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "width", "label": "Width", "type": "int", "default": 640},
        {"id": "height", "label": "Height", "type": "int", "default": 480}
    ]
)
class ResizeNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        w, h = int(params.get('width', 640)), int(params.get('height', 480))
        return {"main": cv2.resize(img, (w, h))}
