"""Regression: a node id reused with a different type must not keep running the old processor.

Loading template B over template A (or regenerating a template) can keep a node id while
changing its type. VisionEngine used to reuse the cached processor instance for that id,
so the old node's code ran silently under the new node's UI.
"""
import asyncio
import contextlib
import io
import os
import sys

_ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ENGINE)
with contextlib.redirect_stdout(io.StringIO()):
    import engine as E  # noqa: E402


def _graph(node_type, params):
    return {'nodes': [{'id': 'x', 'type': node_type, 'position': {'x': 0, 'y': 0},
                       'data': {'label': node_type, 'params': params}}],
            'edges': []}


async def _run_once(eng):
    task = asyncio.create_task(eng.run())
    for _ in range(100):
        await asyncio.sleep(0.02)
        if not eng._run_event.is_set():
            break
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def _engine():
    eng = E.VisionEngine()
    eng._schema_by_type = {s['type']: s for s in E.NODE_SCHEMAS}
    return eng


def test_instance_is_replaced_when_type_changes():
    eng = _engine()
    eng.update_graph(_graph('scalar_input', {'value': 3.0}))
    asyncio.run(_run_once(eng))
    old = eng.node_instances['x']

    eng.update_graph(_graph('string_input', {'value': 'hello'}))

    inst = eng.node_instances.get('x')
    assert inst is None or type(inst) is not type(old)


def test_new_type_actually_runs_after_type_change():
    eng = _engine()

    async def scenario():  # one event loop: the engine's asyncio.Event is loop-bound
        eng.update_graph(_graph('scalar_input', {'value': 3.0}))
        await _run_once(eng)
        eng.update_graph(_graph('string_input', {'value': 'hello'}))
        await _run_once(eng)

    asyncio.run(scenario())
    assert type(eng.node_instances['x']) is E.NODE_CLASS_REGISTRY['string_input']


def test_instance_is_kept_when_type_unchanged():
    eng = _engine()
    eng.update_graph(_graph('scalar_input', {'value': 3.0}))
    asyncio.run(_run_once(eng))
    first = eng.node_instances['x']

    eng.update_graph(_graph('scalar_input', {'value': 5.0}))

    assert eng.node_instances['x'] is first  # stateful nodes (trackers, recorders) keep state
