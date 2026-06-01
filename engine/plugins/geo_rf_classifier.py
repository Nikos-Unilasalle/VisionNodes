"""
geo_rf_classifier.py — Random Forest pixel classifier on geo dicts.

Trains a Random Forest from a multi-band feature stack (geo dict)
and a single-band label raster (geo dict).  Predicts every pixel in
the feature stack and outputs a classified geo dict + confidence map.

Typical use-case: Sinnamary mangrove mapping
  features  ← geo_band_stack (S1 pol + S2 spectral indices, 9 bands)
  labels    ← geo_copernicus  (ESA WorldCover 2021, class 95 = Mangroves)

The label raster is reprojected onto the features grid (nearest-neighbor)
if the two grids differ.  A stratified random sample (max_samples_per_class)
is used for training to avoid class imbalance.
"""
from __future__ import annotations
import hashlib
import json as _json
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_rf'

# ── WorldCover class palette (class_value → BGR) ──────────────────────────────
_WC_PALETTE: dict[int, tuple[int, int, int]] = {
    10:  (34,  139, 34),    # Tree cover          — green
    20:  (154, 205, 50),    # Shrubland           — yellow-green
    30:  (255, 255, 153),   # Grassland           — pale yellow
    40:  (255, 200, 100),   # Cropland            — orange-yellow
    50:  (200, 100, 50),    # Built-up            — brown-orange
    60:  (210, 180, 140),   # Bare/sparse         — tan
    70:  (240, 250, 255),   # Snow/ice            — near-white
    80:  (30,  144, 255),   # Permanent water     — dodger blue
    90:  (70,  200, 200),   # Herbaceous wetland  — teal
    95:  (0,   100, 0),     # Mangroves           — dark green
    100: (200, 200, 200),   # Moss/lichen         — gray
}
_DEFAULT_PALETTE = (128, 128, 128)   # BGR for unknown classes


def _class_color(val: int) -> tuple[int, int, int]:
    return _WC_PALETTE.get(int(val), _DEFAULT_PALETTE)


def _colorize_map(class_map: np.ndarray, unique_classes: list[int]) -> np.ndarray:
    """RGB visualization of classification map (H, W) → (H, W, 3)."""
    h, w = class_map.shape
    rgb = np.full((h, w, 3), 128, dtype=np.uint8)
    for cls in unique_classes:
        b, g, r = _class_color(cls)
        mask = class_map == cls
        rgb[mask] = [r, g, b]
    return rgb


