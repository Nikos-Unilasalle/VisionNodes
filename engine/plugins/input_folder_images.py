"""Folder Images — iterates a directory of images one frame per tick/trigger, like Movie File but for stills.

The Start button self-drives the whole graph through every image (batch processing): a background
ticker wakes the engine repeatedly until the last image, so downstream nodes run once per image.
"""
import cv2
import numpy as np
import os
import glob
import time
import threading
from registry import vision_node, NodeProcessor, send_notification, _notification_queue

_NOTIF = 'folder_images'
_NODE_TYPE = 'input_folder_images'
_TICK_INTERVAL = 0.05  # seconds between engine wake-ups while running


def _load_image_robust(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        try:
            from PIL import Image as _PILImage
            img = np.array(_PILImage.open(path).convert('RGB'))[:, :, ::-1]
        except Exception:
            return None
    if img is not None and len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


@vision_node(
    type_id='input_folder_images',
    label='Folder Images',
    category='input',
    icon='FolderOpen',
    description="Iterates every image in a folder, one per tick — for batch processing hundreds/thousands of "
                "images through the same pipeline. Press Start to run the whole batch automatically.",
    inputs=[],
    outputs=[
        {'id': 'main',     'color': 'image',   'label': 'Image'},
        {'id': 'filename', 'color': 'string',  'label': 'Filename'},
        {'id': 'index',    'color': 'scalar',  'label': 'Index'},
        {'id': 'total',    'color': 'scalar',  'label': 'Total'},
        {'id': 'done',     'color': 'boolean', 'label': 'Done (last image)'},
    ],
    params=[
        {'id': 'folder',   'label': 'Folder Path', 'type': 'string', 'default': 'exports'},
        {'id': 'pattern',  'label': 'Extensions',  'type': 'string', 'default': 'png,jpg,jpeg,bmp,tif,tiff'},
        {'id': '_sec_run',   'label': 'Batch Run',  'type': 'section'},
        {'id': 'start',    'label': 'Start',       'type': 'trigger', 'default': 0},
        {'id': 'stop',     'label': 'Stop',        'type': 'trigger', 'default': 0},
        {'id': 'loop',     'label': 'Loop at End',  'type': 'bool', 'default': False},
        {'id': '_sec_manual', 'label': 'Manual Control', 'type': 'section'},
        {'id': 'index',    'label': 'Index',        'type': 'int',  'default': 0, 'min': 0},
        {'id': 'next',     'label': 'Next Image',   'type': 'trigger', 'default': 0},
        {'id': 'reset',    'label': 'Reset to First', 'type': 'trigger', 'default': 0},
    ]
)
class FolderImagesNode(NodeProcessor):
    def __init__(self, engine=None):
        self.files = []
        self.cached_key = None
        self.cur_index = 0
        self.last_next = 0
        self.last_reset = 0
        self.last_start = 0
        self.last_stop = 0
        self.last_index_param = 0
        self.running = False
        self._ticker = None

    def _refresh_files(self, folder, pattern):
        key = (folder, pattern)
        if key == self.cached_key:
            return
        self.cached_key = key
        exts = [e.strip().lstrip('.').lower() for e in pattern.split(',') if e.strip()]
        found = set()
        for ext in exts:
            found.update(glob.glob(os.path.join(folder, f'*.{ext}')))
            found.update(glob.glob(os.path.join(folder, f'*.{ext.upper()}')))
        self.files = sorted(found)

    def _start_ticker(self):
        if self._ticker is not None and self._ticker.is_alive():
            return
        self._ticker = threading.Thread(target=self._run_ticker, daemon=True)
        self._ticker.start()

    def _run_ticker(self):
        # Repeatedly wake the (static-graph) engine and bust our cache so process() runs fresh
        # for each image. Robust against the engine's end-of-tick run-event clear because it
        # keeps firing on a fixed cadence until self.running flips off.
        while self.running:
            time.sleep(_TICK_INTERVAL)
            _notification_queue.put_nowait({'_wake_engine': True, '_node_type': _NODE_TYPE})

    def process(self, inputs, params):
        folder  = os.path.abspath(os.path.expanduser(str(params.get('folder', ''))))
        pattern = str(params.get('pattern', 'png,jpg,jpeg,bmp,tif,tiff'))
        self._refresh_files(folder, pattern)
        total = len(self.files)
        if total == 0:
            self.running = False
            return {'main': None, 'filename': '', 'index': 0, 'total': 0, 'done': True}

        loop = bool(params.get('loop', False))

        # ── Batch run triggers ────────────────────────────────────────────────
        start_trig = int(params.get('start', 0))
        stop_trig  = int(params.get('stop', 0))
        if start_trig and not self.last_start:
            self.cur_index = 0
            self.running = True
            self._start_ticker()
            send_notification(f"Folder Images: running batch of {total}", level='info', notif_id=_NOTIF)
        if stop_trig and not self.last_stop:
            self.running = False
        self.last_start, self.last_stop = start_trig, stop_trig

        # ── Manual controls ───────────────────────────────────────────────────
        next_trig  = int(params.get('next', 0))
        reset_trig = int(params.get('reset', 0))
        if reset_trig and not self.last_reset:
            self.cur_index = 0
        elif next_trig and not self.last_next:
            self.cur_index += 1
        self.last_next, self.last_reset = next_trig, reset_trig

        # Manual scrub: only jump when the 'index' param itself changed (a slider drag),
        # never re-sync on every idle tick — that would stomp auto-advance back to 0.
        index_param = int(params.get('index', self.cur_index))
        if index_param != self.last_index_param:
            self.cur_index = index_param
            self.last_index_param = index_param

        if self.cur_index >= total:
            self.cur_index = 0 if loop else total - 1
        self.cur_index = max(0, self.cur_index)

        served_index = self.cur_index
        path = self.files[served_index]
        img = _load_image_robust(path)
        filename = os.path.splitext(os.path.basename(path))[0]
        done = served_index >= total - 1

        # ── Advance for the next tick while running ────────────────────────────
        if self.running:
            if not done:
                self.cur_index += 1
            elif loop:
                self.cur_index = 0
            else:
                self.running = False  # batch finished — ticker exits, last image stays served
                send_notification(f"Folder Images: batch done ({total} images)", progress=1.0, notif_id=_NOTIF)

        return {'main': img, 'filename': filename, 'index': served_index, 'total': total, 'done': done}
