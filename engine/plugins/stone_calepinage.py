"""
Stone Calepinage — Wall layout diagram colored by stone type.

Crosses SAM contours (one per stone, index = stone ID) with a classification
dict {type_name: [ids]} (e.g. from an LLM that classified Grounding DINO boxes).
Each stone is filled with its type color. Produces two outputs:
- overlay : drawn on the source photo
- diagram : clean technical plan on a flat background, with legend.
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import json
import re


def _coerce_to_dict(classes):
    """Accept a dict, or a JSON string (possibly wrapped in markdown fences /
    surrounded by prose) and return a dict. Returns {} on failure."""
    if isinstance(classes, dict):
        return classes
    if not isinstance(classes, str):
        return {}
    s = classes.strip()
    # Strip ```json … ``` fences
    if s.startswith('```'):
        s = s.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    # Direct parse
    try:
        return json.loads(s)
    except Exception:
        pass
    # Last resort: grab the first {...} block in the text
    m = re.search(r'\{.*\}', s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}

# Distinct, print-friendly palette (BGR) cycled per stone type
_PALETTE = [
    (80, 127, 255),   # orange
    (80, 220, 100),   # green
    (255, 160, 60),   # blue
    (60, 80, 220),    # red
    (200, 120, 220),  # purple
    (80, 200, 230),   # yellow
    (200, 200, 90),   # teal
    (120, 120, 245),  # salmon
    (180, 140, 70),   # steel
    (90, 180, 180),   # olive
]
_UNKNOWN_COLOR = (150, 150, 150)  # grey for unclassified stones

# Number of user-assignable (class name → color) slots in the inspector
_NUM_COLOR_SLOTS = 12


def _hex_to_bgr(hex_str: str) -> tuple | None:
    """'#RRGGBB' → (B, G, R). Returns None on bad input."""
    if not isinstance(hex_str, str):
        return None
    s = hex_str.strip().lstrip('#')
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (b, g, r)
    except ValueError:
        return None


def _color_slot_params() -> list[dict]:
    """Build (class name, color) param pairs so the user can assign a color
    per class. Grouped under a collapsible 'Class Colors' section. Empty name =
    pair ignored (palette fallback applies)."""
    params = [{'id': 'class_colors_section', 'type': 'section', 'label': 'Class Colors'}]
    for i in range(_NUM_COLOR_SLOTS):
        default_hex = '#%02x%02x%02x' % (
            _PALETTE[i % len(_PALETTE)][2],
            _PALETTE[i % len(_PALETTE)][1],
            _PALETTE[i % len(_PALETTE)][0],
        )
        params.append({'id': f'cls_name_{i}', 'type': 'string', 'default': '',
                       'label': f'Class {i + 1} name'})
        params.append({'id': f'cls_color_{i}', 'type': 'color', 'default': default_hex,
                       'label': f'Class {i + 1} color'})
    return params


# Cache a unicode-capable TrueType font (Hershey/cv2 cannot render accents)
_FONT_PATHS = [
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
    '/Library/Fonts/Arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]
_FONT_CACHE: dict = {}


def _get_font(size: int):
    """Return a PIL ImageFont for the given pixel size, cached. None if PIL missing."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font = None
    for p in _FONT_PATHS:
        try:
            font = ImageFont.truetype(p, size)
            break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
    _FONT_CACHE[size] = font
    return font


def _put_unicode_text(img: np.ndarray, text: str, org: tuple,
                      color_bgr: tuple, px: int) -> np.ndarray:
    """Draw accented/unicode text onto a BGR image via PIL. org = baseline-left
    (matches cv2.putText convention roughly). Returns the image (modified)."""
    try:
        from PIL import Image as PILImage, ImageDraw
    except ImportError:
        # Fallback: cv2 (will mangle accents, but never crash)
        cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, px / 28.0,
                    color_bgr, 1, cv2.LINE_AA)
        return img
    font = _get_font(px)
    if font is None:
        cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, px / 28.0,
                    color_bgr, 1, cv2.LINE_AA)
        return img
    pil = PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    # PIL org = top-left; shift up by font size to approximate cv2 baseline
    x, y = org
    draw.text((x, y - px), text, font=font,
              fill=(color_bgr[2], color_bgr[1], color_bgr[0]))
    img[:] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img


