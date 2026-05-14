import cv2
import numpy as np
import datetime
from registry import vision_node, NodeProcessor

# ── Layout constants ──────────────────────────────────────────────────────────
IW, IH = 1400, 720

# Panels (x1, y1, x2, y2)
P_TITLE  = (0,    0,   IW,   58)
P_PPL    = (8,    66,  296,  310)
P_XPL    = (304,  66,  592,  310)
P_MODAL  = (600,  66,  IW,   310)
P_HISTO  = (8,    318, 560,  712)
P_MORPH  = (568,  318, 984,  712)
P_NEIGH  = (992,  318, IW,   712)

# ── Neutral palette — never accent-tinted ─────────────────────────────────────
BG        = (22,  28,  38)   # main background
BG_PANEL  = (30,  38,  52)   # panel fill
BG_TITLE  = (14,  18,  26)   # title bar (very dark, accent line draws on top)
BG_TH     = (26,  34,  46)   # panel header strip
BG_ROW1   = (34,  44,  58)
BG_ROW2   = (40,  52,  68)
LINE      = (52,  66,  88)
C_WHITE   = (225, 228, 232)
C_LBLUE   = (195, 208, 218)
C_DIM     = (130, 140, 155)
C_WARN    = ( 80, 160, 240)  # classification hint (orange in BGR display)

# Default accent (fallback when param invalid)
_DEF_HEX  = '#4ade80'
_DEF_BGR  = ( 80, 220, 140)  # BGR green


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip('#')
    if len(h) != 6:
        raise ValueError
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def _accent_bgr(params: dict) -> tuple[int, int, int]:
    try:
        return _hex_to_bgr(str(params.get('accent_color', _DEF_HEX)))
    except Exception:
        return _DEF_BGR


def _dim_accent(accent: tuple[int, int, int], factor: float = 0.55) -> tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in accent)  # type: ignore


def _ascii(s: str) -> str:
    acc = {'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ü':'u','ù':'u',
           'û':'u','ô':'o','î':'i','ï':'i','ç':'c','É':'E','È':'E','À':'A','Ç':'C'}
    return ''.join(acc.get(c, c if ord(c) < 128 else '?') for c in str(s))


