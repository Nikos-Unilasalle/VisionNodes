"""
Smoke test: every plugin file must import without error and register at least one node type.
Optional deep check: every registered NodeProcessor must be instantiable.
"""
import sys
import os
import glob
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from registry import NODE_CLASS_REGISTRY, NODE_SCHEMAS, NodeProcessor

_ENGINE_DIR = os.path.dirname(os.path.dirname(__file__))
_PLUGINS_DIR = os.path.join(_ENGINE_DIR, "plugins")

_plugin_files = sorted(
    f for f in glob.glob(os.path.join(_PLUGINS_DIR, "*.py"))
    if os.path.basename(f) != "__init__.py"
)


_LOAD_OK = "ok"
_LOAD_SKIP = "skip"
_LOAD_FAIL = "fail"


def _load_plugin(path: str) -> tuple[str, str]:
    """Load a plugin file; return (status, message).

    status is one of _LOAD_OK, _LOAD_SKIP (missing optional dep), _LOAD_FAIL (real error).
    """
    module_name = f"plugins.{os.path.basename(path)[:-3]}"
    if module_name in sys.modules:
        return _LOAD_OK, ""
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
        return _LOAD_OK, ""
    except ModuleNotFoundError as exc:
        del sys.modules[module_name]
        return _LOAD_SKIP, f"optional dependency missing: {exc.name}"
    except Exception as exc:
        del sys.modules[module_name]
        return _LOAD_FAIL, str(exc)


# ── Build parametrize list once ──────────────────────────────────────────────

_plugin_ids = [os.path.basename(p)[:-3] for p in _plugin_files]


@pytest.mark.parametrize("path,plugin_id", zip(_plugin_files, _plugin_ids), ids=_plugin_ids)
def test_plugin_imports(path, plugin_id):
    """Plugin must load without raising an exception (skip if optional dep missing)."""
    status, msg = _load_plugin(path)
    if status == _LOAD_SKIP:
        pytest.skip(msg)
    assert status == _LOAD_OK, f"{plugin_id} failed to import: {msg}"


# ── After all plugins loaded: registry integrity checks ──────────────────────

def test_all_plugins_loaded_fixture(tmp_path):
    """Load every plugin (idempotent) before registry checks; fail on real errors."""
    failures = {}
    for p in _plugin_files:
        status, msg = _load_plugin(p)
        if status == _LOAD_FAIL:
            failures[os.path.basename(p)[:-3]] = msg
    if failures:
        lines = "\n".join(f"  {k}: {v}" for k, v in failures.items())
        pytest.fail(f"{len(failures)} plugin(s) failed to load:\n{lines}")


def test_registry_not_empty():
    """At least one node type must be registered."""
    for p in _plugin_files:
        _load_plugin(p)
    assert len(NODE_CLASS_REGISTRY) > 0, "NODE_CLASS_REGISTRY is empty after loading all plugins"
    assert len(NODE_SCHEMAS) > 0, "NODE_SCHEMAS is empty after loading all plugins"


def test_registry_schema_class_parity():
    """Every type_id in NODE_SCHEMAS must have a class in NODE_CLASS_REGISTRY and vice-versa."""
    for p in _plugin_files:
        _load_plugin(p)

    schema_types = {s["type"] for s in NODE_SCHEMAS}
    registry_types = set(NODE_CLASS_REGISTRY.keys())

    only_in_schema = schema_types - registry_types
    only_in_registry = registry_types - schema_types

    errors = []
    if only_in_schema:
        errors.append(f"In NODE_SCHEMAS but not NODE_CLASS_REGISTRY: {sorted(only_in_schema)}")
    if only_in_registry:
        errors.append(f"In NODE_CLASS_REGISTRY but not NODE_SCHEMAS: {sorted(only_in_registry)}")

    assert not errors, "\n".join(errors)


def test_every_class_is_node_processor():
    """Every registered class must be a NodeProcessor subclass."""
    for p in _plugin_files:
        _load_plugin(p)

    bad = [
        type_id for type_id, cls in NODE_CLASS_REGISTRY.items()
        if not (isinstance(cls, type) and issubclass(cls, NodeProcessor))
    ]
    assert not bad, f"Not a NodeProcessor subclass: {bad}"


def test_every_class_instantiable():
    """Every registered NodeProcessor must be instantiable with no arguments."""
    for p in _plugin_files:
        _load_plugin(p)

    failures = {}
    for type_id, cls in NODE_CLASS_REGISTRY.items():
        if not (isinstance(cls, type) and issubclass(cls, NodeProcessor)):
            continue
        try:
            cls()
        except Exception as exc:
            failures[type_id] = str(exc)

    if failures:
        lines = "\n".join(f"  {k}: {v}" for k, v in failures.items())
        pytest.fail(f"{len(failures)} class(es) failed to instantiate:\n{lines}")


def test_schema_required_fields():
    """Every schema entry must have type, label, and category."""
    for p in _plugin_files:
        _load_plugin(p)

    bad = []
    for s in NODE_SCHEMAS:
        missing = [f for f in ("type", "label", "category") if not s.get(f)]
        if missing:
            bad.append(f"{s.get('type', '?')!r} missing fields: {missing}")

    assert not bad, "\n".join(bad)
