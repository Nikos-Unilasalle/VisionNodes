from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_blend_images',
    label='Simple Image Blend',
    category='image',
    icon='Layers',
    description="Linearly blends two images based on a simple opacity factor.",
    inputs=[
        {'id': 'image_a', 'color': 'image'},
        {'id': 'image_b', 'color': 'image'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'opacity', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.5}
    ]
)
class ImageBlendNode(NodeProcessor):
    @staticmethod
    def _to_float(img):
        f = img.astype(np.float32)
        if f.max() > 1.0:
            f /= 255.0
        if len(f.shape) == 2:
            f = cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
        return f

    def process(self, inputs, params):
        img_a = inputs.get('image_a')
        img_b = inputs.get('image_b')

        if img_a is None: return {'main': img_b}
        if img_b is None: return {'main': img_a}

        opacity = float(params.get('opacity', 0.5))

        a = self._to_float(img_a)
        b = self._to_float(cv2.resize(img_b, (a.shape[1], a.shape[0])))

        return {'main': np.clip(a * (1.0 - opacity) + b * opacity, 0.0, 1.0).astype(np.float32)}
