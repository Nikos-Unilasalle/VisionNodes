import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='feat_seeds_from_boundaries',
    label='Seeds from Boundaries',
    category='visualize',
    icon='Target',
    description="Generates seed markers for Watershed from a boundary/corner mask. Finds the centers of the 'empty' regions.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[
        {'id': 'markers', 'color': 'any'},
        {'id': 'main',    'color': 'image'},
        {'id': 'dist_map', 'color': 'image'},
        {'id': 'count',   'color': 'scalar'}
    ],
    params=[
        {'id': 'threshold',   'label': 'Peak Sensitivity (%)', 'type': 'number', 'default': 50, 'min': 1, 'max': 99, 'step': 1},
        {'id': 'dilation',    'label': 'Marker Dilation',    'type': 'number', 'default': 2, 'min': 0, 'max': 10},
        {'id': 'invert_mask', 'label': 'Invert Input Mask',  'type': 'boolean', 'default': False},
    ]
)
class SeedsFromBoundariesNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {'markers': None, 'main': None, 'dist_map': None, 'count': 0}
        
        # Ensure grayscale uint8
        if len(mask.shape) == 3:
            if mask.shape[2] >= 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            else:
                mask = mask[:, :, 0]
        mask = mask.astype(np.uint8)
        
        # 1. Handle inversion
        if params.get('invert_mask', False):
            proc_mask = mask
        else:
            proc_mask = cv2.bitwise_not(mask)
        
        # 2. Distance Transform (Distance to the closest black pixel)
        dist_transform = cv2.distanceTransform(proc_mask, cv2.DIST_L2, 5)
        
        # 3. Find peaks
        peak_thresh_pct = float(params.get('threshold', 50)) / 100.0
        max_dist = dist_transform.max()
        if max_dist <= 0: return {'markers': None, 'main': None, 'dist_map': None, 'count': 0}
        
        _, peaks = cv2.threshold(dist_transform, peak_thresh_pct * max_dist, 255, cv2.THRESH_BINARY)
        peaks = np.uint8(peaks)
        
        # 4. Optional Dilation
        dil = int(params.get('dilation', 2))
        if dil > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dil*2+1, dil*2+1))
            peaks = cv2.dilate(peaks, kernel)
        
        # 5. Connected components
        count, markers = cv2.connectedComponents(peaks)
        
        # Visualization
        vis = (markers.astype(np.float32) * (255.0 / max(1, count))).astype(np.uint8)
        color_vis = cv2.applyColorMap(vis, cv2.COLORMAP_TURBO)
        color_vis[markers == 0] = 0
        
        # Distance map visualization
        dist_vis = cv2.normalize(dist_transform, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        return {
            'markers': markers,
            'main': color_vis,
            'dist_map': dist_vis,
            'count': count - 1
        }

@vision_node(
    type_id='sci_general_segmenter',
    label='General Segmenter',
    category='analytics',
    icon='Grid',
    description="Versatile segmentation tool. Combines contrast enhancement (CLAHE), seed detection, and watershed for object separation.",
    inputs=[
        {'id': 'image',   'color': 'image'},
        {'id': 'markers', 'color': 'any'}  # Optional external seeds
    ],
    outputs=[
        {'id': 'main',    'color': 'image'},
        {'id': 'mask',    'color': 'mask'},
        {'id': 'count',   'color': 'scalar'}
    ],
    params=[
        {'id': 'sensitivity', 'label': 'Peak Sensitivity', 'type': 'number', 'default': 30, 'min': 1, 'max': 90},
        {'id': 'contrast',    'label': 'Auto Contrast (CLAHE)', 'type': 'boolean', 'default': True},
        {'id': 'smoothing',   'label': 'Denoise (Blur)',  'type': 'number', 'default': 3, 'min': 0, 'max': 10},
        {'id': 'boundary',    'label': 'Boundary Strength', 'type': 'number', 'default': 5, 'min': 0, 'max': 20},
        {'id': 'min_size',    'label': 'Min Object Size',   'type': 'number', 'default': 50, 'min': 0, 'max': 5000},
        {'id': 'viz_mode',    'label': 'Visualization',     'type': 'enum', 'options': ['Boundaries', 'Colored Objects', 'Full Overlay'], 'default': 2},
    ]
)
class GeneralSegmenterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None, 'mask': None, 'count': 0}
        
        # 1. Pre-process (Grayscale & Contrast)
        if len(img.shape) == 3 and img.shape[2] >= 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif len(img.shape) == 3 and img.shape[2] == 1:
            gray = img[:, :, 0]
        else:
            gray = img
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            
        if params.get('contrast', True):
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)

        sm = int(params.get('smoothing', 3))
        if sm > 0:
            gray = cv2.GaussianBlur(gray, (sm*2+1, sm*2+1), 0)
            
        # 2. Boundary detection (using original joint logic but generalized)
        boundary_val = int(params.get('boundary', 5))
        if boundary_val > 0:
            _, b_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            min_len = boundary_val * 5
            lines = cv2.HoughLinesP(b_mask, 1, np.pi/180, threshold=50, minLineLength=min_len, maxLineGap=min_len//2)
            
            straight_mask = np.zeros_like(b_mask)
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    cv2.line(straight_mask, (x1, y1), (x2, y2), 255, 3)
            
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(straight_mask))
            kernel_fill = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_fill)
        else:
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 3. Find Seeds (Markers)
        external_markers = inputs.get('markers')
        if external_markers is not None:
            markers = external_markers.astype(np.int32)
            num = int(np.max(markers)) + 1
        else:
            dist = cv2.distanceTransform(thresh, cv2.DIST_L2, 5)
            dist = cv2.GaussianBlur(dist, (5, 5), 0)
            sens = float(params.get('sensitivity', 30)) / 100.0
            _, peaks = cv2.threshold(dist, sens * dist.max(), 255, cv2.THRESH_BINARY)
            num, markers = cv2.connectedComponents(np.uint8(peaks))
        
        # 4. Watershed
        markers = cv2.watershed(img, markers.astype(np.int32))
        
        # 5. Size Filtering
        min_size = int(params.get('min_size', 50))
        if min_size > 0:
            new_markers = np.zeros_like(markers)
            counts = np.bincount(markers[markers > 0].flatten())
            valid_ids = np.where(counts >= min_size)[0]
            # Remap valid IDs to be contiguous
            for i, old_id in enumerate(valid_ids, 1):
                new_markers[markers == old_id] = i
            markers = new_markers
            count = len(valid_ids)
        else:
            count = num - 1
            
        # 6. Result Construction
        viz_mode = int(params.get('viz_mode', 2))
        n = max(1, count)
        vis_stones = (np.clip(markers, 0, None).astype(np.float32) * (255.0 / n)).astype(np.uint8)
        colored = cv2.applyColorMap(vis_stones, cv2.COLORMAP_TURBO)
        colored[markers <= 0] = 0
        
        res = img.copy()
        boundary_mask = (markers == -1)
        res[boundary_mask] = [0, 0, 255]
        
        if viz_mode == 0: # Boundaries
            out = res
        elif viz_mode == 1: # Colored
            out = cv2.addWeighted(img, 0.4, colored, 0.6, 0)
        else: # Both
            blended = cv2.addWeighted(img, 0.4, colored, 0.6, 0)
            blended[markers == -1] = [0, 0, 255]
            out = blended
            
        mask_out = np.zeros_like(gray)
        mask_out[markers > 0] = 255
        
        return {
            'main': out,
            'mask': mask_out,
            'count': count
        }

