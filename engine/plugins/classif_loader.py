"""
Classification Loader — load a saved .cls.json (from DINOv2 Classifier) and
replay it as a drop-in replacement for the classifier.

Outputs the same ports as the DINOv2 node (labels_list, classes, summary,
count, overlay), so a one-shot classification can be saved once and reused
instantly without rerunning the heavy model. Feeds Stone Calepinage, reports,
CSV export, etc.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import json
import os

_NOTIF_ID = 'classif_loader'


@vision_node(
    type_id='classif_loader',
    label='Classification Loader',
    category='analysis',
    icon='Database',
    description=(
        "Load a saved .cls.json file produced by the DINOv2 Classifier and replay it. "
        "Drop-in replacement for DINOv2 once classification is done — feeds Stone "
        "Calepinage, reports, CSV export, etc. without rerunning the model."
    ),
    inputs=[
        {'id': 'image', 'color': 'image', 'label': 'Image (for overlay)'},
    ],
    outputs=[
        {'id': 'main',        'color': 'image',  'label': 'Overlay'},
        {'id': 'labels_list', 'color': 'list',   'label': 'Labels List'},
        {'id': 'classes',     'color': 'dict',   'label': 'Classes {type:[ids]}'},
        {'id': 'summary',     'color': 'dict',   'label': 'Summary (per-class)'},
        {'id': 'count',       'color': 'scalar', 'label': 'Count'},
    ],
    params=[
        {'id': 'load_path', 'label': 'File (.cls.json)', 'type': 'file_open',
         'default': '~/VNStudio/exports/classification.cls.json',
         'filters': [{'name': 'Classification', 'extensions': ['json']}]},
        {'id': 'reload', 'label': 'Reload', 'type': 'trigger', 'default': False},
        {'id': 'label_mode', 'label': 'Label Mode', 'type': 'enum',
         'options': ['Label + Score', 'Label', 'None'], 'default': 0},
    ],
    colorable=True,
)
class ClassifLoaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._doc = None
        self._doc_key = None  # (path, mtime)

    def _status(self, image, text, color=(255, 200, 50)):
        canvas = image.copy() if image is not None else np.zeros((120, 480, 3), np.uint8)
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(canvas, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, color, 1, cv2.LINE_AA)
        return canvas

    def _empty(self, image, msg=None, color=(255, 200, 50)):
        main = self._status(image, msg, color) if msg else image
        return {'main': main, 'labels_list': [], 'classes': {}, 'summary': {}, 'count': 0.0}

    def _load_doc(self, path):
        """Load + cache the JSON doc keyed on (path, mtime). Returns doc or None."""
        path = os.path.expanduser((path or '').strip())
        if not path or not os.path.exists(path):
            return None
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        key = (path, mtime)
        if key == self._doc_key and self._doc is not None:
            return self._doc
        try:
            with open(path, 'r') as f:
                doc = json.load(f)
        except Exception as e:
            send_notification(f'ClassifLoader: parse error {str(e)[:80]}',
                              level='error', notif_id=_NOTIF_ID)
            return None
        self._doc = doc
        self._doc_key = key
        return doc

    def process(self, inputs, params):
        image = inputs.get('image')
        path = params.get('load_path', '')

        if bool(params.get('reload', False)):
            self._doc_key = None

        doc = self._load_doc(path)
        if doc is None:
            shown = os.path.basename(os.path.expanduser((path or '').strip())) or 'set path'
            return self._empty(image, f'No file: {shown}', color=(60, 60, 255))

        labels_list = doc.get('labels_list', []) or []
        classes     = doc.get('classes', {}) or {}
        summary     = doc.get('summary', {}) or {}
        count       = float(doc.get('count', len(labels_list)) or 0)
        label_mode  = int(params.get('label_mode', 0))

        # Rebuild overlay from stored boxes + labels (normalized YOLO dicts)
        overlay = image.copy() if image is not None else None
        if overlay is not None:
            h, w = overlay.shape[:2]
            for i, item in enumerate(labels_list):
                box = item.get('box') if isinstance(item, dict) else None
                if not isinstance(box, dict):
                    continue
                x1 = int(box.get('xmin', 0.0) * w)
                y1 = int(box.get('ymin', 0.0) * h)
                x2 = int((box.get('xmin', 0.0) + box.get('width', 0.0)) * w)
                y2 = int((box.get('ymin', 0.0) + box.get('height', 0.0)) * h)
                color = (
                    int((i * 67  + 40) % 200 + 55),
                    int((i * 137 + 80) % 200 + 55),
                    int((i * 197 + 120) % 200 + 55),
                )
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                label = str(item.get('label', ''))
                score = float(item.get('score', 0.0))
                txt = None
                if label_mode == 0:
                    txt = f'{label} {score:.2f}'
                elif label_mode == 1:
                    txt = label
                if txt:
                    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    bx = x1 + 2
                    by = y1 - 4 if y1 > 14 else y1 + th + 4
                    cv2.rectangle(overlay, (bx - 2, by - th - 4), (bx + tw + 2, by + 2), color, -1)
                    cv2.putText(overlay, txt, (bx, by),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        return {
            'main':        overlay,
            'labels_list': labels_list,
            'classes':     classes,
            'summary':     summary,
            'count':       count,
        }
