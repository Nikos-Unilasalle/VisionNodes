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

# Key carrying the traceback back to the editor. Deliberately not an out_* name, so
# it can never collide with a user output port.
ERROR_CHANNEL = '__error__'

_DEFAULT_SCRIPT = """\
# ── Inputs ────────────────────────────────────────────────────────────────────
#   a, b, c, d …  : the connected inputs (a new port appears as you connect each).
#   np, cv2       : numpy and OpenCV always available
#   pd            : pandas (if installed)
#
# ── Outputs ───────────────────────────────────────────────────────────────────
#   out_a, out_b … : assign any variable named out_* to expose it on an output port.
#                    Every out_* name is yours — out_e included.
#                    Output ports are auto-typed by whatever you connect them to.
#       out_a = a if isinstance(a, np.ndarray) else None
#       out_b = float(np.mean(a)) if isinstance(a, np.ndarray) else 0.0
#
# ── VNStudio port types → Python value ────────────────────────────────────────
#   image     → np.ndarray  HxWx3 uint8, BGR (OpenCV order)
#   mask      → np.ndarray  HxW   uint8, 0/255 binary
#   markers   → np.ndarray  HxW   int32, integer label map (0 = background)
#   flow      → np.ndarray  HxWx2 float32, optical-flow dx/dy
#   data      → pd.DataFrame                      (the orange "DataFrame" port)
#   geotiff   → dict {'bands': np.ndarray (C,H,W) float32, 'count': int,
#                     'crs': str, 'transform': affine, 'nodata': float|None}
#   contours  → list[np.ndarray]  each (N,1,2) int32  (cv2 contour format)
#   regions   → list[dict]  e.g. {'area':…, 'centroid':(y,x), 'bbox':…, …}
#   points    → list[dict]  {'x': float, 'y': float, 'label': int}  (1=fg, 0=bg)
#   audio     → np.ndarray  float32 samples  (paired with a scalar sample-rate)
#   scalar    → int | float           string → str           dict → dict
#   list      → list                  boolean → bool          any → anything
#
# ── DataFrame tip ─────────────────────────────────────────────────────────────
#   if isinstance(a, pd.DataFrame):
#       out_a = a[a['species'] == 'Iris-setosa']
#
# ── GeoTIFF tip ───────────────────────────────────────────────────────────────
#   if isinstance(a, dict) and 'bands' in a:
#       ndvi = (a['bands'][3] - a['bands'][2]) / (a['bands'][3] + a['bands'][2] + 1e-6)
#       out_a = ndvi.astype(np.float32)
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
            if key.startswith('out_'):
                result[key] = val

        # The error goes on its own reserved channel, NOT on an out_* name. It used to
        # be written to 'out_e', which silently overwrote the fifth output of any script
        # that named its outputs out_a..out_e after inputs a..e — an empty error string
        # replacing a valid result, with nothing to show for it.
        result[ERROR_CHANNEL] = error

        if _PANDAS_AVAILABLE and _pd_module is not None:
            for key, val in list(result.items()):
                if isinstance(val, _pd_module.DataFrame):
                    try:
                        result['df_meta'] = _df_meta_local(val)
                    except Exception as e:
                        print(f"[Python Node df_meta error] {e}")
                    break

        return result