@vision_node(
    type_id='filter_linearity',
    label='Linear Feature Filter',
    category='cv',
    icon='Slash',
    description="Filters out non-linear noise and keeps only straight segments at any angle.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'main',  'color': 'image'},
        {'id': 'mask',  'color': 'mask'}
    ],
    params=[
        {'id': 'min_length',  'label': 'Min Length',      'type': 'number', 'default': 25, 'min': 5, 'max': 500},
        {'id': 'thickness',   'label': 'Line Thickness',  'type': 'number', 'default': 3, 'min': 1, 'max': 10},
        {'id': 'threshold',   'label': 'Sensitivity',     'type': 'number', 'default': 50, 'min': 1, 'max': 200},
    ]
)
class LinearFeatureFilterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None, 'mask': None}
        
        if len(img.shape) == 3:
            if img.shape[2] >= 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img[:, :, 0]
        else:
            gray = img
            
        # Ensure uint8 for thresholding
        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            
        # Detect joints / dark lines
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        min_len = int(params.get('min_length', 25))
        thresh = int(params.get('threshold', 50))
        thick = int(params.get('thickness', 3))
        
        lines = cv2.HoughLinesP(mask, 1, np.pi/180, threshold=thresh, minLineLength=min_len, maxLineGap=min_len//2)
        
        out_mask = np.zeros_like(gray)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(out_mask, (x1, y1), (x2, y2), 255, thick)
        
        # Output as black and white (main) and binary (mask)
        return {
            'main': cv2.cvtColor(out_mask, cv2.COLOR_GRAY2BGR),
            'mask': out_mask
        }

@vision_node(
    type_id='mask_region_sealer',
    label='Region Sealer',
    category='mask',
    icon='Maximize',
    description="Bridges gaps in boundary masks and fills closed regions to create solid blobs.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'gap_tolerance', 'label': 'Gap Tolerance', 'type': 'number', 'default': 5, 'min': 1, 'max': 50},
        {'id': 'fill_regions',  'label': 'Fill Regions',  'type': 'boolean', 'default': True},
        {'id': 'min_area',      'label': 'Min Area',      'type': 'number', 'default': 100, 'min': 0, 'max': 5000},
    ]
)
class RegionSealerNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {'mask': None}
        
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        
        tol = int(params.get('gap_tolerance', 5))
        fill = params.get('fill_regions', True)
        min_area = int(params.get('min_area', 100))
        
        # 1. Close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tol, tol))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        if fill:
            # 2. Find and fill regions
            # Invert to find 'holes' between the lines
            inv = cv2.bitwise_not(closed)
            contours, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            filled = np.zeros_like(mask)
            for cnt in contours:
                if cv2.contourArea(cnt) >= min_area:
                    cv2.drawContours(filled, [cnt], -1, 255, -1)
            return {'mask': filled}
        
        return {'mask': closed}