def _importance_chart(importances: np.ndarray, names: list[str],
                       w: int = 500, h: int = 280) -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (40, 40, 40), -1)
    cv2.putText(img, 'Feature importance (Gini)', (8, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)

    order = np.argsort(importances)[::-1]
    n = min(len(order), (h - 44) // 20)
    max_imp = float(importances[order[0]]) or 1.0
    bar_max_w = w - 180

    for i, idx in enumerate(order[:n]):
        imp = float(importances[idx])
        bar_w = max(2, int(imp / max_imp * bar_max_w))
        y = 38 + i * 20
        # gradient bar: blue→green
        t = imp / max_imp
        r_c = int(59  + t * (34 - 59))
        g_c = int(130 + t * (197 - 130))
        b_c = int(246 + t * (94 - 246))
        cv2.rectangle(img, (160, y), (160 + bar_w, y + 14), (b_c, g_c, r_c), -1)
        feat_label = (names[idx] if idx < len(names) else f'band_{idx}')[:22]
        cv2.putText(img, feat_label, (4, y + 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 180, 180), 1, cv2.LINE_AA)
        cv2.putText(img, f'{imp:.3f}', (162 + bar_w + 4, y + 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (150, 200, 150), 1, cv2.LINE_AA)
    return img


def _confusion_plot(cm_norm: np.ndarray, labels: list[str]) -> np.ndarray:
    """Render pre-normalized confusion matrix (recall on diagonal) as BGR image."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        n = len(labels)
        fig_size = max(4.0, n * 0.9)
        fig, ax = plt.subplots(figsize=(fig_size + 1, fig_size))
        fig.patch.set_facecolor('#161616')
        ax.set_facecolor('#1e1e1e')

        im = ax.imshow(cm_norm, interpolation='nearest', cmap='Blues', vmin=0, vmax=1)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set(
            xticks=range(n), yticks=range(n),
            xticklabels=labels, yticklabels=labels,
            ylabel='True label', xlabel='Predicted label',
        )
        ax.set_title('Confusion matrix (normalized — recall on diagonal)',
                     fontsize=9, color='#cccccc', pad=6)
        ax.tick_params(colors='#aaaaaa', labelsize=7)
        ax.xaxis.label.set_color('#cccccc')
        ax.yaxis.label.set_color('#cccccc')
        for spine in ax.spines.values():
            spine.set_edgecolor('#555555')
        plt.setp(ax.get_xticklabels(), rotation=40, ha='right',
                 rotation_mode='anchor', fontsize=7)

        thresh = 0.5
        for i in range(n):
            for j in range(n):
                ax.text(j, i, f'{cm_norm[i, j]:.2f}',
                        ha='center', va='center', fontsize=8,
                        color='white' if cm_norm[i, j] > thresh else '#333333',
                        fontweight='bold' if i == j else 'normal')

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=100,
                    facecolor='#161616')
        buf.seek(0)
        arr = np.frombuffer(buf.read(), dtype=np.uint8)
        buf.close()
        plt.close(fig)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img if img is not None else np.full((300, 400, 3), 22, dtype=np.uint8)
    except Exception as e:
        fallback = np.full((300, 400, 3), 22, dtype=np.uint8)
        cv2.putText(fallback, f'CM error: {e}'[:60],
                    (8, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 100, 100), 1)
        return fallback


def _info_panel(lines: list[str], w: int = 500, h: int = 200,
                title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (40, 40, 40), -1)
    cv2.putText(img, title, (8, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 16
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:80], (8, 44 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
    return img


def _reproject_labels_onto(feat_geo: dict, lbl_geo: dict) -> np.ndarray:
    """Reproject single-band label raster onto features grid (nearest-neighbor)."""
    try:
        import rasterio
        from rasterio.warp import reproject, Resampling

        feat_bands = feat_geo['bands']
        _, fH, fW = feat_bands.shape if feat_bands.ndim == 3 else (1, *feat_bands.shape)

        lbl_bands = lbl_geo['bands']
        if lbl_bands.ndim == 3:
            lbl_2d = lbl_bands[0]
        else:
            lbl_2d = lbl_bands

        feat_crs = feat_geo.get('crs')
        lbl_crs  = lbl_geo.get('crs')
        feat_transform = feat_geo.get('transform')
        lbl_transform  = lbl_geo.get('transform')

        if feat_crs is None or lbl_crs is None or feat_transform is None or lbl_transform is None:
            # Fallback: resize via OpenCV if missing CRS
            return cv2.resize(lbl_2d.astype(np.float32), (fW, fH),
                              interpolation=cv2.INTER_NEAREST).astype(lbl_2d.dtype)

        out = np.zeros((fH, fW), dtype=lbl_2d.dtype)
        reproject(
            source=lbl_2d,
            destination=out,
            src_transform=lbl_transform,
            src_crs=lbl_crs,
            dst_transform=feat_transform,
            dst_crs=feat_crs,
            resampling=Resampling.nearest,
        )
        return out
    except Exception as e:
        send_notification(f'RF Classifier: label reproject error: {e}',
                          level='warning', notif_id=_NOTIF)
        # crude fallback
        lbl_bands = lbl_geo['bands']
        lbl_2d = lbl_bands[0] if lbl_bands.ndim == 3 else lbl_bands
        feat_bands = feat_geo['bands']
        _, fH, fW = feat_bands.shape if feat_bands.ndim == 3 else (1, *feat_bands.shape)
        return cv2.resize(lbl_2d.astype(np.float32), (fW, fH),
                          interpolation=cv2.INTER_NEAREST).astype(lbl_2d.dtype)


def _spatial_block_split(
    indices: np.ndarray,
    rows: np.ndarray,
    cols: np.ndarray,
    H: int,
    W: int,
    block_size: int,
    test_frac: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Split sample indices into train/test by spatial blocks.

    Assigns each pixel to a (block_row, block_col) grid cell, then randomly
    assigns ~test_frac of blocks to the test set.  Ensures no pixel in the
    test set is spatially adjacent to a training pixel within the same block.

    Returns train_indices, test_indices (both 1-D int arrays).
    """
    n_bh = max(1, H // block_size)
    n_bw = max(1, W // block_size)

    block_row = np.minimum(rows // block_size, n_bh - 1)
    block_col = np.minimum(cols // block_size, n_bw - 1)
    block_id  = block_row * n_bw + block_col   # unique block int per sample

    unique_blocks = np.unique(block_id)
    n_test = max(1, int(round(len(unique_blocks) * test_frac)))

    perm = rng.permutation(len(unique_blocks))
    test_block_set = set(unique_blocks[perm[:n_test]].tolist())

    is_test  = np.array([b in test_block_set for b in block_id.tolist()], dtype=bool)
    return indices[~is_test], indices[is_test]


_CMAPS = ['tab10', 'viridis', 'plasma', 'Set1', 'RdYlGn']


@vision_node(
    type_id='geo_rf_classifier',
    label='RF Pixel Classifier',
    category='geography',
    icon='Layers',
    description=(
        "Random Forest pixel-by-pixel classifier. "
        "Trains on a multi-band feature stack (geo dict) using a categorical "
        "label raster (geo dict, e.g. ESA WorldCover or io-lulc) as ground truth. "
        "Outputs a classified geo dict, per-pixel confidence map, "
        "feature importance chart, and accuracy metrics. "
        "Label raster is reprojected onto features grid automatically (nearest-neighbor). "
        "Stratified sampling per class avoids imbalance."
    ),
    inputs=[
        {'id': 'features', 'color': 'geotiff', 'label': 'Feature stack (multi-band)'},
        {'id': 'labels',   'color': 'geotiff', 'label': 'Label raster (categorical)'},
    ],
    outputs=[
        {'id': 'classification', 'color': 'geotiff', 'label': 'Classification map'},
        {'id': 'preview',        'color': 'image',   'label': 'Classification RGB'},
        {'id': 'confidence',     'color': 'image',   'label': 'Confidence map'},
        {'id': 'importance',     'color': 'image',   'label': 'Feature importance'},
        {'id': 'accuracy',       'color': 'scalar',  'label': 'Test accuracy (OOB)'},
        {'id': 'n_samples',      'color': 'scalar',  'label': 'Training samples'},
        {'id': 'report',         'color': 'image',   'label': 'Confusion matrix (normalized)'},
        {'id': 'report_data',    'color': 'dict',    'label': 'Classification report (dict)'},
        {'id': 'conf_matrix',    'color': 'data',    'label': 'Confusion matrix data (for ml_classification_report)'},
        {'id': 'model',          'color': 'dict',    'label': 'Trained model bundle (for geo_rf_predict)'},
    ],
    params=[
        {'id': 'band_names', 'type': 'string', 'default': '',
         'label': 'Band names (comma-separated, in stack order)'},
        {'id': 'include_classes', 'type': 'string', 'default': '',
         'label': 'Classes to include (comma-sep values, empty = all non-zero)'},
        {'id': 'class_merge', 'type': 'string', 'default': '',
         'label': 'Class merge before training (e.g. "90=95" merges Wetland into Mangroves)'},
        {'id': 'class_max_samples', 'type': 'string', 'default': '',
         'label': 'Per-class sample override (e.g. "95=15000,60=8000"; falls back to max_samples_per_class)'},
        {'id': 'n_estimators', 'type': 'int', 'default': 100, 'min': 10, 'max': 500,
         'label': 'Number of trees'},
        {'id': 'max_depth', 'type': 'int', 'default': 0, 'min': 0, 'max': 30,
         'label': 'Max depth (0 = unlimited)'},
        {'id': 'max_samples_per_class', 'type': 'int', 'default': 5000, 'min': 100, 'max': 50000,
         'label': 'Max samples per class (global default)'},
        {'id': 'test_fraction', 'type': 'float', 'default': 0.2, 'min': 0.05, 'max': 0.5,
         'label': 'Test fraction (0.2 = 20% held-out)'},
        {'id': 'split_mode', 'type': 'enum', 'default': 1,
         'options': ['Random pixels (biased)', 'Spatial blocks (recommended)'],
         'label': 'Train/test split strategy'},
        {'id': 'block_size_px', 'type': 'int', 'default': 50, 'min': 10, 'max': 500,
         'label': 'Spatial block size (pixels) — for spatial split only'},
        {'id': 'node_note', 'type': 'string', 'default': '',
         'label': 'Note'},
        {'id': 'cache_dir', 'type': 'string', 'default': 'copernicus_cache',
         'label': 'Cache dir'},
    ],
    resizable=True, min_width=320, min_height=220,
)
class GeoRFClassifierNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._cache_key: str | None = None
        self._cache_out: dict | None = None

    def process(self, inputs: dict, params: dict) -> dict:
        if not self.ensure_packages(
            ['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF
        ):
            return {}

        feat_geo = inputs.get('features')
        lbl_geo  = inputs.get('labels')

        if not isinstance(feat_geo, dict) or 'bands' not in feat_geo:
            send_notification('RF Classifier: waiting for feature stack (geo dict)',
                              notif_id=_NOTIF)
            return {}
        if not isinstance(lbl_geo, dict) or 'bands' not in lbl_geo:
            send_notification('RF Classifier: waiting for label raster (geo dict)',
                              notif_id=_NOTIF)
            return {}

        # ── Cache keying ──────────────────────────────────────────────────────
        feat_bands = feat_geo['bands']
        lbl_bands  = lbl_geo['bands']
        _fkey = f'{feat_bands.shape}:{id(feat_bands)}'
        _lkey = f'{lbl_bands.shape}:{id(lbl_bands)}'
        _pkey = _json.dumps(params, sort_keys=True)
        _key  = hashlib.md5((_fkey + _lkey + _pkey).encode()).hexdigest()
        if _key == self._cache_key and self._cache_out is not None:
            return self._cache_out

        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder

        # ── Parse params ──────────────────────────────────────────────────────
        band_names_raw = str(params.get('band_names', '')).strip()
        include_str    = str(params.get('include_classes', '')).strip()
        n_estimators   = max(10, int(params.get('n_estimators', 100)))
        max_depth_raw  = int(params.get('max_depth', 0))
        max_depth      = max_depth_raw if max_depth_raw > 0 else None
        max_spc          = max(100, int(params.get('max_samples_per_class', 5000)))
        test_frac        = float(params.get('test_fraction', 0.2))
        split_mode       = int(params.get('split_mode', 1))
        block_size_px    = max(10, int(params.get('block_size_px', 50)))

        # ── Parse class_merge: "90=95,91=95" → {90: 95, 91: 95} ─────────────
        merge_map: dict[int, int] = {}
        merge_str = str(params.get('class_merge', '')).strip()
        for item in merge_str.split(','):
            item = item.strip()
            if '=' in item:
                try:
                    src, dst = item.split('=', 1)
                    merge_map[int(src.strip())] = int(dst.strip())
                except ValueError:
                    pass

        # ── Parse class_max_samples: "95=15000,60=8000" → {95: 15000, …} ────
        cls_max: dict[int, int] = {}
        cms_str = str(params.get('class_max_samples', '')).strip()
        for item in cms_str.split(','):
            item = item.strip()
            if '=' in item:
                try:
                    cls, cap = item.split('=', 1)
                    cls_max[int(cls.strip())] = max(100, int(cap.strip()))
                except ValueError:
                    pass

        # ── Feature array (C, H, W) → (H*W, C) ──────────────────────────────
        if feat_bands.ndim == 2:
            feat_bands = feat_bands[np.newaxis]
        C, fH, fW = feat_bands.shape

        band_names = [n.strip() for n in band_names_raw.split(',') if n.strip()]
        band_names = (band_names + [f'band_{i+1}' for i in range(len(band_names), C)])[:C]

        send_notification(f'RF Classifier: feature stack {C} bands, {fH}×{fW}…',
                          progress=0.1, notif_id=_NOTIF)

        # ── Reproject label raster onto features grid ─────────────────────────
        send_notification('RF Classifier: aligning label raster…',
                          progress=0.2, notif_id=_NOTIF)
        label_2d = _reproject_labels_onto(feat_geo, lbl_geo)  # (fH, fW)
        label_flat = label_2d.ravel().astype(np.int32)

        # ── Apply class merge (modifies label_flat in-place) ─────────────────
        if merge_map:
            for src_cls, dst_cls in merge_map.items():
                label_flat[label_flat == src_cls] = dst_cls
            merged_summary = ', '.join(f'{s}→{d}' for s, d in merge_map.items())
            send_notification(
                f'RF Classifier: class merge applied: {merged_summary}',
                progress=0.22, notif_id=_NOTIF,
            )

        # ── Determine which classes to use ────────────────────────────────────
        if include_str:
            include_classes: list[int] = [int(v.strip()) for v in include_str.split(',') if v.strip()]
        else:
            # all non-zero classes (0 = nodata)
            include_classes = [int(v) for v in np.unique(label_flat) if v != 0]

        if len(include_classes) < 2:
            send_notification(
                f'RF Classifier: need ≥ 2 classes. Found: {include_classes}. '
                f'Check label raster or "include_classes" param.',
                level='error', notif_id=_NOTIF,
            )
            return {}

        send_notification(
            f'RF Classifier: {len(include_classes)} classes → {include_classes[:8]}…',
            progress=0.25, notif_id=_NOTIF,
        )

        # ── Feature matrix (H*W, C) ───────────────────────────────────────────
        X_all = feat_bands.reshape(C, -1).T.astype(np.float32)  # (H*W, C)

        # ── Stratified sampling ───────────────────────────────────────────────
        sample_indices: list[np.ndarray] = []
        sample_labels:  list[np.ndarray] = []
        for cls in include_classes:
            idx = np.where(label_flat == cls)[0]
            if len(idx) == 0:
                continue
            cap = cls_max.get(cls, max_spc)   # per-class override or global default
            if len(idx) > cap:
                idx = np.random.choice(idx, cap, replace=False)
            sample_indices.append(idx)
            sample_labels.append(np.full(len(idx), cls, dtype=np.int32))

        if not sample_indices:
            send_notification('RF Classifier: 0 valid samples after class filtering',
                              level='error', notif_id=_NOTIF)
            return {}

        all_idx = np.concatenate(sample_indices)
        all_lbl = np.concatenate(sample_labels)
        n_total = len(all_idx)

        # Filter NaN / Inf in features — keep flat pixel indices for spatial split
        X_s = X_all[all_idx]
        valid_mask = np.isfinite(X_s).all(axis=1)
        X_s         = X_s[valid_mask]
        all_lbl     = all_lbl[valid_mask]
        all_idx_valid = all_idx[valid_mask]   # flat pixel indices after NaN filter
        n_valid = len(X_s)

        if n_valid < 20:
            send_notification(f'RF Classifier: only {n_valid} valid samples (NaN in features?)',
                              level='error', notif_id=_NOTIF)
            return {}

        send_notification(
            f'RF Classifier: {n_valid} training samples ({n_total} raw) — training…',
            progress=0.35, notif_id=_NOTIF,
        )

        # ── Train/test split + fit ────────────────────────────────────────────
        le = LabelEncoder()
        y_enc = le.fit_transform(all_lbl)
        classes_encoded = le.classes_   # original class values

        rng = np.random.default_rng(42)

        if split_mode == 1:
            # Spatial block split — avoids spatial autocorrelation bias
            # Recover (row, col) of each sampled pixel from its flat index
            sample_rows  = all_idx_valid // fW
            sample_cols  = all_idx_valid  % fW
            arange       = np.arange(len(X_s))
            tr_sel, te_sel = _spatial_block_split(
                arange, sample_rows, sample_cols,
                fH, fW, block_size_px, test_frac, rng,
            )
            X_tr, X_te = X_s[tr_sel], X_s[te_sel]
            y_tr, y_te = y_enc[tr_sel], y_enc[te_sel]
            split_label = f'spatial blocks ({block_size_px}px)'
        else:
            # Random pixel split (biased — spatial autocorrelation not removed)
            X_tr, X_te, y_tr, y_te = train_test_split(
                X_s, y_enc,
                test_size=max(0.05, min(test_frac, 0.5)),
                random_state=42,
                stratify=y_enc,
            )
            split_label = 'random pixels'

        send_notification(
            f'RF Classifier: split={split_label}  train={len(X_tr):,}  test={len(X_te):,}',
            progress=0.38, notif_id=_NOTIF,
        )

        rf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            n_jobs=-1,
            random_state=42,
            class_weight='balanced',
        )
        rf.fit(X_tr, y_tr)

        test_acc = float(rf.score(X_te, y_te))
        send_notification(
            f'RF Classifier: test accuracy = {test_acc:.1%} ({n_estimators} trees)',
            progress=0.7, notif_id=_NOTIF,
        )

        # ── Confusion matrix + classification report ──────────────────────────
        from sklearn.metrics import classification_report, confusion_matrix as sk_cm

        y_te_pred  = rf.predict(X_te)
        class_strs = [str(int(c)) for c in classes_encoded]

        # Normalized confusion matrix (row-norm = recall on diagonal).
        # Pass explicit labels so matrix is always n×n even when a class is absent from
        # the test split (otherwise sk_cm produces a smaller matrix → index error).
        all_encoded_labels = list(range(len(classes_encoded)))
        cm_int  = sk_cm(y_te, y_te_pred, labels=all_encoded_labels)
        row_sum = cm_int.sum(axis=1, keepdims=True)
        cm_norm = cm_int.astype(float) / np.where(row_sum == 0, 1, row_sum)

        conf_matrix_data = {
            'matrix':           cm_int,
            'normalized':       cm_norm,
            'labels':           class_strs,
            'original_classes': [int(c) for c in classes_encoded],
        }
        report_img = _confusion_plot(cm_norm, class_strs)

        report_dict: dict = classification_report(
            y_te, y_te_pred,
            labels=list(range(len(classes_encoded))),
            target_names=class_strs,
            output_dict=True,
            zero_division=0,
        )
        # Map encoded labels back to original class values in dict keys
        report_data: dict = {}
        for k, v in report_dict.items():
            if k in class_strs:
                original_val = int(classes_encoded[class_strs.index(k)])
                report_data[str(original_val)] = v
            else:
                report_data[k] = v

        # ── Predict all pixels ────────────────────────────────────────────────
        send_notification('RF Classifier: predicting all pixels…',
                          progress=0.75, notif_id=_NOTIF)
        CHUNK = 500_000
        n_pix = fH * fW
        pred_enc  = np.zeros(n_pix, dtype=np.int32)
        conf_flat = np.zeros(n_pix, dtype=np.float32)

        for start in range(0, n_pix, CHUNK):
            end  = min(start + CHUNK, n_pix)
            chunk = X_all[start:end]
            # Replace NaN with 0 for prediction
            chunk = np.where(np.isfinite(chunk), chunk, 0.0)
            proba = rf.predict_proba(chunk)
            pred_enc[start:end]  = rf.predict(chunk)
            conf_flat[start:end] = proba.max(axis=1)

        # Decode predicted class values back to original labels
        pred_classes = le.inverse_transform(pred_enc)
        class_map = pred_classes.reshape(fH, fW).astype(np.int32)
        conf_map  = conf_flat.reshape(fH, fW)

        # ── Visualize ─────────────────────────────────────────────────────────
        preview = _colorize_map(class_map, list(classes_encoded))

        # Confidence map as blue→green gradient (uint8)
        conf_u8 = (conf_map * 255).clip(0, 255).astype(np.uint8)
        conf_bgr = cv2.applyColorMap(conf_u8, cv2.COLORMAP_TURBO)

        # Importance chart
        importance_img = _importance_chart(rf.feature_importances_, band_names,
                                           w=500, h=max(200, C * 22 + 50))

        # Build class distribution summary
        cls_counts = [(int(cls), int((class_map == cls).sum()))
                      for cls in classes_encoded]
        cls_counts.sort(key=lambda x: x[1], reverse=True)

        lines = [
            f'Test accuracy: {test_acc:.1%}',
            f'Training: {n_valid:,} samples  ({n_estimators} trees)',
            f'Classes: {len(classes_encoded)}  —  {list(map(int, classes_encoded))}',
            *[f'  class {c}: {cnt:,} px ({cnt / n_pix * 100:.1f}%)'
              for c, cnt in cls_counts[:6]],
        ]
        info_img = _info_panel(lines, w=500, h=180, title='RF Pixel Classifier')

        # ── Persist trained model to .joblib for geo_rf_predict ───────────────
        import os
        import joblib
        raw_cache = str(params.get('cache_dir', 'copernicus_cache') or 'copernicus_cache').strip()
        _engine_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir   = raw_cache if os.path.isabs(raw_cache) else os.path.join(_engine_dir, raw_cache)
        os.makedirs(cache_dir, exist_ok=True)
        # Hash on training-defining params so re-runs reuse the same path
        model_sig = hashlib.md5(_json.dumps({
            'classes':       [int(c) for c in classes_encoded],
            'band_names':    band_names,
            'n_estimators':  n_estimators,
            'max_depth':     max_depth,
            'n_train':       int(len(X_tr)),
            'split_mode':    split_mode,
        }, sort_keys=True).encode()).hexdigest()[:14]
        model_path = os.path.join(cache_dir, f'rf_model_{model_sig}.joblib')
        try:
            joblib.dump(
                {'rf': rf, 'label_encoder': le, 'band_names': band_names,
                 'classes': [int(c) for c in classes_encoded]},
                model_path, compress=3,
            )
        except Exception as e:
            send_notification(f'RF Classifier: model save failed: {e}',
                              level='warning', notif_id=_NOTIF)

        model_bundle = {
            'path':        model_path,
            'classes':     [int(c) for c in classes_encoded],
            'band_names':  band_names,
            'n_features':  int(C),
            'accuracy':    test_acc,
            'n_trees':     int(n_estimators),
            'created':     model_sig,
        }

        # ── Build output geo dict ──────────────────────────────────────────────
        out_geo = {
            'bands':     class_map[np.newaxis].astype(np.float32),
            'crs':       feat_geo.get('crs'),
            'transform': feat_geo.get('transform'),
            'count':     1,
            'height':    fH,
            'width':     fW,
            'dtype':     'float32',
            'preview':   preview,
        }

        send_notification(
            f'RF Classifier: done — {test_acc:.1%} acc — '
            f'{len(classes_encoded)} classes',
            progress=1.0, notif_id=_NOTIF,
        )

        result = {
            'classification': out_geo,
            'preview':        preview,
            'confidence':     conf_bgr,
            'importance':     importance_img,
            'accuracy':       test_acc,
            'n_samples':      float(n_valid),
            'report':         report_img,
            'report_data':    report_data,
            'conf_matrix':    conf_matrix_data,
            'model':          model_bundle,
        }
        self._cache_key = _key
        self._cache_out = result
        return result
