"""
cv_skeletonize.py — clean 1-px binary skeleton as a usable mask.

feat_skeleton is a *measurement* node (overlay + branch count + inscribed radius).
For a repair pipeline we need the raw 1-pixel medial line as a binary mask to feed
into cv_directional_dilate. This node does pre-clean (small-object removal + hole
close) then a true thinning, and emits the skeleton as a mask.
"""

import cv2
import numpy as np

try:
    from skimage.morphology import skeletonize, medial_axis
    _SKIMAGE_OK = True
except Exception:
    _SKIMAGE_OK = False

from registry import vision_node, NodeProcessor


def _drop_small_blobs(binm: np.ndarray, min_size: int) -> np.ndarray:
    """Remove connected components with area < min_size. Version-proof (cv2)."""
    if min_size <= 0:
        return binm
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binm, connectivity=8)
    keep = np.zeros_like(binm)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_size:
            keep[labels == i] = 1
    return keep


@vision_node(
    type_id='cv_skeletonize',
    label='Skeletonize',
    category='mask',
    icon='GitBranch',
    description=(
        "Reduces a binary mask to its 1-pixel medial line and outputs it as a "
        "clean mask (ready for Directional Dilate). Pre-cleans by removing small "
        "blobs and closing holes. Methods: Skeletonize (Zhang-Suen), Medial Axis, "
        "or OpenCV thinning fallback."
    ),
    resizable=True, min_width=220, min_height=170, colorable=True,
    inputs=[
        {'id': 'mask', 'label': 'Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',     'label': 'Skeleton', 'color': 'mask'},
        {'id': 'preview',  'label': 'Preview',  'color': 'image'},
        {'id': 'length_px','label': 'Length',   'color': 'scalar'},
    ],
    params=[
        {'id': 'method',       'label': 'Method',        'type': 'enum', 'options': ['Skeletonize', 'Medial Axis'], 'default': 0},
        {'id': 'min_size',     'label': 'Min Blob (px)', 'type': 'int',  'default': 32, 'min': 0,  'max': 5000},
        {'id': 'close_holes',  'label': 'Close Holes',   'type': 'int',  'default': 3,  'min': 0,  'max': 25},
    ]
)
class SkeletonizeNode(NodeProcessor):

    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None:
            return {'main': None, 'preview': None, 'length_px': 0.0}
        if not _SKIMAGE_OK:
            if not self.ensure_packages(['skimage'], pip_names=['scikit-image']):
                return {'main': mask, 'preview': None, 'length_px': 0.0}

        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        binm = (mask > 0).astype(np.uint8)

        # pre-clean: close holes then drop tiny blobs
        ch = int(params.get('close_holes', 3))
        if ch > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ch, ch))
            binm = cv2.morphologyEx(binm, cv2.MORPH_CLOSE, k)
        binm = _drop_small_blobs(binm, int(params.get('min_size', 32)))
        boolm = binm.astype(bool)

        if int(params.get('method', 0)) == 1:
            skel = medial_axis(boolm)
        else:
            skel = skeletonize(boolm)
        skel_u8 = (skel.astype(np.uint8)) * 255

        preview = cv2.cvtColor(binm * 255, cv2.COLOR_GRAY2BGR)
        preview[skel] = (0, 0, 255)             # skeleton in red over the mask
        return {'main': skel_u8, 'preview': preview, 'length_px': float(int(skel.sum()))}
