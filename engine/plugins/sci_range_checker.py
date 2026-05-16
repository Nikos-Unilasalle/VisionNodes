import cv2
import numpy as np
import datetime
from registry import vision_node, NodeProcessor

# Panel dimensions
IW, IH = 700, 500

BG       = (22,  28,  38)
BG_PANEL = (30,  38,  52)
BG_TH    = (26,  34,  46)
BG_ROW1  = (34,  44,  58)
BG_ROW2  = (40,  52,  68)
LINE     = (52,  66,  88)
C_WHITE  = (225, 228, 232)
C_DIM    = (130, 140, 155)
C_LBLUE  = (195, 208, 218)
C_OK     = (80,  200, 100)
C_HIGH   = (60,  80,  220)
C_LOW    = (200, 160, 50)
C_CRIT   = (50,  50,  230)


def _hex_to_bgr(h: str) -> tuple:
    try:
        s = h.lstrip('#')
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return (b, g, r)
    except Exception:
        return (100, 200, 100)


def _txt(img, text, x, y, color=C_WHITE, scale=0.40, bold=False):
    cv2.putText(img, str(text), (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2 if bold else 1, cv2.LINE_AA)


def _status(val: float, lo: float, hi: float, warn_lo: float, warn_hi: float):
    if val < lo or val > hi:
        return 'CRITICAL', C_CRIT
    if val < warn_lo or val > warn_hi:
        label = 'LOW' if val < warn_lo else 'HIGH'
        color = C_LOW if val < warn_lo else C_HIGH
        return label, color
    return 'OK', C_OK


@vision_node(
    type_id='sci_range_checker',
    label='Value Gate',
    category='measure',
    icon='Gauge',
    description=(
        'Compares values in a dict against configurable reference ranges.\n\n'
        'For each key in the input dict, define a normal range (warn_lo–warn_hi) '
        'and a critical range (crit_lo–crit_hi) in the JSON ranges param. '
        'Outputs a status dict (OK / HIGH / LOW / CRITICAL per key) '
        'and a visual dashboard image.\n\n'
        'Range JSON format:\n'
        '{"key": [crit_lo, warn_lo, warn_hi, crit_hi], ...}'
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'values', 'label': 'Values (dict)', 'color': 'dict'},
    ],
    outputs=[
        {'id': 'status', 'label': 'Status (dict)', 'color': 'dict'},
        {'id': 'flags',  'label': 'Flags (list)',  'color': 'list'},
        {'id': 'main',   'label': 'Dashboard',     'color': 'image'},
    ],
    params=[
        {'id': 'ranges',       'label': 'Ranges (JSON)',  'type': 'code',
         'default': '{\n  "RBC": [0, 70, 95, 100],\n  "WBC": [0, 1, 12, 20],\n  "PLT": [0, 3, 10, 15]\n}'},
        {'id': 'title',        'label': 'Title',          'type': 'string', 'default': 'Reference Range Check'},
        {'id': 'unit_label',   'label': 'Unit Label',     'type': 'string', 'default': ''},
        {'id': 'accent_color', 'label': 'Accent Color',   'type': 'color',  'default': '#4ade80'},
    ],
)
class RangeCheckerNode(NodeProcessor):
    def process(self, inputs, params):
        values = inputs.get('values') or {}
        accent = _hex_to_bgr(str(params.get('accent_color', '#4ade80')))
        title  = str(params.get('title', 'Reference Range Check'))
        unit   = str(params.get('unit_label', ''))

        # Parse ranges JSON safely
        ranges: dict = {}
        try:
            import json
            raw = str(params.get('ranges', '{}'))
            ranges = json.loads(raw)
        except Exception:
            pass

        status_out: dict[str, str] = {}
        flags: list[dict]          = []

        for key, val in values.items():
            if key == 'total':
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            rng = ranges.get(str(key))
            if rng and len(rng) == 4:
                crit_lo, warn_lo, warn_hi, crit_hi = (float(x) for x in rng)
                lbl, _ = _status(fval, crit_lo, crit_hi, warn_lo, warn_hi)
            else:
                lbl = '—'
            status_out[key] = lbl
            if lbl not in ('OK', '—'):
                flags.append({'key': key, 'value': fval, 'status': lbl})

        # Dashboard image
        img = np.full((IH, IW, 3), BG, dtype=np.uint8)

        # Title bar
        cv2.rectangle(img, (0, 0), (IW, 48), (14, 18, 26), -1)
        cv2.line(img, (0, 47), (IW, 47), accent, 2)
        _txt(img, title, 10, 30, accent, scale=0.55, bold=True)
        _txt(img, datetime.date.today().strftime('%Y-%m-%d'), IW - 110, 30, C_DIM, scale=0.38)

        # Table
        row_h = 44
        ry    = 56
        keys  = [k for k in values if k != 'total']

        for i, key in enumerate(keys):
            try:
                fval = float(values[key])
            except (TypeError, ValueError):
                continue
            bg = BG_ROW1 if i % 2 == 0 else BG_ROW2
            cv2.rectangle(img, (4, ry), (IW - 4, ry + row_h), bg, -1)
            cv2.line(img, (4, ry + row_h), (IW - 4, ry + row_h), LINE, 1)

            rng = ranges.get(str(key))
            if rng and len(rng) == 4:
                crit_lo, warn_lo, warn_hi, crit_hi = (float(x) for x in rng)
                lbl, col = _status(fval, crit_lo, crit_hi, warn_lo, warn_hi)
                range_str = f'[{warn_lo} – {warn_hi}]{" " + unit if unit else ""}'
            else:
                lbl, col  = '—', C_DIM
                range_str = 'no range defined'

            val_str = f'{fval:.2f}' if isinstance(fval, float) and fval != int(fval) else str(int(fval))

            _txt(img, key,        12,       ry + 26, accent,  scale=0.50, bold=True)
            _txt(img, val_str,    200,      ry + 26, C_WHITE, scale=0.52, bold=True)
            _txt(img, range_str,  320,      ry + 26, C_DIM,   scale=0.38)
            _txt(img, lbl,        IW - 110, ry + 26, col,     scale=0.48, bold=True)

            # Bar: fill fraction within warn range
            if rng and len(rng) == 4 and crit_hi > crit_lo:
                frac = min(max((fval - crit_lo) / (crit_hi - crit_lo), 0.0), 1.0)
                bar_w = int((IW - 8) * frac)
                cv2.rectangle(img, (4, ry + row_h - 3), (4 + bar_w, ry + row_h - 1),
                              tuple(max(0, int(c * 0.6)) for c in col), -1)

            ry += row_h
            if ry + row_h > IH - 10:
                break

        # Summary badge
        n_flags = len(flags)
        badge_col = C_OK if n_flags == 0 else (C_HIGH if n_flags > 2 else C_LOW)
        badge_txt = 'ALL OK' if n_flags == 0 else f'{n_flags} FLAG{"S" if n_flags > 1 else ""}'
        cv2.rectangle(img, (IW - 145, IH - 38), (IW - 5, IH - 5), badge_col, -1)
        _txt(img, badge_txt, IW - 135, IH - 14, (10, 20, 10), scale=0.50, bold=True)

        cv2.rectangle(img, (0, 0), (IW - 1, IH - 1), accent, 2)

        return {'status': status_out, 'flags': flags, 'main': img}
