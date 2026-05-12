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
    category: Required[str | list[str]]
    icon: Required[str]
    description: str
    inputs: Required[list[PortSpec]]
    outputs: Required[list[PortSpec]]
    params: Required[list[ParamSpec]]
    resizable: bool
    min_width: int
    min_height: int
    colorable: bool
    dynamic_inputs: bool
    dynamic_outputs: bool
    variable_inputs: bool
    hf_model: str

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
    type_id: str, label: str, category: str | list[str] = "custom", icon: str = "PenTool",
    inputs: Optional[list[PortSpec]] = None,
    outputs: Optional[list[PortSpec]] = None,
    params: Optional[list[ParamSpec]] = None,
    description: str = "",
    resizable: bool = False, min_width: int = 200, min_height: int = 150, colorable: bool = True,
    dynamic_inputs: bool = False, dynamic_outputs: bool = False, variable_inputs: bool = False,
    hf_model: str = "",
    hf_filename: str = "",
):
    def decorator(cls):
        _params = params or []
        if hf_model:
            has_token = any(p.get('id') == 'hf_token' for p in _params)
            if not has_token:
                _params.insert(0, {
                    'id': 'hf_token',
                    'label': 'Hugging Face Token (laisser vide si sauvegardé)',
                    'type': 'string',
                    'default': ''
                })

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
            "dynamic_inputs": dynamic_inputs,
            "dynamic_outputs": dynamic_outputs,
            "variable_inputs": variable_inputs,
            "hf_model": hf_model,
            "hf_filename": hf_filename,
        })
        NODE_CLASS_REGISTRY[type_id] = cls
        return cls
    return decorator


class NodeProcessor(ABC):
    def report_progress(self, value: float, message: str):
        """Call from process() to stream progress to the UI. value: 0.0–1.0 (1.0 dismisses after 3s)."""
        send_notification(message, progress=value, notif_id=f'proc_{type(self).__name__}')

    def get_hf_model_path(self, params: dict) -> Optional[str]:
        """Automatically fetch and return the path to the downloaded HuggingFace model."""
        import json, os, threading

        my_type = None
        for t, cls in NODE_CLASS_REGISTRY.items():
            if isinstance(self, cls):
                my_type = t
                break
        
        schema = next((s for s in NODE_SCHEMAS if s['type'] == my_type), None)
        if not schema or not schema.get('hf_model'):
            return None
            
        hf_model_str = schema['hf_model']
        hf_filename = schema.get('hf_filename', '')
        # Extract repo_id if it's a URL
        repo_id = hf_model_str.replace('https://huggingface.co/', '').strip()
        
        hf_token = params.get('hf_token', '')
        secrets_path = os.path.expanduser('~/.vnstudio/secrets.json')
        if hf_token:
            os.makedirs(os.path.dirname(secrets_path), exist_ok=True)
            secrets = {}
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path, 'r') as f:
                        secrets = json.load(f)
                except Exception: pass
            secrets['hf_token'] = hf_token
            try:
                with open(secrets_path, 'w') as f:
                    json.dump(secrets, f)
            except Exception: pass
        else:
            if os.path.exists(secrets_path):
                try:
                    with open(secrets_path, 'r') as f:
                        secrets = json.load(f)
                        if 'hf_token' in secrets:
                            hf_token = secrets['hf_token']
                except Exception: pass

        if hf_token:
            os.environ['HF_TOKEN'] = hf_token

        if not hasattr(self, '_hf_loading'):
            self._hf_loading = False
            self._hf_path = None
            self._hf_failed = False
            
        if self._hf_path:
            return self._hf_path
            
        if self._hf_failed:
            return None
            
        if not self._hf_loading:
            self._hf_loading = True
            
            def _download_thread():
                try:
                    notif_id = f'hf_download_{repo_id.replace("/", "_")}'
                    self.report_progress(0.1, f'Initializing {repo_id.split("/")[-1]}...')
                    from huggingface_hub import snapshot_download
                    
                    # We report slightly more progress during the wait
                    self.report_progress(0.3, f'Downloading {repo_id.split("/")[-1]} (check terminal for logs)...')
                    
                    if hf_filename:
                        # Download specific file
                        from huggingface_hub import hf_hub_download
                        path = hf_hub_download(repo_id=repo_id, filename=hf_filename, token=hf_token or None)
                    else:
                        # Download entire snapshot
                        from huggingface_hub import snapshot_download
                        path = snapshot_download(repo_id=repo_id, token=hf_token or None)
                    
                    self._hf_path = path
                    self.report_progress(1.0, f'{repo_id.split("/")[-1]} ready ✓')
                except Exception as e:
                    self._hf_failed = True
                    print(f'[HF] Model load FAILED: {e}')
                    send_notification(f'HF error: {str(e)[:120]}', level='error')
                finally:
                    self._hf_loading = False
                    
            threading.Thread(target=_download_thread, daemon=True).start()
            
        return None

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
