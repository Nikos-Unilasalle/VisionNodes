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

_DEFAULT_SCRIPT = """\
# ── Inputs ────────────────────────────────────────────────────────────────────
#   a, b, c, d  : any type (image, scalar, list, dict, DataFrame…)
#   np, cv2     : numpy and OpenCV always available
#   pd          : pandas (if installed)
#
# ── DataFrame tip ─────────────────────────────────────────────────────────────
#   if isinstance(a, pd.DataFrame):
#       out_data   = a[a['species'] == 'Iris-setosa']  # → connecter à DF Stats
#       out_scalar = float(a['sepal_length'].mean())
#       out_dict   = a.describe().to_dict()
#
# ── Outputs ───────────────────────────────────────────────────────────────────
#   out_main   (image)   out_scalar (float)   out_list (list)
#   out_dict   (dict)    out_any    (any)      out_data (DataFrame)
#
# ── Persistence between frames ────────────────────────────────────────────────
#   state['counter'] = state.get('counter', 0) + 1

out_main   = a if isinstance(a, np.ndarray) else None
out_scalar = 0.0
out_list   = []
out_dict   = {}
out_any    = None
out_data   = None
"""

@vision_node(type_id='logic_python', label='Python Node', category='logic', icon='Zap',
             inputs=[
                 {'id': 'a', 'color': 'any'},
                 {'id': 'b', 'color': 'any'},
                 {'id': 'c', 'color': 'any'},
                 {'id': 'd', 'color': 'any'},
                 {'id': 'e', 'color': 'any'},
             ],
             outputs=[
                 {'id': 'main',       'color': 'image'},
                 {'id': 'out_scalar', 'color': 'scalar'},
                 {'id': 'out_list',   'color': 'list'},
                 {'id': 'out_dict',   'color': 'dict'},
                 {'id': 'out_any',    'color': 'any'},
                 {'id': 'out_data',   'color': 'data',   'label': 'DataFrame'},
                 {'id': 'out_e',      'color': 'string', 'label': 'Error'},
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
            'a':     inputs.get('a'),
            'b':     inputs.get('b'),
            'c':     inputs.get('c'),
            'd':     inputs.get('d'),
            'e':     inputs.get('e'),
            'out_main':   None,
            'out_scalar': 0.0,
            'out_list':   [],
            'out_dict':   {},
            'out_any':    None,
            'out_data':   None,
            'out_e':      '',
        }

        try:
            exec(code, ctx)
        except Exception as e:
            print(f"[Python Node Error] {e}")
            ctx['out_e'] = str(e)

        scalar_raw = ctx.get('out_scalar', 0)
        result = {
            'main':       ctx.get('out_main'),
            'out_scalar': float(scalar_raw) if isinstance(scalar_raw, (int, float, bool)) else 0.0,
            'out_list':   ctx.get('out_list', []) if isinstance(ctx.get('out_list'), list) else [],
            'out_dict':   ctx.get('out_dict', {}) if isinstance(ctx.get('out_dict'), dict) else {},
            'out_any':    ctx.get('out_any'),
            'out_data':   ctx.get('out_data'),
            'out_e':      ctx.get('out_e', ''),
        }

        if _PANDAS_AVAILABLE and _pd_module is not None:
            df_out = ctx.get('out_data')
            if isinstance(df_out, _pd_module.DataFrame):
                try:
                    result['df_meta'] = _df_meta_local(df_out)
                except Exception as e:
                    print(f"[Python Node df_meta error] {e}")

        return result
