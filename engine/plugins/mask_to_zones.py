import cv2
import numpy as np
from registry import vision_node, NodeProcessor

N_MASKS = 6


def _binary(m, shape=None):
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if shape is not None and m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


@vision_node(
    type_id='mask_to_zones',
    label='Masks to Zones',
    category='mask',
    icon='Layers',
    description=(
        "Combines up to six masks into one zone map: pixels of Mask k get the value k (1..6), "
        "pixels in none of them stay 0. Where masks overlap, the later one wins. Use it to feed "
        "nodes that work zone by zone (Sample Projection, Zone Statistics) with tissues, land "
        "covers or regions drawn separately. The Names (comma-separated, in mask order) are "
        "passed on as a list for labelling."
    ),
    inputs=[{'id': f'mask_{k}', 'color': 'mask', 'label': f'Mask {k}'} for k in range(1, N_MASKS + 1)],
    outputs=[
        {'id': 'zones', 'color': 'markers', 'label': 'Zone Map (1..N)'},
        {'id': 'names', 'color': 'list', 'label': 'Zone Names'},
        {'id': 'main', 'color': 'image'},
    ],
    params=[
        {'id': 'names', 'label': 'Names (comma-separated)', 'type': 'string', 'default': ''},
    ],
)
class MasksToZonesNode(NodeProcessor):
    def process(self, inputs, params):
        masks = [(k, inputs.get(f'mask_{k}')) for k in range(1, N_MASKS + 1)]
        masks = [(k, m) for k, m in masks if isinstance(m, np.ndarray)]
        names = [n.strip() for n in str(params.get('names', '')).split(',')]
        if not masks:
            return {'zones': None, 'names': names, 'main': None}
        shape = _binary(masks[0][1]).shape
        zones = np.zeros(shape, np.int32)
        for k, m in masks:
            zones[_binary(m, shape)] = k
        vis = cv2.applyColorMap((zones * (255 // N_MASKS)).astype(np.uint8), cv2.COLORMAP_TURBO)
        vis[zones == 0] = 0
        return {'zones': zones, 'names': names, 'main': vis}
