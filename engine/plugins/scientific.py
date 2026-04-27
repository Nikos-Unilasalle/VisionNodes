import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="sci_plotter",
    label="Plotter",
    category="visualize",
    icon="Activity",
    description="Multi-series real-time graph. Connect up to 5 scalar or list inputs (v0–v4). Resizable.",
    inputs=[
        {"id": "v0", "color": "any"},
        {"id": "v1", "color": "any"},
        {"id": "v2", "color": "any"},
        {"id": "v3", "color": "any"},
        {"id": "v4", "color": "any"},
    ],
    outputs=[
        {"id": "v0", "color": "any"},
        {"id": "v1", "color": "any"},
        {"id": "v2", "color": "any"},
        {"id": "v3", "color": "any"},
        {"id": "v4", "color": "any"},
    ],
    params=[
        {"id": "buffer_size", "label": "History Size", "type": "scalar", "min": 10, "max": 500, "default": 100},
        {"id": "min_y", "label": "Y-Axis Min", "type": "float", "min": -1000, "max": 1000, "default": 0},
        {"id": "max_y", "label": "Y-Axis Max", "type": "float", "min": -1000, "max": 1000, "default": 1},
    ]
)
class PlotterNode(NodeProcessor):
    def process(self, inputs, params):
        out = {}
        for k in ('v0', 'v1', 'v2', 'v3', 'v4'):
            v = inputs.get(k)
            if v is not None:
                out[k] = v
        return out

@vision_node(
    type_id="sci_stats",
    label="Statistics",
    category="analysis",
    icon="Info",
    description="Calculates key statistical metrics (mean, median, standard deviation) from a list.",
    inputs=[{"id": "data_list", "color": "list"}],
    outputs=[
        {"id": "mean", "color": "scalar"},
        {"id": "median", "color": "scalar"},
        {"id": "std", "color": "scalar"},
        {"id": "min", "color": "scalar"},
        {"id": "max", "color": "scalar"}
    ]
)
class StatsNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data_list')
        if not data or not isinstance(data, list):
            return {"mean": 0, "median": 0, "std": 0, "min": 0, "max": 0}
        
        # Flatten if it's a list of dicts (like area)
        nums = []
        for item in data:
            if isinstance(item, (int, float)): nums.append(item)
            elif isinstance(item, dict) and 'area' in item: nums.append(item['area'])
            elif isinstance(item, dict) and 'scalar' in item: nums.append(item['scalar'])
            
        if not nums: return {"mean": 0, "median": 0, "std": 0, "min": 0, "max": 0}
        
        arr = np.array(nums)
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr))
        }

