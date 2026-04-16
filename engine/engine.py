import asyncio
import json
import cv2
import base64
import numpy as np
import websockets
import time
import os
import urllib.request
from collections import deque
from abc import ABC, abstractmethod

# --- AI Setup (MediaPipe) ---
MODEL_PATH = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

def download_model():
    if not os.path.exists(MODEL_PATH):
        try: urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        except: pass

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    download_model()
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    detector_options = vision.FaceLandmarkerOptions(base_options=base_options, num_faces=10)
    detector = vision.FaceLandmarker.create_from_options(detector_options)
    AI_AVAILABLE = True
except Exception as e:
    AI_AVAILABLE = False
    print(f"AI Error: {e}")

# --- Plugin System ---
NODE_SCHEMAS = []
NODE_CLASS_REGISTRY = {}

def vision_node(type_id, label, category="custom", icon="PenTool", inputs=None, outputs=None, params=None):
    def decorator(cls):
        NODE_SCHEMAS.append({
            "type": type_id,
            "label": label,
            "category": category,
            "icon": icon,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "params": params or []
        })
        NODE_CLASS_REGISTRY[type_id] = cls()
        return cls
    return decorator

def load_plugins():
    import importlib.util
    import glob
    plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
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

# --- Base ---
class NodeProcessor(ABC):
    @abstractmethod
    def process(self, inputs, params): pass

# --- INPUT UNITS ---
class WebcamInput(NodeProcessor):
    def __init__(self, engine): self.engine = engine
    def process(self, inputs, params):
        idx = int(params.get('device_index', 0))
        if self.engine.current_cap_index != idx: self.engine.switch_camera(idx)
        return {"main": inputs.get('raw_frame')}

class SolidColorNode(NodeProcessor):
    def process(self, inputs, params):
        r = int(params.get('r', 255))
        g = int(params.get('g', 0))
        b = int(params.get('b', 0))
        w = int(params.get('width', 640))
        h = int(params.get('height', 480))
        # OpenCV utilise le format BGR
        img = np.full((h, w, 3), (b, g, r), dtype=np.uint8)
        return {"main": img}

# --- FILTER UNITS ---
class CannyFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return {"main": cv2.Canny(gray, int(params.get('low', 100)), int(params.get('high', 200)))}

class BlurFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        s = int(params.get('size', 5))
        if s % 2 == 0: s += 1
        return {"main": cv2.GaussianBlur(img, (s, s), 0)}

class GrayFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        res = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return {"main": res}

class ThresholdFilter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None, "mask": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, res = cv2.threshold(gray, int(params.get('threshold', 127)), 255, cv2.THRESH_BINARY)
        return {"main": res, "mask": res}

# --- GEOMETRIC UNITS ---
class FlipNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        return {"main": cv2.flip(img, int(params.get('flip_mode', 1)))}

class ResizeNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        sc = float(params.get('scale', 1.0))
        return {"main": cv2.resize(img, None, fx=sc, fy=sc)}

# --- ANALYSIS UNITS ---
class OpticalFlowNode(NodeProcessor):
    def __init__(self): self.prev = None
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"main": None}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        flow = None
        if self.prev is not None and self.prev.shape == gray.shape:
            flow = cv2.calcOpticalFlowFarneback(
                self.prev, gray, None, 
                float(params.get('pyr_scale', 0.5)), int(params.get('levels', 3)), 
                int(params.get('winsize', 15)), int(params.get('iterations', 3)), 
                int(params.get('poly_n', 5)), float(params.get('poly_sigma', 1.2)), 0
            )
        self.prev = gray
        return {"main": img, "data": flow}

class FlowVizNode(NodeProcessor):
    def process(self, inputs, params):
        flow = inputs.get('data')
        if flow is None: return {"main": None}
        h, w = flow.shape[:2]
        hsv = np.zeros((h, w, 3), dtype=np.uint8)
        hsv[..., 1] = 255
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv[..., 0] = ang * 180 / np.pi / 2
        hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        return {"main": cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)}

class ZoneMeanNode(NodeProcessor):
    def process(self, inputs, params):
        flow = inputs.get('data')
        val = 0.0
        if flow is not None:
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            val = float(np.mean(mag))
        return {"main": inputs.get('image'), "scalar": val}

class FaceDetectionNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        import os, urllib.request
        model_path = "blaze_face_short_range.tflite"
        if not os.path.exists(model_path):
            try: urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite", model_path)
            except: pass
            
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.FaceDetectorOptions(base_options=base_options)
        self.detector = vision.FaceDetector.create_from_options(self.options)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"main": None, "faces_list": []}
        import mediapipe as mp
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        detection_result = self.detector.detect(mp_image)
        faces = []
        h, w = image.shape[:2]
        if getattr(detection_result, 'detections', None):
            for detection in detection_result.detections:
                bbox = detection.bounding_box
                faces.append({
                    "xmin": max(0, bbox.origin_x / w),
                    "ymin": max(0, bbox.origin_y / h),
                    "width": min(1.0, bbox.width / w),
                    "height": min(1.0, bbox.height / h)
                })
                
        out = {"faces_list": faces, "main": image}
        for i, face in enumerate(faces):
            out[f"face_{i}"] = face
        return out

class HandDetectionNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        import os, urllib.request
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            try: urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task", model_path)
            except: pass
            
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        base_options = python.BaseOptions(model_asset_path=model_path)
        self.options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
        self.detector = vision.HandLandmarker.create_from_options(self.options)

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"hands_list": [], "main": None}
        import mediapipe as mp
        
        max_hands = params.get('max_hands', 2)
        if hasattr(self.options, 'num_hands') and self.options.num_hands != max_hands:
            self.options.num_hands = int(max_hands)
            from mediapipe.tasks.python import vision
            self.detector = vision.HandLandmarker.create_from_options(self.options)
            
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        results = self.detector.detect(mp_image)
        
        hands_list = []
        if getattr(results, 'hand_landmarks', None):
            for hand_landmarks in results.hand_landmarks:
                x_min = min([lm.x for lm in hand_landmarks])
                y_min = min([lm.y for lm in hand_landmarks])
                x_max = max([lm.x for lm in hand_landmarks])
                y_max = max([lm.y for lm in hand_landmarks])
                hands_list.append({"xmin": max(0, x_min), "ymin": max(0, y_min), "width": min(1-x_min, x_max - x_min), "height": min(1-y_min, y_max - y_min)})
        
        out = {"hands_list": hands_list, "main": image}
        for i, hand in enumerate(hands_list):
            out[f"hand_{i}"] = hand
        return out

class ColorMaskNode(NodeProcessor):
    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None: return {"mask": None}
        
        # S'assurer que l'image est bien en couleur 3 canaux avant la conversion HSV
        if len(image.shape) == 2 or image.shape[2] == 1:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            
        h_min, s_min, v_min = params.get('h_min', 0), params.get('s_min', 0), params.get('v_min', 0)
        h_max, s_max, v_max = params.get('h_max', 179), params.get('s_max', 255), params.get('v_max', 255)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([h_min, s_min, v_min]), np.array([h_max, s_max, v_max]))
        return {"mask": mask}

class MorphologyNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask', inputs.get('image'))
        if mask is None: return {"mask": None}
        op = params.get('operation', 0)
        size = int(params.get('size', 5))
        kernel = np.ones((size, size), np.uint8)
        if op == 0: res = cv2.dilate(mask, kernel, iterations=1)
        else: res = cv2.erode(mask, kernel, iterations=1)
        return {"mask": res}

