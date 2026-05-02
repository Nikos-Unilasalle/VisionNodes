import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='sci_connected_components',
    label='Connected Components',
    category=['analysis', 'scientific'],
    icon='Layers',
    description="Label and count connected regions (particles, cells, blobs). Measures area and centroid of each object.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main',       'color': 'image',  'label': 'Labeled Image'},
        {'id': 'count',      'color': 'scalar', 'label': 'Object Count'},
        {'id': 'areas',      'color': 'list',   'label': 'Areas (px²)'},
        {'id': 'centroids',  'color': 'list',   'label': 'Centroids'},
        {'id': 'labels_map', 'color': 'any',    'label': 'Label Map'},
        {'id': 'mask_out',   'color': 'mask',   'label': 'Binary Mask'},
        {'id': 'contour_out','color': 'mask',   'label': 'Contours Mask'},
    ],
    params=[
        {'id': 'threshold',    'label': 'Threshold',       'type': 'int',  'default': 128,    'min': 0,    'max': 255},
        {'id': 'min_area',     'label': 'Min Area (px²)',  'type': 'int',  'default': 50,     'min': 1,    'max': 1000000},
        {'id': 'max_area',     'label': 'Max Area (px²)',  'type': 'int',  'default': 500000, 'min': 1,    'max': 10000000},
        {'id': 'connectivity', 'label': 'Connectivity',    'type': 'enum', 'options': ['8-connected', '4-connected'], 'default': 0},
        {'id': 'colorize',     'label': 'Colorize Labels', 'type': 'bool', 'default': True},
        {'id': 'show_cross',   'label': 'Show Centroids',  'type': 'bool', 'default': True},
    ]
)
class ConnectedComponentsNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'count': 0, 'areas': [], 'centroids': [],
                    'labels_map': None, 'mask_out': None, 'contour_out': None}

        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, binary = cv2.threshold(gray, int(params.get('threshold', 128)), 255, cv2.THRESH_BINARY)

        conn     = 8 if int(params.get('connectivity', 0)) == 0 else 4
        min_area = int(params.get('min_area', 50))
        max_area = int(params.get('max_area', 500000))

        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=conn)

        valid = [i for i in range(1, n_labels)
                 if min_area <= int(stats[i, cv2.CC_STAT_AREA]) <= max_area]

        areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in valid]
        cents = [(float(centroids[i][0]), float(centroids[i][1])) for i in valid]

        lut_filter = np.zeros(n_labels, dtype=np.int32)
        for i in valid:
            lut_filter[i] = i
        filtered_labels = lut_filter[labels]

        if bool(params.get('colorize', True)):
            rng = np.random.default_rng(42)
            lut = np.zeros((n_labels, 3), dtype=np.uint8)
            for i in valid:
                lut[i] = rng.integers(40, 255, 3)
            out = lut[labels]
        else:
            # Draw region outlines on original image for colorize=False
            base = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            out = base
            solid = (filtered_labels > 0).astype(np.uint8) * 255
            cnts_draw, _ = cv2.findContours(solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(out, cnts_draw, -1, (0, 255, 120), 1)

        if bool(params.get('show_cross', True)):
            for i in valid:
                cx, cy = int(centroids[i][0]), int(centroids[i][1])
                cv2.drawMarker(out, (cx, cy), (255, 255, 255), cv2.MARKER_CROSS, 8, 1)

        cv2.putText(out, f"n={len(valid)}", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        solid_mask = (filtered_labels > 0).astype(np.uint8) * 255
        contours_mask = np.zeros_like(solid_mask)
        cnts, _ = cv2.findContours(solid_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(contours_mask, cnts, -1, 255, 1)

        return {
            'main':        out,
            'count':       len(valid),
            'areas':       areas,
            'centroids':   cents,
            'labels_map':  filtered_labels,
            'mask_out':    solid_mask,
            'contour_out': contours_mask,
        }
