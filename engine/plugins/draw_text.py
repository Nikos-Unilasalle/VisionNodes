from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='draw_text',
    label='Draw Text',
    category='drawing',
    icon='Type',
    description="Creates a text graphic element that can be displayed or repeated.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'x', 'color': 'scalar'},
        {'id': 'y', 'color': 'scalar'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}, {'id': 'graphic', 'color': 'dict'}],
    params=[
        {'id': 'text', 'label': 'Text', 'type': 'string', 'default': 'Hello'},
        {'id': 'x', 'label': 'X Pos', 'type': 'scalar', 'min': 0, 'max': 1, 'step': 0.01, 'default': 0.5},
        {'id': 'y', 'label': 'Y Pos', 'type': 'scalar', 'min': 0, 'max': 1, 'step': 0.01, 'default': 0.5},
        {'id': 'font_scale', 'label': 'Size', 'type': 'scalar', 'min': 0.1, 'max': 5, 'step': 0.1, 'default': 1.0},
        {'id': 'thickness', 'label': 'Thickness', 'type': 'scalar', 'min': 1, 'max': 10, 'step': 1, 'default': 2},
        {'id': 'r', 'label': 'Red', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255},
        {'id': 'g', 'label': 'Green', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255},
        {'id': 'b', 'label': 'Blue', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255}
    ]
)
class DrawTextNode(NodeProcessor):
    def process(self, inputs, params):
        text = str(params.get('text', 'Hello'))
        
        # Priority to inputs, then params
        x = float(inputs.get('x', params.get('x', 0.5)))
        y = float(inputs.get('y', params.get('y', 0.5)))
        
        scale = float(params.get('font_scale', 1.0))
        thick = int(params.get('thickness', 2))
        r, g, b = int(params.get('r', 255)), int(params.get('g', 255)), int(params.get('b', 255))
        
        hex_color = '#%02x%02x%02x' % (r, g, b)
        
        graphic = {
            '_type': 'graphics',
            'shape': 'text',
            'text': text,
            'pts': [[x, y]],
            'relative': True,
            'font_scale': scale,
            'thickness': thick,
            'color': hex_color
        }
        
        img = inputs.get('image')
        return {"main": img, "graphic": graphic}
