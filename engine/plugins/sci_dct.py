from registry import vision_node, NodeProcessor
import cv2
import numpy as np


@vision_node(
    type_id='sci_dct',
    label='DCT Analysis',
    category='signal',
    icon='Waves',
    description="2D Discrete Cosine Transform (the transform behind JPEG). "
                "View the log DCT spectrum as a colormap, or reconstruct the image "
                "keeping only the top-left NxN block of low-frequency coefficients "
                "to visualize lossy compression. Reports the fraction of spectral "
                "energy retained by the kept coefficients.",
    inputs=[{'id': 'image', 'label': 'Image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'label': 'Result', 'color': 'image'},
        {'id': 'data', 'label': 'Info', 'color': 'dict'},
    ],
    params=[
        {'id': 'output', 'label': 'Output', 'type': 'enum',
         'options': ['Log Spectrum', 'Reconstruction'], 'default': 'Log Spectrum'},
        {'id': 'keep_coeffs', 'label': 'Keep NxN', 'type': 'int',
         'min': 1, 'max': 256, 'default': 32},
        {'id': 'normalize', 'label': 'Normalize', 'type': 'bool', 'default': True},
    ]
)
class DCTNode(NodeProcessor):

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None:
            return {'main': None, 'data': None}

        output_mode = params.get('output', 'Log Spectrum')
        keep = int(params.get('keep_coeffs', 32))
        do_normalize = bool(params.get('normalize', True))

        # Grayscale float32
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        gray = gray.astype(np.float32)

        # cv2.dct requires even dimensions; pad if needed
        h, w = gray.shape[:2]
        ph = h + (h % 2)
        pw = w + (w % 2)
        if ph != h or pw != w:
            gray = cv2.copyMakeBorder(gray, 0, ph - h, 0, pw - w, cv2.BORDER_REPLICATE)

        dct = cv2.dct(gray)
        total_energy = float(np.sum(dct.astype(np.float64) ** 2))

        kh = min(keep, dct.shape[0])
        kw = min(keep, dct.shape[1])
        kept_energy = float(np.sum(dct[:kh, :kw].astype(np.float64) ** 2))
        energy_kept_ratio = (kept_energy / total_energy) if total_energy > 0 else 0.0

        if output_mode == 'Log Spectrum':
            viz = np.log1p(np.abs(dct))
            if do_normalize:
                cv2.normalize(viz, viz, 0, 255, cv2.NORM_MINMAX)
            else:
                vmax = float(np.max(viz))
                if vmax > 0:
                    viz = viz / vmax * 255.0
            viz = viz.astype(np.uint8)
            result = cv2.applyColorMap(viz, cv2.COLORMAP_VIRIDIS)
        else:  # Reconstruction
            kept = np.zeros_like(dct)
            kept[:kh, :kw] = dct[:kh, :kw]
            recon = cv2.idct(kept)
            if do_normalize:
                cv2.normalize(recon, recon, 0, 255, cv2.NORM_MINMAX)
            recon = np.clip(recon, 0, 255).astype(np.uint8)
            result = cv2.cvtColor(recon, cv2.COLOR_GRAY2BGR)

        # Crop back to original size
        result = result[:h, :w]

        return {
            'main': result,
            'data': {
                'energy_kept_ratio': energy_kept_ratio,
                'dims': [int(h), int(w)],
            }
        }
