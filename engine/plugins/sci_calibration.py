from registry import vision_node, NodeProcessor
import numpy as np
import cv2

@vision_node(
    type_id='sci_calibration',
    label='Unit Calibration',
    category='measure',
    icon='Scaling',
    description="Converts pixel measurements (length or area) into real-world units based on a calibration factor.",
    inputs=[{'id': 'input', 'color': 'any'}],
    outputs=[{'id': 'output', 'color': 'any'}],
    params=[
        {'id': 'factor',     'label': 'Pixels per Unit', 'type': 'float', 'default': 100.0},
        {'id': 'dimension',  'label': 'Dimension',       'type': 'string', 'default': 'Area', 'options': ['Length', 'Area']},
        {'id': 'unit_name',  'label': 'Unit Name',       'type': 'string', 'default': 'cm'},
    ]
)
class CalibrationNode(NodeProcessor):
    def process(self, inputs, params):
        val = inputs.get('input')
        
        # Fallback for stale connections or mismatched IDs
        if val is None:
            relevant_inputs = [v for k, v in inputs.items() if k not in ['raw_frame', 'image']]
            if relevant_inputs:
                val = relevant_inputs[0]

        if val is None:
            return {'output': None, 'display_value': "---"}
            
        try:
            # Handle list input if necessary
            is_list = isinstance(val, (list, np.ndarray, tuple))
            data = np.array(val) if is_list else float(val)
                
            factor = float(params.get('factor', 100.0))
            dim = params.get('dimension', 'Area')
            
            if factor <= 0:
                res = data
            else:
                if dim == 'Length':
                    res = data / factor
                else:
                    res = data / (factor ** 2)
                
            unit = params.get('unit_name', 'cm') + ('²' if dim == 'Area' else '')
            
            # Formatted display for the node UI
            if is_list:
                display = f"{len(res)} items"
            else:
                display = f"{res:.3f} {unit}"

            return {
                'main': res.tolist() if is_list else float(res),
                'output': res.tolist() if is_list else float(res),
                'display_value': display,
                'unit': unit
            }
        except Exception as e:
            return {'output': None, 'display_value': "Error"}

@vision_node(
    type_id='sci_interactive_calibration',
    label='Visual Calibration',
    category='measure',
    icon='Scaling',
    description="Calculates a calibration factor by drawing a line of a known physical length on the image.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'factor', 'color': 'scalar', 'label': 'Px/Unit'},
        {'id': 'unit',   'color': 'scalar', 'label': 'Unit Name'},
        {'id': 'main',   'color': 'image'}
    ],
    params=[
        {'id': 'points',   'label': 'Line Points', 'type': 'string', 'default': '[]'}, 
        {'id': 'real_len', 'label': 'Known Length', 'type': 'float', 'default': 10.0},
        {'id': 'unit',     'label': 'Unit Name',   'type': 'string', 'default': 'mm'}
    ]
)
class InteractiveCalibrationNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'factor': 1.0}
        
        h, w = img.shape[:2]
        import json
        try:
            pts = json.loads(params.get('points', '[]'))
        except: pts = []
        
        px_per_unit = 1.0
        display = "Draw Line"
        
        out_img = img.copy()
        if len(out_img.shape) == 2:
            out_img = cv2.cvtColor(out_img, cv2.COLOR_GRAY2BGR)

        if len(pts) >= 2:
            p1, p2 = pts[0], pts[1]
            dx = (p2['x'] - p1['x']) * w
            dy = (p2['y'] - p1['y']) * h
            px_dist = np.sqrt(dx**2 + dy**2)
            
            real_len = float(params.get('real_len', 10.0))
            unit = params.get('unit', 'mm')
            
            if px_dist > 0 and real_len > 0:
                px_per_unit = px_dist / real_len
                display = f"{px_per_unit:.2f} px/{unit}"
            
            # Draw line for visual feedback
            cv2.line(out_img, (int(p1['x']*w), int(p1['y']*h)), (int(p2['x']*w), int(p2['y']*h)), (255, 0, 255), 3)
            cv2.circle(out_img, (int(p1['x']*w), int(p1['y']*h)), 5, (255, 255, 255), -1)
            cv2.circle(out_img, (int(p2['x']*w), int(p2['y']*h)), 5, (255, 255, 255), -1)

        # Encode preview to base64
        import base64
        preview_b64 = None
        try:
            # Downscale for performance
            ph, pw = 480, int(480 * (w/h))
            pimg = cv2.resize(out_img, (pw, ph))
            _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 80])
            preview_b64 = base64.b64encode(buf).decode('utf-8')
        except: pass

        unit = params.get('unit', 'mm')
        return {
            'factor': float(px_per_unit),
            'unit': unit,
            'main': out_img,
            'main_preview': preview_b64,
            'display_value': display
        }
