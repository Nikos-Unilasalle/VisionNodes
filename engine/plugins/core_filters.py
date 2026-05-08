import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="filter_canny",
    label="Canny Edge",
    category='cv',
    icon="Waves",
    description="Detects edges using the Canny algorithm.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "low", "label": "Low Threshold", "type": "int", "default": 100},
        {"id": "high", "label": "High Threshold", "type": "int", "default": 200}
    ]
)
class CannyFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return {"main": cv2.Canny(gray, int(params.get('low', 100)), int(params.get('high', 200)))}

@vision_node(
    type_id="filter_blur",
    label="Gaussian Blur",
    category='cv',
    icon="Waves",
    description="Applies a Gaussian blur to smooth the image.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[{"id": "size", "label": "Kernel Size", "type": "int", "default": 5}]
)
class BlurFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        s = int(params.get('size', 5))
        if s % 2 == 0: s += 1
        return {"main": cv2.GaussianBlur(img, (s, s), 0)}

@vision_node(
    type_id="filter_gray",
    label="Grayscale",
    category='cv',
    icon="Waves",
    description="Converts the image to grayscale.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}]
)
class GrayFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        res = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return {"main": res}

@vision_node(
    type_id="filter_threshold",
    label="Threshold",
    category='cv',
    icon="Waves",
    description="Separates the image into black and white based on intensity.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}],
    params=[{"id": "threshold", "label": "Threshold Value", "type": "int", "default": 127}]
)
class ThresholdFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None, "mask": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, res = cv2.threshold(gray, int(params.get('threshold', 127)), 255, cv2.THRESH_BINARY)
        return {"main": res, "mask": res}

@vision_node(
    type_id="filter_color_mask",
    label="Color Mask",
    category='mask',
    icon="Layers",
    description="Creates a mask by isolating a range of colors.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "color", "label": "Target Color (Hex)", "type": "string", "default": "#FF0000"},
        {"id": "tolerance", "label": "Tolerance", "type": "int", "default": 40}
    ]
)
class ColorMaskNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"mask": None}
        hex_c = str(params.get('color', '#FF0000')).lstrip('#')
        bgr = np.array([int(hex_c[4:6], 16), int(hex_c[2:4], 16), int(hex_c[0:2], 16)], dtype=np.uint8)
        tol = int(params.get('tolerance', 40))
        lower = np.clip(bgr.astype(int) - tol, 0, 255).astype(np.uint8)
        upper = np.clip(bgr.astype(int) + tol, 0, 255).astype(np.uint8)
        mask = cv2.inRange(img, lower, upper)
        return {"mask": mask}

@vision_node(
    type_id="filter_morphology",
    label="Morphology",
    category='mask',
    icon="Layers",
    description="Dilation or erosion operations to clean up masks.",
    inputs=[{"id": "mask", "color": "mask"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "operation", "label": "Operation (0=Dilate, 1=Erode)", "type": "int", "default": 0},
        {"id": "size", "label": "Kernel Size", "type": "int", "default": 5}
    ]
)
class MorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"mask": None}
        op, size = int(params.get('operation', 0)), int(params.get('size', 5))
        kernel = np.ones((size, size), np.uint8)
        res = cv2.dilate(mask, kernel) if op == 0 else cv2.erode(mask, kernel)
        return {"mask": res}