@vision_node(
    type_id='stone_calepinage',
    label='Stone Calepinage',
    category='visualize',
    icon='LayoutGrid',
    description=(
        "Wall layout (calepinage) colored by stone type. "
        "Takes SAM contours (one per stone, ordered by ID) and a classification "
        "dict {type: [ids]} from an LLM. Each stone is filled with its type color. "
        "Outputs an overlay on the photo and a clean technical diagram with legend."
    ),
    inputs=[
        {'id': 'image',    'color': 'image', 'label': 'Source Image'},
        {'id': 'contours', 'color': 'list',  'label': 'Contours'},
        {'id': 'classes',  'color': 'any',   'label': 'Classes {type:[ids]} (dict or JSON string)'},
    ],
    outputs=[
        {'id': 'overlay',  'color': 'image', 'label': 'Overlay'},
        {'id': 'diagram',  'color': 'image', 'label': 'Diagram'},
        {'id': 'legend',   'color': 'dict',  'label': 'Legend (type→count)'},
    ],
    params=[
        {'id': 'opacity',        'label': 'Overlay Opacity (%)', 'type': 'number',
         'default': 55, 'min': 0, 'max': 100, 'step': 5},
        {'id': 'outline',        'label': 'Outline Thickness', 'type': 'int',
         'default': 2, 'min': 0, 'max': 8},
        {'id': 'show_ids',       'label': 'Show Stone IDs', 'type': 'bool', 'default': True},
        {'id': 'show_legend',    'label': 'Show Legend', 'type': 'bool', 'default': True},
        {'id': 'font_scale',     'label': 'Font Scale', 'type': 'float',
         'default': 0.45, 'min': 0.2, 'max': 2.0, 'step': 0.05},
        {'id': 'bg_gray',        'label': 'Diagram BG (gray 0-255)', 'type': 'int',
         'default': 245, 'min': 0, 'max': 255},
        {'id': 'class_filter',   'label': 'Show Only Class (empty = all)', 'type': 'string',
         'default': ''},
        {'id': 'others_mode',    'label': 'Other Classes', 'type': 'enum',
         'options': ['Hide', 'Grey'], 'default': 1},
    ] + _color_slot_params(),
    colorable=True,
    resizable=True,
)
class StoneCalepinageNode(NodeProcessor):

    def _build_id_to_type(self, classes: dict) -> tuple:
        """Return (id_to_type dict, ordered list of type names)."""
        id_to_type: dict = {}
        type_names: list = []
        if not isinstance(classes, dict):
            return id_to_type, type_names
        for type_name, ids in classes.items():
            # Skip non-list values (e.g. 'dominant', 'notes' summary keys)
            if not isinstance(ids, (list, tuple)):
                continue
            if type_name not in type_names:
                type_names.append(type_name)
            for sid in ids:
                try:
                    id_to_type[int(sid)] = type_name
                except (ValueError, TypeError):
                    continue
        return id_to_type, type_names

    def _contour_to_np(self, contour) -> np.ndarray | None:
        """Convert a list of [x,y] points to an int32 (N,1,2) array for cv2."""
        if not isinstance(contour, (list, tuple)) or len(contour) < 3:
            return None
        try:
            arr = np.array(contour, dtype=np.int32).reshape(-1, 1, 2)
            return arr
        except Exception:
            return None

    def _draw_legend(self, canvas: np.ndarray, type_colors: dict,
                     counts: dict, font_scale: float) -> None:
        """Draw a legend box (top-left) with color swatch + type name + count."""
        if not type_colors:
            return
        pad = 10
        row_h = max(20, int(28 * font_scale / 0.45))
        sw = row_h - 8  # swatch size
        # Box dimensions
        n = len(type_colors)
        box_w = 240
        box_h = pad * 2 + n * row_h
        x0, y0 = pad, pad
        # Semi-opaque white panel
        panel = canvas[y0:y0 + box_h, x0:x0 + box_w].copy()
        white = np.full_like(panel, 255)
        canvas[y0:y0 + box_h, x0:x0 + box_w] = cv2.addWeighted(panel, 0.25, white, 0.75, 0)
        cv2.rectangle(canvas, (x0, y0), (x0 + box_w, y0 + box_h), (40, 40, 40), 1)

        y = y0 + pad
        for type_name, color in type_colors.items():
            cnt = counts.get(type_name, 0)
            cv2.rectangle(canvas, (x0 + pad, y), (x0 + pad + sw, y + sw), color, -1)
            cv2.rectangle(canvas, (x0 + pad, y), (x0 + pad + sw, y + sw), (40, 40, 40), 1)
            label = f'{type_name} ({cnt})'
            _put_unicode_text(canvas, label, (x0 + pad + sw + 8, y + sw - 2),
                              (20, 20, 20), max(11, int(28 * font_scale / 0.45 * 0.6)))
            y += row_h

    def process(self, inputs: dict, params: dict) -> dict:
        image    = inputs.get('image')
        contours = inputs.get('contours')
        classes  = _coerce_to_dict(inputs.get('classes'))

        if image is None:
            return {'overlay': None, 'diagram': None, 'legend': None}

        h, w = image.shape[:2]

        if not isinstance(contours, list) or len(contours) == 0:
            msg = image.copy()
            cv2.putText(msg, 'No contours — connect SAM contours port',
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 255), 2)
            return {'overlay': msg, 'diagram': msg.copy(), 'legend': None}

        opacity     = float(params.get('opacity', 55)) / 100.0
        outline     = int(params.get('outline', 2))
        show_ids    = bool(params.get('show_ids', True))
        show_legend = bool(params.get('show_legend', True))
        font_scale  = float(params.get('font_scale', 0.45))
        bg_gray     = int(params.get('bg_gray', 245))
        class_filter = str(params.get('class_filter', '') or '').strip()
        others_grey  = int(params.get('others_mode', 1)) == 1

        id_to_type, type_names = self._build_id_to_type(classes)

        # User-assigned colors: {class name → BGR} from the inspector slots
        user_colors: dict = {}
        for i in range(_NUM_COLOR_SLOTS):
            name = str(params.get(f'cls_name_{i}', '') or '').strip()
            if not name:
                continue
            bgr = _hex_to_bgr(params.get(f'cls_color_{i}', ''))
            if bgr is not None:
                user_colors[name] = bgr

        # Assign a color per type name: user choice first, else cycle palette
        type_colors: dict = {}
        for idx, name in enumerate(type_names):
            type_colors[name] = user_colors.get(name, _PALETTE[idx % len(_PALETTE)])

        # Build the two color layers
        fill_overlay = np.zeros((h, w, 3), dtype=np.uint8)
        diagram      = np.full((h, w, 3), bg_gray, dtype=np.uint8)
        region_mask  = np.zeros((h, w), dtype=bool)
        counts: dict = {}
        centroids: dict = {}

        for sid, contour in enumerate(contours):
            cnt = self._contour_to_np(contour)
            if cnt is None:
                continue
            type_name = id_to_type.get(sid)
            matched = (not class_filter) or (type_name == class_filter)

            # Class filter: hide non-matching stones entirely…
            if not matched and not others_grey:
                continue
            # …or render them in grey for context.
            color = type_colors.get(type_name, _UNKNOWN_COLOR) if matched else _UNKNOWN_COLOR

            if matched and type_name is not None:
                counts[type_name] = counts.get(type_name, 0) + 1

            # Fill both layers
            cv2.fillPoly(fill_overlay, [cnt], color)
            cv2.fillPoly(diagram, [cnt], color)
            tmp = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(tmp, [cnt], 255)
            region_mask |= tmp.astype(bool)

            # Outline on diagram
            if outline > 0:
                cv2.polylines(diagram, [cnt], True, (40, 40, 40), outline)

            # Centroid for ID label
            M = cv2.moments(cnt)
            if M['m00'] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                centroids[sid] = (cx, cy)

        # ── Overlay: alpha blend only in stone regions ──
        overlay = image.copy()
        blended = cv2.addWeighted(image, 1.0 - opacity, fill_overlay, opacity, 0)
        overlay[region_mask] = blended[region_mask]
        if outline > 0:
            for sid, contour in enumerate(contours):
                if sid not in centroids:   # skip stones hidden by class filter
                    continue
                cnt = self._contour_to_np(contour)
                if cnt is not None:
                    cv2.polylines(overlay, [cnt], True, (255, 255, 255), 1)

        # ── ID labels on both ──
        if show_ids:
            for sid, (cx, cy) in centroids.items():
                txt = f'{sid}'
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
                for canvas, fg in ((overlay, (255, 255, 255)), (diagram, (20, 20, 20))):
                    cv2.putText(canvas, txt, (cx - tw // 2, cy + th // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, fg, 1, cv2.LINE_AA)

        # ── Legend on diagram ──
        if show_legend:
            legend_colors = type_colors
            if class_filter:
                legend_colors = {class_filter: type_colors.get(class_filter, _UNKNOWN_COLOR)}
            self._draw_legend(diagram, legend_colors, counts, font_scale)

        return {'overlay': overlay, 'diagram': diagram, 'legend': counts}
