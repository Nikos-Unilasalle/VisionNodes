from registry import vision_node, NodeProcessor, send_notification
import math
import numpy as np
import cv2

SAMPLES_PER_CORNER = 30
_NOTIF_ID = 'gaze_to_screen'

@vision_node(
    type_id='math_gaze_to_screen',
    label='Gaze → Screen',
    category='math',
    icon='Monitor',
    description="Maps gaze yaw/pitch to normalized screen coordinates [0..1]. Includes calibration for eye-tracking accuracy.",
    inputs=[
        {'id': '3dvector', 'color': 'dict', 'label': 'Gaze (Yaw/Pitch)'},
        {'id': 'image',    'color': 'image', 'label': 'Visual Feedback'},
    ],
    outputs=[
        {'id': 'main',  'color': 'image', 'label': 'Output Image'},
        {'id': 'x',     'color': 'scalar', 'label': 'Screen X'},
        {'id': 'y',     'color': 'scalar', 'label': 'Screen Y'},
        {'id': 'point', 'color': 'dict', 'label': 'Graphics Point'}
    ],
    params=[
        {'id': 'scale_x',  'label': 'Scale X',    'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 10.0, 'step': 0.05},
        {'id': 'scale_y',  'label': 'Scale Y',    'type': 'float', 'default': 1.0,  'min': 0.1, 'max': 10.0, 'step': 0.05},
        {'id': 'offset_x', 'label': 'Offset X',   'type': 'float', 'default': 0.0,  'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'offset_y', 'label': 'Offset Y',   'type': 'float', 'default': 0.0,  'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'smooth',   'label': 'Smoothing',  'type': 'float', 'default': 0.7,  'min': 0.0,  'max': 0.99,'step': 0.01},
        {'id': 'clamp',    'label': 'Clamp',      'type': 'bool',  'default': True},
        {'id': 'flip_x',   'label': 'Flip X',     'type': 'bool',  'default': False},
        {'id': 'flip_y',   'label': 'Flip Y',     'type': 'bool',  'default': False},
        {'id': 'use_fov',  'label': 'Use Camera FOV', 'type': 'bool', 'default': False},
        {'id': 'hfov',     'label': 'H-FOV (deg)',    'type': 'float', 'default': 60.0, 'min': 10.0, 'max': 170.0},
        {'id': 'sep_cal',  'label': '--- Calibration ---', 'type': 'separator'},
        {'id': 'calibration_enabled', 'label': 'Enable Calibration', 'type': 'bool', 'default': False},
        {'id': 'calibrate_tl',    'label': 'Calibrate TL',    'type': 'trigger'},
        {'id': 'calibrate_tr',    'label': 'Calibrate TR',    'type': 'trigger'},
        {'id': 'calibrate_br',    'label': 'Calibrate BR',    'type': 'trigger'},
        {'id': 'calibrate_bl',    'label': 'Calibrate BL',    'type': 'trigger'},
        {'id': 'calibrate_reset', 'label': 'Reset Calib',    'type': 'trigger'},
    ]
)
class GazeToScreenNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._sx = 0.5
        self._sy = 0.5
        self._initialized = False
        self._cal_samples = []
        self._cal_corner = None
        self._cal_data = {}
        self._calibrated = set()

    def process(self, inputs, params):
        gaze  = inputs.get('3dvector')
        image = inputs.get('image')

        # Compute raw coordinates
        raw_x, raw_y = self._compute_raw(gaze, params, image)
        
        # If no gaze detected, return None
        if not isinstance(gaze, dict):
            point = {'_type': 'graphics', 'shape': 'point', 'pts': [], 'relative': True}
            return {'main': image, 'x': None, 'y': None, 'point': point}

        # Initialize or Smooth
        if not self._initialized:
            self._sx, self._sy = raw_x, raw_y
            self._initialized = True
        else:
            s = float(params.get('smooth', 0.7))
            self._sx = s * self._sx + (1.0 - s) * raw_x
            self._sy = s * self._sy + (1.0 - s) * raw_y

        out_x, out_y = self._sx, self._sy

        # Handle Calibration (Sample based on raw coordinates for responsiveness)
        self._handle_calibration_logic(raw_x, raw_y, params)
        
        # Apply Calibration mapping
        if bool(params.get('calibration_enabled', False)) and len(self._cal_data) >= 4:
            out_x, out_y = self._apply_calibration(out_x, out_y)

        # Final Clamp
        if bool(params.get('clamp', True)):
            out_x = max(0.0, min(1.0, out_x))
            out_y = max(0.0, min(1.0, out_y))

        # Graphics Point
        point = {
            '_type': 'graphics', 'shape': 'point',
            'pts': [[out_x, out_y]], 'relative': True,
            'color': (0, 80, 255), 'thickness': 14
        }

        # Render visual feedback
        out_img = None
        if image is not None:
            out_img = self._render_feedback(image.copy(), out_x, out_y, params)

        return {'main': out_img, 'x': out_x, 'y': out_y, 'point': point}

    def _compute_raw(self, gaze, params, image):
        if not isinstance(gaze, dict):
            return 0.5, 0.5

        yaw   = float(gaze.get('yaw',   0.0))
        pitch = float(gaze.get('pitch', 0.0))
        scale_x = float(params.get('scale_x', 1.0))
        scale_y = float(params.get('scale_y', 1.0))
        ox = float(params.get('offset_x', 0.0))
        oy = float(params.get('offset_y', 0.0))

        if bool(params.get('use_fov', False)):
            if image is not None:
                h_img, w_img = image.shape[:2]
                focal = float(max(w_img, h_img))
            else:
                hfov_rad = math.radians(float(params.get('hfov', 60.0)))
                # Assuming 1.0 is the full screen width in normalized coords
                focal = 0.5 / math.tan(hfov_rad / 2)
                w_img, h_img = 1.0, 1.0 # normalized
            
            raw_x = 0.5 + (math.tan(yaw   + ox) * focal / w_img) * scale_x
            raw_y = 0.5 - (math.tan(pitch + oy) * focal / h_img) * scale_y
        else:
            raw_x = 0.5 + (yaw   + ox) * scale_x
            raw_y = 0.5 - (pitch + oy) * scale_y

        if bool(params.get('flip_x', False)):
            raw_x = 1.0 - raw_x
        if bool(params.get('flip_y', False)):
            raw_y = 1.0 - raw_y

        return raw_x, raw_y

    def _handle_calibration_logic(self, rx, ry, params):
        # Reset
        if params.get('calibrate_reset'):
            self._cal_data = {}
            self._calibrated = set()
            self._cal_corner = None
            self._cal_samples = []
            send_notification('Calibration reset', 1.0, notif_id=_NOTIF_ID)

        # Start a new corner calibration
        if self._cal_corner is None:
            for corner in ['tl', 'tr', 'br', 'bl']:
                if params.get(f'calibrate_{corner}'):
                    self._cal_corner = corner
                    self._cal_samples = []
                    self._cal_frame_count = 0
                    send_notification(f'Look at {corner.upper()} corner...', 0.0, notif_id=_NOTIF_ID)
                    break

        # Accumulate samples
        if self._cal_corner is not None:
            self._cal_samples.append((rx, ry))
            self._cal_frame_count += 1
            progress = min(0.99, self._cal_frame_count / SAMPLES_PER_CORNER)
            send_notification(
                f'Calibrating {self._cal_corner.upper()}... {self._cal_frame_count}/{SAMPLES_PER_CORNER}',
                progress, notif_id=_NOTIF_ID
            )

            if self._cal_frame_count >= SAMPLES_PER_CORNER:
                xs = [s[0] for s in self._cal_samples]
                ys = [s[1] for s in self._cal_samples]
                self._cal_data[self._cal_corner] = (np.mean(xs), np.mean(ys))
                self._calibrated.add(self._cal_corner)
                send_notification(f'{self._cal_corner.upper()} calibrated ({len(self._calibrated)}/4)', 1.0, notif_id=_NOTIF_ID)
                self._cal_corner = None

    def _apply_calibration(self, x, y):
        tl = self._cal_data.get('tl', (0,0))
        tr = self._cal_data.get('tr', (1,0))
        br = self._cal_data.get('br', (1,1))
        bl = self._cal_data.get('bl', (0,1))

        # Bilinear-ish interpolation
        left_x  = (tl[0] + bl[0]) / 2
        right_x = (tr[0] + br[0]) / 2
        top_y   = (tl[1] + tr[1]) / 2
        bot_y   = (bl[1] + br[1]) / 2

        rx = right_x - left_x
        ry = bot_y - top_y

        if rx > 0.001: x = (x - left_x) / rx
        if ry > 0.001: y = (y - top_y) / ry
        return x, y

    def _render_feedback(self, img, out_x, out_y, params):
        h, w = img.shape[:2]
        px, py = int(out_x * w), int(out_y * h)
        
        # Crosshair
        cv2.line(img, (px - 20, py), (px + 20, py), (0, 80, 255), 2)
        cv2.line(img, (px, py - 20), (px, py + 20), (0, 80, 255), 2)
        cv2.circle(img, (px, py), 10, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Calibration Targets
        if self._cal_corner is not None or not bool(params.get('calibration_enabled', False)):
            corners = {'tl': (0.05, 0.05), 'tr': (0.95, 0.05), 'br': (0.95, 0.95), 'bl': (0.05, 0.95)}
            for name, pos in corners.items():
                cx, cy = int(pos[0] * w), int(pos[1] * h)
                color = (0, 255, 0) if name in self._calibrated else (100, 100, 100)
                if name == self._cal_corner: color = (0, 255, 255)
                cv2.circle(img, (cx, cy), 15, color, 2 if name != self._cal_corner else 4)
                cv2.putText(img, name.upper(), (cx - 10, cy - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Status text
        txt = f"Gaze: {out_x:.2f}, {out_y:.2f}"
        if len(self._calibrated) < 4 and bool(params.get('calibration_enabled', False)):
            txt += " (UN-CALIBRATED)"
        cv2.putText(img, txt, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
        cv2.putText(img, txt, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return img
