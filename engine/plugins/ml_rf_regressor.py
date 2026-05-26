"""
ml_rf_regressor.py
==================

Random-Forest regressor for continuous targets (turbidity, chlorophyll-a, ...).
Drop-in companion to `ml_symbolic_regressor`: outputs a `models` dict whose
shape is compatible with `ml_ensemble_apply` (same `estimators` list +
`feature_cols` + `log_transform`), so downstream nodes work unchanged.

Trick: we expose the forest's individual `tree_` estimators as the ensemble
members. Mean across trees = RF prediction; std across trees = per-pixel
uncertainty, available for free with no extra training cost.
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'rf_regressor'


def _info_panel(lines, w=520, h=260, title=''):
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    lh = 16
    for i, line in enumerate(lines[:(h - 36) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, str(line)[:80], (8, 48 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
    return img


def _importance_chart(importances, names, w=520, h=260, top_n=12):
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 28), (45, 45, 45), -1)
    cv2.putText(img, 'Feature importance', (8, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 28), (w, 28), (80, 80, 80), 1)
    order = np.argsort(importances)[::-1][:top_n]
    if len(order) == 0:
        return img
    max_imp = float(importances[order[0]]) or 1.0
    bar_w_max = w - 160
    bar_h = max(12, (h - 50) // len(order) - 4)
    y = 44
    for idx in order:
        imp = float(importances[idx])
        bar_w = int(imp / max_imp * bar_w_max)
        cv2.putText(img, str(names[idx])[:14], (8, y + bar_h - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.95, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.rectangle(img, (130, y), (130 + bar_w, y + bar_h), (90, 180, 220), -1)
        cv2.putText(img, f'{imp:.3f}', (130 + bar_w + 4, y + bar_h - 4),
                    cv2.FONT_HERSHEY_PLAIN, 0.9, (180, 180, 180), 1, cv2.LINE_AA)
        y += bar_h + 4
    return img


@vision_node(
    type_id='ml_rf_regressor',
    label='Random Forest Regressor',
    category='Machine Learning',
    icon='Trees',
    description=(
        "Random Forest regressor for continuous targets. Same I/O contract as "
        "ml_symbolic_regressor: outputs a `models` dict directly usable by "
        "ml_ensemble_apply, so the existing pipeline (Apply → raster) works "
        "unchanged. Each tree in the forest acts as one ensemble member, "
        "exposing per-pixel σ from across-tree variance at no extra cost."
    ),
    inputs=[
        {'id': 'train_table', 'color': 'data', 'label': 'Training table (X + label)'},
    ],
    outputs=[
        {'id': 'models',     'color': 'dict',   'label': 'Trained forest (apply-compatible)'},
        {'id': 'stats',      'color': 'dict',   'label': 'Fit stats (R², RMSE, slope)'},
        {'id': 'importance', 'color': 'image',  'label': 'Feature importance'},
        {'id': 'preview',    'color': 'image',  'label': 'Info panel'},
    ],
    params=[
        {'id': 'target_column',   'type': 'string', 'default': 'label', 'label': 'Target column'},
        {'id': 'feature_columns', 'type': 'string', 'default': '',
         'label': 'Feature columns (comma, blank=auto)'},
        {'id': 'n_estimators',    'type': 'int',    'default': 300, 'min': 10,  'max': 2000,
         'label': 'Num trees'},
        {'id': 'max_depth',       'type': 'int',    'default': 0,   'min': 0,   'max': 50,
         'label': 'Max depth (0 = unlimited)'},
        {'id': 'min_samples_leaf','type': 'int',    'default': 2,   'min': 1,   'max': 50,
         'label': 'Min samples per leaf'},
        {'id': 'max_features',    'type': 'enum',   'options': ['sqrt', 'log2', 'all'],
         'default': 0, 'label': 'Max features / split'},
        {'id': 'test_size',       'type': 'float',  'default': 0.2, 'min': 0.0, 'max': 0.5,
         'label': 'Hold-out test fraction'},
        {'id': 'log_transform',   'type': 'bool',   'default': True,
         'label': 'log1p-transform target (recommended for turbidity)'},
        {'id': 'seed',            'type': 'int',    'default': 42,  'min': 0,   'max': 9999,
         'label': 'Random seed'},
        {'id': 'run',             'type': 'trigger','default': 0,   'label': 'Train'},
    ],
    resizable=True, min_width=320, min_height=220,
)
class RFRegressorNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._prev_run = 0
        self._result   = None

    def process(self, inputs, params):
        run_val = params.get('run', 0)
        rising  = run_val != self._prev_run and run_val not in (False, 0, None)
        self._prev_run = run_val

        df = inputs.get('train_table')
        if df is None:
            if self._result is not None:
                return self._result
            return {'preview': _info_panel(['Connect train_table and click Train.'],
                                            title='RF Regressor')}

        if not rising and self._result is not None:
            return self._result

        if not rising:
            return {'preview': _info_panel([
                f'Rows: {len(df)}',
                f'Columns: {", ".join(list(df.columns)[:6])}...',
                'Click Train to fit forest.',
            ], title='RF Regressor (idle)')}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF):
            return {}

        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_squared_error

        target = str(params.get('target_column', 'label')).strip()
        feat_s = str(params.get('feature_columns', '')).strip()
        if target not in df.columns:
            send_notification(f'RF: target "{target}" not in columns', level='error', notif_id=_NOTIF)
            return {}

        all_cols = list(df.columns)
        numeric  = [c for c in all_cols if df[c].dtype.kind in 'biufc' and c != target]
        # Drop known non-feature columns
        DROP = {'__px_idx', 'station_id', 'lat', 'lon', 'date', 'symbole_unite'}
        numeric = [c for c in numeric if c not in DROP]
        if feat_s:
            features = [c.strip() for c in feat_s.split(',') if c.strip() in numeric]
        else:
            features = numeric
        if not features:
            send_notification('RF: no numeric features found', level='error', notif_id=_NOTIF)
            return {}

        X = df[features].to_numpy(dtype=np.float32)
        y = df[target].to_numpy(dtype=np.float32)
        mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
        X, y = X[mask], y[mask]
        if len(X) < 20:
            send_notification(f'RF: not enough rows after NaN drop ({len(X)})',
                              level='error', notif_id=_NOTIF)
            return {}

        log_transform = bool(params.get('log_transform', True))
        seed          = int(params.get('seed', 42))
        test_size     = float(params.get('test_size', 0.2))
        n_est         = int(params.get('n_estimators', 300))
        max_depth     = int(params.get('max_depth', 0)) or None
        min_leaf      = int(params.get('min_samples_leaf', 2))
        max_feat      = ['sqrt', 'log2', None][int(params.get('max_features', 0))]

        send_notification(f'RF: training {n_est} trees on {len(X)} rows…',
                          progress=0.1, notif_id=_NOTIF)

        y_orig = y.copy()
        y_fit  = np.log1p(y) if log_transform else y

        # Train/test split (deterministic on seed)
        if test_size > 0:
            X_tr, X_te, y_tr, y_te, yo_tr, yo_te = train_test_split(
                X, y_fit, y_orig, test_size=test_size, random_state=seed)
        else:
            X_tr, X_te, y_tr, y_te, yo_tr, yo_te = X, X, y_fit, y_fit, y_orig, y_orig

        rf = RandomForestRegressor(
            n_estimators=n_est, max_depth=max_depth,
            min_samples_leaf=min_leaf, max_features=max_feat,
            random_state=seed, n_jobs=-1,
        )
        rf.fit(X_tr, y_tr)

        # Predictions back in original NTU space
        def _to_orig(p):
            if log_transform:
                return np.expm1(np.clip(p, -10, 20))
            return p

        y_pred_te = _to_orig(rf.predict(X_te))
        y_pred_tr = _to_orig(rf.predict(X_tr))

        r2_te   = float(r2_score(yo_te, y_pred_te)) if len(yo_te) > 1 else 0.0
        rmse_te = float(np.sqrt(mean_squared_error(yo_te, y_pred_te))) if len(yo_te) > 1 else 0.0
        r2_tr   = float(r2_score(yo_tr, y_pred_tr))
        rmse_tr = float(np.sqrt(mean_squared_error(yo_tr, y_pred_tr)))
        slope_te = float(np.polyfit(yo_te, y_pred_te, 1)[0]) if len(yo_te) > 1 else 0.0

        send_notification(
            f'RF: R²_test={r2_te:.3f}  RMSE_test={rmse_te:.2f}  slope={slope_te:.3f}',
            progress=1.0, notif_id=_NOTIF,
        )

        # Package as apply-compatible models dict.
        # Trick: hand the forest's individual trees as "ensemble members" so that
        # ml_ensemble_apply iterates trees → mean = forest prediction, std =
        # across-tree spread (per-pixel uncertainty).
        models = {
            'estimators':   list(rf.estimators_),
            'feature_cols': features,
            'target_col':   target,
            'best_idx':     0,
            'log_transform':log_transform,
            'model_kind':   'random_forest',
            'forest':       rf,
        }

        stats = {
            'r2_test':    round(r2_te, 4),
            'r2_train':   round(r2_tr, 4),
            'rmse_test':  round(rmse_te, 4),
            'rmse_train': round(rmse_tr, 4),
            'slope_test': round(slope_te, 4),
            'n_train':    int(len(X_tr)),
            'n_test':     int(len(X_te)),
            'n_features': int(len(features)),
            'n_trees':    int(n_est),
        }

        importance_img = _importance_chart(rf.feature_importances_, features)
        preview = _info_panel([
            'RandomForest — trained',
            f'rows: {len(X)} (train {len(X_tr)} / test {len(X_te)})',
            f'features: {len(features)}',
            f'trees: {n_est}, depth: {max_depth or "none"}, leaf>={min_leaf}',
            f'log1p target: {log_transform}',
            '',
            f'R² test : {r2_te:.3f}    train: {r2_tr:.3f}',
            f'RMSE test: {rmse_te:.2f}  train: {rmse_tr:.2f}',
            f'Slope test: {slope_te:.3f}',
        ], title='Random Forest Regressor')

        self._result = {
            'models':     models,
            'stats':      stats,
            'importance': importance_img,
            'preview':    preview,
        }
        return self._result
