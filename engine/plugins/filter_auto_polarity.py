import cv2
import numpy as np
from registry import vision_node, NodeProcessor

TARGETS = ['Bright Background', 'Dark Background']
METHODS = ['Image Border', 'Histogram Peak']
PEAK_SMOOTH_SIGMA = 4


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _background_foreground(gray, mask, border_pct):
    """Boolean background / foreground selectors: from the mask when given, else border vs centre."""
    if mask is not None:
        m = _gray(mask)
        if m.shape != gray.shape:
            m = cv2.resize(m, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST)
        fg = m > 0
        return ~fg, fg
    h, w = gray.shape
    b = max(1, int(round(min(h, w) * border_pct / 100.0)))
    bg = np.zeros((h, w), bool)
    bg[:b, :] = bg[-b:, :] = True
    bg[:, :b] = bg[:, -b:] = True
    return bg, ~bg


def _background_is_bright_by_peak(gray):
    """The dominant (most frequent) tone of a smoothed image is taken as the background."""
    smooth = cv2.GaussianBlur(gray, (0, 0), PEAK_SMOOTH_SIGMA)
    hist = np.bincount(smooth.astype(np.uint8).ravel(), minlength=256)
    peak = int(np.argmax(hist))
    return peak >= float(smooth.mean())


@vision_node(
    type_id='filter_auto_polarity',
    label='Auto Polarity',
    category='image',
    icon='Contrast',
    description=(
        "Inverts the image only when needed so the background ends up bright (or dark). "
        "Background = pixels outside the optional foreground mask; otherwise the image border "
        "or the dominant histogram peak (robust when the object touches the frame). "
        "Lets one pipeline accept both bright-field (dark objects on white) and "
        "fluorescence / dark-field (bright objects on black) images."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask', 'color': 'mask', 'label': 'Foreground (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'inverted', 'color': 'boolean'},
    ],
    params=[
        {'id': 'target', 'label': 'Make Background', 'type': 'enum', 'options': TARGETS, 'default': 0},
        {'id': 'method', 'label': 'Detect Background By', 'type': 'enum', 'options': METHODS, 'default': 0},
        {'id': 'border_pct', 'label': 'Border Width (%)', 'type': 'float', 'default': 5.0, 'min': 0.5, 'max': 25},
    ],
)
class AutoPolarityNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'inverted': False}

        gray = _gray(img)
        mask = inputs.get('mask')
        if mask is None and int(params.get('method', 0)) == 1:
            bg_is_bright = _background_is_bright_by_peak(gray)
        else:
            bg, fg = _background_foreground(gray, mask, float(params.get('border_pct', 5.0)))
            if not bg.any() or not fg.any():
                return {'main': img, 'inverted': False}
            bg_is_bright = float(gray[bg].mean()) >= float(gray[fg].mean())

        want_bright = int(params.get('target', 0)) == 0
        invert = bg_is_bright != want_bright

        main = cv2.bitwise_not(img) if invert else img
        return {'main': main, 'inverted': bool(invert)}
