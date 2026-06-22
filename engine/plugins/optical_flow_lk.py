import cv2
import numpy as np
from collections import deque
from registry import vision_node, NodeProcessor

# Maximum number of recent positions kept per tracked point for trajectory drawing.
TRACK_HISTORY_LEN = 15


@vision_node(
    type_id='optical_flow_lk',
    label='Optical Flow (Lucas-Kanade)',
    category='tracking',
    icon='Move',
    description="Sparse optical flow: Shi-Tomasi corner detection (goodFeaturesToTrack) "
                "tracked frame-to-frame with the pyramidal Lucas-Kanade method "
                "(calcOpticalFlowPyrLK). Stateful: keeps the previous frame and tracked "
                "points across frames in a 30fps stream.",
    inputs=[
        {'id': 'image', 'label': 'Input Frame', 'color': 'image'}
    ],
    outputs=[
        {'id': 'main', 'label': 'Overlay', 'color': 'image'},
        {'id': 'data', 'label': 'Stats', 'color': 'dict'}
    ],
    params=[
        {'id': '_sec_detection', 'label': 'Detection', 'type': 'section'},
        {'id': 'max_corners', 'label': 'Max Corners', 'type': 'int', 'min': 10, 'max': 1000, 'default': 200},
        {'id': 'quality', 'label': 'Quality Level', 'type': 'float', 'min': 0.01, 'max': 0.5, 'default': 0.3},
        {'id': 'min_distance', 'label': 'Min Distance', 'type': 'int', 'min': 1, 'max': 50, 'default': 7},
        {'id': 'win_size', 'label': 'Window Size', 'type': 'int', 'min': 5, 'max': 51, 'default': 15},
        {'id': 'redetect_every', 'label': 'Redetect Every (frames)', 'type': 'int', 'min': 1, 'max': 120, 'default': 20},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'draw', 'label': 'Draw Mode', 'type': 'enum', 'options': ['Tracks', 'Arrows', 'Points'], 'default': 'Tracks'},
        {'id': '_sec_control', 'label': 'Control', 'type': 'section'},
        {'id': 'reset', 'label': 'Reset Tracks', 'type': 'trigger', 'default': False}
    ]
)
class OpticalFlowLKNode(NodeProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_gray = None          # previous grayscale frame
        self.prev_pts = None           # tracked points, shape (N,1,2) float32
        self.tracks = []               # list of deque[(x,y)] trajectory history, parallel to prev_pts
        self.frame_count = 0
        self.colors = None             # per-track BGR colors

    def _detect(self, gray, max_corners, quality, min_distance):
        pts = cv2.goodFeaturesToTrack(
            gray, maxCorners=max_corners, qualityLevel=quality,
            minDistance=min_distance, blockSize=7
        )
        if pts is None:
            self.prev_pts = None
            self.tracks = []
            self.colors = None
            return
        pts = pts.astype(np.float32)
        self.prev_pts = pts
        self.tracks = [deque([(float(p[0][0]), float(p[0][1]))], maxlen=TRACK_HISTORY_LEN) for p in pts]
        rng = np.random.default_rng(42)
        self.colors = (rng.integers(0, 255, size=(len(pts), 3))).astype(int).tolist()

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'data': {'n_tracked': 0, 'mean_displacement': 0.0}}

        # --- params ---
        max_corners = int(params.get('max_corners', 200))
        quality = float(params.get('quality', 0.3))
        min_distance = int(params.get('min_distance', 7))
        win = int(params.get('win_size', 15))
        if win < 1:
            win = 1
        redetect_every = max(1, int(params.get('redetect_every', 20)))
        draw_mode = params.get('draw', 'Tracks')

        # --- handle latched reset trigger ---
        reset_triggered = bool(params.get('reset', False))
        if reset_triggered:
            self.prev_gray = None
            self.prev_pts = None
            self.tracks = []
            self.colors = None
            self.frame_count = 0
            # reset the latched trigger so it fires only once
            params['reset'] = False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        overlay = img.copy()

        need_detect = (
            self.prev_gray is None
            or self.prev_pts is None
            or len(self.prev_pts) == 0
            or (self.frame_count % redetect_every == 0)
        )

        mean_disp = 0.0
        n_tracked = 0

        if need_detect:
            self._detect(gray, max_corners, quality, min_distance)
        else:
            lk_params = dict(
                winSize=(win, win),
                maxLevel=2,
                criteria=(cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 10, 0.03)
            )
            try:
                new_pts, status, _err = cv2.calcOpticalFlowPyrLK(
                    self.prev_gray, gray, self.prev_pts, None, **lk_params
                )
            except cv2.error:
                new_pts, status = None, None

            if new_pts is None or status is None:
                # Tracking failed entirely → redetect this frame.
                self._detect(gray, max_corners, quality, min_distance)
            else:
                status = status.reshape(-1)
                good_new = new_pts[status == 1]
                good_old = self.prev_pts[status == 1]
                kept_idx = np.flatnonzero(status == 1)

                if len(good_new) == 0:
                    self._detect(gray, max_corners, quality, min_distance)
                else:
                    # update trajectory history & colors to surviving points
                    new_tracks = []
                    new_colors = []
                    disps = []
                    for j, idx in enumerate(kept_idx):
                        nx, ny = float(good_new[j][0][0]), float(good_new[j][0][1])
                        ox, oy = float(good_old[j][0][0]), float(good_old[j][0][1])
                        disps.append(((nx - ox) ** 2 + (ny - oy) ** 2) ** 0.5)
                        if idx < len(self.tracks):
                            tr = self.tracks[idx]
                        else:
                            tr = deque(maxlen=TRACK_HISTORY_LEN)
                        tr.append((nx, ny))
                        new_tracks.append(tr)
                        if self.colors is not None and idx < len(self.colors):
                            new_colors.append(self.colors[idx])
                        else:
                            new_colors.append([0, 255, 0])

                        col = tuple(int(c) for c in new_colors[-1])
                        if draw_mode == 'Arrows':
                            cv2.arrowedLine(overlay, (int(ox), int(oy)), (int(nx), int(ny)),
                                            col, 2, tipLength=0.4)
                        elif draw_mode == 'Points':
                            cv2.circle(overlay, (int(nx), int(ny)), 3, col, -1)

                    self.prev_pts = good_new.reshape(-1, 1, 2).astype(np.float32)
                    self.tracks = new_tracks
                    self.colors = new_colors
                    n_tracked = len(good_new)
                    if disps:
                        mean_disp = float(np.mean(disps))

                    # draw full trajectories for 'Tracks' mode
                    if draw_mode == 'Tracks':
                        for tr, col in zip(self.tracks, self.colors):
                            if len(tr) >= 2:
                                pts_line = np.array(tr, dtype=np.int32).reshape(-1, 1, 2)
                                cv2.polylines(overlay, [pts_line], False,
                                              tuple(int(c) for c in col), 2)
                            last = tr[-1]
                            cv2.circle(overlay, (int(last[0]), int(last[1])), 3,
                                       tuple(int(c) for c in col), -1)

        # If we (re)detected this frame, draw current points / count them.
        if self.prev_pts is not None:
            n_tracked = len(self.prev_pts)
            if need_detect and draw_mode in ('Points', 'Tracks'):
                for p in self.prev_pts:
                    cv2.circle(overlay, (int(p[0][0]), int(p[0][1])), 3, (0, 255, 0), -1)

        # --- update state for next frame ---
        self.prev_gray = gray.copy()
        self.frame_count += 1

        return {
            'main': overlay,
            'data': {
                'n_tracked': int(n_tracked),
                'mean_displacement': round(float(mean_disp), 3)
            }
        }
