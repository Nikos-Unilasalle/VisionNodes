import cv2
import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='hema_blood_segment',
    label='Blood Smear Segmenter',
    category='hematology',
    icon='ScanLine',
    description=(
        'Segments blood cells from a Giemsa/Wright-stained smear.\n\n'
        'Handles rouleaux (stacked RBCs) via distance-transform watershed. '
        'Outputs a label map ready for Blood Cell Classifier.'
    ),
    resizable=True,
    min_width=260,
    min_height=200,
    colorable=True,
    inputs=[
        {'id': 'image',     'label': 'Smear (BGR)', 'color': 'image'},
        {'id': 'um_per_px', 'label': 'um/px (opt)', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'labels_map', 'label': 'Labels Map', 'color': 'markers'},
        {'id': 'overlay',    'label': 'Overlay',    'color': 'image'},
        {'id': 'mask',       'label': 'Cell Mask',  'color': 'mask'},
        {'id': 'count',      'label': 'Cell Count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'bg_threshold',  'label': 'BG Threshold',      'type': 'int',   'default': 30,  'min': 5,   'max': 120},
        {'id': 'dist_fraction', 'label': 'Split Sensitivity',  'type': 'float', 'default': 0.40,'min': 0.1, 'max': 0.9, 'step': 0.05},
        {'id': 'close_radius',  'label': 'Close Radius (px)',  'type': 'int',   'default': 4,   'min': 1,   'max': 15},
        {'id': 'blur_radius',   'label': 'Blur Radius (px)',   'type': 'int',   'default': 3,   'min': 1,   'max': 11},
        {'id': 'min_cell_px',   'label': 'Min Cell Area (px)', 'type': 'int',   'default': 40,  'min': 5,   'max': 500},
        {'id': 'max_cell_px',   'label': 'Max Cell Area (px)', 'type': 'int',   'default': 1500,'min': 100, 'max': 10000},
        {'id': 'dilate_bg',     'label': 'BG Dilate (px)',     'type': 'int',   'default': 6,   'min': 1,   'max': 20},
    ],
)
class HemaBloodSegmenter(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'labels_map': None, 'overlay': None, 'mask': None, 'count': 0}

        blur_r      = int(params.get('blur_radius', 3)) | 1   # must be odd
        bg_thresh   = int(params.get('bg_threshold', 30))
        close_r     = int(params.get('close_radius', 4))
        dist_frac   = float(params.get('dist_fraction', 0.40))
        min_area    = int(params.get('min_cell_px', 40))
        max_area    = int(params.get('max_cell_px', 1500))
        dilate_bg_r = int(params.get('dilate_bg', 6))

        blurred = cv2.GaussianBlur(img, (blur_r, blur_r), 0)

        # Giemsa/Wright: background is pale → high LAB-L; cells are darker
        lab   = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        l_inv = 255 - lab[:, :, 0]   # cells appear bright here

        _, mask = cv2.threshold(l_inv, bg_thresh, 255, cv2.THRESH_BINARY)

        # Fill holes (rouleaux centers appear pale) then remove tiny noise
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_r * 2 + 1,) * 2)
        k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k_open)
        mask = mask.astype(np.uint8)

        # Sure background = dilated mask
        k_bg   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_bg_r * 2 + 1,) * 2)
        sure_bg = cv2.dilate(mask, k_bg)

        # Sure foreground via distance transform peaks (separates touching cells)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        peak = dist_frac * float(dist.max()) if dist.max() > 0 else 1.0
        _, sure_fg = cv2.threshold(dist, peak, 255, cv2.THRESH_BINARY)
        sure_fg = sure_fg.astype(np.uint8)

        unknown = cv2.subtract(sure_bg, sure_fg)

        _, seeds = cv2.connectedComponents(sure_fg)
        # 0 = unknown, 1 = sure background, ≥2 = individual cells
        seeds = seeds + 1
        seeds[unknown == 255] = 0

        # Watershed needs 3-channel image
        src = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        markers = seeds.astype(np.int32)
        cv2.watershed(src, markers)

        # Remove watershed boundaries (-1) and background (1)
        labels = markers.copy()
        labels[labels <= 1] = 0
        labels[labels == -1] = 0

        # Area filter: remove too small and too large regions
        final_labels = np.zeros_like(labels, dtype=np.int32)
        new_id = 1
        for lid in np.unique(labels):
            if lid == 0:
                continue
            area = int(np.sum(labels == lid))
            if min_area <= area <= max_area:
                final_labels[labels == lid] = new_id
                new_id += 1

        count = new_id - 1

        # Colorized overlay
        rng = np.random.default_rng(42)
        max_lbl = int(final_labels.max()) if final_labels.max() > 0 else 1
        lut = np.zeros((max_lbl + 1, 3), dtype=np.uint8)
        lut[1:] = rng.integers(60, 230, (max_lbl, 3))
        colored = lut[np.clip(final_labels, 0, max_lbl)]
        overlay = cv2.addWeighted(src, 0.50, colored, 0.50, 0)

        cv2.putText(overlay, f'n={count}', (6, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        bin_mask = (final_labels > 0).astype(np.uint8) * 255

        return {
            'labels_map': final_labels,
            'overlay':    overlay,
            'mask':       bin_mask,
            'count':      count,
        }
