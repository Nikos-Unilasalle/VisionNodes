from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_blend_modes',
    label='Blend',
    category='image',
    icon='Layers',
    description="Blends two images. Normal = linear opacity mix. Advanced modes: Multiply, Overlay, etc.",
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
                'Normal',
                'Multiply', 'Screen', 'Overlay', 'Hard Light', 'Soft Light',
                'Color Dodge', 'Color Burn', 'Linear Dodge (Add)', 'Linear Burn',
                'Vivid Light', 'Linear Light', 'Pin Light', 'Hard Mix',
                'Difference', 'Exclusion', 'Subtract', 'Divide', 'Grain Extract', 'Grain Merge',
                'Darken', 'Lighten'
            ],
            'default': 0
        },
        {'id': 'opacity', 'min': 0, 'max': 100, 'step': 1, 'default': 50}
    ]
)
class BlendNode(NodeProcessor):
    def process(self, inputs, params):
        img_a = inputs.get('image_a')
        img_b = inputs.get('image_b')

        if img_a is None: return {'main': img_b}
        if img_b is None: return {'main': img_a}

        if len(img_a.shape) == 2: img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        if len(img_b.shape) == 2: img_b = cv2.cvtColor(img_b, cv2.COLOR_GRAY2BGR)

        def to_float(img):
            f = img.astype(np.float32)
            return f / 255.0 if f.max() > 1.0 else f

        A = to_float(img_a)
        B = to_float(img_b)

        mode = int(params.get('mode', 0))
        opacity = float(params.get('opacity', 50)) / 100.0

        if mode == 0:   # Normal
            res = B
        elif mode == 1: # Multiply
            res = A * B
        elif mode == 2: # Screen
            res = 1.0 - (1.0 - A) * (1.0 - B)
        elif mode == 3: # Overlay
            res = np.where(A < 0.5, 2.0 * A * B, 1.0 - 2.0 * (1.0 - A) * (1.0 - B))
        elif mode == 4: # Hard Light
            res = np.where(B < 0.5, 2.0 * A * B, 1.0 - 2.0 * (1.0 - A) * (1.0 - B))
        elif mode == 5: # Soft Light
            res = (1.0 - 2.0 * B) * (A ** 2) + 2.0 * B * A
        elif mode == 6: # Color Dodge
            res = np.divide(B, 1.0 - A, out=np.ones_like(B), where=(1.0 - A) != 0)
        elif mode == 7: # Color Burn
            res = 1.0 - np.divide(1.0 - B, A, out=np.ones_like(B), where=A != 0)
        elif mode == 8: # Linear Dodge (Add)
            res = A + B
        elif mode == 9: # Linear Burn
            res = A + B - 1.0
        elif mode == 10: # Vivid Light
            res = np.where(B < 0.5,
                           1.0 - np.divide(1.0 - A, 2.0 * B, out=np.ones_like(A), where=(2.0 * B) != 0),
                           np.divide(A, 2.0 * (1.0 - B), out=np.ones_like(A), where=(2.0 * (1.0 - B)) != 0))
        elif mode == 11: # Linear Light
            res = A + 2.0 * B - 1.0
        elif mode == 12: # Pin Light
            res = np.where(B < 0.5, np.minimum(A, 2.0 * B), np.maximum(A, 2.0 * B - 1.0))
        elif mode == 13: # Hard Mix
            res = np.where(A + B >= 1.0, 1.0, 0.0)
        elif mode == 14: # Difference
            res = np.abs(A - B)
        elif mode == 15: # Exclusion
            res = A + B - 2.0 * A * B
        elif mode == 16: # Subtract
            res = B - A
        elif mode == 17: # Divide
            res = np.divide(B, A, out=np.ones_like(B), where=A != 0)
        elif mode == 18: # Grain Extract
            res = A - B + 0.5
        elif mode == 19: # Grain Merge
            res = A + B - 0.5
        elif mode == 20: # Darken
            res = np.minimum(A, B)
        elif mode == 21: # Lighten
            res = np.maximum(A, B)
        else:
            res = B

        return {'main': np.clip(A * (1.0 - opacity) + res * opacity, 0.0, 1.0).astype(np.float32)}
