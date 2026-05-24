"""
geo_point_rasterizer.py — Rasterize a lat/lon DataFrame onto a reference pixel grid.

Takes a tabular dataset (CSV, Kaggle, etc.) with latitude + longitude columns
and projects its value columns onto the same pixel grid produced by geo_bands_to_table.
Output is a geotiff dict compatible with geo_bands_to_table's 'indices' input,
so extra feature bands can be added to any Sentinel-2 / DEM pipeline without
touching anything else.

Aggregation methods per pixel (multiple points → one value):
  mean · sum · max · min · count · first
"""
import io
import math
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_rasterizer'
_AGG   = ['mean', 'sum', 'max', 'min', 'count', 'first']


def _fig_to_bgr(fig, dpi: int = 100) -> np.ndarray:
    import matplotlib
    matplotlib.use('Agg')
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


@vision_node(
    type_id='geo_point_rasterizer',
    label='Point Rasterizer',
    category='geography',
    icon='MapPin',
    description=(
        "Rasterize a lat/lon DataFrame (CSV, Kaggle…) onto a reference pixel grid. "
        "Output is a GeoTIFF dict that plugs directly into the 'indices' port of "
        "'Bands → Table', adding extra feature columns (temperature, population, "
        "deforestation index…) to any ML pipeline. "
        "Multiple points in the same pixel are aggregated (mean/sum/max…)."
    ),
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame (lat/lon + values)'},
        {'id': 'shape',    'color': 'list', 'label': 'Shape [H, W] (from Bands→Table)'},
        {'id': 'geo_meta', 'color': 'dict', 'label': 'Geo metadata (from Bands→Table)'},
    ],
    outputs=[
        {'id': 'geotiff',       'color': 'geotiff', 'label': 'GeoTIFF (→ Bands→Table indices)'},
        {'id': 'table',         'color': 'data',    'label': 'Pixel-indexed DataFrame'},
        {'id': 'preview',       'color': 'image',   'label': 'Preview'},
        {'id': 'points_mapped', 'color': 'scalar',  'label': 'Points mapped'},
    ],
    params=[
        {'id': 'lat_col',    'label': 'Latitude column',            'type': 'string', 'default': 'lat'},
        {'id': 'lon_col',    'label': 'Longitude column',           'type': 'string', 'default': 'lon'},
        {'id': 'value_cols', 'label': 'Value columns (comma, blank=all numeric)', 'type': 'string', 'default': ''},
        {'id': 'aggregation','label': 'Aggregation per pixel',      'type': 'enum',   'options': _AGG, 'default': 0},
        {'id': 'nodata_val', 'label': 'NoData (pixels with no point)', 'type': 'float', 'default': -9999.0},
    ],
    resizable=True, min_width=260, min_height=180,
)
class GeoPointRasterizerNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        df       = inputs.get('table')
        shape    = inputs.get('shape')
        geo_meta = inputs.get('geo_meta')

        if not isinstance(df, pd.DataFrame):
            send_notification('Point Rasterizer: no DataFrame connected', level='warning', notif_id=_NOTIF)
            return {}
        if shape is None or geo_meta is None:
            send_notification('Point Rasterizer: shape + geo_meta required', level='warning', notif_id=_NOTIF)
            return {}

        H, W = int(shape[0]), int(shape[1])
        transform = geo_meta.get('transform') if isinstance(geo_meta, dict) else None
        crs       = geo_meta.get('crs')       if isinstance(geo_meta, dict) else None

        if transform is None:
            send_notification('Point Rasterizer: geo_meta has no transform', level='error', notif_id=_NOTIF)
            return {}

        # ── Resolve columns ────────────────────────────────────────────────────
        lat_col = str(params.get('lat_col', 'lat')).strip()
        lon_col = str(params.get('lon_col', 'lon')).strip()

        if lat_col not in df.columns or lon_col not in df.columns:
            available = list(df.columns)
            send_notification(
                f'Point Rasterizer: lat/lon columns not found. '
                f'Available: {available[:10]}',
                level='error', notif_id=_NOTIF,
            )
            return {}

        val_str  = str(params.get('value_cols', '')).strip()
        if val_str:
            val_cols = [c.strip() for c in val_str.split(',') if c.strip() and c.strip() in df.columns]
        else:
            # All numeric columns except lat/lon
            val_cols = [
                c for c in df.columns
                if c not in (lat_col, lon_col) and pd.api.types.is_numeric_dtype(df[c])
            ]
        if not val_cols:
            send_notification('Point Rasterizer: no numeric value columns found', level='error', notif_id=_NOTIF)
            return {}

        agg_idx = int(params.get('aggregation', 0))
        agg     = _AGG[agg_idx] if 0 <= agg_idx < len(_AGG) else 'mean'
        nodata  = float(params.get('nodata_val', -9999.0))
        nodata  = nodata if not (nodata != nodata) else -9999.0  # guard against NaN input

        # ── Drop rows with missing coords ──────────────────────────────────────
        work = df[[lat_col, lon_col] + val_cols].dropna(subset=[lat_col, lon_col]).copy()
        work[lon_col] = work[lon_col].astype(float)
        work[lat_col] = work[lat_col].astype(float)

        # ── Lat/lon → pixel (col, row) using affine transform inverse ─────────
        # Affine transform: (lon, lat) = T * (col, row)
        # Inverse: (col, row) = ~T * (lon, lat)
        try:
            inv = ~transform
            cols_f = inv.a * work[lon_col].values + inv.b * work[lat_col].values + inv.c
            rows_f = inv.d * work[lon_col].values + inv.e * work[lat_col].values + inv.f
        except Exception:
            # Fallback: affine module may not support ~ operator; compute manually
            # transform params: (a=dx, b=0, c=west, d=0, e=-dy, f=north)
            a, b, c = transform.a, transform.b, transform.c
            d, e, f = transform.d, transform.e, transform.f
            det = a * e - b * d
            if abs(det) < 1e-15:
                send_notification('Point Rasterizer: degenerate transform', level='error', notif_id=_NOTIF)
                return {}
            lons = work[lon_col].values
            lats = work[lat_col].values
            cols_f = ( e * (lons - c) - b * (lats - f)) / det
            rows_f = (-d * (lons - c) + a * (lats - f)) / det

        col_idx = np.floor(cols_f).astype(int)
        row_idx = np.floor(rows_f).astype(int)

        # Keep only points inside the grid
        valid = (col_idx >= 0) & (col_idx < W) & (row_idx >= 0) & (row_idx < H)
        col_idx = col_idx[valid]
        row_idx = row_idx[valid]
        work    = work.iloc[valid].copy()
        work['__col'] = col_idx
        work['__row'] = row_idx
        work['__px_idx'] = row_idx * W + col_idx

        points_mapped = float(len(work))

        # ── Aggregate each value column onto the pixel grid ────────────────────
        nodata_fill = np.nan if math.isnan(nodata) else nodata
        bands = np.full((len(val_cols), H, W), nodata_fill, dtype=np.float32)

        grouped = work.groupby('__px_idx')
        for bi, vc in enumerate(val_cols):
            if agg == 'mean':
                agg_series = grouped[vc].mean()
            elif agg == 'sum':
                agg_series = grouped[vc].sum()
            elif agg == 'max':
                agg_series = grouped[vc].max()
            elif agg == 'min':
                agg_series = grouped[vc].min()
            elif agg == 'count':
                agg_series = grouped[vc].count().astype(float)
            else:  # first
                agg_series = grouped[vc].first()

            px_indices = agg_series.index.values.astype(int)
            valid_px   = (px_indices >= 0) & (px_indices < H * W)
            rows_px    = px_indices[valid_px] // W
            cols_px    = px_indices[valid_px] %  W
            bands[bi, rows_px, cols_px] = agg_series.values[valid_px].astype(np.float32)

        # ── Build pixel-indexed output DataFrame ───────────────────────────────
        px_df_cols = {'__px_idx': np.arange(H * W, dtype=np.int32)}
        for bi, vc in enumerate(val_cols):
            px_df_cols[vc] = bands[bi].ravel()
        px_df = pd.DataFrame(px_df_cols)

        # ── Preview ────────────────────────────────────────────────────────────
        coverage = 100.0 * points_mapped / max(1, len(df))
        lines = [
            f'Points: {int(len(df)):,}  →  mapped: {int(points_mapped):,}  ({coverage:.1f}%)',
            f'Grid  : {H} × {W}',
            f'Aggregation: {agg}',
            f'Value columns ({len(val_cols)}):',
        ] + [f'  {c}' for c in val_cols[:8]]
        if len(val_cols) > 8:
            lines.append(f'  … +{len(val_cols)-8} more')

        preview = _info_panel(lines, w=420, h=200, title='Point Rasterizer')

        return {
            'geotiff':      {'bands': bands, 'count': len(val_cols), 'crs': crs, 'transform': transform},
            'table':        px_df,
            'preview':      preview,
            'points_mapped': points_mapped,
        }
