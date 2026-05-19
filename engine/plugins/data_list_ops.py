from registry import vision_node, NodeProcessor

@vision_node(
    type_id='data_list_ops',
    label='List Ops',
    category='data',
    icon='ListOrdered',
    description="List operations: sort, reverse, unique, slice, flatten, append, length, contains.",
    inputs=[
        {'id': 'list_in', 'color': 'list'},
        {'id': 'value',   'color': 'any'},
    ],
    outputs=[
        {'id': 'list_out',  'color': 'list'},
        {'id': 'value_out', 'color': 'any'},
    ],
    params=[
        {
            'id': 'operation', 'label': 'Operation', 'type': 'enum',
            'options': ['sort', 'sort desc', 'reverse', 'unique', 'flatten', 'slice', 'append', 'length', 'contains'],
            'default': 0,
        },
        {'id': 'slice_start', 'label': 'Slice Start', 'type': 'int', 'default': 0},
        {'id': 'slice_end',   'label': 'Slice End',   'type': 'int', 'default': 10},
        {'id': 'slice_step',  'label': 'Slice Step',  'type': 'int', 'default': 1},
    ]
)
class ListOpsNode(NodeProcessor):
    def process(self, inputs, params):
        lst      = inputs.get('list_in') or []
        value    = inputs.get('value')
        op_idx   = int(params.get('operation', 0))
        ops      = ['sort', 'sort desc', 'reverse', 'unique', 'flatten', 'slice', 'append', 'length', 'contains']
        op       = ops[op_idx] if op_idx < len(ops) else 'sort'

        if not isinstance(lst, list):
            lst = list(lst) if hasattr(lst, '__iter__') else []

        list_out  = lst
        value_out = None

        try:
            if op == 'sort':
                list_out = sorted(lst, key=lambda x: (x is None, x))
            elif op == 'sort desc':
                list_out = sorted(lst, key=lambda x: (x is None, x), reverse=True)
            elif op == 'reverse':
                list_out = list(reversed(lst))
            elif op == 'unique':
                seen, list_out = set(), []
                for item in lst:
                    key = str(item)
                    if key not in seen:
                        seen.add(key)
                        list_out.append(item)
            elif op == 'flatten':
                list_out = []
                for item in lst:
                    if isinstance(item, list):
                        list_out.extend(item)
                    else:
                        list_out.append(item)
            elif op == 'slice':
                start = int(params.get('slice_start', 0))
                end   = int(params.get('slice_end',   10))
                step  = int(params.get('slice_step',  1)) or 1
                list_out = lst[start:end:step]
            elif op == 'append':
                list_out = lst + ([value] if value is not None else [])
            elif op == 'length':
                value_out = float(len(lst))
                list_out  = lst
            elif op == 'contains':
                value_out = 1.0 if value in lst else 0.0
                list_out  = lst
        except Exception as e:
            print(f"[ListOps] {e}")

        return {'list_out': list_out, 'value_out': value_out}
