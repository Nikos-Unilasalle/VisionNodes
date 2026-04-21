import numpy as np
import cv2
from __main__ import vision_node, NodeProcessor

@vision_node(type_id='logic_python', label='Python Node', category='logic', icon='Zap', 
             inputs=[
                 {'id': 'a', 'color': 'any'}, 
                 {'id': 'b', 'color': 'any'}, 
                 {'id': 'c', 'color': 'any'}, 
                 {'id': 'd', 'color': 'any'}
             ],
             outputs=[
                 {'id': 'main', 'color': 'image'},
                 {'id': 'out_scalar', 'color': 'scalar'},
                 {'id': 'out_list', 'color': 'list'},
                 {'id': 'out_dict', 'color': 'dict'},
                 {'id': 'out_any', 'color': 'any'}
             ],
             params=[{
                 'id': 'code', 
                 'label': 'Python Script', 
                 'type': 'string', 
                 'default': "# Logic here\n# Inputs: a, b, c, d\n# State persistant entre frames: state['my_var']\n# Outputs: out_main, out_scalar, out_list, out_dict, out_any\n\nout_main = a if isinstance(a, np.ndarray) else None\nout_scalar = 0.0\nout_list = []\nout_dict = {}\nout_any = None\n"
             }])
class PythonNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        # Dictionnaire persistant entre les frames — accessible via `state` dans le script
        self._state: dict = {}

    def process(self, inputs, params):
        code = params.get('code', '')
        
        # Setup context — `state` est persistant entre les appels
        ctx = {
            '__builtins__': __builtins__,
            'np': np,
            'cv2': cv2,
            'state': self._state,
            'a': inputs.get('a'),
            'b': inputs.get('b'),
            'c': inputs.get('c'),
            'd': inputs.get('d'),
            'out_main': None,
            'out_scalar': 0.0,
            'out_list': [],
            'out_dict': {},
            'out_any': None
        }
        
        try:
            exec(code, ctx)
        except Exception as e:
            print(f"[Python Node Error] {e}")
            ctx['out_any'] = f"Error: {str(e)}"
            
        return {
            'main': ctx.get('out_main'),
            'out_scalar': float(ctx.get('out_scalar', 0)),
            'out_list': ctx.get('out_list', []),
            'out_dict': ctx.get('out_dict', {}),
            'out_any': ctx.get('out_any')
        }
