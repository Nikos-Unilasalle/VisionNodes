"""
Segmentation Loader — load a saved .seg.json (from AI Segmenter / SAM) and
replay it as a drop-in replacement for the segmenter.

Outputs the same ports as the SAM node (boxes, contours, mask, centroids,
areas, count, overlay), so a one-shot 20-minute segmentation can be saved
once and reused instantly without rerunning SAM.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import json
import os

_NOTIF_ID = 'seg_loader'


@vision_node(
    type_id='seg_loader',
    label='Segmentation Loader',
    category='segmentation',
    icon='Database',
    description=(
        "Load a saved .seg.json file (boxes + precise contours) produced by the "
        "AI Segmenter (SAM) and replay it. Drop-in replacement for SAM once the "
        "segmentation work is done — feeds DINOv2 Classifier, Export Crops, etc. "
        "without rerunning the model."
    ),
    inputs=[
        {'id': 'image', 'color': 'image', 'label': 'Image (for overlay)'},
    ],
    outputs=[
        {'id': 'main',      'color': 'image',  'label': 'Overlay'},
        {'id': 'mask',      'color': 'mask',   'label': 'Combined Mask'},
        {'id': 'count',     'color': 'scalar', 'label': 'Object Count'},
        {'id': 'boxes',     'color': 'list',   'label': 'Boxes List (YOLO)'},
        {'id': 'areas',     'color': 'list',   'label': 'Areas (px²)'},
        {'id': 'centroids', 'color': 'list',   'label': 'Centroids'},
        {'id': 'contours',  'color': 'list',   'label': 'Contours List'},
    ],
    params=[
        {'id': 'load_path', 'label': 'File (.seg.json)', 'type': 'file_open',
         'default': '~/VNStudio/exports/segmentation.seg.json',
         'filters': [{'name': 'Segmentation', 'extensions': ['json']}]},
        {'id': 'reload', 'label': 'Reload', 'type': 'trigger', 'default': False},
        {'id': 'overlay_opacity', 'label': 'Overlay Opacity (%)', 'type': 'number',
         'default': 50, 'min': 0, 'max': 100, 'step': 5},
    ],
    colorable=True,
)
class SegLoaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._doc = None
        self._doc_key = None  # (path, mtime)

    def _status(self, image, text, color=(255, 200, 50)):
        if image is None:
            canvas = np.zeros((120, 480, 3), dtype=np.uint8)
        else:
            canvas = image.copy()
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 36), (20, 20, 20), -1)
        cv2.putText(canvas, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, color, 1, cv2.LINE_AA)
        return canvas

    def _empty(self, image, msg=None, color=(255, 200, 50)):
        main = self._status(image, msg, color) if msg else image
        return {'main': main, 'mask': None, 'count': 0,
                'boxes': [], 'areas': [], 'centroids': [], 'contours': []}

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
            send_notification(f'SegLoader: parse error {str(e)[:80]}',
                              level='error', notif_id=_NOTIF_ID)
            return None
        self._doc = doc
        self._doc_key = key
        return doc

    def process(self, inputs, params):
        image = inputs.get('image')
        path = params.get('load_path', '')

        # Trigger forces a cache bust (re-read even if mtime unchanged)
        if bool(params.get('reload', False)):
            self._doc_key = None

        doc = self._load_doc(path)
        if doc is None:
            return self._empty(image, f'No file: {os.path.basename((path or "").strip()) or "set path"}',
                               color=(60, 60, 255))

        objects = doc.get('objects', []) or []
        size = doc.get('image_size', {}) or {}
        fw = int(size.get('w', 0)) or (image.shape[1] if image is not None else 0)
        fh = int(size.get('h', 0)) or (image.shape[0] if image is not None else 0)
        if fw <= 0 or fh <= 0:
            return self._empty(image, 'Invalid image_size in file', color=(60, 60, 255))

        boxes, areas, centroids, all_contours = [], [], [], []
        combined_mask = np.zeros((fh, fw), dtype=np.uint8)
        label_map = np.zeros((fh, fw, 3), dtype=np.uint8)

        for i, obj in enumerate(objects):
            box = obj.get('box')
            if isinstance(box, dict):
                boxes.append(box)
            contour = obj.get('contour') or []
            all_contours.append(contour)
            areas.append(obj.get('area'))
            centroids.append(obj.get('centroid'))

            if contour and len(contour) >= 3:
                pts = np.array(contour, dtype=np.int32).reshape(-1, 1, 2)
                color = [
                    int((i * 67  + 40) % 200 + 55),
                    int((i * 137 + 80) % 200 + 55),
                    int((i * 197 + 120) % 200 + 55),
                ]
                cv2.fillPoly(label_map, [pts], color)
                cv2.fillPoly(combined_mask, [pts], 255)

        # Build overlay on the input image (or the rebuilt label map if no image)
        if image is not None and image.shape[0] == fh and image.shape[1] == fw:
            overlay = image.copy()
            opacity = float(params.get('overlay_opacity', 50)) / 100.0
            blended = cv2.addWeighted(overlay, 1.0 - opacity, label_map, opacity, 0)
            region = label_map.any(axis=2)
            overlay[region] = blended[region]
            cnts, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, cnts, -1, (255, 255, 255), 1)
        else:
            overlay = label_map

        return {
            'main': overlay,
            'mask': combined_mask,
            'count': float(len(objects)),
            'boxes': boxes,
            'areas': areas,
            'centroids': centroids,
            'contours': all_contours,
        }
