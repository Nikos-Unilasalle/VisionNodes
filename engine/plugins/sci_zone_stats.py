import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _labels(arr):
    if arr is None:
        return None
    a = np.asarray(arr)
    if a.ndim == 3:
        a = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    return a.astype(np.int32)


@vision_node(
    type_id='sci_zone_stats',
    label='Zone Region Stats',
    category='measure',
    icon='LayoutGrid',
    description=(
        "Counts labelled regions (cells, grains, particles…) and their mean / total area per zone. "
        "Each region is assigned to the zone under its centroid, so a region is counted once even "
        "if it straddles two zones. Zones = any label map (e.g. Mask Depth Bands); without zones, "
        "all regions form one zone. Watershed lines (−1) and background (0, 1 after watershed "
        "with a mask) are ignored via Min Area and the Ignore Label."
    ),
    inputs=[
        {'id': 'regions', 'color': 'markers'},
        {'id': 'zones', 'color': 'markers', 'label': 'Zones (opt.)'},
    ],
    outputs=[
        {'id': 'stats', 'color': 'dict'},
        {'id': 'total_count', 'color': 'scalar'},
        {'id': 'mean_area', 'color': 'scalar', 'label': 'Mean Area (all)'},
        {'id': 'counts', 'color': 'list'},
        {'id': 'mean_areas', 'color': 'list'},
        {'id': 'areas', 'color': 'list', 'label': 'All Areas'},
        {'id': 'regions_mask', 'color': 'mask', 'label': 'Counted Regions'},
    ],
    params=[
        {'id': 'min_area', 'label': 'Min Area (px)', 'type': 'int', 'default': 20, 'min': 0},
        {'id': 'max_area', 'label': 'Max Area (px, 0=off)', 'type': 'int', 'default': 0, 'min': 0},
        {'id': 'ignore_label', 'label': 'Ignore Label (e.g. 1 = watershed bg)', 'type': 'int', 'default': -99},
    ],
)
class ZoneRegionStatsNode(NodeProcessor):
    def process(self, inputs, params):
        regions = _labels(inputs.get('regions'))
        if regions is None:
            return {'stats': {}, 'total_count': 0, 'mean_area': 0.0, 'counts': [], 'mean_areas': [],
                    'areas': [], 'regions_mask': None}
        zones = _labels(inputs.get('zones'))
        if zones is not None and zones.shape != regions.shape:
            zones = cv2.resize(zones.astype(np.float32), (regions.shape[1], regions.shape[0]),
                               interpolation=cv2.INTER_NEAREST).astype(np.int32)

        ids, inverse = np.unique(regions.ravel(), return_inverse=True)
        valid = (ids > 0) & (ids != int(params.get('ignore_label', -99)))
        areas = np.bincount(inverse, minlength=len(ids)).astype(np.float64)
        ys, xs = np.indices(regions.shape)
        cy = np.bincount(inverse, weights=ys.ravel(), minlength=len(ids)) / np.maximum(areas, 1)
        cx = np.bincount(inverse, weights=xs.ravel(), minlength=len(ids)) / np.maximum(areas, 1)

        min_a, max_a = float(params.get('min_area', 20)), float(params.get('max_area', 0))
        valid &= areas >= min_a
        if max_a > 0:
            valid &= areas <= max_a

        if zones is None:
            zone_of = np.ones(len(ids), np.int32)
            n_zones = 1
        else:
            zone_of = zones[np.clip(cy.round().astype(int), 0, regions.shape[0] - 1),
                            np.clip(cx.round().astype(int), 0, regions.shape[1] - 1)]
            n_zones = max(1, int(zones.max()))
        valid &= zone_of > 0

        counts, means, stats = [], [], {}
        for z in range(1, n_zones + 1):
            sel = valid & (zone_of == z)
            c = int(sel.sum())
            m = float(areas[sel].mean()) if c else 0.0
            counts.append(c)
            means.append(m)
            stats[f'zone_{z}_count'] = c
            stats[f'zone_{z}_mean_area'] = m
            stats[f'zone_{z}_total_area'] = float(areas[sel].sum())

        kept = valid[inverse].reshape(regions.shape)
        all_areas = areas[valid]
        total = int(valid.sum())
        mean_all = float(all_areas.mean()) if total else 0.0
        stats.update(total_count=total, mean_area=mean_all)
        return {'stats': stats, 'total_count': total, 'mean_area': mean_all, 'counts': counts,
                'mean_areas': means, 'areas': all_areas.tolist(),
                'regions_mask': kept.astype(np.uint8) * 255}
