"""Tests for generic nodes added for the RootScan-equivalent template."""
import importlib.util
import os
import sys

import cv2
import numpy as np
import pytest

_ENGINE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ENGINE)
from registry import NODE_CLASS_REGISTRY, NODE_SCHEMAS  # noqa: E402

for _p in ('feat_peak_markers', 'mask_depth_bands', 'sci_zone_stats', 'dict_scale', 'sci_scale_bar_detect',
           'dict_report_panel'):
    _path = os.path.join(_ENGINE, 'plugins', f'{_p}.py')
    _spec = importlib.util.spec_from_file_location(f'plugins.{_p}', _path)
    _spec.loader.exec_module(importlib.util.module_from_spec(_spec))


def _node(t):
    return NODE_CLASS_REGISTRY[t]()


def _inputs(t):
    return [p['id'] for p in next(s for s in NODE_SCHEMAS if s['type'] == t)['inputs']]


# ── Local Maxima Markers ─────────────────────────────────────────────────────

class TestPeakMarkers:
    def _blobs(self):
        img = np.zeros((120, 200), np.uint8)
        for x in (30, 90, 150):
            cv2.circle(img, (x, 60), 18, 220, -1)
        return img

    def test_one_marker_per_bright_blob(self):
        out = _node('feat_peak_markers').process({'image': self._blobs()}, {'sigma': 3, 'min_distance': 10})
        assert out['count'] == 3
        assert out['markers'].max() == 3 and out['markers'].dtype == np.int32

    def test_mask_restricts_markers(self):
        mask = np.zeros((120, 200), np.uint8)
        mask[:, :60] = 255
        out = _node('feat_peak_markers').process({'image': self._blobs(), 'mask': mask}, {'sigma': 3, 'min_distance': 10})
        assert out['count'] == 1

    def test_minima_mode(self):
        out = _node('feat_peak_markers').process({'image': 255 - self._blobs()},
                                                 {'sigma': 3, 'min_distance': 10, 'polarity': 1})
        assert out['count'] == 3

    def test_sigma_and_distance_ports(self):
        assert {'sigma', 'min_distance'} <= set(_inputs('feat_peak_markers'))


# ── Mask Depth Bands ─────────────────────────────────────────────────────────

class TestDepthBands:
    def _rings(self):
        outer = np.zeros((201, 201), np.uint8)
        cv2.circle(outer, (100, 100), 90, 255, -1)
        inner = np.zeros_like(outer)
        cv2.circle(inner, (100, 100), 30, 255, -1)
        return inner, outer

    def test_depth_goes_from_inner_to_outer(self):
        inner, outer = self._rings()
        out = _node('mask_depth_bands').process({'inner': inner, 'outer': outer}, {'bands': 3})
        d = out['depth']
        assert d[100, 100 + 32] < 0.1 and d[100, 100 + 88] > 0.9
        assert abs(d[100, 100 + 60] - 0.5) < 0.05
        assert set(np.unique(out['bands'])) == {0, 1, 2, 3}

    def test_image_border_is_not_an_edge(self):
        inner, outer = self._rings()
        outer = outer.copy()
        outer[:, 150:] = 0          # section truncated by the frame on the right
        outer = outer[:, :150]
        inner = inner[:, :150]
        out = _node('mask_depth_bands').process({'inner': inner, 'outer': outer},
                                                {'bands': 3, 'ignore_border': True})
        # A pixel near the right frame edge but far from the true rim stays mid-depth
        assert out['depth'][100, 145] < 0.9

    def test_band_range_mask(self):
        inner, outer = self._rings()
        out = _node('mask_depth_bands').process({'inner': inner, 'outer': outer},
                                                {'bands': 3, 'range_low': 0.2, 'range_high': 0.8})
        m = out['range_mask']
        assert m[100, 100 + 60] == 255 and m[100, 100 + 33] == 0 and m[100, 100 + 88] == 0


# ── Zone Region Stats ────────────────────────────────────────────────────────

def test_zone_stats_assigns_regions_by_centroid():
    labels = np.zeros((60, 90), np.int32)
    labels[5:15, 5:15] = 1       # zone 1, area 100
    labels[5:25, 35:45] = 2      # zone 2, area 200
    labels[40:50, 35:45] = 3     # zone 2, area 100
    zones = np.zeros((60, 90), np.int32)
    zones[:, :30] = 1
    zones[:, 30:60] = 2
    zones[:, 60:] = 3
    out = _node('sci_zone_stats').process({'regions': labels, 'zones': zones}, {'min_area': 0})
    assert out['counts'] == [1, 2, 0]
    assert out['mean_areas'] == [100.0, 150.0, 0.0]
    assert out['total_count'] == 3 and out['stats']['zone_2_mean_area'] == 150.0


def test_zone_stats_without_zones_counts_all():
    labels = np.zeros((20, 20), np.int32)
    labels[2:5, 2:5] = 1
    labels[10:12, 10:12] = 2
    out = _node('sci_zone_stats').process({'regions': labels}, {'min_area': 5})
    assert out['total_count'] == 1


