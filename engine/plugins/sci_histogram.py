import cv2
import numpy as np
import base64
from registry import NodeProcessor, vision_node

def _channel_stats(chan):
    """Statistiques d'un canal uint8, sur les valeurs brutes.

    Le median passe par la distribution cumulee : sur une image de plusieurs
    millions de pixels, np.median trie et coute bien plus cher que 256 sommes.
    """
    counts = np.bincount(chan.ravel(), minlength=256).astype(np.float64)
    total = counts.sum()
    cumulative = np.cumsum(counts)
    nonzero = np.flatnonzero(counts)
    return {
        'mean': float(np.mean(chan)),
        'std': float(np.std(chan)),
        'min': float(nonzero[0]) if nonzero.size else 0.0,
        'max': float(nonzero[-1]) if nonzero.size else 0.0,
        'median': float(np.searchsorted(cumulative, total / 2.0)),
    }


@vision_node(
    type_id='sci_histogram',
    label='Histogram',
    category='measure',
    icon='BarChart2',
    description="Statistical distribution of pixel intensities. Performs radiometric analysis of input data across spectral channels for scientific validation.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main', 'color': 'image',  'label': 'Main'},
        {'id': 'mean', 'color': 'scalar', 'label': 'Mean (luma)'},
        {'id': 'std',  'color': 'scalar', 'label': 'Std Dev (luma)'},
        {'id': 'data', 'color': 'dict',   'label': 'Stats'},
    ],
    params=[
        {'id': 'mode',      'label': 'Spectral Mode',       'type': 'enum', 'options': ['Overlay (RGB)', 'Monochrome (Luma)'], 'default': 0},
        {'id': 'bins',      'label': 'Quantization (Bins)', 'type': 'scalar', 'min': 16, 'max': 256, 'default': 256},
        {'id': 'log_scale', 'label': 'Logarithmic Scale',   'type': 'boolean', 'default': False},
        {'id': 'show_stats', 'label': 'Display Statistics', 'type': 'boolean', 'default': True},
    ],
    resizable=True,
    min_width=250,
    min_height=180
)
class HistogramNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'mean': None, 'std': None, 'data': None}
        
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
            
        hist_output = {}
        per_channel = []
        for i, h_data in enumerate(hist_data):
            # Convert numpy array to flat list for JSON serialization
            key = f"hist_{i}"
            hist_output[key] = h_data.flatten().tolist()

            # Les statistiques sont calculees dans tous les cas : show_stats ne
            # commande que l'affichage, jamais la donnee produite en sortie.
            chan_data = img_proc[:, :, i] if len(img_proc.shape) == 3 else img_proc
            stats = _channel_stats(chan_data)
            per_channel.append(stats)
            hist_output[f"avg_{i}"] = stats['mean']
            hist_output[f"std_{i}"] = stats['std']

        # Drawing
        max_val = 0
        for h_data in hist_data:
            m = np.max(h_data)
            if m > max_val: max_val = m
            
        if max_val > 0:
            for i, h_data in enumerate(hist_data):
                color = colors[i]
                name = chan_names[i]
                pts = []
                for b in range(bins):
                    val = h_data[b][0]
                    # Normalize y (leave 40px for labels and 20px bottom margin)
                    norm_val = (val / max_val) * (h - 60) 
                    px = int(b * w / (bins - 1)) if bins > 1 else 0
                    py = int(h - 20 - norm_val)
                    pts.append([px, py])
                
                pts = np.array(pts, np.int32)
                
                # Fill under the curve with low alpha
                fill_pts = np.vstack([pts, [[w-1, h-21], [0, h-21]]])
                overlay = out.copy()
                cv2.fillPoly(overlay, [fill_pts], color)
                cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
                
                # Draw the line
                cv2.polylines(out, [pts], False, color, 2, cv2.LINE_AA)
                
                if show_stats:
                    avg = hist_output.get(f"avg_{i}", 0)
                    std = hist_output.get(f"std_{i}", 0)
                    stat_txt = f"{name}: Mean={avg:.1f} Std={std:.1f}"
                    cv2.putText(out, stat_txt, (10, 25 + i * 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # La luminance donne un chiffre unique quel que soit le mode, la ou les
        # statistiques par canal en donnent un par canal.
        luma = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if is_color else img
        luma_stats = _channel_stats(luma)

        data = {
            'channels': chan_names,
            'mean':   [s['mean']   for s in per_channel],
            'std':    [s['std']    for s in per_channel],
            'min':    [s['min']    for s in per_channel],
            'max':    [s['max']    for s in per_channel],
            'median': [s['median'] for s in per_channel],
            'hist': [hist_output[f"hist_{i}"] for i in range(len(per_channel))],
            'bins': bins,
            'pixels': int(luma.size),
            'log_scale': log_scale,
            'luma_mean': luma_stats['mean'],
            'luma_std': luma_stats['std'],
        }

        return {
            'main': out,
            'mean': luma_stats['mean'],
            'std': luma_stats['std'],
            'data': data,
            **hist_output,
            'is_color': is_color,
            'mode': mode
        }
