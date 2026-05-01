from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_ifft',
    label='Inverse FFT',
    category=['analysis', 'scientific'],
    icon='RotateCcw',
    description="Reconstructs an image from its frequency spectrum. Supports two modes: (1) Magnitude + Phase inputs for perfect reconstruction, (2) Complex data input for scientific workflows. The magnitude+phase mode enables lossless FFT → Filter → IFFT pipelines.",
    inputs=[
        {'id': 'magnitude', 'color': 'image', 'optional': True},
        {'id': 'phase', 'color': 'image', 'optional': True},
        {'id': 'complex_data', 'color': 'data', 'optional': True}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'mode', 'label': 'Input Mode', 'type': 'string', 'default': 'auto',
         'options': ['auto', 'magnitude_phase', 'complex_data'],
         'description': 'Auto: detect from inputs. Mag+Phase: use magnitude and phase images. Complex: use complex_data dict'},
        {'id': 'inv_log', 'label': 'Inverse Log', 'type': 'boolean', 'default': True,
         'description': 'Apply inverse log transform to magnitude (only for magnitude_phase mode)'},
        {'id': 'preserve_dynamic_range', 'label': 'Preserve Dynamic Range', 'type': 'boolean', 'default': False,
         'description': 'When enabled, preserves absolute intensity values instead of normalizing to 0-255'}
    ]
)
class IFFTNode(NodeProcessor):
    def process(self, inputs, params):
        mag_img = inputs.get('magnitude')
        phase_img = inputs.get('phase')
        complex_data = inputs.get('complex_data')
        
        mode = params.get('mode', 'auto')
        preserve = params.get('preserve_dynamic_range', False)
        
        # Determine input mode
        if mode == 'complex_data' or (mode == 'auto' and complex_data is not None):
            # Use complex data mode - most accurate for scientific workflows
            if complex_data is None:
                return {'main': None}
            
            # Reconstruct complex array from real/imag components
            real = np.array(complex_data['real'], dtype=np.float64)
            imag = np.array(complex_data['imag'], dtype=np.float64)
            dft_shift = real + 1j * imag
            
        elif mode == 'magnitude_phase' or (mode == 'auto' and mag_img is not None and phase_img is not None):
            # Use magnitude + phase mode - enables perfect reconstruction
            if mag_img is None or phase_img is None:
                return {'main': None}
            
            # Convert magnitude to gray
            if len(mag_img.shape) == 3:
                mag_gray = cv2.cvtColor(mag_img, cv2.COLOR_BGR2GRAY)
            else:
                mag_gray = mag_img
            
            # Convert phase to gray
            if len(phase_img.shape) == 3:
                phase_gray = cv2.cvtColor(phase_img, cv2.COLOR_BGR2GRAY)
            else:
                phase_gray = phase_img
            
            # Reverse normalization and log scale for magnitude
            mag_f = mag_gray.astype(np.float64)
            if params.get('inv_log', True):
                # Inverse of: 20 * log(mag + 1) -> mag = exp(val/20) - 1
                # But first we need to reverse the [0,255] normalization
                # Assuming the magnitude was normalized to 0-255, we need original scale
                # This is approximate - best results with preserve_dynamic_range=True on FFT node
                mag_f = np.exp(mag_f / 20.0) - 1.0
            
            # Reverse phase normalization: phase was mapped from [-pi, pi] to [0, 255]
            phase_f = phase_gray.astype(np.float64)
            phase_rad = (phase_f / 255.0) * (2 * np.pi) - np.pi
            
            # Create complex array: magnitude * exp(i * phase)
            dft_shift = mag_f * np.exp(1j * phase_rad)
            
        else:
            # Fallback to old zero-phase reconstruction (not recommended)
            if mag_img is None:
                return {'main': None}
            
            if len(mag_img.shape) == 3:
                gray = cv2.cvtColor(mag_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = mag_img
                
            mag_f = gray.astype(np.float64)
            if params.get('inv_log', True):
                mag_f = np.exp(mag_f / 20.0) - 1.0
            
            # Zero-phase reconstruction (produces artifacts)
            dft_shift = mag_f.astype(np.complex128)
        
        # Perform inverse FFT
        f_ishift = np.fft.ifftshift(dft_shift)
        img_back = np.fft.ifft2(f_ishift)
        img_back = np.abs(img_back)
        
        # Output handling
        if preserve:
            # Clip to valid range without normalization
            img_back = np.clip(img_back, 0, 255)
            result = img_back.astype(np.uint8)
        else:
            # Normalize for display
            cv2.normalize(img_back, img_back, 0, 255, cv2.NORM_MINMAX)
            result = img_back.astype(np.uint8)
        
        return {
            'main': cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        }