def _txt(img, text, x, y, color=C_WHITE, scale=0.40, bold=False):
    cv2.putText(img, _ascii(text), (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2 if bold else 1, cv2.LINE_AA)


def _panel(img, rect, label: str, accent: tuple):
    x1, y1, x2, y2 = rect
    cv2.rectangle(img, (x1, y1), (x2, y2), BG_PANEL, -1)
    cv2.rectangle(img, (x1, y1), (x2, y1 + 22), BG_TH, -1)
    _txt(img, label, x1 + 6, y1 + 15, accent, scale=0.42, bold=True)
    cv2.rectangle(img, (x1, y1), (x2, y2), LINE, 1)
    # Accent top border
    cv2.line(img, (x1, y1), (x2, y1), accent, 2)


def _thumb(img, src, rect):
    x1, y1, x2, y2 = rect
    if src is None:
        cv2.rectangle(img, (x1, y1 + 22), (x2, y2), (36, 46, 62), -1)
        _txt(img, 'NOT CONNECTED', x1 + 40, (y1 + y2) // 2, C_DIM, scale=0.38)
        return
    frame = src
    if len(frame.shape) == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    tw, th = x2 - x1, y2 - y1 - 23
    img[y1 + 23:y2, x1:x2] = cv2.resize(frame, (tw, th))


def _modal_table(img, modal_stats, rect, accent: tuple):
    x1, y1, x2, y2 = rect
    if not modal_stats:
        _txt(img, 'Not connected', x1 + 8, y1 + 60, C_DIM)
        return
    row_h = 22
    ry = y1 + 28
    items = list(modal_stats.items()) if isinstance(modal_stats, dict) else []
    bar_accent = _dim_accent(accent, 0.8)
    for i, (phase, pct) in enumerate(items):
        bg = BG_ROW1 if i % 2 == 0 else BG_ROW2
        cv2.rectangle(img, (x1 + 4, ry), (x2 - 4, ry + row_h), bg, -1)
        pct_str = str(pct) if isinstance(pct, str) else f'{float(pct):.1f}%'
        _txt(img, str(phase), x1 + 10, ry + row_h - 7, C_LBLUE, scale=0.40)
        _txt(img, pct_str,    x2 - 80,  ry + row_h - 7, accent,  scale=0.42, bold=True)
        try:
            bar_frac = min(float(pct_str.strip('%')) / 100.0, 1.0) if '%' in pct_str else 0.0
        except Exception:
            bar_frac = 0.0
        bar_w = int((x2 - x1 - 90) * bar_frac)
        if bar_w > 0:
            cv2.rectangle(img,
                          (x1 + 10, ry + row_h - 5),
                          (x1 + 10 + bar_w, ry + row_h - 3),
                          bar_accent, -1)
        ry += row_h
        if ry + row_h > y2 - 6:
            break


def _morph_table(img, rect, vals: dict):
    x1, y1, x2, y2 = rect
    row_h = 28
    ry = y1 + 28
    for label, value in vals.items():
        cv2.line(img, (x1 + 4, ry + row_h - 1), (x2 - 4, ry + row_h - 1), LINE, 1)
        _txt(img, label,    x1 + 8,   ry + row_h - 9, C_DIM,   scale=0.39)
        _txt(img, str(value), x2 - 130, ry + row_h - 9, C_WHITE, scale=0.42, bold=True)
        ry += row_h
        if ry + row_h > y2 - 6:
            break


def _classification_hint(modal_stats: dict | None) -> str:
    if not modal_stats:
        return 'No modal data'
    phases = {k.lower(): v for k, v in modal_stats.items()}

    def pct(key):
        for k, v in phases.items():
            if key in k:
                try:
                    return float(str(v).strip('%'))
                except Exception:
                    return 0.0
        return 0.0

    q  = pct('quartz') or pct('grain')
    f  = pct('feldspar') or pct('feldspath')
    m  = pct('matrix') or pct('matrice') or pct('cement') or pct('ciment')
    op = pct('opaque') or pct('opaq')

    total = q + f + m + op
    if total < 5:   return 'Insufficient modal data'
    if op > 40:     return 'Opaque-rich / Fe-Mn ore?'
    if q > 80:      return 'Quartzite / Quartz arenite'
    if q > 60 and f < 10: return 'Quartz arenite (mature)'
    if q > 40 and f > 20: return 'Arkose / Feldspathic arenite'
    if m > 60:      return 'Wacke / Mudstone (high matrix)'
    if f > 50:      return 'Feldspar-rich (arkose / igneous?)'
    return 'Mixed / Litharenite'


@vision_node(
    type_id='geo_thin_section_report',
    label='Thin Section Report',
    category='geology',
    icon='FileText',
    description=(
        "Generates a comprehensive petrographic report image from all analysis results.\n\n"
        "Connect PPL/XPL images, modal stats (from Point Counter), grain morphometry scalars "
        "(from Grain Population Stats), neighbor data, and the size histogram.\n"
        "Fill in sample metadata in the parameters. Use Accent Color to match your theme."
    ),
    inputs=[
        {'id': 'ppl_image',     'color': 'image',  'label': 'PPL Image'},
        {'id': 'xpl_image',     'color': 'image',  'label': 'XPL Image'},
        {'id': 'histogram',     'color': 'image',  'label': 'Size Histogram'},
        {'id': 'modal_stats',   'color': 'any',    'label': 'Modal Stats (Point Counter)'},
        {'id': 'neighbor_data', 'color': 'any',    'label': 'Neighbor Data'},
        {'id': 'grain_count',   'color': 'scalar', 'label': 'Grain Count'},
        {'id': 'mean_dia_um',   'color': 'scalar', 'label': 'Mean Diameter'},
        {'id': 'circularity',   'color': 'scalar', 'label': 'Mean Circularity'},
        {'id': 'grain_frac',    'color': 'scalar', 'label': 'Grain Fraction (%)'},
        {'id': 'opaque_frac',   'color': 'scalar', 'label': 'Opaque Fraction (%)'},
        {'id': 'opaque_count',  'color': 'scalar', 'label': 'Opaque Count'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Report'},
    ],
    params=[
        {'id': 'sample_name',  'label': 'Sample Name',  'type': 'string', 'default': 'Sample 01'},
        {'id': 'rock_type',    'label': 'Rock Type',    'type': 'string', 'default': 'Unknown'},
        {'id': 'formation',    'label': 'Formation',    'type': 'string', 'default': ''},
        {'id': 'analyst',      'label': 'Analyst',      'type': 'string', 'default': 'Anonymous'},
        {'id': 'location',     'label': 'Location',     'type': 'string', 'default': ''},
        {'id': 'age',          'label': 'Age / Period', 'type': 'string', 'default': ''},
        {'id': 'accent_color', 'label': 'Accent Color', 'type': 'color',  'default': '#4ade80'},
    ]
)
class GeoThinSectionReport(NodeProcessor):
    def process(self, inputs, params):
        accent = _accent_bgr(params)
        dim_ac = _dim_accent(accent, 0.35)   # very dark accent for title bg strip

        img = np.full((IH, IW, 3), BG, dtype=np.uint8)

        # ── Title bar ──────────────────────────────────────────────────────
        cv2.rectangle(img, (0, 0), (IW, P_TITLE[3]), BG_TITLE, -1)
        # Full-width accent line at bottom of title
        cv2.line(img, (0, P_TITLE[3] - 1), (IW, P_TITLE[3] - 1), accent, 3)
        # Subtle accent fill at very top (thin strip)
        cv2.rectangle(img, (0, 0), (IW, 4), dim_ac, -1)

        sample  = params.get('sample_name', 'Sample 01')
        rock    = params.get('rock_type',   'Unknown')
        form    = params.get('formation',   '')
        analyst = params.get('analyst',     'Anonymous')
        loc     = params.get('location',    '')
        age     = params.get('age',         '')
        date    = datetime.date.today().strftime('%Y-%m-%d')

        _txt(img, 'THIN SECTION PETROGRAPHIC ANALYSIS', 12, 24,
             accent, scale=0.60, bold=True)
        _txt(img, 'VNStudio Geology', IW - 185, 24, C_DIM, scale=0.42)

        meta_parts = [f'Sample: {sample}', f'Rock: {rock}']
        if form:  meta_parts.append(f'Formation: {form}')
        if loc:   meta_parts.append(f'Location: {loc}')
        if age:   meta_parts.append(f'Age: {age}')
        meta_parts += [f'Analyst: {analyst}', f'Date: {date}']
        _txt(img, '  |  '.join(meta_parts), 12, 46, C_LBLUE, scale=0.38)

        # ── PPL panel ─────────────────────────────────────────────────────
        _panel(img, P_PPL, 'PPL  —  Natural Light (A)', accent)
        _thumb(img, inputs.get('ppl_image'), P_PPL)

        # ── XPL panel ─────────────────────────────────────────────────────
        _panel(img, P_XPL, 'XPL  —  Polarized Light (A+)', accent)
        _thumb(img, inputs.get('xpl_image'), P_XPL)

        # ── Modal analysis panel ───────────────────────────────────────────
        modal = inputs.get('modal_stats')
        _panel(img, P_MODAL, 'MODAL ANALYSIS  (Point Counting)', accent)
        _modal_table(img, modal, P_MODAL, accent)

        hint = _classification_hint(modal if isinstance(modal, dict) else None)
        x1m, y1m, x2m, y2m = P_MODAL
        cv2.line(img, (x1m + 4, y2m - 32), (x2m - 4, y2m - 32), LINE, 1)
        _txt(img, 'Classification hint:', x1m + 8, y2m - 19, C_DIM, scale=0.37)
        _txt(img, hint, x1m + 150, y2m - 19, C_WARN, scale=0.40, bold=True)

        # ── Histogram panel ────────────────────────────────────────────────
        _panel(img, P_HISTO, 'GRAIN SIZE DISTRIBUTION', accent)
        histo = inputs.get('histogram')
        if histo is not None:
            x1h, y1h, x2h, y2h = P_HISTO
            tw, th = x2h - x1h - 8, y2h - y1h - 26
            img[y1h + 24:y2h - 2, x1h + 4:x2h - 4] = cv2.resize(histo, (tw, th))
        else:
            _txt(img, 'Histogram not connected',
                 P_HISTO[0] + 20, (P_HISTO[1] + P_HISTO[3]) // 2, C_DIM)

        # ── Grain morphometry panel ────────────────────────────────────────
        _panel(img, P_MORPH, 'GRAIN MORPHOMETRY', accent)

        def _fv(key, fmt='{:.2f}', suffix=''):
            v = inputs.get(key)
            if v is None: return '—'
            try:   return fmt.format(float(v)) + suffix
            except: return str(v)

        _morph_table(img, P_MORPH, {
            'Grain count':      _fv('grain_count', '{:.0f}'),
            'Mean diameter':    _fv('mean_dia_um',  '{:.1f}', ' µm'),
            'Mean circularity': _fv('circularity',  '{:.3f}'),
            'Grain fraction':   _fv('grain_frac',   '{:.1f}', ' %'),
            'Opaque fraction':  _fv('opaque_frac',  '{:.1f}', ' %'),
            'Opaque count':     _fv('opaque_count', '{:.0f}'),
        })

        # ── Neighbor analysis panel ────────────────────────────────────────
        _panel(img, P_NEIGH, 'NEIGHBOR ANALYSIS  (Context)', accent)
        nd = inputs.get('neighbor_data')
        if isinstance(nd, dict):
            neigh_vals = {
                'Total grains':      str(nd.get('Total Grains', '—')),
                'Mean coordination': f"{nd.get('Mean Coordination', 0):.2f}",
                'Max neighbors':     str(nd.get('Max Neighbors', '—')),
                'Isolated grains':   str(nd.get('Isolated Grains', '—')),
            }
        else:
            neigh_vals = {'Neighbor data': 'not connected'}
        _morph_table(img, P_NEIGH, neigh_vals)

        x1n, y1n, x2n, y2n = P_NEIGH
        mc = nd.get('Mean Coordination', 0) if isinstance(nd, dict) else 0
        if mc > 0:
            fabric = (
                'Open fabric / loose packing'     if mc < 2.5 else
                'Moderate packing (fluvial?)'      if mc < 4.0 else
                'Dense packing / pressure solution?'
            )
            cv2.line(img, (x1n + 4, y2n - 48), (x2n - 4, y2n - 48), LINE, 1)
            _txt(img, 'Fabric:', x1n + 8,  y2n - 33, C_DIM,   scale=0.37)
            _txt(img, fabric,   x1n + 8,  y2n - 14, accent,  scale=0.39, bold=True)

        # ── Outer border ──────────────────────────────────────────────────
        cv2.rectangle(img, (0, 0), (IW - 1, IH - 1), accent, 2)

        return {'main': img}
