from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_fft',
    label='FFT Analysis',
    category=['analysis', 'scientific'],
    icon='Activity',
    description="Computes the 2D Fast Fourier Transform (FFT) to visualize the frequency spectrum of the image. Useful for texture analysis and noise detection.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}, {'id': 'magnitude', 'color': 'image'}],
    params=[
        {'id': 'log_scale', 'label': 'Log Intensity', 'type': 'boolean', 'default': True},
        {'id': 'center',    'label': 'Center Shift',  'type': 'boolean', 'default': True},
    ]
)
class FFTNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'magnitude': None}
            
        # Convert to gray
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
        # Compute FFT
        dft = np.fft.fft2(gray)
        
        if params.get('center', True):
            dft_shift = np.fft.fftshift(dft)
        else:
            dft_shift = dft
            
        # Magnitude Spectrum
        mag = np.abs(dft_shift)
        
        if params.get('log_scale', True):
            mag = 20 * np.log(mag + 1)
            
        # Normalize for visualization
        cv2.normalize(mag, mag, 0, 255, cv2.NORM_MINMAX)
        mag_out = mag.astype(np.uint8)
        
        # Apply a colormap for scientific visualization (Inferno or Jet)
        color_mag = cv2.applyColorMap(mag_out, cv2.COLORMAP_INFERNO)
        
        return {
            'main': color_mag,
            'magnitude': mag_out
        }
