import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util
from registry import NODE_CLASS_REGISTRY

_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'logic_python.py')
_spec = importlib.util.spec_from_file_location('plugins.logic_python', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

PythonNode = NODE_CLASS_REGISTRY['logic_python']


def _run(code, inputs=None):
    node = PythonNode()
    return node.process(inputs or {}, {'code': code})


def test_basic_output():
    out = _run("out_scalar = 42.0")
    assert out['out_scalar'] == 42.0


def test_state_persists_across_frames():
    node = PythonNode()
    node.process({}, {'code': "state['counter'] = state.get('counter', 0) + 1"})
    node.process({}, {'code': "state['counter'] = state.get('counter', 0) + 1"})
    result = node.process({}, {'code': "out_scalar = float(state.get('counter', 0))"})
    assert result['out_scalar'] == 2.0


def test_error_does_not_crash():
    out = _run("raise ValueError('test error')")
    assert 'error' in out.get('__error__', '').lower()


def test_blocked_open():
    out = _run("open('/tmp/pwned', 'w')")
    assert 'not defined' in out.get('__error__', '')


def test_blocked_import():
    out = _run("import os; out_any = os.getcwd()")
    assert 'blocked' in out.get('__error__', '').lower()


def test_blocked_dunder_import():
    out = _run("__import__('os').system('echo pwned')")
    assert 'blocked' in out.get('__error__', '').lower()


def test_numpy_available():
    out = _run("out_scalar = float(np.array([1, 2, 3]).mean())")
    assert out['out_scalar'] == 2.0


def test_list_output():
    out = _run("out_list = [1, 2, 3]")
    assert out['out_list'] == [1, 2, 3]


# ── Dynamic auto-typed I/O ────────────────────────────────────────────────────

def test_dynamic_inputs_injected_as_vars():
    # Every connected input becomes a same-named variable (a, b, c…).
    out = _run("out_a = a + b + c", inputs={'a': 1, 'b': 2, 'c': 3})
    assert out['out_a'] == 6


def test_collects_multiple_out_vars():
    out = _run("out_a = 10\nout_b = 20\nout_c = 30")
    assert out['out_a'] == 10 and out['out_b'] == 20 and out['out_c'] == 30


def test_only_out_prefixed_vars_returned():
    out = _run("tmp = 99\nout_a = tmp")
    assert out['out_a'] == 99 and 'tmp' not in out


def test_reserved_vars_not_emitted_as_outputs():
    # np/cv2/pd/state must never leak into outputs even though they're in ctx.
    out = _run("out_a = 1")
    assert 'np' not in out and 'state' not in out


def test_raw_frame_input_not_injected():
    # engine always passes raw_frame; it must not be referenceable as a script var.
    out = _run("out_a = raw_frame", inputs={'raw_frame': object(), 'a': 5})
    assert "'raw_frame' is not defined" in out['__error__']
