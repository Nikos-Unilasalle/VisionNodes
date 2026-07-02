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
        {'id': 'circ_min',     'type': 'float',  'default': 0.0, 'min': 0.0, 'max': 1.0, 'step': 0.01,
         'label': 'Circularity min'},
        {'id': 'circ_max',     'type': 'float',  'default': 0.0, 'min': 0.0, 'max': 1.0, 'step': 0.01,
         'label': 'Circularity max (0=off)'},
        {'id': 'elong_min',    'type': 'float',  'default': 1.0, 'min': 1.0, 'max': 100.0, 'step': 0.1,
         'label': 'Elongation min (major/minor)'},
        {'id': 'elong_max',    'type': 'float',  'default': 0.0, 'min': 0.0, 'max': 100.0, 'step': 0.1,
         'label': 'Elongation max (0=off)'},
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
        circ_min     = float(params.get('circ_min', 0.0))
        circ_max     = float(params.get('circ_max', 0.0))    # 0 = off
        elong_min    = float(params.get('elong_min', 1.0))
        elong_max    = float(params.get('elong_max', 0.0))   # 0 = off
        thresh_val   = int(params.get('threshold', 127))
        conn         = int(params.get('connectivity', 8))

        # Robust input normalization -> uint8 grayscale spanning 0..255.
        # Handles bool, 0/1 int masks, 0-1 floats, 0-255 — otherwise a 0/1 mask
        # would be wiped out by the 127 threshold ("outputs nothing").
        if mask.dtype == bool:
            mask = mask.astype(np.uint8) * 255
        elif mask.dtype == np.float32 or mask.dtype == np.float64:
            mx = float(np.nanmax(mask)) if mask.size else 0.0
            mask = (mask * 255.0) if mx <= 1.01 else mask.clip(0, 255)
            mask = np.nan_to_num(mask).astype(np.uint8)

        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

        if mask.dtype != np.uint8:
            mask = mask.clip(0, 255).astype(np.uint8)

        # Binary 0/1 integer masks → 0/255 so the threshold keeps them
        if mask.size and mask.max() <= 1:
            mask = mask * 255

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

            # Area filter (vectorized)
            keep_mask = (areas >= min_area)
            if max_area > 0:
                keep_mask &= (areas <= max_area)

            # Shape filters (circularity / elongation) — only when active, per surviving label
            shape_active = (circ_min > 0.0) or (circ_max > 0.0) or (elong_min > 1.0) or (elong_max > 0.0)
            if shape_active:
                for i in range(1, num_labels):
                    if not keep_mask[i - 1]:
                        continue
                    circ, elong = self._shape_metrics(labels, stats, i)
                    if circ < circ_min:
                        keep_mask[i - 1] = False
                    elif circ_max > 0.0 and circ > circ_max:
                        keep_mask[i - 1] = False
                    elif elong < elong_min:
                        keep_mask[i - 1] = False
                    elif elong_max > 0.0 and elong > elong_max:
                        keep_mask[i - 1] = False

            # Map surviving labels to 255 (preserves exact pixels, incl. holes)
            label_map = np.zeros(num_labels, dtype=np.uint8)
            label_map[1:][keep_mask] = 255
            out = label_map[labels]
            count = int(np.sum(keep_mask))

        return {'main': out, 'mask': out, 'count': count}

    @staticmethod
    def _shape_metrics(labels, stats, i):
        """Circularity (4πA/P², clamped ≤1) and elongation (major/minor axis) of label i."""
        x = int(stats[i, cv2.CC_STAT_LEFT]);  y = int(stats[i, cv2.CC_STAT_TOP])
        w = int(stats[i, cv2.CC_STAT_WIDTH]); h = int(stats[i, cv2.CC_STAT_HEIGHT])
        area = float(stats[i, cv2.CC_STAT_AREA])
        sub = (labels[y:y + h, x:x + w] == i).astype(np.uint8)
        cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return 0.0, 1.0
        c = max(cnts, key=cv2.contourArea)
        per = cv2.arcLength(c, True)
        circ = min(4.0 * np.pi * area / (per * per), 1.0) if per > 0 else 0.0
        # Elongation from second-order moments (rotation-invariant, robust for any shape)
        mu = cv2.moments(sub, binaryImage=True)
        m00 = mu['m00']
        if m00 > 0:
            a = mu['mu20'] / m00; b = mu['mu11'] / m00; d = mu['mu02'] / m00
            common = np.sqrt(max((a - d) ** 2 + 4.0 * b * b, 0.0))
            l1 = (a + d + common) / 2.0
            l2 = (a + d - common) / 2.0
            elong = float(np.sqrt(l1 / l2)) if l2 > 1e-9 else 1e3
        else:
            elong = 1.0
        return float(circ), float(elong)
