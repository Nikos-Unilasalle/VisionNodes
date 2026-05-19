from registry import vision_node, NodeProcessor

@vision_node(
    type_id='signal_gate',
    label='Signal Gate',
    category='logic',
    icon='DoorOpen',
    description="Passes or blocks a value based on a gate signal. Hold-last mode retains the last passed value when gate closes.",
    inputs=[
        {'id': 'value', 'color': 'any'},
        {'id': 'gate',  'color': 'scalar'},
    ],
    outputs=[
        {'id': 'out',    'color': 'any'},
        {'id': 'passed', 'color': 'scalar'},
    ],
    params=[
        {
            'id': 'open_when', 'label': 'Open when gate', 'type': 'enum',
            'options': ['> 0', '= 0', 'always'],
            'default': 0,
        },
        {'id': 'hold_last', 'label': 'Hold last value', 'type': 'bool', 'default': False},
    ]
)
class GateNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._last = None

    def process(self, inputs, params):
        value     = inputs.get('value')
        gate_raw  = inputs.get('gate', 1)
        open_when = int(params.get('open_when', 0))
        hold_last = bool(params.get('hold_last', False))

        try:
            gate = float(gate_raw) if gate_raw is not None else 0.0
        except (TypeError, ValueError):
            gate = 0.0

        if open_when == 0:
            is_open = gate > 0
        elif open_when == 1:
            is_open = gate == 0
        else:
            is_open = True

        if is_open:
            self._last = value
            return {'out': value, 'passed': 1.0}
        else:
            out = self._last if hold_last else None
            return {'out': out, 'passed': 0.0}
