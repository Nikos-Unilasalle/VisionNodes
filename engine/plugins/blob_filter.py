from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='filter_blob_filter',
    label='Blob Filter',
    category='mask',
    icon='Filter',
    description="Removes blobs outside an area range from a binary mask using connected components. Eliminates isolated noise pixels while preserving large regions.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[
        {'id': 'mask',  'color': 'mask'},
        {'id': 'count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'min_area',     'type': 'int',  'default': 100, 'label': 'Min Area (px²)'},
        {'id': 'max_area',     'type': 'int',  'default': 0,   'label': 'Max Area (0 = off)'},
        {'id': 'connectivity', 'type': 'int',  'default': 8,   'label': 'Connectivity (4 or 8)'},
    ],
    colorable=True,
)
class BlobFilterNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'mask': None, 'count': 0}

        min_area     = max(1, int(params.get('min_area', 100)))
        max_area     = int(params.get('max_area', 0))
        connectivity = int(params.get('connectivity', 8))
        if connectivity not in (4, 8):
            connectivity = 8

        # Ensure single-channel binary
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            binary, connectivity=connectivity
        )

        out = np.zeros_like(binary)
        count = 0
        for lbl in range(1, num_labels):          # 0 = background, skip
            area = stats[lbl, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            if max_area > 0 and area > max_area:
                continue
            out[labels == lbl] = 255
            count += 1

        return {'mask': out, 'count': count}
