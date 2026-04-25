import numpy as np
import cv2
from registry import vision_node, NodeProcessor

_BLOCKED_IMPORTS = frozenset([
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'http', 'urllib',
    'requests', 'pathlib', 'glob', 'importlib', 'ctypes', 'mmap',
    'builtins', 'io', 'pty', 'atexit', 'signal', 'threading', 'multiprocessing',
])

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    top = (name or '').split('.')[0]
    if top in _BLOCKED_IMPORTS:
        raise ImportError(f"Import of '{name}' blocked in Python Node")
    _bi = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    return _bi['__import__'](name, globals, locals, fromlist, level)

_ALLOWED = {
    'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'chr', 'complex',
    'dict', 'divmod', 'enumerate', 'filter', 'float', 'format',
    'frozenset', 'getattr', 'hasattr', 'hash', 'hex', 'int', 'isinstance',
    'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min', 'next',
    'oct', 'ord', 'pow', 'print', 'range', 'repr', 'reversed', 'round',
    'set', 'setattr', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
    'ArithmeticError', 'AttributeError', 'Exception', 'IndexError', 'KeyError',
    'NotImplementedError', 'OverflowError', 'RuntimeError', 'StopIteration',
    'TypeError', 'ValueError', 'ZeroDivisionError',
}
_builtins_src = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
_SAFE_BUILTINS = {k: v for k, v in _builtins_src.items() if k in _ALLOWED}
_SAFE_BUILTINS['__import__'] = _safe_import

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
            '__builtins__': _SAFE_BUILTINS,
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
