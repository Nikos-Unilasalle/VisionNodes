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
    assert 'Error' in str(out.get('out_any', ''))


def test_blocked_open():
    out = _run("open('/tmp/pwned', 'w')")
    assert 'Error' in str(out.get('out_any', ''))


def test_blocked_import():
    out = _run("import os; out_any = os.getcwd()")
    assert out.get('out_any') is None or 'Error' in str(out.get('out_any', ''))


def test_blocked_dunder_import():
    out = _run("__import__('os').system('echo pwned')")
    assert 'Error' in str(out.get('out_any', ''))


def test_numpy_available():
    out = _run("out_scalar = float(np.array([1, 2, 3]).mean())")
    assert out['out_scalar'] == 2.0


def test_list_output():
    out = _run("out_list = [1, 2, 3]")
    assert out['out_list'] == [1, 2, 3]
