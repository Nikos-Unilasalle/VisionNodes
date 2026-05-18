import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='feat_mask_stats',
    label='Mask Statistics',
    category='analysis',
    icon='BarChart2',
    description=(
        'Computes statistics from a binary mask: area (px), area % relative to ref_mask, '
        'centroid (x, y), bounding box width and height. '
        'Connect ref_mask for area_pct relative to full footprint. '
        'Connect image for intensity-weighted centroid (pressure centroid).'
    ),
    inputs=[
        {'id': 'mask',     'color': 'mask'},
        {'id': 'ref_mask', 'color': 'mask'},
        {'id': 'image',    'color': 'image'},
    ],
    outputs=[
        {'id': 'stats',      'color': 'dict'},
        {'id': 'area_px',    'color': 'scalar'},
        {'id': 'area_pct',   'color': 'scalar'},
        {'id': 'centroid_x', 'color': 'scalar'},
        {'id': 'centroid_y', 'color': 'scalar'},
    ],
    params=[
        {'id': 'weighted_centroid', 'label': 'Weighted Centroid',
         'type': 'bool', 'default': False},
    ],
)
class MaskStatsNode(NodeProcessor):
    def process(self, inputs, params):
        mask     = inputs.get('mask')
        ref_mask = inputs.get('ref_mask')
        image    = inputs.get('image')

        empty = {'stats': {}, 'area_px': 0.0, 'area_pct': 0.0,
                 'centroid_x': 0.0, 'centroid_y': 0.0}

        if mask is None:
            return empty

        weighted = str(params.get('weighted_centroid', False)).lower() not in ('false', '0', 'no')

        mg = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(mg, 127, 255, cv2.THRESH_BINARY)

        ysp, xsp = np.where(binary > 0)
        area_px = int(len(xsp))

        # Reference area for percentage computation
        if ref_mask is not None:
            rg = ref_mask if len(ref_mask.shape) == 2 else cv2.cvtColor(ref_mask, cv2.COLOR_BGR2GRAY)
            _, ref_bin = cv2.threshold(rg, 127, 255, cv2.THRESH_BINARY)
            ref_area = max(1, int(np.sum(ref_bin > 0)))
        else:
            ref_area = max(1, area_px)

        area_pct = round(100.0 * area_px / ref_area, 2)

        # Centroid
        if area_px == 0:
            cx, cy = 0.0, 0.0
        elif weighted and image is not None:
            gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            w_map = gray.astype(np.float32)
            w_map[binary == 0] = 0.0
            total_w = float(np.sum(w_map))
            if total_w > 0:
                cx = float(np.sum(np.arange(w_map.shape[1]) * np.sum(w_map, axis=0)) / total_w)
                cy = float(np.sum(np.arange(w_map.shape[0]) * np.sum(w_map, axis=1)) / total_w)
            else:
                cx, cy = float(np.mean(xsp)), float(np.mean(ysp))
        else:
            cx, cy = float(np.mean(xsp)), float(np.mean(ysp))

        # Bounding box
        bbox_w = int(np.max(xsp) - np.min(xsp)) if area_px > 0 else 0
        bbox_h = int(np.max(ysp) - np.min(ysp)) if area_px > 0 else 0

        stats = {
            'area_px':    area_px,
            'area_pct':   area_pct,
            'centroid_x': round(cx, 1),
            'centroid_y': round(cy, 1),
            'bbox_w':     bbox_w,
            'bbox_h':     bbox_h,
        }

        return {
            'stats':      stats,
            'area_px':    float(area_px),
            'area_pct':   float(area_pct),
            'centroid_x': cx,
            'centroid_y': cy,
        }
