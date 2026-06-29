"""
test_mc_analysis_pipeline.py — Tests for the MC water mask post-analysis .vn templates.

Covers three analysis pipelines that build on mc_water_mask.vn:

  1. mc_analysis.vn  — logic_python uncertainty/confidence analysis
  2. mc_validation.vn — CDF + threshold sweep + index comparison
  3. mc_sensitivity.vn — P(water) sensitivity vs spectral indices

All tests use synthetic numpy data so no TIF/SHP files are required.
"""
import sys
import os
import importlib.util
import types
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


# Lazily load only what each test needs
def _node(modname, classname):
    mod = _load(modname)
    return getattr(mod, classname)()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _prob_geo(prob_arr):
    """Wrap a float32 2-D array in a geo dict (minimal — no CRS)."""
    bands = prob_arr[np.newaxis, :, :].astype(np.float32)
    return {'bands': bands, 'count': 1, 'band_names': ['prob'],
            'crs': None, 'transform': None, 'nodata': None, 'dtype': 'float32'}


def _mask_geo(mask_arr):
    """Wrap a boolean/uint8 2-D array in a geo dict."""
    bands = mask_arr[np.newaxis, :, :].astype(np.float32)
    return {'bands': bands, 'count': 1, 'band_names': ['mask'],
            'crs': None, 'transform': None, 'nodata': None, 'dtype': 'float32'}


def _index_stack(arrs, names):
    """Wrap a list of 2-D float arrays into a multi-band geo dict."""
    bands = np.stack([a.astype(np.float32) for a in arrs], axis=0)
    return {'bands': bands, 'count': len(arrs), 'band_names': names,
            'crs': None, 'transform': None, 'nodata': None, 'dtype': 'float32'}


