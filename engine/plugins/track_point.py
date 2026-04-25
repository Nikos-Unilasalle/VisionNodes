from registry import vision_node, NodeProcessor

@vision_node(
    type_id='geom_track_point',
    label='Track Point',
    category='track',
    icon='Target',
    description="Extracts the precise coordinates of a specific tracked landmark (e.g., joints).",
    inputs=[
        {'id': 'data', 'color': 'dict'},
        {'id': 'image', 'color': 'image'}
    ],
    outputs=[
        {'id': 'x', 'color': 'scalar'},
        {'id': 'y', 'color': 'scalar'},
        {'id': 'draw', 'color': 'dict'}
    ],
    params=[
        {'id': 'point_id', 'min': 0, 'max': 477, 'step': 1, 'default': 8},
        {'id': 'absolute', 'label': 'Absolute Coords', 'type': 'bool', 'default': False},
        {'id': 'thickness', 'min': 1, 'max': 20, 'step': 1, 'default': 5},
        {'id': 'r', 'min': 0, 'max': 255, 'step': 1, 'default': 0},
        {'id': 'g', 'min': 0, 'max': 255, 'step': 1, 'default': 255},
        {'id': 'b', 'min': 0, 'max': 255, 'step': 1, 'default': 0}
    ]
)
class TrackPointNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        out = {'x': 0.0, 'y': 0.0, 'draw': None}
        if not isinstance(data, dict): return out
        
        lms = data.get('landmarks', [])
        pt_id = int(params.get('point_id', 8))
        abs_calc = bool(int(params.get('absolute', 0)))
        
        if pt_id < 0 or pt_id >= len(lms): return out
        
        lm = lms[pt_id]
        x, y = lm['x'], lm['y']
        
        w_mult, h_mult = 1.0, 1.0
        if abs_calc:
            img = inputs.get('image')
            if img is not None:
                h_mult, w_mult = img.shape[:2]
            else:
                w_mult, h_mult = 640.0, 480.0
                
        out['x'] = x * w_mult
        out['y'] = y * h_mult
        
        out['draw'] = {
            '_type': 'graphics',
            'shape': 'point',
            'pts': [(x * w_mult if abs_calc else x, y * h_mult if abs_calc else y)],
            'relative': not abs_calc,
            'thickness': int(params.get('thickness', 5)),
            'r': int(params.get('r', 0)),
            'g': int(params.get('g', 255)),
            'b': int(params.get('b', 0))
        }
        return out
