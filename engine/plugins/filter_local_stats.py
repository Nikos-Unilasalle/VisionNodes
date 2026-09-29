import cv2
import numpy as np
from registry import vision_node, NodeProcessor

STATISTICS = ['Mean', 'Std Dev', 'Variance']


def _to_gray_float(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return gray.astype(np.float32)


def _normalize_u8(arr):
    return cv2.normalize(arr, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


@vision_node(
    type_id='filter_local_stats',
    label='Local Statistics',
    category='image',
    icon='Grid3x3',
    description=(
        "Per-pixel statistic over a square window: local mean, standard deviation or "
        "variance. Std Dev is a texture map — flat backgrounds go dark, textured "
        "regions (tissue, grains, foliage, text) go bright. 'main' is min-max "
        "normalized to 0–255; 'raw' keeps float values."
    ),
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'raw', 'color': 'any', 'label': 'Raw (float)'},
    ],
    params=[
        {'id': 'statistic', 'label': 'Statistic', 'type': 'enum', 'options': STATISTICS, 'default': 1},
        {'id': 'window', 'label': 'Window (px)', 'type': 'int', 'default': 15, 'min': 3, 'max': 201},
    ],
)
class LocalStatsNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'raw': None}

        gray = _to_gray_float(img)
        win = max(3, int(params.get('window', 15)))
        stat = int(params.get('statistic', 1))

        mean = cv2.blur(gray, (win, win))
        if stat == 0:
            raw = mean
        else:
            variance = np.maximum(cv2.blur(gray * gray, (win, win)) - mean * mean, 0)
            raw = variance if stat == 2 else np.sqrt(variance)

        return {'main': _normalize_u8(raw), 'raw': raw}
