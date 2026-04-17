from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_blend_modes',
    label='Advanced Blend',
    category='blend',
    icon='Layers',
    inputs=[
        {'id': 'image_a', 'color': 'image'},
        {'id': 'image_b', 'color': 'image'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {
            'id': 'mode', 
            'type': 'enum',
            'options': [
                'Multiply', 'Screen', 'Overlay', 'Hard Light', 'Soft Light', 
                'Color Dodge', 'Color Burn', 'Linear Dodge (Add)', 'Linear Burn',
                'Vivid Light', 'Linear Light', 'Pin Light', 'Hard Mix',
                'Difference', 'Exclusion', 'Subtract', 'Divide', 'Grain Extract', 'Grain Merge',
                'Darken', 'Lighten'
            ],
            'default': 0
        },
        {'id': 'opacity', 'min': 0, 'max': 100, 'step': 1, 'default': 100}
    ]
)
class AdvancedBlendNode(NodeProcessor):
    def process(self, inputs, params):
        img_a = inputs.get('image_a')
        img_b = inputs.get('image_b')
        
        if img_a is None: return {'main': img_b}
        if img_b is None: return {'main': img_a}
        
        if len(img_a.shape) == 2: img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        if len(img_b.shape) == 2: img_b = cv2.cvtColor(img_b, cv2.COLOR_GRAY2BGR)

        A = img_a.astype(np.float32) / 255.0
        B = img_b.astype(np.float32) / 255.0
        
        mode = int(params.get('mode', 0))
        opacity = float(params.get('opacity', 100)) / 100.0
        
        res = A.copy()
        
        if mode == 0: # Multiply
            res = A * B
        elif mode == 1: # Screen
            res = 1.0 - (1.0 - A) * (1.0 - B)
        elif mode == 2: # Overlay
            res = np.where(A < 0.5, 2.0 * A * B, 1.0 - 2.0 * (1.0 - A) * (1.0 - B))
        elif mode == 3: # Hard Light
            res = np.where(B < 0.5, 2.0 * A * B, 1.0 - 2.0 * (1.0 - A) * (1.0 - B))
        elif mode == 4: # Soft Light
            res = (1.0 - 2.0 * B) * (A ** 2) + 2.0 * B * A
        elif mode == 5: # Color Dodge
            res = np.divide(B, 1.0 - A, out=np.ones_like(B), where=(1.0 - A) != 0)
        elif mode == 6: # Color Burn
            res = 1.0 - np.divide(1.0 - B, A, out=np.ones_like(B), where=A != 0)
        elif mode == 7: # Linear Dodge (Add)
            res = A + B
        elif mode == 8: # Linear Burn
            res = A + B - 1.0
        elif mode == 9: # Vivid Light
            res = np.where(B < 0.5, 
                           1.0 - np.divide(1.0 - A, 2.0 * B, out=np.ones_like(A), where=(2.0 * B) != 0),
                           np.divide(A, 2.0 * (1.0 - B), out=np.ones_like(A), where=(2.0 * (1.0 - B)) != 0))
        elif mode == 10: # Linear Light
            res = A + 2.0 * B - 1.0
        elif mode == 11: # Pin Light
            res = np.where(B < 0.5, np.minimum(A, 2.0 * B), np.maximum(A, 2.0 * B - 1.0))
        elif mode == 12: # Hard Mix
            res = np.where(A + B >= 1.0, 1.0, 0.0)
        elif mode == 13: # Difference
            res = np.abs(A - B)
        elif mode == 14: # Exclusion
            res = A + B - 2.0 * A * B
        elif mode == 15: # Subtract
            res = B - A
        elif mode == 16: # Divide
            res = np.divide(B, A, out=np.ones_like(B), where=A != 0)
        elif mode == 17: # Grain Extract
            res = A - B + 0.5
        elif mode == 18: # Grain Merge
            res = A + B - 0.5
        elif mode == 19: # Darken
            res = np.minimum(A, B)
        elif mode == 20: # Lighten
            res = np.maximum(A, B)

        # Clamping
        res = np.clip(res, 0, 1)
        
        # Opacity blend
        final = A * (1.0 - opacity) + res * opacity
        
        # Back to uint8
        return {
            'main': (final * 255).astype(np.uint8),
            'display_text': params['mode_options'][mode] if 'mode_options' in params else params.get('options', [])[mode] if 'options' in params else f"Mode {mode}"
        }
