import cv2
import numpy as np
from registry import vision_node, NodeProcessor

MAX_BANDS = 10


def _binary(img, shape=None):
    m = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    if shape is not None and m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return (m > 0).astype(np.uint8)


def _distance_to_outer_edge(outer, ignore_border):
    """Distance of each pixel to the outer mask's edge. With ignore_border, the image frame is
    not an edge: the mask is extended past the frame by edge replication before measuring."""
    if not ignore_border:
        return cv2.distanceTransform(outer, cv2.DIST_L2, 5)
    h, w = outer.shape
    pad = max(h, w) // 2
    padded = cv2.copyMakeBorder(outer, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    return cv2.distanceTransform(padded, cv2.DIST_L2, 5)[pad:pad + h, pad:pad + w]


@vision_node(
    type_id='mask_depth_bands',
    label='Mask Depth Bands',
    category='mask',
    icon='Target',
    description=(
        "Relative depth between an inner mask and the edge of an outer mask: 0 at the inner "
        "boundary, 1 at the outer edge. Splits the layer in between into N concentric bands "
        "(e.g. inner / middle / outer cortex, rind layers, coating thickness zones) and outputs "
        "a mask for a depth range (e.g. 0.2–0.8 = middle 60%). The image frame is not treated "
        "as an edge, so objects cut by the frame keep correct depths."
    ),
    inputs=[
        {'id': 'inner', 'color': 'mask', 'label': 'Inner (e.g. stele)'},
        {'id': 'outer', 'color': 'mask', 'label': 'Outer (e.g. section)'},
    ],
    outputs=[
        {'id': 'bands', 'color': 'markers', 'label': 'Band Labels (1..N)'},
        {'id': 'range_mask', 'color': 'mask', 'label': 'Depth Range'},
        {'id': 'band_1', 'color': 'mask'},
        {'id': 'band_2', 'color': 'mask'},
        {'id': 'band_3', 'color': 'mask'},
        {'id': 'depth', 'color': 'any', 'label': 'Depth (0–1 float)'},
        {'id': 'main', 'color': 'image'},
    ],
    params=[
        {'id': 'bands', 'label': 'Number of Bands', 'type': 'int', 'default': 3, 'min': 1, 'max': MAX_BANDS},
        {'id': 'range_low', 'label': 'Range Low (0–1)', 'type': 'float', 'default': 0.2, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'range_high', 'label': 'Range High (0–1)', 'type': 'float', 'default': 0.8, 'min': 0, 'max': 1, 'step': 0.05},
        {'id': 'ignore_border', 'label': 'Image Frame Is Not an Edge', 'type': 'bool', 'default': True},
    ],
)
class MaskDepthBandsNode(NodeProcessor):
    def process(self, inputs, params):
        outer_in, inner_in = inputs.get('outer'), inputs.get('inner')
        if outer_in is None:
            return {'bands': None, 'range_mask': None, 'band_1': None, 'band_2': None,
                    'band_3': None, 'depth': None, 'main': None}

        outer = _binary(outer_in)
        inner = _binary(inner_in, outer.shape) if inner_in is not None else np.zeros_like(outer)
        layer = (outer > 0) & (inner == 0)

        d_in = cv2.distanceTransform((inner == 0).astype(np.uint8), cv2.DIST_L2, 5) if inner.any() \
            else np.zeros(outer.shape, np.float32)
        d_out = _distance_to_outer_edge(outer, bool(params.get('ignore_border', True)))
        depth = np.where(layer, d_in / (d_in + d_out + 1e-6), 0).astype(np.float32)

        n = int(np.clip(int(params.get('bands', 3)), 1, MAX_BANDS))
        bands = np.where(layer, np.minimum((depth * n).astype(np.int32), n - 1) + 1, 0).astype(np.int32)
        lo, hi = float(params.get('range_low', 0.2)), float(params.get('range_high', 0.8))
        range_mask = (layer & (depth >= lo) & (depth <= hi)).astype(np.uint8) * 255

        vis = cv2.applyColorMap((depth * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
        vis[~layer] = 0
        out = {'bands': bands, 'range_mask': range_mask, 'depth': depth, 'main': vis}
        for k in (1, 2, 3):
            out[f'band_{k}'] = (bands == k).astype(np.uint8) * 255
        return out
