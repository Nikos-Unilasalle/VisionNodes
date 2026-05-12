import sys
import subprocess

def check_and_install_dependencies():
    # Map package names to import names
    deps = {
        "opencv-python": "cv2",
        "mediapipe": "mediapipe",
        "websockets": "websockets",
        "numpy": "numpy",
        "ultralytics": "ultralytics",
        "torch": "torch",
        "pytesseract": "pytesseract",
        "easyocr": "easyocr",
        "rasterio": "rasterio",
        "pyproj": "pyproj",
        "earthengine-api": "ee",
        "geopy": "geopy",
        "librosa": "librosa",
        "soundfile": "soundfile",
    }
    
    missing = []
    for pkg, import_name in deps.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
            
    if missing:
        print(f"\n📦 VISION NODES :: Missing dependencies: {missing}")
        print("🚀 For a clean experience, please run: npm run setup\n")
        print("Trying auto-installation... please wait.\n")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print("\n✅ Installation complete. Starting engine...\n")
        except Exception as e:
            print(f"\n❌ Auto-install failed: {e}")
            print("👉 Please run manually: npm run setup or pip install -r engine/requirements.txt\n")

# Silencing OpenCV / FFMPEG startup warnings
import os
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_PRIORITY_BACKEND"] = "AVFOUNDATION"

# Run bootstrap before other imports
check_and_install_dependencies()

import asyncio
import json
import cv2
import base64
import numpy as np
import websockets
import time
import os
from registry import (
    NODE_SCHEMAS, NODE_CLASS_REGISTRY,
    _notification_queue, send_notification,
    topological_sort,
)

# Optimized for Linux/Arch, use CAP_ANY as primary to avoid V4L2 index errors
CAP_BACKEND = cv2.CAP_ANY

def list_available_cameras():
    index = 0
    arr = []
    while index < 8:
        # Try primary backend first, then CAP_V4L2 as fallback specifically for Linux
        cap = cv2.VideoCapture(index, CAP_BACKEND)
        if not cap.isOpened():
            cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
            
        if cap.isOpened():
            arr.append(index)
            cap.release()
        index += 1
    return arr

# --- Plugin System ---