# ── Scale Dict Values ────────────────────────────────────────────────────────

def test_dict_scale_divides_by_factor_power():
    d = {'RXSA': 1_000_000.0, 'label': 'x', 'n': 3}
    out = _node('dict_scale').process({'dict': d, 'factor': 1000.0}, {'operation': 1, 'power': 2, 'skip_keys': 'n'})
    assert out['dict']['RXSA'] == pytest.approx(1.0)
    assert out['dict']['label'] == 'x' and out['dict']['n'] == 3


# ── Scale Bar Detect ─────────────────────────────────────────────────────────

class TestScaleBar:
    def test_detects_white_bar_on_dark(self):
        img = np.zeros((400, 600, 3), np.uint8)
        cv2.circle(img, (250, 180), 150, (120, 120, 120), -1)
        cv2.rectangle(img, (440, 370), (580, 373), (255, 255, 255), -1)   # 141 px bar
        out = _node('sci_scale_bar_detect').process({'image': img}, {'bar_length': 200, 'unit': 0})
        assert out['length_px'] == pytest.approx(141, abs=2)
        assert out['px_per_mm'] == pytest.approx(141 / 0.2, rel=0.02)

    def test_detects_dark_bar_on_light(self):
        img = np.full((400, 600), 230, np.uint8)
        cv2.rectangle(img, (400, 380), (560, 383), 20, -1)                # 161 px bar
        out = _node('sci_scale_bar_detect').process({'image': img}, {'bar_length': 500, 'unit': 0})
        assert out['length_px'] == pytest.approx(161, abs=2)

    def test_no_bar_returns_none(self):
        img = np.random.default_rng(0).integers(0, 255, (200, 200), dtype=np.uint8)
        out = _node('sci_scale_bar_detect').process({'image': img}, {'bar_length': 100, 'unit': 0})
        assert out['px_per_mm'] is None


# ── Report Panel ─────────────────────────────────────────────────────────────

def test_report_panel_groups_and_orders_keys():
    d = {'b': 2.0, 'a': 1.0, 'c': 3.0, 'extra': 9}
    out = _node('dict_report_panel').process({'dict': d}, {'groups': 'First: a, b\nSecond: c, missing'})
    assert list(out['report'].keys())[:3] == ['a', 'b', 'c']
    assert out['groups'] == [{'label': 'First', 'keys': ['a', 'b']}, {'label': 'Second', 'keys': ['c', 'missing']}]
    assert out['report']['extra'] == 9


def test_report_panel_merges_multiple_dicts():
    out = _node('dict_report_panel').process({'dict': {'a': 1}, 'dict_2': {'b': 2}}, {'groups': ''})
    assert out['report'] == {'a': 1, 'b': 2}


# ── Watershed — boundaries mask output ───────────────────────────────────────

def test_watershed_outputs_boundary_mask():
    _path = os.path.join(_ENGINE, 'plugins', 'watershed_analysis.py')
    _spec = importlib.util.spec_from_file_location('plugins.watershed_analysis', _path)
    _spec.loader.exec_module(importlib.util.module_from_spec(_spec))
    img = np.full((60, 120, 3), 200, np.uint8)
    img[:, 58:62] = 30                       # dark wall between two cells
    markers = np.zeros((60, 120), np.int32)
    markers[30, 20] = 1
    markers[30, 100] = 2
    out = _node('feat_watershed').process({'image': img, 'markers': markers}, {})
    b = out['boundaries']
    assert b.dtype == np.uint8 and b.shape == (60, 120)
    assert b[:, 55:65].max() == 255 and b[:, :40].max() == 0


# ── Scale Bar Detect — manual source (line drawn with Visual Calibration) ────

def _bar_image():
    img = np.full((400, 600), 230, np.uint8)
    cv2.rectangle(img, (400, 380), (560, 383), 20, -1)        # 161 px bar
    return img


def test_scale_bar_manual_source_uses_drawn_calibration():
    out = _node('sci_scale_bar_detect').process({'image': _bar_image(), 'manual_px_per_mm': 812.5},
                                                {'bar_length': 500, 'unit': 0, 'source': 1})
    assert out['px_per_mm'] == pytest.approx(812.5)
    assert out['px_per_um'] == pytest.approx(0.8125)


def test_scale_bar_manual_without_line_falls_back_to_detection():
    # Visual Calibration outputs 1.0 when no line is drawn: not a usable calibration
    out = _node('sci_scale_bar_detect').process({'image': _bar_image(), 'manual_px_per_mm': 1.0},
                                                {'bar_length': 500, 'unit': 0, 'source': 1})
    assert out['px_per_mm'] == pytest.approx(161 / 0.5, rel=0.02)


def test_scale_bar_auto_source_ignores_manual_input():
    out = _node('sci_scale_bar_detect').process({'image': _bar_image(), 'manual_px_per_mm': 812.5},
                                                {'bar_length': 500, 'unit': 0, 'source': 0})
    assert out['px_per_mm'] == pytest.approx(161 / 0.5, rel=0.02)
