import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_hist_compare',
    label='Histogram Compare',
    category='measure',
    icon='BarChart2',
    description=(
        "Compares histograms of two images using classical similarity metrics (ch3 §3.4–3.5).\n\n"
        "χ² (Chi-squared): sensitive to bin differences, good for textures.\n"
        "Bhattacharyya: geometric mean — 0=identical, 1=no overlap.\n"
        "Wasserstein 1D: Earth Mover's Distance along the chosen channel.\n"
        "Correlation: Pearson correlation between histograms (1=identical, -1=opposite).\n\n"
        "Channel: Luma (perceptual Y), R, G, B, or Hue (H from HSV).\n"
        "Optional masks restrict the region analysed.\n"
        "Output: scalar distance + side-by-side histogram overlay."
    ),
    inputs=[
        {'id': 'image_a', 'label': 'Image A', 'color': 'image'},
        {'id': 'image_b', 'label': 'Image B', 'color': 'image'},
        {'id': 'mask_a',  'label': 'Mask A',  'color': 'mask'},
        {'id': 'mask_b',  'label': 'Mask B',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',     'label': 'Histogram Plot', 'color': 'image'},
        {'id': 'distance', 'label': 'Distance',       'color': 'scalar'},
    ],
    params=[
        {'id': 'metric',  'label': 'Metric',  'type': 'enum',
         'options': ['Bhattacharyya', 'Chi-squared', 'Wasserstein', 'Correlation'],
         'default': 'Bhattacharyya'},
        {'id': 'channel', 'label': 'Channel', 'type': 'enum',
         'options': ['Luma', 'R', 'G', 'B', 'Hue'], 'default': 'Luma'},
        {'id': 'bins',    'label': 'Bins',    'type': 'int',
         'default': 64, 'min': 8, 'max': 256},
    ]
)
class HistCompareNode(NodeProcessor):

    # Enum options — must match the `params` order above. The UI stores an enum
    # value as either its string label (default) or its integer index (once the
    # dropdown is touched), so _resolve() accepts both.
    _METRICS  = ['Bhattacharyya', 'Chi-squared', 'Wasserstein', 'Correlation']
    _CHANNELS = ['Luma', 'R', 'G', 'B', 'Hue']

    @staticmethod
    def _resolve(val, options, default):
        if isinstance(val, bool):
            return default
        if isinstance(val, (int, float)):
            i = int(val)
            return options[i] if 0 <= i < len(options) else default
        if isinstance(val, str) and val in options:
            return val
        return default

    @staticmethod
    def _extract_channel(image: np.ndarray, channel: str) -> np.ndarray:
        if image.ndim == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image

        if channel == 'Luma':
            yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
            return yuv[..., 0]
        elif channel == 'R':
            return bgr[..., 2]
        elif channel == 'G':
            return bgr[..., 1]
        elif channel == 'B':
            return bgr[..., 0]
        else:  # Hue
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            return hsv[..., 0]

    @staticmethod
    def _prepare_mask(mask, shape):
        if mask is None:
            return None
        m = mask
        if m.ndim == 3:
            m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
        if m.shape[:2] != shape[:2]:
            m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
        return (m > 127).astype(np.uint8) * 255

    @staticmethod
    def _compute_hist(channel_img: np.ndarray, mask, bins: int,
                      is_hue: bool) -> np.ndarray:
        rang = [0, 180] if is_hue else [0, 256]
        h = cv2.calcHist([channel_img], [0], mask, [bins], rang)
        h = h.flatten().astype(np.float32)
        total = h.sum()
        return h / (total + 1e-8)

    def _draw_plot(self, h_a: np.ndarray, h_b: np.ndarray, distance: float,
                   metric: str, channel: str) -> np.ndarray:
        W, H = 512, 256
        canvas = np.zeros((H + 50, W, 3), dtype=np.uint8)
        bins = len(h_a)
        bar_w = max(1, W // bins)

        max_val = max(h_a.max(), h_b.max(), 1e-8)
        for i in range(bins):
            x = i * bar_w
            # A: cyan
            h_val_a = int(h_a[i] / max_val * H)
            cv2.rectangle(canvas, (x, H - h_val_a), (x + bar_w - 1, H),
                          (200, 180, 0), -1)
            # B: orange (blended)
            h_val_b = int(h_b[i] / max_val * H)
            cv2.rectangle(canvas, (x, H - h_val_b), (x + bar_w - 1, H),
                          (0, 140, 255), 1)

        label = f'{metric} [{channel}]: {distance:.4f}'
        cv2.putText(canvas, label, (8, H + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(canvas, 'A', (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 180, 0), 1, cv2.LINE_AA)
        cv2.putText(canvas, 'B', (30, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 140, 255), 1, cv2.LINE_AA)
        return canvas

    def process(self, inputs, params):
        img_a = inputs.get('image_a')
        img_b = inputs.get('image_b')
        if img_a is None or img_b is None:
            return {'main': None, 'distance': 0.0}

        metric  = self._resolve(params.get('metric'),  self._METRICS,  'Bhattacharyya')
        channel = self._resolve(params.get('channel'), self._CHANNELS, 'Luma')
        bins    = int(params.get('bins', 64))

        is_hue = (channel == 'Hue')

        ch_a = self._extract_channel(img_a, channel)
        ch_b = self._extract_channel(img_b, channel)

        mask_a = self._prepare_mask(inputs.get('mask_a'), img_a.shape)
        mask_b = self._prepare_mask(inputs.get('mask_b'), img_b.shape)

        h_a = self._compute_hist(ch_a, mask_a, bins, is_hue)
        h_b = self._compute_hist(ch_b, mask_b, bins, is_hue)

        if metric == 'Chi-squared':
            denom = h_a + h_b + 1e-8
            dist = float(np.sum((h_a - h_b) ** 2 / denom))

        elif metric == 'Bhattacharyya':
            bc = float(np.sum(np.sqrt(h_a * h_b + 1e-8)))
            dist = float(-np.log(bc + 1e-8))
            dist = min(dist, 5.0)  # cap for display

        elif metric == 'Wasserstein':
            cdf_a = np.cumsum(h_a)
            cdf_b = np.cumsum(h_b)
            dist = float(np.sum(np.abs(cdf_a - cdf_b))) / bins

        else:  # Correlation — convert to distance (0=identical)
            corr = cv2.compareHist(h_a.reshape(-1, 1), h_b.reshape(-1, 1),
                                   cv2.HISTCMP_CORREL)
            dist = float((1.0 - corr) / 2.0)

        plot = self._draw_plot(h_a, h_b, dist, metric, channel)

        return {
            'main':     plot,
            'distance': round(dist, 4),
        }
