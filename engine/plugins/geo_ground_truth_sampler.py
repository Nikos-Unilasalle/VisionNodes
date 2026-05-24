"""
geo_ground_truth_sampler.py — Sample Sentinel-2 reflectances at in-situ ground truth points.

Reads a CSV with (lat, lon, target) columns, reprojects coordinates to the geotiff CRS,
extracts band values at each sample pixel, and outputs a labeled training table ready
for ml_symbolic_regressor.

Designed for matchup datasets (GLORIA, Naïades, USGS WQP…).
"""
import os
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'gt_sampler'


def _fig_to_bgr(fig, dpi: int = 100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _info_panel(lines, w=460, h=240, title=''):
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    line_h = 15
    max_lines = (h - 36) // line_h
    for i, line in enumerate(lines[:max_lines]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:80], (8, 44 + i * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
    return img


@vision_node(
    type_id='geo_ground_truth_sampler',
    label='Ground Truth Sampler (CSV)',
    category='geography',
    icon='Crosshair',
    description=(
        "Sample reflectance values from a multi-band geotiff at in-situ ground "
        "truth points (CSV with lat/lon/target columns). Outputs a labeled "
        "training table for ml_symbolic_regressor. "
        "Compatible with GLORIA, Naïades, USGS Water Quality Portal CSV exports. "
        "CSV coordinates assumed in WGS84 (EPSG:4326); reprojected to raster CRS."
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Reflectance raster'},
        {'id': 'table',   'color': 'data',    'label': 'Measurements table (lat/lon/label) — overrides CSV path'},
    ],
    outputs=[
        {'id': 'train_table',  'color': 'data',   'label': 'Labeled training table'},
        {'id': 'sample_mask',  'color': 'mask',   'label': 'Sample location mask'},
        {'id': 'preview',      'color': 'image',  'label': 'Overview'},
        {'id': 'n_samples',    'color': 'scalar', 'label': 'Points sampled'},
        {'id': 'n_filtered',   'color': 'scalar', 'label': 'Points dropped'},
    ],
    params=[
        {'id': 'csv_path',    'type': 'string', 'default': '',
         'label': 'CSV path (lat, lon, target)'},
        {'id': 'lat_col',     'type': 'string', 'default': 'lat',     'label': 'Latitude column'},
        {'id': 'lon_col',     'type': 'string', 'default': 'lon',     'label': 'Longitude column'},
        {'id': 'target_col',  'type': 'string', 'default': 'label', 'label': 'Target column (NTU → sortira comme "label")'},
        {'id': 'band_names',  'type': 'string', 'default': 'Bleu,Vert,Rouge,NIR',
         'label': 'Band names (comma, in raster order)'},
        {'id': 'target_min',  'type': 'float',  'default': 0.0,
         'min': -1e9, 'max': 1e9, 'label': 'Target min (filter)'},
        {'id': 'target_max',  'type': 'float',  'default': 500.0,
         'min': -1e9, 'max': 1e9, 'label': 'Target max (filter)'},
        {'id': 'mask_radius', 'type': 'int',    'default': 5, 'min': 1, 'max': 30,
         'label': 'Sample mask radius (px, viz only)'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class GroundTruthSamplerNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas', 'rasterio', 'pyproj'], notif_id=_NOTIF):
            return {}
        import pandas as pd
        from rasterio.transform import rowcol
        from pyproj import Transformer

        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            send_notification('GT Sampler: waiting for GeoTIFF (connect ACOLITE/Copernicus output)',
                              notif_id=_NOTIF)
            return {}

        lat_col   = str(params.get('lat_col', 'lat')).strip()
        lon_col   = str(params.get('lon_col', 'lon')).strip()
        tgt_col   = str(params.get('target_col', 'label')).strip()

        # Accept DataFrame from connected node (e.g. Naïades) or fall back to CSV file
        in_table = inputs.get('table')
        if isinstance(in_table, pd.DataFrame):
            df = in_table.copy()
            send_notification(f'GT Sampler: using connected table ({len(df)} rows)', progress=0.15, notif_id=_NOTIF)
        else:
            csv_path = str(params.get('csv_path', '')).strip()
            if not csv_path or not os.path.isfile(csv_path):
                send_notification(f'GT Sampler: no table connected and CSV not found: {csv_path}',
                                  level='error', notif_id=_NOTIF)
                return {}
            send_notification(f'GT Sampler: reading {csv_path}…', progress=0.1, notif_id=_NOTIF)
            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                send_notification(f'GT Sampler: CSV read error: {e}', level='error', notif_id=_NOTIF)
                return {}
        band_str  = str(params.get('band_names', 'Bleu,Vert,Rouge,NIR')).strip()
        t_min     = float(params.get('target_min', 0.0))
        t_max     = float(params.get('target_max', 500.0))
        m_radius  = max(1, int(params.get('mask_radius', 5)))

        bands     = geo['bands']
        if bands.ndim == 2:
            bands = bands[np.newaxis]
        count, H, W = bands.shape
        crs       = geo.get('crs')
        transform = geo.get('transform')
        if transform is None or crs is None:
            send_notification('GT Sampler: missing CRS/transform on geotiff', level='error', notif_id=_NOTIF)
            return {}

        for c in (lat_col, lon_col, tgt_col):
            if c not in df.columns:
                send_notification(f'GT Sampler: missing column "{c}". Have: {list(df.columns)[:8]}',
                                  level='error', notif_id=_NOTIF)
                return {}

        n_total = len(df)
        send_notification(f'GT Sampler: {n_total:,} CSV rows', progress=0.2, notif_id=_NOTIF)

        # ── Filter target range
        df = df[(df[tgt_col] >= t_min) & (df[tgt_col] <= t_max)].copy()
        df = df.dropna(subset=[lat_col, lon_col, tgt_col])

        # ── Reproject lat/lon (WGS84) → raster CRS
        send_notification(f'GT Sampler: reprojecting → {crs}…', progress=0.35, notif_id=_NOTIF)
        try:
            transformer = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
            xs, ys = transformer.transform(df[lon_col].values, df[lat_col].values)
        except Exception as e:
            send_notification(f'GT Sampler: reprojection error: {e}', level='error', notif_id=_NOTIF)
            return {}

        # ── Convert world coords → pixel (row, col)
        rows, cols = rowcol(transform, list(xs), list(ys))
        rows = np.asarray(rows, dtype=np.int64)
        cols = np.asarray(cols, dtype=np.int64)

        in_bounds = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
        n_inbounds = int(in_bounds.sum())
        if n_inbounds == 0:
            # Compute raster bbox in WGS84 for diagnosis
            try:
                from rasterio.transform import xy as _xy
                from pyproj import Transformer as _T
                _t = _T.from_crs(crs, 'EPSG:4326', always_xy=True)
                _x0, _y0 = _xy(transform, 0, 0)
                _x1, _y1 = _xy(transform, H - 1, W - 1)
                _lon0, _lat0 = _t.transform(_x0, _y0)
                _lon1, _lat1 = _t.transform(_x1, _y1)
                _pts_lat = df[lat_col].values
                _pts_lon = df[lon_col].values
                send_notification(
                    f'GT Sampler: 0/{len(df)} points in raster. '
                    f'Raster bbox: lat[{min(_lat0,_lat1):.3f},{max(_lat0,_lat1):.3f}] '
                    f'lon[{min(_lon0,_lon1):.3f},{max(_lon0,_lon1):.3f}]. '
                    f'Points bbox: lat[{_pts_lat.min():.3f},{_pts_lat.max():.3f}] '
                    f'lon[{_pts_lon.min():.3f},{_pts_lon.max():.3f}]',
                    level='error', notif_id=_NOTIF,
                )
            except Exception:
                send_notification('GT Sampler: no points within raster bounds', level='error', notif_id=_NOTIF)
            return {}

        df_in = df[in_bounds].copy()
        rows  = rows[in_bounds]
        cols  = cols[in_bounds]

        # ── Extract band values at sample pixels
        send_notification(f'GT Sampler: extracting bands at {n_inbounds} points…', progress=0.6, notif_id=_NOTIF)
        band_names = [n.strip() for n in band_str.split(',') if n.strip()]
        band_names = (band_names + [f'band_{i+1}' for i in range(len(band_names), count)])[:count]

        sample_df = pd.DataFrame({'__px_idx': (rows * W + cols).astype(np.int32)})
        for i, name in enumerate(band_names):
            sample_df[name] = bands[i, rows, cols].astype(np.float32)
        sample_df['label']     = df_in[tgt_col].to_numpy(dtype=np.float32)
        sample_df['lat']       = df_in[lat_col].to_numpy(dtype=np.float64)
        sample_df['lon']       = df_in[lon_col].to_numpy(dtype=np.float64)

        # Drop any NaN reflectance (cloud / nodata)
        valid = ~sample_df[band_names].isna().any(axis=1) & (sample_df[band_names].sum(axis=1) > 0)
        n_dropped = int((~valid).sum())
        sample_df = sample_df[valid].reset_index(drop=True)

        n_kept = len(sample_df)
        n_filtered = n_total - n_kept

        # ── Build viz mask (visible markers on map)
        sample_mask = np.zeros((H, W), dtype=np.uint8)
        for r, c in zip(rows, cols):
            cv2.circle(sample_mask, (int(c), int(r)), m_radius, 255, -1)

        # ── Preview panel
        lines = [
            f'CSV: {os.path.basename(csv_path)}',
            f'Total rows: {n_total:,}',
            f'In raster bounds: {n_inbounds:,}',
            f'Kept (valid bands): {n_kept:,}',
            f'Dropped (filter/nodata): {n_filtered:,}',
            f'Target [{tgt_col}]: μ={sample_df["label"].mean():.2f}  '
            f'σ={sample_df["label"].std():.2f}',
            f'           min={sample_df["label"].min():.2f}  '
            f'max={sample_df["label"].max():.2f}',
            f'Bands: {", ".join(band_names)}',
        ]
        preview = _info_panel(lines, w=480, h=220, title='Ground Truth Sampler')

        send_notification(
            f'GT Sampler: OK — {n_kept} labeled points ({n_filtered} dropped)',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'train_table': sample_df,
            'sample_mask': sample_mask,
            'preview':     preview,
            'n_samples':   float(n_kept),
            'n_filtered':  float(n_filtered),
        }
