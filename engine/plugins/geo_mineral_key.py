import cv2
import numpy as np
from registry import vision_node, NodeProcessor

# (name, PPL color, XPL/biref color, biref level, cleavage, diagnostic notes)
_MINERALS = {
    0: [  # Igneous / Magmatique
        ('Quartz',       'Colorless',      'Gray / White',    'Low',      'None',         'Wavy extinction; no cleavage'),
        ('K-Feldspar',   'Colorless / pk', 'Gray',            'Low',      '2 clvg ~90d',  'Grid or Carlsbad twins'),
        ('Plagioclase',  'Colorless',      'Gray',            'Low',      '2 cleavages',  'Polysynthetic (albite) twins'),
        ('Biotite',      'Brown / red',    'Yellow-brown',    'High',     '1 perfect',    'Strong pleochroism; 6-sided'),
        ('Muscovite',    'Colorless',      'Yellow / Red',    'High',     '1 perfect',    'Flakes; birds-eye extinction'),
        ('Hornblende',   'Green-brown',    'Green vivid',     'Moderate', '2 x 60d',      'Green pleochroism; ~15-25d ext'),
        ('Pyroxene',     'Colorless-grn',  'Gray-yellow',     'Moderate', '2 x 90d',      'Straight extinction; 2 clvg'),
        ('Olivine',      'Colorless',      'Vivid polychrome','High',     '2 cracks',     'Fractures; iddingsite alterat.'),
        ('Magnetite',    'Black opaque',   'Black opaque',    'Opaque',   'None',         'Isotropic; bright in refl. PPL'),
        ('Apatite',      'Colorless',      'Weak gray',       'Low',      'Imperfect',    'Hexagonal sections; inclusions'),
        ('Zircon',       'Colorless',      'High / vivid',    'High',     'Imperfect',    'Pleochroic haloes in biotite'),
    ],
    1: [  # Sedimentary / Sedimentaire
        ('Detr. Quartz', 'Colorless',      'Gray / White',    'Low',      'None',         'Possible wavy extinction'),
        ('Detr. Feldspar','Colorless',     'Gray',            'Low',      '2 cleavages',  'Altered -> clay / kaolinite'),
        ('Calcite',      'Colorless',      'Vivid colors',    'Very high','3 cleavages',  'Rhombohedral; HCl effervescence'),
        ('Dolomite',     'Colorless',      'Vivid colors',    'Very high','3 cleavages',  'Rhombohedra; curved faces'),
        ('Chert',        'Light brown',    'Isotropic / dark','Very low', 'None',         'Microcrystalline SiO2'),
        ('Glauconite',   'Green',          'Weak green',      'Low',      'Imperfect',    'Green pellets; marine indicator'),
        ('Pyrite',       'Yellow (refl)',  'Yellow (refl)',   'Opaque',   'None',         'Cubic; bright in reflected PPL'),
        ('Org. Matter',  'Brown / black',  'Opaque',          'Opaque',   '—',            'Vitrinite; amorphous kerogen'),
        ('Opal',         'Colorless',      'Isotropic',       'Isotropic','None',         'Amorphous SiO2; no extinction'),
    ],
    2: [  # Metamorphic / Metamorphique
        ('Quartz',       'Colorless',      'Gray',            'Low',      'None',         'Strong wavy extinction'),
        ('Garnet',       'Pink / red',     'Black (isotropic)','Isotrop.','Imperfect',    '12-sided sections; no cleavage'),
        ('Staurolite',   'Yellow-brown',   'Weak',            'Low',      '1 cleavage',   'Cruciform (cross) twins'),
        ('Kyanite',      'Colorless / bl', 'Gray-white',      'Low',      '2 clvg ~90d',  'Oblique extinction ~30d'),
        ('Sillimanite',  'Colorless',      'Gray-yellow',     'Low',      '1 perfect',    'Fibrous (fibrolite) or prismatic'),
        ('Andalusite',   'Pink / red',     'Weak',            'Low',      '2 cleavages',  'Chiastolite in metapelites'),
        ('Hornblende',   'Green-brown',    'Green vivid',     'Moderate', '2 x 60d',      'Common in amphibolites'),
        ('Biotite',      'Brown',          'Brown-yellow',    'High',     '1 perfect',    'Foliation; pleochroic'),
        ('Chlorite',     'Green',          'Anomal. blue',    'Low',      '1 perfect',    'Replaces biotite; anomal. biref'),
        ('Epidote',      'Yellow-green',   'Yellow-green',    'High',     '1 cleavage',   'Pistachio green; high biref'),
    ],
}

_SECTION_LABELS = ['IGNEOUS', 'SEDIMENTARY', 'METAMORPHIC']
_HEADERS = ['MINERAL', 'PPL COLOR', 'XPL / BIREF.', 'BIREF.', 'CLEAVAGE', 'NOTES']

# Column x-offsets and widths
_COL_X = [8, 138, 258, 388, 468, 568]
_COL_W = [130, 120, 130, 80,  100, 222]

W = 800
ROW_H    = 24
HEADER_H = 30
TITLE_H  = 36
SECTION_H= 28
PAD_Y    = 6

