"""
Axis Calibration — maps a pixel-coordinate point set onto real-world values.

Generic 2-point linear calibration per axis (like a ruler with two known ticks).
Works on any point list, not just digitized charts: pixel trajectories, plots, scans…
"""
from datetime import datetime
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'axis_calibration'

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False


def _pixel_to_value(pixel: float, px1: float, v1: float, px2: float, v2: float) -> float:
    if px2 == px1:
        return v1
    t = (pixel - px1) / (px2 - px1)
    return v1 + t * (v2 - v1)


def _parse_anchor(raw: str, is_date: bool, date_format: str) -> float:
    raw = str(raw).strip()
    return datetime.strptime(raw, date_format).toordinal() if is_date else float(raw.replace(',', '.'))


def _format_value(value: float, is_date: bool, date_format: str):
    return datetime.fromordinal(round(value)).strftime(date_format) if is_date else round(value, 6)


@vision_node(
    type_id='sci_axis_calibration',
    label='Axis Calibration',
    category='DataFrame',
    icon='Ruler',
    description="Converts a pixel-coordinate point list into real values via linear calibration. "
                "Both axes are calibrated against the point set's own pixel extremes — just give the real "
                "value/date at each end, no pixel coordinates to read off. Outputs a DataFrame — connect to DF Export for CSV.",
    inputs=[{'id': 'points', 'color': 'points'}],
    outputs=[{'id': 'data', 'color': 'data'}],
    params=[
        {'id': '_sec_x',      'label': 'X Calibration', 'type': 'section'},
        {'id': 'x_type',      'label': 'X Type',        'type': 'enum',   'options': ['Number', 'Date'], 'default': 0},
        {'id': 'date_format', 'label': 'Date Format',   'type': 'string', 'default': '%Y%m%d'},
        {'id': 'x_value_1',   'label': 'X Value @ First Point', 'type': 'string', 'default': '0'},
        {'id': 'x_value_2',   'label': 'X Value @ Last Point',  'type': 'string', 'default': '100'},

        {'id': '_sec_y',      'label': 'Y Calibration', 'type': 'section'},
        {'id': 'y_value_1',   'label': 'Y Value @ Min Pixel (top)',    'type': 'float', 'default': 1.0},
        {'id': 'y_value_2',   'label': 'Y Value @ Max Pixel (bottom)', 'type': 'float', 'default': 0.0},

        {'id': '_sec_out',    'label': 'Output',        'type': 'section'},
        {'id': 'x_col',       'label': 'X Column Name', 'type': 'string', 'default': 'x'},
        {'id': 'y_col',       'label': 'Y Column Name', 'type': 'string', 'default': 'y'},
    ]
)
class AxisCalibrationNode(NodeProcessor):
    def process(self, inputs, params):
        if not _PD_OK:
            send_notification("Axis Calibration: pandas not installed", level='error', notif_id=_NOTIF)
            return {}

        points = inputs.get('points')
        if not points or not isinstance(points, list):
            send_notification("Axis Calibration: no points connected", level='warning', notif_id=_NOTIF)
            return {}

        xs = [float(p['x']) for p in points if isinstance(p, dict) and 'x' in p]
        ys = [float(p['y']) for p in points if isinstance(p, dict) and 'y' in p]
        if not xs or not ys:
            send_notification("Axis Calibration: points missing 'x'/'y' pixel fields", level='warning', notif_id=_NOTIF)
            return {}
        x_px1, x_px2 = min(xs), max(xs)
        y_px1, y_px2 = min(ys), max(ys)

        x_is_date   = int(params.get('x_type', 0)) == 1
        date_format = str(params.get('date_format', '%Y%m%d'))
        try:
            x_v1  = _parse_anchor(params.get('x_value_1', '0'), x_is_date, date_format)
            x_v2  = _parse_anchor(params.get('x_value_2', '100'), x_is_date, date_format)
            y_v1  = float(params.get('y_value_1', 1.0))
            y_v2  = float(params.get('y_value_2', 0.0))
        except ValueError as e:
            send_notification(f"Axis Calibration: bad calibration value ({e})", level='error', notif_id=_NOTIF)
            return {}

        x_col = str(params.get('x_col', 'x'))
        y_col = str(params.get('y_col', 'y'))

        records = []
        for p in points:
            if not isinstance(p, dict) or 'x' not in p or 'y' not in p:
                continue
            x_val = _pixel_to_value(float(p['x']), x_px1, x_v1, x_px2, x_v2)
            y_val = _pixel_to_value(float(p['y']), y_px1, y_v1, y_px2, y_v2)
            records.append({x_col: _format_value(x_val, x_is_date, date_format), y_col: round(y_val, 6)})

        df = pd.DataFrame.from_records(records)
        send_notification(f"Axis Calibration: {len(df)} rows calibrated", level='info', notif_id=_NOTIF)
        return {'data': df}
