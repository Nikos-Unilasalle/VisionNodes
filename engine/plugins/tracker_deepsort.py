"""
DeepSORT Tracker — Plugin VNStudio
Ref: Wojke et al. 2017 — https://arxiv.org/abs/1703.07402

Utilise la bibliothèque 'deep-sort-realtime' (pip install deep-sort-realtime).
Combining Kalman filtering + a CNN appearance descriptor to dramatically
reduce identity switches compared to plain SORT.
"""
from __main__ import vision_node, NodeProcessor
import numpy as np

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False
    print("[DeepSORT] 'deep-sort-realtime' not installed. Run: pip install deep-sort-realtime")

# Embedder options exposed to the user
_EMBEDDER_NAMES = {
    0: 'mobilenet',   # Léger, rapide
    1: 'clip_ViT-B/16',   # Plus précis, plus lourd
    2: 'torchreid',   # Re-ID spécialisé
}

@vision_node(
    type_id='tracker_deepsort',
    label='DeepSORT Tracker',
    category='track',
    icon='ScanSearch',
    description="Suivi multi-objets avec DeepSORT : Kalman Filter + embeddings CNN pour une ré-identification robuste et moins de changements d'ID.",
    inputs=[
        {'id': 'detections', 'color': 'list'},
        {'id': 'image',      'color': 'image'}
    ],
    outputs=[
        {'id': 'main',    'color': 'image'},
        {'id': 'tracks',  'color': 'list'},
        {'id': 'track_0', 'color': 'dict'},
        {'id': 'track_1', 'color': 'dict'},
        {'id': 'track_2', 'color': 'dict'},
        {'id': 'track_3', 'color': 'dict'},
        {'id': 'track_4', 'color': 'dict'},
        {'id': 'count',   'color': 'scalar'},
    ],
    params=[
        {'id': 'max_age',         'label': 'Max Age (frames)',    'min': 1,  'max': 60, 'step': 1, 'default': 5},
        {'id': 'n_init',          'label': 'Min Hits (n_init)',  'min': 1,  'max': 10, 'step': 1, 'default': 2},
        {'id': 'embedder',        'label': 'Embedder (0=mobilenet 1=clip 2=torchreid)', 'min': 0, 'max': 2, 'step': 1, 'default': 0},
        {'id': 'max_cosine_dist', 'label': 'Max Cosine Dist (%)', 'min': 1,  'max': 99, 'step': 1, 'default': 40},
    ]
)
class DeepSORTTrackerNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._tracker: 'DeepSort | None' = None
        self._last_params: dict = {}

    def _get_tracker(self, params: dict) -> 'DeepSort':
        max_age         = int(params.get('max_age', 5))
        n_init          = int(params.get('n_init', 2))
        embedder_idx    = int(params.get('embedder', 0))
        max_cosine_dist = float(params.get('max_cosine_dist', 40)) / 100.0
        embedder_name   = _EMBEDDER_NAMES.get(embedder_idx, 'mobilenet')

        need_reset = (
            self._tracker is None or
            self._last_params.get('max_age')         != max_age         or
            self._last_params.get('n_init')          != n_init          or
            self._last_params.get('embedder')        != embedder_idx    or
            self._last_params.get('max_cosine_dist') != max_cosine_dist
        )
        if need_reset:
            print(f"[DeepSORT] Creating tracker: embedder={embedder_name}, max_age={max_age}, n_init={n_init}")
            try:
                self._tracker = DeepSort(
                    max_age=max_age,
                    n_init=n_init,
                    max_cosine_distance=max_cosine_dist,
                    embedder=embedder_name,
                    half=False,         # Full precision pour compatibilité CPU
                    bgr=True,           # OpenCV frames sont BGR
                )
            except Exception as e:
                print(f"[DeepSORT] Tracker init failed: {e}")
                self._tracker = None
            self._last_params = {
                'max_age': max_age, 'n_init': n_init,
                'embedder': embedder_idx, 'max_cosine_dist': max_cosine_dist
            }

        return self._tracker

    def process(self, inputs: dict, params: dict) -> dict:
        image      = inputs.get('image')
        detections = inputs.get('detections', [])

        empty_out = {
            'main': image, 'tracks': [], 'count': 0.0,
            **{f'track_{i}': None for i in range(5)}
        }

        if not DEEPSORT_AVAILABLE:
            return empty_out

        if image is None:
            return empty_out

        tracker = self._get_tracker(params)
        if tracker is None:
            return empty_out

        h, w = image.shape[:2]

        # Convertir les détections au format attendu par deep-sort-realtime :
        # list of ([left, top, width, height], confidence, class_name)
        ds_dets = []
        for det in (detections or []):
            if not isinstance(det, dict):
                continue
            xmin  = det.get('xmin', 0)
            ymin  = det.get('ymin', 0)
            bw    = det.get('width', 0)
            bh    = det.get('height', 0)
            label = det.get('label', '')
            score = float(det.get('score', 0.0))
            # Coordonnées absolues pixels
            left  = int(xmin * w)
            top   = int(ymin * h)
            pw    = int(bw * w)
            ph    = int(bh * h)
            if pw > 0 and ph > 0:
                ds_dets.append(([left, top, pw, ph], score, label))

        try:
            raw_tracks = tracker.update_tracks(ds_dets, frame=image)
        except Exception as e:
            print(f"[DeepSORT] update_tracks error: {e}")
            return empty_out

        tracks_out = []
        for trk in raw_tracks:
            if not trk.is_confirmed():
                continue
            ltrb = trk.to_ltrb()  # [left, top, right, bottom]
            x1, y1, x2, y2 = ltrb[0] / w, ltrb[1] / h, ltrb[2] / w, ltrb[3] / h
            x1, y1 = max(0.0, x1), max(0.0, y1)
            x2, y2 = min(1.0, x2), min(1.0, y2)
            tid   = trk.track_id
            label = trk.get_det_class() or ''
            score = float(trk.get_det_conf() or 0.0)

            track_dict = {
                'track_id': tid,
                'label':    f"#{tid} {label}",
                'score':    score,
                'xmin':     x1, 'ymin': y1,
                'width':    x2 - x1, 'height': y2 - y1,
                '_type':    'graphics', 'shape': 'rect',
                'pts':      [[x1, y1], [x2, y2]],
                'thickness': 2,
                'r': int(abs(np.sin(tid * 0.9)) * 255),
                'g': int(abs(np.sin(tid * 0.9 + 2.1)) * 255),
                'b': int(abs(np.sin(tid * 0.9 + 4.2)) * 255),
            }
            tracks_out.append(track_dict)

        out = {
            'main':   image,
            'tracks': tracks_out,
            'count':  float(len(tracks_out)),
        }
        for i in range(5):
            out[f'track_{i}'] = tracks_out[i] if i < len(tracks_out) else None

        return out
