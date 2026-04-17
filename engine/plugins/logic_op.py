from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="logic_compare",
    label="Data Compare",
    category="logic",
    icon="Activity",
    inputs=[{"id": "a", "color": "any"}, {"id": "b", "color": "any"}],
    outputs=[{"id": "result", "color": "boolean"}],
    params=[
        {"id": "op", "label": "Operator", "type": "enum", "options": ["==", "!=", ">", "<", ">=", "<="], "default": 0}
    ]
)
class CompareNode(NodeProcessor):
    def process(self, inputs, params):
        a = inputs.get('a')
        b = inputs.get('b')
        op_idx = params.get('op', 0)
        
        # Default fallback
        if a is None or b is None:
            # We try to compare with 0 if possible, otherwise False
            try:
                if a is None: a = 0
                if b is None: b = 0
            except:
                return {"result": False}

        res = False
        try:
            if op_idx == 0: res = (a == b)
            elif op_idx == 1: res = (a != b)
            elif op_idx == 2: res = (float(a) > float(b))
            elif op_idx == 3: res = (float(a) < float(b))
            elif op_idx == 4: res = (float(a) >= float(b))
            elif op_idx == 5: res = (float(a) <= float(b))
        except:
            res = False
            
        return {"result": bool(res)}

@vision_node(
    type_id="logic_presence",
    label="Presence Check",
    category="logic",
    icon="Search",
    inputs=[{"id": "data", "color": "any"}],
    outputs=[{"id": "found", "color": "boolean"}]
)
class PresenceNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        if data is None:
            return {"found": False}
        
        # Check for list length
        if isinstance(data, list):
            return {"found": len(data) > 0}
        
        # Check for numeric presence (non-zero)
        if isinstance(data, (int, float)):
            return {"found": data != 0}
            
        # Treat anything else that isn't None as True
        return {"found": True}

@vision_node(
    type_id="logic_switch",
    label="Switch",
    category="logic",
    icon="Zap",
    inputs=[
        {"id": "condition", "color": "boolean"},
        {"id": "if_true", "color": "any"},
        {"id": "if_false", "color": "any"}
    ],
    outputs=[{"id": "output", "color": "any"}]
)
class SwitchNode(NodeProcessor):
    def process(self, inputs, params):
        cond = inputs.get('condition', False)
        # In case it's numeric (0/1)
        if isinstance(cond, (int, float)):
            cond = bool(cond)
            
        if cond:
            return {"output": inputs.get('if_true')}
        else:
            return {"output": inputs.get('if_false')}

@vision_node(
    type_id="logic_gate",
    label="Logic Gate",
    category="logic",
    icon="Layers",
    inputs=[{"id": "in_a", "color": "boolean"}, {"id": "in_b", "color": "boolean"}],
    outputs=[{"id": "result", "color": "boolean"}],
    params=[
        {"id": "mode", "label": "Mode", "type": "enum", "options": ["AND", "OR", "XOR", "NOT A"], "default": 0}
    ]
)
class LogicGateNode(NodeProcessor):
    def process(self, inputs, params):
        a = bool(inputs.get('in_a', False))
        b = bool(inputs.get('in_b', False))
        mode = params.get('mode', 0)
        
        res = False
        if mode == 0: res = a and b
        elif mode == 1: res = a or b
        elif mode == 2: res = a != b # XOR
        elif mode == 3: res = not a
        
        return {"result": res}
