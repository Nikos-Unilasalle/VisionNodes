from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import sys
import subprocess

# ── Dependency bootstrap ───────────────────────────────────────────────────────
try:
    import skimage  # noqa: F401
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    send_notification('scikit-image missing — installing…', progress=0.05, notif_id='skimage_install')
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', 'scikit-image>=0.21.0'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import skimage  # noqa: F401, F811
        SKIMAGE_AVAILABLE = True
        send_notification('scikit-image installed', progress=1.0, notif_id='skimage_install')
    except Exception as e:
        send_notification(f'scikit-image install failed: {e}', level='error', notif_id='skimage_install')

_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'jet':     cv2.COLORMAP_JET,
    'hot':     cv2.COLORMAP_HOT,
}


@vision_node(
    type_id='sliding_window',
    label='Sliding Window',
    category='cv',
    icon='ScanLine',
    description='Apply a sliding window operation (local Otsu, mean, std, entropy, normalize, custom).',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'output', 'color': 'image', 'label': 'Output'},
        {'id': 'map',    'color': 'image', 'label': 'Map'},
    ],
    params=[
        {'id': 'operation',  'type': 'enum',   'options': ['otsu', 'mean', 'std', 'normalize', 'entropy', 'custom'], 'default': 'otsu',       'label': 'Operation'},
        {'id': 'radius',     'type': 'int',    'default': 15,   'min': 1,   'max': 200, 'label': 'Radius (px)'},
        {'id': 'threshold',  'type': 'float',  'default': 0.0,  'min': -1.0, 'max': 1.0, 'label': 'Threshold Bias'},
        {'id': 'invert',     'type': 'toggle', 'default': False,                          'label': 'Invert'},
        {'id': 'colormap',   'type': 'enum',   'options': list(_CV2_COLORMAPS.keys()), 'default': 'viridis', 'label': 'Colormap'},
        {'id': 'expression', 'type': 'string', 'default': 'np.mean(w)',                  'label': 'Expression  (w = window)'},
    ]
)
class SlidingWindowNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'output': None, 'map': None}

        radius    = max(1, int(params.get('radius', 15)))
        operation = params.get('operation', 'otsu')
        bias      = float(params.get('threshold', 0.0))
        invert    = bool(params.get('invert', False))
        cmap_key  = params.get('colormap', 'viridis')
        expression = params.get('expression', 'np.mean(w)')

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
        gray_f = gray.astype(np.float32) / 255.0

        result_map = None
        output_gray = None

        if operation == 'otsu':
            if not SKIMAGE_AVAILABLE:
                return {'output': None, 'map': None}
            from skimage.filters.rank import otsu as rank_otsu
            from skimage.morphology import disk
            local_thresh_u8 = rank_otsu(gray, disk(radius))
            local_thresh_f  = local_thresh_u8.astype(np.float32) / 255.0
            result_map  = local_thresh_f
            binary_mask = gray_f >= (local_thresh_f + bias)
            output_gray = (binary_mask.astype(np.float32) * 255).astype(np.uint8)

        elif operation == 'mean':
            from scipy.ndimage import uniform_filter
            local_mean = uniform_filter(gray_f, size=2 * radius + 1)
            result_map  = local_mean
            binary_mask = gray_f >= (local_mean + bias)
            output_gray = (binary_mask.astype(np.float32) * 255).astype(np.uint8)

        elif operation == 'std':
            from scipy.ndimage import uniform_filter
            size = 2 * radius + 1
            mean_f  = uniform_filter(gray_f, size=size)
            mean_sq = uniform_filter(gray_f ** 2, size=size)
            local_std  = np.sqrt(np.maximum(mean_sq - mean_f ** 2, 0.0))
            result_map  = local_std
            norm        = _normalize01(local_std)
            binary_mask = norm >= (0.5 + bias)
            output_gray = (binary_mask.astype(np.float32) * 255).astype(np.uint8)

        elif operation == 'normalize':
            from scipy.ndimage import uniform_filter
            size = 2 * radius + 1
            mean_f  = uniform_filter(gray_f, size=size)
            mean_sq = uniform_filter(gray_f ** 2, size=size)
            local_std  = np.sqrt(np.maximum(mean_sq - mean_f ** 2, 0.0)) + 1e-8
            normalized  = (gray_f - mean_f) / local_std
            result_map  = normalized
            clipped     = np.clip(normalized, -3.0 + bias * 3.0, 3.0 + bias * 3.0)
            output_gray = ((clipped + 3.0) / 6.0 * 255).astype(np.uint8)

        elif operation == 'entropy':
            if not SKIMAGE_AVAILABLE:
                return {'output': None, 'map': None}
            from skimage.filters.rank import entropy as rank_entropy
            from skimage.morphology import disk
            ent        = rank_entropy(gray, disk(radius)).astype(np.float32)
            result_map  = ent
            norm        = _normalize01(ent)
            binary_mask = norm >= (0.5 + bias)
            output_gray = (binary_mask.astype(np.float32) * 255).astype(np.uint8)

        elif operation == 'custom':
            from scipy.ndimage import generic_filter
            try:
                fn = eval(f'lambda w: {expression}', {'np': np})
                result_map = generic_filter(gray_f, fn, size=2 * radius + 1).astype(np.float32)
            except Exception:
                result_map = np.zeros_like(gray_f)
            norm        = _normalize01(result_map)
            binary_mask = norm >= (0.5 + bias)
            output_gray = (binary_mask.astype(np.float32) * 255).astype(np.uint8)

        else:
            output_gray = gray
            result_map  = gray_f

        if invert:
            output_gray = 255 - output_gray

        output_bgr = cv2.cvtColor(output_gray, cv2.COLOR_GRAY2BGR)

        map_u8     = (_normalize01(result_map) * 255).astype(np.uint8)
        cmap       = _CV2_COLORMAPS.get(cmap_key, cv2.COLORMAP_VIRIDIS)
        map_colored = cv2.applyColorMap(map_u8, cmap)

        return {'output': output_bgr, 'map': map_colored}


def _normalize01(arr):
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-10:
        return np.zeros_like(arr, dtype=np.float32)
    return ((arr - mn) / (mx - mn)).astype(np.float32)
