"""
Track Visualizer — Plugin VNStudio

Affiche les résultats de SORT ou DeepSORT avec :
- Boîtes des tracks colorées par ID
- Label + ID de tracking
- Trail de trajectoire (historique des centroïdes)
"""
from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np
from collections import defaultdict, deque


def _id_color(track_id: int) -> tuple[int, int, int]:
    """Génère une couleur HSV stable et distincte à partir d'un ID."""
    hue = int((track_id * 47) % 180)
    hsv = np.uint8([[[hue, 230, 230]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


@vision_node(
    type_id='tracker_visualize',
    label='Track Visualizer',
    category='draw',
    icon='Tv2',
    description="Rendu visuel des tracks SORT/DeepSORT : boîtes colorées par ID, labels et trails de trajectoire.",
    inputs=[
        {'id': 'image',  'color': 'image'},
        {'id': 'tracks', 'color': 'list'},
        {'id': 'point',  'color': 'dict'}
    ],
    outputs=[
        {'id': 'main',   'color': 'image'},
    ],
    params=[
        {'id': 'show_trail',   'label': 'Show Trail',            'type': 'bool', 'default': True},
        {'id': 'trail_length', 'label': 'Trail Length (frames)', 'min': 2, 'max': 120, 'step': 1, 'default': 30},
        {'id': 'show_id',      'label': 'Show Track ID',         'type': 'bool', 'default': True},
        {'id': 'show_label',   'label': 'Show Class Label',      'type': 'bool', 'default': True},
        {'id': 'thickness',    'label': 'Box Thickness',         'min': 1, 'max': 10, 'step': 1, 'default': 2},
        {'id': 'font_scale',   'label': 'Font Scale (%)',        'min': 1, 'max': 100, 'step': 1, 'default': 40},
        {'id': 'fill_alpha',   'label': 'Box Fill Alpha (%)',    'min': 0, 'max': 60, 'step': 1, 'default': 10},
        {'id': 'show_point',        'label': 'Show Point',          'type': 'bool', 'default': False},
        {'id': 'point_radius',      'label': 'Point Radius',        'min': 1, 'max': 40, 'step': 1, 'default': 6},
        {'id': 'point_use_id_color','label': 'Point: use ID color', 'type': 'bool', 'default': True},
        {'id': 'point_r',           'label': 'Point R',             'min': 0, 'max': 255, 'step': 1,   'default': 255},
        {'id': 'point_g',           'label': 'Point G',             'min': 0, 'max': 255, 'step': 1,   'default': 255},
        {'id': 'point_b',           'label': 'Point B',             'min': 0, 'max': 255, 'step': 1,   'default': 255},
    ]
)
class TrackVisualizerNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._trails: dict[int, deque] = defaultdict(lambda: deque(maxlen=120))
        self._active_ids: set[int] = set()
        self._point_trail: deque = deque(maxlen=120)

    def process(self, inputs: dict, params: dict) -> dict:
        image  = inputs.get('image')
        tracks = inputs.get('tracks', [])
        point  = inputs.get('point')

        if image is None:
            return {'main': None}

        res = image.copy()
        if len(res.shape) == 2:
            res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)

        h, w = res.shape[:2]

        show_trail   = bool(int(params.get('show_trail', 1)))
        trail_length = int(params.get('trail_length', 30))
        show_id      = bool(int(params.get('show_id', 1)))
        show_label   = bool(int(params.get('show_label', 1)))
        thickness    = int(params.get('thickness', 2))
        font_scale        = float(params.get('font_scale', 40)) / 100.0
        fill_alpha        = float(params.get('fill_alpha', 10)) / 100.0
        show_point        = bool(int(params.get('show_point', 0)))
        point_radius      = int(params.get('point_radius', 6))
        point_use_id_color= bool(int(params.get('point_use_id_color', 1)))
        point_r           = int(params.get('point_r', 255))
        point_g           = int(params.get('point_g', 255))
        point_b           = int(params.get('point_b', 255))

        if not isinstance(tracks, list) or len(tracks) == 0:
            return {'main': res}

        current_ids: set[int] = set()

        for trk in tracks:
            if not isinstance(trk, dict):
                continue

            tid   = trk.get('track_id', 0)
            xmin  = trk.get('xmin', 0.0)
            ymin  = trk.get('ymin', 0.0)
            bw    = trk.get('width', 0.0)
            bh    = trk.get('height', 0.0)
            label = trk.get('label', f'#{tid}')
            score = trk.get('score', 0.0)

            # Conversion en pixels
            x1 = int(xmin * w)
            y1 = int(ymin * h)
            x2 = int((xmin + bw) * w)
            y2 = int((ymin + bh) * h)

            color_bgr = _id_color(tid)
            current_ids.add(tid)

            # ── Fill semi-transparent ────────────────────────────────────────
            if fill_alpha > 0:
                overlay = res.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color_bgr, -1)
                cv2.addWeighted(overlay, fill_alpha, res, 1 - fill_alpha, 0, res)

            # ── Bounding box ─────────────────────────────────────────────────
            cv2.rectangle(res, (x1, y1), (x2, y2), color_bgr, thickness)

            # ── Trail ───────────────────────────────────────────────────────
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            trail_deq = self._trails[tid]
            trail_deq.append((cx, cy))

            if show_point:
                pt_color = color_bgr if point_use_id_color else (point_b, point_g, point_r)
                cv2.circle(res, (cx, cy), point_radius, pt_color, -1)

            if show_trail and len(trail_deq) > 1:
                pts = list(trail_deq)[-trail_length:]
                for k in range(1, len(pts)):
                    # Épaisseur et opacité décroissantes vers l'ancien
                    alpha = k / len(pts)
                    lw = max(1, int(thickness * alpha))
                    cv2.line(res, pts[k - 1], pts[k], color_bgr, lw)

            # ── Label ───────────────────────────────────────────────────────
            parts = []
            if show_id:
                parts.append(f'#{tid}')
            if show_label:
                raw_label = label.lstrip(f'#{tid}').strip()
                if raw_label:
                    parts.append(raw_label)
                if score > 0:
                    parts.append(f'{score:.0%}')

            if parts:
                text = ' '.join(parts)
                (tw, th), baseline = cv2.getTextSize(
                    text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
                )
                # Fond du label
                lx1 = x1
                ly1 = y1 - th - baseline - 4
                ly2 = y1
                cv2.rectangle(res, (lx1, max(0, ly1)), (lx1 + tw + 6, ly2), color_bgr, -1)
                cv2.putText(
                    res, text,
                    (lx1 + 3, max(th, y1 - baseline - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                    (255, 255, 255), 1, cv2.LINE_AA
                )

        # Purger les trails des IDs qui ont disparu depuis > 1 frame
        stale = self._active_ids - current_ids
        for sid in stale:
            if sid in self._trails:
                del self._trails[sid]
        self._active_ids = current_ids

        # ── Single point input ───────────────────────────────────────────────
        if isinstance(point, dict):
            pts = point.get('pts')
            relative = point.get('relative', True)
            if pts and len(pts) > 0:
                px, py = pts[0]
                if relative:
                    px, py = int(px * w), int(py * h)
                else:
                    px, py = int(px), int(py)
                self._point_trail.append((px, py))

                pt_color = (
                    point.get('b', 0),
                    point.get('g', 255),
                    point.get('r', 80),
                )
                radius = point.get('thickness', 8)

                # Trail
                if show_trail and len(self._point_trail) > 1:
                    pts_list = list(self._point_trail)[-trail_length:]
                    for k in range(1, len(pts_list)):
                        alpha = k / len(pts_list)
                        lw = max(1, int(thickness * alpha))
                        cv2.line(res, pts_list[k - 1], pts_list[k], pt_color, lw)

                cv2.circle(res, (px, py), radius, pt_color, -1)
        else:
            self._point_trail.clear()

        return {'main': res}
