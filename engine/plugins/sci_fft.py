from registry import vision_node, NodeProcessor
import cv2
import numpy as np

_FILTER_TYPES = ['None', 'Low-pass', 'High-pass', 'Band-pass', 'Band-stop']

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
        {'id': 'complex_data', 'color': 'data'},
        {'id': 'magnitude_raw', 'color': 'data', 'label': 'Magnitude (raw)'},
    ],
    params=[
        {'id': 'log_scale',              'label': 'Log Intensity',   'type': 'bool',  'default': True},
        {'id': 'preserve_dynamic_range', 'label': 'Scientific Range','type': 'bool',  'default': False,
         'description': 'Keeps relative intensities instead of normalizing 0-255'},
        {'id': 'filter_type', 'label': 'Filter Type', 'type': 'enum', 'default': 0,
         'options': ['None', 'Low-pass', 'High-pass', 'Band-pass', 'Band-stop']},
        {'id': 'low_cutoff',  'label': 'Min Freq %', 'type': 'int', 'min': 0, 'max': 100, 'step': 1, 'default': 0},
        {'id': 'high_cutoff', 'label': 'Max Freq %', 'type': 'int', 'min': 0, 'max': 100, 'step': 1, 'default': 10},
    ]
)
class FFTNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'magnitude': None, 'phase': None, 'complex_data': None, 'magnitude_raw': None}

        img_f = img.astype(np.float64)
        is_color = len(img_f.shape) == 3 and img_f.shape[2] == 3
        channels = [img_f[:, :, i] for i in range(3)] if is_color else [img_f]

        rows, cols = img_f.shape[:2]
        crow, ccol = rows // 2, cols // 2
        diag = np.sqrt(rows**2 + cols**2) / 2.0

        f_type = _FILTER_TYPES[int(params.get('filter_type', 0))]
        low_norm  = int(params.get('low_cutoff', 0))  / 100.0
        high_norm = int(params.get('high_cutoff', 10)) / 100.0
        log_scale = params.get('log_scale', True)
        preserve  = params.get('preserve_dynamic_range', False)

        mask = np.ones((rows, cols), np.float64)
        if f_type != 'None':
            mask = np.zeros((rows, cols), np.float64)
            r_inner = int(low_norm  * diag)
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

        magnitudes     = []
        magnitudes_raw = []
        phases         = []
        filtered_imgs  = []
        complex_results = []

        for ch in channels:
            f_transform = np.fft.fft2(ch)
            f_shift     = np.fft.fftshift(f_transform)

            phase     = np.angle(f_shift)
            magnitude = np.abs(f_shift)
            magnitudes_raw.append(magnitude)

            f_shift_filtered = f_shift * mask

            f_ishift = np.fft.ifftshift(f_shift_filtered)
            img_back = np.abs(np.fft.ifft2(f_ishift))

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
            phases.append(((phase + np.pi) / (2 * np.pi) * 255).astype(np.uint8))
            filtered_imgs.append(img_back.astype(np.uint8))
            complex_results.append(f_shift_filtered)

        def stack(l):
            if is_color: return np.stack(l, axis=2)
            return l[0]

        out_filtered = stack(filtered_imgs)
        out_phase    = stack(phases)

        mag_stacked = stack(magnitudes)
        if is_color:
            mag_gray = cv2.cvtColor(mag_stacked, cv2.COLOR_BGR2GRAY)
            out_mag = cv2.applyColorMap(mag_gray, cv2.COLORMAP_INFERNO)
        else:
            out_mag = cv2.applyColorMap(mag_stacked, cv2.COLORMAP_INFERNO)

        return {
            'main':      out_filtered,
            'magnitude': out_mag,
            'phase':     out_phase,
            'complex_data': {
                'channels': complex_results,
                'is_color': is_color,
                'shape':    img.shape
            },
            'magnitude_raw': {
                'channels': magnitudes_raw,
                'is_color': is_color
            }
        }
