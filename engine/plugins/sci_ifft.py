from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_ifft',
    label='Inverse FFT',
    category=['analysis', 'scientific'],
    icon='RotateCcw',
    description="Reconstructs an image from its frequency magnitude spectrum. Since phase information is often missing, this uses a Zero-Phase reconstruction to visualize frequency contributions.",
    inputs=[{'id': 'magnitude', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'inv_log', 'label': 'Inverse Log', 'type': 'boolean', 'default': True},
    ]
)
class IFFTNode(NodeProcessor):
    def process(self, inputs, params):
        mag_img = inputs.get('magnitude')
        if mag_img is None:
            return {'main': None}
            
        # Convert to gray
        if len(mag_img.shape) == 3:
            gray = cv2.cvtColor(mag_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = mag_img
            
        # 1. Reverse normalization and log scale
        mag_f = gray.astype(np.float32)
        if params.get('inv_log', True):
            # Inverse of: 20 * log(mag + 1) -> mag = exp(val/20) - 1
            mag_f = np.exp(mag_f / 20.0) - 1.0
            
        # 2. Create complex array with Zero Phase
        # mag * exp(i * phase) -> phase = 0 -> mag * (1 + 0i) = mag
        dft_shift = mag_f.astype(np.complex64)
        
        # 3. Inverse FFT
        f_ishift = np.fft.ifftshift(dft_shift)
        img_back = np.fft.ifft2(f_ishift)
        img_back = np.abs(img_back)
        
        # 4. Final normalization for display
        cv2.normalize(img_back, img_back, 0, 255, cv2.NORM_MINMAX)
        result = img_back.astype(np.uint8)
        
        return {
            'main': cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        }
