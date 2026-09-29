"""Tests for the generic nodes backing the Root Anatomy template rewrite.

New nodes: filter_local_stats, filter_dog, filter_auto_polarity, mask_keep_largest.
Extended nodes: feat_threshold_adv (mask/offset/value), sci_calibration (factor port),
util_csv_export (dict inputs flattened into columns).
"""
import csv
import importlib.util
import os
import sys
import tempfile

import cv2
import numpy as np
import pytest

_ENGINE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ENGINE)

from registry import NODE_CLASS_REGISTRY, NODE_SCHEMAS  # noqa: E402


def _load(name):
    path = os.path.join(_ENGINE, 'plugins', f'{name}.py')
    spec = importlib.util.spec_from_file_location(f'plugins.{name}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


for _p in ('filter_local_stats', 'filter_dog', 'filter_auto_polarity',
           'mask_keep_largest', 'watershed_analysis', 'sci_calibration', 'csv_export',
           'blob_filter', 'list_natural_break', 'mask_select_by_marker'):
    _load(_p)


def _node(type_id):
    return NODE_CLASS_REGISTRY[type_id]()


def _schema(type_id):
    return next(s for s in NODE_SCHEMAS if s['type'] == type_id)


def _disk(h=200, w=200, r=60, cx=100, cy=100):
    m = np.zeros((h, w), np.uint8)
    cv2.circle(m, (cx, cy), r, 255, -1)
    return m


# ── Local Statistics ─────────────────────────────────────────────────────────

class TestLocalStats:
    def test_std_is_high_on_texture_and_zero_on_flat(self):
        # Arrange: left half flat, right half checkerboard texture
        img = np.full((100, 200), 128, np.uint8)
        img[:, 100:] = ((np.indices((100, 100)).sum(axis=0) % 2) * 255).astype(np.uint8)
        # Act
        out = _node('filter_local_stats').process({'image': img}, {'statistic': 1, 'window': 7})
        # Assert
        main = out['main']
        assert main.dtype == np.uint8 and main.shape == img.shape
        assert main[50, 20] == 0
        assert main[50, 150] > 200

    def test_mean_matches_box_filter(self):
        img = np.random.default_rng(0).integers(0, 255, (50, 50), dtype=np.uint8)
        out = _node('filter_local_stats').process({'image': img}, {'statistic': 0, 'window': 5})
        ref = cv2.blur(img.astype(np.float32), (5, 5))
        np.testing.assert_allclose(out['raw'], ref, atol=1e-3)

    def test_color_input_is_converted_to_gray(self):
        img = np.zeros((40, 40, 3), np.uint8)
        out = _node('filter_local_stats').process({'image': img}, {'statistic': 1, 'window': 5})
        assert out['main'].ndim == 2

    def test_none_input_returns_none(self):
        out = _node('filter_local_stats').process({}, {})
        assert out['main'] is None


# ── Difference of Gaussians ─────────────────────────────────────────────────

class TestDoG:
    def test_band_energy_responds_to_matching_scale(self):
        # Fine texture (period 4px) on the left, coarse texture (period 32px) on the right
        yy, xx = np.indices((128, 256))
        fine = ((xx // 2) % 2) * 255
        coarse = ((xx // 16) % 2) * 255
        img = np.where(xx < 128, fine, coarse).astype(np.uint8)
        out = _node('filter_dog').process({'image': img}, {'sigma': 6.0, 'ratio': 2.0, 'output': 0})
        raw = out['raw']
        assert raw[64, 40:90].mean() < raw[64, 170:220].mean()

    def test_sigma_input_port_exists_for_param_externalization(self):
        ids = [p['id'] for p in _schema('filter_dog')['inputs']]
        assert 'sigma' in ids

    def test_signed_output_centered_on_flat_image(self):
        img = np.full((50, 50), 90, np.uint8)
        out = _node('filter_dog').process({'image': img}, {'sigma': 2.0, 'ratio': 2.0, 'output': 1})
        assert np.allclose(out['raw'], 0, atol=1e-3)
        assert out['main'].dtype == np.uint8

    def test_invalid_sigma_is_clamped(self):
        img = np.zeros((20, 20), np.uint8)
        out = _node('filter_dog').process({'image': img}, {'sigma': -3, 'ratio': 0.5, 'output': 0})
        assert out['main'] is not None


# ── Auto Polarity ────────────────────────────────────────────────────────────

class TestAutoPolarity:
    def test_dark_background_is_inverted_to_bright(self):
        img = np.zeros((200, 200), np.uint8)
        img[_disk() > 0] = 200
        out = _node('filter_auto_polarity').process({'image': img}, {'target': 0, 'border_pct': 5})
        assert out['inverted'] is True
        assert out['main'][0, 0] == 255

    def test_bright_background_is_untouched(self):
        img = np.full((200, 200), 230, np.uint8)
        img[_disk() > 0] = 60
        out = _node('filter_auto_polarity').process({'image': img}, {'target': 0, 'border_pct': 5})
        assert out['inverted'] is False
        np.testing.assert_array_equal(out['main'], img)

    def test_foreground_mask_defines_background(self):
        # Background bright in the mask sense even though the border is dark
        img = np.zeros((200, 200), np.uint8)
        fg = _disk()
        img[fg == 0] = 20
        img[fg > 0] = 220
        out = _node('filter_auto_polarity').process(
            {'image': img, 'mask': fg}, {'target': 1, 'border_pct': 5})
        assert out['inverted'] is False

    def test_color_image_keeps_channels(self):
        img = np.zeros((60, 60, 3), np.uint8)
        out = _node('filter_auto_polarity').process({'image': img}, {'target': 0, 'border_pct': 5})
        assert out['main'].shape == img.shape


# ── Keep Largest Blobs ───────────────────────────────────────────────────────

class TestKeepLargest:
    def _mask(self):
        m = np.zeros((200, 200), np.uint8)
        cv2.circle(m, (50, 50), 30, 255, -1)    # large
        cv2.circle(m, (150, 150), 20, 255, -1)  # medium
        cv2.circle(m, (150, 40), 5, 255, -1)    # small
        return m

    def test_keeps_only_largest(self):
        out = _node('mask_keep_largest').process({'mask': self._mask()}, {'count': 1})
        m = out['mask']
        assert m[50, 50] == 255 and m[150, 150] == 0 and m[40, 150] == 0
        assert out['count'] == 1
        assert out['area_px'] == int((m > 0).sum())

    def test_keeps_n_largest(self):
        out = _node('mask_keep_largest').process({'mask': self._mask()}, {'count': 2})
        m = out['mask']
        assert m[50, 50] == 255 and m[150, 150] == 255 and m[40, 150] == 0
        assert out['count'] == 2

    def test_empty_mask(self):
        out = _node('mask_keep_largest').process({'mask': np.zeros((10, 10), np.uint8)}, {'count': 1})
        assert out['count'] == 0 and out['mask'].max() == 0


# ── Threshold (Advanced) — mask + offset ─────────────────────────────────────

class TestThresholdAdvMasked:
    def _img(self):
        # Outside the mask: very bright; inside: two populations 50 / 150
        img = np.full((100, 100), 250, np.uint8)
        img[20:80, 20:50] = 50
        img[20:80, 50:80] = 150
        mask = np.zeros_like(img)
        mask[20:80, 20:80] = 255
        return img, mask

    def test_otsu_is_computed_inside_mask_only(self):
        img, mask = self._img()
        out = _node('feat_threshold_adv').process({'image': img, 'mask': mask}, {'mode': 2})
        m = out['mask']
        assert m[50, 30] == 0 and m[50, 60] == 255
        assert m[5, 5] == 0  # outside mask is always 0
        assert 50 <= out['value'] < 150

    def test_offset_shifts_auto_threshold(self):
        img, mask = self._img()
        base = _node('feat_threshold_adv').process({'image': img, 'mask': mask}, {'mode': 2})['value']
        shifted = _node('feat_threshold_adv').process(
            {'image': img, 'mask': mask}, {'mode': 2, 'offset': -10})['value']
        assert shifted == base - 10

    def test_without_mask_behaviour_unchanged(self):
        img, _ = self._img()
        out = _node('feat_threshold_adv').process({'image': img}, {'mode': 2})
        _, ref = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        np.testing.assert_array_equal(out['mask'], ref)


# ── Unit Calibration — factor port ──────────────────────────────────────────

def test_calibration_exposes_factor_port():
    ids = [p['id'] for p in _schema('sci_calibration')['inputs']]
    assert 'factor' in ids


def test_calibration_area_conversion():
    out = _node('sci_calibration').process({'input': 400.0}, {'factor': 20.0, 'dimension': 'Area'})
    assert out['main'] == pytest.approx(1.0)


# ── CSV Export — dict inputs become columns ─────────────────────────────────

def test_csv_snapshot_flattens_dict_input():
    with tempfile.TemporaryDirectory() as d:
        node = _node('util_csv_export')
        params = {'snapshot': 1, 'filename': 'rep', 'path': d, 'auto_timestamp': False}
        node.process({'report_0': {'RXSA': 1.5, 'TSA': 0.3}, 'note': 'x'}, params)
        with open(os.path.join(d, 'rep.csv')) as fh:
            rows = list(csv.reader(fh))
        assert rows[0][1:] == ['RXSA', 'TSA', 'note']
        assert float(rows[1][1]) == pytest.approx(1.5)


# ── Threshold (Advanced) — Triangle (dominant background peak) ─────────────

class TestThresholdTriangle:
    def _img(self):
        # Large flat bright background (peak) + darker objects of varying tone
        img = np.full((200, 200), 228, np.uint8)
        img[50:150, 20:80] = 170    # pale, out-of-focus tissue
        img[50:150, 120:180] = 90   # dark tissue
        return img

    def test_triangle_inv_keeps_everything_darker_than_background(self):
        out = _node('feat_threshold_adv').process({'image': self._img()}, {'mode': 6, 'offset': -10})
        m = out['mask']
        assert m[100, 50] == 255 and m[100, 150] == 255 and m[10, 10] == 0

    def test_triangle_bright_objects_on_dark_background(self):
        img = 255 - self._img()
        out = _node('feat_threshold_adv').process({'image': img}, {'mode': 5, 'offset': 10})
        m = out['mask']
        assert m[100, 50] == 255 and m[100, 150] == 255 and m[10, 10] == 0


# ── Blob Filter — min_area port ──────────────────────────────────────────────

def test_blob_filter_min_area_is_externalizable():
    ids = [p['id'] for p in _schema('filter_blob_filter')['inputs']]
    assert 'min_area' in ids


# ── Auto Polarity — histogram peak method ────────────────────────────────────

class TestAutoPolarityPeak:
    def test_section_touching_border_is_not_inverted(self):
        # Dark tissue covers 3 borders; bright background is still the dominant tone
        rng = np.random.default_rng(1)
        img = np.full((200, 200), 228, np.uint8)
        img[:, 60:] = rng.integers(40, 200, (200, 140), dtype=np.uint8)  # textured tissue
        out = _node('filter_auto_polarity').process({'image': img}, {'target': 0, 'method': 1})
        assert out['inverted'] is False

    def test_fluorescence_is_inverted(self):
        img = np.full((200, 200), 10, np.uint8)
        img[40:160, 40:160] = 200
        out = _node('filter_auto_polarity').process({'image': img}, {'target': 0, 'method': 1})
        assert out['inverted'] is True


# ── List Natural Break ───────────────────────────────────────────────────────

class TestListNaturalBreak:
    def test_splits_two_populations(self):
        values = [220, 250, 300, 280, 400, 500, 640, 700, 1100, 1500, 2600, 3400, 4000]
        out = _node('list_natural_break').process({'values': values}, {'log_scale': True})
        assert 700 < out['threshold'] <= 1100
        assert out['count_above'] == 5 and out['count_below'] == 8

    def test_min_value_floor_ignores_noise(self):
        values = [1, 2, 3, 500, 600, 5000, 6000]
        out = _node('list_natural_break').process({'values': values}, {'log_scale': True, 'min_value': 100})
        assert 600 < out['threshold'] <= 5000

    def test_empty_or_single_value(self):
        assert _node('list_natural_break').process({'values': []}, {})['threshold'] is None
        out = _node('list_natural_break').process({'values': [5.0]}, {})
        assert out['count_above'] + out['count_below'] == 1


def test_natural_break_min_value_is_externalizable():
    ids = [p['id'] for p in _schema('list_natural_break')['inputs']]
    assert 'min_value' in ids


# ── Select Blobs by Marker (morphological reconstruction) ─────────────────────

class TestSelectByMarker:
    def _mask(self):
        m = np.zeros((100, 100), np.uint8)
        cv2.circle(m, (25, 25), 15, 255, -1)
        cv2.circle(m, (75, 75), 15, 255, -1)
        marker = np.zeros_like(m)
        marker[70:73, 70:73] = 255   # touches only the second blob
        return m, marker

    def test_keeps_whole_blobs_touched_by_marker(self):
        m, marker = self._mask()
        out = _node('mask_select_by_marker').process({'mask': m, 'marker': marker}, {'mode': 0})
        assert out['mask'][75, 75] == 255 and out['mask'][88, 75] == 255  # whole blob restored
        assert out['mask'][25, 25] == 0
        assert out['count'] == 1

    def test_remove_mode_drops_marked_blobs(self):
        m, marker = self._mask()
        out = _node('mask_select_by_marker').process({'mask': m, 'marker': marker}, {'mode': 1})
        assert out['mask'][25, 25] == 255 and out['mask'][75, 75] == 0

    def test_missing_marker_passes_mask_through(self):
        m, _ = self._mask()
        out = _node('mask_select_by_marker').process({'mask': m}, {'mode': 0})
        assert np.array_equal(out['mask'] > 0, m > 0)
