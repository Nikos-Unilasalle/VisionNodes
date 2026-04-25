"""
Plugin registry — single source of truth for vision_node decorator, NodeProcessor,
NODE_SCHEMAS and NODE_CLASS_REGISTRY. Import from here instead of __main__.
"""
import queue
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional
from typing_extensions import TypedDict, Required


class ParamSpec(TypedDict, total=False):
    id: Required[str]
    label: str
    type: str          # 'int' | 'float' | 'number' | 'string' | 'bool' | 'toggle' | 'enum' | 'trigger' | 'code' | 'color'
    default: Any
    min: float
    max: float
    step: float
    options: list[str]


class PortSpec(TypedDict, total=False):
    id: Required[str]
    color: Required[str]  # 'image' | 'mask' | 'any' | 'scalar' | ...
    label: str


class NodeSchema(TypedDict, total=False):
    type: Required[str]
    label: Required[str]
    category: Required[str]
    icon: Required[str]
    description: str
    inputs: Required[list[PortSpec]]
    outputs: Required[list[PortSpec]]
    params: Required[list[ParamSpec]]
    resizable: bool
    min_width: int
    min_height: int
    colorable: bool


NODE_SCHEMAS: list[NodeSchema] = []
NODE_CLASS_REGISTRY: dict[str, type] = {}

_notification_queue: queue.Queue = queue.Queue()


def send_notification(message, progress=None, level='info', notif_id=None):
    _notification_queue.put_nowait({
        'id': notif_id or ('notif_' + str(uuid.uuid4())[:8]),
        'message': message,
        'progress': progress,
        'level': level,
    })


def vision_node(
    type_id: str, label: str, category: str = "custom", icon: str = "PenTool",
    inputs: Optional[list[PortSpec]] = None,
    outputs: Optional[list[PortSpec]] = None,
    params: Optional[list[ParamSpec]] = None,
    description: str = "",
    resizable: bool = False, min_width: int = 200, min_height: int = 150, colorable: bool = True,
):
    def decorator(cls):
        NODE_SCHEMAS.append({
            "type": type_id,
            "label": label,
            "category": category,
            "icon": icon,
            "description": description,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "params": params or [],
            "resizable": resizable,
            "min_width": min_width,
            "min_height": min_height,
            "colorable": colorable,
        })
        NODE_CLASS_REGISTRY[type_id] = cls
        return cls
    return decorator


class NodeProcessor(ABC):
    @abstractmethod
    def process(self, inputs, params): pass


def topological_sort(nodes: list, edges: list) -> list:
    """Kahn's algorithm. Returns node IDs in execution order.
    Nodes not reachable from any source (disconnected cycles) are omitted."""
    node_ids = {n['id'] for n in nodes}
    valid_edges = [
        e for e in edges
        if e.get('source') in node_ids and e.get('target') in node_ids
    ]
    adj: dict = {nid: [] for nid in node_ids}
    indegree: dict = {nid: 0 for nid in node_ids}
    for e in valid_edges:
        adj[e['source']].append(e['target'])
        indegree[e['target']] += 1

    from collections import deque
    queue = deque(nid for nid in node_ids if indegree[nid] == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    return order
