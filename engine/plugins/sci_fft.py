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
        {'id': 'log_scale',   'label': 'Log Intensity', 'type': 'boolean', 'default': True},
        {'id': 'filter_type', 'label': 'Filter Type',  'type': 'string', 'default': 'None', 
         'options': ['None', 'Low-pass', 'High-pass', 'Band-pass', 'Band-stop']},
        {'id': 'low_cutoff',  'label': 'Min Cutoff',   'type': 'scalar', 'min': 0, 'max': 500, 'default': 0},
        {'id': 'high_cutoff', 'label': 'Max Cutoff',   'type': 'scalar', 'min': 0, 'max': 500, 'default': 50},
    ]
)
class FFTNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'magnitude': None}
            
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
            
        dft = np.fft.fft2(gray.astype(np.float32))
        dft_shift = np.fft.fftshift(dft)
        
        f_type = params.get('filter_type', 'None')
        low = float(params.get('low_cutoff', 0))
        high = float(params.get('high_cutoff', 50))
        
        # Ensure high >= low for logic safety
        if high < low: high = low
        
        mask = np.ones((rows, cols), np.float32)
        if f_type != 'None':
            y, x = np.ogrid[-crow:rows-crow, -ccol:cols-ccol]
            dist_sq = x*x + y*y
            
            if f_type == 'Low-pass':
                mask = np.where(dist_sq <= high*high, 1, 0).astype(np.float32)
            elif f_type == 'High-pass':
                mask = np.where(dist_sq >= low*low, 1, 0).astype(np.float32)
            elif f_type == 'Band-pass':
                mask = np.where((dist_sq >= low*low) & (dist_sq <= high*high), 1, 0).astype(np.float32)
            elif f_type == 'Band-stop':
                mask = np.where((dist_sq >= low*low) & (dist_sq <= high*high), 0, 1).astype(np.float32)
                
            dft_shift = dft_shift * mask
            
        mag = np.abs(dft_shift)
        if params.get('log_scale', True):
            mag = 20 * np.log(mag + 1)
            
        cv2.normalize(mag, mag, 0, 255, cv2.NORM_MINMAX)
        mag_out = mag.astype(np.uint8)
        color_mag = cv2.applyColorMap(mag_out, cv2.COLORMAP_INFERNO)
        
        if f_type != 'None':
            f_ishift = np.fft.ifftshift(dft_shift)
            img_back = np.fft.ifft2(f_ishift)
            img_back = np.abs(img_back)
            cv2.normalize(img_back, img_back, 0, 255, cv2.NORM_MINMAX)
            result = img_back.astype(np.uint8)
            if len(img.shape) == 3:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        else:
            result = img
            
        return {
            'main': result,
            'magnitude': color_mag,
            'data': dft_shift.tolist() if isinstance(dft_shift, np.ndarray) else None
        }
