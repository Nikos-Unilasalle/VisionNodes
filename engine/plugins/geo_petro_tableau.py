from registry import vision_node, NodeProcessor


def _pct(v) -> str:
    try:
        f = float(v)
        return f'{f:.1f} %'
    except Exception:
        return str(v) if v is not None else '—'


def _fmt(v, decimals: int = 2, suffix: str = '') -> str:
    if v is None:
        return '—'
    try:
        f = float(v)
        if f == int(f):
            return f'{int(f)}{suffix}'
        return f'{f:.{decimals}f}{suffix}'
    except Exception:
        return str(v)


def _classification_hint(modal: dict | None) -> str:
    if not modal:
        return 'No modal data'
    phases = {k.lower(): v for k, v in modal.items()}

    def pct(key):
        for k, v in phases.items():
            if key in k:
                try:
                    return float(str(v).strip('%'))
                except Exception:
                    return 0.0
        return 0.0

    q  = pct('quartz') or pct('grain') or pct('phase 1')
    f  = pct('feldspar') or pct('feldspath')
    m  = pct('matrix') or pct('matrice') or pct('cement') or pct('ciment') or pct('phase 2')
    op = pct('opaque') or pct('opaq')

    total = q + f + m + op
    if total < 5:         return 'Insufficient modal data'
    if op > 40:           return 'Opaque-rich / Fe-Mn ore?'
    if q > 80:            return 'Quartzite / Quartz arenite'
    if q > 60 and f < 10: return 'Quartz arenite (mature)'
    if q > 40 and f > 20: return 'Arkose / Feldspathic arenite'
    if m > 60:            return 'Wacke / Mudstone (matrix-rich)'
    if f > 50:            return 'Feldspar-rich (arkose / igneous?)'
    return 'Mixed / Litharenite'


@vision_node(
    type_id='geo_petro_tableau',
    label='Petro Report (Tableau)',
    category='geology',
    icon='FileText',
    description=(
        "Aggregates all petrographic analysis results into a structured data report.\n\n"
        "Output is a nested dict {section: {key: value}} displayed as a clean React table.\n"
        "Connect: modal stats (Point Counter), opaque stats, grain morphometry scalars, "
        "and neighbor data. Metadata set in params."
    ),
    inputs=[
        {'id': 'modal_stats',   'color': 'any',    'label': 'Modal Stats (Point Counter)'},
        {'id': 'neighbor_data', 'color': 'any',    'label': 'Neighbor Data'},
        {'id': 'grain_count',   'color': 'scalar', 'label': 'Grain Count'},
        {'id': 'mean_dia_um',   'color': 'scalar', 'label': 'Mean Diameter (µm)'},
        {'id': 'circularity',   'color': 'scalar', 'label': 'Mean Circularity'},
        {'id': 'grain_frac',    'color': 'scalar', 'label': 'Grain Fraction (%)'},
        {'id': 'opaque_count',  'color': 'scalar', 'label': 'Opaque Count'},
        {'id': 'opaque_frac',   'color': 'scalar', 'label': 'Opaque Fraction (%)'},
        {'id': 'aspect_ratio',  'color': 'scalar', 'label': 'Mean Aspect Ratio'},
    ],
    outputs=[
        {'id': 'report', 'color': 'any', 'label': 'Report Dict'},
    ],
    params=[
        {'id': 'sample_name', 'label': 'Sample Name',  'type': 'string', 'default': 'Sample 01'},
        {'id': 'rock_type',   'label': 'Rock Type',    'type': 'string', 'default': 'Unknown'},
        {'id': 'formation',   'label': 'Formation',    'type': 'string', 'default': ''},
        {'id': 'analyst',     'label': 'Analyst',      'type': 'string', 'default': 'Anonymous'},
        {'id': 'location',    'label': 'Location',     'type': 'string', 'default': ''},
        {'id': 'age',         'label': 'Age / Period', 'type': 'string', 'default': ''},
    ]
)
class GeoPetroTableauNode(NodeProcessor):
    def process(self, inputs, params):
        modal   = inputs.get('modal_stats')
        nd_data = inputs.get('neighbor_data')

        # ── Modal Analysis section ─────────────────────────────────────────
        modal_section: dict = {}
        if isinstance(modal, dict):
            for phase, pct in modal.items():
                modal_section[str(phase)] = str(pct) if isinstance(pct, str) else f'{float(pct):.1f} %'
        else:
            modal_section['Status'] = 'Not connected'

        # ── Grain Morphometry section ──────────────────────────────────────
        morph_section = {
            'Count':       _fmt(inputs.get('grain_count'), 0),
            'Mean diam.':  _fmt(inputs.get('mean_dia_um'),  1, ' µm'),
            'Circularity': _fmt(inputs.get('circularity'),  3),
            'Aspect ratio':_fmt(inputs.get('aspect_ratio'), 2),
            'Grain frac.': _pct(inputs.get('grain_frac')),
        }

        # ── Opaques section ────────────────────────────────────────────────
        opaque_section = {
            'Count':    _fmt(inputs.get('opaque_count'), 0),
            'Fraction': _pct(inputs.get('opaque_frac')),
        }

        # ── Neighbor Analysis section ──────────────────────────────────────
        if isinstance(nd_data, dict):
            neighbor_section = {
                'Total grains':    str(nd_data.get('Total Grains', '—')),
                'Mean coord.':     _fmt(nd_data.get('Mean Coordination'), 2),
                'Max neighbors':   str(nd_data.get('Max Neighbors', '—')),
                'Isolated grains': str(nd_data.get('Isolated Grains', '—')),
            }
        else:
            neighbor_section = {'Status': 'Not connected'}

        # ── Classification section ─────────────────────────────────────────
        hint = _classification_hint(modal if isinstance(modal, dict) else None)
        mc = nd_data.get('Mean Coordination', 0) if isinstance(nd_data, dict) else 0
        if mc > 0:
            fabric = (
                'Open / loose packing'        if mc < 2.5 else
                'Moderate (fluvial?)'          if mc < 4.0 else
                'Dense / pressure solution?'
            )
        else:
            fabric = '—'

        class_section = {
            'Rock type':  params.get('rock_type',  'Unknown'),
            'Formation':  params.get('formation',  '—') or '—',
            'Age':        params.get('age',        '—') or '—',
            'Analyst':    params.get('analyst',    'Anonymous'),
            'Location':   params.get('location',   '—') or '—',
            'Petro hint': hint,
            'Fabric':     fabric,
        }

        report = {
            'Modal Analysis':    modal_section,
            'Morphometry':       morph_section,
            'Opaques':           opaque_section,
            'Neighbor Analysis': neighbor_section,
            'Classification':    class_section,
        }

        return {
            'report':      report,
            'display_value': hint,
        }
