"""Standalone Python script generator from a VNStudio pipeline graph."""
from __future__ import annotations

import ast
import inspect

from registry import NODE_CLASS_REGISTRY, NODE_SCHEMAS, topological_sort


_SOURCE_TYPES = {'input_webcam', 'input_image', 'input_movie', 'input_solid_color'}
_SKIP_TYPES = {
    'canvas_note', 'canvas_reroute', 'canvas_frame',
    'group_node', 'group_input', 'group_output',
    'export_py', 'output_display', 'output_movie',
    'data_inspector',
}
_SKIP_MODULES = {'registry', '__main__', 'code_generator'}

# Imports safe to include in standalone scripts
_IMPORT_WHITELIST = {
    'cv2', 'numpy', 'math', 'os', 'sys', 're', 'json', 'base64',
    'PIL', 'mediapipe', 'sklearn', 'scipy', 'torch', 'tensorflow',
    'threading', 'time', 'typing', 'collections', 'itertools',
    'pathlib', 'tempfile', 'functools', 'struct', 'copy', 'random',
    'urllib', 'io', 'abc', 'enum', 'dataclasses',
}


def _out_var(node_id: str) -> str:
    safe = node_id.replace('-', '_')
    return f'_out_{safe}'


def _inst_var(node_id: str) -> str:
    safe = node_id.replace('-', '_')
    return f'_inst_{safe}'


def _port_id(handle: str) -> str:
    return handle.split('__', 1)[-1] if '__' in handle else handle


def _import_root(imp_seg: str) -> str:
    """Extract root module name from import statement."""
    # 'import cv2' → 'cv2'
    # 'from mediapipe.tasks import python' → 'mediapipe'
    # 'import numpy as np' → 'numpy'
    seg = imp_seg.strip()
    if seg.startswith('from '):
        mod = seg[5:].split()[0]
    elif seg.startswith('import '):
        mod = seg[7:].split()[0].split('.')[0]
    else:
        return ''
    return mod.split('.')[0]


def _is_engine_file(fpath: str) -> bool:
    import os
    return os.path.basename(fpath) == 'engine.py'


