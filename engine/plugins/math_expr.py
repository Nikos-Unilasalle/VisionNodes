import ast
import math
from registry import vision_node, NodeProcessor

_MATH_CONTEXT = {
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'asin': math.asin, 'acos': math.acos, 'atan': math.atan, 'atan2': math.atan2,
    'sqrt': math.sqrt, 'exp': math.exp, 'log': math.log, 'log2': math.log2, 'log10': math.log10,
    'pow': math.pow, 'floor': math.floor, 'ceil': math.ceil, 'round': round,
    'abs': abs, 'min': min, 'max': max,
    'pi': math.pi, 'e': math.e, 'inf': math.inf,
    'clamp': lambda x, lo, hi: max(lo, min(hi, x)),
    'lerp': lambda a, b, t: a + (b - a) * t,
    'sign': lambda x: (1 if x > 0 else -1 if x < 0 else 0),
    'frac': lambda x: x - math.floor(x),
    'deg': math.degrees, 'rad': math.radians,
}

_ALLOWED_NODE_TYPES = frozenset({
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.IfExp,
    ast.Compare, ast.Call, ast.Constant, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.And, ast.Or,
})


def _safe_eval(expr: str, variables: dict) -> float:
    try:
        tree = ast.parse(expr.strip(), mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e}")

    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODE_TYPES:
            raise ValueError(f"Forbidden construct: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in _MATH_CONTEXT and node.id not in variables:
            raise ValueError(f"Unknown variable: '{node.id}'")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            if node.func.id not in _MATH_CONTEXT:
                raise ValueError(f"Unknown function: '{node.func.id}'")

    ctx = {**_MATH_CONTEXT, **variables}
    result = eval(compile(tree, '<expr>', 'eval'), {'__builtins__': {}}, ctx)
    return float(result)


def _extract_port_index(key: str) -> int:
    """Extract numeric index from dynamic port key like '0_x7k2' → 0."""
    try:
        return int(key.split('_')[0])
    except (ValueError, IndexError):
        return 9999


@vision_node(
    type_id='math_expr',
    label='Math Expression',
    category='math',
    icon='Function',
    description="Evaluates a math expression. Connected inputs map to a, b, c… in connection order. Supports: sin, cos, sqrt, clamp, lerp, log, pow, pi, e, (a+b)/c, etc.",
    dynamic_inputs=True,
    inputs=[],
    outputs=[
        {'id': 'result', 'color': 'scalar'},
    ],
    params=[
        {
            'id': 'expression',
            'label': 'Expression',
            'type': 'string',
            'default': 'a + b',
        },
    ]
)
class MathExprNode(NodeProcessor):
    def process(self, inputs, params):
        expr = str(params.get('expression', 'a + b')).strip()
        if not expr:
            return {'result': 0.0}

        # Sort dynamic port keys by embedded index → map to a, b, c…
        sorted_keys = sorted(inputs.keys(), key=_extract_port_index)
        variables = {}
        for i, key in enumerate(sorted_keys):
            if i >= 26:
                break
            varname = chr(ord('a') + i)
            val = inputs[key]
            try:
                variables[varname] = float(val) if val is not None else 0.0
            except (TypeError, ValueError):
                variables[varname] = 0.0

        try:
            result = _safe_eval(expr, variables)
        except Exception as e:
            print(f"[MathExpr] {e}")
            result = 0.0

        return {'result': result}
