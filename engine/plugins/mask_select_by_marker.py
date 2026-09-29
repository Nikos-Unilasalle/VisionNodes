import cv2
import numpy as np
from registry import vision_node, NodeProcessor

MODES = ['Keep Marked', 'Remove Marked']
CONNECTIVITY = ['4-connected', '8-connected']


def _binary(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return (g > 0).astype(np.uint8)


@vision_node(
    type_id='mask_select_by_marker',
    label='Select Blobs by Marker',
    category='mask',
    icon='MousePointerClick',
    description=(
        "Morphological reconstruction: keeps (or removes) every whole blob of the mask that "
        "touches the marker mask. Use a strict detector as marker and a permissive one as "
        "mask to get complete objects (e.g. full vessels from their bright highlight, "
        "whole cells from seed points, entire grains from a few confident pixels)."
    ),
    inputs=[
        {'id': 'mask', 'color': 'mask'},
        {'id': 'marker', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'mask', 'color': 'mask'},
        {'id': 'count', 'color': 'scalar', 'label': 'Blobs Kept'},
    ],
    params=[
        {'id': 'mode', 'label': 'Mode', 'type': 'enum', 'options': MODES, 'default': 0},
        {'id': 'connectivity', 'label': 'Connectivity', 'type': 'enum', 'options': CONNECTIVITY, 'default': 0},
    ],
)
class SelectByMarkerNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'mask': None, 'count': 0}
        binary = _binary(mask)
        marker = inputs.get('marker')
        if marker is None:
            n = cv2.connectedComponents(binary)[0] - 1
            return {'mask': binary * 255, 'count': int(n)}

        mk = _binary(marker)
        if mk.shape != binary.shape:
            mk = cv2.resize(mk, (binary.shape[1], binary.shape[0]), interpolation=cv2.INTER_NEAREST)
        conn = 8 if int(params.get('connectivity', 0)) == 1 else 4
        n_labels, labels = cv2.connectedComponents(binary, connectivity=conn)
        touched = np.zeros(n_labels, bool)
        touched[np.unique(labels[mk > 0])] = True
        touched[0] = False
        keep = ~touched if int(params.get('mode', 0)) == 1 else touched
        keep[0] = False
        return {'mask': keep[labels].astype(np.uint8) * 255, 'count': int(keep.sum())}
