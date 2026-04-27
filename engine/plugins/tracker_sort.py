"""
SORT (Simple Online and Realtime Tracking) — Plugin VNStudio
Ref: Bewley et al. 2016 — https://arxiv.org/abs/1602.00763

Implémentation auto-contenue : Kalman Filter (filterpy) + Hungarian (scipy).
Compatible avec les détections de YOLO et MediaPipe.
"""
from registry import vision_node, NodeProcessor
import numpy as np

# ── Dépendances optionnelles ──────────────────────────────────────────────────
try:
    from filterpy.kalman import KalmanFilter
    FILTERPY_OK = True
except ImportError:
    FILTERPY_OK = False

try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

SORT_AVAILABLE = FILTERPY_OK and SCIPY_OK

# ── Utilitaires IOU ───────────────────────────────────────────────────────────

def _iou_batch(bb_test: np.ndarray, bb_gt: np.ndarray) -> np.ndarray:
    """Calcule la matrice IOU entre deux ensembles de boîtes [x1,y1,x2,y2]."""
    bb_gt = np.expand_dims(bb_gt, 0)
    bb_test = np.expand_dims(bb_test, 1)

    xx1 = np.maximum(bb_test[..., 0], bb_gt[..., 0])
    yy1 = np.maximum(bb_test[..., 1], bb_gt[..., 1])
    xx2 = np.minimum(bb_test[..., 2], bb_gt[..., 2])
    yy2 = np.minimum(bb_test[..., 3], bb_gt[..., 3])

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    inter = w * h

    area_test = (bb_test[..., 2] - bb_test[..., 0]) * (bb_test[..., 3] - bb_test[..., 1])
    area_gt   = (bb_gt[..., 2]   - bb_gt[..., 0])   * (bb_gt[..., 3]   - bb_gt[..., 1])

    iou = inter / (area_test + area_gt - inter + 1e-9)
    return iou


def _bbox_to_z(bbox: np.ndarray) -> np.ndarray:
    """[x1,y1,x2,y2] → [cx, cy, s, r] (center, scale, aspect ratio)."""
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    cx = bbox[0] + w / 2.0
    cy = bbox[1] + h / 2.0
    s = w * h          # surface
    r = w / float(h) if h > 0 else 1.0
    return np.array([cx, cy, s, r]).reshape((4, 1))


def _z_to_bbox(z: np.ndarray, score: float = 0.0) -> np.ndarray:
    """[cx, cy, s, r] → [x1, y1, x2, y2, score].
    
    z peut avoir shape (7,1) (état Kalman) ou (7,) — on flatten pour éviter
    les arrays inhomogènes dans np.array([...]).
    """
    z = np.asarray(z).flatten()
    w = float(np.sqrt(np.abs(z[2] * z[3])))
    h = float(z[2]) / w if w > 0 else 0.0
    return np.array([
        float(z[0]) - w / 2.0,
        float(z[1]) - h / 2.0,
        float(z[0]) + w / 2.0,
        float(z[1]) + h / 2.0,
        float(score)
    ], dtype=float)

# ── Kalman Box Tracker ─────────────────────────────────────────────────────────

class KalmanBoxTracker:
    """Tracker individuel basé sur le modèle de mouvement à vitesse constante."""
    _count = 0

    def __init__(self, bbox: np.ndarray, label: str = '', score: float = 0.0):
        if not FILTERPY_OK:
            raise RuntimeError("filterpy not available")

        # Kalman filter : état = [cx, cy, s, r, vx, vy, vs]
        self.kf = KalmanFilter(dim_x=7, dim_z=4)

        # Matrice de transition (vitesse constante)
        self.kf.F = np.array([
            [1,0,0,0,1,0,0],
            [0,1,0,0,0,1,0],
            [0,0,1,0,0,0,1],
            [0,0,0,1,0,0,0],
            [0,0,0,0,1,0,0],
            [0,0,0,0,0,1,0],
            [0,0,0,0,0,0,1],
        ], dtype=float)

        # Matrice d'observation (on observe cx, cy, s, r directement)
        self.kf.H = np.array([
            [1,0,0,0,0,0,0],
            [0,1,0,0,0,0,0],
            [0,0,1,0,0,0,0],
            [0,0,0,1,0,0,0],
        ], dtype=float)

        # Bruit de mesure
        self.kf.R[2:, 2:] *= 10.0
        # Covariance initiale (vitesse inconnue → grande incertitude)
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        # Bruit de processus
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01

        self.kf.x[:4] = _bbox_to_z(bbox)

        self.time_since_update = 0
        self.id = KalmanBoxTracker._count
        KalmanBoxTracker._count += 1

        self.history: list[np.ndarray] = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0

        self.label = label
        self.score = score

    def update(self, bbox: np.ndarray, score: float = 0.0):
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.score = score
        self.kf.update(_bbox_to_z(bbox))

    def predict(self) -> np.ndarray:
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        self.history.append(_z_to_bbox(self.kf.x))
        return self.history[-1]

    def get_state(self) -> np.ndarray:
        return _z_to_bbox(self.kf.x)

