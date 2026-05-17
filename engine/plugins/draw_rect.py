from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_rect',
    label='Draw Rect',
    category='draw',
    icon='Box',
    description="Defines a rectangle to be displayed over the video stream.",
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
        {'id': 'x1', 'type': 'float', 'default': 0.2, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y1', 'type': 'float', 'default': 0.2, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'x2', 'type': 'float', 'default': 0.8, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y2', 'type': 'float', 'default': 0.8, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'color', 'label': 'Color', 'type': 'color', 'default': '#0000FF'},
        {'id': 'thickness', 'type': 'int', 'default': 2, 'min': 1, 'max': 20},
        {'id': 'fill', 'label': 'Fill', 'type': 'bool', 'default': False}
    ]
)
class DrawRectNode(NodeProcessor):
    def process(self, inputs, params):
        x1 = inputs.get('x1', params.get('x1', 0.2))
        y1 = inputs.get('y1', params.get('y1', 0.2))
        x2 = inputs.get('x2', params.get('x2', 0.8))
        y2 = inputs.get('y2', params.get('y2', 0.8))
        
        color = str(params.get('color', '#0000FF'))
        hex_c = color.lstrip('#')
        r, g, b = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)) if len(hex_c) == 6 else (0, 0, 255)
        
        return {
            'draw': {
                '_type': 'graphics',
                'shape': 'rect',
                'pts': [(x1, y1), (x2, y2)],
                'relative': True,
                'color': color,
                'r': r,
                'g': g,
                'b': b,
                'thickness': int(params.get('thickness', 2)),
                'fill': bool(params.get('fill', 0))
            }
        }
