from __main__ import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import os
import threading
import urllib.request

# Absolute path to the gaze/ folder (two levels up from this plugin file)
_PLUGIN_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(os.path.dirname(_PLUGIN_DIR))   # engine/plugins → engine → project root
_DEFAULT_CKPT = os.path.join(_PROJECT_DIR, 'gaze', 'epoch_24_ckpt.pth.tar')

# ── ETH-XGaze face model: 3-D reference points (mm) ─────────────────────────
# Extracted from face_model.txt rows [20, 23, 26, 29, 15, 19]
# Paired with MediaPipe landmarks:   [33, 133, 362, 263,  4, 152]
_FACE_MODEL_3D = np.array([
    [-46.50949860, -38.32709503,  36.41600418],   # 33  left eye outer
    [-17.76072121, -32.58519745,  29.07615662],   # 133 left eye inner
    [ 18.04391098, -30.95682335,  29.06296730],   # 362 right eye inner
    [ 44.73758698, -34.10787201,  36.73243713],   # 263 right eye outer
    [-15.56392288, -53.81772232,  12.00321198],   # 4   nose tip
    [ 11.28962994,  13.86424446,  21.83790016],   # 152 chin
], dtype=np.float64)

_LANDMARK_IDS = [33, 133, 362, 263, 4, 152]

_NOTIF_ID = 'gaze_estimator'


# ── Inline gaze_network (ETH-XGaze ResNet50 backbone) ────────────────────────
def _build_gaze_network():
    import torch.nn as nn
    from torchvision.models import resnet50

    class GazeNetwork(nn.Module):
        def __init__(self):
            super().__init__()
            self.gaze_network = resnet50(weights=None)
            self.gaze_fc = nn.Sequential(nn.Linear(2048, 2))

        def forward(self, x):
            n = self.gaze_network
            x = n.maxpool(n.relu(n.bn1(n.conv1(x))))
            x = n.layer4(n.layer3(n.layer2(n.layer1(x))))
            feat = n.avgpool(x).view(x.size(0), -1)
            return self.gaze_fc(feat)

    return GazeNetwork()


# ── ETH normalisation (from reference script) ────────────────────────────────
def _normalize_face(img, landmarks_2d, rvec, tvec, cam_matrix):
    focal_norm    = 960
    distance_norm = 600
    roi_size      = (224, 224)

    ht = tvec.reshape((3, 1))
    hR = cv2.Rodrigues(rvec)[0]
    Fc = np.dot(hR, _FACE_MODEL_3D.T) + ht                  # (3, 6)

    two_eye_center = np.mean(Fc[:, 0:4], axis=1, keepdims=True)
    nose_center    = np.mean(Fc[:, 4:6], axis=1, keepdims=True)
    face_center    = np.mean(np.hstack([two_eye_center, nose_center]),
                             axis=1, keepdims=True)

    distance = float(np.linalg.norm(face_center))
    z_scale  = distance_norm / distance

    cam_norm = np.array([
        [focal_norm, 0,          roi_size[0] / 2],
        [0,          focal_norm, roi_size[1] / 2],
        [0,          0,          1.0],
    ])
    S = np.diag([1.0, 1.0, z_scale])

    fc_vec  = (face_center / distance).reshape(3)
    hRx     = hR[:, 0]
    down    = np.cross(fc_vec, hRx);  down  /= np.linalg.norm(down)
    right   = np.cross(down, fc_vec); right /= np.linalg.norm(right)
    R       = np.column_stack([right, down, fc_vec]).T

    W = cam_norm @ S @ R @ np.linalg.inv(cam_matrix)
    img_warped = cv2.warpPerspective(img, W, roi_size)
    return img_warped


