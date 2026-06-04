import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util
from registry import NODE_CLASS_REGISTRY

_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'logic_math.py')
_spec = importlib.util.spec_from_file_location('plugins.logic_math', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ScalarInputNode = NODE_CLASS_REGISTRY['scalar_input']


def test_scalar_input_basic():
    node = ScalarInputNode()
    res = node.process({}, {'format': 1, 'value': 42.5})
    assert res['value'] == 42.5


def test_scalar_input_integer_format():
    node = ScalarInputNode()
    res = node.process({}, {'format': 0, 'value': 42.5})
    assert res['value'] == 42


def test_scalar_input_clamping():
    node = ScalarInputNode()
    # Test clamping high
    res = node.process({}, {'format': 1, 'value': 150.0, 'min': 0.0, 'max': 100.0})
    assert res['value'] == 100.0

    # Test clamping low
    res = node.process({}, {'format': 1, 'value': -50.0, 'min': 0.0, 'max': 100.0})
    assert res['value'] == 0.0

    # Test inverted bounds (min > max)
    res = node.process({}, {'format': 1, 'value': 50.0, 'min': 100.0, 'max': 0.0})
    assert res['value'] == 50.0
