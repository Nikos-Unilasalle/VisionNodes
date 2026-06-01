"""
image_legend.py — Overlay a colour-coded legend on any image.

Each entry: one line → "Label:#RRGGBB"  or  "Label:R,G,B"
Blank lines and lines without ':' are skipped.
"""
from __future__ import annotations
import re
import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'image_legend'

_HEX_RE = re.compile(r'^#?([0-9A-Fa-f]{6})$')
_RGB_RE = re.compile(r'^(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})$')


def _parse_color(s: str) -> tuple[int, int, int] | None:
    """Parse '#RRGGBB' or 'R,G,B' → (B, G, R) for OpenCV."""
    s = s.strip()
    m = _HEX_RE.match(s)
    if m:
        h = m.group(1)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (b, g, r)
    m = _RGB_RE.match(s)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (b, g, r)
    return None


def _parse_entries(text: str) -> list[tuple[str, tuple[int, int, int]]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        idx = line.index(':')
        label = line[:idx].strip()
        color = _parse_color(line[idx + 1:].strip())
        if label and color is not None:
            out.append((label, color))
    return out


_DEFAULT_ENTRIES = (
    "Forêt stable:#226422\n"
    "Repousse / site abandonné:#64C864\n"
    "Déboisement:#8C501E\n"
    "Eau claire:#0000FF\n"
    "Eau turbide:#FF1400\n"
    "Dégradé avant T₀:#500014"
)


@vision_node(
    type_id='image_legend',
    label='Image Legend',
    category='cv',
    icon='BookOpen',
    description=(
        'Overlay a colour-coded legend on any image. '
        'Entries: one per line, format "Label:#RRGGBB" or "Label:R,G,B". '
        'Semi-transparent background, configurable corner.'
    ),
    inputs=[
        {'id': 'image', 'color': 'image', 'label': 'Image'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Image + legend'},
    ],
    params=[
        {'id': 'entries',     'type': 'string',  'default': _DEFAULT_ENTRIES,
         'label': 'Entries  Label:#RRGGBB  (one per line)'},
        {'id': 'position',    'type': 'enum',    'default': 'bottom-left',
         'options': ['top-left', 'top-right', 'bottom-left', 'bottom-right'],
         'label': 'Position'},
        {'id': 'font_scale',  'type': 'float',   'default': 0.5,  'min': 0.2, 'max': 2.0,
         'label': 'Font scale'},
        {'id': 'swatch_size', 'type': 'int',     'default': 16,   'min': 6,   'max': 48,
         'label': 'Swatch size (px)'},
        {'id': 'bg_alpha',    'type': 'float',   'default': 0.55, 'min': 0.0, 'max': 1.0,
         'label': 'Background opacity'},
        {'id': 'padding',     'type': 'int',     'default': 8,    'min': 0,   'max': 40,
         'label': 'Padding (px)'},
        {'id': 'node_note',   'type': 'string',  'default': '',   'label': 'Note'},
    ],
    resizable=True, min_width=280, min_height=160,
)
class ImageLegendNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        img = inputs.get('image')
        if img is None:
            send_notification('ImageLegend: connect an image', notif_id=_NOTIF)
            return {}

        if isinstance(img, np.ndarray):
            canvas = img.copy()
        else:
            send_notification('ImageLegend: expected numpy image', notif_id=_NOTIF)
            return {}

        if canvas.ndim == 2:
            canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
        elif canvas.shape[2] == 4:
            canvas = canvas[:, :, :3].copy()

        entries = _parse_entries(str(params.get('entries', _DEFAULT_ENTRIES)))
        if not entries:
            return {'main': canvas}

        font       = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = float(params.get('font_scale', 0.5))
        swatch     = int(params.get('swatch_size', 16))
        bg_alpha   = float(params.get('bg_alpha', 0.55))
        pad        = int(params.get('padding', 8))
        position   = str(params.get('position', 'bottom-left'))

        thickness  = 1
        line_gap   = 4

        # Measure text widths
        text_sizes = [
            cv2.getTextSize(lbl, font, font_scale, thickness)[0]
            for lbl, _ in entries
        ]
        max_tw = max(s[0] for s in text_sizes) if text_sizes else 0
        row_h  = max(swatch, max(s[1] for s in text_sizes) if text_sizes else swatch)

        box_w = pad + swatch + pad + max_tw + pad
        box_h = pad + len(entries) * (row_h + line_gap) - line_gap + pad

        H, W = canvas.shape[:2]
        if 'right' in position:
            x0 = W - box_w - 4
        else:
            x0 = 4
        if 'bottom' in position:
            y0 = H - box_h - 4
        else:
            y0 = 4

        x0, y0 = max(0, x0), max(0, y0)
        x1 = min(W, x0 + box_w)
        y1 = min(H, y0 + box_h)

        # Semi-transparent background
        overlay = canvas.copy()
        cv2.rectangle(overlay, (x0, y0), (x1, y1), (20, 20, 20), cv2.FILLED)
        cv2.addWeighted(overlay, bg_alpha, canvas, 1 - bg_alpha, 0, canvas)

        # Draw entries
        for i, (label, bgr) in enumerate(entries):
            row_y = y0 + pad + i * (row_h + line_gap)
            sx = x0 + pad
            sy = row_y
            cv2.rectangle(canvas, (sx, sy), (sx + swatch, sy + swatch), bgr, cv2.FILLED)
            cv2.rectangle(canvas, (sx, sy), (sx + swatch, sy + swatch), (180, 180, 180), 1)
            tx = sx + swatch + pad
            ty = sy + swatch - (swatch - text_sizes[i][1]) // 2
            cv2.putText(canvas, label, (tx, ty), font, font_scale,
                        (230, 230, 230), thickness, cv2.LINE_AA)

        return {'main': canvas}
