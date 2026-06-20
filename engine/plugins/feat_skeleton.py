import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='feat_skeleton',
    label='Skeleton',
    category='measure',
    icon='GitBranch',
    description=(
        "Reduces a binary mask to its medial axis (skeleton) (ch11 §11.5).\n\n"
        "Method: Distance Transform + local maxima (crêtes de la carte de distance,\n"
        "consistent with ch10 §10.5). Each skeleton pixel is the centre of a maximal\n"
        "inscribed disc — the skeleton and the DT encode the same geometry.\n\n"
        "Outputs: skeleton overlay, branch count, max inscribed radius."
    ),
    inputs=[
        {'id': 'mask', 'label': 'Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',        'label': 'Skeleton',         'color': 'image'},
        {'id': 'branch_count','label': 'Branch Count',     'color': 'scalar'},
        {'id': 'max_radius',  'label': 'Max Inscribed R',  'color': 'scalar'},
    ],
    params=[
        {'id': 'min_radius', 'label': 'Min Local Radius (px)', 'type': 'int',
         'default': 2, 'min': 1, 'max': 20},
        {'id': 'overlay',    'label': 'Overlay on Mask',   'type': 'bool', 'default': True},
    ]
)
class SkeletonNode(NodeProcessor):

    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'main': None, 'branch_count': 0, 'max_radius': 0.0}

        if mask.ndim == 3:
            gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            gray = mask.copy()
        binary = (gray > 127).astype(np.uint8)

        min_r  = int(params.get('min_radius', 2))
        overlay = bool(params.get('overlay', True))

        # Distance transform — ridge = skeleton (ch10 §10.5)
        dt = cv2.distanceTransform(binary, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        max_radius = float(dt.max())

        # Local maxima: pixel is a skeleton point if it equals the max in a (2r+1) window
        # Use morphological dilation to detect local peaks
        win = 2 * max(min_r, 1) + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (win, win))
        local_max = cv2.dilate(dt, kernel)
        skel_mask = ((dt > 0) & (np.abs(dt - local_max) < 0.5)).astype(np.uint8) * 255

        # Branch count: connected components of the skeleton
        n_labels, _ = cv2.connectedComponents(skel_mask, connectivity=8)
        branch_count = max(0, n_labels - 1)

        # Visualise
        H, W = binary.shape
        if overlay:
            base = cv2.cvtColor(binary * 255, cv2.COLOR_GRAY2BGR)
        else:
            base = np.zeros((H, W, 3), dtype=np.uint8)

        vis = base.copy()
        vis[skel_mask > 0] = (0, 255, 100)   # green skeleton on mask

        cv2.putText(vis, f'branches={branch_count}  max_r={max_radius:.1f}px',
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (255, 255, 255), 1, cv2.LINE_AA)

        return {
            'main':         vis,
            'branch_count': branch_count,
            'max_radius':   round(max_radius, 2),
        }
