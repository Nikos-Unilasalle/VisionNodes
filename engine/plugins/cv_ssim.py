"""
SSIM / PSNR node — image quality comparison against a reference.
Chapter 14 (image quality).
"""

import cv2
import numpy as np
from skimage.metrics import structural_similarity, peak_signal_noise_ratio
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_ssim',
    label='SSIM / PSNR',
    category='measure',
    icon='GitCompare',
    description="Compare a test image against a reference: computes SSIM (structural "
                "similarity) and PSNR (peak signal-to-noise ratio). Outputs an SSIM map, "
                "difference image, or the test image with metrics overlaid.",
    inputs=[
        {'id': 'image', 'label': 'Test Image', 'color': 'image'},
        {'id': 'reference', 'label': 'Reference', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Result', 'color': 'image'},
        {'id': 'ssim', 'label': 'SSIM', 'color': 'scalar'},
        {'id': 'psnr', 'label': 'PSNR (dB)', 'color': 'scalar'},
        {'id': 'data', 'label': 'Metrics', 'color': 'dict'},
    ],
    params=[
        {'id': 'output', 'label': 'Output', 'type': 'enum',
         'options': ['SSIM Map', 'Difference', 'Test Image'], 'default': 'SSIM Map'},
        {'id': 'grayscale', 'label': 'Grayscale (luminance)', 'type': 'bool', 'default': True},
    ]
)
class SsimNode(NodeProcessor):
    """Computes SSIM and PSNR between a test image and a reference."""

    @staticmethod
    def _overlay_metrics(img, ssim_score, psnr_val):
        out = img.copy()
        lines = [f"SSIM: {ssim_score:.4f}", f"PSNR: {psnr_val:.2f} dB"]
        y = 28
        for line in lines:
            cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 1, cv2.LINE_AA)
            y += 30
        return out

    def process(self, inputs, params):
        img = inputs.get('image')
        ref = inputs.get('reference')
        if img is None or ref is None:
            return {'main': None}

        output_mode = params.get('output', 'SSIM Map')
        use_gray = bool(params.get('grayscale', True))

        # Ensure 3-channel BGR uint8
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if ref.ndim == 2:
            ref = cv2.cvtColor(ref, cv2.COLOR_GRAY2BGR)
        img = img.astype(np.uint8)
        ref = ref.astype(np.uint8)

        # Resize reference to match the test image if shapes differ
        if ref.shape[:2] != img.shape[:2]:
            ref = cv2.resize(ref, (img.shape[1], img.shape[0]),
                             interpolation=cv2.INTER_LINEAR)

        # Compute SSIM (+ full map) and PSNR
        if use_gray:
            a = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            b = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
            ssim_score, ssim_map = structural_similarity(
                a, b, full=True, data_range=255)
        else:
            ssim_score, ssim_map = structural_similarity(
                img, ref, full=True, data_range=255, channel_axis=2)
            # Collapse per-channel map to a single-channel map for visualization
            ssim_map = ssim_map.mean(axis=2)

        psnr_val = float(peak_signal_noise_ratio(ref, img, data_range=255))
        mse = float(np.mean((img.astype(np.float64) - ref.astype(np.float64)) ** 2))
        ssim_score = float(ssim_score)

        # Guard against non-finite PSNR (identical images -> inf)
        if not np.isfinite(psnr_val):
            psnr_val = 100.0

        # Build the requested output image
        if output_mode == 'SSIM Map':
            norm = np.clip((ssim_map + 1.0) * 0.5, 0.0, 1.0)  # [-1,1] -> [0,1]
            norm_u8 = (norm * 255).astype(np.uint8)
            result = cv2.applyColorMap(norm_u8, cv2.COLORMAP_VIRIDIS)
        elif output_mode == 'Difference':
            diff = cv2.absdiff(img, ref)
            result = diff.astype(np.uint8)
        else:  # 'Test Image'
            result = img.copy()

        result = self._overlay_metrics(result, ssim_score, psnr_val)

        return {
            'main': result,
            'ssim': ssim_score,
            'psnr': psnr_val,
            'data': {'ssim': ssim_score, 'psnr': psnr_val, 'mse': mse},
        }
