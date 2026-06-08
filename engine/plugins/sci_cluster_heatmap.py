import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_COLORMAPS = [
    ('Viridis', cv2.COLORMAP_VIRIDIS),
    ('Plasma',  cv2.COLORMAP_PLASMA),
    ('Turbo',   cv2.COLORMAP_TURBO),
    ('Jet',     cv2.COLORMAP_JET),
    ('Hot',     cv2.COLORMAP_HOT),
    ('Cool',    cv2.COLORMAP_COOL),
    ('Inferno', cv2.COLORMAP_INFERNO),
    ('Magma',   cv2.COLORMAP_MAGMA),
]
_CMAP_NAMES = [n for n, _ in _COLORMAPS]
_CMAP_IDS   = [i for _, i in _COLORMAPS]

_ID_KEYS = ('id', 'label', 'cluster_id', 'region_id', 'idx')


def _find_id(r: dict) -> int | None:
    for k in _ID_KEYS:
        if k in r:
            try:
                return int(r[k])
            except (ValueError, TypeError):
                continue
    return None


@vision_node(
    type_id='sci_cluster_heatmap',
    label='Cluster Heatmap',
    category='measure',
    icon='Palette',
    description=(
        "False-color each labeled region by a feature value (area, circularity, intensity…). "
        "Requires a label map and the regions list from Region Props. "
        "Includes a colorbar legend with min/max values."
    ),
    inputs=[
        {'id': 'labels_map', 'color': 'any',   'label': 'Label Map'},
        {'id': 'regions',    'color': 'list',  'label': 'Regions'},
        {'id': 'image',      'color': 'image', 'label': 'Background (optional)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Heatmap'},
    ],
    params=[
        {'id': 'feature',     'label': 'Feature',        'type': 'string', 'default': 'area', 'hints': 'item_keys'},
        {'id': 'colormap',    'label': 'Colormap',        'type': 'enum',   'options': _CMAP_NAMES, 'default': 0},
        {'id': 'alpha',       'label': 'Heatmap Alpha',   'type': 'float',  'default': 0.85, 'min': 0.0, 'max': 1.0},
        {'id': 'bg_alpha',    'label': 'BG Alpha',        'type': 'float',  'default': 0.25, 'min': 0.0, 'max': 1.0},
        {'id': 'show_values', 'label': 'Show Values',     'type': 'bool',   'default': False},
        {'id': 'colorbar',    'label': 'Show Colorbar',   'type': 'bool',   'default': True},
    ]
)
class ClusterHeatmapNode(NodeProcessor):
    def process(self, inputs, params):
        labels  = inputs.get('labels_map')
        regions = inputs.get('regions')
        img     = inputs.get('image')

        available_keys = sorted({
            k for r in (regions or []) if isinstance(r, dict)
            for k, v in r.items() if isinstance(v, (int, float))
        })

        if labels is None or not regions:
            return {'main': img, '_available_keys': available_keys}

        label_img = labels.astype(np.int32)
        h, w      = label_img.shape[:2]

        feat_name = str(params.get('feature', 'area')).strip() or 'area'

        cmap_id       = _CMAP_IDS[int(params.get('colormap', 0))]
        alpha         = float(params.get('alpha', 0.85))
        bg_alpha      = float(params.get('bg_alpha', 0.25))
        show_values   = bool(params.get('show_values', False))
        show_colorbar = bool(params.get('colorbar', True))

        # Build label → feature value map; auto-detect id key
        lbl_to_val = {}
        for r in regions:
            if not isinstance(r, dict):
                continue
            if feat_name not in r:
                continue
            region_id = _find_id(r)
            if region_id is None:
                continue
            try:
                lbl_to_val[region_id] = float(r[feat_name])
            except (ValueError, TypeError):
                continue

        if not lbl_to_val:
            return {'main': img, '_available_keys': available_keys}

        vals = list(lbl_to_val.values())
        vmin, vmax = min(vals), max(vals)
        vrange = vmax - vmin if vmax > vmin else 1.0

        # Build normalised [0,255] map per pixel
        val_map   = np.zeros((h, w), dtype=np.float32)
        valid_pix = np.zeros((h, w), dtype=bool)
        for lbl, val in lbl_to_val.items():
            mask = label_img == lbl
            val_map[mask]   = (val - vmin) / vrange
            valid_pix      |= mask

        norm_u8 = (val_map * 255).clip(0, 255).astype(np.uint8)
        colored = cv2.applyColorMap(norm_u8, cmap_id)
        colored[~valid_pix] = 0  # background stays black

        # Blend with background
        if img is not None:
            base = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if base.shape[:2] != (h, w):
                base = cv2.resize(base, (w, h))
            out = (base.astype(np.float32) * bg_alpha + colored.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)
        else:
            out = colored.copy()

        # Value labels at centroids
        if show_values:
            for r in regions:
                if not isinstance(r, dict) or feat_name not in r: continue
                cx = int(r.get('centroid_x', 0))
                cy = int(r.get('centroid_y', 0))
                val = r[feat_name]
                txt = f"{val:.1f}" if isinstance(val, float) else str(val)
                cv2.putText(out, txt, (cx - 12, cy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)

        # Colorbar
        if show_colorbar and h > 40:
            bar_w  = 12
            bar_h  = max(40, h - 30)
            bar_x  = w - bar_w - 8
            bar_y  = 12
            # gradient strip
            for y in range(bar_h):
                v     = int((1.0 - y / bar_h) * 255)
                color = cv2.applyColorMap(np.array([[v]], dtype=np.uint8), cmap_id)[0][0].tolist()
                cv2.rectangle(out, (bar_x, bar_y + y), (bar_x + bar_w, bar_y + y + 1), color, -1)
            cv2.rectangle(out, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (180, 180, 180), 1)
            # labels
            lbl_x = bar_x - 1
            cv2.putText(out, f"{vmax:.2g}", (lbl_x, bar_y + 9),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (240, 240, 240), 1, cv2.LINE_AA)
            cv2.putText(out, f"{vmin:.2g}", (lbl_x, bar_y + bar_h + 1),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (240, 240, 240), 1, cv2.LINE_AA)
            feat_label = feat_name[:8]
            cv2.putText(out, feat_label, (bar_x - 2, bar_y + bar_h + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.26, (180, 180, 180), 1, cv2.LINE_AA)

        return {'main': out, '_available_keys': available_keys}
