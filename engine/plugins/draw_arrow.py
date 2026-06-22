from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_arrow',
    label='Draw Arrow',
    category='draw',
    icon='MoveRight',
    description="Draws an arrow from (x1,y1) to (x2,y2). Coordinates are normalized [0,1].",
    inputs=[
        {'id': 'x1', 'color': 'scalar'},
        {'id': 'y1', 'color': 'scalar'},
        {'id': 'x2', 'color': 'scalar'},
        {'id': 'y2', 'color': 'scalar'},
    ],
    outputs=[{'id': 'draw', 'color': 'dict'}],
    params=[
        {'id': '_sec_geometry', 'label': 'Geometry', 'type': 'section'},
        {'id': 'x1',        'label': 'X1',        'type': 'float', 'default': 0.2, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y1',        'label': 'Y1',        'type': 'float', 'default': 0.5, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'x2',        'label': 'X2',        'type': 'float', 'default': 0.8, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'y2',        'label': 'Y2',        'type': 'float', 'default': 0.5, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': '_sec_style', 'label': 'Style', 'type': 'section'},
        {'id': 'color',     'label': 'Color',     'type': 'color', 'default': '#FF6600'},
        {'id': 'thickness', 'label': 'Thickness', 'type': 'int',   'default': 2, 'min': 1, 'max': 20},
        {'id': 'tip_length','label': 'Tip Length','type': 'float', 'default': 0.3, 'min': 0.05, 'max': 1.0, 'step': 0.05},
    ]
)
class DrawArrowNode(NodeProcessor):
    def process(self, inputs, params):
        x1 = float(inputs.get('x1') if inputs.get('x1') is not None else params.get('x1', 0.2))
        y1 = float(inputs.get('y1') if inputs.get('y1') is not None else params.get('y1', 0.5))
        x2 = float(inputs.get('x2') if inputs.get('x2') is not None else params.get('x2', 0.8))
        y2 = float(inputs.get('y2') if inputs.get('y2') is not None else params.get('y2', 0.5))

        color  = str(params.get('color', '#FF6600'))
        hex_c  = color.lstrip('#')
        r, g, b = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)) if len(hex_c) == 6 else (255, 102, 0)

        return {
            'draw': {
                '_type':      'graphics',
                'shape':      'arrow',
                'pts':        [(x1, y1), (x2, y2)],
                'relative':   True,
                'color':      color,
                'r': r, 'g': g, 'b': b,
                'thickness':  int(params.get('thickness', 2)),
                'tip_length': float(params.get('tip_length', 0.3)),
            }
        }
