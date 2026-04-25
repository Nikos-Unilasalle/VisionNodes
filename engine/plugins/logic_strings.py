from registry import vision_node, NodeProcessor

@vision_node(type_id='string_concat', label='String: Concat', category='strings', icon='PlusSquare', 
             inputs=[{'id': 'a', 'color': 'string'}, {'id': 'b', 'color': 'string'}],
             outputs=[{'id': 'result', 'color': 'string'}],
             params=[{'id': 'separator', 'label': 'Separator', 'type': 'string', 'default': ''}])
class StringConcatNode(NodeProcessor):
    def process(self, inputs, params):
        a = str(inputs.get('a', ''))
        b = str(inputs.get('b', ''))
        sep = params.get('separator', '')
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

@vision_node(type_id='string_input', label='String: Input', category='strings', icon='Keyboard', 
             outputs=[{'id': 'result', 'color': 'string'}],
             params=[{'id': 'value', 'label': 'Text', 'type': 'string', 'default': 'Hello'}])
class StringInputNode(NodeProcessor):
    def process(self, inputs, params):
        return {'result': params.get('value', '')}
