from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_point',
    label='Draw Point',
    category='draw',
    icon='Target',
    description="Defines a graphical point to overlay on the image.",
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
        {'id': 'color', 'label': 'Color', 'type': 'color', 'default': '#FF0000'},
        {'id': 'thickness', 'type': 'int', 'default': 5, 'min': 1, 'max': 20}
    ]
)
class DrawPointNode(NodeProcessor):
    def process(self, inputs, params):
        x = inputs.get('x', params.get('x', 0.5))
        y = inputs.get('y', params.get('y', 0.5))
        
        color = str(params.get('color', '#FF0000'))
        hex_c = color.lstrip('#')
        r, g, b = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)) if len(hex_c) == 6 else (255, 0, 0)
        
        return {
            'draw': {
                '_type': 'graphics',
                'shape': 'point',
                'pts': [(x, y)],
                'relative': True,
                'color': color,
                'r': r,
                'g': g,
                'b': b,
                'thickness': int(params.get('thickness', 5))
            }
        }
