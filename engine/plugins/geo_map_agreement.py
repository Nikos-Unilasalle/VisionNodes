"""
geo_map_agreement.py — Spatial agreement between two classification maps

Compares a predicted classification map (RF output, WorldCover class values)
against an independent reference map (e.g. MapBiomas class values).

Both maps are remapped to a common 1-5 label space via user-defined mappings,
then compared pixel by pixel. Computes Cohen's kappa and per-class agreement
for independent accuracy assessment (Fig 6 in paper).

Default class mapping (Sinnamary use case):

  WorldCover → common:  10=1, 60=4, 80=2, 90=3, 95=5
  MapBiomas  → common:  3=1, 6=1, 11=3, 25=4, 30=4, 33=2, 41=5

  Common classes:  1=Forest, 2=Water, 3=Wetland, 4=Bare/Mining, 5=Mangrove

Typical use:
  geo_rf_classifier (classmap) + geo_mapbiomas (geotiff) → geo_map_agreement
"""
from __future__ import annotations
import io

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_map_agreement'

_MPL_DARK = {
    'figure.facecolor':  '#161616',
    'axes.facecolor':    '#1e1e1e',
    'axes.edgecolor':    '#555555',
    'axes.labelcolor':   '#cccccc',
    'text.color':        '#cccccc',
    'xtick.color':       '#aaaaaa',
    'ytick.color':       '#aaaaaa',
    'grid.color':        '#333333',
    'grid.linestyle':    '--',
    'grid.linewidth':    0.5,
}

# Defaults match the 4-class merged WorldCover model (95 = CoastalVeg = mangrove+wetland)
# compared against IO-LULC Annual v02 (Planetary Computer fallback when MapBiomas COGs 404).
# IO-LULC codes: 1=Water, 2=Trees, 4=FloodedVeg, 7=Built, 8=Bare, 11=Rangeland.
_DEFAULT_PRED_MAPPING  = '10=1,60=4,80=2,95=5'
_DEFAULT_REF_MAPPING   = '1=2,2=1,4=5,8=4,11=4'
_DEFAULT_COMMON_LABELS = '1=Forest,2=Water,4=Bare,5=CoastalVeg'

# BGR colors for agreement map
_AGREE_COLOR    = (50,  200,  50)   # green — agree
_DISAGREE_COLOR = (50,   50, 200)   # red   — disagree
_NODATA_COLOR   = (40,   40,  40)   # dark  — no data


def _parse_int_map(s: str) -> dict[int, int]:
    out: dict[int, int] = {}
    for item in s.split(','):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            try:
                out[int(k.strip())] = int(v.strip())
            except ValueError:
                pass
    return out


