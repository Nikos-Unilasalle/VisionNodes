import cv2
import numpy as np
import datetime
from registry import vision_node, NodeProcessor

IW, IH = 1400, 720

P_TITLE   = (0,    0,    IW,   58)
P_PREVIEW = (8,    66,   296,  400)
P_CBC     = (304,  66,   700,  400)
P_DIFF    = (708,  66,   1100, 400)
P_META    = (1108, 66,   1392, 400)
P_INTERP  = (8,    408,  1392, 712)

BG        = (22,  28,  38)
BG_PANEL  = (30,  38,  52)
BG_TITLE  = (14,  18,  26)
BG_TH     = (26,  34,  46)
BG_ROW1   = (34,  44,  58)
BG_ROW2   = (40,  52,  68)
LINE      = (52,  66,  88)
C_WHITE   = (225, 228, 232)
C_LBLUE   = (195, 208, 218)
C_DIM     = (130, 140, 155)
C_OK      = (80,  200, 100)
C_WARN    = (50,  130, 240)
C_HIGH    = (60,  80,  220)
C_LOW     = (200, 160, 50)

_DEF_HEX = '#ef4444'
_DEF_BGR = (68, 68, 239)

# Percentage of total cells per field
CBC_RANGES = {
    'RBC': (85.0, 100.0),
    'WBC': (1.0,  12.0),
    'PLT': (3.0,  10.0),
}

DIFF_RANGES = {
    'Neutrophil': (60.0, 77.0),
    'Lymphocyte': (12.0, 30.0),
    'Monocyte':   (3.0,  10.0),
    'Eosinophil': (2.0,  10.0),
    'Basophil':   (0.0,  2.0),
}

SPECIES_LABEL = {
    'Canine':  'Canine (Dog)',
    'Feline':  'Feline (Cat)',
    'Equine':  'Equine (Horse)',
    'Bovine':  'Bovine (Cattle)',
}


def _hex_to_bgr(h):
    try:
        s = h.lstrip('#')
        if len(s) != 6:
            return _DEF_BGR
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        return (b, g, r)
    except Exception:
        return _DEF_BGR


def _accent_bgr(params):
    return _hex_to_bgr(str(params.get('accent_color', _DEF_HEX)))


def _dim_accent(accent, factor=0.55):
    return tuple(max(0, int(c * factor)) for c in accent)


def _ascii(s):
    acc = {'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ü':'u','ù':'u',
           'û':'u','ô':'o','î':'i','ï':'i','ç':'c','É':'E','È':'E','À':'A','Ç':'C'}
    return ''.join(acc.get(c, c if ord(c) < 128 else '?') for c in str(s))


