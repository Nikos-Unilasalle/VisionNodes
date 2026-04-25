from __main__ import vision_node, NodeProcessor
import math

@vision_node(
    type_id='geom_track_line',
    label='Track Line',
    category='track',
    icon='Maximize',
    description="Calculates the distance in pixels between two tracked landmarks.",
    inputs=[
        {'id': 'data', 'color': 'dict'},
        {'id': 'image', 'color': 'image'}
    ],
    outputs=[
        {'id': 'distance', 'color': 'scalar'},
        {'id': 'draw', 'color': 'dict'}
    ],
    params=[
        {'id': 'pt_a', 'min': 0, 'max': 477, 'step': 1, 'default': 4},
        {'id': 'pt_b', 'min': 0, 'max': 477, 'step': 1, 'default': 8},
        {'id': 'absolute', 'label': 'Absolute Coords', 'type': 'bool', 'default': False},
        {'id': 'thickness', 'min': 1, 'max': 20, 'step': 1, 'default': 4},
        {'id': 'r', 'min': 0, 'max': 255, 'step': 1, 'default': 0},
        {'id': 'g', 'min': 0, 'max': 255, 'step': 1, 'default': 255},
        {'id': 'b', 'min': 0, 'max': 255, 'step': 1, 'default': 0}
    ]
)
class TrackLineNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        out = {'distance': 0.0, 'draw': None}
        if not isinstance(data, dict): return out
        
        lms = data.get('landmarks', [])
        pt_a = int(params.get('pt_a', 4))
        pt_b = int(params.get('pt_b', 8))
        abs_calc = bool(int(params.get('absolute', 0)))
        
        if pt_a < 0 or pt_a >= len(lms) or pt_b < 0 or pt_b >= len(lms): return out
        
        lm_a = lms[pt_a]
        lm_b = lms[pt_b]
        
        xa, ya = lm_a['x'], lm_a['y']
        xb, yb = lm_b['x'], lm_b['y']
        
        w_mult, h_mult = 1.0, 1.0
        if abs_calc:
            img = inputs.get('image')
            if img is not None:
                h_mult, w_mult = img.shape[:2]
            else:
                w_mult, h_mult = 640.0, 480.0
                
        dx = (xa - xb) * w_mult
        dy = (ya - yb) * h_mult
        dist = math.sqrt(dx*dx + dy*dy)
        out['distance'] = dist
        
        # Pour les graphiques on passe toujours les coordonnées relatives à l'image courante
        # de l'Overlay, sauf si abs_calc est vrai auquel cas on a calculé en base fixe.
        # Si abs_calc est faux, la distance renvoyée est "relative de 0 à 1" ce qui n'a pas 
        # grand sens physiquement mais reflète la demande.
        
        out['draw'] = {
            '_type': 'graphics',
            'shape': 'line',
            'pts': [(xa*w_mult if abs_calc else xa, ya*h_mult if abs_calc else ya), 
                    (xb*w_mult if abs_calc else xb, yb*h_mult if abs_calc else yb)],
            'relative': not abs_calc,
            'thickness': int(params.get('thickness', 4)),
            'r': int(params.get('r', 0)),
            'g': int(params.get('g', 255)),
            'b': int(params.get('b', 0))
        }
        return out
