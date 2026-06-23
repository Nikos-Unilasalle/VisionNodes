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

# ── Writable package overlay (for bundled / read-only installs) ─────────────────
# In a packaged app (.app/.exe/AppImage) the bundled interpreter's site-packages
# is read-only, so runtime `pip install` (ensure_packages) would fail. We route
# such installs into ~/.vnstudio via PYTHONUSERBASE + `pip --user`, and put that
# user-site on sys.path so the freshly installed packages import immediately.
# In dev (.venv, writable) this is a no-op and installs go to the venv as before.
import os as _os
import sys as _sys
import site as _site
import sysconfig as _sysconfig

def _site_is_writable() -> bool:
    """True when the interpreter's main site-packages can be written to."""
    p = _sysconfig.get_paths().get('purelib')
    return bool(p) and _os.access(p, _os.W_OK)

VN_HOME = _os.path.join(_os.path.expanduser('~'), '.vnstudio')

def setup_user_overlay() -> None:
    """Make ~/.vnstudio a writable, importable package overlay (bundled only)."""
    _os.makedirs(VN_HOME, exist_ok=True)
    _os.environ.setdefault('PYTHONUSERBASE', VN_HOME)
    # site.USER_BASE/USER_SITE were resolved at interpreter start from the default
    # home; recompute now that PYTHONUSERBASE points at ~/.vnstudio.
    _site.ENABLE_USER_SITE = True
    _site.USER_BASE = None
    _site.USER_SITE = None
    us = _site.getusersitepackages()
    _os.makedirs(us, exist_ok=True)
    if us not in _sys.path:
        _site.addsitedir(us)

# Only stand up the overlay when the main site-packages is read-only (packaged
# build). Detecting by writability keeps dev (.venv) on its normal install path,
# where `pip --user` is refused inside a virtualenv anyway.
_USE_USER_OVERLAY = not _site_is_writable()
if _USE_USER_OVERLAY:
    setup_user_overlay()

# ── Cancel bus ────────────────────────────────────────────────────────────────
import threading as _threading
_cancel_flags: dict[str, _threading.Event] = {}

# ── Install-state bus ──────────────────────────────────────────────────────────
# Keyed by notif_id so reset_install_state() can clear by the same id the
# frontend received in the error notification.
_install_states: dict[str, dict] = {}

def reset_install_state(notif_id: str) -> None:
    """Clear a failed install state so the next engine tick retries it."""
    _install_states.pop(notif_id, None)
    print(f"[registry] Install state reset: {notif_id!r}")

def request_cancel(notif_id: str) -> None:
    """Signal cancellation for a running operation identified by notif_id."""
    flag = _cancel_flags.get(notif_id)
    if flag is None:
        _cancel_flags[notif_id] = _threading.Event()
    _cancel_flags[notif_id].set()

def is_cancelled(notif_id: str) -> bool:
    """Return True if cancellation has been requested for notif_id."""
    return _cancel_flags.get(notif_id, _threading.Event()).is_set()

def clear_cancel(notif_id: str) -> None:
    """Clear the cancel flag (call at start of a new operation)."""
    if notif_id in _cancel_flags:
        _cancel_flags[notif_id].clear()


def send_notification(message, progress=None, level='info', notif_id=None):
    _notification_queue.put_nowait({
        'id': notif_id or ('notif_' + str(uuid.uuid4())[:8]),
        'message': message,
        'progress': progress,
        'level': level,
    })


import contextlib

