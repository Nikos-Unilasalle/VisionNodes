import cv2
import numpy as np
from registry import vision_node, NodeProcessor

CONNECTIVITY = ['8-connected', '4-connected']


def _binary(mask):
    m = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask
    return (m > 0).astype(np.uint8)


@vision_node(
    type_id='mask_keep_largest',
    label='Keep Largest Blobs',
    category='mask',
    icon='Maximize2',
    description=(
        "Keeps only the N largest connected blobs of a mask and drops everything else. "
        "Typical use: isolate the main object (a section, a leaf, a grain, a part) "
        "after a threshold that also picked up debris."
    ),
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[
        {'id': 'mask', 'color': 'mask'},
        {'id': 'count', 'color': 'scalar', 'label': 'Kept'},
        {'id': 'area_px', 'color': 'scalar', 'label': 'Area (px)'},
    ],
    params=[
        {'id': 'count', 'label': 'Keep N', 'type': 'int', 'default': 1, 'min': 1, 'max': 100},
        {'id': 'connectivity', 'label': 'Connectivity', 'type': 'enum', 'options': CONNECTIVITY, 'default': 0},
    ],
)
class KeepLargestBlobsNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'mask': None, 'count': 0, 'area_px': 0}

        binary = _binary(mask)
        conn = 4 if int(params.get('connectivity', 0)) == 1 else 8
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=conn)
        if n_labels < 2:
            return {'mask': np.zeros_like(binary), 'count': 0, 'area_px': 0}

        keep_n = max(1, int(params.get('count', 1)))
        areas = stats[1:, cv2.CC_STAT_AREA]
        kept = 1 + np.argsort(areas)[::-1][:keep_n]
        out = np.isin(labels, kept).astype(np.uint8) * 255
        return {'mask': out, 'count': int(len(kept)), 'area_px': int(areas[kept - 1].sum())}
