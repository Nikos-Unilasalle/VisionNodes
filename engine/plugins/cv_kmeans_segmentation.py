import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_kmeans_segmentation',
    label='K-Means Segmentation',
    category='segmentation',
    icon='Target',
    description=(
        "Colour segmentation via K-Means clustering on pixel values (ch12 §12.4).\n\n"
        "Each pixel is replaced by the centroid colour of its cluster. Work in Lab\n"
        "colour space (perceptually uniform) for better cluster quality."
    ),
    inputs=[
        {'id': 'image', 'label': 'Image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',   'label': 'Segmented', 'color': 'image'},
        {'id': 'k_used', 'label': 'K Used',    'color': 'scalar'},
    ],
    params=[
        {'id': 'k',            'label': 'K Clusters',   'type': 'int',  'default': 4,   'min': 2,  'max': 20},
        {'id': 'color_space',  'label': 'Color Space',  'type': 'enum',
         'options': ['RGB', 'Lab'], 'default': 1},
        {'id': 'attempts',     'label': 'Attempts',     'type': 'int',  'default': 3,   'min': 1,  'max': 10},
        {'id': 'max_iter',     'label': 'Max Iterations','type': 'int', 'default': 100, 'min': 10, 'max': 500},
    ]
)
class KMeansSegmentationNode(NodeProcessor):

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'k_used': 0}

        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        k          = int(params.get('k', 4))
        use_lab    = int(params.get('color_space', 1)) == 1
        attempts   = int(params.get('attempts', 3))
        max_iter   = int(params.get('max_iter', 100))

        work = cv2.cvtColor(img, cv2.COLOR_BGR2Lab) if use_lab else img.copy()

        pixels = work.reshape(-1, 3).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, max_iter, 0.2)
        _, labels, centers = cv2.kmeans(
            pixels, k, None, criteria, attempts, cv2.KMEANS_PP_CENTERS
        )

        centers = centers.astype(np.uint8)
        segmented_lab = centers[labels.flatten()].reshape(work.shape)

        if use_lab:
            result = cv2.cvtColor(segmented_lab, cv2.COLOR_Lab2BGR)
        else:
            result = segmented_lab

        return {'main': result, 'k_used': k}
