import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="util_fill_holes",
    label="Fill Holes",
    category='mask',
    icon="ShieldCheck",
    description="Fills holes (black areas) inside white objects in a binary mask.",
    inputs=[{"id": "mask", "color": "any"}],
    outputs=[{"id": "mask", "color": "mask"}],
    params=[]
)
class FillHolesNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"mask": None}
        
        # Ensure 8-bit grayscale
        if len(mask.shape) == 3:
            if mask.shape[2] >= 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            else:
                mask = mask[:, :, 0]
        mask = mask.astype(np.uint8)
        
        # Fill holes using floodFill
        mask_filled = mask.copy()
        h, w = mask.shape[:2]
        flood_mask = np.zeros((h+2, w+2), np.uint8)
        cv2.floodFill(mask_filled, flood_mask, (0,0), 255)
        mask_filled_inv = cv2.bitwise_not(mask_filled)
        result = mask | mask_filled_inv
        
        return {"mask": result}

@vision_node(
    type_id="util_colormap",
    label="Apply Colormap",
    category='visualize',
    icon="Palette",
    description="Applies a scientific colormap (Heatmap, Jet, Magma) to a grayscale image.",
    inputs=[{"id": "image", "color": "any"}],
    outputs=[{"id": "image", "color": "image"}],
    params=[
        {"id": "map", "label": "Colormap", "type": "enum", "options": ["Jet", "Heatmap (HOT)", "Magma", "Viridis", "Inferno", "Cividis", "Rainbow"], "default": 0}
    ]
)
class ApplyColormapNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"image": None}
        
        # Ensure 8-bit grayscale
        if len(img.shape) == 3:
            if img.shape[2] >= 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                img = img[:, :, 0]
        
        # Normalize if needed
        if img.dtype != np.uint8 or img.max() <= 1.0:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        map_idx = int(params.get('map', 0))
        maps = [
            cv2.COLORMAP_JET, cv2.COLORMAP_HOT, cv2.COLORMAP_MAGMA,
            cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_INFERNO, cv2.COLORMAP_CIVIDIS,
            cv2.COLORMAP_RAINBOW
        ]
        
        res = cv2.applyColorMap(img, maps[min(map_idx, len(maps)-1)])
        return {"image": res}

@vision_node(
    type_id="util_image_math",
    label="Image Math (Power)",
    category='cv',
    icon="Zap",
    description="Applies mathematical power operation (gamma) to image pixels.",
    inputs=[{"id": "image", "color": "any"}],
    outputs=[{"id": "image", "color": "image"}],
    params=[
        {"id": "power", "label": "Power (Gamma)", "type": "float", "default": 1.0, "min": 0.1, "max": 5.0}
    ]
)
class ImageMathNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"image": None}
        
        p = float(params.get('power', 1.0))
        # Normalize 0-1, apply power, then back to 0-255
        norm = img.astype(float) / 255.0
        res = np.power(norm, p)
        return {"image": (res * 255).astype(np.uint8)}

@vision_node(
    type_id="util_draw_contours",
    label="Draw Contours",
    category='draw',
    icon="PenTool",
    description="Draws a list of contours onto an image or a new black background.",
    inputs=[{"id": "image", "color": "any"}, {"id": "contours", "color": "list"}],
    outputs=[{"id": "image", "color": "image"}],
    params=[
        {"id": "color", "label": "Color", "type": "color", "default": "#00FF00"},
        {"id": "thickness", "label": "Thickness", "type": "int", "default": 2, "min": -1, "max": 20},
        {"id": "background", "label": "New Background", "type": "boolean", "default": False}
    ]
)
class DrawContoursNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        cnts = inputs.get('contours')
        if cnts is None: return {"image": img}
        
        # Handle background
        if params.get('background', False) or img is None:
            h, w = (img.shape[0], img.shape[1]) if img is not None else (480, 640)
            canvas = np.zeros((h, w, 3), dtype=np.uint8)
        else:
            canvas = img.copy()
            if len(canvas.shape) == 2:
                canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
        
        # Parse color
        import re
        hex_c = str(params.get('color', '#00FF00')).lstrip('#')
        bgr = (int(hex_c[4:6], 16), int(hex_c[2:4], 16), int(hex_c[0:2], 16)) if len(hex_c) == 6 else (0, 255, 0)
        
        thick = int(params.get('thickness', 2))
        
        # Draw. cnts is expected to be a list of numpy arrays
        cv2.drawContours(canvas, cnts, -1, bgr, thick)
        
        return {"image": canvas}