# ── Algorithme SORT Principal ──────────────────────────────────────────────────

def _associate_detections(detections: np.ndarray, trackers: np.ndarray,
                           iou_threshold: float = 0.3):
    """Associe les détections aux trackers via la matrice IOU + algorithme hongrois."""
    if len(trackers) == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(len(detections)),
            np.empty((0,), dtype=int)
        )

    iou_matrix = _iou_batch(detections, trackers)

    if min(iou_matrix.shape) > 0:
        a = (iou_matrix > iou_threshold).astype(int)
        if a.sum(1).max() == 1 and a.sum(0).max() == 1:
            # Assignation greedy si pas d'ambiguïté
            matched_indices = np.stack(np.where(a), axis=1)
        else:
            # Algorithme hongrois complet
            row_ind, col_ind = linear_sum_assignment(-iou_matrix)
            matched_indices = np.stack([row_ind, col_ind], axis=1)
    else:
        matched_indices = np.empty(shape=(0, 2), dtype=int)

    unmatched_detections = [
        d for d in range(len(detections))
        if d not in matched_indices[:, 0]
    ]
    unmatched_trackers = [
        t for t in range(len(trackers))
        if t not in matched_indices[:, 1]
    ]

    # Filtrer les matches à faible IOU
    matches = []
    for m in matched_indices:
        if iou_matrix[m[0], m[1]] < iou_threshold:
            unmatched_detections.append(m[0])
            unmatched_trackers.append(m[1])
        else:
            matches.append(m.reshape(1, 2))

    matches = np.concatenate(matches, axis=0) if matches else np.empty((0, 2), dtype=int)

    return matches, np.array(unmatched_detections), np.array(unmatched_trackers)


class SORTTracker:
    """Tracker principal SORT — gère un pool de KalmanBoxTracker."""

    def __init__(self, max_age: int = 5, min_hits: int = 2, iou_threshold: float = 0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers: list[KalmanBoxTracker] = []
        self.frame_count = 0
        # Reset compteur global à chaque instanciation de node
        KalmanBoxTracker._count = 0

    def reset(self):
        self.trackers = []
        self.frame_count = 0
        KalmanBoxTracker._count = 0

    def update(self, dets: np.ndarray, labels: list[str], scores: list[float]):
        """
        dets : np.ndarray shape (N, 4) en [x1, y1, x2, y2] absolus ou normalisés
        Retourne : list de dict track
        """
        self.frame_count += 1

        # Prédire positions futures pour tous les trackers existants
        trks_pred = np.zeros((len(self.trackers), 5))
        to_del = []
        for t, trk in enumerate(self.trackers):
            pos = trk.predict()[:4]
            trks_pred[t] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(t)
        trks_pred = np.ma.compress_rows(np.ma.masked_invalid(trks_pred))
        for t in reversed(to_del):
            self.trackers.pop(t)

        # Associer détections ↔ trackers
        matched, unmatched_dets, unmatched_trks = _associate_detections(
            dets, trks_pred[:, :4], self.iou_threshold
        )

        # Mettre à jour les trackers matchés
        for d, t in matched:
            self.trackers[t].update(dets[d], scores[d] if scores else 0.0)

        # Créer de nouveaux trackers pour les détections non matchées
        for i in unmatched_dets:
            lbl = labels[i] if i < len(labels) else ''
            sc  = scores[i]  if i < len(scores)  else 0.0
            self.trackers.append(KalmanBoxTracker(dets[i], lbl, sc))

        # Collecter les tracks valides et nettoyer les anciens
        results = []
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            d = trk.get_state()[:4]
            i -= 1
            if trk.time_since_update <= 1 and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                results.append({
                    'track_id': trk.id,
                    'label': trk.label,
                    'score': float(trk.score),
                    'x1': float(d[0]), 'y1': float(d[1]),
                    'x2': float(d[2]), 'y2': float(d[3]),
                })
            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)

        return results

