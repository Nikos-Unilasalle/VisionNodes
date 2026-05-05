import cv2
import numpy as np
from registry import vision_node, NodeProcessor

def _parse_hex(s, fallback=(0, 212, 170)):
    if isinstance(s, str) and s.startswith('#'):
        try:
            r = int(s[1:3], 16)
            g = int(s[3:5], 16)
            b = int(s[5:7], 16)
            return (b, g, r)
        except:
            pass
    return fallback

@vision_node(
    type_id='sci_matrix_dist',
    label='Matrix Distribution',
    category=['analysis', 'scientific'],
    icon='BarChart',
    description="Histogram and distribution analysis of float matrix data.",
    inputs=[{'id': 'data', 'color': 'any'}],
    outputs=[
        {'id': 'main',   'color': 'image', 'label': 'Histogram'},
        {'id': 'bins',   'color': 'any',   'label': 'Bin Centers'},
        {'id': 'counts', 'color': 'any',   'label': 'Bin Counts'},
        {'id': 'stats',  'color': 'any',   'label': 'Stats'},
    ],
    params=[
        {'id': 'bins',       'label': 'Bins',       'type': 'int',    'default': 64,  'min': 8,  'max': 512},
        {'id': 'log_scale',  'label': 'Log Scale',  'type': 'toggle', 'default': False},
        {'id': 'cumulative', 'label': 'Cumulative',  'type': 'toggle', 'default': False},
        {'id': 'show_stats', 'label': 'Show Stats',  'type': 'toggle', 'default': True},
        {'id': 'bar_color',  'label': 'Bar Color',  'type': 'color',  'default': '#00d4aa'},
    ],
    resizable=True, min_width=200, min_height=120
)
class MatrixDistNode(NodeProcessor):
    def _extract(self, val):
        if val is None:
            return None
        if isinstance(val, np.ndarray):
            return val.astype(np.float32)
        if isinstance(val, dict) and 'bands' in val:
            return val['bands'][0].astype(np.float32)
        return None

    def process(self, inputs, params):
        mat = self._extract(inputs.get('data'))
        if mat is None:
            return {'main': None, 'bins': None, 'counts': None, 'stats': None}

        flat = mat.flatten()
        valid = flat[np.isfinite(flat)]
        if len(valid) == 0:
            return {'main': None, 'bins': None, 'counts': None, 'stats': None}

        n_bins = int(params.get('bins', 64))
        log_scale = bool(params.get('log_scale', False))
        cumulative = bool(params.get('cumulative', False))

        m_min, m_max = float(np.min(valid)), float(np.max(valid))
        mean = float(np.mean(valid))
        std = float(np.std(valid))
        count = len(valid)
        if m_max <= m_min:
            m_max = m_min + 1.0

        hist, bin_edges = np.histogram(valid, bins=n_bins, range=(m_min, m_max))
        bin_centers = ((bin_edges[:-1] + bin_edges[1:]) * 0.5).tolist()

        if cumulative:
            hist = np.cumsum(hist)
        if log_scale:
            hist = np.log10(hist + 1.0)

        # ── Render ──
        cw, ch = 400, 200
        chart = np.full((ch, cw, 3), 18, dtype=np.uint8)

        for i in range(1, 4):
            x = int(cw * i / 4)
            y = int(ch * i / 4)
            cv2.line(chart, (x, 0), (x, ch), (40, 40, 40), 1)
            cv2.line(chart, (0, y), (cw, y), (40, 40, 40), 1)

        h_max = float(np.max(hist)) or 1.0
        pad = 8
        area_w = cw - 2 * pad
        area_h = ch - 2 * pad
        n = len(hist)
        bar_w = max(1, area_w // n)
        bc = _parse_hex(params.get('bar_color', '#00d4aa'), (0, 212, 170))

        for i, v in enumerate(hist):
            bh = int(v / h_max * area_h)
            x0 = pad + int(i / n * area_w)
            y0 = ch - pad - bh
            cv2.rectangle(chart, (x0, y0), (x0 + bar_w, ch - pad), bc, -1)

        if params.get('show_stats', True):
            font = cv2.FONT_HERSHEY_SIMPLEX
            lines = [
                f"mean={mean:.4f}  std={std:.4f}",
                f"min={m_min:.4f}  max={m_max:.4f}  n={count}",
            ]
            for li, txt in enumerate(lines):
                cv2.putText(chart, txt, (8, 14 + li * 14), font, 0.38, (180, 180, 180), 1)

        hist_list = hist.tolist()
        return {
            'main': chart,
            'bins': bin_centers,
            'counts': hist_list,
            'hist_0': hist_list,
            'stats': {'mean': mean, 'std': std, 'min': m_min, 'max': m_max, 'count': count},
            'hist_min': m_min,
            'hist_max': m_max,
        }
