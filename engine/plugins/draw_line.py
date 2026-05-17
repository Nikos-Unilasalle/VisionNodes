from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_line',
    label='Draw Line',
    category='draw',
    icon='Target',
    description="Defines a line between two coordinates for graphical overlay.",
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
        {'id': 'color', 'label': 'Color', 'type': 'color', 'default': '#00FF00'},
        {'id': 'thickness', 'type': 'int', 'default': 2, 'min': 1, 'max': 20}
    ]
)
class DrawLineNode(NodeProcessor):
    def process(self, inputs, params):
        x1 = inputs.get('x1', params.get('x1', 0.1))
        y1 = inputs.get('y1', params.get('y1', 0.1))
        x2 = inputs.get('x2', params.get('x2', 0.9))
        y2 = inputs.get('y2', params.get('y2', 0.9))
        
        color = str(params.get('color', '#00FF00'))
        hex_c = color.lstrip('#')
        r, g, b = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)) if len(hex_c) == 6 else (0, 255, 0)
        
        return {
            'draw': {
                '_type': 'graphics',
                'shape': 'line',
                'pts': [(x1, y1), (x2, y2)],
                'relative': True,
                'color': color,
                'r': r,
                'g': g,
                'b': b,
                'thickness': int(params.get('thickness', 2))
            }
        }