def _targeted_classes(cls: type, source: str) -> dict[str, str]:
    """Extract cls + its local base classes only. Skip NodeProcessor/ABC."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    all_defs: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            seg = ast.get_source_segment(source, node)
            if seg:
                all_defs[node.name] = seg

    skip = {'NodeProcessor', 'ABC', 'object'}
    needed: dict[str, str] = {}
    queue = [cls.__name__]
    visited: set[str] = set()

    while queue:
        name = queue.pop(0)
        if name in visited or name in skip or name not in all_defs:
            continue
        visited.add(name)
        needed[name] = all_defs[name]
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ClassDef) and node.name == name:
                for base in node.bases:
                    base_name = base.id if isinstance(base, ast.Name) else None
                    if base_name and base_name in all_defs and base_name not in skip:
                        queue.append(base_name)

    return needed


def _file_imports(source: str, engine_file: bool = False) -> list[str]:
    # engine.py imports are all engine-internal; cv2/numpy already hardcoded
    if engine_file:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ImportFrom) and node.module in _SKIP_MODULES:
            continue
        seg = ast.get_source_segment(source, node) or ''
        if not seg or seg in seen:
            continue
        seen.add(seg)
        result.append(seg)
    return result


def generate_pipeline_script(nodes: list[dict], edges: list[dict], export_node_id: str) -> str:
    schema_map = {s['type']: s for s in NODE_SCHEMAS}

    # Split nodes: pipeline vs skip
    pipeline_nodes = [
        n for n in nodes
        if n['id'] != export_node_id and n.get('type') not in _SKIP_TYPES
    ]
    pipeline_ids = {n['id'] for n in pipeline_nodes}
    # Only keep edges between pipeline nodes (filters stale/parasitic edges)
    internal_edges = [
        e for e in edges
        if e.get('target') != export_node_id
        and e.get('source') in pipeline_ids
        and e.get('target') in pipeline_ids
    ]
    export_edges   = [e for e in edges if e.get('target') == export_node_id]

    # Topological execution order
    order    = topological_sort(pipeline_nodes, internal_edges)
    node_map = {n['id']: n for n in pipeline_nodes}
    ordered  = [node_map[nid] for nid in order if nid in node_map]

    # Edge lookup: (target_id, target_port) → (source_id, source_port, target_color)
    # target_color used for fallback color-based matching (engine uses same logic)
    edge_lookup: dict[tuple[str, str], tuple[str, str, str]] = {}
    for e in internal_edges:
        src_id     = e.get('source', '')
        tgt_id     = e.get('target', '')
        src_port   = _port_id(e.get('sourceHandle', ''))
        tgt_handle = e.get('targetHandle', '')
        tgt_port   = _port_id(tgt_handle)
        tgt_color  = tgt_handle.split('__')[0] if '__' in tgt_handle else ''
        edge_lookup[(tgt_id, tgt_port)] = (src_id, src_port, tgt_color)

    # Export node port labels (for return key names)
    export_node = next((n for n in nodes if n['id'] == export_node_id), None)
    export_ports: list[dict] = []
    if export_node:
        export_ports = (export_node.get('data') or {}).get('ports') or []

    # Collect imports and class bodies from all used plugin files
    all_imports: list[str] = []
    all_classes: dict[str, str] = {}
    seen_files: set[str] = set()

    for node in ordered:
        ntype = node.get('type', '')
        if ntype in _SOURCE_TYPES:
            continue
        cls = NODE_CLASS_REGISTRY.get(ntype)
        if cls is None:
            continue
        try:
            fpath = inspect.getfile(cls)
        except TypeError:
            continue
        if fpath in seen_files:
            continue
        seen_files.add(fpath)
        try:
            with open(fpath, encoding='utf-8') as f:
                src = f.read()
        except OSError:
            continue
        is_engine = _is_engine_file(fpath)
        for imp in _file_imports(src, engine_file=is_engine):
            if imp not in all_imports:
                all_imports.append(imp)
        for name, body in _targeted_classes(cls, src).items():
            if name not in all_classes:
                all_classes[name] = body

    # ── Script assembly ───────────────────────────────────────────────────────
    L: list[str] = []

    L += ['# Generated by VNStudio', '']
    L += ['import cv2', 'import numpy as np']
    for imp in all_imports:
        if not imp.startswith('import cv2') and not imp.startswith('import numpy'):
            L.append(imp)
    L += ['', '', 'class NodeProcessor:', '    def process(self, inputs, params): raise NotImplementedError', '', '']

    for cls_body in all_classes.values():
        L.append(cls_body)
        L += ['', '']

    # Module-level node instances (handles __init__ with model loading)
    non_source = [n for n in ordered if n.get('type') not in _SOURCE_TYPES]
    if non_source:
        for node in non_source:
            ntype = node.get('type', '')
            cls   = NODE_CLASS_REGISTRY.get(ntype)
            if cls:
                L.append(f'{_inst_var(node["id"])} = {cls.__name__}()')
        L += ['', '']

    # Pipeline function
    L.append('def run_pipeline(frame):')

    for node in ordered:
        nid   = node['id']
        ntype = node.get('type', '')
        label = (node.get('data') or {}).get('label') or ntype
        params = (node.get('data') or {}).get('params') or {}

        L.append(f'    # {label}')

        if ntype in _SOURCE_TYPES:
            L.append(f'    {_out_var(nid)} = {{"main": frame}}')
            L.append('')
            continue

        cls = NODE_CLASS_REGISTRY.get(ntype)
        if cls is None:
            L.append(f'    # WARNING: unresolved type {ntype!r}')
            L.append(f'    {_out_var(nid)} = {{}}')
            L.append('')
            continue

        # Mirror engine input resolution: tgt_port = handle.split('__')[-1]
        # 'main'/'image' tgt_port also writes inputs['image'] (engine special case)
        inp_dict: dict[str, str] = {}  # port_name → code_expr
        for (tid, tport), (sid, sport, _) in edge_lookup.items():
            if tid != nid or not tport:
                continue
            expr = f'{_out_var(sid)}.get({sport!r})'
            inp_dict[tport] = expr
            if tport in ('main', 'image') and 'image' not in inp_dict:
                inp_dict['image'] = expr

        clean_params = {
            k: v for k, v in params.items()
            if isinstance(v, (int, float, str, bool, type(None)))
        }

        if inp_dict:
            inp_lines = ', '.join(f'{k!r}: {v}' for k, v in inp_dict.items())
            L.append(f'    {_out_var(nid)} = {_inst_var(nid)}.process({{{inp_lines}}}, {clean_params!r})')
        else:
            L.append(f'    {_out_var(nid)} = {_inst_var(nid)}.process({{}}, {clean_params!r})')
        L.append('')

    # Return statement
    returns: list[str] = []
    for i, e in enumerate(export_edges):
        src_id     = e.get('source', '')
        src_port   = _port_id(e.get('sourceHandle', ''))
        tgt_handle = e.get('targetHandle', '')
        port_obj   = next((p for p in export_ports if p.get('id') == tgt_handle), None)
        key        = (port_obj.get('label') or f'output_{i}') if port_obj else f'output_{i}'
        returns.append(f'        {key!r}: {_out_var(src_id)}.get({src_port!r})')

    if returns:
        L.append('    return {')
        L += [r + ',' for r in returns]
        L.append('    }')
    else:
        L.append('    return {}')

    L += [
        '', '',
        "if __name__ == '__main__':",
        '    cap = cv2.VideoCapture(0)',
        '    while True:',
        '        ret, frame = cap.read()',
        '        if not ret:',
        '            break',
        '        outputs = run_pipeline(frame)',
        '        for name, img in outputs.items():',
        '            if isinstance(img, np.ndarray):',
        '                cv2.imshow(name, img)',
        '        if cv2.waitKey(1) & 0xFF == ord("q"):',
        '            break',
        '    cap.release()',
        '    cv2.destroyAllWindows()',
    ]

    return '\n'.join(L)