# Colors (BGR)
BG         = ( 30,  38,  50)
BG_ODD     = ( 36,  46,  60)
BG_EVEN    = ( 42,  54,  70)
BG_HEADER  = ( 18,  62,  48)
BG_TITLE   = ( 12,  45,  35)
BG_SECTION = ( 22,  52,  42)
C_TEXT     = (218, 224, 230)
C_TITLE    = ( 90, 225, 150)
C_HEADER   = (160, 235, 195)
C_SECTION  = (100, 210, 160)
C_DIM      = (140, 148, 158)
C_HIGH_LOW    = (120, 210, 100)
C_HIGH_HIGH   = ( 80, 120, 220)
C_HIGH_VERY   = ( 60,  80, 240)
C_HIGH_ISOTR  = (180, 180, 100)
C_HIGH_OPAQUE = ( 80,  80,  80)
C_HIGH_MOD    = (140, 185, 230)


def _biref_color(level: str):
    l = level.lower()
    if 'opaque' in l: return C_HIGH_OPAQUE
    if 'isotropic' in l or 'isotrop' in l: return C_HIGH_ISOTR
    if 'very high' in l: return C_HIGH_VERY
    if 'high' in l: return C_HIGH_HIGH
    if 'moderate' in l: return C_HIGH_MOD
    return C_HIGH_LOW


def _text(img, s, x, y, color=None, scale=0.40, bold=False):
    color = color or C_TEXT
    thick = 2 if bold else 1
    cv2.putText(img, str(s), (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def _build_table(systems: list[int]) -> np.ndarray:
    rows = []
    for sys_idx in systems:
        rows.append(('__section__', _SECTION_LABELS[sys_idx]))
        rows.extend(_MINERALS[sys_idx])

    total_h = TITLE_H + HEADER_H + len(rows) * ROW_H + PAD_Y * 2
    img = np.full((total_h, W, 3), BG, dtype=np.uint8)

    # Title bar
    cv2.rectangle(img, (0, 0), (W, TITLE_H), BG_TITLE, -1)
    _text(img, 'PETROGRAPHIC MINERAL IDENTIFICATION KEY  (PPL + XPL)',
          8, TITLE_H - 10, C_TITLE, scale=0.50, bold=True)

    # Column headers
    hy = TITLE_H + HEADER_H
    cv2.rectangle(img, (0, TITLE_H), (W, hy), BG_HEADER, -1)
    for col_i, hdr in enumerate(_HEADERS):
        _text(img, hdr, _COL_X[col_i], hy - 9, C_HEADER, scale=0.40, bold=True)
    cv2.line(img, (0, hy), (W, hy), (60, 80, 100), 1)

    # Data rows
    y = hy
    row_i = 0
    for row in rows:
        if row[0] == '__section__':
            # Section separator
            cv2.rectangle(img, (0, y), (W, y + SECTION_H), BG_SECTION, -1)
            _text(img, '  ' + row[1], 8, y + SECTION_H - 9, C_SECTION, scale=0.44, bold=True)
            y += SECTION_H
            row_i = 0
        else:
            name, ppl, xpl, biref, clvg, notes = row
            bg = BG_ODD if row_i % 2 == 0 else BG_EVEN
            cv2.rectangle(img, (0, y), (W, y + ROW_H), bg, -1)
            ty = y + ROW_H - 8

            _text(img, name,  _COL_X[0], ty, C_TEXT,           scale=0.40, bold=True)
            _text(img, ppl,   _COL_X[1], ty, C_DIM,            scale=0.38)
            _text(img, xpl,   _COL_X[2], ty, C_DIM,            scale=0.38)
            _text(img, biref, _COL_X[3], ty, _biref_color(biref), scale=0.37, bold=True)
            _text(img, clvg,  _COL_X[4], ty, C_DIM,            scale=0.37)
            _text(img, notes, _COL_X[5], ty, C_DIM,            scale=0.36)

            cv2.line(img, (0, y + ROW_H - 1), (W, y + ROW_H - 1), (50, 62, 78), 1)
            y += ROW_H
            row_i += 1

    # Vertical column dividers
    for cx in _COL_X[1:]:
        cv2.line(img, (cx - 2, TITLE_H), (cx - 2, total_h), (50, 62, 78), 1)

    # Footer
    cv2.line(img, (0, total_h - 1), (W, total_h - 1), (60, 80, 100), 1)

    return img


@vision_node(
    type_id='geo_mineral_key',
    label='Mineral ID Key (PPL/XPL)',
    category='geology',
    icon='BookOpen',
    description=(
        "Displays a petrographic reference table for thin-section mineral identification.\n\n"
        "Columns: PPL color | XPL birefringence | Biref. level | Cleavage | Diagnostic notes.\n"
        "Biref. level is color-coded: green=low, blue=high, dark=opaque/isotropic."
    ),
    inputs=[],
    outputs=[{'id': 'main', 'color': 'image', 'label': 'Mineral Key Table'}],
    params=[
        {'id': 'system', 'label': 'Rock System', 'type': 'enum',
         'options': ['Igneous', 'Sedimentary', 'Metamorphic', 'All Systems'],
         'default': 3},
    ]
)
class GeoMineralKey(NodeProcessor):
    def process(self, inputs, params):
        system = int(params.get('system', 3))
        if system == 3:
            systems = [0, 1, 2]
        else:
            systems = [system]
        return {'main': _build_table(systems)}
