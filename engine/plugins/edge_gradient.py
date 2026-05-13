from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_gradient',
    label='Image Gradient',
    category='cv',
    icon='ArrowUpRight',
    description="Computes image gradients (magnitude and orientation) using Sobel or Scharr operators.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'magnitude', 'label': 'Magnitude', 'color': 'image'},
        {'id': 'angle', 'label': 'Orientation', 'color': 'image'},
        {'id': 'dx', 'label': 'Dx (Horizontal)', 'color': 'any'},
        {'id': 'dy', 'label': 'Dy (Vertical)', 'color': 'any'}
    ],
    params=[
        {'id': 'method', 'label': 'Method', 'type': 'enum', 'options': ['Sobel', 'Scharr'], 'default': 0},
        {'id': 'ksize', 'label': 'Kernel Size', 'type': 'scalar', 'min': 1, 'max': 7, 'step': 2, 'default': 3},
        {'id': 'normalize', 'label': 'Normalize Out', 'type': 'bool', 'default': True}
    ]
)
class GradientNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'magnitude': None, 'angle': None, 'dx': None, 'dy': None}
        
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
        method = int(params.get('method', 0))
        ksize = int(params.get('ksize', 3))
        do_norm = bool(params.get('normalize', True))
        
        # Ensure ksize is odd and >= 1 for Sobel
        if method == 0: # Sobel
            if ksize % 2 == 0: ksize += 1
            dx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=ksize)
            dy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=ksize)
        else: # Scharr
            dx = cv2.Scharr(gray, cv2.CV_64F, 1, 0)
            dy = cv2.Scharr(gray, cv2.CV_64F, 0, 1)
            
        # Magnitude and Angle
        magnitude, angle = cv2.cartToPolar(dx, dy, angleInDegrees=True)
        
        # Visualization / Normalization
        if do_norm:
            mag_vis = cv2.convertScaleAbs(magnitude)
            # For angle, we can normalize 0-360 to 0-255 for grayscale visualization
            # or keep it as float for calculations. Here we provide a visual version.
            ang_vis = (angle * (255.0 / 360.0)).astype(np.uint8)
        else:
            mag_vis = magnitude
            ang_vis = angle
            
        return {
            'magnitude': mag_vis,
            'angle': ang_vis,
            'dx': dx,
            'dy': dy
        }
