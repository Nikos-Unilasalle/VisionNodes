from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_sobel',
    label='Sobel Edge filter',
    category='filter',
    icon='Activity',
    description="Detects horizontal and vertical gradients using the Sobel operator.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'kernel_size', 'min': 1, 'max': 7, 'step': 2, 'default': 3},
        {'id': 'x_dir', 'label': 'X Direction', 'type': 'bool', 'default': True},
        {'id': 'y_dir', 'label': 'Y Direction', 'type': 'bool', 'default': True}
    ]
)
class SobelNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        ksize = int(params.get('kernel_size', 3))
        dx = int(params.get('x_dir', 1))
        dy = int(params.get('y_dir', 1))
        
        # S'assurer d'avoir au moins une direction
        if dx == 0 and dy == 0:
            dx = 1
        
        # Passage en gris pour Sobel
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
        sobelx = cv2.Sobel(gray, cv2.CV_64F, dx, 0, ksize=ksize) if dx > 0 else np.zeros(gray.shape, dtype=np.float64)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, dy, ksize=ksize) if dy > 0 else np.zeros(gray.shape, dtype=np.float64)
        
        # Magnitude
        magnitude = cv2.magnitude(sobelx, sobely)
        magnitude = cv2.convertScaleAbs(magnitude)
        
        return {'main': magnitude}