def _txt(img, text, x, y, color=C_WHITE, scale=0.40, bold=False):
    cv2.putText(img, _ascii(text), (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2 if bold else 1, cv2.LINE_AA)


def _panel(img, rect, label, accent):
    x1, y1, x2, y2 = rect
    cv2.rectangle(img, (x1, y1), (x2, y2), BG_PANEL, -1)
    cv2.rectangle(img, (x1, y1), (x2, y1 + 22), BG_TH, -1)
    _txt(img, label, x1 + 6, y1 + 15, accent, scale=0.42, bold=True)
    cv2.rectangle(img, (x1, y1), (x2, y2), LINE, 1)
    cv2.line(img, (x1, y1), (x2, y1), accent, 2)


def _thumb(img, src, rect):
    x1, y1, x2, y2 = rect
    if src is None:
        cv2.rectangle(img, (x1, y1 + 22), (x2, y2), (36, 46, 62), -1)
        _txt(img, 'NOT CONNECTED', x1 + 16, (y1 + y2) // 2, C_DIM, scale=0.38)
        return
    frame = src if len(src.shape) == 3 else cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)
    tw, th = x2 - x1, y2 - y1 - 23
    img[y1 + 23:y2, x1:x2] = cv2.resize(frame, (tw, th))


def _status_for(key, value, total):
    if total <= 0:
        return '—', C_DIM
    pct = value / total * 100.0
    lo, hi = CBC_RANGES.get(key, (0, 100))
    if pct < lo:
        return f'{pct:.1f}% (LOW)', C_LOW
    if pct > hi:
        return f'{pct:.1f}% (HIGH)', C_HIGH
    return f'{pct:.1f}% OK', C_OK


def _cbc_table(img, counts, rect, accent):
    x1, y1, x2, y2 = rect
    total = max(1, int(counts.get('total', 1)))
    row_h = 48
    ry = y1 + 30
    keys = [('RBC', 'Erythrocytes'), ('WBC', 'Leukocytes'), ('PLT', 'Thrombocytes')]
    for i, (key, name) in enumerate(keys):
        bg = BG_ROW1 if i % 2 == 0 else BG_ROW2
        cv2.rectangle(img, (x1 + 4, ry), (x2 - 4, ry + row_h), bg, -1)
        cv2.line(img, (x1 + 4, ry + row_h), (x2 - 4, ry + row_h), LINE, 1)
        val = int(counts.get(key, 0))
        status_str, status_col = _status_for(key, val, total)
        _txt(img, key,       x1 + 10, ry + 16, accent,     scale=0.55, bold=True)
        _txt(img, name,      x1 + 10, ry + 34, C_DIM,      scale=0.35)
        _txt(img, str(val),  x2 - 120, ry + 16, C_WHITE,   scale=0.55, bold=True)
        _txt(img, status_str, x2 - 120, ry + 34, status_col, scale=0.36)
        ry += row_h
    _txt(img, f'Total cells counted: {total}', x1 + 10, ry + 18, C_DIM, scale=0.37)


def _diff_table(img, counts, wbc_diff, rect, accent):
    x1, y1, x2, y2 = rect
    wbc_total = max(1, int(counts.get('WBC', 1)))
    row_h = 48
    ry = y1 + 30
    subtypes = ['Neutrophil', 'Lymphocyte', 'Monocyte', 'Eosinophil', 'Basophil']
    bar_w_max = (x2 - x1) - 20
    for i, stype in enumerate(subtypes):
        bg = BG_ROW1 if i % 2 == 0 else BG_ROW2
        cv2.rectangle(img, (x1 + 4, ry), (x2 - 4, ry + row_h), bg, -1)
        n = int(wbc_diff.get(stype, 0))
        pct = n / wbc_total * 100.0
        lo, hi = DIFF_RANGES.get(stype, (0, 100))
        if pct < lo:
            bar_col = C_LOW
            flag = ' LOW'
        elif pct > hi:
            bar_col = C_HIGH
            flag = ' HIGH'
        else:
            bar_col = C_OK
            flag = ''
        _txt(img, stype[:5],        x1 + 8,  ry + 16, C_LBLUE, scale=0.45, bold=True)
        _txt(img, f'{n} cells',     x1 + 8,  ry + 33, C_DIM,   scale=0.34)
        _txt(img, f'{pct:.0f}%{flag}', x2 - 80, ry + 24, bar_col, scale=0.42, bold=True)
        bar_fill = int(bar_w_max * min(pct / 100.0, 1.0))
        if bar_fill > 0:
            cv2.rectangle(img,
                          (x1 + 10, ry + row_h - 6),
                          (x1 + 10 + bar_fill, ry + row_h - 3),
                          _dim_accent(bar_col, 0.85), -1)
        ry += row_h


def _meta_panel(img, params, rect):
    x1, y1, x2, y2 = rect
    row_h = 26
    ry = y1 + 30
    fields = [
        ('Patient',  params.get('patient_id', '—')),
        ('Owner',    params.get('owner', '—') or '—'),
        ('Vet',      params.get('vet', '—') or '—'),
        ('Clinic',   params.get('clinic', '—') or '—'),
        ('Species',  SPECIES_LABEL.get(params.get('species', 'Canine'), 'Canine')),
        ('Date',     datetime.date.today().strftime('%Y-%m-%d')),
    ]
    for label, value in fields:
        cv2.line(img, (x1 + 4, ry + row_h - 1), (x2 - 4, ry + row_h - 1), LINE, 1)
        _txt(img, label,  x1 + 8,  ry + row_h - 9, C_DIM,   scale=0.37)
        _txt(img, value,  x1 + 70, ry + row_h - 9, C_WHITE, scale=0.39, bold=True)
        ry += row_h
    notes = params.get('notes', '')
    if notes:
        _txt(img, 'Notes:', x1 + 8, ry + 16, C_DIM, scale=0.37)
        _txt(img, notes,    x1 + 8, ry + 32, C_LBLUE, scale=0.36)


def _compute_flags(counts, wbc_diff):
    total = max(1, int(counts.get('total', 1)))
    wbc_total = max(1, int(counts.get('WBC', 1)))
    flags = []
    wbc_pct = counts.get('WBC', 0) / total * 100.0
    plt_pct = counts.get('PLT', 0) / total * 100.0
    n_pct   = wbc_diff.get('Neutrophil', 0) / wbc_total * 100.0
    l_pct   = wbc_diff.get('Lymphocyte', 0) / wbc_total * 100.0
    if wbc_pct > 12.0:
        flags.append(('LEUKOCYTOSIS', 'WBC elevated — infection / inflammation?', C_HIGH))
    if wbc_pct < 1.0:
        flags.append(('LEUKOPENIA', 'WBC low — immunosuppression?', C_WARN))
    if plt_pct < 3.0:
        flags.append(('THROMBOCYTOPENIA', 'PLT low — check clotting', C_LOW))
    if n_pct > 80.0:
        flags.append(('NEUTROPHILIA', 'Neutrophils elevated — bacterial infection?', C_HIGH))
    if l_pct > 35.0:
        flags.append(('LYMPHOCYTOSIS', 'Lymphocytes elevated — viral / lymphoma?', C_WARN))
    return flags[:4]


def _interp_panel(img, counts, wbc_diff, rect, accent):
    x1, y1, x2, y2 = rect
    flags = _compute_flags(counts, wbc_diff)

    _txt(img, 'INTERPRETATION', x1 + 8, y1 + 20, accent, scale=0.45, bold=True)
    cv2.line(img, (x1 + 8, y1 + 28), (x2 - 8, y1 + 28), LINE, 1)

    if not flags:
        badge_x, badge_y = x1 + 20, y1 + 60
        cv2.rectangle(img, (badge_x, badge_y), (badge_x + 260, badge_y + 34), C_OK, -1)
        _txt(img, 'Within normal parameters', badge_x + 10, badge_y + 22,
             (20, 30, 20), scale=0.50, bold=True)
        return

    bx = x1 + 20
    for code, msg, col in flags:
        by = y1 + 50
        badge_w = 160
        cv2.rectangle(img, (bx, by), (bx + badge_w, by + 28), _dim_accent(col, 0.35), -1)
        cv2.rectangle(img, (bx, by), (bx + badge_w, by + 28), col, 1)
        _txt(img, code, bx + 6, by + 19, col, scale=0.40, bold=True)
        _txt(img, msg,  bx + 6, by + 50, C_LBLUE, scale=0.38)
        bx += badge_w + 30


@vision_node(
    type_id='hema_blood_report',
    label='Blood Report',
    category='hematology',
    icon='FileHeart',
    description=(
        'Generates a 1400x720 veterinary hematology report dashboard.\n\n'
        'Connect Counts and WBC Diff from Blood Cell Classifier, '
        'optional smear preview image. Fill patient metadata in params.'
    ),
    resizable=True,
    min_width=300,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'rbc_count', 'label': 'RBC count',  'color': 'scalar'},
        {'id': 'wbc_count', 'label': 'WBC count',  'color': 'scalar'},
        {'id': 'plt_count', 'label': 'PLT count',  'color': 'scalar'},
        {'id': 'counts',    'label': 'Counts dict (legacy)', 'color': 'dict'},
        {'id': 'wbc_diff',  'label': 'WBC Diff',             'color': 'dict'},
        {'id': 'image',     'label': 'Smear Preview',        'color': 'image'},
    ],
    outputs=[
        {'id': 'main', 'label': 'Report', 'color': 'image'},
    ],
    params=[
        {'id': 'species',    'label': 'Species',    'type': 'enum',   'options': ['Canine', 'Feline', 'Equine', 'Bovine'], 'default': 0},
        {'id': 'patient_id', 'label': 'Patient ID', 'type': 'string', 'default': 'Patient 01'},
        {'id': 'owner',      'label': 'Owner',      'type': 'string', 'default': ''},
        {'id': 'vet',        'label': 'Vet',        'type': 'string', 'default': ''},
        {'id': 'clinic',     'label': 'Clinic',     'type': 'string', 'default': ''},
        {'id': 'notes',      'label': 'Notes',      'type': 'string', 'default': ''},
        {'id': 'accent_color', 'label': 'Accent Color', 'type': 'color', 'default': '#ef4444'},
    ],
)
class HemaBloodReport(NodeProcessor):
    def process(self, inputs, params):
        rbc_s = inputs.get('rbc_count')
        wbc_s = inputs.get('wbc_count')
        plt_s = inputs.get('plt_count')
        if rbc_s is not None or wbc_s is not None or plt_s is not None:
            rbc = int(rbc_s) if rbc_s is not None else 0
            wbc = int(wbc_s) if wbc_s is not None else 0
            plt = int(plt_s) if plt_s is not None else 0
            counts = {'RBC': rbc, 'WBC': wbc, 'PLT': plt, 'total': rbc + wbc + plt}
        else:
            counts = inputs.get('counts') or {'RBC': 0, 'WBC': 0, 'PLT': 0, 'total': 0}
        wbc_diff = inputs.get('wbc_diff') or {'Neutrophil': 0, 'Lymphocyte': 0,
                                               'Monocyte': 0, 'Eosinophil': 0, 'Basophil': 0}
        smear    = inputs.get('image')

        accent  = _accent_bgr(params)
        dim_ac  = _dim_accent(accent, 0.35)
        _species_list = ['Canine', 'Feline', 'Equine', 'Bovine']
        species = SPECIES_LABEL.get(_species_list[int(params.get('species', 0))], 'Canine (Dog)')
        date    = datetime.date.today().strftime('%Y-%m-%d')

        img = np.full((IH, IW, 3), BG, dtype=np.uint8)

        # Title bar
        cv2.rectangle(img, (0, 0), (IW, P_TITLE[3]), BG_TITLE, -1)
        cv2.rectangle(img, (0, 0), (IW, 4), dim_ac, -1)
        cv2.line(img, (0, P_TITLE[3] - 1), (IW, P_TITLE[3] - 1), accent, 3)
        _txt(img, 'HEMATOLOGY REPORT  --  VETERINARY', 12, 24, accent, scale=0.60, bold=True)
        _txt(img, f'VNStudio | {date}', IW - 210, 24, C_DIM, scale=0.42)

        patient  = params.get('patient_id', 'Patient 01')
        owner    = params.get('owner', '')
        vet      = params.get('vet', '')
        clinic   = params.get('clinic', '')
        meta_parts = [f'Patient: {patient}', f'Species: {species}']
        if owner:  meta_parts.append(f'Owner: {owner}')
        if vet:    meta_parts.append(f'Vet: {vet}')
        if clinic: meta_parts.append(f'Clinic: {clinic}')
        _txt(img, '  |  '.join(meta_parts), 12, 46, C_LBLUE, scale=0.38)

        # Preview panel
        _panel(img, P_PREVIEW, 'BLOOD SMEAR', accent)
        _thumb(img, smear, P_PREVIEW)

        # CBC panel
        _panel(img, P_CBC, 'COMPLETE BLOOD COUNT  (cells / field)', accent)
        _cbc_table(img, counts, P_CBC, accent)

        # Differential panel
        _panel(img, P_DIFF, 'WBC DIFFERENTIAL  (% of leukocytes)', accent)
        _diff_table(img, counts, wbc_diff, P_DIFF, accent)

        # Metadata panel
        _panel(img, P_META, 'PATIENT INFO', accent)
        _meta_panel(img, params, P_META)

        # Interpretation panel
        cv2.rectangle(img, P_INTERP[:2], P_INTERP[2:], BG_PANEL, -1)
        cv2.rectangle(img, P_INTERP[:2], P_INTERP[2:], LINE, 1)
        cv2.line(img, P_INTERP[:2], (P_INTERP[2], P_INTERP[1]), accent, 2)
        _interp_panel(img, counts, wbc_diff, P_INTERP, accent)

        cv2.rectangle(img, (0, 0), (IW - 1, IH - 1), accent, 2)

        return {'main': img}