# ── Node VNStudio ─────────────────────────────────────────────────────────────

@vision_node(
    type_id='tracker_sort',
    label='SORT Tracker',
    category='track',
    icon='Crosshair',
    description="Suivi multi-objets en temps réel avec SORT (Kalman Filter + Hungarian). Connecter la sortie 'objects_list' d'un détecteur YOLO ou MediaPipe.",
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
        {'id': 'max_age',       'label': 'Max Age (frames)',   'min': 1,  'max': 60,  'step': 1, 'default': 5},
        {'id': 'min_hits',      'label': 'Min Hits',           'min': 1,  'max': 10,  'step': 1, 'default': 2},
        {'id': 'iou_threshold', 'label': 'IOU Threshold (%)',  'min': 5,  'max': 95,  'step': 1, 'default': 30},
    ]
)
class SORTTrackerNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._tracker: SORTTracker | None = None
        self._last_params: dict = {}

    def _get_tracker(self, params: dict) -> SORTTracker:
        max_age  = int(params.get('max_age', 5))
        min_hits = int(params.get('min_hits', 2))
        iou_thr  = float(params.get('iou_threshold', 30)) / 100.0

        need_reset = (
            self._tracker is None or
            self._last_params.get('max_age')       != max_age  or
            self._last_params.get('min_hits')      != min_hits or
            self._last_params.get('iou_threshold') != iou_thr
        )
        if need_reset:
            self._tracker = SORTTracker(max_age, min_hits, iou_thr)
            self._last_params = {'max_age': max_age, 'min_hits': min_hits, 'iou_threshold': iou_thr}

        return self._tracker

    def process(self, inputs: dict, params: dict) -> dict:
        image      = inputs.get('image')
        detections = inputs.get('detections', [])

        empty_out = {
            'main': image, 'tracks': [], 'count': 0.0,
            **{f'track_{i}': None for i in range(5)}
        }

        if not SORT_AVAILABLE:
            print("[SORT] filterpy and/or scipy not available. Run: pip install filterpy scipy")
            return empty_out

        if image is None or not detections:
            # Quand même mettre à jour le tracker (les objets peuvent disparaître)
            if self._tracker is not None:
                self._tracker.update(np.empty((0, 4)), [], [])
            return empty_out

        h, w = image.shape[:2]
        tracker = self._get_tracker(params)

        # Convertir les détections au format [x1,y1,x2,y2] absolu
        dets_arr, labels, scores = [], [], []
        for det in detections:
            if not isinstance(det, dict):
                continue
            xmin  = det.get('xmin', 0)
            ymin  = det.get('ymin', 0)
            bw    = det.get('width', 0)
            bh    = det.get('height', 0)
            dets_arr.append([xmin * w, ymin * h, (xmin + bw) * w, (ymin + bh) * h])
            labels.append(det.get('label', ''))
            scores.append(float(det.get('score', 0.0)))

        if not dets_arr:
            return empty_out

        raw_tracks = tracker.update(np.array(dets_arr, dtype=float), labels, scores)

        # Reconvertir en format normalisé du projet
        tracks_out = []
        for t in raw_tracks:
            x1, y1, x2, y2 = t['x1'] / w, t['y1'] / h, t['x2'] / w, t['y2'] / h
            x1, y1 = max(0.0, x1), max(0.0, y1)
            x2, y2 = min(1.0, x2), min(1.0, y2)
            track_dict = {
                'track_id': t['track_id'],
                'label': f"#{t['track_id']} {t['label']}",
                'score': t['score'],
                'xmin': x1, 'ymin': y1,
                'width': x2 - x1, 'height': y2 - y1,
                '_type': 'graphics', 'shape': 'rect',
                'pts': [[x1, y1], [x2, y2]],
                'thickness': 2,
                # Couleur dérivée de l'ID (HSV → BGR-like)
                'r': int(abs(np.sin(t['track_id'] * 0.9)) * 255),
                'g': int(abs(np.sin(t['track_id'] * 0.9 + 2.1)) * 255),
                'b': int(abs(np.sin(t['track_id'] * 0.9 + 4.2)) * 255),
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
