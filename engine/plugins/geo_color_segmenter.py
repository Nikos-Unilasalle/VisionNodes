import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='geo_color_segmenter',
    label='Geo Color Segmenter',
    category='geology',
    icon='PieChart',
    description=(
        "Segments an image into multiple mineral phases based on color distance. "
        "Calculates surface area and percentage for each class. Best used on PPL or XPL images."
    ),
    inputs=[{'id': 'image', 'color': 'image', 'label': 'Input Image'}],
    outputs=[
        {'id': 'overlay',      'color': 'image',  'label': 'Visual Overlay'},
        {'id': 'labeled_mask', 'color': 'mask',   'label': 'Labeled Mask (0=bg, 1…4=phase)'},
        {'id': 'mask1',        'color': 'mask',   'label': 'Mask 1'},
        {'id': 'mask2',        'color': 'mask',   'label': 'Mask 2'},
        {'id': 'mask3',        'color': 'mask',   'label': 'Mask 3'},
        {'id': 'mask4',        'color': 'mask',   'label': 'Mask 4'},
        {'id': 'stats',        'color': 'dict',   'label': 'Statistics'},
        {'id': 'summary',      'color': 'string', 'label': 'Text Summary'},
    ],
    params=[
        {'id': 'use_lab', 'label': 'Perceptual Mode (CIELAB)', 'type': 'boolean', 'default': True},
        
        {'id': 'c1_active', 'label': 'Phase 1 Active', 'type': 'boolean', 'default': True},
        {'id': 'c1_label',  'label': 'Phase 1 Label',  'type': 'string',  'default': 'Phase 1'},
        {'id': 'c1_color',  'label': 'Phase 1 Color',  'type': 'color',   'default': '#FF00FF'},
        {'id': 'c1_tol',    'label': 'Phase 1 Tol.',   'type': 'int',     'default': 30, 'min': 1, 'max': 200},
        
        {'id': 'c2_active', 'label': 'Phase 2 Active', 'type': 'boolean', 'default': True},
        {'id': 'c2_label',  'label': 'Phase 2 Label',  'type': 'string',  'default': 'Phase 2'},
        {'id': 'c2_color',  'label': 'Phase 2 Color',  'type': 'color',   'default': '#00FFFF'},
        {'id': 'c2_tol',    'label': 'Phase 2 Tol.',   'type': 'int',     'default': 30, 'min': 1, 'max': 200},
        
        {'id': 'c3_active', 'label': 'Phase 3 Active', 'type': 'boolean', 'default': False},
        {'id': 'c3_label',  'label': 'Phase 3 Label',  'type': 'string',  'default': 'Phase 3'},
        {'id': 'c3_color',  'label': 'Phase 3 Color',  'type': 'color',   'default': '#FFFF00'},
        {'id': 'c3_tol',    'label': 'Phase 3 Tol.',   'type': 'int',     'default': 30, 'min': 1, 'max': 200},
        
        {'id': 'c4_active', 'label': 'Phase 4 Active', 'type': 'boolean', 'default': False},
        {'id': 'c4_label',  'label': 'Phase 4 Label',  'type': 'string',  'default': 'Phase 4'},
        {'id': 'c4_color',  'label': 'Phase 4 Color',  'type': 'color',   'default': '#00FF00'},
        {'id': 'c4_tol',    'label': 'Phase 4 Tol.',   'type': 'int',     'default': 30, 'min': 1, 'max': 200},
    ]
)
class GeoColorSegmenter(NodeProcessor):

    def _hex_to_bgr(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return (b, g, r)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None:
            return {}
        
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif len(image.shape) == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        
        h, w = image.shape[:2]
        total_px = h * w
        use_lab = params.get('use_lab', True)

        # Initialize all outputs with empty masks to ensure data flow
        labeled_mask = np.zeros((h, w), dtype=np.uint8)
        results = {
            'overlay': image.copy(),
            'labeled_mask': labeled_mask,
            'mask1': np.zeros((h, w), dtype=np.uint8),
            'mask2': np.zeros((h, w), dtype=np.uint8),
            'mask3': np.zeros((h, w), dtype=np.uint8),
            'mask4': np.zeros((h, w), dtype=np.uint8),
            'stats': {},
            'summary': 'No phases active. Check "Phase Active" boxes.'
        }
        
        # Prepare target colors and parameters
        phases = []
        for i in range(1, 5):
            if params.get(f'c{i}_active', False):
                color_hex = params.get(f'c{i}_color', '#FF00FF')
                bgr = self._hex_to_bgr(color_hex)
                label = params.get(f'c{i}_label', f'Phase {i}')
                tol = int(params.get(f'c{i}_tol', 30))
                phases.append({
                    'id': i,
                    'label': label,
                    'bgr': bgr,
                    'tol': tol
                })
        
        if not phases:
            return {'overlay': image, 'summary': 'No phases active.'}

        # Conversion for distance calculation
        if use_lab:
            working_img = cv2.cvtColor(image, cv2.COLOR_BGR2Lab).astype(np.float32)
            for p in phases:
                # Convert target BGR to Lab
                tmp = np.uint8([[p['bgr']]])
                p['target'] = cv2.cvtColor(tmp, cv2.COLOR_BGR2Lab)[0][0].astype(np.float32)
        else:
            working_img = image.astype(np.float32)
            for p in phases:
                p['target'] = np.array(p['bgr'], dtype=np.float32)

        # Process masks
        overlay = image.copy()
        stats_data = {}
        summary_lines = []
        
        for p in phases:
            # Calculate Euclidean distance in color space
            dist = np.sqrt(np.sum((working_img - p['target'])**2, axis=2))
            
            # Threshold distance
            mask = (dist <= p['tol']).astype(np.uint8) * 255
            
            # Area calculations
            area_px = int(np.count_nonzero(mask))
            area_pct = (area_px / total_px) * 100.0
            
            results[f'mask{p["id"]}'] = mask
            # Labeled mask: assign phase id where unassigned (first match wins)
            labeled_mask[mask == 255] = p['id']
            stats_data[p['label']] = round(area_pct, 2)
            summary_lines.append(f"{p['label']}: {area_pct:.1f}%")
            
            # Apply to overlay with half transparency
            color_mask = np.zeros_like(image)
            color_mask[:] = p['bgr']
            overlay = cv2.addWeighted(overlay, 1.0, cv2.bitwise_and(color_mask, color_mask, mask=mask), 0.5, 0)

        results['overlay'] = overlay
        results['labeled_mask'] = labeled_mask
        results['stats'] = stats_data
        results['summary'] = "\n".join(summary_lines)
        
        return results
