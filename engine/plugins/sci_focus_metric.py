import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_METHODS = ['Laplacian Variance', 'Tenengrad', 'Normalized Variance']

@vision_node(
    type_id='sci_focus_metric',
    label='Focus Metric',
    category=['analysis', 'scientific'],
    icon='Eye',
    description="Measure image sharpness / focus quality. Higher score = sharper. Use for autofocus, Z-stack selection, QC.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main',  'color': 'image',  'label': 'Pass-through'},
        {'id': 'score', 'color': 'scalar', 'label': 'Focus Score'},
    ],
    params=[
        {'id': 'method',     'label': 'Method',          'type': 'enum',  'options': _METHODS, 'default': 0},
        {'id': 'roi_margin', 'label': 'ROI Margin (%)',  'type': 'float', 'default': 0.0, 'min': 0.0, 'max': 40.0},
        {'id': 'show_score', 'label': 'Show Score',      'type': 'bool',  'default': True},
    ]
)
class FocusMetricNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'score': 0.0}

        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)

        h, w   = img.shape[:2]
        margin = float(params.get('roi_margin', 0.0)) / 100.0
        mx, my = int(w * margin), int(h * margin)
        roi    = img[my:h - my, mx:w - mx] if margin > 0 and my < h // 2 and mx < w // 2 else img

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        method = int(params.get('method', 0))

        if method == 0:  # Laplacian Variance
            score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        elif method == 1:  # Tenengrad (Sobel energy)
            g  = gray.astype(np.float64)
            gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
            score = float(np.mean(gx**2 + gy**2))
        else:  # Normalized Variance
            g     = gray.astype(np.float64)
            mean  = g.mean()
            score = float(g.var() / (mean + 1e-8))

        out = img.copy()
        if bool(params.get('show_score', True)):
            if len(out.shape) == 2:
                out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
            label = f"Focus: {score:.2f}"
            cv2.putText(out, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 160), 1, cv2.LINE_AA)

        return {'main': out, 'score': score}
