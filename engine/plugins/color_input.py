"""Color Value — standalone color source, used when a 'color' param is externalized."""
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='color_input',
    label='Color Value',
    category='color',
    icon='Palette',
    description="Outputs a hex color string. Drive multiple color params from one shared value.",
    outputs=[{'id': 'result', 'color': 'string'}],
    params=[{'id': 'value', 'label': 'Color', 'type': 'color', 'default': '#FF0000'}],
)
class ColorInputNode(NodeProcessor):
    def process(self, inputs, params):
        return {'result': str(params.get('value', '#FF0000'))}
