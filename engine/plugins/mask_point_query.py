from registry import NodeProcessor, vision_node

@vision_node(
    type_id="mask_point_query",
    label="Mask Point Query",
    category="logic",
    icon="Crosshair",
    description="Checks if a point (x, y) falls within a mask. Returns True if the mask value at that point is non-zero.",
    inputs=[
        {"id": "mask", "color": "mask"},
        {"id": "x", "color": "scalar"},
        {"id": "y", "color": "scalar"}
    ],
    outputs=[{"id": "inside", "color": "boolean"}]
)
class MaskPointQueryNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        x = inputs.get('x', 0)
        y = inputs.get('y', 0)

        if mask is None:
            return {"inside": False}

        try:
            fx, fy = float(x), float(y)
            h, w = mask.shape[:2]
            if 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0:
                ix, iy = int(round(fx * (w - 1))), int(round(fy * (h - 1)))
            else:
                ix, iy = int(round(fx)), int(round(fy))
            if ix < 0 or ix >= w or iy < 0 or iy >= h:
                return {"inside": False}
            return {"inside": bool(mask[iy, ix])}
        except Exception:
            return {"inside": False}
