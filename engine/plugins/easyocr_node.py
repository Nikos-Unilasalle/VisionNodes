import cv2
import numpy as np
import threading
from registry import vision_node, NodeProcessor, send_notification

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

_LANG_CODES = [['en'], ['fr'], ['en', 'fr'], ['de'], ['es'], ['ch_sim', 'en']]
_LANG_LABELS = ['English', 'French', 'Eng + Fra', 'German', 'Spanish', 'Chinese + Eng']
_NOTIF_ID = 'easyocr_load'


def _canonical_corners(pts):
    """Sort 4 absolute-pixel corners to [TL, TR, BR, BL] via sum/diff."""
    a = np.array(pts, dtype=np.float32)
    s = a.sum(axis=1); d = np.diff(a, axis=1).ravel()
    return [a[np.argmin(s)].tolist(), a[np.argmin(d)].tolist(),
            a[np.argmax(s)].tolist(), a[np.argmax(d)].tolist()]


@vision_node(
    type_id='ocr_easyocr',
    label='OCR (EasyOCR)',
    category='ocr',
    icon='ScanText',
    description='End-to-end text detection + recognition with EasyOCR. Handles rotated, curved and multi-language text in one pass.',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main',         'color': 'image',  'label': 'Annotated'},
        {'id': 'text_regions', 'color': 'list',   'label': 'Regions'},
        {'id': 'texts',        'color': 'list',   'label': 'Text List'},
    ],
    params=[
        {'id': 'lang',           'label': 'Language',    'type': 'enum',
         'options': _LANG_LABELS, 'default': 0},
        {'id': 'min_confidence', 'label': 'Min Conf',    'type': 'scalar',
         'min': 0.0, 'max': 1.0, 'step': 0.01, 'default': 0.4},
        {'id': 'gpu',            'label': 'GPU',         'type': 'boolean', 'default': False},
        {'id': 'draw_text',      'label': 'Draw Text',   'type': 'boolean', 'default': True},
    ]
)
class EasyOcrNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.reader = None
        self._loading = False
        self._loaded_lang_idx = -1
        self._loaded_gpu = None

    def _load_reader(self, lang_idx, gpu):
        self._loading = True
        langs = _LANG_CODES[lang_idx]
        send_notification(f'EasyOCR: loading {_LANG_LABELS[lang_idx]}…',
                          progress=0.1, notif_id=_NOTIF_ID)
        try:
            self.reader = easyocr.Reader(langs, gpu=gpu, verbose=False)
            self._loaded_lang_idx = lang_idx
            self._loaded_gpu = gpu
            send_notification(f'EasyOCR: ready ({_LANG_LABELS[lang_idx]})',
                              progress=1.0, notif_id=_NOTIF_ID)
        except Exception as e:
            send_notification(f'EasyOCR load error: {e}',
                              level='error', notif_id=_NOTIF_ID)
            self.reader = None
        self._loading = False

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'text_regions': [], 'texts': []}

        if not EASYOCR_AVAILABLE:
            return {'main': img, 'text_regions': [],
                    'texts': ['pip install easyocr']}

        lang_idx = int(params.get('lang', 0))
        gpu      = bool(params.get('gpu', False))
        min_conf = float(params.get('min_confidence', 0.4))
        do_text  = bool(params.get('draw_text', True))

        # Reload if language or gpu changed
        need_load = (self.reader is None or
                     self._loaded_lang_idx != lang_idx or
                     self._loaded_gpu != gpu)

        if need_load and not self._loading:
            threading.Thread(target=self._load_reader,
                             args=(lang_idx, gpu), daemon=True).start()

        if self.reader is None:
            return {'main': img, 'text_regions': [], 'texts': []}

        H, W = img.shape[:2]
        out = img.copy()

        try:
            raw = self.reader.readtext(img)
        except Exception as e:
            print(f'[EasyOCR] readtext error: {e}')
            return {'main': img, 'text_regions': [], 'texts': []}

        regions, texts = [], []
        for (box, text, conf) in raw:
            if conf < min_conf:
                continue

            # box: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] absolute pixels
            ordered = _canonical_corners(box)  # TL, TR, BR, BL

            xs = [p[0] for p in ordered]; ys = [p[1] for p in ordered]
            x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
            x1, y1 = min(W, int(max(xs))), min(H, int(max(ys)))
            norm_pts = [[float(np.clip(p[0]/W, 0, 1)),
                         float(np.clip(p[1]/H, 0, 1))] for p in ordered]

            regions.append({
                'xmin': x0/W, 'ymin': y0/H,
                'width': (x1-x0)/W, 'height': (y1-y0)/H,
                'label': text, 'confidence': float(conf),
                '_type': 'graphics', 'shape': 'polygon',
                'pts': norm_pts, 'color': '#00ff00', 'relative': True,
            })
            texts.append(text)

            # Draw rotated box
            poly = np.array([[int(p[0]), int(p[1])] for p in ordered], np.int32)
            cv2.polylines(out, [poly.reshape(-1, 1, 2)], True, (0, 255, 0), 2)
            if do_text:
                cv2.putText(out, f'{text} {conf:.2f}', (x0, max(0, y0-6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        return {'main': out, 'text_regions': regions, 'texts': texts}