@vision_node(
    type_id='analysis_gaze',
    label='Gaze Estimator',
    category='track',
    icon='Eye',
    description="ETH-XGaze gaze estimation (pitch/yaw). Loads epoch_24_ckpt.pth.tar. Requires torch + torchvision.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main',  'color': 'image'},
        {'id': 'gaze',  'color': 'dict'},
        {'id': 'yaw',   'color': 'scalar'},
        {'id': 'pitch', 'color': 'scalar'}
    ],
    params=[
        {'id': 'weights',          'label': 'Checkpoint path',    'type': 'string', 'default': ''},
        {'id': 'calibration',      'label': 'Camera calibration', 'type': 'enum',   'options': ['Auto (image-based)', 'Custom XML'], 'default': 0},
        {'id': 'calibration_path', 'label': 'Calibration XML',    'type': 'string', 'default': ''},
        {'id': 'pitch_offset',     'label': 'Pitch offset (°)',   'type': 'float',  'default': 0.0, 'min': -45.0, 'max': 45.0, 'step': 0.5},
        {'id': 'yaw_offset',       'label': 'Yaw offset (°)',     'type': 'float',  'default': 0.0, 'min': -45.0, 'max': 45.0, 'step': 0.5},
    ]
)
class GazeEstimatorNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.model          = None
        self.transform      = None
        self.face_mesh      = None
        self.loaded_weights = None
        self._loading       = False
        self._failed        = set()
        self._calib_cache   = {}  # path → (base_cam, base_dist, orig_w, orig_h)

    def _load_in_thread(self, weights_path):
        try:
            import torch
            from torchvision import transforms

            send_notification('Loading ETH-XGaze model…', progress=0.1, notif_id=_NOTIF_ID)

            if not os.path.exists(weights_path):
                send_notification(
                    f'Checkpoint not found: {weights_path}',
                    progress=None, level='error', notif_id=_NOTIF_ID
                )
                self._failed.add(weights_path)
                return

            net = _build_gaze_network()
            ckpt = torch.load(weights_path, map_location='cpu', weights_only=False)
            state = ckpt.get('model_state', ckpt)
            net.load_state_dict(state, strict=False)
            net.eval()

            send_notification('ETH-XGaze ready ✓', progress=0.5, notif_id=_NOTIF_ID)

            # MediaPipe Tasks API (same as FaceDetectionNode in engine.py)
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            task_path = os.path.join(_PROJECT_DIR, 'face_landmarker.task')
            if not os.path.exists(task_path):
                send_notification('Downloading face_landmarker.task…', progress=0.6, notif_id=_NOTIF_ID)
                urllib.request.urlretrieve(
                    'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
                    task_path
                )

            base_opts   = mp_python.BaseOptions(model_asset_path=task_path)
            lm_options  = mp_vision.FaceLandmarkerOptions(
                base_options=base_opts,
                running_mode=mp_vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            face_mesh = mp_vision.FaceLandmarker.create_from_options(lm_options)
            self._mp = mp   # keep ref for Image creation

            trans = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225]),
            ])

            self.model          = net
            self.transform      = trans
            self.face_mesh      = face_mesh
            self.loaded_weights = weights_path
            send_notification('Gaze Estimator ready ✓', progress=1.0, notif_id=_NOTIF_ID)

        except Exception as e:
            self._failed.add(weights_path)
            print(f'[GazeEstimator] FAILED: {e}')
            send_notification(f'Gaze Estimator error: {str(e)[:120]}',
                              progress=None, level='error', notif_id=_NOTIF_ID)
        finally:
            self._loading = False

    def process(self, inputs, params):
        import torch
        image = inputs.get('image')
        empty   = {'yaw': 0.0, 'pitch': 0.0, 'vec_x': 0.0, 'vec_y': 0.0, 'vec_z': -1.0}
        no_data = {'main': image, 'gaze': empty, 'yaw': 0.0, 'pitch': 0.0}

        if image is None:
            return no_data

        weights = params.get('weights', '') or _DEFAULT_CKPT

        if self.model is None and not self._loading and weights not in self._failed:
            if self.loaded_weights != weights:
                send_notification('Starting Gaze Estimator…', progress=0.0, notif_id=_NOTIF_ID)
                self._loading = True
                threading.Thread(target=self._load_in_thread, args=(weights,), daemon=True).start()
            return no_data

        if self.model is None:
            return no_data

        h, w = image.shape[:2]
        mp_img  = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        )
        results = self.face_mesh.detect(mp_img)

        if not results.face_landmarks:
            return no_data

        face_lms = results.face_landmarks[0]  # list of NormalizedLandmark

        # 2-D landmarks (pixel coords), shape (6,1,2)
        pts_2d = np.array(
            [[face_lms[i].x * w, face_lms[i].y * h] for i in _LANDMARK_IDS],
            dtype=np.float64
        ).reshape(6, 1, 2)

        calib_mode = params.get('calibration', 0)
        xml_path   = (params.get('calibration_path') or '').strip()

        if calib_mode == 1 and xml_path:
            if xml_path not in self._calib_cache:
                if os.path.exists(xml_path):
                    fs = cv2.FileStorage(xml_path, cv2.FILE_STORAGE_READ)
                    base_cam  = fs.getNode('Camera_Matrix').mat()
                    base_dist = fs.getNode('Distortion_Coefficients').mat()
                    w_node, h_node = fs.getNode('image_Width'), fs.getNode('image_Height')
                    orig_w = int(w_node.real()) if not w_node.empty() else 0
                    orig_h = int(h_node.real()) if not h_node.empty() else 0
                    fs.release()
                    self._calib_cache[xml_path] = (base_cam, base_dist, orig_w, orig_h)
                else:
                    send_notification(f'Calibration XML not found: {xml_path}',
                                      progress=None, level='error', notif_id=_NOTIF_ID)

            if xml_path in self._calib_cache:
                base_cam, base_dist, orig_w, orig_h = self._calib_cache[xml_path]
                cam = base_cam.copy()
                if orig_w > 0 and orig_h > 0:
                    cam[0, 0] *= w / orig_w;  cam[0, 2] *= w / orig_w
                    cam[1, 1] *= h / orig_h;  cam[1, 2] *= h / orig_h
                dist = base_dist
            else:
                cam  = np.array([[float(w), 0, w/2], [0, float(w), h/2], [0, 0, 1]], dtype=np.float64)
                dist = np.zeros((4, 1))
        else:
            cam  = np.array([[float(w), 0, w/2], [0, float(w), h/2], [0, 0, 1]], dtype=np.float64)
            dist = np.zeros((4, 1))

        _, rvec, tvec = cv2.solvePnP(
            _FACE_MODEL_3D, pts_2d, cam, dist,
            flags=cv2.SOLVEPNP_EPNP
        )
        _, rvec, tvec = cv2.solvePnP(
            _FACE_MODEL_3D, pts_2d, cam, dist,
            rvec, tvec, useExtrinsicGuess=True
        )

        img_norm = _normalize_face(image, pts_2d, rvec, tvec, cam)

        # BGR → RGB for transform
        inp = self.transform(img_norm[:, :, ::-1].copy()).unsqueeze(0)
        with torch.no_grad():
            pred = self.model(inp)[0].cpu().numpy()   # (pitch, yaw) in radians

        pitch_rad = float(pred[0]) + np.radians(float(params.get('pitch_offset', 0.0)))
        yaw_rad   = float(pred[1]) + np.radians(float(params.get('yaw_offset',   0.0)))

        vec_x = -np.cos(yaw_rad) * np.sin(pitch_rad)
        vec_y = -np.sin(yaw_rad)
        vec_z = -np.cos(yaw_rad) * np.cos(pitch_rad)

        face_center = pts_2d.mean(axis=0).flatten().astype(int)
        length = max(w, h) // 6
        gaze_2d = np.array([-np.sin(yaw_rad) * np.cos(pitch_rad),
                             -np.sin(pitch_rad)]) * length
        endpoint = (face_center + gaze_2d).astype(int)

        out_img = image.copy()
        cv2.arrowedLine(out_img, tuple(face_center), tuple(endpoint),
                        (0, 255, 100), 2, tipLength=0.3)

        gaze = {
            'yaw': yaw_rad, 'pitch': pitch_rad,
            'vec_x': float(vec_x), 'vec_y': float(vec_y), 'vec_z': float(vec_z),
        }
        return {'main': out_img, 'gaze': gaze, 'yaw': yaw_rad, 'pitch': pitch_rad}
