"""
ml_spectral_features.py — Add spectral indices / band ratios to a pixel table.

Inserts new columns into a DataFrame (from GT Sampler or Bands->Table).
Place between GT Sampler -> GP (training) and Bands->Table -> Apply (inference).
Both paths must use the same node config so feature columns match.
"""
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'spectral_feat'

_EPS = 1e-6  # avoid div-by-zero


def _safe_ratio(a, b):
    return a / (b + _EPS)


def _safe_log(a):
    return np.log1p(np.clip(a, 0, None))


def _info_panel(lines, w=440, h=200, title=''):
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 15
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:68], (8, 44 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.37, color, 1, cv2.LINE_AA)
    return img


@vision_node(
    type_id='ml_spectral_features',
    label='Spectral Features',
    category='ml',
    icon='GitBranch',
    description=(
        "Add spectral indices and band ratios to a pixel table. "
        "Place between GT Sampler and GP (training) AND between "
        "Bands->Table and Apply Ensemble (inference). "
        "Both paths must use identical settings so feature columns match."
    ),
    inputs=[
        {'id': 'table', 'color': 'data', 'label': 'Pixel table (band columns)'},
    ],
    outputs=[
        {'id': 'table',   'color': 'data',  'label': 'Augmented table'},
        {'id': 'preview', 'color': 'image', 'label': 'Features added'},
    ],
    params=[
        {'id': 'blue_col',  'type': 'string', 'default': 'Bleu',  'label': 'Blue column name'},
        {'id': 'green_col', 'type': 'string', 'default': 'Vert',  'label': 'Green column name'},
        {'id': 'red_col',   'type': 'string', 'default': 'Rouge', 'label': 'Red column name'},
        {'id': 'nir_col',   'type': 'string', 'default': 'NIR',   'label': 'NIR column name'},
        # Predefined indices
        {'id': 'add_red_green',  'type': 'bool', 'default': True,  'label': 'Red/Green (turbidity proxy)'},
        {'id': 'add_blue_green', 'type': 'bool', 'default': True,  'label': 'Blue/Green'},
        {'id': 'add_blue_red',   'type': 'bool', 'default': False, 'label': 'Blue/Red'},
        {'id': 'add_blue_nir',   'type': 'bool', 'default': False, 'label': 'Blue/NIR'},
        {'id': 'add_ndti',       'type': 'bool', 'default': True,  'label': 'NDTI = (Red-Green)/(Red+Green)'},
        {'id': 'add_ndwi',       'type': 'bool', 'default': False, 'label': 'NDWI = (Green-NIR)/(Green+NIR)'},
        {'id': 'add_log_red',    'type': 'bool', 'default': True,  'label': 'log(Red+1)'},
        {'id': 'add_log_blue',   'type': 'bool', 'default': False, 'label': 'log(Blue+1)'},
        # Custom expressions (Python, use b=blue, g=green, r=red, n=nir)
        {'id': 'custom_expr', 'type': 'string', 'default': '',
         'label': 'Custom expr (e.g. r/g, log1p(b/r)) — use b,g,r,n'},
        {'id': 'custom_name', 'type': 'string', 'default': 'custom',
         'label': 'Custom feature name'},
    ],
    resizable=True, min_width=280, min_height=200,
)
class SpectralFeaturesNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        df = inputs.get('table')
        print(f'[SpectralFeatures] inputs keys={list(inputs.keys())} table_type={type(df).__name__}')
        if df is None or not isinstance(df, pd.DataFrame):
            send_notification('SpectralFeatures: waiting for table input', notif_id=_NOTIF)
            return {}
        print(f'[SpectralFeatures] cols_in={list(df.columns)[:10]} len={len(df)}')

        df = df.copy()

        b_col = str(params.get('blue_col',  'Bleu')).strip()
        g_col = str(params.get('green_col', 'Vert')).strip()
        r_col = str(params.get('red_col',   'Rouge')).strip()
        n_col = str(params.get('nir_col',   'NIR')).strip()

        missing = [c for c in (b_col, g_col, r_col, n_col) if c not in df.columns]
        if missing:
            send_notification(f'SpectralFeatures: missing columns {missing}. Have: {list(df.columns)[:8]}',
                              level='error', notif_id=_NOTIF)
            return {}

        b = df[b_col].to_numpy(dtype=np.float32)
        g = df[g_col].to_numpy(dtype=np.float32)
        r = df[r_col].to_numpy(dtype=np.float32)
        n = df[n_col].to_numpy(dtype=np.float32)

        added = []

        if params.get('add_red_green', True):
            df['Red_Green'] = _safe_ratio(r, g)
            added.append('Red_Green')

        if params.get('add_blue_green', True):
            df['Blue_Green'] = _safe_ratio(b, g)
            added.append('Blue_Green')

        if params.get('add_blue_red', False):
            df['Blue_Red'] = _safe_ratio(b, r)
            added.append('Blue_Red')

        if params.get('add_blue_nir', False):
            df['Blue_NIR'] = _safe_ratio(b, n)
            added.append('Blue_NIR')

        if params.get('add_ndti', True):
            df['NDTI'] = _safe_ratio(r - g, r + g)
            added.append('NDTI')

        if params.get('add_ndwi', False):
            df['NDWI'] = _safe_ratio(g - n, g + n)
            added.append('NDWI')

        if params.get('add_log_red', True):
            df['log_Red'] = _safe_log(r)
            added.append('log_Red')

        if params.get('add_log_blue', False):
            df['log_Blue'] = _safe_log(b)
            added.append('log_Blue')

        # Custom expression
        expr = str(params.get('custom_expr', '')).strip()
        cname = str(params.get('custom_name', 'custom')).strip() or 'custom'
        if expr:
            try:
                result = eval(expr, {'__builtins__': {}}, {  # noqa: S307
                    'b': b, 'g': g, 'r': r, 'n': n,
                    'log1p': np.log1p, 'sqrt': np.sqrt,
                    'abs': np.abs, 'clip': np.clip,
                })
                df[cname] = np.asarray(result, dtype=np.float32)
                added.append(cname)
            except Exception as e:
                send_notification(f'SpectralFeatures: custom expr error: {e}', level='error', notif_id=_NOTIF)

        send_notification(f'SpectralFeatures: +{len(added)} features ({len(df)} rows)',
                          progress=1.0, notif_id=_NOTIF)

        lines = [
            f'Rows: {len(df)}',
            f'Added {len(added)} features:',
        ] + [f'  + {f}' for f in added]
        preview = _info_panel(lines, title='Spectral Features')

        return {'table': df, 'preview': preview}
