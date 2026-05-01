from registry import vision_node, NodeProcessor
import cv2
import numpy as np

_MODES = ['auto', 'complex_data', 'magnitude_phase']

@vision_node(
    type_id='sci_ifft',
    label='Inverse FFT',
    category=['analysis', 'scientific'],
    icon='RotateCcw',
    description="Reconstructs an image from spectral data. Perfect reconstruction from Complex Data or Magnitude Raw + Phase. Magnitude image input is approximate (visualization data).",
    inputs=[
        {'id': 'complex_data',  'color': 'data',  'optional': True},
        {'id': 'magnitude_raw', 'color': 'data',  'optional': True},
        {'id': 'magnitude',     'color': 'image', 'optional': True},
        {'id': 'phase',         'color': 'image', 'optional': True}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'mode', 'label': 'Input Mode', 'type': 'enum', 'default': 0,
         'options': ['auto', 'complex_data', 'magnitude_phase']},
        {'id': 'inv_log', 'label': 'Inverse Log', 'type': 'bool', 'default': False,
         'description': 'Undo log(x+1) on magnitude image input. Not needed for magnitude_raw.'},
        {'id': 'preserve_dynamic_range', 'label': 'Scientific Range', 'type': 'bool', 'default': True},
    ]
)
class IFFTNode(NodeProcessor):
    def process(self, inputs, params):
        complex_data = inputs.get('complex_data')
        mag_raw      = inputs.get('magnitude_raw')
        mag_img      = inputs.get('magnitude')
        phase_img    = inputs.get('phase')

        mode     = _MODES[int(params.get('mode', 0))]
        preserve = params.get('preserve_dynamic_range', True)
        inv_log  = params.get('inv_log', False)

        reconstructed_channels = []
        is_color = False

        # --- MODE 1: Complex Data (perfect reconstruction of filtered signal) ---
        if mode == 'complex_data' or (mode == 'auto' and complex_data is not None):
            if complex_data is None: return {'main': None}

            is_color = complex_data.get('is_color', False)
            for ch_complex in complex_data.get('channels', []):
                f_ishift   = np.fft.ifftshift(ch_complex)
                img_recon  = np.abs(np.fft.ifft2(f_ishift))
                reconstructed_channels.append(img_recon)

        # --- MODE 2: Magnitude + Phase ---
        elif mode == 'magnitude_phase' or (mode == 'auto' and (mag_raw is not None or mag_img is not None)):

            # magnitude_raw (lossless float) takes priority over colormap-mapped image
            if mag_raw is not None:
                is_color = mag_raw.get('is_color', False)
                mags     = mag_raw.get('channels', [])
                use_raw  = True
            elif mag_img is not None:
                is_color = len(mag_img.shape) == 3 and mag_img.shape[2] == 3
                mags     = [mag_img[:, :, i].astype(np.float64) for i in range(3)] if is_color \
                           else [mag_img.astype(np.float64)]
                use_raw  = False
            else:
                return {'main': None}

            if phase_img is not None:
                phase_data = phase_img.astype(np.float64)
                phases = [phase_data[:, :, i] for i in range(3)] if is_color else [phase_data]
                # Denormalize [0, 255] → [-π, π]
                phases = [(p / 255.0) * 2 * np.pi - np.pi for p in phases]
            else:
                phases = [np.zeros(m.shape, dtype=np.float64) for m in mags]

            for m, p in zip(mags, phases):
                mag_f = m.astype(np.float64)
                if not use_raw and inv_log:
                    # Inverse of np.log(x + 1) applied before normalization
                    mag_f = np.exp(mag_f) - 1.0

                f_shift   = mag_f * np.exp(1j * p)
                f_ishift  = np.fft.ifftshift(f_shift)
                img_recon = np.abs(np.fft.ifft2(f_ishift))
                reconstructed_channels.append(img_recon)

        if not reconstructed_channels:
            return {'main': None}

        result = np.stack(reconstructed_channels, axis=2) if is_color else reconstructed_channels[0]

        if not preserve:
            cv2.normalize(result, result, 0, 255, cv2.NORM_MINMAX)
        else:
            r_max = np.max(result)
            if r_max > 0:
                result = (result / r_max) * 255

        return {'main': result.astype(np.uint8)}
