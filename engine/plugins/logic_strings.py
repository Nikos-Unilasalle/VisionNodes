from registry import vision_node, NodeProcessor
import re as _re

@vision_node(type_id='string_concat', label='String: Concat', category='strings', icon='PlusSquare',
             inputs=[{'id': 'a', 'color': 'string'}, {'id': 'b', 'color': 'string'}, {'id': 'list_in', 'color': 'list', 'label': 'List'}],
             outputs=[{'id': 'result', 'color': 'string'}],
             params=[{'id': 'separator', 'label': 'Separator', 'type': 'string', 'default': ''}])
class StringConcatNode(NodeProcessor):
    def process(self, inputs, params):
        sep = str(params.get('separator', ''))
        lst = inputs.get('list_in')
        if isinstance(lst, list) and lst:
            return {'result': sep.join(str(x) for x in lst)}
        a = str(inputs.get('a', '') or '')
        b = str(inputs.get('b', '') or '')
        return {'result': f"{a}{sep}{b}"}

@vision_node(type_id='string_split', label='String: Split', category='strings', icon='Scissors', 
             inputs=[{'id': 'string', 'color': 'string'}],
             outputs=[{'id': 'list', 'color': 'list'}, {'id': 'first', 'color': 'string'}],
             params=[{'id': 'separator', 'label': 'Separator', 'type': 'string', 'default': ' '}])
class StringSplitNode(NodeProcessor):
    def process(self, inputs, params):
        s = str(inputs.get('string', ''))
        sep = params.get('separator', ' ')
        parts = s.split(sep) if sep else list(s)
        return {'list': parts, 'first': parts[0] if parts else ''}

@vision_node(type_id='string_length', label='String: Length', category='strings', icon='Hash', 
             inputs=[{'id': 'string', 'color': 'string'}],
             outputs=[{'id': 'length', 'color': 'scalar'}])
class StringLengthNode(NodeProcessor):
    def process(self, inputs, params):
        s = str(inputs.get('string', ''))
        return {'length': float(len(s))}

@vision_node(type_id='string_case', label='String: Case', category='strings', icon='Type', 
             inputs=[{'id': 'string', 'color': 'string'}],
             outputs=[{'id': 'result', 'color': 'string'}],
             params=[{'id': 'mode', 'label': 'Mode', 'type': 'enum', 'options': ['UPPER', 'lower'], 'default': 0}])
class StringCaseNode(NodeProcessor):
    def process(self, inputs, params):
        s = str(inputs.get('string', ''))
        mode = int(params.get('mode', 0))
        res = s.upper() if mode == 0 else s.lower()
        return {'result': res}

@vision_node(type_id='string_replace', label='String: Replace', category='strings', icon='Replace',
             inputs=[{'id': 'string', 'color': 'string'}],
             outputs=[{'id': 'result', 'color': 'string'}],
             params=[
                 {'id': 'search',    'label': 'Search',     'type': 'string',  'default': ''},
                 {'id': 'replace',   'label': 'Replace',    'type': 'string',  'default': ''},
                 {'id': 'use_regex', 'label': 'Regex',      'type': 'boolean', 'default': False},
                 {'id': 'case',      'label': 'Case-sensitive', 'type': 'boolean', 'default': True},
             ])
class StringReplaceNode(NodeProcessor):
    def process(self, inputs, params):
        s       = str(inputs.get('string', '') or '')
        search  = str(params.get('search',  ''))
        replace = str(params.get('replace', ''))
        regex   = bool(params.get('use_regex', False))
        case    = bool(params.get('case', True))
        if not search:
            return {'result': s}
        flags = 0 if case else _re.IGNORECASE
        try:
            if regex:
                result = _re.sub(search, replace, s, flags=flags)
            else:
                result = _re.sub(_re.escape(search), replace, s, flags=flags)
        except _re.error:
            result = s
        return {'result': result}


@vision_node(type_id='string_input', label='String: Input', category='strings', icon='Keyboard',
             outputs=[{'id': 'result', 'color': 'string'}],
             params=[{'id': 'value', 'label': 'Text', 'type': 'string', 'default': 'Hello'}])
class StringInputNode(NodeProcessor):
    def process(self, inputs, params):
        return {'result': params.get('value', '')}
