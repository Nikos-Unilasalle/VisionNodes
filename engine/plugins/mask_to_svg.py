import cv2
import numpy as np
import os
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='mask_to_svg',
    label='Export Mask to SVG',
    category='output',
    icon='Download',
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'path', 'type': 'file_path', 'default': 'output.svg', 'label': 'File Path'},
        {'id': 'trigger', 'type': 'trigger', 'label': 'Save SVG'},
        {'id': 'stroke_color', 'type': 'color', 'default': '#000000', 'label': 'Stroke Color'},
        {'id': 'fill_color', 'type': 'color', 'default': '#ffffff', 'label': 'Fill Color'},
        {'id': 'stroke_width', 'type': 'number', 'default': 1.5, 'min': 0.5, 'max': 10, 'label': 'Stroke Width'},
    ]
)
class MaskToSvgNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')

        if mask is None:
            return {'mask': None}

        if params.get('trigger'):
            self._save_svg(mask, params)

        return {'mask': mask}

    def _save_svg(self, mask, params):
        path = params.get('path', 'output.svg')
        stroke_color = params.get('stroke_color', '#000000')
        fill_color = params.get('fill_color', 'none')
        stroke_width = float(params.get('stroke_width', 1.5))

        # Ensure mask is uint8
        if mask.dtype != np.uint8:
            m = (mask > 0).astype(np.uint8) * 255
        else:
            m = mask.copy()

        if m.ndim == 3:
            m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)

        h, w = m.shape[:2]

        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        path_elements = []
        for contour in contours:
            if len(contour) < 2:
                continue
            pts = contour.reshape(-1, 2)
            d = 'M {},{}'.format(pts[0][0], pts[0][1])
            for pt in pts[1:]:
                d += ' L {},{}'.format(pt[0], pt[1])
            d += ' Z'
            path_elements.append(
                '  <path d="{}" stroke="{}" fill="{}" stroke-width="{}"/>'.format(
                    d, stroke_color, fill_color, stroke_width
                )
            )

        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(w, h, w, h),
        ]
        svg_lines.extend(path_elements)
        svg_lines.append('</svg>')
        svg_content = '\n'.join(svg_lines)

        out_path = os.path.expanduser(path)
        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