# --- UTILS & TERMINALS ---
class OverlayNode(NodeProcessor):
    def process(self, inputs, params):
        img, data = inputs.get('image'), inputs.get('data')
        if img is None: return {"main": None}
        res = img.copy()
        if len(res.shape) == 2: res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)
        h, w = res.shape[:2]
        thick = int(params.get('thickness', 2))
        r = int(params.get('r', 0))
        g = int(params.get('g', 255))
        b = int(params.get('b', 0))
        col = (b, g, r)
        
        if isinstance(data, dict) and 'xmin' in data:
            cv2.rectangle(res, (int(data['xmin']*w), int(data['ymin']*h)), (int((data['xmin']+data['width'])*w), int((data['ymin']+data['height'])*h)), col, thick)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'xmin' in item:
                    cv2.rectangle(res, (int(item['xmin']*w), int(item['ymin']*h)), (int((item['xmin']+item['width'])*w), int((item['ymin']+item['height'])*h)), col, thick)
        elif isinstance(data, (float, int)):
            cv2.putText(res, f"v: {data:.4f}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, col, thick)
        return {"main": res}

class ListSelectorNode(NodeProcessor):
    def process(self, inputs, params):
        d_list = inputs.get('data')
        if not isinstance(d_list, list): return {"item_out": None}
        idx = int(params.get('index', 0))
        if 0 <= idx < len(d_list): return {"item_out": d_list[idx]}
        return {"item_out": None}

class CoordSplitterNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('data')
        if not isinstance(d, dict): return {"x": None, "y": None, "w": None, "h": None}
        return {"x": d.get("xmin"), "y": d.get("ymin"), "w": d.get("width"), "h": d.get("height")}

class CoordCombineNode(NodeProcessor):
    def process(self, inputs, params):
        return {"dict_out": {
            "xmin": float(inputs.get("x", 0.0) or 0.0),
            "ymin": float(inputs.get("y", 0.0) or 0.0),
            "width": float(inputs.get("w", 0.0) or 0.0),
            "height": float(inputs.get("h", 0.0) or 0.0)
        }}

class CoordToMaskNode(NodeProcessor):
    def process(self, inputs, params):
        img_ref, data = inputs.get('image'), inputs.get('data')
        if img_ref is None:
            w, h = int(params.get('width', 640)), int(params.get('height', 480))
        else:
            h, w = img_ref.shape[:2]
        
        mask = np.zeros((h, w), dtype=np.uint8)
        
        if isinstance(data, dict) and 'xmin' in data:
            cv2.rectangle(mask, (int(data['xmin']*w), int(data['ymin']*h)), (int((data['xmin']+data['width'])*w), int((data['ymin']+data['height'])*h)), 255, -1)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'xmin' in item:
                    cv2.rectangle(mask, (int(item['xmin']*w), int(item['ymin']*h)), (int((item['xmin']+item['width'])*w), int((item['ymin']+item['height'])*h)), 255, -1)
        return {"mask": mask}

class MaskBlendNode(NodeProcessor):
    def process(self, inputs, params):
        img_a = inputs.get('image_a', inputs.get('image'))
        img_b = inputs.get('image_b')
        mask = inputs.get('mask')
        if img_a is None: return {"main": None}
        if img_b is None or mask is None: return {"main": img_a}
        
        if len(mask.shape) == 3: mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        mask = cv2.resize(mask, (img_a.shape[1], img_a.shape[0]))
        
        # S'assurer que le mask est 3D pour le broadcasting mathématique constant
        mask_expanded = np.expand_dims(mask, axis=2)
        mask_normalized = mask_expanded / 255.0
        
        # Homogénéiser les deux images en 3 canaux
        if len(img_a.shape) == 2 or img_a.shape[2] == 1:
            img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)
            
        img_b_resized = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        if len(img_b_resized.shape) == 2 or img_b_resized.shape[2] == 1:
            img_b_resized = cv2.cvtColor(img_b_resized, cv2.COLOR_GRAY2BGR)
        
        blended = (img_a * (1.0 - mask_normalized)) + (img_b_resized * mask_normalized)
        return {"main": blended.astype(np.uint8)}

class InspectorNode(NodeProcessor):
    def process(self, inputs, params):
        return {"main": inputs.get('image'), "data_out": inputs.get('data')}

class DisplayOutput(NodeProcessor):
    def process(self, inputs, params): return {"main": inputs.get('image')}

