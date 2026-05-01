from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='cv_shadow_highlight',
    label='Shadow removal',
    category='cv',
    icon='Sun',
    description="Selectively brightens shadows and darkens highlights while preserving midtones, similar to professional photo editors.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'shadows',    'label': 'Shadows (Boost)',     'type': 'scalar', 'min': 0, 'max': 100, 'default': 30},
        {'id': 'highlights', 'label': 'Highlights (Reduce)', 'type': 'scalar', 'min': 0, 'max': 100, 'default': 0},
        {'id': 'radius',     'label': 'Mask Radius',         'type': 'scalar', 'min': 1, 'max': 251, 'step': 2, 'default': 41},
    ]
)
class ShadowHighlightNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        s_amt = float(params.get('shadows', 30)) / 100.0
        h_amt = float(params.get('highlights', 0)) / 100.0
        radius = int(params.get('radius', 41))
        if radius % 2 == 0: radius += 1
        
        # Convert to LAB color space to process Luminance (L) independently
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l_float = l.astype(np.float32)
        
        # --- SHADOWS ---
        # Generate a shadow mask based on the inverse of luminance
        # We blur the mask to ensure soft transitions and avoid edge halos
        shadow_mask = 255.0 - l_float
        shadow_mask = cv2.GaussianBlur(shadow_mask, (radius, radius), 0)
        
        # Apply shadow boost: the darker the area, the more it is brightened
        l_mod = l_float + (shadow_mask * s_amt)
        
        # --- HIGHLIGHTS ---
        # Generate a highlight mask based on the current modified luminance
        highlight_mask = l_mod
        highlight_mask = cv2.GaussianBlur(highlight_mask, (radius, radius), 0)
        
        # Apply highlight reduction: the brighter the area, the more it is darkened
        l_mod = l_mod - (highlight_mask * h_amt)
        
        # Final clipping and color space conversion
        l_final = np.clip(l_mod, 0, 255).astype(np.uint8)
        lab_final = cv2.merge((l_final, a, b))
        
        return {'main': cv2.cvtColor(lab_final, cv2.COLOR_LAB2BGR)}
