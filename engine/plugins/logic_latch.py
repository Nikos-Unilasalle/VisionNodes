from registry import vision_node, NodeProcessor

@vision_node(
    type_id='logic_latch',
    label='Latch',
    category='logic',
    icon='BookmarkCheck',
    description="Holds the last valid (non-null, non-zero) value. Useful for intermittent detections. Optional reset trigger.",
    inputs=[
        {'id': 'value', 'color': 'any'},
        {'id': 'reset', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'held',   'color': 'any'},
        {'id': 'active', 'color': 'scalar'},
    ],
    params=[
        {
            'id': 'mode', 'label': 'Latch on', 'type': 'enum',
            'options': ['non-null', 'non-zero', 'any'],
            'default': 0,
        },
    ]
)
class LatchNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._held = None
        self._prev_reset = 0.0

    def process(self, inputs, params):
        value = inputs.get('value')
        reset = inputs.get('reset', 0)
        mode  = int(params.get('mode', 0))

        # Rising edge on reset
        try:
            reset_f = float(reset) if reset is not None else 0.0
        except (TypeError, ValueError):
            reset_f = 0.0

        if reset_f > 0.5 and self._prev_reset <= 0.5:
            self._held = None
        self._prev_reset = reset_f

        # Determine if value should latch
        should_latch = False
        if mode == 0:  # non-null
            should_latch = value is not None
        elif mode == 1:  # non-zero
            try:
                should_latch = value is not None and float(value) != 0.0
            except (TypeError, ValueError):
                should_latch = value is not None
        else:  # any — always latch whatever arrives
            should_latch = True

        if should_latch:
            self._held = value

        return {
            'held':   self._held,
            'active': 1.0 if self._held is not None else 0.0,
        }
