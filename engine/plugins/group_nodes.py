from registry import vision_node, NodeProcessor


@vision_node(
    type_id='group_node',
    label='Group',
    category='canvas',
    icon='Package',
    description='Encapsulates a subgraph. Double-click to enter/edit.',
    inputs=[],
    outputs=[],
    params=[{'id': 'label', 'type': 'string', 'default': 'Group'}],
    dynamic_inputs=True,
    dynamic_outputs=True
)
class GroupNodeProcessor(NodeProcessor):
    def process(self, inputs, params):
        return {}  # replaced by flatten_groups before execution


@vision_node(
    type_id='group_input',
    label='Group IN',
    category='canvas',
    icon='LogIn',
    description='Relay: group input ports into the subgraph.',
    inputs=[],
    outputs=[{'id': 'slot_0', 'color': 'any'}],
    params=[],
    dynamic_outputs=True
)
class GroupInputProcessor(NodeProcessor):
    def process(self, inputs, params):
        return {}  # replaced by flatten_groups


@vision_node(
    type_id='group_output',
    label='Group OUT',
    category='canvas',
    icon='LogOut',
    description='Relay: inner subgraph outputs to group output ports.',
    inputs=[{'id': 'slot_0', 'color': 'any'}],
    outputs=[],
    params=[],
    dynamic_inputs=True
)
class GroupOutputProcessor(NodeProcessor):
    def process(self, inputs, params):
        return {}  # replaced by flatten_groups
