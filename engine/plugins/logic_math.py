import math
from __main__ import vision_node, NodeProcessor

class MathBase(NodeProcessor):
    def process(self, inputs, params):
        a_in = inputs.get('a')
        b_in = inputs.get('b')
        a = float(a_in) if a_in is not None else float(params.get('value_a', 0.0))
        b = float(b_in) if b_in is not None else float(params.get('value_b', 0.0))
        res = self.calc(a, b)
        return {'result': res}
    
    def calc(self, a, b): return 0.0

@vision_node(type_id='math_add', label='Math: Add', category='math', icon='Plus', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A (if disconnected)', 'type': 'number', 'default': 0},
                     {'id': 'value_b', 'label': 'B (if disconnected)', 'type': 'number', 'default': 0}])
class MathAddNode(MathBase):
    def calc(self, a, b): return a + b

@vision_node(type_id='math_sub', label='Math: Subtract', category='math', icon='Minus', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A (if disconnected)', 'type': 'number', 'default': 0},
                     {'id': 'value_b', 'label': 'B (if disconnected)', 'type': 'number', 'default': 0}])
class MathSubNode(MathBase):
    def calc(self, a, b): return a - b

@vision_node(type_id='math_mul', label='Math: Multiply', category='math', icon='Hash', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A (if disconnected)', 'type': 'number', 'default': 1},
                     {'id': 'value_b', 'label': 'B (if disconnected)', 'type': 'number', 'default': 1}])
class MathMulNode(MathBase):
    def calc(self, a, b): return a * b

@vision_node(type_id='math_div', label='Math: Divide', category='math', icon='Divide', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A (if disconnected)', 'type': 'number', 'default': 1},
                     {'id': 'value_b', 'label': 'B (if disconnected)', 'type': 'number', 'default': 1}])
class MathDivNode(MathBase):
    def calc(self, a, b): return a / b if b != 0 else 0.0

@vision_node(type_id='math_mod', label='Math: Modulo', category='math', icon='Hash', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A (if disconnected)', 'type': 'number', 'default': 0},
                     {'id': 'value_b', 'label': 'B (if disconnected)', 'type': 'number', 'default': 1}])
class MathModNode(MathBase):
    def calc(self, a, b): return a % b if b != 0 else 0.0

@vision_node(type_id='math_min', label='Math: Min', category='math', icon='ChevronDown', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A', 'type': 'number', 'default': 0},
                     {'id': 'value_b', 'label': 'B', 'type': 'number', 'default': 0}])
class MathMinNode(MathBase):
    def calc(self, a, b): return min(a, b)

@vision_node(type_id='math_max', label='Math: Max', category='math', icon='ChevronUp', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'A', 'type': 'number', 'default': 0},
                     {'id': 'value_b', 'label': 'B', 'type': 'number', 'default': 0}])
class MathMaxNode(MathBase):
    def calc(self, a, b): return max(a, b)

@vision_node(type_id='math_pow', label='Math: Power', category='math', icon='Zap', 
             inputs=[{'id': 'a', 'color': 'scalar'}, {'id': 'b', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'Base', 'type': 'number', 'default': 1},
                     {'id': 'value_b', 'label': 'Exp', 'type': 'number', 'default': 2}])
class MathPowNode(MathBase):
    def calc(self, a, b): 
        try: return a ** b
        except: return 0.0

@vision_node(type_id='math_abs', label='Math: Absolute', category='math', icon='Maximize', 
             inputs=[{'id': 'a', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'Value', 'type': 'number', 'default': 0}])
class MathAbsNode(NodeProcessor):
    def process(self, inputs, params):
        v = float(inputs.get('a', params.get('value_a', 0.0)))
        return {'result': abs(v)}

@vision_node(type_id='math_round', label='Math: Round', category='math', icon='Target', 
             inputs=[{'id': 'a', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'Value', 'type': 'number', 'default': 0}])
class MathRoundNode(NodeProcessor):
    def process(self, inputs, params):
        v = float(inputs.get('a', params.get('value_a', 0.0)))
        return {'result': float(round(v))}

@vision_node(type_id='math_sin', label='Math: Sin', category='math', icon='Waves', 
             inputs=[{'id': 'a', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'Radians', 'type': 'number', 'default': 0}])
class MathSinNode(NodeProcessor):
    def process(self, inputs, params):
        v = float(inputs.get('a', params.get('value_a', 0.0)))
        return {'result': math.sin(v)}

@vision_node(type_id='math_cos', label='Math: Cos', category='math', icon='Waves', 
             inputs=[{'id': 'a', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'value_a', 'label': 'Radians', 'type': 'number', 'default': 0}])
class MathCosNode(NodeProcessor):
    def process(self, inputs, params):
        v = float(inputs.get('a', params.get('value_a', 0.0)))
        return {'result': math.cos(v)}

@vision_node(type_id='math_clamp', label='Math: Clamp', category='math', icon='Scaling', 
             inputs=[{'id': 'val', 'color': 'scalar'}, {'id': 'min', 'color': 'scalar'}, {'id': 'max', 'color': 'scalar'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[{'id': 'val', 'label': 'Value', 'type': 'number', 'default': 0},
                     {'id': 'min', 'label': 'Min', 'type': 'number', 'default': 0},
                     {'id': 'max', 'label': 'Max', 'type': 'number', 'default': 1}])
class MathClampNode(NodeProcessor):
    def process(self, inputs, params):
        v = float(inputs.get('val', params.get('val', 0.0)))
        low = float(inputs.get('min', params.get('min', 0.0)))
        high = float(inputs.get('max', params.get('max', 1.0)))
        return {'result': max(low, min(high, v))}

@vision_node(type_id='math_distance', label='Math: Distance', category='math', icon='Maximize', 
             inputs=[{'id': 'p1', 'color': 'dict'}, {'id': 'p2', 'color': 'dict'}],
             outputs=[{'id': 'result', 'color': 'scalar'}],
             params=[])
class MathDistanceNode(NodeProcessor):
    def process(self, inputs, params):
        p1 = inputs.get('p1', {})
        p2 = inputs.get('p2', {})
        
        # Fallback to 0 if dictionary is missing keys or empty
        x1 = float(p1.get('x', p1.get('xmin', 0.0)))
        y1 = float(p1.get('y', p1.get('ymin', 0.0)))
        x2 = float(p2.get('x', p2.get('xmin', 0.0)))
        y2 = float(p2.get('y', p2.get('ymin', 0.0)))
        
        return {'result': math.sqrt((x2 - x1)**2 + (y2 - y1)**2)}


