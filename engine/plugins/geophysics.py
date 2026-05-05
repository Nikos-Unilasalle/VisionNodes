import cv2
import numpy as np
import os
import base64
from registry import NodeProcessor, vision_node

# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_preview(img, max_h=120, quality=50):
    try:
        h, w = img.shape[:2]
        sc = max_h / h
        pw = int(w * sc)
        if pw > 0:
            pimg = cv2.resize(img, (pw, max_h))
            _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, quality])
            return base64.b64encode(buf).decode('utf-8')
    except:
        pass
    return None

def _resolve_path(path):
    if not path:
        return None
    if os.path.exists(path):
        return os.path.abspath(path)
    for candidate in [
        os.path.join(os.getcwd(), 'samples', path),
        os.path.join(os.getcwd(), 'samples', os.path.basename(path)),
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def _make_matrix_dict(band, w, h, mmin, mmax):
    return {
        "bands": [band], "count": 1,
        "width": w, "height": h,
        "min": float(mmin), "max": float(mmax),
        "dtype": "float32"
    }

# RdYlGn LUT (BGR) — good contrast for diverging geophysical data
_RDYLGN_LUT = np.zeros((256, 1, 3), dtype=np.uint8)
for i in range(256):
    if i < 128:
        t = i / 127.0
        _RDYLGN_LUT[i] = [0, int(255 * t), 255]
    else:
        t = (i - 128) / 127.0
        _RDYLGN_LUT[i] = [0, 255, int(255 * (1 - t))]

def _apply_rdylgn(vis):
    bgr = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    return cv2.LUT(bgr, _RDYLGN_LUT)

# ── Sediment Layers ─────────────────────────────────────────────────────────

_SED_COLORMAPS = [
    cv2.COLORMAP_INFERNO, cv2.COLORMAP_VIRIDIS,
    cv2.COLORMAP_MAGMA,   cv2.COLORMAP_JET,
    cv2.COLORMAP_BONE,
]

@vision_node(
    type_id="geo_sediment_loader",
    label="Sediment Layers",
    category=["geo", "src"],
    icon="Layers",
    description="Loads a (x,y,z) CSV of sediment conductivity into a regular grid.",
    inputs=[],
    outputs=[
        {"id": "main", "color": "image", "label": "Heatmap"},
        {"id": "data", "color": "any", "label": "Matrix"},
    ],
    params=[
        {"id": "path", "label": "CSV Path", "type": "string", "default": "sediment_layers.csv"},
        {"id": "layer_index", "label": "Layer", "type": "int", "min": 1, "max": 10, "default": 1},
        {"id": "norm_mode", "label": "Normalization", "type": "enum", "options": ["Local (per-layer)", "Global (all layers)"], "default": 0},
        {"id": "flip_y", "label": "Flip Y", "type": "boolean", "default": False},
        {"id": "colormap", "label": "Colormap", "type": "enum", "options": ["Inferno", "Viridis", "Magma", "Jet", "Bone"], "default": 0},
        {"id": "reload", "label": "Reload", "type": "trigger"}
    ]
)
class SedimentLoaderNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.layers = None
        self.last_path = None
        self.nx = self.ny = self.n_layers = 0
        self.global_min = self.global_max = 0.0

    def _load_data(self, path):
        resolved = _resolve_path(path)
        if resolved is None:
            print(f"[SedimentLoader] File not found: {path}")
            return False
        try:
            raw = np.genfromtxt(resolved, delimiter=',', skip_header=1)
            z = raw[:, 2].astype(np.float32)
            nx = int(np.max(raw[:, 0])) + 1
            ny = int(np.max(raw[:, 1])) + 1
            n_layers = len(z) // (nx * ny)
            if n_layers == 0 or len(z) % (nx * ny) != 0:
                print(f"[SedimentLoader] Invalid format: {len(z)} rows, grid {nx}x{ny}")
                return False
            self.nx, self.ny, self.n_layers = nx, ny, n_layers
            self.layers = z.reshape((n_layers, nx, ny)).transpose(0, 2, 1)
            self.global_min = float(np.min(self.layers))
            self.global_max = float(np.max(self.layers))
            self.last_path = resolved
            print(f"[SedimentLoader] {n_layers} layers {nx}x{ny} [{self.global_min:.2f}, {self.global_max:.2f}]")
            return True
        except Exception as e:
            print(f"[SedimentLoader] Error: {e}")
            return False

    def process(self, inputs, params):
        path = params.get('path', '')
        if path != self.last_path or params.get('reload') == 1:
            self._load_data(path)

        if self.layers is None:
            return {"main": None, "data": None}

        idx = max(0, min(self.n_layers - 1, int(params.get('layer_index', 1)) - 1))
        matrix = self.layers[idx].copy()
        if params.get('flip_y', False):
            matrix = np.flipud(matrix)

        norm_mode = int(params.get('norm_mode', 0))
        if norm_mode == 1: # Local (per-layer)
            m_min, m_max = float(np.min(matrix)), float(np.max(matrix))
        else: # Global (all layers)
            m_min, m_max = self.global_min, self.global_max

        if m_max > m_min:
            vis = ((matrix - m_min) / (m_max - m_min) * 255).astype(np.uint8)
        else:
            vis = np.zeros_like(matrix, dtype=np.uint8)

        vis_large = cv2.resize(vis, (300, 300), interpolation=cv2.INTER_NEAREST)
        cmap_idx = int(params.get('colormap', 0))
        heatmap = cv2.applyColorMap(vis_large, _SED_COLORMAPS[cmap_idx])

        return {
            "main": heatmap,
            "data": _make_matrix_dict(matrix, self.nx, self.ny, m_min, m_max),
            "preview": _make_preview(heatmap)
        }


# ── Geophysics Index ───────────────────────────────────────────────────────

_INDEX_CMAP = [
    ("RdYlGn (reco.)", _apply_rdylgn),
    ("Jet",            lambda v: cv2.applyColorMap(v, cv2.COLORMAP_JET)),
    ("Magma",          lambda v: cv2.applyColorMap(v, cv2.COLORMAP_MAGMA)),
    ("Viridis",        lambda v: cv2.applyColorMap(v, cv2.COLORMAP_VIRIDIS)),
    ("Inferno",        lambda v: cv2.applyColorMap(v, cv2.COLORMAP_INFERNO)),
]

@vision_node(
    type_id="geo_index",
    label="Geophysics Index",
    category=["geo", "analysis"],
    icon="Divide",
    description="Compute an index between two layers: normalized diff, ratio, sum, etc.",
    inputs=[
        {"id": "layer_a", "color": "any", "label": "Layer A"},
        {"id": "layer_b", "color": "any", "label": "Layer B"}
    ],
    outputs=[
        {"id": "main", "color": "image", "label": "Heatmap"},
        {"id": "data", "color": "any", "label": "Matrix"},
    ],
    params=[
        {"id": "mode", "label": "Formula", "type": "enum",
         "options": ["Normalized Diff (A-B)/(A+B)", "Difference (A-B)",
                     "Ratio A/B", "Normalized Sum (A+B)/max"],
         "default": 0},
        {"id": "colormap", "label": "Colormap", "type": "enum",
         "options": [c[0] for c in _INDEX_CMAP], "default": 0}
    ]
)
class GeoIndexNode(NodeProcessor):
    def _extract_matrix(self, val):
        if val is None:
            return None
        if isinstance(val, np.ndarray):
            return val.astype(np.float32)
        if isinstance(val, dict) and 'bands' in val:
            return val['bands'][0].astype(np.float32)
        return None

    def process(self, inputs, params):
        ma = self._extract_matrix(inputs.get('layer_a'))
        mb = self._extract_matrix(inputs.get('layer_b'))
        if ma is None or mb is None:
            return {"main": None, "data": None}

        if ma.shape != mb.shape:
            mb = cv2.resize(mb, (ma.shape[1], ma.shape[0]))

        mode = int(params.get('mode', 0))
        eps = 1e-10

        if mode == 0:  # Normalized Difference
            res = np.clip((ma - mb) / (ma + mb + eps), -1.0, 1.0)
            m_min, m_max = -1.0, 1.0
        elif mode == 1:  # Simple Difference
            res = ma - mb
            bound = max(abs(np.min(res)), abs(np.max(res))) or 1.0
            m_min, m_max = -bound, bound
        elif mode == 2:  # Ratio A/B
            res = np.where(np.abs(mb) > eps, ma / mb, 0.0)
            m_min, m_max = float(np.min(res)), float(np.max(res))
        else:  # Normalized Sum
            s = ma + mb
            mx = float(np.max(np.abs(s))) or 1.0
            res = s / mx
            m_min, m_max = -1.0, 1.0

        if m_max > m_min:
            vis = np.clip(((res - m_min) / (m_max - m_min) * 255), 0, 255).astype(np.uint8)
        else:
            vis = np.zeros_like(res, dtype=np.uint8)

        vis_large = cv2.resize(vis, (300, 300), interpolation=cv2.INTER_NEAREST)
        cmap_idx = int(params.get('colormap', 0))
        heatmap = _INDEX_CMAP[cmap_idx][1](vis_large)

        return {
            "main": heatmap,
            "data": _make_matrix_dict(res, ma.shape[1], ma.shape[0], m_min, m_max),
            "preview": _make_preview(heatmap)
        }
