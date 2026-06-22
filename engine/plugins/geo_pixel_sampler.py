"""
geo_pixel_sampler.py — Sample pixels from a multi-band raster by class label raster.

Unlike geo_ground_truth_sampler (which needs a CSV with lat/lon),
this node works purely raster-to-raster: it randomly samples N pixels
per class from a label raster (e.g. ESA WorldCover, io-lulc, or the
output of geo_rf_classifier) and returns a labeled DataFrame.

Output `table` feeds directly into ml_scatter_plot, ml_histogram,
ml_corr_heatmap, or any DataFrame-based ML node.

Typical use:
  features (9-band S1+S2 stack) + labels (WorldCover) →
  geo_pixel_sampler → ml_scatter_plot (x=NDVI, y=MNDWI, hue=class)
  → feature-space separability figure for the paper.
"""
from __future__ import annotations
import hashlib
import json as _json
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_px_sampler'


def _info_panel(lines: list[str], w: int = 460, h: int = 200,
                title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (40, 40, 40), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX,
                0.44, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 15
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:72], (8, 44 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
    return img


def _reproject_nearest(feat_geo: dict, lbl_geo: dict) -> np.ndarray:
    """Reproject label raster onto features grid (nearest-neighbor). Returns 2D int32."""
    try:
        import rasterio
        from rasterio.warp import reproject, Resampling

        feat_b = feat_geo['bands']
        _, fH, fW = feat_b.shape if feat_b.ndim == 3 else (1, *feat_b.shape)

        lbl_b = lbl_geo['bands']
        lbl_2d = lbl_b[0] if lbl_b.ndim == 3 else lbl_b

        feat_crs  = feat_geo.get('crs');   lbl_crs  = lbl_geo.get('crs')
        feat_tf   = feat_geo.get('transform'); lbl_tf = lbl_geo.get('transform')

        if all(v is not None for v in (feat_crs, lbl_crs, feat_tf, lbl_tf)):
            out = np.zeros((fH, fW), dtype=lbl_2d.dtype)
            reproject(
                source=lbl_2d,
                destination=out,
                src_transform=lbl_tf,  src_crs=lbl_crs,
                dst_transform=feat_tf, dst_crs=feat_crs,
                resampling=Resampling.nearest,
            )
            return out
    except Exception:
        pass

    # Fallback: OpenCV resize
    feat_b = feat_geo['bands']
    _, fH, fW = feat_b.shape if feat_b.ndim == 3 else (1, *feat_b.shape)
    lbl_b = lbl_geo['bands']
    lbl_2d = lbl_b[0] if lbl_b.ndim == 3 else lbl_b
    return cv2.resize(lbl_2d.astype(np.float32), (fW, fH),
                      interpolation=cv2.INTER_NEAREST).astype(np.int32)


@vision_node(
    type_id='geo_pixel_sampler',
    label='Pixel Sampler (by class)',
    category='geography',
    icon='Grid',
    description=(
        "Randomly sample pixels from a multi-band feature raster, stratified by a "
        "categorical label raster. Outputs a labeled DataFrame with one row per "
        "sampled pixel and one column per band (named by band_names) plus a 'class' "
        "column. Connect to ml_scatter_plot (set hue='class') for feature-space "
        "separability figures. No CSV required — purely raster-to-raster."
    ),
    inputs=[
        {'id': 'features', 'color': 'geotiff', 'label': 'Feature stack (multi-band)'},
        {'id': 'labels',   'color': 'geotiff', 'label': 'Label raster (categorical)'},
    ],
    outputs=[
        {'id': 'table',    'color': 'data',   'label': 'Labeled DataFrame'},
        {'id': 'preview',  'color': 'image',  'label': 'Sample counts'},
        {'id': 'n_samples','color': 'scalar', 'label': 'Total samples'},
    ],
    params=[
        {'id': '_sec_data', 'label': 'Data', 'type': 'section'},
        {'id': 'band_names', 'type': 'string', 'default': '',
         'label': 'Band names (comma-sep, in stack order)'},
        {'id': 'include_classes', 'type': 'string', 'default': '',
         'label': 'Classes to include (comma-sep, empty = all non-zero)'},
        {'id': 'class_labels', 'type': 'string', 'default': '',
         'label': 'Class labels (e.g. "10=Trees,60=Bare,95=Mangroves")'},
        {'id': '_sec_sampling', 'label': 'Sampling', 'type': 'section'},
        {'id': 'max_samples_per_class', 'type': 'int', 'default': 2000,
         'min': 50, 'max': 50000, 'label': 'Max samples per class'},
        {'id': 'seed', 'type': 'int', 'default': 42, 'min': 0, 'max': 9999,
         'label': 'Random seed'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=280, min_height=160,
)
class GeoPixelSamplerNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._cache_key: str | None = None
        self._cache_out: dict | None = None

    def process(self, inputs: dict, params: dict) -> dict:
        feat_geo = inputs.get('features')
        lbl_geo  = inputs.get('labels')

        if not isinstance(feat_geo, dict) or 'bands' not in feat_geo:
            send_notification('Pixel Sampler: waiting for feature stack', notif_id=_NOTIF)
            return {}
        if not isinstance(lbl_geo, dict) or 'bands' not in lbl_geo:
            send_notification('Pixel Sampler: waiting for label raster', notif_id=_NOTIF)
            return {}

        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        feat_b = feat_geo['bands']
        if feat_b.ndim == 2:
            feat_b = feat_b[np.newaxis]
        C, H, W = feat_b.shape

        # Cache key
        _key = hashlib.md5((
            f'{feat_b.shape}:{id(feat_b)}:{lbl_geo["bands"].shape}:{id(lbl_geo["bands"])}'
            + _json.dumps(params, sort_keys=True)
        ).encode()).hexdigest()
        if _key == self._cache_key and self._cache_out is not None:
            return self._cache_out

        # Parse params
        band_names_raw = str(params.get('band_names', '')).strip()
        include_str    = str(params.get('include_classes', '')).strip()
        labels_str     = str(params.get('class_labels', '')).strip()
        max_spc        = max(50, int(params.get('max_samples_per_class', 2000)))
        seed           = int(params.get('seed', 42))
        rng            = np.random.default_rng(seed)

        band_names = [n.strip() for n in band_names_raw.split(',') if n.strip()]
        band_names = (band_names + [f'band_{i+1}' for i in range(len(band_names), C)])[:C]

        # Parse class label map: "10=Trees,60=Bare" → {10: "Trees", 60: "Bare"}
        label_map: dict[int, str] = {}
        for item in labels_str.split(','):
            item = item.strip()
            if '=' in item:
                k, v = item.split('=', 1)
                try:
                    label_map[int(k.strip())] = v.strip()
                except ValueError:
                    pass

        # Reproject labels
        send_notification('Pixel Sampler: aligning rasters…', progress=0.2, notif_id=_NOTIF)
        label_2d = _reproject_nearest(feat_geo, lbl_geo).astype(np.int32)
        label_flat = label_2d.ravel()

        # Determine classes
        if include_str:
            include_classes = [int(v.strip()) for v in include_str.split(',') if v.strip()]
        else:
            include_classes = [int(v) for v in np.unique(label_flat) if v != 0]

        if not include_classes:
            send_notification('Pixel Sampler: no valid classes found', level='error', notif_id=_NOTIF)
            return {}

        # Sample pixels per class
        send_notification(
            f'Pixel Sampler: sampling {len(include_classes)} classes…',
            progress=0.4, notif_id=_NOTIF,
        )
        X_all = feat_b.reshape(C, -1).T.astype(np.float32)  # (H*W, C)
        rows_list: list[np.ndarray] = []
        lbls_list: list[np.ndarray] = []

        class_counts: list[tuple[int, str, int]] = []

        for cls in include_classes:
            idx = np.where(label_flat == cls)[0]
            if len(idx) == 0:
                continue
            if len(idx) > max_spc:
                idx = rng.choice(idx, max_spc, replace=False)
            X_c = X_all[idx]
            valid = np.isfinite(X_c).all(axis=1)
            X_c = X_c[valid]
            if len(X_c) == 0:
                continue
            rows_list.append(X_c)
            cls_label = label_map.get(cls, str(cls))
            lbls_list.append(np.full(len(X_c), cls_label))
            class_counts.append((cls, cls_label, len(X_c)))

        if not rows_list:
            send_notification('Pixel Sampler: 0 valid samples', level='error', notif_id=_NOTIF)
            return {}

        X_mat = np.vstack(rows_list)
        y_arr = np.concatenate(lbls_list)
        df = pd.DataFrame(X_mat, columns=band_names)
        df['class'] = y_arr
        n_total = len(df)

        # Preview panel
        lines = [
            f'Total: {n_total:,} samples  ·  {len(class_counts)} classes  ·  {C} bands',
            *[f'  class {cls} ({lbl}): {cnt:,} px' for cls, lbl, cnt in class_counts[:10]],
        ]
        preview = _info_panel(lines, w=480, h=max(160, len(class_counts) * 16 + 60),
                              title='Pixel Sampler')

        send_notification(
            f'Pixel Sampler: {n_total:,} samples — {len(class_counts)} classes — '
            f'{C} bands. Connect → ml_scatter_plot (hue=class).',
            progress=1.0, notif_id=_NOTIF,
        )

        result = {'table': df, 'preview': preview, 'n_samples': float(n_total)}
        self._cache_key = _key
        self._cache_out = result
        return result
