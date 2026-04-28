from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import base64


_CV2_COLORMAPS = {
    'viridis': cv2.COLORMAP_VIRIDIS,
    'plasma':  cv2.COLORMAP_PLASMA,
    'turbo':   cv2.COLORMAP_TURBO,
    'jet':     cv2.COLORMAP_JET,
    'hot':     cv2.COLORMAP_HOT,
    'gray':    cv2.COLORMAP_BONE,
}


@vision_node(
    type_id='geo_band_calc',
    label='Band Calculator',
    category='geo',
    icon='Calculator',
    description="Free expression on bands. Variables: B1, B2, … Bn. Example: (B4-B3)/(B4+B3+1e-10)",
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[
        {'id': 'raw',      'color': 'geotiff', 'label': 'Result'},
        {'id': 'colormap', 'color': 'image',   'label': 'Colormap'},
    ],
    params=[
        {'id': 'expression', 'type': 'code',  'default': '(B4 - B3) / (B4 + B3 + 1e-10)', 'label': 'Expression'},
        {'id': 'clamp_min',  'type': 'float', 'default': -1.0, 'min': -1e6, 'max': 0,   'label': 'Clamp Min'},
        {'id': 'clamp_max',  'type': 'float', 'default':  1.0, 'min': 0,    'max': 1e6, 'label': 'Clamp Max'},
        {'id': 'colormap',   'type': 'enum',  'options': list(_CV2_COLORMAPS.keys()), 'default': 'viridis', 'label': 'Colormap'},
    ]
)
class BandCalcNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._last_expr = None
        self._compiled  = None

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'raw': None, 'colormap': None}

        bands     = geo['bands']
        count     = geo['count']
        expr      = str(params.get('expression', '')).strip()
        clamp_min = float(params.get('clamp_min', -1.0))
        clamp_max = float(params.get('clamp_max',  1.0))

        if not expr:
            return {'raw': None, 'colormap': None}

        ns = {f'B{i+1}': bands[i].astype(np.float32) for i in range(count)}
        ns['np']   = np
        ns['sqrt'] = np.sqrt
        ns['log']  = np.log
        ns['abs']  = np.abs
        ns['exp']  = np.exp

        try:
            result = eval(expr, {'__builtins__': {}}, ns)  # noqa: S307
        except Exception as e:
            send_notification(f'Band Calc: expression error: {e}', level='error', notif_id='band_calc')
            return {'raw': None, 'colormap': None}

        result  = np.asarray(result, dtype=np.float32)
        result  = np.clip(result, clamp_min, clamp_max)
        raw_geo = {**geo, 'bands': result[np.newaxis], 'count': 1, 'band_names': ['result']}

        span       = clamp_max - clamp_min if clamp_max != clamp_min else 1.0
        normalized = ((result - clamp_min) / span * 255).astype(np.uint8)
        cmap       = _CV2_COLORMAPS.get(params.get('colormap', 'viridis'), cv2.COLORMAP_VIRIDIS)
        colored    = cv2.applyColorMap(normalized, cmap)

        h, w = colored.shape[:2]
        sc   = 120 / h
        thumb_img = cv2.resize(colored, (max(1, int(w * sc)), 120))
        _, buf    = cv2.imencode('.jpg', thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb     = base64.b64encode(buf).decode('utf-8')

        return {'raw': raw_geo, 'colormap': colored, '_thumb': thumb}
