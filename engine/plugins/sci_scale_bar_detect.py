import cv2
import numpy as np
from registry import vision_node, NodeProcessor

UNITS = ['µm', 'mm', 'nm', 'cm']
UNIT_TO_MM = [1e-3, 1.0, 1e-6, 10.0]
MIN_LEN_FRAC = 0.04     # a bar is at least 4 % of the image width
MAX_THICK_FRAC = 0.015  # and at most 1.5 % of the image height thick
MIN_FILL = 0.8          # a straight bar fills its bounding box (curved walls do not)
MIN_CONTRAST = 25       # grey levels above its immediate surroundings
MIN_ASPECT = 12
SOURCES = ['Auto (detect bar)', 'Manual (drawn line)']
MIN_MANUAL_PX_PER_MM = 1.5   # Visual Calibration outputs 1.0 when no line is drawn
MIN_LEN_PX = 30
MAX_BAR_STD = 30        # a printed bar has a uniform tone along its length


def _edge_shift(gray, d):
    """Contrast of each pixel against the pixel d rows above and d rows below (one side is enough)."""
    g = gray.astype(np.int16)
    above = np.zeros_like(g)
    below = np.zeros_like(g)
    above[d:] = g[d:] - g[:-d]
    below[:-d] = g[:-d] - g[d:]
    return np.maximum(above, below)


def _long_straight_runs(gray, min_len, shift):
    """Pixels brighter than their vertical neighbour on at least one side, kept only where they
    form a straight horizontal run of at least min_len pixels."""
    contrast = (_edge_shift(gray, shift) >= MIN_CONTRAST).astype(np.uint8)
    horiz = cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1))
    return cv2.morphologyEx(contrast, cv2.MORPH_OPEN, horiz)


def _best_bar(runs, gray, min_len, max_thick):
    n, _, stats, _ = cv2.connectedComponentsWithStats(runs, connectivity=8)
    best = None
    for i in range(1, n):
        x, y, w, h = stats[i, :4]
        if w < min_len or h > max_thick or w < MIN_ASPECT * max(h, 1):
            continue
        if stats[i, cv2.CC_STAT_AREA] < MIN_FILL * w * h:
            continue
        if float(gray[y + h // 2, x:x + w].std()) > MAX_BAR_STD:   # tone along the bar's centre line
            continue
        if best is None or w > best[2]:
            best = (int(x), int(y), int(w), int(h))
    return best


def _manual_calibration(value):
    """A usable drawn calibration, or None (not connected / no line drawn / invalid)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) and v >= MIN_MANUAL_PX_PER_MM else None


@vision_node(
    type_id='sci_scale_bar_detect',
    label='Scale Bar Detect',
    category='measure',
    icon='Ruler',
    description=(
        "Finds the scale bar burnt into a micrograph or photo (the longest thin horizontal line, "
        "bright or dark) and converts its known length into a calibration: pixels per mm / per µm. "
        "Enter the length printed next to the bar. Connect px/mm to Unit Calibration or Scale Dict "
        "Values so every measurement follows the image's real magnification. Source = Manual uses "
        "the px/mm of a line drawn with Visual Calibration (unit mm) instead; if no line is drawn "
        "it falls back to automatic detection."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'bar_length', 'color': 'scalar', 'label': 'Bar Length'},
        {'id': 'manual_px_per_mm', 'color': 'scalar', 'label': 'Manual px/mm'},
    ],
    outputs=[
        {'id': 'px_per_mm', 'color': 'scalar', 'label': 'px / mm'},
        {'id': 'px_per_um', 'color': 'scalar', 'label': 'px / µm'},
        {'id': 'length_px', 'color': 'scalar', 'label': 'Bar Length (px)'},
        {'id': 'bar_mask', 'color': 'mask'},
        {'id': 'main', 'color': 'image'},
    ],
    params=[
        {'id': 'source', 'label': 'Source', 'type': 'enum', 'options': SOURCES, 'default': 0},
        {'id': 'bar_length', 'label': 'Bar Length (printed value)', 'type': 'float', 'default': 500.0, 'min': 0},
        {'id': 'unit', 'label': 'Unit', 'type': 'enum', 'options': UNITS, 'default': 0},
        {'id': 'fallback_px_per_mm', 'label': 'Fallback px/mm (no bar found)', 'type': 'float', 'default': 0.0, 'min': 0},
    ],
)
class ScaleBarDetectNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        empty = {'px_per_mm': None, 'px_per_um': None, 'length_px': None, 'bar_mask': None, 'main': img}
        manual = _manual_calibration(inputs.get('manual_px_per_mm'))
        if int(params.get('source', 0)) == 1 and manual is not None:
            return {**empty, 'px_per_mm': manual, 'px_per_um': manual / 1000.0}
        if img is None:
            return empty

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        gray = gray if gray.dtype == np.uint8 else cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        h, w = gray.shape
        min_len = max(MIN_LEN_PX, int(w * MIN_LEN_FRAC))
        max_thick = max(3, int(h * MAX_THICK_FRAC))

        shift = max(2, max_thick // 3)
        # Bright bars first (most common); dark bars only if no bright bar is found
        candidates = []
        for g in (gray, cv2.bitwise_not(gray)):
            found = _best_bar(_long_straight_runs(g, min_len, shift), g, min_len, max_thick)
            if found is not None:
                candidates = [found]
                break
        bar_len = float(params.get('bar_length', 500.0))
        unit_mm = UNIT_TO_MM[int(params.get('unit', 0)) % len(UNITS)]

        if not candidates or bar_len <= 0:
            fb = float(params.get('fallback_px_per_mm', 0.0))
            if fb > 0:
                return {**empty, 'px_per_mm': fb, 'px_per_um': fb / 1000.0}
            return empty

        x, y, bw, bh = max(candidates, key=lambda c: c[2])
        px_per_mm = bw / (bar_len * unit_mm)
        mask = np.zeros_like(gray)
        mask[y:y + bh, x:x + bw] = 255
        vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(vis, (x, y - 4), (x + bw, y + bh + 4), (0, 0, 255), 2)
        cv2.putText(vis, f'{bw} px = {bar_len:g} {["um", "mm", "nm", "cm"][int(params.get("unit", 0)) % len(UNITS)]}',
                    (max(0, x), max(15, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return {'px_per_mm': float(px_per_mm), 'px_per_um': float(px_per_mm / 1000.0),
                'length_px': float(bw), 'bar_mask': mask, 'main': vis}
