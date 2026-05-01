from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_fft',
    label='FFT Analysis',
    category=['analysis', 'scientific'],
    icon='Activity',
    description="Computes the 2D Fast Fourier Transform (FFT) to visualize the frequency spectrum of the image. Outputs magnitude, phase, and complex data for scientific analysis and perfect reconstruction via IFFT.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'magnitude', 'color': 'image'},
        {'id': 'phase', 'color': 'image'},
        {'id': 'complex_data', 'color': 'data'}
    ],
    params=[
        {'id': 'log_scale',   'label': 'Log Intensity', 'type': 'boolean', 'default': True},
        {'id': 'preserve_dynamic_range', 'label': 'Preserve Dynamic Range', 'type': 'boolean', 'default': False,
         'description': 'When enabled, avoids normalization to preserve absolute values for scientific accuracy'},
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
            return {'main': None, 'magnitude': None, 'phase': None, 'complex_data': None}
            
        # Store original dtype for reconstruction
        original_dtype = img.dtype
        
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
            
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
            
        # Compute FFT with float64 for precision
        dft = np.fft.fft2(gray.astype(np.float64))
        dft_shift = np.fft.fftshift(dft)
        
        # Extract magnitude and phase BEFORE filtering
        mag_original = np.abs(dft_shift)
        phase_original = np.angle(dft_shift)
        
        f_type = params.get('filter_type', 'None')
        low = float(params.get('low_cutoff', 0))
        high = float(params.get('high_cutoff', 50))
        
        # Ensure high >= low for logic safety
        if high < low: high = low
        
        mask = np.ones((rows, cols), np.float64)
        if f_type != 'None':
            y, x = np.ogrid[-crow:rows-crow, -ccol:cols-ccol]
            dist_sq = x*x + y*y
            
            if f_type == 'Low-pass':
                mask = np.where(dist_sq <= high*high, 1, 0).astype(np.float64)
            elif f_type == 'High-pass':
                mask = np.where(dist_sq >= low*low, 1, 0).astype(np.float64)
            elif f_type == 'Band-pass':
                mask = np.where((dist_sq >= low*low) & (dist_sq <= high*high), 1, 0).astype(np.float64)
            elif f_type == 'Band-stop':
                mask = np.where((dist_sq >= low*low) & (dist_sq <= high*high), 0, 1).astype(np.float64)
                
            dft_shift = dft_shift * mask
            # Update magnitude and phase after filtering
            mag_original = np.abs(dft_shift)
            phase_original = np.angle(dft_shift)
            
        preserve = params.get('preserve_dynamic_range', False)
        
        # Prepare magnitude visualization
        mag = mag_original.copy()
        if params.get('log_scale', True):
            mag = 20 * np.log(mag + 1)
            
        if not preserve:
            cv2.normalize(mag, mag, 0, 255, cv2.NORM_MINMAX)
            mag_out = mag.astype(np.uint8)
        else:
            # Scale to uint8 range but keep info for data output
            mag_min, mag_max = mag.min(), mag.max()
            if mag_max > mag_min:
                mag_out = ((mag - mag_min) / (mag_max - mag_min) * 255).astype(np.uint8)
            else:
                mag_out = np.zeros_like(mag, dtype=np.uint8)
        
        color_mag = cv2.applyColorMap(mag_out, cv2.COLORMAP_INFERNO)
        
        # Prepare phase visualization
        phase_vis = phase_original.copy()
        # Phase is in [-pi, pi], normalize to [0, 255]
        phase_normalized = (phase_vis + np.pi) / (2 * np.pi) * 255
        phase_out = phase_normalized.astype(np.uint8)
        color_phase = cv2.applyColorMap(phase_out, cv2.COLORMAP_TWILIGHT)
        
        # Reconstruct image if filter applied
        if f_type != 'None':
            f_ishift = np.fft.ifftshift(dft_shift)
            img_back = np.fft.ifft2(f_ishift)
            img_back = np.abs(img_back)
            
            if preserve:
                # Keep original dynamic range
                img_back = np.clip(img_back, 0, 255)
            else:
                cv2.normalize(img_back, img_back, 0, 255, cv2.NORM_MINMAX)
            
            result = img_back.astype(np.uint8)
            if len(img.shape) == 3:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        else:
            result = img
            
        return {
            'main': result,
            'magnitude': color_mag,
            'phase': color_phase,
            'complex_data': {
                'real': dft_shift.real.tolist(),
                'imag': dft_shift.imag.tolist(),
                'shape': list(dft_shift.shape),
                'dtype': 'complex64'
            }
        }
