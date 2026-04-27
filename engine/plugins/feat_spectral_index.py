import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

_BANDS   = ["Blue (0)", "Green (1)", "Red (2)", "Luminance"]
_PRESETS = ["Custom", "NDWI proxy (B−G)", "NDVI proxy (G−R)", "NDSI proxy (B−R)"]

@vision_node(
    type_id="feat_spectral_index",
    label="Spectral Index",
    category="features",
    icon="Activity",
    description="Generic normalized difference index (A−B)/(A+B). Presets: NDWI, NDVI, NDSI. Custom: pick channels freely. Connect image_b for two-image mode (e.g. separate NIR band).",
    inputs=[
        {"id": "image_a", "color": "image"},
        {"id": "image_b", "color": "image"}
    ],
    outputs=[
        {"id": "main",     "color": "image"},
        {"id": "mask",     "color": "mask"},
        {"id": "coverage", "color": "scalar"}
    ],
    params=[
        {"id": "preset",    "label": "Preset",    "type": "enum",   "options": _PRESETS, "default": 0},
        {"id": "ch_a",      "label": "Band A",    "type": "enum",   "options": _BANDS,   "default": 0},
        {"id": "ch_b",      "label": "Band B",    "type": "enum",   "options": _BANDS,   "default": 1},
        {"id": "threshold", "label": "Threshold", "type": "scalar", "min": -1.0, "max": 1.0, "default": 0.2, "step": 0.01},
        {"id": "colormap",  "label": "Colormap",  "type": "enum",   "options": ["Viridis", "Ocean", "Autumn"], "default": 0}
    ]
)
class SpectralIndexNode(NodeProcessor):
    _CMAPS    = [cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_OCEAN, cv2.COLORMAP_AUTUMN]
    # Preset → (ch_a, ch_b) for single-image extraction
    _PRESETS  = {1: (0, 1), 2: (1, 2), 3: (0, 2)}

    def _extract(self, img, ch):
        if len(img.shape) == 2:
            return img.astype(np.float32)
        ch = int(ch)
        if ch <= 2:
            return img[:, :, ch].astype(np.float32)
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)

    def process(self, inputs, params):
        img_a = inputs.get('image_a') or inputs.get('image')
        if img_a is None:
            return {"main": None, "mask": None, "coverage": 0.0}

        if len(img_a.shape) == 2:
            img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)

        img_b     = inputs.get('image_b')
        preset    = int(params.get('preset', 0))
        threshold = float(params.get('threshold', 0.0))
        cmap_idx  = int(params.get('colormap', 0))

        # Resolve channels from preset or manual selection
        if preset > 0 and preset in self._PRESETS:
            ca, cb = self._PRESETS[preset]
        else:
            ca = int(params.get('ch_a', 0))
            cb = int(params.get('ch_b', 1))

        band_a = self._extract(img_a, ca)
        band_b = self._extract(img_b if img_b is not None else img_a, cb)

        # Resize band_b to match band_a if needed
        if band_b.shape != band_a.shape:
            band_b = cv2.resize(band_b, (band_a.shape[1], band_a.shape[0]), interpolation=cv2.INTER_LINEAR)

        index = (band_a - band_b) / (band_a + band_b + 1e-6)

        # Colorized output
        idx_u8 = ((index + 1.0) / 2.0 * 255.0).clip(0, 255).astype(np.uint8)
        cmap   = self._CMAPS[min(cmap_idx, len(self._CMAPS) - 1)]
        main   = cv2.applyColorMap(idx_u8, cmap)

        mask     = (index > threshold).astype(np.uint8) * 255
        coverage = float(np.count_nonzero(mask)) / mask.size * 100.0

        return {"main": main, "mask": mask, "coverage": coverage}
