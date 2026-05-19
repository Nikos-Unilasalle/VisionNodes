import cv2
import numpy as np
from registry import vision_node, NodeProcessor

# Standard Laplacian kernels (∇²)
_KERNELS = {
    0: np.array([[0,  1, 0],
                 [1, -4, 1],
                 [0,  1, 0]], dtype=np.float32),   # 4-connected
    1: np.array([[1,  1, 1],
                 [1, -8, 1],
                 [1,  1, 1]], dtype=np.float32),   # 8-connected
    2: np.array([[0.05, 0.2, 0.05],
                 [0.2, -1.0, 0.2],
                 [0.05, 0.2, 0.05]], dtype=np.float32),  # weighted (smoother)
}

@vision_node(
    type_id='filter_laplacian',
    label='Laplacian',
    category='image',
    icon='Sigma',
    description="Computes the discrete Laplacian (∇²) of an image in float32 precision. Essential for reaction-diffusion diffusion step.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'laplacian', 'color': 'image'}],
    params=[
        {'id': 'kernel',    'label': 'Kernel',      'type': 'enum',   'options': ['4-connected', '8-connected', 'Weighted'], 'default': 0},
        {'id': 'scale',     'label': 'Scale',        'type': 'float',  'default': 1.0, 'min': 0.001, 'max': 10.0, 'step': 0.01},
        {'id': 'normalize', 'label': 'Normalize out','type': 'bool',   'default': False},
    ]
)
class LaplacianNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'laplacian': None}

        src = img.astype(np.float32)
        if len(src.shape) == 3:
            src = cv2.cvtColor(src if src.max() > 1.0 else (src * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        elif src.max() > 1.0:
            src = src / 255.0

        kernel_idx = int(params.get('kernel', 0))
        kernel = _KERNELS.get(kernel_idx, _KERNELS[0])
        scale  = float(params.get('scale', 1.0))

        lap = cv2.filter2D(src, cv2.CV_32F, kernel) * scale

        if bool(params.get('normalize', False)):
            mn, mx = lap.min(), lap.max()
            if mx > mn:
                lap = (lap - mn) / (mx - mn)

        return {'laplacian': lap}
