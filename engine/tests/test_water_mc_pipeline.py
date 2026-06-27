"""
test_water_mc_pipeline.py — End-to-end composition test for the Monte-Carlo
probabilistic water-masking pipeline, built ENTIRELY from generic nodes:

    geo_raster_noise → geo_spectral_indices → geo_band_calc (k-of-4 vote)
      → geotiff_to_mask → sci_frame_accumulator (Running Mean = probability)

No bespoke water node is involved — this is the reproducibility contract for the
study. Repeated ticks through the stochastic noise node form the MC ensemble; the
accumulator mean over N ticks is the calibrated per-pixel water probability.
"""
import sys
import os
import importlib.util
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
_PLUGINS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins')


def _load(modname):
    path = os.path.join(_PLUGINS, f'{modname}.py')
    spec = importlib.util.spec_from_file_location(f'plugins.{modname}', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f'plugins.{modname}'] = mod
    spec.loader.exec_module(mod)
    return mod


noise_mod   = _load('geo_raster_noise')
indices_mod = _load('geo_spectral_indices')
calc_mod    = _load('geo_band_calc')
tomask_mod  = _load('geotiff_to_mask')
accum_mod   = _load('sci_frame_accumulator')


def _synthetic_scene():
    """6-band reflectance scene [Blue, Green, Red, NIR, SWIR1, SWIR2], water on the left half."""
    H, W = 32, 32
    bands = np.zeros((6, H, W), dtype=np.float32)
    # land / vegetation (high NIR & SWIR)
    land = [0.05, 0.06, 0.04, 0.45, 0.30, 0.25]
    # water (low NIR & SWIR, higher green)
    water = [0.06, 0.08, 0.05, 0.02, 0.01, 0.01]
    for b in range(6):
        bands[b, :, :] = land[b]
        bands[b, :, :W // 2] = water[b]   # left half is water
    geo = {'bands': bands, 'count': 6,
           'band_names': ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'],
           'crs': None, 'transform': None, 'nodata': None, 'dtype': 'float32'}
    water_mask = np.zeros((H, W), dtype=bool)
    water_mask[:, :W // 2] = True
    return geo, water_mask


# Param sets mirroring the example .vn graph
_IDX_PARAMS = {
    'sensor': 0, 'nir_band': 4, 'red_band': 3, 'green_band': 2, 'blue_band': 1, 'swir_band': 5,
    'ndvi': False, 'ndwi': True, 'evi': False, 'mndwi': True, 'nbr': False, 'bsi': False,
    'expr1_enable': True, 'expr1_label': 'AWEInsh', 'expr1': '4*(GREEN - SWIR) - (0.25*NIR + 2.75*B6)',
    'expr2_enable': True, 'expr2_label': 'AWEIsh',  'expr2': 'BLUE + 2.5*GREEN - 1.5*(NIR + SWIR) - 0.25*B6',
    'colormap': 0, 'clamp_min': -5.0, 'clamp_max': 5.0,
}
# NB: 1*(...) forces integer arithmetic — numpy '+' on boolean arrays is logical OR, not a count.
_VOTE_PARAMS = {'expression': '(1*(B1>0)+1*(B2>0)+1*(B3>0)+1*(B4>0)) >= 2', 'clamp_min': 0.0,
                'clamp_max': 1.0, 'colormap': 'gray'}
_TOMASK_PARAMS = {'band_index': 0, 'threshold': 0.5}


def _one_tick(geo, noise_node, idx_node, vote_node, tomask_node, noise_params):
    perturbed = noise_node.process({'geotiff': geo}, noise_params)['geotiff']
    stack = idx_node.process({'geotiff': perturbed}, _IDX_PARAMS)['stack']
    assert stack['band_names'] == ['NDWI', 'MNDWI', 'AWEInsh', 'AWEIsh']
    vote = vote_node.process({'geotiff': stack}, _VOTE_PARAMS)['raw']
    mask = tomask_node.process({'geotiff': vote}, _TOMASK_PARAMS)['mask']
    return mask


def test_deterministic_consensus_no_noise():
    """With σ=0 the 4-index consensus must perfectly separate water from land."""
    geo, truth = _synthetic_scene()
    mask = _one_tick(
        geo, noise_mod.RasterNoiseNode(), indices_mod.SpectralIndicesNode(),
        calc_mod.BandCalcNode(), tomask_mod.GeoTiffToMaskNode(),
        {'sigma_abs': 0.0, 'sigma_rel': 0.0, 'seed': 0},
    )
    water = mask > 127
    assert np.array_equal(water, truth)


def test_monte_carlo_probability_converges():
    """Over N noisy ticks the accumulator mean yields a calibrated probability:
    ~1 deep in water, ~0 deep in land."""
    geo, truth = _synthetic_scene()
    noise_node  = noise_mod.RasterNoiseNode()
    idx_node    = indices_mod.SpectralIndicesNode()
    vote_node   = calc_mod.BandCalcNode()
    tomask_node = tomask_mod.GeoTiffToMaskNode()
    accum_node  = accum_mod.FrameAccumulatorNode()

    N = 60
    noise_params = {'sigma_abs': 0.02, 'sigma_rel': 0.02, 'seed': 100, 'clip_negative': True}
    prob = None
    for _ in range(N):
        mask = _one_tick(geo, noise_node, idx_node, vote_node, tomask_node, noise_params)
        prob = accum_node.process({'image': mask}, {'mode': 0, 'window': N, 'reset': False})['main']

    prob01 = prob.astype(np.float32) / 255.0
    H, W = truth.shape
    # Deep-water column (far from boundary) → high probability
    assert prob01[:, 2].mean() > 0.9
    # Deep-land column → low probability
    assert prob01[:, -2].mean() < 0.1
    # Probability is a proper [0,1] field
    assert prob01.min() >= 0.0 and prob01.max() <= 1.0


def _gradient_scene():
    """6-band scene with a smooth water→land gradient across columns, so the MC
    water probability sweeps the full 1→0 range and a genuine mid-range band exists."""
    H, W = 16, 48
    water = np.array([0.06, 0.08, 0.05, 0.02, 0.01, 0.01], dtype=np.float32)
    land  = np.array([0.05, 0.06, 0.04, 0.45, 0.30, 0.25], dtype=np.float32)
    t = np.linspace(0.0, 1.0, W, dtype=np.float32)            # 0=water … 1=land
    bands = np.empty((6, H, W), dtype=np.float32)
    for b in range(6):
        row = (1.0 - t) * water[b] + t * land[b]
        bands[b] = np.tile(row, (H, 1))
    return {'bands': bands, 'count': 6,
            'band_names': ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'],
            'crs': None, 'transform': None, 'nodata': None, 'dtype': 'float32'}


def test_uncertainty_peaks_at_decision_boundary():
    """Running-Std (uncertainty) must be maximal where probability ≈ 0.5 (Bernoulli
    variance), and near zero where the consensus is confident — scene-independent."""
    geo = _gradient_scene()
    noise_node  = noise_mod.RasterNoiseNode()
    idx_node    = indices_mod.SpectralIndicesNode()
    vote_node   = calc_mod.BandCalcNode()
    tomask_node = tomask_mod.GeoTiffToMaskNode()
    mean_node   = accum_mod.FrameAccumulatorNode()
    std_node    = accum_mod.FrameAccumulatorNode()

    N = 80
    np_params = {'sigma_abs': 0.0, 'sigma_rel': 0.15, 'seed': 11, 'clip_negative': True}
    prob = std = None
    for _ in range(N):
        mask = _one_tick(geo, noise_node, idx_node, vote_node, tomask_node, np_params)
        prob = mean_node.process({'image': mask}, {'mode': 0, 'window': N})['main'].astype(np.float32) / 255.0
        std  = std_node.process({'image': mask},  {'mode': 3, 'window': N})['main'].astype(np.float32)

    p = prob.ravel()
    s = std.ravel()
    confident = (p < 0.1) | (p > 0.9)
    ambiguous = (p > 0.35) & (p < 0.65)
    assert ambiguous.any(), 'gradient scene should yield a mid-probability band'
    # Uncertainty is high in the ambiguous band and low where the vote is confident.
    assert s[ambiguous].mean() > s[confident].mean() * 3