@vision_node(
    type_id="sci_heatmap",
    label="Heatmap",
    category="analysis",
    icon="Wind",
    description="Generates a cumulative heatmap based on provided detection points.",
    inputs=[{"id": "image", "color": "image"}, {"id": "points", "color": "any"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "res", "label": "Resolution", "type": "scalar", "min": 16, "max": 256, "default": 64},
        {"id": "decay", "label": "Decay (Fade)", "type": "scalar", "min": 0, "max": 0.1, "step": 0.001, "default": 0.01},
        {"id": "intensity", "label": "Intensity", "type": "scalar", "min": 0.1, "max": 5.0, "default": 1.0},
        {"id": "blur", "label": "Blur Radius", "type": "scalar", "min": 0, "max": 21, "step": 2, "default": 5},
        {"id": "colormap", "label": "Colormap", "type": "enum", "options": ["Jet", "Hot", "Magma", "Viridis", "Ocean"], "default": 0},
        {"id": "blend", "label": "Alpha Blend", "type": "scalar", "min": 0, "max": 1.0, "step": 0.1, "default": 0.7},
        {"id": "reset", "label": "Reset Buffer", "type": "trigger", "default": 0}
    ]
)
class HeatmapNode(NodeProcessor):
    def __init__(self):
        self.buffer = None
        self.res = 0

    def process(self, inputs, params):
        img = inputs.get('image')
        points = inputs.get('points')
        
        res = int(params.get('res', 64))
        decay = float(params.get('decay', 0.01))
        intensity = float(params.get('intensity', 1.0))
        reset = int(params.get('reset', 0))

        
        # Init or Reset buffer
        if self.buffer is None or self.res != res or reset == 1:
            self.buffer = np.zeros((res, res), dtype=np.float32)
            self.res = res
            
        # If reset is not active, we update the buffer
        # 1. Decay previous heat
        if decay > 0:
            self.buffer *= (1.0 - decay)
            
        # 2. Add new data (Points or Optical Flow)
        if points is not None:
            # Case A: Optical Flow or Dense Map (numpy array)
            if isinstance(points, np.ndarray):
                try:
                    # If flow has 2 channels (u,v), calculate magnitude
                    if len(points.shape) == 3 and points.shape[2] == 2:
                        mag, _ = cv2.cartToPolar(points[..., 0], points[..., 1])
                        # Resize magnitude map to buffer resolution
                        data_heat = cv2.resize(mag, (res, res))
                        self.buffer += data_heat * (intensity * 0.1) # Scale down flow intensity slightly
                    # If it's a single channel intensity map
                    elif len(points.shape) == 2 or (len(points.shape) == 3 and points.shape[2] == 1):
                        data_heat = cv2.resize(points, (res, res))
                        if data_heat.dtype != np.float32: data_heat = data_heat.astype(np.float32) / 255.0
                        self.buffer += data_heat * intensity
                except Exception as e:
                    print(f"[Heatmap) Flow Error: {e}")
            
            # Case B: List of Points (Detections)
            elif isinstance(points, list) or isinstance(points, dict):
                pts_list = points if isinstance(points, list) else [points]
                for p in pts_list:
                    x, y = 0, 0
                    if isinstance(p, dict):
                        if 'center' in p: 
                            x, y = p['center'].get('x', 0), p['center'].get('y', 0)
                        elif 'x' in p and 'y' in p:
                            x, y = p['x'], p['y']
                        elif 'xmin' in p: # box
                            x, y = p['xmin'] + p.get('width', 0.0)/2, p['ymin'] + p.get('height', 0.0)/2
                    
                    ix, iy = int(x * res), int(y * res)
                    if 0 <= ix < res and 0 <= iy < res:
                        self.buffer[iy, ix] += intensity

        # 3. Process buffer for display
        # Normalize for visualization
        display_buf = self.buffer.copy()
        max_val = np.max(display_buf)
        if max_val > 0: display_buf /= max_val
        
        # Upscale and colormap
        vis = (display_buf * 255).astype(np.uint8)
        
        # Small blur for smoothness
        blur_r = int(params.get('blur', 5))
        if blur_r > 0:
            if blur_r % 2 == 0: blur_r += 1
            vis = cv2.GaussianBlur(vis, (blur_r, blur_r), 0)
            
        # Apply colormap
        maps = [cv2.COLORMAP_JET, cv2.COLORMAP_HOT, cv2.COLORMAP_MAGMA, cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_OCEAN]
        color_map = maps[int(params.get('colormap', 0))]
        heatmap_img = cv2.applyColorMap(vis, color_map)
        
        if img is None: return {"main": heatmap_img}
        
        # 4. Blend with original
        h, w = img.shape[:2]
        heatmap_resized = cv2.resize(heatmap_img, (w, h))
        blend_alpha = float(params.get('blend', 0.7))
        
        # Ensure background is BGR (handles Grayscale inputs to avoid OpenCV Errors)
        background = img.copy()
        if len(background.shape) == 2 or (len(background.shape) == 3 and background.shape[2] == 1):
            background = cv2.cvtColor(background, cv2.COLOR_GRAY2BGR)
            
        out = cv2.addWeighted(background, 1.0 - blend_alpha, heatmap_resized, blend_alpha, 0)
        return {"main": out}
