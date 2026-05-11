from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='filter_blob_filter',
    label='Blob Filter',
    category='mask',
    icon='Filter',
    description="Removes blobs based on area range from a binary mask. Eliminates noise or isolates specific objects.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[
        {'id': 'main',  'color': 'mask',  'label': 'Filtered Mask'},
        {'id': 'mask',  'color': 'mask',  'label': 'Mask (Legacy)'},
        {'id': 'count', 'color': 'scalar', 'label': 'Blob Count'},
    ],
    params=[
        {'id': 'min_area',     'type': 'int',    'default': 100, 'min': 1, 'max': 1000000, 'label': 'Min Area (px²)'},
        {'id': 'max_area',     'type': 'int',    'default': 0,   'min': 0, 'max': 1000000, 'label': 'Max Area (0=off)'},
        {'id': 'threshold',    'type': 'int',    'default': 127, 'min': 1, 'max': 254,     'label': 'Binary Threshold'},
        {'id': 'connectivity', 'type': 'int',    'default': 8,   'options': ['4', '8'],    'label': 'Connectivity'},
    ],
    colorable=True,
)
class BlobFilterNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'main': None, 'mask': None, 'count': 0}

        min_area     = int(params.get('min_area', 100))
        max_area     = int(params.get('max_area', 0))
        thresh_val   = int(params.get('threshold', 127))
        conn         = int(params.get('connectivity', 8))

        # Robust input normalization
        if mask.dtype == np.float32 or mask.dtype == np.float64:
            if mask.max() <= 1.01: # Assume 0-1 range
                mask = (mask * 255).astype(np.uint8)
            else:
                mask = mask.clip(0, 255).astype(np.uint8)
        
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        
        # Ensure uint8 for OpenCV
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)

        # Threshold to ensure strict binary
        _, binary = cv2.threshold(mask, thresh_val, 255, cv2.THRESH_BINARY)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            binary, connectivity=conn
        )

        # Vectorized filtering for speed
        out = np.zeros_like(binary)
        count = 0
        
        if num_labels > 1:
            # Extract areas of all components (skipping background at index 0)
            areas = stats[1:, cv2.CC_STAT_AREA]
            
            # Create a boolean mask of labels to keep
            keep_mask = (areas >= min_area)
            if max_area > 0:
                keep_mask &= (areas <= max_area)
            
            # Map labels to 255 or 0
            # label 0 (bg) -> 0
            # label i -> 255 if keep_mask[i-1] else 0
            label_map = np.zeros(num_labels, dtype=np.uint8)
            label_map[1:][keep_mask] = 255
            
            out = label_map[labels]
            count = int(np.sum(keep_mask))

        return {'main': out, 'mask': out, 'count': count}
