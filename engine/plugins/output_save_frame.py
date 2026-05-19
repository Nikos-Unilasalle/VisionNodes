import cv2
import os
import time
from registry import vision_node, NodeProcessor

_FORMATS = {0: '.png', 1: '.jpg', 2: '.tiff', 3: '.bmp'}

@vision_node(
    type_id='output_save_frame',
    label='Save Frame',
    category='output',
    icon='ImageDown',
    description="Saves an image to disk on trigger. Supports PNG, JPG, TIFF, BMP. Auto-timestamp option.",
    inputs=[
        {'id': 'image',   'color': 'image'},
        {'id': 'trigger', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'saved_path', 'color': 'string'},
    ],
    params=[
        {'id': 'path',           'label': 'Folder',         'type': 'string',  'default': 'exports'},
        {'id': 'filename',       'label': 'Filename',        'type': 'string',  'default': 'frame'},
        {'id': 'format',         'label': 'Format',          'type': 'enum',    'options': ['PNG', 'JPG', 'TIFF', 'BMP'], 'default': 0},
        {'id': 'auto_timestamp', 'label': 'Auto Timestamp',  'type': 'bool',    'default': True},
        {'id': 'record',         'label': 'Record (every frame)', 'type': 'toggle', 'default': False},
        {'id': 'quality',        'label': 'JPG Quality',     'type': 'int',     'default': 95, 'min': 1, 'max': 100},
    ]
)
class SaveFrameNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._prev_trigger = 0.0
        self._last_path: str | None = None

    def _build_path(self, params) -> str:
        folder    = params.get('path', 'exports')
        name      = params.get('filename', 'frame')
        fmt_idx   = int(params.get('format', 0))
        auto_ts   = bool(params.get('auto_timestamp', True))
        ext       = _FORMATS.get(fmt_idx, '.png')
        ts        = f"_{int(time.time() * 1000)}" if auto_ts else ""
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{name}{ts}{ext}")

    def _write(self, image, path: str, params) -> bool:
        fmt_idx = int(params.get('format', 0))
        ext     = _FORMATS.get(fmt_idx, '.png')
        try:
            if ext == '.jpg':
                quality = int(params.get('quality', 95))
                ok = cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            else:
                ok = cv2.imwrite(path, image)
            if ok:
                print(f"[SaveFrame] → {path}")
            return ok
        except Exception as e:
            print(f"[SaveFrame] write error: {e}")
            return False

    def process(self, inputs, params):
        image   = inputs.get('image')
        trigger = inputs.get('trigger', 0)
        record  = bool(params.get('record', False))

        try:
            trigger_f = float(trigger) if trigger is not None else 0.0
        except (TypeError, ValueError):
            trigger_f = 0.0

        saved = None

        # Rising edge trigger
        if trigger_f > 0.5 and self._prev_trigger <= 0.5:
            if image is not None:
                path = self._build_path(params)
                if self._write(image, path, params):
                    saved = path
                    self._last_path = path

        self._prev_trigger = trigger_f

        # Continuous record mode
        if record and image is not None:
            path = self._build_path(params)
            if self._write(image, path, params):
                saved = path
                self._last_path = path

        return {'saved_path': saved or self._last_path or ''}
