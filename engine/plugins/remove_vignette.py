import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _fit_fov_circle(gray: np.ndarray, dark_thresh: int, margin: int):
    _, bright = cv2.threshold(gray, dark_thresh, 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, k)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    if not contours:
        return w // 2, h // 2, min(h, w) // 2 - margin
    largest = max(contours, key=cv2.contourArea)
    (cx, cy), r = cv2.minEnclosingCircle(largest)
    r = max(10, int(r) - margin)
    return int(cx), int(cy), r


def _hex_to_bgr(h: str) -> tuple:
    try:
        s = h.lstrip('#')
        if len(s) != 6:
            return (255, 255, 255)
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return (b, g, r)
    except Exception:
        return (255, 255, 255)


@vision_node(
    type_id='remove_vignette',
    label='Remove Vignette',
    category='utility',
    icon='Circle',
    description=(
        'Removes circular vignette (dark border) from images with a round field of view.\n\n'
        'Works for microscopy, telescope, fisheye, or any circular FOV. '
        'Auto-detects the bright circle or use Manual mode for precise control. '
        'Feather blends the edge softly. Outputs cleaned image + FOV mask.'
    ),
    resizable=True,
    min_width=240,
    min_height=180,
    colorable=True,
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',    'label': 'Cleaned',  'color': 'image'},
        {'id': 'mask',    'label': 'FOV Mask', 'color': 'mask'},
        {'id': 'cropped', 'label': 'Cropped',  'color': 'image'},
    ],
    params=[
        {'id': 'mode',        'label': 'Mode',           'type': 'enum',  'options': ['Auto-detect', 'Manual'], 'default': 0},
        {'id': 'fill',        'label': 'Fill Outside',   'type': 'enum',  'options': ['Color', 'Blur', 'Black'], 'default': 0},
        {'id': 'fill_color',  'label': 'Fill Color',     'type': 'color', 'default': '#ffffff'},
        {'id': 'feather_px',  'label': 'Feather (px)',   'type': 'int',   'default': 0,   'min': 0,   'max': 120},
        {'id': 'dark_thresh', 'label': 'Dark Threshold', 'type': 'int',   'default': 30,  'min': 5,   'max': 120},
        {'id': 'margin_px',   'label': 'Shrink (px)',    'type': 'int',   'default': 8,   'min': 0,   'max': 100},
        {'id': 'center_x',    'label': 'Center X (%)',   'type': 'float', 'default': 50.0,'min': 5.0, 'max': 95.0, 'step': 0.5},
        {'id': 'center_y',    'label': 'Center Y (%)',   'type': 'float', 'default': 50.0,'min': 5.0, 'max': 95.0, 'step': 0.5},
        {'id': 'radius_pct',  'label': 'Radius (%)',     'type': 'float', 'default': 46.0,'min': 5.0, 'max': 70.0, 'step': 0.5},
    ],
)
class RemoveVignetteNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'mask': None, 'cropped': None}

        src = img if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w = src.shape[:2]
        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

        mode        = int(params.get('mode', 0))   # 0=Auto-detect 1=Manual
        fill_mode   = int(params.get('fill', 0))   # 0=Color 1=Blur 2=Black
        feather     = int(params.get('feather_px', 0))
        dark_thresh = int(params.get('dark_thresh', 30))
        margin      = int(params.get('margin_px', 8))

        if mode == 1:  # Manual
            cx = int(float(params.get('center_x', 50.0)) / 100.0 * w)
            cy = int(float(params.get('center_y', 50.0)) / 100.0 * h)
            r  = max(1, int(float(params.get('radius_pct', 46.0)) / 100.0 * min(h, w)))
        else:  # Auto-detect
            cx, cy, r = _fit_fov_circle(gray, dark_thresh, margin)

        # Build fill layer
        if fill_mode == 1:   # Blur
            k = max(51, (min(h, w) // 20) | 1)
            fill_layer = cv2.GaussianBlur(src, (k, k), 0)
        elif fill_mode == 2:  # Black
            fill_layer = np.zeros((h, w, 3), dtype=np.uint8)
        else:                 # Color (0) — fill_color picker, white by default
            bgr = _hex_to_bgr(str(params.get('fill_color', '#ffffff')))
            fill_layer = np.empty((h, w, 3), dtype=np.uint8)
            fill_layer[:] = bgr

        # Distance map from center → alpha mask (float32, 0..1)
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X.astype(np.float32) - cx) ** 2 +
                       (Y.astype(np.float32) - cy) ** 2)

        if feather > 0:
            # Smooth fade from 1 (inside r-feather) to 0 (outside r)
            alpha = np.clip((float(r) - dist) / float(feather), 0.0, 1.0)
        else:
            alpha = (dist <= r).astype(np.float32)

        alpha3 = alpha[:, :, np.newaxis]
        result = (src.astype(np.float32) * alpha3 +
                  fill_layer.astype(np.float32) * (1.0 - alpha3)).astype(np.uint8)

        fov_mask = (alpha * 255).astype(np.uint8)

        # Tight crop — clamp to image bounds
        x1 = max(0, cx - r)
        y1 = max(0, cy - r)
        x2 = min(w, cx + r)
        y2 = min(h, cy + r)
        cropped = result[y1:y2, x1:x2] if y2 > y1 and x2 > x1 else result

        return {
            'main':    result,
            'mask':    fov_mask,
            'cropped': cropped,
        }
