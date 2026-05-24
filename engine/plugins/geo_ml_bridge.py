"""
geo_ml_bridge.py — Bridge between raster geo data and ML pixel classification.

Two generic nodes:
  geo_bands_to_table : stack raster bands → pixel DataFrame (full table)
  geo_table_to_raster: pixel DataFrame → 2D raster image + GeoTIFF dict
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_ml'


def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


def _fig_to_bgr(fig, dpi: int = 100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _info_panel(lines: list[str], w: int = 420, h: int = 200, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
    for i, line in enumerate(lines[:(h - 44) // 16]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:60], (8, 44 + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
    return img


# ─── Bands → Table ────────────────────────────────────────────────────────────

@vision_node(
    type_id='geo_bands_to_table',
    label='Bands → Table',
    category='geography',
    icon='Table2',
    description=(
        "Convert a multi-band raster into a pixel DataFrame. "
        "Each row = one pixel, each column = one band. "
        "If a label mask is connected, a 'label' column is added (−1=unlabeled). "
        "Use ml_train_test_split downstream to extract labeled/train subsets. "
        "Generic: works for any per-pixel ML task."
    ),
    inputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'Raster source'},
        {'id': 'indices',  'color': 'geotiff', 'label': 'Extra computed indices (optional)'},
        {'id': 'label',    'color': 'image',   'label': 'Label mask (optional, −1=unlabeled)'},
    ],
    outputs=[
        {'id': 'table',          'color': 'data',   'label': 'Full table (all pixels)'},
        {'id': 'shape',          'color': 'list',   'label': 'Shape [H, W]'},
        {'id': 'geo_meta',       'color': 'dict',   'label': 'Geo metadata (CRS + transform)'},
        {'id': 'preview',        'color': 'image',  'label': 'Info preview'},
        {'id': 'labeled_count',  'color': 'scalar', 'label': 'Labeled pixels'},
        {'id': 'total_count',    'color': 'scalar', 'label': 'Total pixels'},
    ],
    params=[
        {'id': 'band_names',   'label': 'Band names (comma, blank=auto)',  'type': 'string', 'default': ''},
        {'id': 'index_names',  'label': 'Extra index names (comma)',        'type': 'string', 'default': 'ndvi'},
        {'id': 'filter_nodata','label': 'Exclude NaN/nodata pixels',       'type': 'bool',   'default': True},
    ],
    resizable=True, min_width=260, min_height=160,
)
class GeoBandsToTableNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            send_notification('BandsToTable: waiting for GeoTIFF input', notif_id=_NOTIF)
            return {}

        raw_bands = geo['bands']      # [count, H, W]
        crs       = geo.get('crs')
        transform = geo.get('transform')

        if raw_bands.ndim == 2:
            raw_bands = raw_bands[np.newaxis, :, :]
        count, H, W = raw_bands.shape

        # ── Band names ────────────────────────────────────────────────────────
        names_str = str(params.get('band_names', '')).strip()
        base_names = [n.strip() for n in names_str.split(',') if n.strip()]
        base_names = (base_names + [f'band_{i+1}' for i in range(len(base_names), count)])[:count]

        # ── Build pixel columns ───────────────────────────────────────────────
        cols: dict[str, np.ndarray] = {}
        for i in range(count):
            cols[base_names[i]] = raw_bands[i].ravel().astype(np.float32)

        # ── Extra computed indices (e.g. NDVI from geo_spectral_index raw) ───
        extra_geo = inputs.get('indices')
        if isinstance(extra_geo, dict) and 'bands' in extra_geo:
            eb = extra_geo['bands']
            if eb.ndim == 2:
                eb = eb[np.newaxis, :, :]
            idx_names_str = str(params.get('index_names', '')).strip()
            idx_names = [n.strip() for n in idx_names_str.split(',') if n.strip()]
            idx_names = (idx_names + [f'index_{j+1}' for j in range(len(idx_names), eb.shape[0])])[:eb.shape[0]]
            for j in range(eb.shape[0]):
                if eb[j].shape == (H, W):
                    cols[idx_names[j]] = eb[j].ravel().astype(np.float32)

        # ── Pixel index (preserved through ML pipeline for reconstruction) ───
        px_idx = np.arange(H * W, dtype=np.int32)

        full_df = pd.DataFrame(cols)
        full_df['__px_idx'] = px_idx

        # ── Filter NaN ────────────────────────────────────────────────────────
        if bool(params.get('filter_nodata', True)):
            band_cols = [c for c in full_df.columns if c != '__px_idx']
            valid = ~full_df[band_cols].isna().any(axis=1)
            full_df = full_df[valid].copy()

        total_count = float(len(full_df))

        # ── Label mask → add 'label' column to full_df (−1 = unlabeled) ──────
        labeled_count = 0.0

        label_arr = inputs.get('label')
        if isinstance(label_arr, np.ndarray):
            lbl = label_arr[:, :, 0] if label_arr.ndim == 3 else label_arr
            lbl_flat = lbl.ravel().astype(np.float32)
            lbl_for_full = lbl_flat[full_df['__px_idx'].values]
            full_df = full_df.copy()
            full_df['label'] = lbl_for_full
            labeled_count = float((lbl_for_full >= 0).sum())

        # ── Preview panel ─────────────────────────────────────────────────────
        lines = [
            f'Raster : {H} × {W} px  |  {count} bands',
            f'Bands : {", ".join(base_names)}',
            f'Valid pixels : {int(total_count):,}',
        ]
        if labeled_count > 0:
            lines += [
                f'Labeled pixels : {int(labeled_count):,}',
                f'Classes : {sorted(full_df["label"].dropna().astype(int).unique())}',
            ]
        if extra_geo is not None:
            idx_names_str = str(params.get('index_names', '')).strip()
            lines.append(f'Extra indices : {idx_names_str or "auto"}')

        preview = _info_panel(lines, w=420, h=200, title='Bands → Table')

        return {
            'table':         full_df,
            'shape':         [H, W],
            'geo_meta':      {'crs': crs, 'transform': transform},
            'preview':       preview,
            'labeled_count': labeled_count,
            'total_count':   total_count,
        }


# ─── Table → Raster ───────────────────────────────────────────────────────────

_COLORMAPS = ['RdYlGn', 'viridis', 'tab10', 'hot', 'gray', 'plasma', 'coolwarm']


@vision_node(
    type_id='geo_table_to_raster',
    label='Table → Raster',
    category='geography',
    icon='Map',
    description=(
        "Reconstruct a 2D raster from any pixel DataFrame. "
        "Requires the '__px_idx' column produced by 'Bands → Table'. "
        "Pick any column to map (predictions, labels, indices, etc.). "
        "Outputs a colorized visualization image and a GeoTIFF dict "
        "ready for the GeoTIFF Writer node. "
        "Built-in export: set file_path and click Save to write a QGIS-ready GeoTIFF."
    ),
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame (any per-pixel column)'},
        {'id': 'shape',    'color': 'list', 'label': 'Shape [H, W]'},
        {'id': 'geo_meta', 'color': 'dict', 'label': 'Geo metadata (optional)'},
    ],
    outputs=[
        {'id': 'main',   'color': 'image',   'label': 'Colorized map'},
        {'id': 'geotiff','color': 'geotiff', 'label': 'GeoTIFF (→ Writer)'},
        {'id': 'raster', 'color': 'dict',    'label': 'Raw raster (dict)'},
    ],
    params=[
        {'id': 'column',        'label': 'Column to map',       'type': 'string', 'default': 'prediction'},
        {'id': 'colormap',      'label': 'Colormap',            'type': 'enum',   'options': _COLORMAPS, 'default': 0},
        {'id': 'nodata_val',    'label': 'NoData value',        'type': 'float',  'default': -1.0},
        {'id': 'class_0_label', 'label': 'Class 0 legend',     'type': 'string', 'default': 'Class 0'},
        {'id': 'class_1_label', 'label': 'Class 1 legend',     'type': 'string', 'default': 'Class 1'},
        {'id': 'file_path',     'label': 'Export path (.tif)',  'type': 'string', 'default': 'output.tif'},
        {'id': 'save',          'label': 'Save GeoTIFF',        'type': 'trigger','default': 0},
    ],
    resizable=True, min_width=260, min_height=200,
)
class GeoTableToRasterNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._prev_save = 0

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        df    = inputs.get('table')
        shape = inputs.get('shape')

        if not isinstance(df, pd.DataFrame) or shape is None:
            return {}

        H, W = int(shape[0]), int(shape[1])

        # ── Resolve column to map ─────────────────────────────────────────────
        col = str(params.get('column', 'prediction')).strip()
        if col not in df.columns:
            # fallback: first column that contains 'pred' or 'class', else last
            for c in df.columns:
                if any(k in c.lower() for k in ('pred', 'class', 'label')):
                    col = c
                    break
            else:
                numeric = [c for c in df.columns if c != '__px_idx']
                col = numeric[-1] if numeric else df.columns[-1]

        nodata = float(params.get('nodata_val', -1.0))
        raster_flat = np.full(H * W, nodata, dtype=np.float32)

        if '__px_idx' in df.columns:
            idx  = df['__px_idx'].values.astype(int)
            vals = df[col].values.astype(np.float32)
            valid = (idx >= 0) & (idx < H * W)
            raster_flat[idx[valid]] = vals[valid]
        else:
            vals = df[col].values.astype(np.float32)
            n = min(len(vals), H * W)
            raster_flat[:n] = vals[:n]

        raster_2d = raster_flat.reshape(H, W)

        # ── Colorize with matplotlib ──────────────────────────────────────────
        cmap_name = _COLORMAPS[int(params.get('colormap', 0))]
        _, plt = _get_mpl()

        valid_mask = raster_2d != nodata
        valid_vals = raster_2d[valid_mask]
        vmin = float(valid_vals.min()) if valid_vals.size > 0 else 0.0
        vmax = float(valid_vals.max()) if valid_vals.size > 0 else 1.0

        display = np.where(valid_mask, raster_2d, np.nan)

        with plt.rc_context({'figure.facecolor': '#161616', 'axes.facecolor': '#1e1e1e',
                              'text.color': '#cccccc', 'axes.labelcolor': '#cccccc'}):
            fig, ax = plt.subplots(figsize=(6, 5))
            im = ax.imshow(display, cmap=cmap_name, vmin=vmin, vmax=vmax,
                           interpolation='nearest')
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.ax.tick_params(colors='#aaaaaa')

            # Simple legend for 2-class case
            uniq = np.unique(valid_vals.astype(int)) if valid_vals.size > 0 else []
            if len(uniq) == 2:
                labels = {
                    int(uniq[0]): str(params.get('class_0_label', 'Class 0')),
                    int(uniq[1]): str(params.get('class_1_label', 'Class 1')),
                }
                cbar.set_ticks(list(labels.keys()))
                cbar.set_ticklabels(list(labels.values()))

            ax.set_title(f'Map: {col}', fontsize=10, color='#cccccc')
            ax.axis('off')
            fig.tight_layout()
            main_img = _fig_to_bgr(fig, dpi=100)
            plt.close(fig)

        # ── GeoTIFF output dict ───────────────────────────────────────────────
        geo_meta = inputs.get('geo_meta')
        crs       = geo_meta.get('crs')       if isinstance(geo_meta, dict) else None
        transform = geo_meta.get('transform') if isinstance(geo_meta, dict) else None

        geotiff_out = {
            'bands':     raster_2d[np.newaxis, :, :].astype(np.float32),
            'count':     1,
            'crs':       crs,
            'transform': transform,
        }

        # ── Built-in GeoTIFF export (QGIS-ready) ─────────────────────────────
        save_val = params.get('save', 0)
        rising   = save_val != self._prev_save and save_val not in (False, 0, None)
        self._prev_save = save_val
        if rising:
            self._export_geotiff(geotiff_out, str(params.get('file_path', 'output.tif')).strip() or 'output.tif')

        return {
            'main':    main_img,
            'geotiff': geotiff_out,
            'raster':  {'data': raster_2d, 'shape': [H, W], 'column': col},
        }

    def _export_geotiff(self, geotiff_out: dict, path: str) -> None:
        import os
        try:
            import rasterio
        except ImportError:
            send_notification('rasterio missing — pip install rasterio', level='error', notif_id=_NOTIF)
            return

        bands     = geotiff_out['bands']          # [1, H, W] float32
        crs       = geotiff_out.get('crs')
        transform = geotiff_out.get('transform')
        _, H, W   = bands.shape

        profile = {
            'driver': 'GTiff',
            'dtype':  'float32',
            'width':  W,
            'height': H,
            'count':  1,
            'compress': 'lzw',
        }
        if crs:
            profile['crs'] = crs
        if transform:
            profile['transform'] = transform

        abs_path = os.path.abspath(path)
        try:
            os.makedirs(os.path.dirname(abs_path) or '.', exist_ok=True)
            send_notification(f'Saving GeoTIFF → {abs_path}…', progress=0.3, notif_id=_NOTIF)
            with rasterio.open(abs_path, 'w', **profile) as dst:
                dst.write(bands.astype(np.float32))
            send_notification(f'GeoTIFF saved: {abs_path}', progress=1.0, notif_id=_NOTIF)
        except Exception as exc:
            send_notification(f'GeoTIFF export error: {exc}', level='error', notif_id=_NOTIF)
