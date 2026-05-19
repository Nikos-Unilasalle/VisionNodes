from registry import vision_node, NodeProcessor

@vision_node(
    type_id='math_map_range',
    label='Map Range',
    category='math',
    icon='ArrowLeftRight',
    description="Remaps a scalar from [in_min, in_max] to [out_min, out_max]. Optional clamp.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'result', 'color': 'scalar'}],
    params=[
        {'id': 'in_min',  'label': 'In Min',   'type': 'float', 'default': 0.0},
        {'id': 'in_max',  'label': 'In Max',   'type': 'float', 'default': 1.0},
        {'id': 'out_min', 'label': 'Out Min',  'type': 'float', 'default': 0.0},
        {'id': 'out_max', 'label': 'Out Max',  'type': 'float', 'default': 100.0},
        {'id': 'clamp',   'label': 'Clamp',    'type': 'bool',  'default': False},
    ]
)
class MapRangeNode(NodeProcessor):
    def process(self, inputs, params):
        value = inputs.get('value')
        if value is None:
            return {'result': 0.0}

        try:
            v = float(value)
        except (TypeError, ValueError):
            return {'result': 0.0}

        in_min  = float(params.get('in_min',  0.0))
        in_max  = float(params.get('in_max',  1.0))
        out_min = float(params.get('out_min', 0.0))
        out_max = float(params.get('out_max', 100.0))
        clamp   = bool(params.get('clamp', False))

        in_range = in_max - in_min
        if abs(in_range) < 1e-12:
            return {'result': out_min}

        t = (v - in_min) / in_range
        if clamp:
            t = max(0.0, min(1.0, t))

        result = out_min + t * (out_max - out_min)
        return {'result': result}