@vision_node(
    type_id='filter_linear_direction',
    label='Linear Direction Filter',
    category='cv',
    icon='Compass',
    description="Suppresses or isolates linear elements based on their orientation (angle in degrees).",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main',  'color': 'image'},
        {'id': 'mask',  'color': 'mask'}
    ],
    params=[
        {'id': 'angle',       'label': 'Target Angle (°)', 'type': 'number', 'default': 0, 'min': 0, 'max': 180},
        {'id': 'tolerance',   'label': 'Tolerance (°)',    'type': 'number', 'default': 10, 'min': 1, 'max': 90},
        {'id': 'min_length',  'label': 'Min Length',       'type': 'number', 'default': 20, 'min': 5, 'max': 500},
        {'id': 'extend',      'label': 'Extension (px)',   'type': 'number', 'default': 0,  'min': 0, 'max': 100},
        {'id': 'thickness',   'label': 'Erase Thickness',  'type': 'number', 'default': 5,  'min': 1, 'max': 50},
        {'id': 'mode',        'label': 'Mode',             'type': 'enum', 'options': ['Suppress (Remove)', 'Isolate (Keep)'], 'default': 0},
    ]
)
class LinearDirectionFilterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None, 'mask': None}
        
        # 1. Grayscale conversion
        if len(img.shape) == 3:
            if img.shape[2] >= 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img[:, :, 0]
        else:
            gray = img
            
        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            
        # 2. Thresholding to find features
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        target_angle = float(params.get('angle', 0))
        tolerance = float(params.get('tolerance', 10))
        min_len = int(params.get('min_length', 20))
        extend = int(params.get('extend', 0))
        thick = int(params.get('thickness', 5))
        mode = int(params.get('mode', 0))
        
        # 3. Detect lines
        lines = cv2.HoughLinesP(binary, 1, np.pi/180, threshold=30, minLineLength=min_len, maxLineGap=min_len//2)
        
        mask_overlay = np.zeros_like(gray)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Angle in degrees [0, 180]
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
                
                # Distance check with wrap-around
                diff = abs(angle - target_angle)
                if diff > 90: diff = 180 - diff
                
                match = (diff <= tolerance)
                
                # Extend line if requested
                if extend > 0:
                    dx, dy = x2 - x1, y2 - y1
                    dist = np.sqrt(dx**2 + dy**2)
                    if dist > 0:
                        ex, ey = (dx / dist) * extend, (dy / dist) * extend
                        x1, y1 = int(x1 - ex), int(y1 - ey)
                        x2, y2 = int(x2 + ex), int(y2 + ey)

                # If we want to REMOVE (Suppress), we draw the matches to subtract them later
                # If we want to KEEP (Isolate), we draw the NON-matches to subtract them later
                if mode == 0: # Suppress
                    if match:
                        cv2.line(mask_overlay, (x1, y1), (x2, y2), 255, thick)
                else: # Isolate
                    if match:
                        cv2.line(mask_overlay, (x1, y1), (x2, y2), 255, thick)
        
        # 4. Result Construction
        if mode == 0: # Suppress
            # Remove detected lines from original binary
            res_mask = cv2.subtract(binary, mask_overlay)
        else: # Isolate
            # Use only the detected (and extended) lines
            res_mask = mask_overlay
        
        return {
            'main': cv2.cvtColor(res_mask, cv2.COLOR_GRAY2BGR),
            'mask': res_mask
        }

@vision_node(
    type_id='filter_directional_morphology',
    label='Directional Morphology',
    category='cv',
    icon='StretchHorizontal',
    description="Performs morphological operations (Dilate, Close, etc.) along a specific axis (Horizontal or Vertical).",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'axis',      'label': 'Axis',      'type': 'enum', 'options': ['Horizontal', 'Vertical'], 'default': 0},
        {'id': 'operation', 'label': 'Operation', 'type': 'enum', 'options': ['Dilate', 'Erode', 'Open', 'Close'], 'default': 0},
        {'id': 'size',      'label': 'Size (px)', 'type': 'number', 'default': 5, 'min': 1, 'max': 100},
    ]
)
class DirectionalMorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {'mask': None}
        
        # Ensure 8-bit grayscale
        if len(mask.shape) == 3:
            if mask.shape[2] >= 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            else:
                mask = mask[:, :, 0]
        
        axis = int(params.get('axis', 0))
        op_idx = int(params.get('operation', 0))
        size = int(params.get('size', 5))
        
        # Create directional kernel
        if axis == 0: # Horizontal
            kernel = np.ones((1, size), np.uint8)
        else: # Vertical
            kernel = np.ones((size, 1), np.uint8)
            
        if op_idx == 0: # Dilate
            res = cv2.dilate(mask, kernel)
        elif op_idx == 1: # Erode
            res = cv2.erode(mask, kernel)
        elif op_idx == 2: # Open
            res = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        else: # Close
            res = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
        return {'mask': res}