def load_plugins():
    import importlib.util
    import glob
    import sys

    engine_dir = os.path.dirname(os.path.abspath(__file__))
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)

    if hasattr(sys, '_MEIPASS'):
        plugin_dir = os.path.join(sys._MEIPASS, "engine", "plugins")
    else:
        plugin_dir = os.path.join(engine_dir, "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    for file in glob.glob(os.path.join(plugin_dir, "*.py")):
        if os.path.basename(file) == "__init__.py": continue
        module_name = f"plugins.{os.path.basename(file)[:-3]}"
        spec = importlib.util.spec_from_file_location(module_name, file)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            print(f"[Plugins] Loaded: {module_name}")
        except Exception as e:
            print(f"[Plugins] Failed to load {module_name}: {e}")


from registry import vision_node, NodeProcessor

class _PassThrough(dict):
    """Returns the single pass-through value for any key — supports dynamic fan-out outputs."""
    def __init__(self, val):
        self._val = val
        super().__init__({'out': val, 'main': val, 'image': val, 'data': val})
    def get(self, key, default=None): return self._val
    def __getitem__(self, key): return self._val
    def __contains__(self, key): return True

@vision_node(
    type_id="canvas_reroute",
    label="Reroute",
    category="canvas",
    icon="GitCommit",
    description="Pass-through node to organize wires.",
    inputs=[{"id": "in", "color": "any"}],
    outputs=[{"id": "out", "color": "any"}],
    dynamic_inputs=True,
    dynamic_outputs=True
)
class RerouteNode(NodeProcessor):
    def process(self, inputs, params):
        return _PassThrough(inputs.get('in'))

# --- CORE ENGINE ---
def _is_serializable(v):
    """Reject numpy arrays, rasterio Affine, and any container holding them."""
    if isinstance(v, (str, int, float, bool, type(None))):
        return True
    if isinstance(v, np.ndarray):
        return False
    if isinstance(v, dict):
        return all(_is_serializable(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return all(_is_serializable(x) for x in v)
    return False  # Affine, bytes, unknown objects — skip

def flatten_groups(node_list, edge_list, prefix=''):
    """Recursively expand group_node types into flat nodes+edges."""
    flat_nodes = []
    flat_edges = []
    group_ids = {n['id'] for n in node_list if n.get('type') == 'group_node'}
    non_group_ids = {n['id'] for n in node_list if n.get('type') != 'group_node'}

    for node in node_list:
        if node.get('type') != 'group_node':
            flat_nodes.append({**node, 'id': prefix + node['id']})

    for e in edge_list:
        src, tgt = e.get('source', ''), e.get('target', '')
        if src in non_group_ids and tgt in non_group_ids:
            flat_edges.append({**e, 'source': prefix + src, 'target': prefix + tgt})

    for node in node_list:
        if node.get('type') != 'group_node':
            continue
        g_id = node['id']
        gprefix = prefix + g_id + '::'
        sub = node.get('data', {}).get('subGraph', {})
        sub_nodes = sub.get('nodes', [])
        sub_edges = sub.get('edges', [])

        gin = next((n for n in sub_nodes if n.get('type') == 'group_input'), None)
        gout = next((n for n in sub_nodes if n.get('type') == 'group_output'), None)
        gin_id = gin['id'] if gin else None
        gout_id = gout['id'] if gout else None

        inner_nodes = [n for n in sub_nodes if n.get('type') not in ('group_input', 'group_output')]
        inner_edges = [e for e in sub_edges
                       if e.get('source') not in (gin_id, gout_id)
                       and e.get('target') not in (gin_id, gout_id)]

        sub_flat_nodes, sub_flat_edges = flatten_groups(inner_nodes, inner_edges, prefix=gprefix)
        flat_nodes.extend(sub_flat_nodes)
        flat_edges.extend(sub_flat_edges)

        for outer_e in edge_list:
            if outer_e.get('target') != g_id or not gin_id:
                continue
            # Skip: source is also a group — handled by that group's output expansion
            if outer_e.get('source') in group_ids:
                continue
            th = outer_e.get('targetHandle', '')
            for inner_e in sub_edges:
                if inner_e.get('source') != gin_id or inner_e.get('sourceHandle', '') != th:
                    continue
                flat_edges.append({
                    'id': f"f_{outer_e.get('id','')}_{inner_e.get('id','')}",
                    'source': prefix + outer_e['source'],
                    'sourceHandle': outer_e.get('sourceHandle', ''),
                    'target': gprefix + inner_e['target'],
                    'targetHandle': inner_e.get('targetHandle', ''),
                })

        for outer_e in edge_list:
            if outer_e.get('source') != g_id or not gout_id:
                continue
            sh = outer_e.get('sourceHandle', '')
            for inner_e in sub_edges:
                if inner_e.get('target') != gout_id or inner_e.get('targetHandle', '') != sh:
                    continue
                tgt_id = outer_e['target']
                tgt_handle = outer_e.get('targetHandle', '')
                tgt_prefix = prefix
                # If target is also a group, resolve through its gin to get a flat target
                if tgt_id in group_ids:
                    tgt_node = next((n for n in node_list if n['id'] == tgt_id), None)
                    if tgt_node:
                        tgt_sub = tgt_node.get('data', {}).get('subGraph', {})
                        tgt_gin = next((n for n in tgt_sub.get('nodes', []) if n.get('type') == 'group_input'), None)
                        if tgt_gin:
                            for tgt_ie in tgt_sub.get('edges', []):
                                if tgt_ie.get('source') == tgt_gin['id'] and tgt_ie.get('sourceHandle', '') == tgt_handle:
                                    tgt_prefix = prefix + tgt_id + '::'
                                    tgt_id = tgt_ie['target']
                                    tgt_handle = tgt_ie.get('targetHandle', '')
                                    break
                flat_edges.append({
                    'id': f"f_{inner_e.get('id','')}_{outer_e.get('id','')}",
                    'source': gprefix + inner_e['source'],
                    'sourceHandle': inner_e.get('sourceHandle', ''),
                    'target': tgt_prefix + tgt_id,
                    'targetHandle': tgt_handle,
                })

    return flat_nodes, flat_edges


REALTIME_NODE_TYPES = {
    'input_webcam', 'input_movie', 'plugin_audio_input',
    'signal_generator', 'signal_clock', 'serial_reader',
    'plotter_pro', 'sci_plotter', 'analysis_monitor', 'util_inspector',
    'logic_collect',
}


class VisionEngine:
    def __init__(self):
        self.current_cap_index = 0
        self.cap = None
        self.has_webcam_node = False
        self.has_realtime_node = False
        self.graph = {"nodes": [], "edges": []}
        self.sorted_nodes = []
        self.connected_clients = set()
        self.node_instances = {}
        self._node_cache = {}  # {nid: {'params': str, 'output': dict}}
        self.registry = {}
        self.registry.update(NODE_CLASS_REGISTRY)
        self.pending_capture = None
        self.pending_snapshot = None
        self.preview_node_id = None

        self.fallback_img = None
        img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img", "fallback.jpg")
        if os.path.exists(img_path):
            self.fallback_img = cv2.imread(img_path)

        self._run_event = asyncio.Event()  # set only when a live source is active

    def switch_camera(self, idx):
        target_idx = str(idx)
        current_idx = str(getattr(self, 'current_cap_index', -1))
        
        # If we are already on this index, don't try again (even if it's closed/failed)
        if current_idx == target_idx and self.cap is not None:
            return
            
        print(f"[Engine] Camera Switch Request: {current_idx} -> {target_idx}")
        
        if self.cap: 
            self.cap.release()
            self.cap = None
            
        # Try primary backend
        print(f"[Engine] Attempting to open cam {target_idx} (CAP_ANY)...")
        cap = cv2.VideoCapture(int(idx), CAP_BACKEND)
        
        if not cap.isOpened():
            print(f"[Engine] Fallback to CAP_V4L2 for cam {target_idx}...")
            cap = cv2.VideoCapture(int(idx), cv2.CAP_V4L2)
            
        self.cap = cap
        self.current_cap_index = int(idx)
        print(f"[Engine] Camera {target_idx} opened: {self.cap.isOpened()}")
        
        if not self.cap.isOpened():
            print(f"[Engine] CRITICAL: Camera {target_idx} failed to open. Stopping retry loop.")

    def _should_run(self):
        return len(self.sorted_nodes) > 0

    def update_graph(self, g):
        raw_edges = [e for e in g.get('edges', []) if e.get('source') and e.get('target')]
        flat_nodes, flat_edges = flatten_groups(g.get('nodes', []), raw_edges)
        self.graph = {'nodes': flat_nodes, 'edges': flat_edges}
        nodes_dict = {n['id']: n for n in flat_nodes}
        s_ids = topological_sort(flat_nodes, flat_edges)
        self.sorted_nodes = [nodes_dict[nid] for nid in s_ids if nid in nodes_dict]
        active_nids = set(nodes_dict.keys())
        self.node_instances = {nid: inst for nid, inst in self.node_instances.items() if nid in active_nids}
        self._node_cache = {}
        node_types = {n.get('type') for n in flat_nodes}
        needs_camera = 'input_webcam' in node_types
        if needs_camera and (self.cap is None or not self.cap.isOpened()):
            self.cap = cv2.VideoCapture(self.current_cap_index, CAP_BACKEND)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.current_cap_index, cv2.CAP_V4L2)
            print(f"[Engine] Camera {self.current_cap_index} opened (webcam node added)")
        elif not needs_camera and self.cap is not None:
            self.cap.release()
            self.cap = None
            print("[Engine] Camera released (no webcam node in graph)")
        self.has_webcam_node = needs_camera
        self.has_realtime_node = bool(node_types & REALTIME_NODE_TYPES)
        if self._should_run():
            self._run_event.set()
        else:
            self._run_event.clear()

    async def _drain_notifs_loop(self):
        """Background task: flush notification queue to clients every 50 ms."""
        while True:
            await asyncio.sleep(0.05)
            while not _notification_queue.empty():
                try:
                    notif = _notification_queue.get_nowait()
                    notif_msg = json.dumps({"type": "notification", **notif})
                    if self.connected_clients:
                        await asyncio.gather(*[c.send(notif_msg) for c in list(self.connected_clients)], return_exceptions=True)
                except Exception as e:
                    print(f"[Engine] Notification drain error: {e}")

    async def run(self):
        while True:
            if not self._run_event.is_set():
                await self._run_event.wait()
                continue
            frame = None
            if self.cap is not None and self.has_webcam_node:
                ret, frame = self.cap.read()
                if not ret:
                    frame = None
                    await asyncio.sleep(0.05)
            results, node_datas, final_img, commands = {}, {}, None, []
            locked_out_nids = {n['id'] for n in self.sorted_nodes if n.get('data', {}).get('lockedOut', False)}
            bypassed_nids = {n['id'] for n in self.sorted_nodes if n.get('data', {}).get('bypassed', False)}
            schema_by_type = {s['type']: s for s in NODE_SCHEMAS}
            for node in self.sorted_nodes:
                nid, ntype = node['id'], node['type']
                inputs = {"raw_frame": frame}
                for e in self.graph.get('edges', []):
                    if e['source'] in locked_out_nids:
                        continue
                    if e['target'] == nid and e['source'] in results:
                        source_res = results[e['source']]
                        sh_raw = e.get('sourceHandle', 'main')
                        th_raw = e.get('targetHandle', '')
                        sh = sh_raw.split('__')[-1].lower()
                        th = th_raw.split('__')[-1].lower()
                        
                        # Try to get value from source results (case-insensitive keys)
                        val = source_res.get(sh) if hasattr(source_res, 'get') else None
                        if val is None:
                            source_res_lower = {k.lower(): v for k, v in source_res.items()}
                            val = source_res_lower.get(sh)
                        
                        if val is None and sh == 'main':
                            # Fallback: if 'main' requested but not found, take the first available output
                            if source_res:
                                val = next(iter(source_res.values()))

                        if val is not None:
                            if th:
                                inputs[th] = val
                                # Compatibility shims for common names
                                if th in ['image', 'main'] and isinstance(val, np.ndarray):
                                    inputs['image'] = val
                                elif th == 'image':
                                    inputs.pop('image', None)
                                if th in ['data', 'in', 'value']:
                                    inputs['data'] = val
                                    inputs['in'] = val
                                    inputs['value'] = val
                            else:
                                # Default handle behavior
                                if isinstance(val, np.ndarray): inputs['image'] = val
                                else: inputs['data'] = val
                # Bypass: pass matching-type inputs directly to outputs
                if nid in bypassed_nids:
                    schema = schema_by_type.get(ntype, {})
                    bypass_result = {}
                    for out_spec in schema.get('outputs', []):
                        out_color, out_id = out_spec.get('color'), out_spec.get('id')
                        for in_spec in schema.get('inputs', []):
                            in_color = in_spec.get('color')
                            # 'any' matches everything
                            if in_color == out_color or in_color == 'any' or out_color == 'any':
                                val = inputs.get(in_spec.get('id'))
                                if val is not None:
                                    bypass_result[out_id] = val
                                break
                    results[nid] = bypass_result
                    continue

                # Get or create instance for this specific node
                if nid not in self.node_instances:
                    cls = self.registry.get(ntype)
                    if cls:
                        # Handle special cases if needed, or pass engine reference
                        try:
                            # Try passing self (engine) in case it's needed
                            self.node_instances[nid] = cls(self)
                        except TypeError:
                            # Fallback to no-args init
                            self.node_instances[nid] = cls()
                
                proc = self.node_instances.get(nid)
                if proc:
                    try:
                        params = node.get('data', {}).get('params', {})
                        has_array_input = any(isinstance(v, np.ndarray) for v in inputs.values())
                        is_cacheable = ntype not in REALTIME_NODE_TYPES and not has_array_input
                        cache = self._node_cache.get(nid)
                        params_sig = str(sorted(params.items()))
                        # Include non-array inputs in cache key so scalar-driven nodes invalidate correctly
                        scalar_inputs_sig = str({k: v for k, v in inputs.items() if not isinstance(v, np.ndarray) and k != 'raw_frame'})
                        cache_sig = params_sig + scalar_inputs_sig
                        if is_cacheable and cache and cache['sig'] == cache_sig:
                            out = cache['output']
                        else:
                            out = await asyncio.to_thread(proc.process, inputs, params)
                            if is_cacheable:
                                self._node_cache[nid] = {'sig': cache_sig, 'output': out}
                        results[nid] = out
                        
                        # Handle On-Demand Capture
                        if self.pending_capture and (nid == self.pending_capture or nid.endswith('::' + self.pending_capture)) and out.get('main') is not None:
                            try:
                                capture_img = out['main']
                                if len(capture_img.shape) == 2: capture_img = cv2.cvtColor(capture_img, cv2.COLOR_GRAY2BGR)
                                _, c_buf = cv2.imencode('.png', capture_img)
                                c_b64 = base64.b64encode(c_buf).decode('utf-8')
                                async def send_capture(b):
                                    msg = json.dumps({"type": "node_capture", "node_id": nid, "image": b})
                                    if self.connected_clients: await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)], return_exceptions=True)
                                asyncio.create_task(send_capture(c_b64))
                                self.pending_capture = None # Reset
                            except Exception as ce: print(f"Capture Error: {ce}")

                        # Handle Snapshot-to-Node
                        if self.pending_snapshot and (nid == self.pending_snapshot or nid.endswith('::' + self.pending_snapshot)) and out.get('main') is not None:
                            try:
                                snap_img = out['main'].copy()
                                if snap_img.ndim == 2: snap_img = cv2.cvtColor(snap_img, cv2.COLOR_GRAY2BGR)
                                elif snap_img.ndim == 3 and snap_img.shape[2] == 4: snap_img = cv2.cvtColor(snap_img, cv2.COLOR_BGRA2BGR)
                                engine_dir = os.path.dirname(os.path.abspath(__file__))
                                project_root = os.path.dirname(engine_dir)
                                snap_dir = os.path.join(project_root, "public", "snapshots")
                                if not os.path.exists(snap_dir): os.makedirs(snap_dir, exist_ok=True)
                                ts = int(time.time() * 1000)
                                fname = f"snap_{ts}.png"
                                snap_path = os.path.join(snap_dir, fname)
                                res = cv2.imwrite(snap_path, snap_img)
                                print(f"[Snapshot] imwrite -> {res}  path={snap_path}")
                                if res:
                                    commands.append({"type": "add_node", "node_type": "input_image", "params": {"path": snap_path}})
                                    send_notification(f"Snapshot capturé : {fname}", level='info')
                                else:
                                    send_notification("Erreur écriture snapshot", level='error')
                                self.pending_snapshot = None
                            except Exception as se:
                                print(f"Snapshot Error: {se}")
                                self.pending_snapshot = None

                        for k, v in out.items():
                            if k == "_command" and v:
                                cmd = dict(v)
                                if cmd.get('node_id') == '__self__': cmd['node_id'] = nid
                                commands.append(cmd)
                            elif k != "main" and not isinstance(v, np.ndarray) and _is_serializable(v):
                                node_datas[f"{nid}:{k}"] = v
                        if self.preview_node_id and (nid == self.preview_node_id or nid.endswith('::' + self.preview_node_id)):
                            preview_img = out.get('main')
                            if preview_img is None:
                                for _v in out.values():
                                    if isinstance(_v, np.ndarray) and len(_v.shape) >= 2:
                                        preview_img = _v; break
                            if preview_img is not None: final_img = preview_img
                        elif not self.preview_node_id and ntype == 'output_display' and out.get('main') is not None:
                            final_img = out['main']
                    except Exception as e: print(f"Error {nid}: {e}")
            if final_img is None:
                final_img = getattr(self, 'fallback_img', None)
                if final_img is None:
                    final_img = np.zeros((480, 640, 3), dtype=np.uint8)
            if final_img is not None and self.connected_clients:
                try:
                    if len(final_img.shape) == 2: final_img = cv2.cvtColor(final_img, cv2.COLOR_GRAY2BGR)
                    elif len(final_img.shape) == 3 and final_img.shape[2] == 2:
                        hsv = np.zeros((final_img.shape[0], final_img.shape[1], 3), dtype=np.uint8); hsv[..., 1] = 255
                        mag, ang = cv2.cartToPolar(final_img[..., 0], final_img[..., 1])
                        hsv[..., 0], hsv[..., 2] = ang * 180 / np.pi / 2, cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
                        final_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                    _, buf = cv2.imencode('.jpg', final_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    msg = json.dumps({
                        "type": "update", 
                        "image": base64.b64encode(buf).decode('utf-8'), 
                        "nodes_data": node_datas,
                        "commands": commands
                    })
                    if self.connected_clients: await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)], return_exceptions=True)
                except Exception as e: print(f"Encoding Error: {e}")

            await asyncio.sleep(1/30 if self.has_realtime_node else 0.5)

    async def hdl(self, ws):
        self.connected_clients.add(ws)
        if NODE_SCHEMAS:
            try:
                await ws.send(json.dumps({"type": "schema", "nodes": NODE_SCHEMAS}))
            except Exception as e:
                print(f"[Engine] Failed to send schema: {e}")
        try:
            async for m in ws:
                try:
                    d = json.loads(m)
                    if d.get('type') == 'update_graph':
                        self.update_graph(d.get('graph', {}))
                    elif d.get('type') == 'request_node_capture':
                        self.pending_capture = d.get('node_id')
                    elif d.get('type') == 'snapshot_to_node':
                        self.pending_snapshot = d.get('node_id')
                        print(f"[Engine] pending_snapshot set to {self.pending_snapshot}")
                    elif d.get('type') == 'set_preview_node':
                        self.preview_node_id = d.get('node_id')
                    elif d.get('type') == 'export_py':
                        try:
                            from code_generator import generate_pipeline_script
                            code = generate_pipeline_script(
                                d.get('nodes', []),
                                d.get('edges', []),
                                d.get('export_node_id', ''),
                            )
                            await ws.send(json.dumps({'type': 'export_py_code', 'code': code}))
                        except Exception as gen_err:
                            await ws.send(json.dumps({'type': 'export_py_code', 'error': str(gen_err)}))
                except Exception as e:
                    print(f"[Engine] Message handler error: {e}")
        except Exception as e:
            print(f"[Engine] WebSocket closed: {e}")
        finally:
            self.connected_clients.remove(ws)

load_plugins()

async def main(engine_instance):
    try:
        # Increase timeouts and disable pings to be more resilient during heavy CPU/Network load (SAM Large)
        async with websockets.serve(
            engine_instance.hdl, "localhost", 8765,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=60,
            max_size=2**24 # 16MB max message size for large graphs/images
        ):
            await asyncio.gather(
                engine_instance.run(),
                engine_instance._drain_notifs_loop(),
            )
    except Exception as e:
        print(f"Server Error: {e}")

def free_port(port):
    import signal
    try:
        result = subprocess.run(['ss', '-tlnp', f'sport = :{port}'],
                                capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'pid=' in line:
                pid = int(line.split('pid=')[1].split(',')[0])
                if pid != os.getpid():
                    os.kill(pid, signal.SIGKILL)
        time.sleep(0.3)
    except Exception:
        pass

if __name__ == "__main__":
    print("[Engine] Starting OpenCV Sidecar...")
    free_port(8765)
    cameras = list_available_cameras()
    print(f"[Engine] Available cameras: {cameras}")

    engine = VisionEngine()
    try:
        asyncio.run(main(engine))
    except KeyboardInterrupt:
        print("\n[Engine] Stopped.")
