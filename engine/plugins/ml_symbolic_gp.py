"""
ml_symbolic_gp.py — Genetic Programming Symbolic Regression with Ensemble Uncertainty.

Three nodes:
  ml_symbolic_regressor        : Train N independent GP regressors (bootstrap) → ensemble
  ml_ensemble_apply            : Apply ensemble of GP models → mean + std prediction tables
  ml_synthetic_regression_data : Generate synthetic training table from known formula (validation)

Key innovation: per-pixel uncertainty quantification via GP ensemble disagreement.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'ml_gp'


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


_MPL_DARK = {
    'figure.facecolor': '#161616',
    'axes.facecolor':   '#1e1e1e',
    'axes.edgecolor':   '#555555',
    'axes.labelcolor':  '#cccccc',
    'text.color':       '#cccccc',
    'xtick.color':      '#aaaaaa',
    'ytick.color':      '#aaaaaa',
    'grid.color':       '#333333',
    'grid.linestyle':   '--',
    'grid.linewidth':   0.5,
}


def _fig_to_bgr(fig, dpi: int = 100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _info_panel(lines: list, w: int = 480, h: int = 240, title: str = '') -> np.ndarray:
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


# ─── Protected math functions (module-level for gplearn pickling) ─────────────

def _protected_division(x1, x2):
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(np.abs(x2) > 1e-3, x1 / x2, 1.0)


def _protected_log(x1):
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(np.abs(x1) > 1e-3, np.log(np.abs(x1)), 0.0)


def _protected_sqrt(x1):
    return np.sqrt(np.abs(x1))


def _protected_exp(x1):
    with np.errstate(over='ignore'):
        return np.exp(np.clip(x1, -50, 50))


# ─── 1. Synthetic data generator ──────────────────────────────────────────────

@vision_node(
    type_id='ml_synthetic_regression_data',
    label='Synthetic Regression Data',
    category='ml',
    icon='Sigma',
    description=(
        "Generate a synthetic training table from a known mathematical formula. "
        "Used to validate the GP ensemble pipeline (Phase 1) before real satellite data. "
        "Default formula simulates Sentinel-2 water turbidity: 15.5 * (Red/Green) + log(NIR). "
        "Outputs: training table (small) + full raster table (large) + true formula string. "
        "Connect train_table → GP Regressor, raster_table → Ensemble Apply."
    ),
    inputs=[],
    outputs=[
        {'id': 'train_table',  'color': 'data',   'label': 'Training table (X + label)'},
        {'id': 'raster_table', 'color': 'data',   'label': 'Full raster table (X only)'},
        {'id': 'shape',        'color': 'list',   'label': 'Raster shape [H, W]'},
        {'id': 'true_formula', 'color': 'string', 'label': 'Ground truth formula'},
        {'id': 'preview',      'color': 'image',  'label': 'Info preview'},
    ],
    params=[
        {'id': 'n_train',   'type': 'int',   'default': 200,   'min': 20, 'max': 5000, 'label': 'Training samples'},
        {'id': 'raster_h',  'type': 'int',   'default': 200,   'min': 32, 'max': 1024, 'label': 'Raster height (px)'},
        {'id': 'raster_w',  'type': 'int',   'default': 200,   'min': 32, 'max': 1024, 'label': 'Raster width (px)'},
        {'id': 'formula',   'type': 'code',
         'default': '15.5 * (Rouge / Vert) + log(NIR)',
         'label': 'True formula (vars: Bleu, Vert, Rouge, NIR)'},
        {'id': 'noise_std', 'type': 'float', 'default': 0.5,  'min': 0.0, 'max': 5.0, 'label': 'Noise std-dev'},
        {'id': 'seed',      'type': 'int',   'default': 42,   'min': 0,   'max': 9999, 'label': 'Random seed'},
    ],
    resizable=True, min_width=260, min_height=180,
)
class SyntheticRegressionDataNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        n_train  = max(20, int(params.get('n_train', 200)))
        H        = max(32, int(params.get('raster_h', 200)))
        W        = max(32, int(params.get('raster_w', 200)))
        formula  = str(params.get('formula', '15.5 * (Rouge / Vert) + log(NIR)')).strip()
        noise_sd = float(params.get('noise_std', 0.5))
        seed     = int(params.get('seed', 42))

        send_notification(f'Synth: {n_train} samples + raster {W}×{H}…', progress=0.1, notif_id=_NOTIF)

        rng = np.random.default_rng(seed)

        def _sample_bands(n):
            return {
                'Bleu':  rng.uniform(0.01,  0.05, n).astype(np.float32),
                'Vert':  rng.uniform(0.02,  0.08, n).astype(np.float32),
                'Rouge': rng.uniform(0.01,  0.12, n).astype(np.float32),
                'NIR':   rng.uniform(0.005, 0.04, n).astype(np.float32),
            }

        # ── Training table (with label = noisy true formula evaluation)
        train_bands = _sample_bands(n_train)
        ns = {
            **train_bands,
            'log':  _protected_log,
            'sqrt': _protected_sqrt,
            'exp':  _protected_exp,
            'abs':  np.abs,
            'np':   np,
        }
        try:
            y_clean = np.asarray(eval(formula, {'__builtins__': {}}, ns), dtype=np.float32)
        except Exception as e:
            send_notification(f'Synth: formula error: {e}', level='error', notif_id=_NOTIF)
            return {}

        y_noisy = y_clean + rng.normal(0, noise_sd, n_train).astype(np.float32)
        train_df = pd.DataFrame({**train_bands, 'label': y_noisy})
        train_df['__px_idx'] = np.arange(n_train, dtype=np.int32)

        # ── Raster table (no label, full HxW pixels)
        send_notification('Synth: raster pixels…', progress=0.5, notif_id=_NOTIF)
        n_raster = H * W
        raster_bands = _sample_bands(n_raster)
        raster_df = pd.DataFrame(raster_bands)
        raster_df['__px_idx'] = np.arange(n_raster, dtype=np.int32)

        # ── Preview
        lines = [
            f'Formule: {formula}',
            f'Training: {n_train} samples  |  Bruit σ={noise_sd}',
            f'Raster: {W} × {H}  ({n_raster:,} pixels)',
            f'Variables: Bleu, Vert, Rouge, NIR',
            f'Label stats: μ={y_noisy.mean():.2f}  σ={y_noisy.std():.2f}',
            f'             min={y_noisy.min():.2f}  max={y_noisy.max():.2f}',
            f'Seed: {seed}',
        ]
        preview = _info_panel(lines, w=480, h=200, title='Synthetic Data (Phase 1 validation)')

        send_notification(f'Synth: OK — {n_train} train + {n_raster:,} raster px', progress=1.0, notif_id=_NOTIF)
        return {
            'train_table':  train_df,
            'raster_table': raster_df,
            'shape':        [H, W],
            'true_formula': formula,
            'preview':      preview,
        }


# ─── 2. GP Symbolic Regressor (Ensemble) ──────────────────────────────────────

@vision_node(
    type_id='ml_symbolic_regressor',
    label='GP Symbolic Regressor',
    category='ml',
    icon='GitBranch',
    description=(
        "Genetic Programming symbolic regression with bootstrap ensemble. "
        "Evolves N independent mathematical formulas from a labeled table "
        "(X features + y target column). Each ensemble member is trained on a "
        "bootstrap sample with a different random seed. "
        "Output models can be fed to ml_ensemble_apply for mean + uncertainty maps. "
        "Set n_ensemble=1 for a single regressor."
    ),
    inputs=[
        {'id': 'train_table', 'color': 'data', 'label': 'Training table (X + label)'},
    ],
    outputs=[
        {'id': 'models',   'color': 'dict',   'label': 'Trained ensemble'},
        {'id': 'formulas', 'color': 'string', 'label': 'Evolved formulas'},
        {'id': 'stats',    'color': 'dict',   'label': 'Fit stats (R², RMSE)'},
        {'id': 'preview',  'color': 'image',  'label': 'Fitness + formulas panel'},
    ],
    params=[
        {'id': 'target_column',    'type': 'string', 'default': 'label',
         'label': 'Target column'},
        {'id': 'feature_columns',  'type': 'string', 'default': '',
         'label': 'Feature columns (comma, blank=auto)'},
        {'id': 'n_ensemble',       'type': 'int',    'default': 10,  'min': 1,  'max': 50,
         'label': 'Ensemble size N'},
        {'id': 'population_size',  'type': 'int',    'default': 500, 'min': 50, 'max': 5000,
         'label': 'Population per GP'},
        {'id': 'generations',      'type': 'int',    'default': 20,  'min': 5,  'max': 200,
         'label': 'Generations'},
        {'id': 'parsimony',        'type': 'float',  'default': 0.005, 'min': 0.0, 'max': 0.1,
         'label': 'Parsimony coefficient'},
        {'id': 'test_size',        'type': 'float',  'default': 0.2, 'min': 0.0, 'max': 0.5,
         'label': 'Hold-out test fraction'},
        {'id': 'use_log',          'type': 'bool',   'default': True,  'label': 'Include log'},
        {'id': 'use_sqrt',         'type': 'bool',   'default': True,  'label': 'Include sqrt'},
        {'id': 'use_div',          'type': 'bool',   'default': True,  'label': 'Include protected div'},
        {'id': 'log_transform',    'type': 'bool',   'default': True,
         'label': 'Log-transform target (log1p/expm1)  — recommandé turbidité'},
        {'id': 'seed',             'type': 'int',    'default': 42,    'min': 0, 'max': 9999,
         'label': 'Base random seed'},
        {'id': 'run',              'type': 'trigger','default': 0,     'label': 'Train Ensemble'},
    ],
    resizable=True, min_width=320, min_height=240,
)
class SymbolicRegressorNode(NodeProcessor):
    """GP ensemble symbolic regressor — caches by trigger only (training is heavy)."""

    def __init__(self):
        super().__init__()
        self._last_trigger = 0
        self._cached_out = None

    def process(self, inputs, params):
        if not self.ensure_packages(['gplearn', 'sklearn', 'pandas'],
                                    pip_names=['gplearn', 'scikit-learn', 'pandas'],
                                    notif_id=_NOTIF):
            return {}
        import pandas as pd
        from gplearn.genetic import SymbolicRegressor
        from gplearn.functions import make_function
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_squared_error

        df = inputs.get('train_table')
        if df is None or not isinstance(df, pd.DataFrame):
            send_notification('GP: waiting for TRAIN_TABLE input', notif_id=_NOTIF)
            return {}

        # ── Trigger gate: only retrain on explicit user click
        trig = int(params.get('run', 0))
        if trig == self._last_trigger and self._cached_out is not None:
            return self._cached_out
        if trig == self._last_trigger and self._cached_out is None:
            send_notification(
                f'GP: {len(df)} rows ready — click "Train Ensemble" to train',
                notif_id=_NOTIF,
            )
            return {}

        target = str(params.get('target_column', 'label')).strip()
        if target not in df.columns:
            send_notification(f'GP: target column "{target}" not found', level='error', notif_id=_NOTIF)
            return {}

        # ── Feature columns
        _EXCLUDE = {target, '__px_idx', 'lat', 'lon', 'latitude', 'longitude',
                    'GLORIA_ID', 'date', 'Date_Time_UTC'}
        feat_str = str(params.get('feature_columns', '')).strip()
        if feat_str:
            features = [c.strip() for c in feat_str.split(',') if c.strip() in df.columns]
        else:
            features = [c for c in df.columns
                        if c not in _EXCLUDE and pd.api.types.is_numeric_dtype(df[c])]
        if not features:
            all_cols = list(df.columns)
            send_notification(
                f'GP: no numeric features. Columns received: {all_cols}. '
                f'Expected band columns (Bleu/Vert/Rouge/NIR) from GT Sampler output. '
                f'Check TRAIN_TABLE is connected to GT Sampler "train_table" port, not Naiades.',
                level='error', notif_id=_NOTIF,
            )
            return {}

        X_all = df[features].to_numpy(dtype=np.float32)
        y_all = df[target].to_numpy(dtype=np.float32)

        # Drop NaN
        valid = ~(np.isnan(X_all).any(axis=1) | np.isnan(y_all))
        X_all = X_all[valid]
        y_all = y_all[valid]
        if len(X_all) < 10:
            send_notification(f'GP: only {len(X_all)} valid rows', level='error', notif_id=_NOTIF)
            return {}

        # ── Log-transform target (turbidité suit loi log-normale)
        log_transform = bool(params.get('log_transform', True))
        y_orig = y_all.copy()
        if log_transform:
            y_all = np.log1p(np.maximum(0.0, y_all)).astype(np.float32)
            send_notification('GP: log1p(target) appliqué', progress=0.04, notif_id=_NOTIF)

        # ── Build function set
        protected_log_fn  = make_function(function=_protected_log,      name='log',  arity=1)
        protected_sqrt_fn = make_function(function=_protected_sqrt,     name='sqrt', arity=1)
        protected_div_fn  = make_function(function=_protected_division, name='div',  arity=2)

        function_set = ['add', 'sub', 'mul']
        if bool(params.get('use_div',  True)): function_set.append(protected_div_fn)
        if bool(params.get('use_log',  True)): function_set.append(protected_log_fn)
        if bool(params.get('use_sqrt', True)): function_set.append(protected_sqrt_fn)

        # ── Ensemble hyperparams
        n_ens   = max(1, int(params.get('n_ensemble', 10)))
        pop     = max(50, int(params.get('population_size', 500)))
        gens    = max(5, int(params.get('generations', 20)))
        pars    = float(params.get('parsimony', 0.005))
        ts      = float(params.get('test_size', 0.2))
        base_seed = int(params.get('seed', 42))

        send_notification(
            f'GP: ensemble N={n_ens}  pop={pop}  gen={gens}  features={len(features)}…',
            progress=0.05, notif_id=_NOTIF,
        )

        # ── Train/test split (same across ensemble for fair R² comparison)
        if ts > 0 and len(X_all) > 20:
            X_tr_pool, X_te, y_tr_pool, y_te = train_test_split(
                X_all, y_all, test_size=ts, random_state=base_seed,
            )
            # Keep original-scale test labels for final NTU scoring
            _, _, y_orig_tr, y_orig_te = train_test_split(
                X_all, y_orig, test_size=ts, random_state=base_seed,
            )
        else:
            X_tr_pool, y_tr_pool = X_all, y_all
            X_te, y_te = None, None
            y_orig_tr, y_orig_te = y_orig, None

        rng = np.random.default_rng(base_seed)
        estimators = []
        formulas   = []
        r2_tr_list, r2_te_list = [], []
        rmse_tr_list, rmse_te_list = [], []

        for i in range(n_ens):
            # ── Bootstrap sample
            idx = rng.integers(0, len(X_tr_pool), size=len(X_tr_pool))
            X_boot = X_tr_pool[idx]
            y_boot = y_tr_pool[idx]

            seed_i = base_seed + i * 7

            est = SymbolicRegressor(
                population_size=pop,
                generations=gens,
                stopping_criteria=0.001,
                p_crossover=0.7,
                p_subtree_mutation=0.1,
                p_hoist_mutation=0.05,
                p_point_mutation=0.1,
                function_set=function_set,
                parsimony_coefficient=pars,
                feature_names=features,
                verbose=0,
                random_state=seed_i,
                n_jobs=1,
            )
            est.fit(X_boot, y_boot)

            y_pred_tr_log = est.predict(X_tr_pool)
            r2_tr = r2_score(y_tr_pool, y_pred_tr_log)
            if log_transform:
                y_pred_tr_ntu = np.expm1(np.clip(y_pred_tr_log, -10, 20))
                rmse_tr = float(np.sqrt(mean_squared_error(y_orig_tr, y_pred_tr_ntu)))
            else:
                rmse_tr = float(np.sqrt(mean_squared_error(y_tr_pool, y_pred_tr_log)))
            r2_tr_list.append(r2_tr); rmse_tr_list.append(rmse_tr)

            if X_te is not None:
                y_pred_te_log = est.predict(X_te)
                if log_transform:
                    # Score en espace NTU original
                    y_pred_te = np.expm1(np.clip(y_pred_te_log, -10, 20)).astype(np.float32)
                    r2_te   = r2_score(y_orig_te, y_pred_te)
                    rmse_te = float(np.sqrt(mean_squared_error(y_orig_te, y_pred_te)))
                else:
                    r2_te   = r2_score(y_te, y_pred_te_log)
                    rmse_te = float(np.sqrt(mean_squared_error(y_te, y_pred_te_log)))
                r2_te_list.append(r2_te); rmse_te_list.append(rmse_te)

            estimators.append(est)
            formulas.append(str(est._program))

            send_notification(
                f'GP: ensemble {i+1}/{n_ens}  R²_tr={r2_tr:.3f}',
                progress=0.1 + 0.85 * (i + 1) / n_ens, notif_id=_NOTIF,
            )

        # ── Stats summary
        stats = {
            'n_ensemble':   n_ens,
            'n_features':   len(features),
            'n_train':      int(len(X_tr_pool)),
            'n_test':       int(len(X_te)) if X_te is not None else 0,
            'r2_train_mean':  round(float(np.mean(r2_tr_list)),   4),
            'r2_train_std':   round(float(np.std(r2_tr_list)),    4),
            'rmse_train_mean':round(float(np.mean(rmse_tr_list)), 4),
        }
        if r2_te_list:
            stats.update({
                'r2_test_mean':   round(float(np.mean(r2_te_list)),   4),
                'r2_test_std':    round(float(np.std(r2_te_list)),    4),
                'rmse_test_mean': round(float(np.mean(rmse_te_list)), 4),
            })

        # ── Find best formula (highest test R², fallback train)
        ref = r2_te_list if r2_te_list else r2_tr_list
        best_idx = int(np.argmax(ref))
        stats['best_idx']     = best_idx
        stats['best_formula'] = formulas[best_idx]
        stats['best_r2']      = round(float(ref[best_idx]), 4)

        # ── Render preview panel: fitness distribution + top formulas
        _, plt = _get_mpl()
        with plt.rc_context(_MPL_DARK):
            fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.4))
            ax_box = axes[0]
            data = [r2_tr_list] + ([r2_te_list] if r2_te_list else [])
            labels = ['Train'] + (['Test'] if r2_te_list else [])
            bp = ax_box.boxplot(data, labels=labels, patch_artist=True, widths=0.5)
            for patch, c in zip(bp['boxes'], ['#5b8def', '#f5a623']):
                patch.set_facecolor(c); patch.set_alpha(0.7)
            log_lbl = '  [log1p target]' if log_transform else ''
            ax_box.set_title(f'Ensemble R²  (N={n_ens}){log_lbl}', fontsize=10)
            ax_box.set_ylim(min(0, min(r2_tr_list) - 0.05), 1.02)
            ax_box.grid(True, alpha=0.25)

            ax_txt = axes[1]; ax_txt.set_axis_off()
            txt_lines = [f'Best  R²={stats["best_r2"]:.3f}']
            best_f = formulas[best_idx]
            # Wrap formula
            for chunk in [best_f[i:i+50] for i in range(0, min(len(best_f), 250), 50)]:
                txt_lines.append('  ' + chunk)
            txt_lines.append('')
            txt_lines.append(f'Features: {", ".join(features)}')
            txt_lines.append(f'Train: {stats["n_train"]}  Test: {stats["n_test"]}')
            ax_txt.text(0.0, 0.98, '\n'.join(txt_lines), va='top', ha='left',
                        fontfamily='monospace', fontsize=8, color='#cccccc')

            fig.tight_layout(pad=0.6)
            preview = _fig_to_bgr(fig, dpi=110)
            plt.close(fig)

        # ── Pack models for downstream apply
        models = {
            'estimators':   estimators,
            'feature_cols': features,
            'target_col':   target,
            'best_idx':     best_idx,
            'log_transform':log_transform,
        }

        # ── Formula string (multi-line for display)
        formulas_str = '\n'.join(f'[{i:2d}] {f}' for i, f in enumerate(formulas))

        send_notification(
            f'GP: OK — best R²={stats["best_r2"]:.3f}  σ={stats.get("r2_test_std", stats["r2_train_std"]):.3f}',
            progress=1.0, notif_id=_NOTIF,
        )

        self._cached_out = {
            'models':   models,
            'formulas': formulas_str,
            'stats':    stats,
            'preview':  preview,
        }
        self._last_trigger = trig
        return self._cached_out


# ─── 3. Ensemble Apply ────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_ensemble_apply',
    label='Ensemble Apply (μ + σ)',
    category='ml',
    icon='Layers',
    description=(
        "Apply a trained GP ensemble to a pixel table. Each ensemble member "
        "produces a prediction; the output tables hold the per-pixel mean "
        "(central estimate) and standard deviation (uncertainty). "
        "Feed mean_table + std_table to two Table → Raster nodes for "
        "side-by-side NTU + uncertainty maps."
    ),
    inputs=[
        {'id': 'table',  'color': 'data', 'label': 'Pixel table (X features)'},
        {'id': 'models', 'color': 'dict', 'label': 'Trained ensemble'},
    ],
    outputs=[
        {'id': 'mean_table', 'color': 'data',  'label': 'Mean predictions table'},
        {'id': 'std_table',  'color': 'data',  'label': 'Std-dev predictions table'},
        {'id': 'stats',      'color': 'dict',  'label': 'Pixel-level stats'},
        {'id': 'preview',    'color': 'image', 'label': 'Distribution preview'},
    ],
    params=[
        {'id': 'pred_column', 'type': 'string', 'default': 'prediction',
         'label': 'Output column name'},
        {'id': 'clip_min',    'type': 'float',  'default': 0.0,
         'min': -1e6, 'max': 1e6, 'label': 'Clip min (e.g. 0 for NTU)'},
        {'id': 'clip_max',    'type': 'float',  'default': 1000.0,
         'min': -1e6, 'max': 1e9, 'label': 'Clip max (outlier ceiling)'},
    ],
    resizable=True, min_width=280, min_height=180,
)
class EnsembleApplyNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        df     = inputs.get('table')
        models = inputs.get('models')
        print(f'[Apply] inputs keys={list(inputs.keys())} table_type={type(df).__name__} models_type={type(models).__name__}')
        if df is None or not isinstance(df, pd.DataFrame):
            send_notification('Apply: waiting for pixel table (TABLE input)', notif_id=_NOTIF)
            return {}
        if not isinstance(models, dict):
            send_notification('Apply: waiting for trained ensemble (MODELS input)', notif_id=_NOTIF)
            return {}

        estimators = models.get('estimators') or []
        features   = models.get('feature_cols') or []
        if not estimators or not features:
            send_notification('Apply: empty ensemble or features — train GP first', level='error', notif_id=_NOTIF)
            return {}

        missing = [f for f in features if f not in df.columns]
        if missing:
            send_notification(f'Apply: missing columns: {missing}', level='error', notif_id=_NOTIF)
            return {}

        X = df[features].to_numpy(dtype=np.float32)
        n = len(X)
        n_ens = len(estimators)

        clip_min = float(params.get('clip_min', 0.0))
        clip_max = float(params.get('clip_max', 1000.0))
        pred_col = str(params.get('pred_column', 'prediction')).strip() or 'prediction'

        send_notification(f'Apply: {n_ens} models on {n:,} pixels…', progress=0.1, notif_id=_NOTIF)

        # ── Predict with each estimator
        log_transform = bool(models.get('log_transform', False))

        preds_stack = np.zeros((n_ens, n), dtype=np.float32)
        for i, est in enumerate(estimators):
            try:
                p = np.asarray(est.predict(X), dtype=np.float32)
            except Exception as e:
                send_notification(f'Apply: model {i} failed: {e}', level='error', notif_id=_NOTIF)
                p = np.zeros(n, dtype=np.float32)
            if log_transform:
                p = np.expm1(np.clip(p, -10, 20)).astype(np.float32)
            preds_stack[i] = np.clip(p, clip_min, clip_max)
            if (i + 1) % max(1, n_ens // 5) == 0:
                send_notification(
                    f'Apply: model {i+1}/{n_ens}', progress=0.1 + 0.7 * (i + 1) / n_ens,
                    notif_id=_NOTIF,
                )

        mean_pred = preds_stack.mean(axis=0)
        std_pred  = preds_stack.std(axis=0)

        # ── Build output tables (keep __px_idx for raster reconstruction)
        send_notification('Apply: building output tables…', progress=0.9, notif_id=_NOTIF)
        mean_df = pd.DataFrame({pred_col: mean_pred})
        std_df  = pd.DataFrame({pred_col: std_pred})
        if '__px_idx' in df.columns:
            mean_df['__px_idx'] = df['__px_idx'].values
            std_df['__px_idx']  = df['__px_idx'].values

        # ── Stats
        cv = float(np.mean(std_pred / (np.abs(mean_pred) + 1e-6)))
        stats = {
            'n_pixels':      int(n),
            'n_ensemble':    int(n_ens),
            'mean_overall':  round(float(mean_pred.mean()), 4),
            'mean_min':      round(float(mean_pred.min()),  4),
            'mean_max':      round(float(mean_pred.max()),  4),
            'std_mean':      round(float(std_pred.mean()),  4),
            'std_max':       round(float(std_pred.max()),   4),
            'coef_variation':round(cv, 4),
        }

        # ── Preview: side-by-side histograms (mean + std)
        _, plt = _get_mpl()
        with plt.rc_context(_MPL_DARK):
            fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.0))
            _bins = lambda arr: 50 if arr.max() > arr.min() else 1
            axes[0].hist(mean_pred, bins=_bins(mean_pred), color='#5b8def', alpha=0.85)
            axes[0].set_title(f'Mean  μ={stats["mean_overall"]:.2f}', fontsize=10)
            axes[0].grid(True, alpha=0.25)
            axes[1].hist(std_pred, bins=_bins(std_pred), color='#f5a623', alpha=0.85)
            axes[1].set_title(f'Std-dev  μ={stats["std_mean"]:.2f}', fontsize=10)
            axes[1].grid(True, alpha=0.25)
            fig.suptitle(f'Ensemble Apply  ({n_ens} models × {n:,} pixels)',
                         fontsize=10, color='#cccccc')
            fig.tight_layout(pad=0.6)
            preview = _fig_to_bgr(fig, dpi=110)
            plt.close(fig)

        send_notification(
            f'Apply: OK — μ̄={stats["mean_overall"]:.2f}  σ̄={stats["std_mean"]:.2f}  CV={cv:.2%}',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'mean_table': mean_df,
            'std_table':  std_df,
            'stats':      stats,
            'preview':    preview,
        }
