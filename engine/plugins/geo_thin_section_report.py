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

# Colors (BGR)
BG        = (28,  36,  48)
BG_PANEL  = (34,  44,  58)
BG_TITLE  = (12,  48,  36)
BG_TH     = (20,  65,  50)
BG_ROW1   = (38,  50,  64)
BG_ROW2   = (44,  58,  74)
LINE      = (55,  72,  92)
C_WHITE   = (230, 232, 235)
C_GREEN   = ( 80, 220, 140)
C_LBLUE   = (200, 210, 220)
C_DIM     = (140, 148, 160)
C_ACCENT  = (100, 200, 255)
C_WARN    = ( 80, 160, 240)
C_SECTION = (130, 220, 170)


def _ascii(s: str) -> str:
    acc = {'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ü':'u','ù':'u',
           'û':'u','ô':'o','î':'i','ï':'i','ç':'c','É':'E','È':'E','À':'A','Ç':'C'}
    return ''.join(acc.get(c, c if ord(c) < 128 else '?') for c in str(s))


def _txt(img, text, x, y, color=None, scale=0.40, bold=False):
    color = color or C_WHITE
    cv2.putText(img, _ascii(text), (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2 if bold else 1, cv2.LINE_AA)


def _panel(img, rect, label: str, label_color=None):
    x1, y1, x2, y2 = rect
    cv2.rectangle(img, (x1, y1), (x2, y2), BG_PANEL, -1)
    cv2.rectangle(img, (x1, y1), (x2, y1 + 22), BG_TH, -1)
    _txt(img, label, x1 + 6, y1 + 15, label_color or C_GREEN, scale=0.42, bold=True)
    cv2.rectangle(img, (x1, y1), (x2, y2), LINE, 1)


def _thumb(img, src, rect):
    x1, y1, x2, y2 = rect
    tw, th = x2 - x1, y2 - y1
    if src is None:
        cv2.rectangle(img, (x1, y1 + 22), (x2, y2), (40, 50, 65), -1)
        _txt(img, 'NOT CONNECTED', x1 + 40, (y1 + y2) // 2, C_DIM, scale=0.38)
        return
    frame = src
    if len(frame.shape) == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    thumb = cv2.resize(frame, (tw, y2 - y1 - 23))
    img[y1 + 23:y2, x1:x2] = thumb


def _modal_table(img, modal_stats, rect):
    x1, y1, x2, y2 = rect
    if not modal_stats:
        _txt(img, 'Not connected', x1 + 8, y1 + 60, C_DIM)
        return
    row_h = 22
    ry = y1 + 28
    items = list(modal_stats.items()) if isinstance(modal_stats, dict) else []
    for i, (phase, pct) in enumerate(items):
        bg = BG_ROW1 if i % 2 == 0 else BG_ROW2
        cv2.rectangle(img, (x1 + 4, ry), (x2 - 4, ry + row_h), bg, -1)
        pct_str = str(pct) if isinstance(pct, str) else f'{float(pct):.1f}%'
        _txt(img, str(phase),   x1 + 10, ry + row_h - 7, C_LBLUE, scale=0.40)
        _txt(img, pct_str,      x2 - 80, ry + row_h - 7, C_ACCENT, scale=0.42, bold=True)
        bar_w = int((x2 - x1 - 90) * min(float(pct_str.strip('%')) / 100.0 if '%' in pct_str else 0.0, 1.0))
        cv2.rectangle(img, (x1 + 10, ry + row_h - 5), (x1 + 10 + bar_w, ry + row_h - 3),
                      C_GREEN, -1)
        ry += row_h
        if ry + row_h > y2 - 6:
            break


def _morph_table(img, rect, vals: dict):
    x1, y1, x2, y2 = rect
    row_h = 28
    ry = y1 + 28
    for label, value in vals.items():
        cv2.line(img, (x1 + 4, ry + row_h - 1), (x2 - 4, ry + row_h - 1), LINE, 1)
        _txt(img, label, x1 + 8, ry + row_h - 9, C_DIM,   scale=0.39)
        _txt(img, str(value), x2 - 130, ry + row_h - 9, C_WHITE, scale=0.42, bold=True)
        ry += row_h
        if ry + row_h > y2 - 6:
            break


def _classification_hint(modal_stats: dict | None) -> str:
    """Very rough rock type hint based on modal percentages."""
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
    if total < 5:
        return 'Insufficient modal data'
    if op > 40:
        return 'Opaque-rich / Fe-Mn ore?'
    if q > 80:
        return 'Quartzite / Quartz arenite'
    if q > 60 and f < 10:
        return 'Quartz arenite (mature)'
    if q > 40 and f > 20:
        return 'Arkose / Feldspathic arenite'
    if m > 60:
        return 'Wacke / Mudstone (high matrix)'
    if f > 50:
        return 'Feldspar-rich (arkose / igneous?)'
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
        "Fill in sample metadata in the parameters."
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
        {'id': 'sample_name', 'label': 'Sample Name',   'type': 'string', 'default': 'Sample 01'},
        {'id': 'rock_type',   'label': 'Rock Type',     'type': 'string', 'default': 'Unknown'},
        {'id': 'formation',   'label': 'Formation',     'type': 'string', 'default': ''},
        {'id': 'analyst',     'label': 'Analyst',       'type': 'string', 'default': 'Anonymous'},
        {'id': 'location',    'label': 'Location',      'type': 'string', 'default': ''},
        {'id': 'age',         'label': 'Age / Period',  'type': 'string', 'default': ''},
    ]
)
class GeoThinSectionReport(NodeProcessor):
    def process(self, inputs, params):
        img = np.full((IH, IW, 3), BG, dtype=np.uint8)

        # ── Title bar ──────────────────────────────────────────────────────
        cv2.rectangle(img, (0, 0), (IW, P_TITLE[3]), BG_TITLE, -1)
        cv2.line(img, (0, P_TITLE[3]), (IW, P_TITLE[3]), C_GREEN, 2)

        sample  = params.get('sample_name', 'Sample 01')
        rock    = params.get('rock_type',   'Unknown')
        form    = params.get('formation',   '')
        analyst = params.get('analyst',     'Anonymous')
        loc     = params.get('location',    '')
        age     = params.get('age',         '')
        date    = datetime.date.today().strftime('%Y-%m-%d')

        _txt(img, 'THIN SECTION PETROGRAPHIC ANALYSIS', 10, 22,
             C_GREEN, scale=0.60, bold=True)
        _txt(img, 'VNStudio Geology', IW - 185, 22, C_DIM, scale=0.42)

        meta_parts = [f'Sample: {sample}', f'Rock: {rock}']
        if form:    meta_parts.append(f'Formation: {form}')
        if loc:     meta_parts.append(f'Location: {loc}')
        if age:     meta_parts.append(f'Age: {age}')
        meta_parts.append(f'Analyst: {analyst}')
        meta_parts.append(f'Date: {date}')
        _txt(img, '  |  '.join(meta_parts), 10, 46, C_LBLUE, scale=0.38)

        # ── PPL panel ─────────────────────────────────────────────────────
        _panel(img, P_PPL, 'PPL  —  Natural Light (A)')
        _thumb(img, inputs.get('ppl_image'), P_PPL)

        # ── XPL panel ─────────────────────────────────────────────────────
        _panel(img, P_XPL, 'XPL  —  Polarized Light (A+)')
        _thumb(img, inputs.get('xpl_image'), P_XPL)

        # ── Modal analysis panel ───────────────────────────────────────────
        modal = inputs.get('modal_stats')
        _panel(img, P_MODAL, 'MODAL ANALYSIS  (Point Counting)')
        _modal_table(img, modal, P_MODAL)

        # Classification hint in bottom of modal panel
        hint = _classification_hint(modal if isinstance(modal, dict) else None)
        x1m, y1m, x2m, y2m = P_MODAL
        cv2.line(img, (x1m + 4, y2m - 32), (x2m - 4, y2m - 32), LINE, 1)
        _txt(img, 'Classification hint:', x1m + 8, y2m - 19, C_DIM, scale=0.37)
        _txt(img, hint, x1m + 150, y2m - 19, C_WARN, scale=0.40, bold=True)

        # ── Histogram panel ────────────────────────────────────────────────
        _panel(img, P_HISTO, 'GRAIN SIZE DISTRIBUTION')
        histo = inputs.get('histogram')
        if histo is not None:
            x1h, y1h, x2h, y2h = P_HISTO
            tw, th = x2h - x1h - 8, y2h - y1h - 26
            thumb = cv2.resize(histo, (tw, th))
            img[y1h + 24:y2h - 2, x1h + 4:x2h - 4] = thumb
        else:
            _txt(img, 'Histogram not connected', P_HISTO[0] + 20, (P_HISTO[1] + P_HISTO[3]) // 2, C_DIM)

        # ── Grain morphometry panel ────────────────────────────────────────
        _panel(img, P_MORPH, 'GRAIN MORPHOMETRY')

        def _fv(key, fmt='{:.2f}', suffix=''):
            v = inputs.get(key)
            if v is None:
                return '—'
            try:
                return fmt.format(float(v)) + suffix
            except Exception:
                return str(v)

        morph_vals = {
            'Grain count':     _fv('grain_count', '{:.0f}'),
            'Mean diameter':   _fv('mean_dia_um',   '{:.1f}', ' µm'),
            'Mean circularity':_fv('circularity',   '{:.3f}'),
            'Grain fraction':  _fv('grain_frac',    '{:.1f}', ' %'),
            'Opaque fraction': _fv('opaque_frac',   '{:.1f}', ' %'),
            'Opaque count':    _fv('opaque_count',  '{:.0f}'),
        }
        _morph_table(img, P_MORPH, morph_vals)

        # ── Neighbor analysis panel ────────────────────────────────────────
        _panel(img, P_NEIGH, 'NEIGHBOR ANALYSIS  (Context)')
        nd = inputs.get('neighbor_data')
        if isinstance(nd, dict):
            neigh_vals = {
                'Total grains':     str(nd.get('Total Grains', '—')),
                'Mean coordination':f"{nd.get('Mean Coordination', 0):.2f}",
                'Max neighbors':    str(nd.get('Max Neighbors', '—')),
                'Isolated grains':  str(nd.get('Isolated Grains', '—')),
            }
        else:
            neigh_vals = {'Neighbor data': 'not connected'}
        _morph_table(img, P_NEIGH, neigh_vals)

        # Rock fabric note
        x1n, y1n, x2n, y2n = P_NEIGH
        mc = nd.get('Mean Coordination', 0) if isinstance(nd, dict) else 0
        if mc > 0:
            if mc < 2.5:
                fabric = 'Open fabric / loose packing'
            elif mc < 4.0:
                fabric = 'Moderate packing (fluvial?)'
            else:
                fabric = 'Dense packing / pressure solution?'
            cv2.line(img, (x1n + 4, y2n - 48), (x2n - 4, y2n - 48), LINE, 1)
            _txt(img, 'Fabric:', x1n + 8, y2n - 33, C_DIM, scale=0.37)
            _txt(img, fabric,   x1n + 8, y2n - 14, C_SECTION, scale=0.39, bold=True)

        # ── Border ────────────────────────────────────────────────────────
        cv2.rectangle(img, (0, 0), (IW - 1, IH - 1), LINE, 2)

        return {'main': img}
