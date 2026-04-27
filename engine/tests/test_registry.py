import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from registry import vision_node, NodeProcessor, NODE_SCHEMAS, NODE_CLASS_REGISTRY, topological_sort


# ── vision_node decorator ──────────────────────────────────────────────────

def test_vision_node_registers_schema():
    initial_count = len(NODE_SCHEMAS)

    @vision_node(type_id='_test_node', label='Test', category='test')
    class _TestNode(NodeProcessor):
        def process(self, inputs, params): return {}

    assert len(NODE_SCHEMAS) == initial_count + 1
    schema = next(s for s in NODE_SCHEMAS if s['type'] == '_test_node')
    assert schema['label'] == 'Test'
    assert schema['category'] == 'test'
    assert NODE_CLASS_REGISTRY['_test_node'] is _TestNode


def test_vision_node_defaults():
    @vision_node(type_id='_test_defaults', label='Defaults')
    class _D(NodeProcessor):
        def process(self, inputs, params): return {}

    schema = next(s for s in NODE_SCHEMAS if s['type'] == '_test_defaults')
    assert schema['inputs'] == []
    assert schema['outputs'] == []
    assert schema['params'] == []
    assert schema['resizable'] is False
    assert schema['colorable'] is True


def test_node_processor_abstract():
    with pytest.raises(TypeError):
        NodeProcessor()  # type: ignore


# ── topological_sort ──────────────────────────────────────────────────────

def _nodes(*ids):
    return [{'id': i} for i in ids]

def _edge(src, tgt):
    return {'source': src, 'target': tgt}


def test_topo_linear_chain():
    nodes = _nodes('a', 'b', 'c')
    edges = [_edge('a', 'b'), _edge('b', 'c')]
    order = topological_sort(nodes, edges)
    assert order.index('a') < order.index('b') < order.index('c')


def test_topo_diamond():
    nodes = _nodes('src', 'l', 'r', 'dst')
    edges = [_edge('src', 'l'), _edge('src', 'r'), _edge('l', 'dst'), _edge('r', 'dst')]
    order = topological_sort(nodes, edges)
    assert order.index('src') < order.index('dst')
    assert order.index('l') < order.index('dst')
    assert order.index('r') < order.index('dst')


def test_topo_disconnected():
    nodes = _nodes('a', 'b', 'c')
    edges = [_edge('a', 'b')]
    order = topological_sort(nodes, edges)
    assert set(order) == {'a', 'b', 'c'}
    assert order.index('a') < order.index('b')


def test_topo_no_edges():
    nodes = _nodes('x', 'y', 'z')
    order = topological_sort(nodes, [])
    assert set(order) == {'x', 'y', 'z'}


def test_topo_empty():
    assert topological_sort([], []) == []


def test_topo_ignores_invalid_edges():
    nodes = _nodes('a', 'b')
    edges = [_edge('a', 'b'), _edge('a', 'ghost')]  # 'ghost' not in nodes
    order = topological_sort(nodes, edges)
    assert set(order) == {'a', 'b'}
    assert order.index('a') < order.index('b')
