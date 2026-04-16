from __main__ import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='draw_point',
    label='Draw Point',
    category='util',
    icon='Target',
    inputs=[
        {'id': 'x', 'color': 'scalar'},
        {'id': 'y', 'color': 'scalar'}
    ],
    outputs=[
        {'id': 'draw', 'color': 'dict'}
    ],
    params=[
        {'id': 'x', 'type': 'float', 'default': 0.5, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y', 'type': 'float', 'default': 0.5, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'r', 'type': 'int', 'default': 255, 'min': 0, 'max': 255},
        {'id': 'g', 'type': 'int', 'default': 0, 'min': 0, 'max': 255},
        {'id': 'b', 'type': 'int', 'default': 0, 'min': 0, 'max': 255},
        {'id': 'thickness', 'type': 'int', 'default': 5, 'min': 1, 'max': 20}
    ]
)
class DrawPointNode(NodeProcessor):
    def process(self, inputs, params):
        x = inputs.get('x', params.get('x', 0.5))
        y = inputs.get('y', params.get('y', 0.5))
        
        return {
            'draw': {
                '_type': 'graphics',
                'shape': 'point',
                'pts': [(x, y)],
                'relative': True,
                'r': int(params.get('r', 255)),
                'g': int(params.get('g', 0)),
                'b': int(params.get('b', 0)),
                'thickness': int(params.get('thickness', 5))
            }
        }
