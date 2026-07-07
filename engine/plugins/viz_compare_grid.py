"""
viz_compare_grid.py — generic multi-input visual comparison.

Tiles N connected images into one labelled montage on a uniform grid, so several
pipeline outputs (e.g. two K-Means runs and a Mean-Shift result) can be compared
side by side. Inputs are DYNAMIC: drag any number of image links onto the node.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_RESERVED = {'raw_frame', 'image', 'data', 'in', 'value', 'main'}


def _port_index(key: str) -> int:
    """Dynamic port keys look like '0_x7k2' → 0. Non-indexed keys sort last."""
    try:
        return int(key.split('_')[0])
    except (ValueError, IndexError):
        return 9999


@vision_node(
    type_id='viz_compare_grid',
    label='Compare Grid',
    category='visualize',
    icon='LayoutGrid',
    description=(
        "Tiles N connected images into one labelled montage for side-by-side "
        "comparison. Inputs are dynamic — drag several image links onto the node "
        "(e.g. two segmentations with different seeds vs a third method). Each "
        "panel is resized to a common cell and labelled A, B, C…"
    ),
    dynamic_inputs=True,
    inputs=[],
    outputs=[
        {'id': 'main', 'label': 'Grid', 'color': 'image'},
        {'id': 'n_panels', 'label': 'Panels', 'color': 'scalar'},
    ],
    params=[
        {'id': 'cols',      'label': 'Columns (0=auto)', 'type': 'int',  'default': 0, 'min': 0, 'max': 8},
        {'id': 'panel_px',  'label': 'Panel Size (px)',  'type': 'int',  'default': 320, 'min': 96, 'max': 768},
        {'id': 'show_labels','label': 'Show Labels',     'type': 'bool', 'default': True},
    ]
)
class CompareGridNode(NodeProcessor):

    @staticmethod
    def _to_bgr(img: np.ndarray) -> np.ndarray:
        if img.ndim == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.ndim == 3 and img.shape[2] == 4:
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    def _panel(self, img: np.ndarray, label: str, panel_px: int, show_labels: bool) -> np.ndarray:
        bgr = self._to_bgr(img)
        if bgr.dtype != np.uint8:
            bgr = np.clip(bgr, 0, 255).astype(np.uint8)
        h, w = bgr.shape[:2]
        scale = panel_px / max(h, w)
        pw, ph = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        small = cv2.resize(bgr, (pw, ph), interpolation=cv2.INTER_AREA)
        cv2.rectangle(small, (0, 0), (pw - 1, ph - 1), (70, 70, 70), 1)
        if show_labels:
            cv2.putText(small, label, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(small, label, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
        return small

    def process(self, inputs, params):
        panel_px    = int(params.get('panel_px', 320))
        cols_param  = int(params.get('cols', 0))
        show_labels = bool(params.get('show_labels', True))

        # Collect connected images in port order
        keys = sorted((k for k in inputs
                       if k not in _RESERVED and isinstance(inputs[k], np.ndarray)),
                      key=_port_index)
        imgs = [inputs[k] for k in keys]

        if not imgs:
            return {'main': None, 'n_panels': 0}

        panels = [self._panel(im, chr(ord('A') + i), panel_px, show_labels)
                  for i, im in enumerate(imgs)]

        n = len(panels)
        cols = cols_param if cols_param > 0 else int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        cell_h = max(p.shape[0] for p in panels)
        cell_w = max(p.shape[1] for p in panels)
        gap = 6
        canvas = np.full((rows * cell_h + (rows + 1) * gap,
                          cols * cell_w + (cols + 1) * gap, 3), 18, dtype=np.uint8)
        for idx, p in enumerate(panels):
            rr, cc = divmod(idx, cols)
            y = gap + rr * (cell_h + gap)
            x = gap + cc * (cell_w + gap)
            canvas[y:y + p.shape[0], x:x + p.shape[1]] = p

        return {'main': canvas, 'n_panels': n}
