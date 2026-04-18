import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="sci_plotter",
    label="Plotter",
    category="analysis",
    icon="Activity",
    description="Real-time graph visualizer for tracking numerical data changes over time.",
    inputs=[{"id": "value", "color": "scalar"}],
    outputs=[{"id": "value", "color": "scalar"}],
    params=[
        {"id": "buffer_size", "label": "History Size", "type": "scalar", "min": 10, "max": 500, "default": 100},
        {"id": "min_y", "label": "Y-Axis Min", "type": "scalar", "min": -1000, "max": 1000, "default": 0},
        {"id": "max_y", "label": "Y-Axis Max", "type": "scalar", "min": -1000, "max": 1000, "default": 1}
    ]
)
class PlotterNode(NodeProcessor):
    def process(self, inputs, params):
        val = inputs.get('value', 0.0)
        return {"value": val, "display_text": f"Tracking: {val:.4f}"}

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
        {"id": "reset", "label": "Reset Buffer", "type": "scalar", "min": 0, "max": 1, "step": 1, "default": 0}
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
            
        # 1. Decay previous heat
        if decay > 0:
            self.buffer *= (1.0 - decay)
            
        # 2. Add new points
        if points:
            if not isinstance(points, list): points = [points]
            for p in points:
                x, y = 0, 0
                if isinstance(p, dict):
                    # Try center first, then x/y
                    if 'center' in p: 
                        x, y = p['center'].get('x', 0), p['center'].get('y', 0)
                    elif 'x' in p and 'y' in p:
                        x, y = p['x'], p['y']
                    elif 'xmin' in p: # box
                        x, y = p['xmin'] + p.get('width', 0)/2, p['ymin'] + p.get('height', 0)/2
                
                # Plot onto buffer grid
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
        
        # Create a weight mask from the buffer to only blend where there is "heat"
        # Or just global blend
        out = cv2.addWeighted(img, 1.0 - blend_alpha, heatmap_resized, blend_alpha, 0)
        return {"main": out}
