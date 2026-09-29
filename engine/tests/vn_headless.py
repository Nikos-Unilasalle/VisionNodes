"""Headless executor for .vn templates — test helper.

Mirrors the input-gathering rules of engine.py (lower-cased handle keys,
param externalization, string-enum index resolution) so a template can be run
end-to-end without the WebSocket server or the UI.
"""
import contextlib
import importlib
import io
import os
import sys
from collections import defaultdict, deque

import numpy as np

_ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ENGINE)

import registry  # noqa: E402

CANVAS_ONLY = {'canvas_frame', 'canvas_note', 'canvas_reroute'}


def load_plugins(names=None):
    """Import plugins (all of them when `names` is None); import errors are skipped."""
    plugin_dir = os.path.join(_ENGINE, 'plugins')
    files = names or [f[:-3] for f in sorted(os.listdir(plugin_dir))
                      if f.endswith('.py') and not f.startswith('_')]
    for name in files:
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                importlib.import_module(f'plugins.{name}')
        except Exception:
            pass


def schema(type_id):
    return next((s for s in registry.NODE_SCHEMAS if s['type'] == type_id), None)


def _topo_order(nodes, edges):
    ids = [n['id'] for n in nodes]
    indeg = {i: 0 for i in ids}
    succ = defaultdict(list)
    for e in edges:
        if e['source'] in indeg and e['target'] in indeg:
            succ[e['source']].append(e['target'])
            indeg[e['target']] += 1
    queue = deque(i for i in ids if indeg[i] == 0)
    order = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for t in succ[nid]:
            indeg[t] -= 1
            if indeg[t] == 0:
                queue.append(t)
    if len(order) != len(ids):
        raise ValueError('graph has a cycle')
    return order


def _resolve_params(node, inputs):
    params = dict(node.get('data', {}).get('params', {}))
    specs = (schema(node['type']) or {}).get('params', [])
    for ps in specs:
        pid = ps.get('id')
        if pid in inputs and inputs[pid] is not None:
            params[pid] = inputs[pid]
        opts = ps.get('options') or []
        if ps.get('type') == 'enum' and isinstance(ps.get('default'), str) and isinstance(params.get(pid), int):
            if 0 <= params[pid] < len(opts):
                params[pid] = opts[params[pid]]
    return params


def _gather_inputs(nid, edges_by_target, results):
    inputs = {'raw_frame': None}
    for e in edges_by_target.get(nid, []):
        src = results.get(e['source'])
        if src is None:
            continue
        sh = e.get('sourceHandle', 'main').split('__')[-1].lower()
        th = e.get('targetHandle', '').split('__')[-1].lower()
        val = src.get(sh)
        if val is None:
            val = {k.lower(): v for k, v in src.items()}.get(sh)
        if val is None or not th:
            continue
        inputs[th] = val
        if th in ('image', 'main') and isinstance(val, np.ndarray):
            inputs['image'] = val
        if th in ('data', 'in', 'value'):
            inputs.update(data=val, value=val)
            inputs['in'] = val
    return inputs


def run(vn, overrides=None):
    """Run a parsed .vn dict. `overrides` = {node_id: {param: value}}. Returns {node_id: outputs}."""
    overrides = overrides or {}
    nodes = [n for n in vn['nodes'] if n['type'] not in CANVAS_ONLY]
    reroutes = {n['id'] for n in vn['nodes'] if n['type'] == 'canvas_reroute'}
    edges = _collapse_reroutes(vn['edges'], reroutes)
    edges_by_target = defaultdict(list)
    for e in edges:
        edges_by_target[e['target']].append(e)

    by_id = {n['id']: n for n in nodes}
    results = {}
    for nid in _topo_order(nodes, edges):
        node = by_id[nid]
        cls = registry.NODE_CLASS_REGISTRY.get(node['type'])
        if cls is None:
            raise KeyError(f"unknown node type {node['type']} ({nid})")
        inputs = _gather_inputs(nid, edges_by_target, results)
        params = {**_resolve_params(node, inputs), **overrides.get(nid, {})}
        try:
            proc = cls()
        except TypeError:
            proc = cls(None)
        results[nid] = proc.process(inputs, params) or {}
    return results


def _collapse_reroutes(edges, reroutes):
    if not reroutes:
        return list(edges)
    upstream = {e['target']: e for e in edges if e['target'] in reroutes}

    def origin(e):
        while e['source'] in reroutes:
            e = {**upstream[e['source']], 'target': e['target'], 'targetHandle': e['targetHandle']}
        return e

    return [origin(e) for e in edges if e['target'] not in reroutes]
