from registry import vision_node, NodeProcessor

DEFAULT_GROUPS = 'Values: *'


def _parse_groups(text):
    """'Title: k1, k2' per line (or '|' separated) → [{'label', 'keys'}]. '*' = all remaining keys."""
    groups = []
    for line in str(text or '').replace('|', '\n').splitlines():
        if ':' not in line:
            continue
        label, keys = line.split(':', 1)
        key_list = [k.strip() for k in keys.split(',') if k.strip()]
        if label.strip() and key_list:
            groups.append({'label': label.strip(), 'keys': key_list})
    return groups


def _merge(inputs):
    merged = {}
    for k in sorted(inputs):
        if k.startswith('dict') and isinstance(inputs[k], dict):
            merged.update(inputs[k])
    return merged


@vision_node(
    type_id='dict_report_panel',
    label='Report Panel',
    category='visualize',
    icon='BarChart2',
    description=(
        "Displays one or more dicts as a grouped measurement panel (compact and expanded views). "
        "Groups are separated by '|' (or new lines): 'Title: key1, key2 | Title2: …' ('*' = every key not listed "
        "elsewhere). Outputs the merged dict, ordered as displayed, for CSV export."
    ),
    inputs=[
        {'id': 'dict', 'color': 'dict'},
        {'id': 'dict_2', 'color': 'dict'},
    ],
    outputs=[{'id': 'report', 'color': 'dict'}],
    params=[
        {'id': 'title', 'label': 'Title', 'type': 'string', 'default': 'Report'},
        {'id': 'groups', 'label': 'Groups (Title: key, key | Title: …)', 'type': 'string', 'default': DEFAULT_GROUPS},
        {'id': 'digits', 'label': 'Displayed Digits', 'type': 'int', 'default': 4, 'min': 0, 'max': 10},
    ],
    resizable=True,
)
class ReportPanelNode(NodeProcessor):
    def process(self, inputs, params):
        merged = _merge(inputs)
        groups = _parse_groups(params.get('groups', DEFAULT_GROUPS))
        listed = [k for g in groups for k in g['keys'] if k != '*']
        rest = [k for k in merged if k not in listed]
        groups = [{'label': g['label'], 'keys': [x for k in g['keys'] for x in (rest if k == '*' else [k])]}
                  for g in groups]
        ordered = {k: merged[k] for g in groups for k in g['keys'] if k in merged}
        ordered.update({k: v for k, v in merged.items() if k not in ordered})
        return {'report': ordered, 'groups': groups, 'title': str(params.get('title', 'Report')),
                'digits': int(params.get('digits', 4))}
