import numpy as np
import cv2
from registry import vision_node, NodeProcessor

try:
    import pandas as _pd_module
    _PANDAS_AVAILABLE = True
except ImportError:
    _pd_module = None
    _PANDAS_AVAILABLE = False


def _df_meta_local(df) -> dict:
    """Serializable DataFrame metadata — inlined to avoid cross-plugin imports."""
    r, c = df.shape
    head_df = df.head(8)

    def _serialize(v):
        if isinstance(v, float) and v != v:  # NaN
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, (int,)):
            return v
        if isinstance(v, (float, np.floating)):
            return float(v)
        return str(v)

    return {
        'shape':   [r, c],
        'columns': [str(col) for col in df.columns],
        'dtypes':  {str(col): str(df[col].dtype) for col in df.columns},
        'nulls':   {str(col): int(df[col].isna().sum()) for col in df.columns},
        'head':    [{str(k): _serialize(v) for k, v in row.items()}
                   for _, row in head_df.iterrows()],
    }


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

_RESERVED_VARS = frozenset(['np', 'cv2', 'pd', 'state'])

_DEFAULT_SCRIPT = """\
# ── Inputs ────────────────────────────────────────────────────────────────────
#   a, b, c, d …  : the connected inputs (a new port appears as you connect each).
#                   Any type — image, scalar, list, dict, DataFrame…
#   np, cv2       : numpy and OpenCV always available
#   pd            : pandas (if installed)
#
# ── Outputs ───────────────────────────────────────────────────────────────────
#   out_a, out_b … : assign any variable named out_* to expose it on an output port.
#                    Output ports are auto-typed by whatever you connect them to.
#       out_a = a if isinstance(a, np.ndarray) else None
#       out_b = float(np.mean(a)) if isinstance(a, np.ndarray) else 0.0
#
# ── DataFrame tip ─────────────────────────────────────────────────────────────
#   if isinstance(a, pd.DataFrame):
#       out_a = a[a['species'] == 'Iris-setosa']
#
# ── Persistence between frames ────────────────────────────────────────────────
#   state['counter'] = state.get('counter', 0) + 1

out_a = a if isinstance(a, np.ndarray) else None
"""

@vision_node(type_id='logic_python', label='Python Node', category='logic', icon='Zap',
             dynamic_inputs=True,
             dynamic_outputs=True,
             inputs=[
                 {'id': 'a', 'color': 'any'},
             ],
             outputs=[
                 {'id': 'out_a', 'color': 'any'},
             ],
             params=[{
                 'id':      'code',
                 'label':   'Python Script',
                 'type':    'string',
                 'default': _DEFAULT_SCRIPT,
             }])
class PythonNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        # Dictionnaire persistant entre les frames — accessible via `state` dans le script
        self._state: dict = {}

    def process(self, inputs, params):
        code = params.get('code', '')

        ctx = {
            '__builtins__': _SAFE_BUILTINS,
            'np':    np,
            'cv2':   cv2,
            'pd':    _pd_module,
            'state': self._state,
        }
        # Inject every connected input as a variable (a, b, c…). Skip engine internals.
        for key, val in inputs.items():
            if key == 'raw_frame' or not key.isidentifier():
                continue
            ctx[key] = val

        error = ''
        try:
            exec(code, ctx)
        except Exception as e:
            print(f"[Python Node Error] {e}")
            error = str(e)

        # Collect every out_* variable the script defined → auto-typed output ports.
        result: dict = {}
        for key, val in ctx.items():
            if key.startswith('out_') and key not in _RESERVED_VARS:
                result[key] = val

        # Always expose the error string (inspector reads liveData.out_e for the editor).
        result['out_e'] = error

        if _PANDAS_AVAILABLE and _pd_module is not None:
            for key, val in list(result.items()):
                if isinstance(val, _pd_module.DataFrame):
                    try:
                        result['df_meta'] = _df_meta_local(val)
                    except Exception as e:
                        print(f"[Python Node df_meta error] {e}")
                    break

        return result
