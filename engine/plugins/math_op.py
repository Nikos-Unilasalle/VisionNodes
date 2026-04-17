from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='math_operation',
    label='Math Op',
    category='math',
    icon='Hash',
    description="Performs simple mathematical operations (+, -, *, /) on two numerical values.",
    inputs=[
        {'id': 'a', 'color': 'scalar'}, 
        {'id': 'b', 'color': 'scalar'}
    ],
    outputs=[{'id': 'result', 'color': 'scalar'}],
    params=[
        {
            'id': 'operation', 
            'type': 'enum',
            'options': ['Add (+)', 'Subtract (-)', 'Multiply (*)', 'Divide (/)'],
            'default': 0
        },
        {'id': 'value_b', 'min': -100, 'max': 100, 'step': 1, 'default': 0}
    ]
)
class MathOpNode(NodeProcessor):
    def process(self, inputs, params):
        a_input = inputs.get('a')
        b_input = inputs.get('b')
        
        a = float(a_input) if a_input is not None else 0.0
        b = float(b_input) if b_input is not None else float(params.get('value_b', 0.0))
        
        op = int(params.get('operation', 0))
        res = 0.0
        
        if op == 0: res = a + b
        elif op == 1: res = a - b
        elif op == 2: res = a * b
        elif op == 3 and b != 0: res = a / b
        
        op_char = "+" if op == 0 else "-" if op == 1 else "*" if op == 2 else "/"
        return {
            'result': res,
            'display_text': f"{a:.2f} {op_char} {b:.2f} = {res:.4f}"
        }
