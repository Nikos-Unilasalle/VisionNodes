from registry import vision_node, NodeProcessor
import cv2
import numpy as np

# 3D canonical face model (mm) — 6 stable landmarks for solvePnP
# Indices for MediaPipe Face Mesh (478 pts)
_LANDMARK_IDS = [1, 152, 33, 263, 61, 291]  # nose tip, chin, eye outer L/R, mouth L/R
_MODEL_3D = np.array([
    [ 0.0,    0.0,    0.0  ],
    [ 0.0,  -63.6,  -12.5  ],
    [-43.3,  32.7,  -26.0  ],
    [ 43.3,  32.7,  -26.0  ],
    [-28.9, -28.9,  -24.1  ],
    [ 28.9, -28.9,  -24.1  ],
], dtype=np.float64)

@vision_node(
    type_id='analysis_head_pose',
    label='Head Pose',
    category='detect',
    icon='Crosshair',
    description="Estimates 3D head orientation (yaw, pitch, roll) via solvePnP on facial landmarks. Connect Face Tracker output.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'face',  'color': 'dict'}
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'pose', 'color': 'dict'}
    ],
    params=[
        {'id': 'draw_axes', 'label': 'Draw Axes', 'type': 'bool', 'default': True}
    ]
)
class HeadPoseNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        face  = inputs.get('face')
        empty = {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0, 'rvec': [], 'tvec': [], 'cam_matrix': []}

        if image is None or not isinstance(face, dict) or 'landmarks' not in face:
            return {'main': image, 'pose': empty}

        lms = face['landmarks']
        if len(lms) < max(_LANDMARK_IDS) + 1:
            return {'main': image, 'pose': empty}

        h, w = image.shape[:2]
        try:
            pts_2d = np.array(
                [[lms[i]['x'] * w, lms[i]['y'] * h] for i in _LANDMARK_IDS],
                dtype=np.float64
            )
        except (KeyError, TypeError):
            return {'main': image, 'pose': empty}

        focal = float(w)
        cam_matrix = np.array([
            [focal, 0,     w / 2.0],
            [0,     focal, h / 2.0],
            [0,     0,     1.0    ]
        ], dtype=np.float64)

        ok, rvec, tvec = cv2.solvePnP(
            _MODEL_3D, pts_2d, cam_matrix, np.zeros((4, 1)),
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not ok:
            return {'main': image, 'pose': empty}

        rot_mat, _ = cv2.Rodrigues(rvec)
        proj_mat   = np.hstack((rot_mat, tvec))
        _, _, _, _, _, _, euler = cv2.decomposeProjectionMatrix(proj_mat)
        pitch = float(euler[0][0])
        yaw   = float(euler[1][0])
        roll  = float(euler[2][0])

        out_img = image
        if int(params.get('draw_axes', 1)):
            out_img = image.copy()
            nose_2d = tuple(pts_2d[0].astype(int))
            axis_pts, _ = cv2.projectPoints(
                np.float64([[60,0,0],[0,60,0],[0,0,60]]),
                rvec, tvec, cam_matrix, np.zeros((4,1))
            )
            ax = axis_pts.reshape(-1, 2).astype(int)
            cv2.arrowedLine(out_img, nose_2d, tuple(ax[0]), (0,   0, 255), 2, tipLength=0.3)  # X red
            cv2.arrowedLine(out_img, nose_2d, tuple(ax[1]), (0, 255,   0), 2, tipLength=0.3)  # Y green
            cv2.arrowedLine(out_img, nose_2d, tuple(ax[2]), (255, 0,   0), 2, tipLength=0.3)  # Z blue

        pose = {
            'yaw':        yaw,
            'pitch':      pitch,
            'roll':       roll,
            'rvec':       rvec.flatten().tolist(),
            'tvec':       tvec.flatten().tolist(),
            'cam_matrix': cam_matrix.flatten().tolist(),
            'img_w':      w,
            'img_h':      h,
        }
        return {'main': out_img, 'pose': pose}
