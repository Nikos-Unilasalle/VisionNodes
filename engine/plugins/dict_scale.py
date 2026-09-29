from registry import vision_node, NodeProcessor

OPERATIONS = ['Multiply', 'Divide']


def _skip_set(text):
    return {k.strip() for k in str(text or '').split(',') if k.strip()}


@vision_node(
    type_id='dict_scale',
    label='Scale Dict Values',
    category='data',
    icon='Scale',
    description=(
        "Multiplies or divides every numeric value of a dict by factor^power — unit conversion of "
        "a whole table at once (e.g. areas in px² ÷ (px/mm)² = mm², lengths ÷ px/mm = mm). "
        "Non-numeric values and keys listed in 'Skip Keys' are passed through unchanged."
    ),
    inputs=[
        {'id': 'dict', 'color': 'dict'},
        {'id': 'factor', 'color': 'scalar'},
    ],
    outputs=[{'id': 'dict', 'color': 'dict'}],
    params=[
        {'id': 'operation', 'label': 'Operation', 'type': 'enum', 'options': OPERATIONS, 'default': 1},
        {'id': 'factor', 'label': 'Factor', 'type': 'float', 'default': 1.0},
        {'id': 'power', 'label': 'Power (1=length, 2=area)', 'type': 'float', 'default': 2.0},
        {'id': 'skip_keys', 'label': 'Skip Keys (comma-separated)', 'type': 'string', 'default': ''},
        {'id': 'digits', 'label': 'Round to Digits (-1 = off)', 'type': 'int', 'default': -1, 'min': -1, 'max': 12},
    ],
)
class DictScaleNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('dict')
        if not isinstance(d, dict):
            return {'dict': {}}
        f_in = inputs.get('factor')
        factor = float(f_in if f_in is not None else params.get('factor', 1.0))
        scale = factor ** float(params.get('power', 2.0))
        if scale == 0:
            return {'dict': dict(d)}
        divide = int(params.get('operation', 1)) == 1
        skip = _skip_set(params.get('skip_keys'))
        digits = int(params.get('digits', -1))

        out = {}
        for k, v in d.items():
            if k in skip or isinstance(v, bool) or not isinstance(v, (int, float)):
                out[k] = v
                continue
            val = v / scale if divide else v * scale
            out[k] = round(val, digits) if digits >= 0 else val
        return {'dict': out}
