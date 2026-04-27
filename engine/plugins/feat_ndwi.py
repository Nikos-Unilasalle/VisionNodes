import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="feat_ndwi",
    label="NDWI Water Index",
    category="features",
    icon="Droplets",
    description="Normalized Difference Water Index. Standard formula: (Green−NIR)/(Green+NIR) — connect a NIR band to the second input (Sentinel-2 B8, Landsat B5). RGB Approx. mode uses (B−G)/(B+G) for standard RGB images only. Water threshold: >0.2.",
    inputs=[
        {"id": "image", "color": "image"},
        {"id": "nir",   "color": "image"}
    ],
    outputs=[
        {"id": "main",     "color": "image"},
        {"id": "mask",     "color": "mask"},
        {"id": "coverage", "color": "scalar"}
    ],
    params=[
        {"id": "mode",      "label": "Mode",      "type": "enum",   "options": ["RGB Approx. (B−G)", "Green + NIR (standard)"], "default": 0},
        {"id": "threshold", "label": "Threshold", "type": "scalar", "min": -1.0, "max": 1.0, "default": 0.2, "step": 0.01},
        {"id": "colormap",  "label": "Colormap",  "type": "enum",   "options": ["Viridis", "Ocean", "Jet"],     "default": 0}
    ]
)
class NdwiNode(NodeProcessor):
    _CMAPS = [cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_OCEAN, cv2.COLORMAP_JET]

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {"main": None, "mask": None, "coverage": 0.0}

        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        mode      = int(params.get('mode', 0))
        threshold = float(params.get('threshold', 0.0))
        cmap_idx  = int(params.get('colormap', 0))
        nir       = inputs.get('nir')

        if mode == 1 and nir is not None:
            # True NDWI: (Green - NIR) / (Green + NIR)
            green = img[:, :, 1].astype(np.float32)
            nir_band = (cv2.cvtColor(nir, cv2.COLOR_BGR2GRAY) if len(nir.shape) == 3 else nir).astype(np.float32)
            ndwi = (green - nir_band) / (green + nir_band + 1e-6)
        else:
            # RGB proxy: (Blue - Green) / (Blue + Green)
            b = img[:, :, 0].astype(np.float32)
            g = img[:, :, 1].astype(np.float32)
            ndwi = (b - g) / (b + g + 1e-6)

        # Colorized index map
        ndwi_u8 = ((ndwi + 1.0) / 2.0 * 255.0).clip(0, 255).astype(np.uint8)
        cmap    = self._CMAPS[min(cmap_idx, len(self._CMAPS) - 1)]
        main    = cv2.applyColorMap(ndwi_u8, cmap)

        # Water mask: pixels above threshold
        mask     = (ndwi > threshold).astype(np.uint8) * 255
        coverage = float(np.count_nonzero(mask)) / mask.size * 100.0

        return {"main": main, "mask": mask, "coverage": coverage}