# --- CORE ENGINE ---
class VisionEngine:
    def __init__(self):
        self.current_cap_index = 0
        self.cap = cv2.VideoCapture(self.current_cap_index)
        self.graph = {"nodes": [], "edges": []}
        self.sorted_nodes = []
        self.connected_clients = set()
        self.registry = {
            'input_webcam': WebcamInput(self),
            'input_solid_color': SolidColorNode(),
            'filter_canny': CannyFilter(),
            'filter_blur': BlurFilter(),
            'filter_gray': GrayFilter(),
            'filter_threshold': ThresholdFilter(),
            'geom_flip': FlipNode(),
            'geom_resize': ResizeNode(),
            'analysis_flow': OpticalFlowNode(),
            'analysis_flow_viz': FlowVizNode(),
            'analysis_zone_mean': ZoneMeanNode(),
            'analysis_face_mp': FaceDetectionNode(),
            'analysis_hand_mp': HandDetectionNode(),
            'filter_color_mask': ColorMaskNode(),
            'filter_morphology': MorphologyNode(),
            'draw_overlay': OverlayNode(),
            'util_coord_to_mask': CoordToMaskNode(),
            'util_mask_blend': MaskBlendNode(),
            'data_list_selector': ListSelectorNode(),
            'data_coord_splitter': CoordSplitterNode(),
            'data_coord_combine': CoordCombineNode(),
            'data_inspector': InspectorNode(),
            'output_display': DisplayOutput()
        }
        self.registry.update(NODE_CLASS_REGISTRY)

    def switch_camera(self, idx):
        self.cap.release(); self.cap = cv2.VideoCapture(idx); self.current_cap_index = idx

    def update_graph(self, g):
        self.graph = g
        nodes = {n['id']: n for n in g.get('nodes', [])}
        adj = {nid: [] for nid in nodes}; degr = {nid: 0 for nid in nodes}
        for e in g.get('edges', []):
            if e['source'] in adj and e['target'] in adj:
                adj[e['source']].append(e['target']); degr[e['target']] += 1
        q = deque([nid for nid in nodes if degr[nid] == 0])
        s_ids = []
        while q:
            u = q.popleft(); s_ids.append(u)
            for v in adj[u]:
                degr[v] -= 1
                if degr[v] == 0: q.append(v)
        self.sorted_nodes = [nodes[nid] for nid in s_ids if nid in nodes]

    async def run(self):
        while True:
            ret, frame = self.cap.read()
            if not ret: await asyncio.sleep(0.1); continue
            results = {}; node_datas = {}; final_img = frame
            for node in self.sorted_nodes:
                nid, ntype = node['id'], node['type']
                inputs = {"raw_frame": frame}
                for e in self.graph.get('edges', []):
                    if e['target'] == nid and e['source'] in results:
                        source_res = results[e['source']]
                        sh = e.get('sourceHandle', 'main').split('__')[-1]
                        th = e.get('targetHandle', '').split('__')[-1]
                        val = source_res.get(sh)
                        if val is not None:
                            if th: inputs[th] = val
                            if isinstance(val, np.ndarray): inputs['image'] = val
                            else: inputs['data'] = val
                proc = self.registry.get(ntype)
                if proc:
                    try:
                        out = proc.process(inputs, node.get('data', {}).get('params', {}))
                        results[nid] = out
                        for k, v in out.items():
                            if k != "main" and not isinstance(v, np.ndarray):
                                node_datas[f"{nid}:{k}"] = v
                        if ntype == 'output_display' and out.get('main') is not None: final_img = out['main']
                    except Exception as e: print(f"Error {nid}: {e}")
            if final_img is not None:
                try:
                    if len(final_img.shape) == 2: 
                        final_img = cv2.cvtColor(final_img, cv2.COLOR_GRAY2BGR)
                    elif len(final_img.shape) == 3 and final_img.shape[2] == 2:
                        # Rendu de tolérance (Magie visuelle auto) au cas où un Tenseur brut est branché à l'écran !
                        hsv = np.zeros((final_img.shape[0], final_img.shape[1], 3), dtype=np.uint8)
                        hsv[..., 1] = 255
                        mag, ang = cv2.cartToPolar(final_img[..., 0], final_img[..., 1])
                        hsv[..., 0] = ang * 180 / np.pi / 2
                        hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
                        final_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                        
                    _, buf = cv2.imencode('.jpg', final_img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    msg = json.dumps({"type": "update", "image": base64.b64encode(buf).decode('utf-8'), "nodes_data": node_datas})
                    if self.connected_clients: await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)], return_exceptions=True)
                except Exception as e:
                    print(f"Engine Encoding Error: {e}")
            await asyncio.sleep(1/30)

    async def hdl(self, ws):
        self.connected_clients.add(ws)
        if NODE_SCHEMAS:
            try: await ws.send(json.dumps({"type": "schema", "nodes": NODE_SCHEMAS}))
            except: pass
        try:
            async for m in ws:
                d = json.loads(m)
                if d.get('type') == 'update_graph': self.update_graph(d.get('graph', {}))
        except: pass
        finally: self.connected_clients.remove(ws)

load_plugins()

engine = VisionEngine()
async def main():
    async with websockets.serve(engine.hdl, "localhost", 8765): await engine.run()
if __name__ == "__main__": asyncio.run(main())
