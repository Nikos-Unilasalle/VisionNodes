"""
geo_gsw_monthly.py — JRC Global Surface Water MonthlyHistory as a DATED reference mask.

Why a dated reference matters
-----------------------------
Scoring a prediction made from a single acquisition against an ANNUAL reference is an
estimand error, not a detail. ESA WorldCover class 80 encodes *permanent* water bodies for
a whole year, so seasonal water that the prediction correctly finds is counted as a false
positive, and a shoreline that moved between the reference year and the acquisition is
counted as error. JRC GSW MonthlyHistory is resolved per calendar month, so it can be
matched to the month the imagery was taken.

Band semantics (the trap)
-------------------------
The `water` band is TERNARY::

    0 = not observed (cloud, gap, no Landsat overpass)
    1 = land
    2 = water

Treating 0 as land silently turns missing observations into false negatives. This node
therefore emits the water mask and a separate **validity** mask; downstream metrics must
restrict their evaluation domain to valid pixels.

Coverage and resolution caveats
-------------------------------
* MonthlyHistory spans **1984-03 to 2021-12** only. Imagery outside that window cannot be
  matched and the node fails loudly rather than returning a plausible wrong mask.
* GSW is Landsat-derived at **30 m**. Resampled onto a 10 m Sentinel-2 grid it is a
  coarse reference: fine for area comparison, weak for boundary metrics on narrow
  channels. Pair it with a 10 m annual product and report the disagreement between the
  two as an empirical bound on reference error.

With `auto_date` on (the default) the month is taken from the input raster's own date
metadata, so the reference cannot silently drift away from the imagery.
"""
from __future__ import annotations

import io
import re

import cv2
import ee
import numpy as np
import requests

from registry import vision_node, NodeProcessor

_COLLECTION = 'JRC/GSW1_4/MonthlyHistory'
_COVERAGE_FIRST = (1984, 3)
_COVERAGE_LAST = (2021, 12)

_CODE_UNOBSERVED = 0
_CODE_LAND = 1
_CODE_WATER = 2

_WATER_COLOR = (255, 96, 0)        # BGR — water overlay
_GAP_COLOR = (0, 215, 255)         # BGR — unobserved overlay
_REQUEST_TIMEOUT_S = 30
_DATE_RE = re.compile(r'(\d{4})-(\d{2})')


