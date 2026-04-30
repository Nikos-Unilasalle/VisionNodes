from registry import vision_node, NodeProcessor

@vision_node(
    type_id='plugin_dict_get',
    label='Dict Get',
    category='data',
    icon='Key',
    description="Extracts 1 to 3 values from a dictionary by key name. val_1/2/3 outputs accept any downstream type; scalar_1 coerces val_1 to float.",
    inputs=[{'id': 'dict_in', 'color': 'any'}],
    outputs=[
        {'id': 'val_1',    'color': 'any'},
        {'id': 'val_2',    'color': 'any'},
        {'id': 'val_3',    'color': 'any'},
        {'id': 'scalar_1', 'color': 'scalar'},
        {'id': 'dict_1',   'color': 'dict'},
    ],
    params=[
        {'id': 'key_1', 'type': 'string', 'default': 'xmin'},
        {'id': 'key_2', 'type': 'string', 'default': ''},
        {'id': 'key_3', 'type': 'string', 'default': ''},
    ]
)
class DictGetNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('dict_in')
        if not isinstance(d, dict):
            return {'val_1': None, 'val_2': None, 'val_3': None, 'scalar_1': 0.0, 'dict_1': None}

        k1 = str(params.get('key_1', 'xmin')).strip()
        k2 = str(params.get('key_2', '')).strip()
        k3 = str(params.get('key_3', '')).strip()

        v1 = d.get(k1) if k1 else None
        v2 = d.get(k2) if k2 else None
        v3 = d.get(k3) if k3 else None

        try:
            s1 = float(v1) if v1 is not None else 0.0
        except (TypeError, ValueError):
            s1 = 0.0

        d1 = v1 if isinstance(v1, dict) else None

        return {'val_1': v1, 'val_2': v2, 'val_3': v3, 'scalar_1': s1, 'dict_1': d1}
