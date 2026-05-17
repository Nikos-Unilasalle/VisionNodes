from registry import vision_node, NodeProcessor

@vision_node(
    type_id='draw_ellipse',
    label='Draw Ellipse',
    category='draw',
    icon='Circle',
    description="Defines an ellipse to be displayed over the video stream via Draw Overlay.",
    inputs=[
        {'id': 'cx',    'color': 'scalar', 'label': 'Center X'},
        {'id': 'cy',    'color': 'scalar', 'label': 'Center Y'},
        {'id': 'rx',    'color': 'scalar', 'label': 'Radius X'},
        {'id': 'ry',    'color': 'scalar', 'label': 'Radius Y'},
        {'id': 'angle', 'color': 'scalar', 'label': 'Angle (°)'},
    ],
    outputs=[
        {'id': 'draw', 'color': 'dict'}
    ],
    params=[
        {'id': 'cx',        'label': 'Center X',   'type': 'float', 'default': 0.5,  'min': 0.0, 'max': 1.0, 'step': 0.01},
        {'id': 'cy',        'label': 'Center Y',   'type': 'float', 'default': 0.5,  'min': 0.0, 'max': 1.0, 'step': 0.01},
        {'id': 'rx',        'label': 'Radius X',   'type': 'float', 'default': 0.2,  'min': 0.0, 'max': 1.0, 'step': 0.01},
        {'id': 'ry',        'label': 'Radius Y',   'type': 'float', 'default': 0.1,  'min': 0.0, 'max': 1.0, 'step': 0.01},
        {'id': 'angle',     'label': 'Angle (°)',  'type': 'float', 'default': 0.0,  'min': 0.0, 'max': 360.0, 'step': 1.0},
        {'id': 'color',     'label': 'Color',      'type': 'color', 'default': '#00FF00'},
        {'id': 'thickness', 'label': 'Thickness',  'type': 'int',   'default': 2,    'min': 1,   'max': 20},
        {'id': 'fill',      'label': 'Fill',       'type': 'bool',  'default': False},
    ]
)
class DrawEllipseNode(NodeProcessor):
    def process(self, inputs, params):
        cx    = float(inputs.get('cx',    params.get('cx',    0.5)))
        cy    = float(inputs.get('cy',    params.get('cy',    0.5)))
        rx    = float(inputs.get('rx',    params.get('rx',    0.2)))
        ry    = float(inputs.get('ry',    params.get('ry',    0.1)))
        angle = float(inputs.get('angle', params.get('angle', 0.0)))
        
        color = str(params.get('color', '#00FF00'))
        hex_c = color.lstrip('#')
        r, g, b = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)) if len(hex_c) == 6 else (0, 255, 0)

        return {
            'draw': {
                '_type':     'graphics',
                'shape':     'ellipse',
                'pts':       [(cx, cy)],
                'relative':  True,
                'rx':        rx,
                'ry':        ry,
                'angle':     angle,
                'color':     color,
                'r':         r,
                'g':         g,
                'b':         b,
                'thickness': int(params.get('thickness', 2)),
                'fill':      bool(params.get('fill', False)),
            }
        }
