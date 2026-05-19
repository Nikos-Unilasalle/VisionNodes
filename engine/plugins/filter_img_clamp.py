import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='filter_img_clamp',
    label='Image Clamp',
    category='image',
    icon='Minimize2',
    description="Clamps all pixel values of a float image between min and max. Prevents overflow in iterative pipelines (reaction-diffusion, accumulators).",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'image', 'color': 'image'}],
    params=[
        {'id': 'min_val', 'label': 'Min', 'type': 'float', 'default': 0.0, 'min': -10.0, 'max': 10.0, 'step': 0.01},
        {'id': 'max_val', 'label': 'Max', 'type': 'float', 'default': 1.0, 'min': -10.0, 'max': 10.0, 'step': 0.01},
    ]
)
class ImageClampNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'image': None}

        mn = float(params.get('min_val', 0.0))
        mx = float(params.get('max_val', 1.0))
        return {'image': np.clip(img, mn, mx).astype(np.float32)}
