from registry import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='sci_histogram',
    label='Histogram Analysis',
    category=['visualize', 'analysis'],
    icon='BarChart2',
    description="Statistical distribution of pixel intensities. Performs radiometric analysis of input data across spectral channels for scientific validation.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'mode',      'label': 'Spectral Mode',       'type': 'enum', 'options': ['Overlay (RGB)', 'Monochrome (Luma)'], 'default': 0},
        {'id': 'bins',      'label': 'Quantization (Bins)', 'type': 'scalar', 'min': 16, 'max': 256, 'default': 256},
        {'id': 'log_scale', 'label': 'Logarithmic Scale',   'type': 'boolean', 'default': False},
        {'id': 'show_stats', 'label': 'Display Statistics', 'type': 'boolean', 'default': True},
        {'id': 'width',     'label': 'Plot Width',          'type': 'scalar', 'min': 200, 'max': 1200, 'default': 512},
        {'id': 'height',    'label': 'Plot Height',         'type': 'scalar', 'min': 150, 'max': 800, 'default': 300},
    ]
)
class HistogramNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        
        mode = int(params.get('mode', 0))
        bins = int(params.get('bins', 256))
        log_scale = bool(params.get('log_scale', False))
        show_stats = bool(params.get('show_stats', True))
        w = int(params.get('width', 512))
        h = int(params.get('height', 300))
        
        # Prepare dark technical background
        out = np.zeros((h, w, 3), dtype=np.uint8) + 18 
        
        # Draw coordinate grid
        for i in range(1, 4):
            x_line = int(w * i / 4)
            cv2.line(out, (x_line, 0), (x_line, h), (45, 45, 45), 1)
            y_line = int(h * i / 4)
            cv2.line(out, (0, y_line), (w, y_line), (45, 45, 45), 1)
            
        # Robust type handling: Histogram calculation requires uint8
        if img.dtype != np.uint8:
            if img.max() <= 1.1: # Likely 0.0-1.0 range
                img = (img * 255).clip(0, 255).astype(np.uint8)
            else:
                img = img.clip(0, 255).astype(np.uint8)

        # Analyze channels
        is_color = len(img.shape) == 3 and img.shape[2] == 3
        if mode == 1 and is_color: # Convert to luma for monochrome mode
             img_proc = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
             channels = [0]
             colors = [(220, 220, 220)]
             chan_names = ["Luminance"]
        elif is_color:
             img_proc = img
             channels = [0, 1, 2] # BGR
             colors = [(255, 120, 100), (100, 255, 120), (100, 120, 255)] 
             chan_names = ["Blue channel", "Green channel", "Red channel"]
        else:
             img_proc = img
             channels = [0]
             colors = [(220, 220, 220)]
             chan_names = ["Intensity"]
             
        hist_data = []
        for i in channels:
            # calcHist returns an array of shape (bins, 1)
            hist = cv2.calcHist([img_proc], [i], None, [bins], [0, 256])
            if log_scale:
                hist = np.log10(hist + 1)
            hist_data.append(hist)
            
        # Normalize based on global max to maintain relative scale
        max_val = max([h.max() for h in hist_data]) if hist_data else 1.0
        if max_val <= 0: max_val = 1.0
        
        # Render curves
        for i, hist in enumerate(hist_data):
            pts = []
            for j in range(bins):
                val = float(hist[j][0]) # Ensure we get the scalar value
                x_px = int(j * (w - 1) / (bins - 1)) if bins > 1 else 0
                y_px = int((h - 1) - (val / max_val * (h - 1)))
                y_px = np.clip(y_px, 0, h - 1)
                pts.append([x_px, y_px])
            
            pts = np.array(pts, np.int32)
            cv2.polylines(out, [pts], False, colors[i], 2, cv2.LINE_AA)
            
            # Metadata Overlay
            if show_stats:
                try:
                    chan_data = img_proc[:,:,i] if len(img_proc.shape)==3 else img_proc
                    mean_val = np.mean(chan_data)
                    std_val = np.std(chan_data)
                    stat_text = f"{chan_names[i]}: avg={mean_val:.1f} std={std_val:.1f}"
                    cv2.putText(out, stat_text, (12, 22 + i*20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1, cv2.LINE_AA)
                except:
                    pass

        # Border
        cv2.rectangle(out, (0, 0), (w-1, h-1), (80, 80, 80), 1)
        
        return {'main': out}