@vision_node(
    type_id='geo_gsw_monthly',
    label='GSW Monthly Water',
    category='geography',
    icon='CalendarRange',
    description=(
        "JRC Global Surface Water MonthlyHistory: a water reference mask for ONE calendar "
        "month, fetched on the input raster's grid.\n\n"
        "Use it instead of an annual land-cover class when the prediction comes from a "
        "single acquisition — an annual 'permanent water' reference scores correctly "
        "detected seasonal water as a false positive.\n\n"
        "The source band is ternary (0 = not observed, 1 = land, 2 = water), so the node "
        "outputs a separate VALID mask. Restrict metrics to valid pixels, otherwise "
        "missing observations become false negatives.\n\n"
        "Coverage 1984-03 → 2021-12, 30 m (Landsat-derived): coarse for boundary metrics "
        "on narrow channels. With Auto date on, the month follows the input imagery."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'Target grid (+ date)'}],
    outputs=[
        {'id': 'mask',    'color': 'mask',   'label': 'Water mask'},
        {'id': 'valid',   'color': 'mask',   'label': 'Observed mask (exclude gaps)'},
        {'id': 'overlay', 'color': 'image',  'label': 'Viz Overlay'},
        {'id': 'stats',   'color': 'dict',   'label': 'Fractions / date used'},
        {'id': 'meta',    'color': 'string', 'label': 'Status'},
    ],
    params=[
        {'id': 'auto_date', 'label': 'Auto date from input imagery', 'type': 'bool',
         'default': True},
        {'id': 'year', 'label': 'Year', 'type': 'int', 'default': 2021,
         'min': _COVERAGE_FIRST[0], 'max': _COVERAGE_LAST[0], 'step': 1,
         'show_if': {'param': 'auto_date', 'value': False}},
        {'id': 'month', 'label': 'Month', 'type': 'int', 'default': 9,
         'min': 1, 'max': 12, 'step': 1,
         'show_if': {'param': 'auto_date', 'value': False}},
        {'id': 'gcp_project', 'label': 'Manual Project ID', 'type': 'string', 'default': ''},
        {'id': 'opacity', 'label': 'Overlay Opacity', 'type': 'float', 'default': 0.5,
         'min': 0.0, 'max': 1.0},
        {'id': 'node_note', 'label': 'Note', 'type': 'string', 'default': ''},
    ],
    resizable=True, min_width=240, min_height=140,
)
class GswMonthlyNode(NodeProcessor):
    """Fetch one month of JRC GSW water history onto the input raster's grid."""

    # ---- pure helpers (unit-testable without GEE) ----------------------------

    @staticmethod
    def _decode(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Split the ternary `water` band into (water mask, validity mask), both 0/255."""
        water = (raw == _CODE_WATER).astype(np.uint8) * 255
        valid = (raw != _CODE_UNOBSERVED).astype(np.uint8) * 255
        return water, valid

    @staticmethod
    def _parse_year_month(dates: str | None) -> tuple[int, int] | None:
        """First YYYY-MM found in a raster's date metadata, or None."""
        if not dates:
            return None
        match = _DATE_RE.search(str(dates))
        if not match:
            return None
        year, month = int(match.group(1)), int(match.group(2))
        return (year, month) if 1 <= month <= 12 else None

    @staticmethod
    def _in_coverage(year: int, month: int) -> bool:
        return _COVERAGE_FIRST <= (year, month) <= _COVERAGE_LAST

    @staticmethod
    def _roi(geo: dict, width: int, height: int):
        transform = geo['transform']
        # Loaders hand back whatever their backend produced: the STAC path stores a
        # rasterio CRS object, and Earth Engine cannot encode it
        # ("EEException: Cannot encode object: EPSG:32631"), silently returning no mask.
        crs = str(geo.get('crs') or 'EPSG:4326')
        x_min, y_max = transform[2], transform[5]
        x_max = x_min + width * transform[0]
        y_min = y_max + height * transform[4]
        west, east = min(x_min, x_max), max(x_min, x_max)
        south, north = min(y_min, y_max), max(y_min, y_max)
        return ee.Geometry.Rectangle([west, south, east, north], crs, False), crs

    # ---- failure shape -------------------------------------------------------

    @staticmethod
    def _fail(message: str) -> dict:
        return {'mask': None, 'valid': None, 'overlay': None, 'stats': {},
                'meta': message}

    # ---- overlay -------------------------------------------------------------

    @staticmethod
    def _overlay(geo: dict, water: np.ndarray, valid: np.ndarray,
                 opacity: float) -> np.ndarray:
        background = geo['bands'][0]
        norm = cv2.normalize(background, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        base = cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)
        painted = base.copy()
        painted[valid == 0] = _GAP_COLOR
        painted[water > 0] = _WATER_COLOR
        return cv2.addWeighted(base, 1.0 - opacity, painted, opacity, 0)

    # ---- engine entry point -------------------------------------------------

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None or 'bands' not in geo or geo.get('transform') is None:
            return self._fail('No georeferenced GeoTIFF connected')

        project_id = geo.get('_gcp_project') or params.get('gcp_project') or ''
        try:
            ee.Initialize(project=project_id) if project_id else ee.Initialize()
        except Exception as exc:
            return self._fail(f'GEE Init Error: {exc}')

        # Resolve the month. Auto mode keeps the reference locked to the imagery.
        if bool(params.get('auto_date', True)):
            parsed = self._parse_year_month(geo.get('_dates'))
            if parsed is None:
                return self._fail('Auto date: no YYYY-MM in the raster metadata — '
                                  'set the month manually')
            year, month = parsed
        else:
            year, month = int(params.get('year', 2021)), int(params.get('month', 9))

        if not self._in_coverage(year, month):
            return self._fail(
                f'{year}-{month:02d} is outside GSW MonthlyHistory coverage '
                f'({_COVERAGE_FIRST[0]}-{_COVERAGE_FIRST[1]:02d} to '
                f'{_COVERAGE_LAST[0]}-{_COVERAGE_LAST[1]:02d}) — use imagery inside that '
                f'window, or a different reference')

        height, width = geo['bands'][0].shape[:2]
        try:
            roi, crs = self._roi(geo, width, height)
            start = f'{year}-{month:02d}-01'
            end = f'{year + (month // 12)}-{(month % 12) + 1:02d}-01'
            image = (ee.ImageCollection(_COLLECTION)
                     .filterDate(start, end)
                     .first())
            if image is None:
                return self._fail(f'No GSW image for {year}-{month:02d}')

            url = ee.Image(image).select('water').clip(roi).getDownloadURL({
                'dimensions': [width, height],
                'crs': crs,
                'region': roi,
                'format': 'NPY',
            })
            response = requests.get(url, timeout=_REQUEST_TIMEOUT_S)
            if response.status_code != 200:
                return self._fail(f'GEE Error: {response.text[:100]}')

            raw = np.load(io.BytesIO(response.content))
            if raw.dtype.names:
                raw = raw[raw.dtype.names[0]]
            if raw is None or raw.size == 0:
                return self._fail('Received empty data from GEE')
            if raw.ndim == 3:
                raw = raw[0]

            water, valid = self._decode(raw)
            if water.shape != (height, width):
                water = cv2.resize(water, (width, height), interpolation=cv2.INTER_NEAREST)
                valid = cv2.resize(valid, (width, height), interpolation=cv2.INTER_NEAREST)

            n_px = water.size
            n_valid = int(np.count_nonzero(valid))
            n_water = int(np.count_nonzero(water))
            stats = {
                'year': year,
                'month': month,
                'collection': _COLLECTION,
                'native_resolution_m': 30,
                'valid_fraction': round(n_valid / n_px, 5) if n_px else 0.0,
                'water_fraction_of_valid': round(n_water / n_valid, 5) if n_valid else 0.0,
                'water_fraction_of_scene': round(n_water / n_px, 5) if n_px else 0.0,
                'n_water_px': n_water,
                'n_valid_px': n_valid,
            }
            overlay = self._overlay(geo, water, valid,
                                    float(params.get('opacity', 0.5)))
            gap_warning = '' if stats['valid_fraction'] > 0.9 else \
                f" WARNING: only {stats['valid_fraction']:.1%} of the scene was observed"
            return {
                'mask': water,
                'valid': valid,
                'overlay': overlay,
                'stats': stats,
                'meta': (f"OK {year}-{month:02d}: {n_water} water px, "
                         f"{stats['valid_fraction']:.1%} observed.{gap_warning}"),
            }
        except Exception as exc:
            import traceback
            print(traceback.format_exc())
            return self._fail(f'Runtime Error: {str(exc)[:80]}')
