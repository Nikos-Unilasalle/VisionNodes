from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_fft',
    label='FFT Analysis',
    category=['analysis', 'scientific'],
    icon='Activity',
    description="Advanced 2D FFT Analysis with full color support. Treats BGR channels independently to preserve spectral information. Outputs magnitude, phase, and filtered reconstruction.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Filtered'},
        {'id': 'magnitude', 'color': 'image', 'label': 'Magnitude'},
        {'id': 'phase', 'color': 'image', 'label': 'Phase'},
        {'id': 'complex_data', 'color': 'data'}
    ],
    params=[
        {'id': 'log_scale',   'label': 'Log Intensity', 'type': 'boolean', 'default': True},
        {'id': 'preserve_dynamic_range', 'label': 'Scientific Range', 'type': 'boolean', 'default': False,
         'description': 'If enabled, keeps relative intensities instead of normalizing 0-255'},
        {'id': 'filter_type', 'label': 'Filter Type',  'type': 'string', 'default': 'None', 
         'options': ['None', 'Low-pass', 'High-pass', 'Band-pass', 'Band-stop']},
        {'id': 'low_cutoff',  'label': 'Min Freq',     'type': 'scalar', 'min': 0, 'max': 1, 'default': 0},
        {'id': 'high_cutoff', 'label': 'Max Freq',     'type': 'scalar', 'min': 0, 'max': 1, 'default': 0.1},
    ]
)
class FFTNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'magnitude': None, 'phase': None, 'complex_data': None}
            
        # 1. Prepare data
        img_f = img.astype(np.float64)
        is_color = len(img_f.shape) == 3 and img_f.shape[2] == 3
        channels = [img_f[:, :, i] for i in range(3)] if is_color else [img_f]
        
        rows, cols = img_f.shape[:2]
        crow, ccol = rows // 2, cols // 2
        diag = np.sqrt(rows**2 + cols**2) / 2.0 # Max radius
        
        f_type = params.get('filter_type', 'None')
        low_norm = float(params.get('low_cutoff', 0))
        high_norm = float(params.get('high_cutoff', 0.1))
        log_scale = params.get('log_scale', True)
        preserve = params.get('preserve_dynamic_range', False)
        
        # 2. Build Filter Mask using cv2 for precision
        mask = np.ones((rows, cols), np.float64)
        if f_type != 'None':
            mask = np.zeros((rows, cols), np.float64)
            r_inner = int(low_norm * diag)
            r_outer = int(high_norm * diag)
            
            if f_type == 'Low-pass':
                cv2.circle(mask, (ccol, crow), r_outer, 1, -1)
            elif f_type == 'High-pass':
                mask[:] = 1.0
                cv2.circle(mask, (ccol, crow), r_inner, 0, -1)
            elif f_type == 'Band-pass':
                cv2.circle(mask, (ccol, crow), r_outer, 1, -1)
                cv2.circle(mask, (ccol, crow), r_inner, 0, -1)
            elif f_type == 'Band-stop':
                mask[:] = 1.0
                cv2.circle(mask, (ccol, crow), r_outer, 0, -1)
                cv2.circle(mask, (ccol, crow), r_inner, 1, -1)

        magnitudes = []
        phases = []
        filtered_imgs = []
        complex_results = []

        # 3. Process each channel
        for ch in channels:
            # FFT
            f_transform = np.fft.fft2(ch)
            f_shift = np.fft.fftshift(f_transform)
            
            # Save original phase and magnitude
            phase = np.angle(f_shift)
            magnitude = np.abs(f_shift)
            
            # Apply frequency filtering
            f_shift_filtered = f_shift * mask
            
            # Inverse FFT for the 'main' output
            f_ishift = np.fft.ifftshift(f_shift_filtered)
            img_back = np.abs(np.fft.ifft2(f_ishift))
            
            # Visualization
            mag_vis = np.log(magnitude + 1) if log_scale else magnitude.copy()
            
            if not preserve:
                cv2.normalize(mag_vis, mag_vis, 0, 255, cv2.NORM_MINMAX)
                cv2.normalize(img_back, img_back, 0, 255, cv2.NORM_MINMAX)
            else:
                m_max = np.max(mag_vis)
                if m_max > 0: mag_vis = (mag_vis / m_max) * 255
                b_max = np.max(img_back)
                if b_max > 0: img_back = (img_back / b_max) * 255

            magnitudes.append(mag_vis.astype(np.uint8))
            # Phase [-pi, pi] -> [0, 255]
            phases.append(((phase + np.pi) / (2 * np.pi) * 255).astype(np.uint8))
            filtered_imgs.append(img_back.astype(np.uint8))
            
            # Keep raw complex data for IFFT node
            complex_results.append(f_shift_filtered)

        # 4. Final Stacking
        def stack(l):
            if is_color: return np.stack(l, axis=2)
            return l[0]

        out_filtered = stack(filtered_imgs)
        out_phase = stack(phases)
        
        # Magnitude visualization with colormap
        mag_stacked = stack(magnitudes)
        if is_color:
            # Convert to gray for consistent colormapping
            mag_gray = cv2.cvtColor(mag_stacked, cv2.COLOR_BGR2GRAY)
            out_mag = cv2.applyColorMap(mag_gray, cv2.COLORMAP_INFERNO)
        else:
            out_mag = cv2.applyColorMap(mag_stacked, cv2.COLORMAP_INFERNO)

        return {
            'main': out_filtered,
            'magnitude': out_mag,
            'phase': out_phase,
            'complex_data': {
                'channels': complex_results,
                'is_color': is_color,
                'shape': img.shape
            }
        }