def _parse_label_map(s: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in s.split(','):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            try:
                out[int(k.strip())] = v.strip()
            except ValueError:
                pass
    return out


def _remap(arr: np.ndarray, mapping: dict[int, int]) -> np.ndarray:
    """Remap class values via lookup table. Unmapped values → 0 (no-data)."""
    out = np.zeros_like(arr, dtype=np.uint8)
    for src_val, dst_val in mapping.items():
        out[arr == src_val] = dst_val
    return out


def _reproject_ref_to_pred(
    ref_arr: np.ndarray,
    ref_geo: dict,
    pred_geo: dict,
) -> np.ndarray:
    """Reproject reference to predicted map grid (nearest neighbor for classes)."""
    import rasterio
    from rasterio.crs import CRS
    from rasterio.warp import reproject, Resampling

    pred_h   = int(pred_geo['height'])
    pred_w   = int(pred_geo['width'])
    pred_crs = CRS.from_user_input(pred_geo['crs'])
    pred_tf  = pred_geo['transform']

    ref_crs  = CRS.from_user_input(ref_geo['crs'])
    ref_tf   = ref_geo['transform']

    dst = np.zeros((pred_h, pred_w), dtype=ref_arr.dtype)
    reproject(
        source=ref_arr,
        destination=dst,
        src_transform=ref_tf,
        src_crs=ref_crs,
        dst_transform=pred_tf,
        dst_crs=pred_crs,
        resampling=Resampling.nearest,
    )
    return dst


def _cohen_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Cohen's kappa from two 1-D integer arrays."""
    classes = np.union1d(y_true, y_pred)
    n = len(y_true)
    if n == 0:
        return 0.0
    po = float(np.mean(y_true == y_pred))
    pe = 0.0
    for c in classes:
        p_true = float(np.mean(y_true == c))
        p_pred = float(np.mean(y_pred == c))
        pe += p_true * p_pred
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def _render_report(
    pred_common: np.ndarray,
    ref_common:  np.ndarray,
    label_map:   dict[int, str],
    kappa:       float,
    oa:          float,
    dpi:         int,
) -> np.ndarray | None:
    """Render Cohen's kappa + per-class agreement bar chart."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        common_classes = sorted(label_map)
        class_labels   = [label_map.get(c, str(c)) for c in common_classes]
        agreements     = []
        for c in common_classes:
            mask = ref_common == c
            if mask.sum() == 0:
                agreements.append(0.0)
            else:
                agreements.append(float(np.mean(pred_common[mask] == c)))

        # color bars by agreement level
        bar_colors = [
            '#2a7a2a' if a >= 0.85 else '#7a6a10' if a >= 0.70 else '#7a2a2a'
            for a in agreements
        ]

        with plt.rc_context(_MPL_DARK):
            fig, (ax_bar, ax_kappa) = plt.subplots(
                1, 2, figsize=(9, 3.5),
                gridspec_kw={'width_ratios': [3, 1]},
            )

            # ── Per-class agreement bar chart ───────────────────────────────
            y_pos = range(len(common_classes))
            bars  = ax_bar.barh(y_pos, agreements, color=bar_colors, edgecolor='#444')
            ax_bar.set_yticks(list(y_pos))
            ax_bar.set_yticklabels(class_labels, fontsize=9)
            ax_bar.set_xlim(0, 1.0)
            ax_bar.set_xlabel('Agreement (proportion)', fontsize=8)
            ax_bar.set_title(
                'Per-class agreement: RF (WorldCover classes) vs Reference (IO-LULC)',
                fontsize=8, pad=5,
            )
            ax_bar.axvline(0.85, color='#555', linestyle='--', linewidth=0.8)
            ax_bar.axvline(0.70, color='#444', linestyle=':', linewidth=0.8)
            for bar, val in zip(bars, agreements):
                ax_bar.text(
                    min(val + 0.02, 0.97), bar.get_y() + bar.get_height() / 2,
                    f'{val:.2f}', va='center', fontsize=8, color='#dddddd',
                )

            # ── Cohen's kappa + OA panel ────────────────────────────────────
            ax_kappa.axis('off')
            kappa_color = '#2a7a2a' if kappa >= 0.70 else '#7a6a10' if kappa >= 0.50 else '#7a2a2a'
            ax_kappa.text(
                0.5, 0.65, f'κ = {kappa:.3f}',
                ha='center', va='center', fontsize=22,
                color=kappa_color, fontweight='bold',
                transform=ax_kappa.transAxes,
            )
            ax_kappa.text(
                0.5, 0.40, f'OA = {oa:.1%}',
                ha='center', va='center', fontsize=13,
                color='#cccccc',
                transform=ax_kappa.transAxes,
            )
            ax_kappa.text(
                0.5, 0.18,
                'κ ≥ 0.85 ■  ≥ 0.70 ■  < 0.70 ■',
                ha='center', va='center', fontsize=6,
                color='#888888',
                transform=ax_kappa.transAxes,
            )
            ax_kappa.set_title('Cohen\'s κ\nvs Reference (IO-LULC)', fontsize=8, pad=5)

            fig.suptitle(
                f'Independent validation — RF (WorldCover-trained) vs Reference (IO-LULC)  '
                f'·  κ={kappa:.3f}  ·  OA={oa:.1%}',
                fontsize=9, y=1.01,
            )
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi,
                        facecolor='#161616')
            buf.seek(0)
            arr = np.frombuffer(buf.read(), dtype=np.uint8)
            buf.close()
            plt.close(fig)

        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img

    except Exception as e:
        print(f'[geo_map_agreement] render error: {e}', flush=True)
        return None


@vision_node(
    type_id='geo_map_agreement',
    label='Map Agreement',
    category='Machine Learning',
    icon='GitCompare',
    description=(
        'Compares two classification maps (predicted vs reference) remapped to a '
        'common label space. Computes Cohen\'s kappa and per-class spatial agreement '
        'for independent accuracy assessment. Designed for RF (WorldCover classes) '
        'vs Reference (IO-LULC) cross-validation. '
        'Outputs: agreement RGB map, kappa scalar, report figure (Fig 6).'
    ),
    inputs=[
        {'id': 'classmap',  'color': 'geotiff', 'label': 'Predicted classmap (RF output)'},
        {'id': 'reference', 'color': 'geotiff', 'label': 'Reference map (IO-LULC or MapBiomas)'},
    ],
    outputs=[
        {'id': 'agreement', 'color': 'image',  'label': 'Agreement map (green=agree, red=disagree)'},
        {'id': 'report',    'color': 'image',  'label': 'Fig 6 — kappa + per-class agreement'},
        {'id': 'kappa',     'color': 'scalar', 'label': 'Cohen\'s κ'},
        {'id': 'oa',        'color': 'scalar', 'label': 'Overall agreement'},
    ],
    params=[
        {
            'id': 'pred_mapping', 'type': 'string',
            'default': _DEFAULT_PRED_MAPPING,
            'label': 'Predicted map class → common (e.g. 95=5,80=2,…)',
        },
        {
            'id': 'ref_mapping', 'type': 'string',
            'default': _DEFAULT_REF_MAPPING,
            'label': 'Reference map class → common (e.g. 41=5,33=2,…)',
        },
        {
            'id': 'common_labels', 'type': 'string',
            'default': _DEFAULT_COMMON_LABELS,
            'label': 'Common class labels (e.g. 5=Mangrove,2=Water,…)',
        },
        {
            'id': 'dpi', 'type': 'int',
            'default': 110, 'min': 72, 'max': 300,
            'label': 'Output DPI',
        },
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GeoMapAgreementNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        pred_geo = inputs.get('classmap')
        ref_geo  = inputs.get('reference')

        if not isinstance(pred_geo, dict) or not isinstance(ref_geo, dict):
            send_notification(
                'Map Agreement: connect classmap (RF) + reference (LULC)',
                notif_id=_NOTIF,
            )
            return {}

        # ── Parse params ─────────────────────────────────────────────────────
        pred_map_str   = str(params.get('pred_mapping',   _DEFAULT_PRED_MAPPING)).strip()
        ref_map_str    = str(params.get('ref_mapping',    _DEFAULT_REF_MAPPING)).strip()
        common_lbl_str = str(params.get('common_labels',  _DEFAULT_COMMON_LABELS)).strip()
        dpi            = max(72, int(params.get('dpi', 110)))

        pred_mapping   = _parse_int_map(pred_map_str)
        ref_mapping    = _parse_int_map(ref_map_str)
        label_map      = _parse_label_map(common_lbl_str)

        if not pred_mapping or not ref_mapping:
            send_notification(
                'Map Agreement: invalid class mapping params',
                level='error', notif_id=_NOTIF,
            )
            return {}

        # ── Extract arrays ───────────────────────────────────────────────────
        pred_bands = pred_geo.get('bands')
        ref_bands  = ref_geo.get('bands')

        if pred_bands is None or ref_bands is None:
            send_notification('Map Agreement: missing bands in geo dict',
                              level='error', notif_id=_NOTIF)
            return {}

        pred_arr = pred_bands[0] if pred_bands.ndim == 3 else pred_bands
        ref_arr  = ref_bands[0]  if ref_bands.ndim  == 3 else ref_bands

        # ── Reproject reference onto predicted grid ──────────────────────────
        try:
            ref_reproj = _reproject_ref_to_pred(ref_arr, ref_geo, pred_geo)
        except Exception as e:
            send_notification(
                f'Map Agreement: reproject failed: {e}',
                level='error', notif_id=_NOTIF,
            )
            return {}

        # ── Remap both to common label space ─────────────────────────────────
        pred_common = _remap(pred_arr,   pred_mapping)
        ref_common  = _remap(ref_reproj, ref_mapping)

        # ── Mask: only pixels where BOTH maps have valid (non-zero) class ────
        valid_mask = (pred_common > 0) & (ref_common > 0)
        n_valid    = int(valid_mask.sum())

        if n_valid < 100:
            send_notification(
                f'Map Agreement: only {n_valid} overlapping valid pixels — '
                'check bbox and class mappings',
                level='error', notif_id=_NOTIF,
            )
            return {}

        y_pred = pred_common[valid_mask].astype(np.int32)
        y_ref  = ref_common[valid_mask].astype(np.int32)

        # ── Metrics ──────────────────────────────────────────────────────────
        kappa = _cohen_kappa(y_ref, y_pred)
        oa    = float(np.mean(y_pred == y_ref))

        # ── Agreement map ────────────────────────────────────────────────────
        h, w       = pred_arr.shape
        agr_img    = np.full((h, w, 3), _NODATA_COLOR, dtype=np.uint8)
        agree_mask = valid_mask & (pred_common == ref_common)
        diff_mask  = valid_mask & (pred_common != ref_common)
        agr_img[agree_mask] = _AGREE_COLOR
        agr_img[diff_mask]  = _DISAGREE_COLOR

        # ── Report figure ────────────────────────────────────────────────────
        report_img = _render_report(pred_common, ref_common, label_map, kappa, oa, dpi)

        send_notification(
            f'Map Agreement: κ={kappa:.3f}  OA={oa:.1%}  valid_px={n_valid:,}',
            progress=1.0, notif_id=_NOTIF,
        )

        result: dict = {
            'agreement': agr_img,
            'kappa':     kappa,
            'oa':        oa,
        }
        if report_img is not None:
            result['report'] = report_img

        return result
