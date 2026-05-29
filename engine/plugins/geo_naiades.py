"""
geo_naiades.py — Download French water quality data from Hub'Eau (Naïades API).

Fetches turbidity (or any parameter) measurements with lat/lon from
the French national water quality portal (https://hubeau.eaufrance.fr).
Output is a CSV-like DataFrame compatible with geo_ground_truth_sampler.

API endpoint: /api/v1/qualite_rivieres/resultats
Turbidity parameter code: 1295 (Turbidité Formazine NTU)
"""
import os
import io
import datetime
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'naiades'

_PARAM_PRESETS = {
    'Turbidity (NTU)': '1295',
    'SPM (mg/L)':      '1305',
    'Chlorophyll-a':   '1433',
    'DOC':             '1841',
    'Custom':          '',
}

# Region presets: (lon_min, lat_min, lon_max, lat_max)
_REGION_PRESETS = {
    'All France':              (-5.5, 41.0,  9.5, 51.5),
    'Seine basin (Paris)':     ( 1.5, 48.5,  3.5, 49.2),
    'Seine downstream/Rouen':  ( 0.0, 49.0,  1.5, 49.6),
    'Seine estuary':           (-0.5, 49.2,  1.0, 49.7),
    'Loire basin':             (-2.0, 47.0,  4.0, 48.5),
    'Rhone basin':             ( 4.0, 43.5,  6.0, 46.0),
    'Garonne basin':           (-1.5, 43.0,  2.0, 45.0),
    'Custom bbox':             None,
}


def _info_panel(lines: list, w: int = 480, h: int = 240, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 15
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:72], (8, 44 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.37, color, 1, cv2.LINE_AA)
    return img


