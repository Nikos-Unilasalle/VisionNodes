import cv2
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="geom_flip",
    label="Flip",
    category='geometry',
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
    category='geometry',
    icon="Scaling",
    description="Réduit la résolution de l'image pour accélérer les traitements en aval.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[
        {"id": "main", "color": "image"},
        {"id": "width", "color": "scalar"},
        {"id": "height", "color": "scalar"}
    ],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["Échelle (%)", "Largeur", "Hauteur", "Exact"], "default": 0},
        {"id": "scale", "label": "Échelle", "type": "float", "default": 0.5, "min": 0.01, "max": 1.0, "step": 0.01},
        {"id": "width", "label": "Largeur (px)", "type": "int", "default": 640, "min": 1, "max": 7680},
        {"id": "height", "label": "Hauteur (px)", "type": "int", "default": 480, "min": 1, "max": 7680},
        {"id": "interpolation", "label": "Interpolation", "type": "enum", "options": ["Auto (reco.)", "Nearest", "Linear", "Cubic", "Lanczos", "Area"], "default": 0}
    ]
)
class ResizeNode(NodeProcessor):
    INTERP_MAP = [None, cv2.INTER_NEAREST, cv2.INTER_LINEAR,
                  cv2.INTER_CUBIC, cv2.INTER_LANCZOS4, cv2.INTER_AREA]

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            img = inputs.get('main')
        if img is None: return {"main": None, "width": 0, "height": 0}
        ih, iw = img.shape[:2]
        mode = int(params.get('mode', 0))
        if mode == 0:
            sc = float(params.get('scale', 0.5))
            ow, oh = max(1, int(iw * sc)), max(1, int(ih * sc))
        elif mode == 1:
            ow = max(1, int(params.get('width', 640)))
            oh = max(1, int(ih * ow / iw))
        elif mode == 2:
            oh = max(1, int(params.get('height', 480)))
            ow = max(1, int(iw * oh / ih))
        else:
            ow = max(1, int(params.get('width', 640)))
            oh = max(1, int(params.get('height', 480)))
        interp_idx = int(params.get('interpolation', 0))
        interp = self.INTERP_MAP[interp_idx] if 0 <= interp_idx < len(self.INTERP_MAP) else None
        if interp is None:
            interp = cv2.INTER_AREA if (ow * oh < iw * ih) else cv2.INTER_LINEAR
        out = cv2.resize(img, (ow, oh), interpolation=interp)
        return {"main": out, "width": ow, "height": oh}
