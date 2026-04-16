from ..engine_core import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='draw_line',
    label='Draw Line',
    category='util',
    icon='Target',
    inputs=[
        {'id': 'x1', 'color': 'scalar'},
        {'id': 'y1', 'color': 'scalar'},
        {'id': 'x2', 'color': 'scalar'},
        {'id': 'y2', 'color': 'scalar'}
    ],
    outputs=[
        {'id': 'draw', 'color': 'dict'}
    ],
    params=[
        {'id': 'x1', 'type': 'float', 'default': 0.1, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y1', 'type': 'float', 'default': 0.1, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'x2', 'type': 'float', 'default': 0.9, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y2', 'type': 'float', 'default': 0.9, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'r', 'type': 'int', 'default': 0, 'min': 0, 'max': 255},
        {'id': 'g', 'type': 'int', 'default': 255, 'min': 0, 'max': 255},
        {'id': 'b', 'type': 'int', 'default': 0, 'min': 0, 'max': 255},
        {'id': 'thickness', 'type': 'int', 'default': 2, 'min': 1, 'max': 20}
    ]
)
class DrawLineNode(NodeProcessor):
    def process(self, inputs, params):
        x1 = inputs.get('x1', params.get('x1', 0.1))
        y1 = inputs.get('y1', params.get('y1', 0.1))
        x2 = inputs.get('x2', params.get('x2', 0.9))
        y2 = inputs.get('y2', params.get('y2', 0.9))
        
        return {
            'draw': {
                '_type': 'graphics',
                'shape': 'line',
                'pts': [(x1, y1), (x2, y2)],
                'relative': True,
                'r': int(params.get('r', 0)),
                'g': int(params.get('g', 255)),
                'b': int(params.get('b', 0)),
                'thickness': int(params.get('thickness', 2))
            }
        }