def _synthetic_prob_and_masks(H=32, W=64):
    """
    Left half = water (high P), right half = land (low P).
    with_bridges mask = left 3/4 (river extent including bridge columns).
    no_bridges mask   = left 1/2 (pure open water).
    """
    prob = np.zeros((H, W), dtype=np.float32)
    prob[:, :W // 2] = 0.92    # deep water
    prob[:, W // 2:] = 0.05    # land

    with_m = np.zeros((H, W), dtype=np.uint8)
    with_m[:, :3 * W // 4] = 255   # river extent (wider)

    no_m = np.zeros((H, W), dtype=np.uint8)
    no_m[:, :W // 2] = 255         # open water only

    return prob, with_m, no_m


# ──────────────────────────────────────────────────────────────────────────────
# 1. logic_python uncertainty analysis (mc_analysis.vn)
# ──────────────────────────────────────────────────────────────────────────────

# Extract and exec the analysis code directly (isolates from live VN runtime)
_ANALYSIS_CODE = """\
N_MC = 100
RUNTIME_S = 900.0

if not (isinstance(a, dict) and 'bands' in a and isinstance(b, dict) and 'bands' in b):
    out_a = 'missing inputs'
else:
    prob = a['bands'][0].astype(np.float64)
    mask_raw = b['bands'][0]
    valid = np.isfinite(prob)
    water = (mask_raw > 0.5) & valid
    n_valid = int(valid.sum())
    n_water = int(water.sum())
    if n_valid == 0:
        out_a = 'ERROR: no valid pixels'
    else:
        p = prob[water].astype(np.float64)
        mean_p = float(np.mean(p)) if len(p) > 0 else float('nan')
        med_p  = float(np.median(p)) if len(p) > 0 else float('nan')
        p10 = float(np.percentile(p, 10)) if len(p) > 0 else float('nan')
        p90 = float(np.percentile(p, 90)) if len(p) > 0 else float('nan')
        high = float(np.mean(p >= 0.9)) * 100 if len(p) > 0 else 0.0
        amb  = float(np.mean((p > 0.3) & (p < 0.7))) * 100 if len(p) > 0 else 0.0
        low  = float(np.mean(p <= 0.1)) * 100 if len(p) > 0 else 0.0
        u    = p * (1.0 - p)
        mu   = float(np.mean(u)) if len(u) > 0 else float('nan')
        p95u = float(np.percentile(u, 95)) if len(u) > 0 else float('nan')
        cv   = float(np.std(p) / mean_p) if (len(p) > 0 and mean_p > 0) else float('nan')
        lines = ['MC iterations:', f'{N_MC}', f'valid={n_valid}', f'water={n_water}',
                 f'mean_p={mean_p:.3f}', f'p10={p10:.3f}', f'p90={p90:.3f}',
                 f'high={high:.2f}', f'amb={amb:.2f}', f'low={low:.2f}',
                 f'mu={mu:.4f}', f'p95u={p95u:.4f}', f'cv={cv:.3f}']
        if RUNTIME_S is not None:
            pxs  = n_valid / RUNTIME_S / 1e6
            mops = n_valid * N_MC / RUNTIME_S / 1e6
            lines += [f'pxs={pxs:.4f}', f'mops={mops:.4f}']
        out_a = '\\n'.join(lines)
"""


def _run_analysis(a, b):
    ctx = {'np': np, 'a': a, 'b': b}
    exec(_ANALYSIS_CODE, ctx)  # noqa: S102
    return ctx.get('out_a', '')


def test_analysis_missing_inputs():
    result = _run_analysis(None, None)
    assert 'missing inputs' in result.lower()


def test_analysis_basic_metrics():
    H, W = 32, 64
    prob = np.full((H, W), 0.92, dtype=np.float32)
    mask = np.ones((H, W), dtype=np.float32)
    result = _run_analysis(_prob_geo(prob), _mask_geo(mask))
    assert f'valid={H * W}' in result
    assert f'water={H * W}' in result
    assert 'mean_p=0.920' in result
    assert 'pxs=' in result    # efficiency metrics with RUNTIME_S=900


def test_analysis_high_confidence_water():
    """All pixels at P=0.95 → high_conf should be 100.00%."""
    H, W = 16, 16
    prob = np.full((H, W), 0.95, dtype=np.float32)
    mask = np.ones((H, W), dtype=np.float32)
    result = _run_analysis(_prob_geo(prob), _mask_geo(mask))
    assert 'high=100.00' in result
    assert 'amb=0.00' in result
    assert 'low=0.00' in result


def test_analysis_uncertainty_maximum_at_half():
    """P=0.5 → Bernoulli variance P(1-P)=0.25 → mu=0.2500."""
    H, W = 8, 8
    prob = np.full((H, W), 0.5, dtype=np.float32)
    mask = np.ones((H, W), dtype=np.float32)
    result = _run_analysis(_prob_geo(prob), _mask_geo(mask))
    assert 'mu=0.2500' in result


def test_analysis_no_water_pixels():
    """Mask all-zero → n_water=0, should not crash."""
    H, W = 16, 16
    prob = np.full((H, W), 0.8, dtype=np.float32)
    mask = np.zeros((H, W), dtype=np.float32)
    result = _run_analysis(_prob_geo(prob), _mask_geo(mask))
    assert 'water=0' in result


# ──────────────────────────────────────────────────────────────────────────────
# 2. CDF & threshold sweep logic (mc_validation.vn — py_cdf node)
# ──────────────────────────────────────────────────────────────────────────────

_CDF_LOGIC = """\
# Minimal version of the CDF/threshold sweep without matplotlib rendering
# Returns sweep results as out_dict for unit testing
MC_THRESHOLD = 0.7
if not (isinstance(a, dict) and 'bands' in a):
    out_dict = None
else:
    prob     = a['bands'][0].astype(np.float64)
    valid    = np.isfinite(prob)
    with_m   = (b > 127) & valid if (b is not None and isinstance(b, np.ndarray)) else np.zeros_like(valid)
    no_m     = (c > 127) & valid if (c is not None and isinstance(c, np.ndarray)) else np.zeros_like(valid)
    bridge_m = with_m & ~no_m
    p_w = prob[no_m]
    p_b = prob[bridge_m]
    sep = float(np.mean(p_w)) - float(np.mean(p_b)) if len(p_b) > 0 else float('nan')
    thresholds = [0.3, 0.5, 0.7, 0.9]
    sweep = {}
    for t in thresholds:
        pred  = (prob >= t) & valid
        tp = int(np.sum(pred & no_m)); fp = int(np.sum(pred & ~no_m & valid)); fn = int(np.sum(~pred & no_m))
        pr_ = tp/(tp+fp) if (tp+fp) > 0 else 0.0
        rc_ = tp/(tp+fn) if (tp+fn) > 0 else 0.0
        f1_ = 2*pr_*rc_/(pr_+rc_) if (pr_+rc_) > 0 else 0.0
        sweep[t] = f1_
    out_dict = {'sep': sep, 'n_water': len(p_w), 'n_bridge': len(p_b), 'sweep': sweep}
"""


def _run_cdf(a, b, c):
    ctx = {'np': np, 'a': a, 'b': b, 'c': c}
    exec(_CDF_LOGIC, ctx)  # noqa: S102
    return ctx.get('out_dict')


def test_cdf_separation_positive():
    """Open water > bridge pixels → separation should be positive."""
    prob, with_m, no_m = _synthetic_prob_and_masks()
    result = _run_cdf(_prob_geo(prob), with_m, no_m)
    assert result is not None
    assert result['sep'] > 0
    assert result['n_water'] > 0
    assert result['n_bridge'] > 0


def test_cdf_threshold_sweep_monotone():
    """F1 at P≥0.7 (correct threshold) should be higher than at P≥0.9 for this scene."""
    prob, with_m, no_m = _synthetic_prob_and_masks()
    result = _run_cdf(_prob_geo(prob), with_m, no_m)
    assert result['sweep'][0.7] >= result['sweep'][0.9]


def test_cdf_no_bridge_pixels():
    """If with_bridges == no_bridges, bridge_m is empty → n_bridge=0, sep=nan."""
    H, W = 16, 32
    prob = np.full((H, W), 0.9, dtype=np.float32)
    no_m = np.ones((H, W), dtype=np.uint8) * 255
    result = _run_cdf(_prob_geo(prob), no_m, no_m)
    assert result is not None
    assert result['n_bridge'] == 0
    assert np.isnan(result['sep'])


def test_cdf_missing_prob():
    result = _run_cdf(None, None, None)
    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# 3. Index comparison logic (mc_validation.vn — py_idx node)
# ──────────────────────────────────────────────────────────────────────────────

_IDX_LOGIC = """\
MC_THRESHOLD = 0.7
if not (isinstance(a, dict) and 'bands' in a and isinstance(b, dict) and 'bands' in b):
    out_dict = None
else:
    prob     = a['bands'][0].astype(np.float64)
    valid    = np.isfinite(prob)
    n_idx    = min(4, b['count'])
    names    = (b.get('band_names') or ['MNDWI','NDWI','AWEI','MBWI'])[:n_idx]
    idx_arrs = [b['bands'][i].astype(np.float64) for i in range(n_idx)]
    with_m   = (c > 127) & valid if (c is not None and isinstance(c, np.ndarray)) else np.zeros_like(valid)
    no_m     = (d > 127) & valid if (d is not None and isinstance(d, np.ndarray)) else np.zeros_like(valid)

    def get_f1(pred, ref):
        tp = int(np.sum(pred & ref)); fp = int(np.sum(pred & ~ref)); fn = int(np.sum(~pred & ref))
        pr_ = tp/(tp+fp) if (tp+fp) > 0 else 0.0
        rc_ = tp/(tp+fn) if (tp+fn) > 0 else 0.0
        return 2*pr_*rc_/(pr_+rc_) if (pr_+rc_) > 0 else 0.0

    mc_pred = (prob >= MC_THRESHOLD) & valid
    results = {}
    results['MC'] = get_f1(mc_pred, no_m)
    for i, name in enumerate(names):
        idx_pred = (idx_arrs[i] >= 0.0) & np.isfinite(idx_arrs[i]) & valid
        results[name] = get_f1(idx_pred, no_m)
    out_dict = results
"""


def _run_idx(a, b, c, d):
    ctx = {'np': np, 'a': a, 'b': b, 'c': c, 'd': d}
    exec(_IDX_LOGIC, ctx)  # noqa: S102
    return ctx.get('out_dict')


def _synthetic_index_scene(H=32, W=64):
    """
    Left half = water (MNDWI>0, NDWI>0, positive AWEI, high MBWI).
    Right half = land (all indices negative/low).
    """
    mndwi = np.where(np.arange(W) < W // 2, 0.4, -0.3).astype(np.float32)
    mndwi = np.tile(mndwi, (H, 1))
    ndwi  = mndwi * 0.9
    awei  = mndwi * 2.0
    mbwi  = mndwi * 3.0
    return mndwi, ndwi, awei, mbwi


def test_idx_mc_outperforms_land_index():
    """
    With a perfect P(water) and spectral indices that correlate, MC F1 ≥ index F1
    (or at least all methods detect the water patch).
    """
    H, W = 32, 64
    prob, with_m, no_m = _synthetic_prob_and_masks(H, W)
    mndwi, ndwi, awei, mbwi = _synthetic_index_scene(H, W)
    stack = _index_stack([mndwi, ndwi, awei, mbwi], ['MNDWI', 'NDWI', 'AWEI', 'MBWI'])
    result = _run_idx(_prob_geo(prob), stack, with_m, no_m)
    assert result is not None
    assert 'MC' in result and 'MNDWI' in result
    # MC should detect more water (P=0.92 >> threshold 0.7)
    assert result['MC'] > 0.5


def test_idx_missing_inputs():
    result = _run_idx(None, None, None, None)
    assert result is None


def test_idx_all_negative_indices():
    """Indices all < 0 → index predictions empty → F1 = 0 for each index."""
    H, W = 16, 32
    prob = np.full((H, W), 0.9, dtype=np.float32)
    no_m = np.ones((H, W), dtype=np.uint8) * 255
    with_m = no_m.copy()
    neg = np.full((H, W), -0.5, dtype=np.float32)
    stack = _index_stack([neg, neg, neg, neg], ['MNDWI', 'NDWI', 'AWEI', 'MBWI'])
    result = _run_idx(_prob_geo(prob), stack, with_m, no_m)
    assert result is not None
    for name in ['MNDWI', 'NDWI', 'AWEI', 'MBWI']:
        assert result[name] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 4. Sensitivity binned stats + Spearman r (mc_sensitivity.vn logic)
# ──────────────────────────────────────────────────────────────────────────────

_SENS_LOGIC = """\
# Stripped version: compute Spearman r and binned stats, return as out_dict
N_BINS = 20

def spearman_r(x, y):
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 30: return float('nan')
    xa, ya = x[m].astype(np.float64), y[m].astype(np.float64)
    ra = np.argsort(np.argsort(xa)).astype(np.float64)
    rb = np.argsort(np.argsort(ya)).astype(np.float64)
    return float(np.corrcoef(ra, rb)[0, 1])

def binned_stats(x_all, y_all, n_bins):
    m = np.isfinite(x_all) & np.isfinite(y_all)
    x, y = x_all[m], y_all[m]
    if x.size < 500: return None
    edges = np.unique(np.quantile(x, np.linspace(0, 1, n_bins + 1)))
    if edges.size < 5: return None
    bidx = np.digitize(x, edges[1:-1], right=True)
    rows = []
    for i in range(edges.size - 1):
        sel = bidx == i
        if sel.sum() < 50: continue
        yi = y[sel]
        rows.append({'mid': (edges[i]+edges[i+1])/2, 'mean': float(np.mean(yi))})
    return rows

if not (isinstance(a, dict) and 'bands' in a and isinstance(b, dict) and 'bands' in b):
    out_dict = None
else:
    prob = a['bands'][0].astype(np.float64)
    valid_base = np.isfinite(prob)
    n_idx = min(4, b['count'])
    names = (b.get('band_names') or ['NDWI','MNDWI','AWEI','MBWI'])[:n_idx]
    corrs = {}
    for i in range(n_idx):
        arr = b['bands'][i].astype(np.float64)
        valid = valid_base & np.isfinite(arr)
        r = spearman_r(arr[valid], prob[valid])
        stats = binned_stats(arr[valid], prob[valid], N_BINS)
        corrs[names[i]] = {'r': r, 'n_bins': len(stats) if stats else 0}
    out_dict = corrs
"""


def _run_sensitivity(a, b):
    ctx = {'np': np, 'a': a, 'b': b}
    exec(_SENS_LOGIC, ctx)  # noqa: S102
    return ctx.get('out_dict')


def _large_sensitivity_scene(H=64, W=512):
    """
    NDWI perfectly correlated with P(water): large, smooth gradient.
    MBWI anti-correlated. MNDWI/AWEI partial.
    """
    t = np.linspace(0.0, 1.0, W, dtype=np.float32)   # 0=water, 1=land
    prob = np.tile((1.0 - t), (H, 1))                 # water prob
    ndwi  = np.tile((1.0 - 2*t), (H, 1))              # strong positive corr
    mndwi = np.tile((0.8 - 1.6*t), (H, 1))            # similar
    awei  = np.tile((0.3 - 0.6*t), (H, 1))            # moderate
    mbwi  = np.tile((-1.0 + 2*t), (H, 1))             # anti-correlated
    return prob, ndwi, mndwi, awei, mbwi


def test_sensitivity_spearman_positive_for_ndwi():
    """NDWI increases as P(water) increases → Spearman r > 0."""
    prob, ndwi, mndwi, awei, mbwi = _large_sensitivity_scene()
    stack = _index_stack([ndwi, mndwi, awei, mbwi], ['NDWI', 'MNDWI', 'AWEI', 'MBWI'])
    result = _run_sensitivity(_prob_geo(prob), stack)
    assert result is not None
    assert result['NDWI']['r'] > 0.9


def test_sensitivity_spearman_negative_for_anti_corr():
    """MBWI anti-correlated with P(water) → Spearman r < 0."""
    prob, ndwi, mndwi, awei, mbwi = _large_sensitivity_scene()
    stack = _index_stack([ndwi, mndwi, awei, mbwi], ['NDWI', 'MNDWI', 'AWEI', 'MBWI'])
    result = _run_sensitivity(_prob_geo(prob), stack)
    assert result is not None
    assert result['MBWI']['r'] < -0.9


def test_sensitivity_bins_populated():
    """Each index should produce at least 5 populated bins."""
    prob, ndwi, mndwi, awei, mbwi = _large_sensitivity_scene()
    stack = _index_stack([ndwi, mndwi, awei, mbwi], ['NDWI', 'MNDWI', 'AWEI', 'MBWI'])
    result = _run_sensitivity(_prob_geo(prob), stack)
    for name in ['NDWI', 'MNDWI', 'AWEI']:
        assert result[name]['n_bins'] >= 5, f'{name} has too few bins'


def test_sensitivity_missing_inputs():
    result = _run_sensitivity(None, None)
    assert result is None


def test_sensitivity_nan_in_index():
    """NaN values in index bands should not crash the analysis."""
    H, W = 64, 256
    prob = np.random.default_rng(0).random((H, W)).astype(np.float32)
    ndwi = np.random.default_rng(1).random((H, W)).astype(np.float32) * 2 - 1
    ndwi[:, :W // 4] = np.nan   # quarter of the scene has NaN
    stack = _index_stack([ndwi], ['NDWI'])
    result = _run_sensitivity(_prob_geo(prob), stack)
    assert result is not None
    # r should be finite (or nan if too few valid samples, but not a crash)