@contextlib.contextmanager
def hf_ui_progress(notif_id: str, prefix: str = "Downloading"):
    """Context manager to intercept huggingface_hub downloads and pipe them to UI."""
    try:
        from huggingface_hub import utils as hf_utils
        import tqdm
        
        original_tqdm = hf_utils.tqdm
        
        class UI_Tqdm(tqdm.tqdm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._notif_id = notif_id
                self._prefix = prefix
                self._last_pct = 0.0

            def update(self, n=1):
                super().update(n)
                if getattr(self, 'total', None) and self.total > 0:
                    pct = self.n / self.total
                    if pct - self._last_pct >= 0.05 or pct >= 1.0:
                        desc = getattr(self, 'desc', '') or ''
                        desc = desc.split('/')[-1] if desc else ''
                        msg = f"{self._prefix} {desc}: {int(pct*100)}%"
                        send_notification(msg, progress=pct, notif_id=self._notif_id)
                        self._last_pct = pct

        hf_utils.tqdm = UI_Tqdm
        yield
    except ImportError:
        yield
    finally:
        try:
            from huggingface_hub import utils as hf_utils
            hf_utils.tqdm = original_tqdm
        except Exception:
            pass



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
                        with hf_ui_progress(notif_id, prefix="Downloading"):
                            path = hf_hub_download(repo_id=repo_id, filename=hf_filename, token=hf_token or None)
                    else:
                        # Download entire snapshot
                        from huggingface_hub import snapshot_download
                        with hf_ui_progress(notif_id, prefix="Downloading"):
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

    def ensure_packages(self, packages: list[str], pip_names: Optional[list[str]] = None, notif_id: str = None) -> bool:
        """
        Check if packages are installed. If not, try to install them via pip in a background thread.
        Returns True if already installed, False if installation is in progress or failed.
        
        :param packages: List of import names to check (e.g. ['transformers', 'timm'])
        :param pip_names: List of pip package names if different from import names.
        :param notif_id: Optional notification ID for status updates.
        """
        import importlib.util
        import sys
        import subprocess
        import threading

        # 1. Quick check if everything is already there
        missing_indices = []
        for i, pkg in enumerate(packages):
            if importlib.util.find_spec(pkg) is None:
                missing_indices.append(i)
        
        if not missing_indices:
            return True

        # 2. State management for installation (module-level so reset_install_state() can clear it)
        nid = notif_id or f'install_{self.__class__.__name__}'
        state = _install_states.setdefault(nid, {'installing': False, 'failed': False, 'success': False})

        if state['success']:
            return True
        if state['failed']:
            return False

        # 3. Trigger installation if not already running
        if not state['installing']:
            state['installing'] = True

            # Use provided pip names or fallback to import names
            targets = []
            for idx in missing_indices:
                if pip_names and idx < len(pip_names):
                    targets.append(pip_names[idx])
                else:
                    targets.append(packages[idx])

            def _install_thread():
                try:
                    send_notification(
                        f"Installing dependencies: {', '.join(targets)}...",
                        progress=0.1, notif_id=nid
                    )

                    # --no-build-isolation reuses packages already installed,
                    # avoiding redundant re-downloads of heavy deps like torch.
                    cmd = [
                        sys.executable, "-m", "pip", "install", "--quiet",
                        "--no-build-isolation",
                    ]
                    # Packaged build: site-packages is read-only, so install into
                    # the ~/.vnstudio user overlay (already on sys.path). pip --user
                    # still resolves against the bundled packages, so torch & co.
                    # are reused, not reinstalled. --break-system-packages is
                    # required because python-build-standalone ships an
                    # EXTERNALLY-MANAGED marker (PEP 668) that otherwise blocks pip.
                    if _USE_USER_OVERLAY:
                        cmd += ["--user", "--break-system-packages"]
                    subprocess.check_call(cmd + targets)

                    # Make the freshly installed modules importable in this
                    # already-running interpreter (no engine restart needed).
                    import importlib
                    importlib.invalidate_caches()

                    state['success'] = True
                    send_notification(
                        f"Dependencies installed ✓",
                        progress=1.0, notif_id=nid
                    )
                    print(f"[{self.__class__.__name__}] Successfully installed {targets}")
                except Exception as e:
                    state['failed'] = True
                    print(f"[{self.__class__.__name__}] Installation FAILED: {e}")
                    send_notification(
                        f"Install failed: {str(e)[:100]}",
                        level='error', notif_id=nid
                    )
                finally:
                    state['installing'] = False

            threading.Thread(target=_install_thread, daemon=True).start()
        
        return False

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
