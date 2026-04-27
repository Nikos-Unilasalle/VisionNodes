from registry import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='geom_track_polygon',
    label='Track Polygon',
    category='track',
    icon='Target',
    description="Calculates the area of a zone defined by multiple tracked landmarks.",
    inputs=[
        {'id': 'data', 'color': 'dict'},
        {'id': 'image', 'color': 'image'}
    ],
    outputs=[
        {'id': 'area', 'color': 'scalar'},
        {'id': 'draw', 'color': 'dict'}
    ],
    params=[
        {'id': 'pt_1', 'min': -1, 'max': 477, 'step': 1, 'default': 0},
        {'id': 'pt_2', 'min': -1, 'max': 477, 'step': 1, 'default': 5},
        {'id': 'pt_3', 'min': -1, 'max': 477, 'step': 1, 'default': 9},
        {'id': 'pt_4', 'min': -1, 'max': 477, 'step': 1, 'default': 13},
        {'id': 'pt_5', 'min': -1, 'max': 477, 'step': 1, 'default': 17},
        {'id': 'pt_6', 'min': -1, 'max': 477, 'step': 1, 'default': -1},
        {'id': 'pt_7', 'min': -1, 'max': 477, 'step': 1, 'default': -1},
        {'id': 'pt_8', 'min': -1, 'max': 477, 'step': 1, 'default': -1},
        {'id': 'pt_9', 'min': -1, 'max': 477, 'step': 1, 'default': -1},
        {'id': 'pt_10', 'min': -1, 'max': 477, 'step': 1, 'default': -1},
        {'id': 'absolute', 'label': 'Absolute Coords', 'type': 'bool', 'default': False},
        {'id': 'fill',     'label': 'Fill',            'type': 'bool', 'default': True},
        {'id': 'thickness', 'min': 1, 'max': 20, 'step': 1, 'default': 2},
        {'id': 'r', 'min': 0, 'max': 255, 'step': 1, 'default': 0},
        {'id': 'g', 'min': 0, 'max': 255, 'step': 1, 'default': 255},
        {'id': 'b', 'min': 0, 'max': 255, 'step': 1, 'default': 0}
    ]
)
class TrackPolygonNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        out = {'area': 0.0, 'draw': None}
        if not isinstance(data, dict): return out
        
        lms = data.get('landmarks', [])
        
        valid_pts = []
        for i in range(1, 11):
            pid = int(params.get(f'pt_{i}', -1))
            if 0 <= pid < len(lms):
                valid_pts.append(lms[pid])
                
        if len(valid_pts) < 3: return out
        
        abs_calc = bool(int(params.get('absolute', 0)))
        w_mult, h_mult = 1.0, 1.0
        if abs_calc:
            img = inputs.get('image')
            if img is not None:
                h_mult, w_mult = img.shape[:2]
            else:
                w_mult, h_mult = 640.0, 480.0
                
        pts = [(p['x'] * w_mult, p['y'] * h_mult) for p in valid_pts]
        
        area = 0.0
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        area = abs(area) / 2.0
        
        out['area'] = area
        
        out['draw'] = {
            '_type': 'graphics',
            'shape': 'polygon',
            'pts': pts if abs_calc else [(p['x'], p['y']) for p in valid_pts],
            'relative': not abs_calc,
            'fill': bool(int(params.get('fill', 1))),
            'thickness': int(params.get('thickness', 2)),
            'r': int(params.get('r', 0)),
            'g': int(params.get('g', 255)),
            'b': int(params.get('b', 0))
        }
        return out
