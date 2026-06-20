import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='sci_first_order_stats',
    label='First Order Statistics',
    category='measure',
    icon='BarChart2',
    description=(
        "First-order texture statistics from the pixel histogram (ch13 §13.1).\n\n"
        "Outputs mean, variance, entropy and uniformity — purely statistical,\n"
        "blind to spatial arrangement. Demonstrates the angle mort of order-1 descriptors."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',       'label': 'Stats Overlay', 'color': 'image'},
        {'id': 'mean',       'label': 'Mean',          'color': 'scalar'},
        {'id': 'variance',   'label': 'Variance',      'color': 'scalar'},
        {'id': 'entropy',    'label': 'Entropy',       'color': 'scalar'},
        {'id': 'uniformity', 'label': 'Uniformity',    'color': 'scalar'},
    ],
    params=[
        {'id': 'region_size', 'label': 'Region Size (0=full)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 512},
    ]
)
class FirstOrderStatsNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'mean': 0.0, 'variance': 0.0,
                    'entropy': 0.0, 'uniformity': 0.0}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()

        region = int(params.get('region_size', 0))
        if region > 0:
            h, w = gray.shape
            cy, cx = h // 2, w // 2
            r = region // 2
            roi = gray[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
        else:
            roi = gray

        hist = cv2.calcHist([roi], [0], None, [256], [0, 256]).flatten()
        hist_norm = hist / hist.sum()

        levels = np.arange(256)
        mean_val   = float(np.sum(levels * hist_norm))
        var_val    = float(np.sum((levels - mean_val) ** 2 * hist_norm))
        unif_val   = float(np.sum(hist_norm ** 2))
        nz         = hist_norm[hist_norm > 0]
        entr_val   = float(-np.sum(nz * np.log2(nz)))

        vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        if region > 0:
            cy, cx = gray.shape[0] // 2, gray.shape[1] // 2
            r = region // 2
            cv2.rectangle(vis, (cx - r, cy - r), (cx + r, cy + r), (0, 200, 255), 1)

        lines = [
            f'mean={mean_val:.1f}',
            f'var={var_val:.1f}',
            f'H={entr_val:.2f}',
            f'U={unif_val:.3f}',
        ]
        for i, txt in enumerate(lines):
            cv2.putText(vis, txt, (6, 16 + i * 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

        return {
            'main':       vis,
            'mean':       round(mean_val, 2),
            'variance':   round(var_val, 2),
            'entropy':    round(entr_val, 4),
            'uniformity': round(unif_val, 6),
        }
