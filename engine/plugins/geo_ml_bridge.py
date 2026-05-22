"""
geo_ml_bridge.py — Bridge between raster geo data and ML pixel classification.

Two generic nodes:
  geo_bands_to_table : stack raster bands → pixel DataFrame (train + full)
  geo_table_to_raster: prediction DataFrame → 2D raster image + GeoTIFF dict
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
        "If a label mask is connected, also outputs a filtered training table "
        "(labeled pixels only). Generic: works for any per-pixel ML task."
    ),
    inputs=[
        {'id': 'geotiff',  'color': 'geotiff', 'label': 'Raster source'},
        {'id': 'indices',  'color': 'geotiff', 'label': 'Extra computed indices (optional)'},
        {'id': 'label',    'color': 'image',   'label': 'Label mask (optional, −1=unlabeled)'},
    ],
    outputs=[
        {'id': 'train_table',    'color': 'data',   'label': 'Train table (labeled pixels)'},
        {'id': 'full_table',     'color': 'data',   'label': 'Full table (all pixels)'},
        {'id': 'shape',          'color': 'list',   'label': 'Shape [H, W]'},
        {'id': 'geo_meta',       'color': 'dict',   'label': 'Geo metadata (CRS + transform)'},
        {'id': 'preview',        'color': 'image',  'label': 'Info preview'},
        {'id': 'labeled_count',  'color': 'scalar', 'label': 'Labeled pixels'},
        {'id': 'total_count',    'color': 'scalar', 'label': 'Total pixels'},
    ],
    params=[
        {'id': 'band_names',   'label': 'Noms des bandes (virgule, blank=auto)',   'type': 'string', 'default': ''},
        {'id': 'index_names',  'label': 'Noms des indices extra (virgule)',         'type': 'string', 'default': 'ndvi'},
        {'id': 'filter_nodata','label': 'Exclure pixels NaN/nodata',               'type': 'bool',   'default': True},
        {'id': 'sample_pct',   'label': 'Sous-échantillonnage train % (0=tout)',   'type': 'int',    'default': 0, 'min': 0, 'max': 99},
        {'id': 'seed',         'label': 'Seed sous-échantillonnage',               'type': 'int',    'default': 42, 'min': 0, 'max': 9999},
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

        # ── Label mask → train_table ──────────────────────────────────────────
        train_df      = None
        labeled_count = 0.0

        label_arr = inputs.get('label')
        if isinstance(label_arr, np.ndarray):
            lbl = label_arr[:, :, 0] if label_arr.ndim == 3 else label_arr
            lbl_flat = lbl.ravel().astype(np.float32)

            # Map pixel indices to label values
            lbl_for_full = lbl_flat[full_df['__px_idx'].values]
            full_with_lbl = full_df.copy()
            full_with_lbl['label'] = lbl_for_full

            train_df = full_with_lbl[full_with_lbl['label'] >= 0].copy()
            train_df['label'] = train_df['label'].astype(int)

            # Optional sub-sampling
            pct = int(params.get('sample_pct', 0))
            if 0 < pct < 100 and len(train_df) > 0:
                seed = int(params.get('seed', 42))
                train_df = train_df.sample(frac=pct / 100.0, random_state=seed)

            labeled_count = float(len(train_df))

        # ── Preview panel ─────────────────────────────────────────────────────
        lines = [
            f'Raster : {H} × {W} px  |  {count} bandes',
            f'Bandes : {", ".join(base_names)}',
            f'Pixels valides : {int(total_count):,}',
        ]
        if labeled_count > 0:
            lines += [
                f'Pixels étiquetés : {int(labeled_count):,}',
                f'Classes : {sorted(train_df["label"].unique())}',
            ]
        if extra_geo is not None:
            idx_names_str = str(params.get('index_names', '')).strip()
            lines.append(f'Indices extra : {idx_names_str or "auto"}')

        preview = _info_panel(lines, w=420, h=200, title='Bands → Table')

        return {
            'train_table':   train_df,
            'full_table':    full_df,
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
        "Reconstruct a 2D raster from a pixel prediction DataFrame. "
        "Requires the '__px_idx' column produced by 'Bands → Table'. "
        "Outputs a colorized visualization image and a GeoTIFF dict "
        "ready for the GeoTIFF Writer node. Generic: any per-pixel prediction."
    ),
    inputs=[
        {'id': 'predictions', 'color': 'data', 'label': 'Predictions DataFrame'},
        {'id': 'shape',       'color': 'list', 'label': 'Shape [H, W]'},
        {'id': 'geo_meta',    'color': 'dict', 'label': 'Geo metadata (optional)'},
    ],
    outputs=[
        {'id': 'main',   'color': 'image',   'label': 'Carte colorisée'},
        {'id': 'geotiff','color': 'geotiff', 'label': 'GeoTIFF (→ Writer)'},
        {'id': 'raster', 'color': 'dict',    'label': 'Raster brut (dict)'},
    ],
    params=[
        {'id': 'column',    'label': 'Colonne à cartographier',    'type': 'string', 'default': 'prediction'},
        {'id': 'colormap',  'label': 'Colormap',                   'type': 'enum',   'options': _COLORMAPS, 'default': 0},
        {'id': 'nodata_val','label': 'Valeur NoData',              'type': 'float',  'default': -1.0},
        {'id': 'class_0_label', 'label': 'Légende classe 0',      'type': 'string', 'default': 'Classe 0'},
        {'id': 'class_1_label', 'label': 'Légende classe 1',      'type': 'string', 'default': 'Classe 1'},
    ],
    resizable=True, min_width=260, min_height=200,
)
class GeoTableToRasterNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        df    = inputs.get('predictions')
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
                    int(uniq[0]): str(params.get('class_0_label', 'Classe 0')),
                    int(uniq[1]): str(params.get('class_1_label', 'Classe 1')),
                }
                cbar.set_ticks(list(labels.keys()))
                cbar.set_ticklabels(list(labels.values()))

            ax.set_title(f'Carte : {col}', fontsize=10, color='#cccccc')
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

        return {
            'main':    main_img,
            'geotiff': geotiff_out,
            'raster':  {'data': raster_2d, 'shape': [H, W], 'column': col},
        }