@vision_node(
    type_id='geo_naiades',
    label='Naiades Downloader (Hub\'eau)',
    category='geography',
    icon='Database',
    description=(
        "Download French water quality measurements from Hub'eau Naiades API. "
        "Returns a labeled DataFrame (lat, lon, label) ready for geo_ground_truth_sampler. "
        "Filter by bounding box, date range, and water quality parameter. "
        "Turbidity (NTU) code: 1295. Requires internet connection."
    ),
    inputs=[
        {'id': 'bbox',       'color': 'string', 'label': 'BBox (str)'},
        {'id': 'date_start', 'color': 'string', 'label': 'Start Date'},
        {'id': 'date_end',   'color': 'string', 'label': 'End Date'},
    ],
    outputs=[
        {'id': 'csv_table',   'color': 'data',   'label': 'Measurements table (lat/lon/label)'},
        {'id': 'preview',     'color': 'image',  'label': 'Download summary'},
        {'id': 'n_stations',  'color': 'scalar', 'label': 'Stations found'},
        {'id': 'n_samples',   'color': 'scalar', 'label': 'Measurements'},
    ],
    params=[
        {'id': 'parameter',   'label': 'Parameter',               'type': 'enum',
         'options': list(_PARAM_PRESETS.keys()), 'default': 0},
        {'id': 'param_code',  'label': 'Custom code (if Custom)',
         'type': 'string', 'default': '1295'},
        {'id': 'region',      'label': 'Region preset',            'type': 'enum',
         'options': list(_REGION_PRESETS.keys()), 'default': 0},
        {'id': 'bbox_lon_min','label': 'Lon min (W)  [Custom only]',  'type': 'float', 'default': -5.5,  'min': -5.5, 'max': 10.0},
        {'id': 'bbox_lon_max','label': 'Lon max (E)',  'type': 'float', 'default':  9.5,  'min': -5.5, 'max': 10.0},
        {'id': 'bbox_lat_min','label': 'Lat min (S)',  'type': 'float', 'default': 41.0,  'min': 41.0, 'max': 52.0},
        {'id': 'bbox_lat_max','label': 'Lat max (N)',  'type': 'float', 'default': 51.5,  'min': 41.0, 'max': 52.0},
        {'id': 'date_min',    'label': 'Date start (YYYY-MM-DD)', 'type': 'string', 'default': '2017-01-01'},
        {'id': 'date_max',    'label': 'Date end   (YYYY-MM-DD)', 'type': 'string', 'default': '2024-12-31'},
        {'id': 'target_min',  'label': 'Value min filter',  'type': 'float', 'default': 0.0,   'min': 0.0,  'max': 1e6},
        {'id': 'target_max',  'label': 'Value max filter',  'type': 'float', 'default': 500.0, 'min': 0.0,  'max': 1e6},
        {'id': 'max_results', 'label': 'Max results (API cap 20000)', 'type': 'int', 'default': 5000, 'min': 100, 'max': 20000},
        {'id': 'save_csv',    'label': 'Save to CSV path', 'type': 'string', 'default': ''},
        {'id': 'fetch',       'label': 'Fetch data',  'type': 'trigger', 'default': 0},
    ],
    resizable=True, min_width=300, min_height=240,
)
class NaiadesNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._prev_fetch = 0
        self._cache_df   = None
        self._cache_preview = None

    def process(self, inputs, params):
        if not self.ensure_packages(['requests', 'pandas'], notif_id=_NOTIF):
            return {}
        import requests
        import pandas as pd

        fetch_val = params.get('fetch', 0)
        rising    = fetch_val != self._prev_fetch and fetch_val not in (False, 0, None)
        self._prev_fetch = fetch_val

        if not rising and self._cache_df is not None:
            return {
                'csv_table':  self._cache_df,
                'preview':    self._cache_preview,
                'n_stations': float(self._cache_df['station_id'].nunique()) if 'station_id' in self._cache_df else 0.0,
                'n_samples':  float(len(self._cache_df)),
            }

        if not rising:
            lines = ['Click Fetch to download data', '(no cache yet)']
            return {'preview': _info_panel(lines, title="Naiades Hub'eau")}

        # ── Resolve parameter code
        param_key = list(_PARAM_PRESETS.keys())[int(params.get('parameter', 0))]
        if param_key == 'Custom':
            code = str(params.get('param_code', '1295')).strip()
        else:
            code = _PARAM_PRESETS[param_key]

        # ── Resolve region (preset overrides custom bbox unless 'Custom bbox')
        region_key = list(_REGION_PRESETS.keys())[int(params.get('region', 0))]
        preset = _REGION_PRESETS[region_key]
        
        bbox_in = str(inputs.get('bbox', '') or '').strip()
        if bbox_in:
            try:
                parts = [float(v) for v in bbox_in.split(',')]
                if len(parts) == 4:
                    lon_min, lat_min, lon_max, lat_max = parts
                else:
                    raise ValueError
            except Exception:
                lon_min, lat_min, lon_max, lat_max = preset if preset else (
                    float(params.get('bbox_lon_min', -5.5)),
                    float(params.get('bbox_lat_min', 41.0)),
                    float(params.get('bbox_lon_max',  9.5)),
                    float(params.get('bbox_lat_max', 51.5))
                )
        else:
            if preset is not None:
                lon_min, lat_min, lon_max, lat_max = preset
            else:
                lon_min = float(params.get('bbox_lon_min', -5.5))
                lon_max = float(params.get('bbox_lon_max',  9.5))
                lat_min = float(params.get('bbox_lat_min', 41.0))
                lat_max = float(params.get('bbox_lat_max', 51.5))
                
        d_min   = str(inputs.get('date_start') or params.get('date_min', '2017-01-01')).strip()
        d_max   = str(inputs.get('date_end') or params.get('date_max', '2024-12-31')).strip()
        t_min   = float(params.get('target_min', 0.0))
        t_max   = float(params.get('target_max', 500.0))
        max_r   = min(int(params.get('max_results', 5000)), 20000)

        send_notification(f"Naiades: fetching code={code} bbox=[{lon_min},{lat_min}→{lon_max},{lat_max}]...",
                          progress=0.05, notif_id=_NOTIF)

        url = 'https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/analyse_pc'

        # API caps each query at size=20000 and returns oldest-first.
        # Chunk by year to get coverage across the whole date range.
        try:
            y0 = int(d_min[:4])
            y1 = int(d_max[:4])
        except Exception:
            y0, y1 = 2017, datetime.date.today().year
        years = list(range(y0, y1 + 1))

        per_year_cap = min(max_r, 20000)
        all_records = []
        for i, y in enumerate(years):
            yd_min = f'{y}-01-01' if y > y0 else d_min
            yd_max = f'{y}-12-31' if y < y1 else d_max
            payload = {
                'code_parametre':         code,
                'bbox':                   f'{lon_min},{lat_min},{lon_max},{lat_max}',
                'date_debut_prelevement': yd_min,
                'date_fin_prelevement':   yd_max,
                'code_remarque':          1,
                'size':                   per_year_cap,
                'fields':                 'code_station,libelle_station,latitude,longitude,date_prelevement,resultat,symbole_unite',
            }
            try:
                resp = requests.get(url, params=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                send_notification(f'Naiades: API error (year {y}) — {e}', level='warning', notif_id=_NOTIF)
                continue
            recs = data.get('data', [])
            all_records.extend(recs)
            send_notification(
                f'Naiades: year {y} → {len(recs)} rows (total {len(all_records)})',
                progress=0.05 + 0.55 * (i + 1) / len(years), notif_id=_NOTIF,
            )

        if not all_records:
            send_notification('Naiades: no data returned (check bbox/dates/code)',
                              level='error', notif_id=_NOTIF)
            return {}

        send_notification(f'Naiades: {len(all_records)} raw records — processing...',
                          progress=0.65, notif_id=_NOTIF)

        df = pd.DataFrame(all_records)
        df = df.rename(columns={
            'latitude':          'lat',
            'longitude':         'lon',
            'resultat':          'label',
            'code_station':      'station_id',
            'libelle_station':   'station_name',
            'date_prelevement':  'date',
        })

        df = df.dropna(subset=['lat', 'lon', 'label'])
        df['lat']   = pd.to_numeric(df['lat'],   errors='coerce')
        df['lon']   = pd.to_numeric(df['lon'],   errors='coerce')
        df['label'] = pd.to_numeric(df['label'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon', 'label'])
        df = df[(df['label'] >= t_min) & (df['label'] <= t_max)]

        n_stations = int(df['station_id'].nunique()) if 'station_id' in df.columns else 0
        n_samples  = len(df)

        # ── Optionally save CSV
        save_path = str(params.get('save_csv', '')).strip()
        if save_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(save_path)) or '.', exist_ok=True)
                df.to_csv(save_path, index=False)
                send_notification(f'Naiades: saved → {save_path}', progress=0.9, notif_id=_NOTIF)
            except Exception as e:
                send_notification(f'Naiades: save error — {e}', level='error', notif_id=_NOTIF)

        stats = df['label'].describe()
        lines = [
            f"Parameter: {param_key} (code {code})",
            f"BBox: [{lon_min},{lat_min}] -> [{lon_max},{lat_max}]",
            f"Period: {d_min} -> {d_max}",
            f"Stations: {n_stations}   Samples: {n_samples}",
            f"Label: min={stats['min']:.1f}  max={stats['max']:.1f}",
            f"       mean={stats['mean']:.1f}  median={stats['50%']:.1f}",
            f"Unit filter: [{t_min}, {t_max}]",
        ]
        if save_path:
            lines.append(f"Saved: {os.path.basename(save_path)}")

        preview = _info_panel(lines, w=480, h=200, title="Naiades Hub'eau")

        send_notification(f"Naiades: OK — {n_samples} samples, {n_stations} stations",
                          progress=1.0, notif_id=_NOTIF)

        self._cache_df      = df
        self._cache_preview = preview

        return {
            'csv_table':  df,
            'preview':    preview,
            'n_stations': float(n_stations),
            'n_samples':  float(n_samples),
        }
