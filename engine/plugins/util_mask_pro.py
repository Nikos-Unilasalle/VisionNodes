import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='util_label_filter_area',
    label='Label Area Filter',
    category='mask',
    icon='Target',
    description="Filters a label image (from Segmenter) by area. More precise than filtering a binary mask.",
    inputs=[{'id': 'labels', 'color': 'any'}],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'min_area_pct', 'label': 'Min Area (%)', 'type': 'number', 'default': 0.1, 'min': 0, 'max': 20, 'step': 0.05},
        {'id': 'min_area_px',  'label': 'Min Area (px)', 'type': 'number', 'default': 0,   'min': 0, 'max': 500000, 'step': 100},
        {'id': 'mode',         'label': 'Mode', 'type': 'enum', 'options': ['Keep Matches', 'Remove Matches'], 'default': 0}
    ]
)
class LabelAreaFilterNode(NodeProcessor):
    def process(self, inputs, params):
        labels = inputs.get('labels')
        if labels is None: return {'mask': None}
        
        # Labels should be int32 label image
        h, w = labels.shape[:2]
        total_px = h * w
        
        pct = float(params.get('min_area_pct', 0.1))
        px_min = float(params.get('min_area_px', 0))
        min_a = max(px_min, (pct / 100.0) * total_px)
        
        mode = int(params.get('mode', 0))
        
        # Efficiently calculate areas of all labels
        # bincount is very fast for non-negative ints
        # We need to flatten and handle negative markers (boundaries) if any
        flat = labels.flatten()
        # Watershed markers are often -1 (boundaries), 0 (unknown), 1...N (objects)
        # Shift everything to be positive for bincount
        offset = -np.min(flat) if len(flat) > 0 else 0
        counts = np.bincount((flat + offset).astype(np.int32))
        
        out_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Iterate over labels that exist in counts
        for i, count in enumerate(counts):
            real_label = i - offset
            if real_label <= 0: continue # Skip boundaries and background
            
            is_match = count >= min_a
            should_keep = is_match if mode == 0 else not is_match
            
            if should_keep:
                out_mask[labels == real_label] = 255
                
        return {'mask': out_mask}

@vision_node(
    type_id='mask_filter_area',
    label='Mask Area Filter',
    category='mask',
    icon='Filter',
    description="Filters connected components (blobs) based on their area as a % of the image. Adaptive to resolution.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'min_area_pct', 'label': 'Min Area (%)', 'type': 'number', 'default': 0.1, 'min': 0, 'max': 20, 'step': 0.05},
        {'id': 'min_area_px',  'label': 'Min Area (px)', 'type': 'number', 'default': 0,   'min': 0, 'max': 500000, 'step': 100},
        {'id': 'fill_holes',   'label': 'Fill Holes (Contours mode)', 'type': 'boolean', 'default': False},
        {'id': 'invert',       'label': 'Invert Input', 'type': 'boolean', 'default': False},
        {'id': 'mode',         'label': 'Mode', 'type': 'enum', 'options': ['Keep Matches', 'Remove Matches'], 'default': 0}
    ]
)
class MaskAreaFilterNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {'mask': None}
        
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        
        h, w = mask.shape[:2]
        total_px = h * w
        
        pct = float(params.get('min_area_pct', 0.1))
        px_min = float(params.get('min_area_px', 0))
        
        # Effective min area is either px or pct based
        min_a = max(px_min, (pct / 100.0) * total_px)
        
        if params.get('invert', False):
            mask = cv2.bitwise_not(mask)

        if params.get('fill_holes', False):
            # Close gaps and fill enclosed regions
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            filled = np.zeros_like(mask)
            for cnt in contours:
                cv2.drawContours(filled, [cnt], -1, 255, -1)
            mask = filled
        
        mode = int(params.get('mode', 0))
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        out_mask = np.zeros_like(mask)
        
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            is_match = area >= min_a
            
            should_keep = is_match if mode == 0 else not is_match
            if should_keep:
                out_mask[labels == i] = 255
                
        return {'mask': out_mask}

@vision_node(
    type_id='util_image_masking',
    label='Image Masking',
    category='mask',
    icon='Layers',
    description="Applies a binary mask to an image. Pixels outside the mask are filled with a specific background color.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'bg_color', 'label': 'BG Color', 'type': 'color', 'default': '#000000'}
    ]
)
class ImageMaskingNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        mask = inputs.get('mask')
        if img is None: return {'main': None}
        if mask is None: return {'main': img}
        
        # Ensure mask is 8-bit grayscale
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        
        # Resize mask if needed
        if mask.shape[:2] != img.shape[:2]:
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]))
            
        # Parse background color
        hex_color = str(params.get('bg_color', '#000000')).lstrip('#')
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except:
            r, g, b = 0, 0, 0
            
        bg = np.full_like(img, (b, g, r))
        
        # Apply mask
        # mask is uint8 (0 or 255)
        # Convert to boolean for indexing
        mask_bool = mask > 0
        
        out = bg.copy()
        out[mask_bool] = img[mask_bool]
        
        return {'main': out}
