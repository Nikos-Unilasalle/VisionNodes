import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id="filter_canny",
    label="Canny Edge",
    category='image',
    icon="Waves",
    description="Detects edges using the Canny algorithm.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "low",  "label": "Low Threshold",  "type": "int", "default": 100, "min": 0, "max": 500, "step": 1},
        {"id": "high", "label": "High Threshold", "type": "int", "default": 200, "min": 0, "max": 500, "step": 1}
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
    label="Blur",
    category='image',
    icon="Waves",
    description="Smooths the image. Multiple methods (Gaussian, Median, Box, "
                "Bilateral, Motion). Connect a mask to blur only that region.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "mask", "color": "mask"},
    ],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "method", "label": "Method", "type": "enum",
         "options": ["Gaussian", "Median", "Box", "Bilateral", "Motion"], "default": 0},
        {"id": "size", "label": "Strength (kernel)", "type": "scalar",
         "min": 1, "max": 99, "step": 2, "default": 5},
        {"id": "sigma", "label": "Sigma (Gaussian, 0=auto)", "type": "float",
         "min": 0, "max": 50, "step": 0.5, "default": 0},
        {"id": "sigma_color", "label": "Sigma Color (Bilateral)", "type": "scalar",
         "min": 1, "max": 200, "default": 75},
        {"id": "sigma_space", "label": "Sigma Space (Bilateral)", "type": "scalar",
         "min": 1, "max": 200, "default": 75},
        {"id": "angle", "label": "Angle (Motion)", "type": "scalar",
         "min": 0, "max": 360, "default": 0},
    ]
)
class BlurFilter(NodeProcessor):
    @staticmethod
    def _odd(v, lo=1):
        v = int(round(v))
        if v < lo: v = lo
        if v % 2 == 0: v += 1
        return v

    def _apply(self, img, params):
        method = int(params.get('method', 0))
        size = self._odd(params.get('size', 5))

        if method == 1:  # Median
            return cv2.medianBlur(img, size)
        if method == 2:  # Box / Average
            return cv2.blur(img, (size, size))
        if method == 3:  # Bilateral (edge-preserving)
            sc = float(params.get('sigma_color', 75))
            ss = float(params.get('sigma_space', 75))
            src = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            out = cv2.bilateralFilter(src, size, sc, ss)
            return out if img.ndim == 3 else cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        if method == 4:  # Motion (directional)
            angle = float(params.get('angle', 0))
            kernel = np.zeros((size, size), dtype=np.float32)
            kernel[size // 2, :] = 1.0
            kernel = cv2.warpAffine(
                kernel,
                cv2.getRotationMatrix2D((size / 2 - 0.5, size / 2 - 0.5), angle, 1.0),
                (size, size))
            s = kernel.sum()
            if s > 0: kernel /= s
            return cv2.filter2D(img, -1, kernel)
        # Gaussian (default)
        sigma = float(params.get('sigma', 0))
        return cv2.GaussianBlur(img, (size, size), sigma)

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}

        blurred = self._apply(img, params)

        mask = inputs.get('mask')
        if mask is None:
            return {"main": blurred}

        # Composite: blurred inside the mask, original outside, with soft edges.
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        if mask.shape[:2] != img.shape[:2]:
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        alpha = (mask.astype(np.float32) / 255.0)
        if img.ndim == 3:
            alpha = alpha[:, :, None]
        out = blurred.astype(np.float32) * alpha + img.astype(np.float32) * (1.0 - alpha)
        return {"main": out.astype(img.dtype)}

@vision_node(
    type_id="filter_gray",
    label="Grayscale",
    category='image',
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
    category='image',
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
    category="mask",
    icon="Layers",
    description="Creates a mask by isolating a range of colors (HSV or RGB distance).",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["HSV Range", "RGB Distance"], "default": 0},
        {"id": "color", "label": "Target Color", "type": "color", "default": "#FF0000"},
        {"id": "h_tol", "label": "H Tolerance", "type": "int", "default": 10, "min": 0, "max": 90},
        {"id": "s_tol", "label": "S Tolerance", "type": "int", "default": 40, "min": 0, "max": 255},
        {"id": "v_tol", "label": "V Tolerance", "type": "int", "default": 40, "min": 0, "max": 255},
        {"id": "threshold", "label": "RGB Threshold", "type": "int", "default": 30, "min": 0, "max": 441}
    ]
)
class ColorMaskNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"mask": None}
        if len(image.shape) == 2 or image.shape[2] == 1:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        mode = int(params.get('mode', 0))
        color_hex = str(params.get('color', '#FF0000')).strip().lstrip('#')
        if len(color_hex) == 3: color_hex = ''.join([c*2 for c in color_hex])
        if len(color_hex) != 6: color_hex = "FF0000"
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)

        if mode == 1:  # RGB Distance
            thresh = int(params.get('threshold', 30))
            target = np.array([b, g, r], dtype=np.float32)
            dist = np.sqrt(np.sum((image.astype(np.float32) - target) ** 2, axis=2))
            mask = (dist <= thresh).astype(np.uint8) * 255
        else:  # HSV Range
            h_tol = int(params.get('h_tol', 10))
            s_tol = int(params.get('s_tol', 40))
            v_tol = int(params.get('v_tol', 40))
            target_hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]
            th, ts, tv = int(target_hsv[0]), int(target_hsv[1]), int(target_hsv[2])
            h_min, h_max = (th - h_tol) % 180, (th + h_tol) % 180
            s_min, s_max = max(0, ts - s_tol), min(255, ts + s_tol)
            v_min, v_max = max(0, tv - v_tol), min(255, tv + v_tol)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            if h_min < h_max:
                mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min], dtype=np.uint8), 
                                  np.array([h_max, s_max, v_max], dtype=np.uint8))
            else:
                mask1 = cv2.inRange(hsv, np.array([h_min, s_min, v_min], dtype=np.uint8), 
                                   np.array([179, s_max, v_max], dtype=np.uint8))
                mask2 = cv2.inRange(hsv, np.array([0, s_min, v_min], dtype=np.uint8), 
                                   np.array([h_max, s_max, v_max], dtype=np.uint8))
                mask = cv2.bitwise_or(mask1, mask2)
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
        {"id": "operation", "label": "Operation", "type": "enum", "options": ["Dilate", "Erode"], "default": 0},
        {"id": "size", "label": "Kernel Size", "type": "scalar", "min": 1, "max": 51, "default": 3}
    ]
)
class MorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"mask": None}
        
        op_idx = int(params.get('operation', 0))
        size = int(params.get('size', 3))
        if size < 1: size = 1
        
        kernel = np.ones((size, size), np.uint8)
        res = cv2.dilate(mask, kernel) if op_idx == 0 else cv2.erode(mask, kernel)
        return {"mask": res}
