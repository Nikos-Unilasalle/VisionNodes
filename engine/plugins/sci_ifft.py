from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_ifft',
    label='Inverse FFT',
    category=['analysis', 'scientific'],
    icon='RotateCcw',
    description="Reconstructs an image from spectral data. Supports perfect reconstruction from Complex Data or approximation from Magnitude + Phase. Handles color channels.",
    inputs=[
        {'id': 'complex_data', 'color': 'data', 'optional': True},
        {'id': 'magnitude', 'color': 'image', 'optional': True},
        {'id': 'phase', 'color': 'image', 'optional': True}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'mode', 'label': 'Input Mode', 'type': 'string', 'default': 'auto',
         'options': ['auto', 'complex_data', 'magnitude_phase']},
        {'id': 'inv_log', 'label': 'Inverse Log', 'type': 'boolean', 'default': True,
         'description': 'Apply to magnitude if it was log-scaled'},
        {'id': 'preserve_dynamic_range', 'label': 'Scientific Range', 'type': 'boolean', 'default': True},
    ]
)
class IFFTNode(NodeProcessor):
    def process(self, inputs, params):
        complex_data = inputs.get('complex_data')
        mag_img = inputs.get('magnitude')
        phase_img = inputs.get('phase')
        
        mode = params.get('mode', 'auto')
        preserve = params.get('preserve_dynamic_range', True)
        inv_log = params.get('inv_log', True)
        
        reconstructed_channels = []
        is_color = False

        # --- MODE 1: Complex Data (Perfect) ---
        if mode == 'complex_data' or (mode == 'auto' and complex_data is not None):
            if complex_data is None: return {'main': None}
            
            is_color = complex_data.get('is_color', False)
            for ch_complex in complex_data.get('channels', []):
                # Inverse shift
                f_ishift = np.fft.ifftshift(ch_complex)
                # Inverse FFT
                img_recon = np.abs(np.fft.ifft2(f_ishift))
                reconstructed_channels.append(img_recon)

        # --- MODE 2: Magnitude + Phase (Approximate / Manual) ---
        elif mode == 'magnitude_phase' or (mode == 'auto' and mag_img is not None):
            if mag_img is None: return {'main': None}
            
            is_color = len(mag_img.shape) == 3 and mag_img.shape[2] == 3
            mags = [mag_img[:, :, i] for i in range(3)] if is_color else [mag_img]
            
            # Phase is optional (assumes zero phase if missing)
            if phase_img is not None:
                # Denormalize phase [0, 255] -> [-pi, pi]
                phase_data = phase_img.astype(np.float64)
                phases = [phase_data[:, :, i] for i in range(3)] if is_color else [phase_data]
                phases = [(p / 255.0) * 2 * np.pi - np.pi for p in phases]
            else:
                phases = [np.zeros_like(m) for m in mags]

            for m, p in zip(mags, phases):
                mag_f = m.astype(np.float64)
                if inv_log:
                    # Reverse 20 * log(mag + 1)
                    mag_f = np.exp(mag_f / 20.0) - 1.0
                
                # Reconstruct complex: mag * exp(i * phase)
                f_shift = mag_f * np.exp(1j * p)
                
                f_ishift = np.fft.ifftshift(f_shift)
                img_recon = np.abs(np.fft.ifft2(f_ishift))
                reconstructed_channels.append(img_recon)
        
        if not reconstructed_channels:
            return {'main': None}

        # --- Final Stacking & Normalization ---
        if is_color:
            result = np.stack(reconstructed_channels, axis=2)
        else:
            result = reconstructed_channels[0]

        if not preserve:
            cv2.normalize(result, result, 0, 255, cv2.NORM_MINMAX)
        else:
            r_max = np.max(result)
            if r_max > 0:
                result = (result / r_max) * 255
                
        return {'main': result.astype(np.uint8)}
