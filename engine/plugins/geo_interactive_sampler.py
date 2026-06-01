"""
geo_interactive_sampler.py — Interactive spectral sampling on a GeoTIFF.

The user selects up to 3 spectral indices (band names) via checkboxes.
  slot 0 (L-click)   → samples selectedIndices[0]
  slot 1 (R-click)   → samples selectedIndices[1]
  slot 2 (Shift+L)   → samples selectedIndices[2]

Each point samples only the index bound to its click type.
Output table: one row per point → [id, index, value, lat, lon].
band_previews: dict {band_name → base64 JPEG} for the editor basemap selector.
"""
from __future__ import annotations
import base64
import json
import cv2
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_interactive_sampler'

_SLOT_COLOR   = {0: (50, 220, 34), 1: (68, 68, 255), 2: (255, 212, 0)}
_SLOT_GESTURE = {0: 'L-click', 1: 'R-click', 2: 'Shift'}


def _band_to_base64(band: np.ndarray, colormap: int = cv2.COLORMAP_VIRIDIS, max_px: int = 1024) -> str:
    lo, hi = float(np.nanmin(band)), float(np.nanmax(band))
    norm = ((band - lo) / (hi - lo) * 255).clip(0, 255).astype(np.uint8) if hi > lo else np.zeros_like(band, dtype=np.uint8)
    colored = cv2.applyColorMap(norm, colormap)
    h, w = colored.shape[:2]
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        colored = cv2.resize(colored, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode('.jpg', colored, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return base64.b64encode(buf).decode('utf-8')


@vision_node(
    type_id='geo_interactive_sampler',
    label='Geo Interactive Sampler',
    category='geography',
    icon='Crosshair',
    description=(
        'Interactive spectral sampler. Select up to 3 indices (band names) via '
        'checkboxes; left-click samples index 1, right-click index 2, shift+click '
        'index 3. Outputs a table [id / index / value / lat / lon]. '
        'The editor basemap can be switched to any available band.'
    ),
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Feature stack (geo_spectral_indices)'},
        {'id': 'image',   'color': 'image',   'label': 'Preview image (optional base / basemap)'},
    ],
    outputs=[
        {'id': 'table',   'color': 'data',  'label': 'Samples table (index / value / lat / lon)'},
        {'id': 'preview', 'color': 'image', 'label': 'Annotated preview'},
    ],
    params=[
        {'id': 'points',       'type': 'string', 'default': '[]',
         'label': 'Points JSON (managed by editor)'},
        {'id': 'indices',      'type': 'string', 'default': '[]',
         'label': 'Selected indices JSON (max 3, order = L/R/Shift)'},
        {'id': 'point_radius', 'type': 'int',    'default': 8, 'min': 3, 'max': 30,
         'label': 'Point radius (preview)'},
    ],
    resizable=True, min_width=300, min_height=200, colorable=True,
)
class GeoInteractiveSamplerNode(NodeProcessor):

    def __init__(self) -> None:
        super().__init__()
        self._previews_cache: dict[str, str] = {}
        self._previews_hash: int | None = None
        self._image_cache: str | None = None
        self._image_hash: int | None = None

    def process(self, inputs: dict, params: dict) -> dict:
        if not self.ensure_packages(['pandas', 'rasterio'], notif_id=_NOTIF):
            return {}
        import pandas as pd
        import rasterio.warp

        geo   = inputs.get('geotiff')
        image = inputs.get('image')
        empty = {'table': None, 'preview': image, 'band_names': [], 'band_previews': {}}

        if geo is None:
            return empty

        bands_arr  = np.asarray(geo['bands'], dtype=np.float32)
        transform  = geo.get('transform')
        crs        = geo.get('crs')
        band_names: list[str] = geo.get('band_names') or [
            f'B{i+1}' for i in range(bands_arr.shape[0] if bands_arr.ndim == 3 else 1)
        ]

        if bands_arr.size == 0 or transform is None:
            return {**empty, 'band_names': band_names}

        if bands_arr.ndim == 2:
            bands_arr = bands_arr[np.newaxis]
        _, H, W = bands_arr.shape

        # Build per-band preview thumbnails — cached by data hash to avoid 30fps recompute
        bands_hash = hash(bands_arr.tobytes())
        if bands_hash != self._previews_hash:
            self._previews_cache = {}
            for idx, name in enumerate(band_names):
                try:
                    self._previews_cache[name] = _band_to_base64(bands_arr[idx])
                except Exception:
                    pass
            self._previews_hash = bands_hash

        band_previews: dict[str, str] = dict(self._previews_cache)

        # Image input thumbnail — cached separately
        if image is not None:
            img_hash = hash(image.tobytes())
            if img_hash != self._image_hash:
                try:
                    h, w = image.shape[:2]
                    if max(h, w) > 1024:
                        scale = 1024 / max(h, w)
                        thumb = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                    else:
                        thumb = image
                    _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 82])
                    self._image_cache = base64.b64encode(buf).decode('utf-8')
                except Exception:
                    self._image_cache = None
                self._image_hash = img_hash
            if self._image_cache:
                band_previews['__image__'] = self._image_cache

        try:
            points_raw = json.loads(params.get('points', '[]'))
            if not isinstance(points_raw, list):
                points_raw = []
        except (json.JSONDecodeError, TypeError):
            points_raw = []

        try:
            selected: list[str] = json.loads(params.get('indices', '[]'))
            if not isinstance(selected, list):
                selected = []
            selected = selected[:3]
        except (json.JSONDecodeError, TypeError):
            selected = []

        slot_bidx: list[int | None] = [
            band_names.index(n) if n in band_names else None
            for n in selected
        ]

        radius = int(params.get('point_radius', 8))

        # Annotated preview uses the connected image (or first band) as base
        if image is not None:
            canvas = cv2.resize(image, (W, H)) if (image.shape[1] != W or image.shape[0] != H) else image.copy()
        else:
            band0 = bands_arr[0]
            lo, hi = float(np.nanmin(band0)), float(np.nanmax(band0))
            vis = ((band0 - lo) / (hi - lo) * 255).clip(0, 255).astype(np.uint8) if hi > lo else np.zeros_like(band0, dtype=np.uint8)
            canvas = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

        rows: list[dict] = []
        x_proj_list: list[float] = []
        y_proj_list: list[float] = []
        # point_values: keyed by original points_raw index (str) for the editor live display
        point_values: dict[str, dict] = {}

        for i, pt in enumerate(points_raw):
            if not isinstance(pt, dict):
                continue
            nx   = float(pt.get('x', 0))
            ny   = float(pt.get('y', 0))
            slot = int(pt.get('type', 0))

            if slot >= len(selected) or not selected[slot]:
                continue

            col_i = max(0, min(W - 1, int(round(nx * (W - 1)))))
            row_i = max(0, min(H - 1, int(round(ny * (H - 1)))))

            x_proj = transform.a * col_i + transform.b * row_i + transform.c
            y_proj = transform.d * col_i + transform.e * row_i + transform.f

            bidx  = slot_bidx[slot]
            value = float(bands_arr[bidx, row_i, col_i]) if bidx is not None else float('nan')
            value_r = round(value, 4)

            rows.append({
                'id':     i + 1,
                'index':  selected[slot],
                'value':  value_r,
                'col_px': col_i,
                'row_px': row_i,
                'x_proj': x_proj,
                'y_proj': y_proj,
                '_slot':  slot,
            })
            point_values[str(i)] = {'index': selected[slot], 'value': value_r}
            x_proj_list.append(x_proj)
            y_proj_list.append(y_proj)

        # Reproject → WGS84
        if x_proj_list and crs is not None and str(crs).upper() != 'EPSG:4326':
            try:
                lons, lats = rasterio.warp.transform(crs, 'EPSG:4326', x_proj_list, y_proj_list)
            except Exception as exc:
                send_notification(f'Geo Sampler: projection error: {exc}', level='warn', notif_id=_NOTIF)
                lons, lats = x_proj_list, y_proj_list
        else:
            lons, lats = x_proj_list, y_proj_list

        for j, rec in enumerate(rows):
            rec['longitude'] = round(lons[j], 6) if j < len(lons) else rec['x_proj']
            rec['latitude']  = round(lats[j], 6) if j < len(lats) else rec['y_proj']

        # Draw annotated points on canvas
        for rec in rows:
            slot  = rec['_slot']
            color = _SLOT_COLOR.get(slot, (255, 255, 255))
            cx, cy = rec['col_px'], rec['row_px']
            cv2.circle(canvas, (cx, cy), radius, color, -1)
            cv2.circle(canvas, (cx, cy), radius + 2, (255, 255, 255), 1)
            lbl = f"{rec['index']}={rec['value']:.2f}"
            cv2.putText(canvas, lbl, (cx + radius + 4, cy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # Wide format: one column per selected index, NaN if point didn't sample that index
        wide_rows = []
        for rec in rows:
            row: dict = {'id': rec['id'], 'latitude': rec['latitude'], 'longitude': rec['longitude']}
            for s, name in enumerate(selected):
                row[name] = rec['value'] if rec['_slot'] == s else float('nan')
            wide_rows.append(row)

        base_cols = ['id', 'latitude', 'longitude']
        index_cols = list(selected)
        df = pd.DataFrame(wide_rows, columns=base_cols + index_cols) if wide_rows else pd.DataFrame(columns=base_cols + index_cols)

        slot_counts = {s: sum(1 for r in rows if r['_slot'] == s) for s in range(3)}
        send_notification(
            f'Geo Sampler: {len(rows)} pts  ' +
            '  '.join(f'{_SLOT_GESTURE[s]}={selected[s]}×{slot_counts[s]}' for s in range(len(selected))),
            progress=1.0, notif_id=_NOTIF
        )

        return {'table': df, 'preview': canvas, 'band_names': band_names, 'band_previews': band_previews, 'point_values': point_values}
