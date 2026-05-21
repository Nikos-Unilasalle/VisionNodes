from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import base64
import os

_FULL_RES_PX_PER_CM = 236.2  # 600 dpi


@vision_node(
    type_id='bpa_image_loader',
    label='BPA Image Loader',
    category='forensics',
    icon='Image',
    description="Loads a BPA bloodstain JPG (600 dpi). Downscales for processing — full res is ~32k×26k px. px_per_cm output adjusts to chosen scale.",
    inputs=[
        {'id': 'image_path', 'color': 'string', 'label': 'Image Path'},
    ],
    outputs=[
        {'id': 'main',       'color': 'image',  'label': 'Image'},
        {'id': 'width',      'color': 'scalar', 'label': 'Width (px)'},
        {'id': 'height',     'color': 'scalar', 'label': 'Height (px)'},
        {'id': 'px_per_cm',  'color': 'scalar', 'label': 'px/cm'},
        {'id': 'width_cm',   'color': 'scalar', 'label': 'Width (cm)'},
        {'id': 'height_cm',  'color': 'scalar', 'label': 'Height (cm)'},
    ],
    params=[
        {'id': 'load_scale', 'label': 'Load Scale', 'type': 'float',
         'default': 0.1, 'min': 0.01, 'max': 1.0},
        {'id': 'path_override', 'label': 'Path Override', 'type': 'string', 'default': ''},
    ],
    colorable=True,
)
class BPAImageLoaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key = None
        self._cache_img = None   # full-res BGR
        self._cache_hw  = (0, 0)

    def _null(self):
        return {'main': None, 'width': 0, 'height': 0,
                'px_per_cm': 0.0, 'width_cm': 0.0, 'height_cm': 0.0}

    def process(self, inputs, params):
        path = params.get('path_override', '').strip() or (inputs.get('image_path') or '')
        if not path:
            return self._null()

        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path):
            send_notification(f'BPA Loader: file not found — {path}', level='error', notif_id='bpa_loader')
            return self._null()

        if path != self._cache_key:
            send_notification(f'BPA Loader: loading {os.path.basename(path)}…', progress=0.1, notif_id='bpa_loader')
            img = cv2.imread(path)
            if img is None:
                send_notification(f'BPA Loader: cv2.imread failed — {path}', level='error', notif_id='bpa_loader')
                return self._null()
            self._cache_img = img
            self._cache_hw  = img.shape[:2]
            self._cache_key = path
            h, w = self._cache_hw
            send_notification(
                f'BPA Loader: {os.path.basename(path)} — {w}×{h}px ({w/_FULL_RES_PX_PER_CM:.1f}×{h/_FULL_RES_PX_PER_CM:.1f} cm)',
                progress=1.0, notif_id='bpa_loader'
            )

        scale = float(params.get('load_scale', 0.1))
        scale = max(0.01, min(1.0, scale))

        full_h, full_w = self._cache_hw
        new_w = max(1, int(full_w * scale))
        new_h = max(1, int(full_h * scale))

        if scale < 1.0:
            img_out = cv2.resize(self._cache_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            img_out = self._cache_img.copy()

        px_per_cm = _FULL_RES_PX_PER_CM * scale
        width_cm  = full_w / _FULL_RES_PX_PER_CM
        height_cm = full_h / _FULL_RES_PX_PER_CM

        out = {
            'main':      img_out,
            'width':     new_w,
            'height':    new_h,
            'px_per_cm': round(px_per_cm, 4),
            'width_cm':  round(width_cm, 2),
            'height_cm': round(height_cm, 2),
        }

        try:
            sc = 120 / new_h
            pw = max(1, int(new_w * sc))
            prev = cv2.resize(img_out, (pw, 120))
            _, buf = cv2.imencode('.jpg', prev, [cv2.IMWRITE_JPEG_QUALITY, 50])
            out['_thumb'] = base64.b64encode(buf).decode('utf-8')
        except Exception:
            pass

        return out
