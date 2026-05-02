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


def _is_engine_file(fpath: str) -> bool:
    import os
    return os.path.basename(fpath) == 'engine.py'


def _get_source_file(cls: type) -> str | None:
    """Get plugin source file. Falls back to method co_filename when torch
    patches inspect.getfile and raises TypeError for dynamically-loaded classes."""
    try:
        return inspect.getfile(cls)
    except TypeError:
        pass
    for attr in ('process', '__init__', '_load_model', 'calc'):
        meth = getattr(cls, attr, None)
        if meth is None:
            continue
        code = getattr(getattr(meth, '__func__', meth), '__code__', None)
        if code:
            return code.co_filename
    return None


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


def _extract_file_content(
    source: str,
    needed_names: set[str],
    registered_names: set[str],
    engine_file: bool = False,
) -> str:
    """Extract top-level content from a plugin file.

    engine.py  — only the needed class bodies (no helpers, no imports).
    plugin file — all top-level defs: functions, constants, helper classes,
                  plus needed registered node classes.
                  Registered node classes NOT in this pipeline are skipped.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ''

    if engine_file:
        blocks = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in needed_names:
                seg = ast.get_source_segment(source, node)
                if seg:
                    blocks.append(seg)
        return '\n\n'.join(blocks)

    blocks = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue  # collected separately via _file_imports
        if isinstance(node, ast.ClassDef):
            # Registered node class not needed in this pipeline → skip
            if node.name in registered_names and node.name not in needed_names:
                continue
        seg = ast.get_source_segment(source, node)
        if seg:
            blocks.append(seg)
    return '\n\n'.join(blocks)


def generate_pipeline_script(nodes: list[dict], edges: list[dict], export_node_id: str) -> str:
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
    export_edges = [e for e in edges if e.get('target') == export_node_id]

    # Topological execution order
    order    = topological_sort(pipeline_nodes, internal_edges)
    node_map = {n['id']: n for n in pipeline_nodes}
    ordered  = [node_map[nid] for nid in order if nid in node_map]

    # Edge lookup: (target_id, target_port) → (source_id, source_port, target_color)
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

    # All registered node class names — used to distinguish node classes from helpers
    registered_names: set[str] = {cls.__name__ for cls in NODE_CLASS_REGISTRY.values()}

    # First pass: collect file paths and which class names are needed per file
    file_cache: dict[str, str] = {}
    file_needed_names: dict[str, set[str]] = {}
    file_is_engine: dict[str, bool] = {}
    fpath_order: list[str] = []  # preserve first-seen order

    for node in ordered:
        ntype = node.get('type', '')
        if ntype in _SOURCE_TYPES:
            continue
        cls = NODE_CLASS_REGISTRY.get(ntype)
        if cls is None:
            continue
        fpath = _get_source_file(cls)
        if fpath is None:
            continue
        if fpath not in file_cache:
            try:
                with open(fpath, encoding='utf-8') as f:
                    file_cache[fpath] = f.read()
            except OSError:
                continue
            file_is_engine[fpath] = _is_engine_file(fpath)
            file_needed_names[fpath] = set()
            fpath_order.append(fpath)
        file_needed_names[fpath].add(cls.__name__)

    # Second pass: extract imports and content per file
    all_imports: list[str] = []
    all_content_blocks: list[str] = []

    for fpath in fpath_order:
        src       = file_cache[fpath]
        is_engine = file_is_engine[fpath]
        needed    = file_needed_names[fpath]

        for imp in _file_imports(src, engine_file=is_engine):
            if imp not in all_imports:
                all_imports.append(imp)

        block = _extract_file_content(src, needed, registered_names, engine_file=is_engine)
        if block:
            all_content_blocks.append(block)

    # ── Script assembly ───────────────────────────────────────────────────────
    L: list[str] = []

    L += ['# Generated by VNStudio', '']
    L += ['import cv2', 'import numpy as np']
    for imp in all_imports:
        if not imp.startswith('import cv2') and not imp.startswith('import numpy'):
            L.append(imp)
    L += ['', '', 'class NodeProcessor:', '    def process(self, inputs, params): raise NotImplementedError', '', '']

    for block in all_content_blocks:
        L.append(block)
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
        nid    = node['id']
        ntype  = node.get('type', '')
        label  = (node.get('data') or {}).get('label') or ntype
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

        # Mirror engine input resolution: tgt_port also sets inputs['image'] when main/image
        inp_dict: dict[str, str] = {}
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
