"""
ML Training — Supervised Learning (Linear Regression, SVM, Decision Tree).
Designed for the VNStudio ML formation.

ml_linear_regression : R², RMSE, scatter prédit/réel, residuals, coefficients bar chart.
ml_svm_classifier    : SVM avec C/kernel/gamma. 2 features → frontière, N → confusion matrix.
ml_decision_tree     : max_depth slider, arbre visualisé, feature importances.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_sup'

_MPL_DARK = {
    'figure.facecolor':  '#161616',
    'axes.facecolor':    '#1e1e1e',
    'axes.edgecolor':    '#555555',
    'axes.labelcolor':   '#cccccc',
    'text.color':        '#cccccc',
    'xtick.color':       '#aaaaaa',
    'ytick.color':       '#aaaaaa',
    'grid.color':        '#333333',
    'grid.linestyle':    '--',
    'grid.linewidth':    0.5,
}

_CMAPS       = ['tab10', 'Set1', 'Set2', 'viridis', 'plasma']
_CMAP_LABELS = ['Tab10', 'Set1', 'Set2', 'Viridis', 'Plasma']


def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


def _fig_to_bgr(fig) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _text_panel(text: str, w: int, h: int, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
    y0, lh = 44, 15
    for i, line in enumerate(text.split('\n')[:(h - y0) // lh]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, line[:90], (8, y0 + i * lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
    return img


def _pick_features(df, feat_str):
    num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc']
    if feat_str:
        sel = [c.strip() for c in feat_str.split(',') if c.strip() in num_cols]
        return sel if sel else num_cols
    return num_cols


def _prepare_Xy(train_df, test_df, features, target):
    """Extract X/y arrays, drop NaNs. Returns (X_tr, y_tr, X_te, y_te) or raises."""
    X_tr = train_df[features].values.astype(float)
    y_tr = train_df[target].values
    X_te = test_df[features].values.astype(float) if test_df is not None else np.empty((0, len(features)))
    y_te = test_df[target].values if test_df is not None else np.array([])

    m_tr = ~np.isnan(X_tr).any(axis=1)
    m_te = ~np.isnan(X_te).any(axis=1) if len(X_te) else np.array([], dtype=bool)
    return X_tr[m_tr], y_tr[m_tr], X_te[m_te], y_te[m_te]


# ─── Boundary / Confusion helpers (shared by SVM & DT) ────────────────────────

def _boundary_plot(model, X_tr, y_tr, X_te, y_te, features, classes, cmap,
                   res, acc, model_name, w_px, h_px, plt):
    X_all  = np.vstack([X_tr, X_te]) if len(X_te) else X_tr
    margin = (X_all.max(axis=0) - X_all.min(axis=0)) * 0.12 + 1e-6
    xx, yy = np.meshgrid(
        np.linspace(X_all[:, 0].min() - margin[0], X_all[:, 0].max() + margin[0], res),
        np.linspace(X_all[:, 1].min() - margin[1], X_all[:, 1].max() + margin[1], res),
    )
    Z = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    fig, ax = plt.subplots(figsize=(w_px / 100, h_px / 100))
    ax.contourf(xx, yy, Z, alpha=0.22, cmap=cmap, levels=len(classes))
    ax.contour(xx, yy, Z, colors='#555', linewidths=0.5)

    colors = plt.cm.get_cmap(cmap)(np.linspace(0, 1, len(classes)))
    for i, (cls, color) in enumerate(zip(classes, colors)):
        m = y_tr == i
        ax.scatter(X_tr[m, 0], X_tr[m, 1], color=color, s=28, alpha=0.8,
                   edgecolors='none', label=str(cls))
        if len(X_te):
            mt = y_te == i
            ax.scatter(X_te[mt, 0], X_te[mt, 1], color=color, s=55,
                       marker='*', edgecolors='white', linewidths=0.4, zorder=4)

    ax.set_xlabel(features[0])
    ax.set_ylabel(features[1])
    ax.set_title(f"{model_name}  |  test acc = {acc:.1%}", fontsize=10)
    ax.legend(fontsize=8, labelcolor='#cccccc', loc='best', framealpha=0.4)
    ax.grid(True)
    fig.tight_layout()
    img = _fig_to_bgr(fig)
    plt.close(fig)
    return img


def _confusion_plot(model, X_te, y_te, classes, cmap, acc, model_name, w_px, h_px, plt):
    from sklearn.metrics import confusion_matrix
    if len(X_te) == 0:
        blank = np.full((h_px, w_px, 3), 22, dtype=np.uint8)
        cv2.putText(blank, "No test data", (20, h_px // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        return blank

    cm = confusion_matrix(y_te, model.predict(X_te))
    n  = len(classes)
    fig, ax = plt.subplots(figsize=(w_px / 100, h_px / 100))
    im = ax.imshow(cm, cmap=cmap, aspect='auto')
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels([str(c) for c in classes], rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels([str(c) for c in classes], fontsize=8)
    ax.set_xlabel('Predicted'); ax.set_ylabel('Actual')
    for i in range(n):
        for j in range(n):
            color = 'white' if cm[i, j] < cm.max() * 0.6 else 'black'
            ax.text(j, i, str(cm[i, j]), ha='center', va='center', fontsize=9, color=color)
    ax.set_title(f"{model_name}  |  acc = {acc:.1%}", fontsize=10)
    fig.tight_layout()
    img = _fig_to_bgr(fig)
    plt.close(fig)
    return img


# ─── Linear Regression ────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_linear_regression',
    label='Linear Regression',
    category='ML / Supervised',
    icon='TrendingUp',
    description=(
        "Linear regression: scatter prédit vs réel, résidus, "
        "et bar chart des coefficients par feature. "
        "Sorties : R² train/test, RMSE."
    ),
    inputs=[
        {'id': 'train', 'color': 'data', 'label': 'Train set'},
        {'id': 'test',  'color': 'data', 'label': 'Test set'},
    ],
    outputs=[
        {'id': 'preview',    'color': 'image',  'label': 'Prédit vs Réel + Résidus'},
        {'id': 'coef_plot',  'color': 'image',  'label': 'Coefficients'},
        {'id': 'r2_test',    'color': 'scalar', 'label': 'R² test'},
        {'id': 'r2_train',   'color': 'scalar', 'label': 'R² train'},
        {'id': 'rmse',       'color': 'scalar', 'label': 'RMSE test'},
    ],
    params=[
        {'id': 'features',    'label': 'Features (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'target',      'label': 'Target column',                  'type': 'string', 'default': ''},
        {'id': 'fit_intercept','label': 'Fit intercept',                 'type': 'bool',   'default': True},
        {'id': 'standardize', 'label': 'Standardize features',           'type': 'bool',   'default': False},
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLLinearRegressionNode(NodeProcessor):
    def process(self, inputs, params):
        train_df = inputs.get('train')
        test_df  = inputs.get('test')
        if train_df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import StandardScaler

        _, plt = _get_mpl()

        feat_str      = str(params.get('features', '')).strip()
        target        = str(params.get('target', '')).strip()
        fit_intercept = bool(params.get('fit_intercept', True))
        standardize   = bool(params.get('standardize', False))
        w_px          = int(params.get('width',  600))
        h_px          = int(params.get('height', 420))

        all_cols = list(train_df.columns)
        num_cols = [c for c in all_cols if train_df[c].dtype.kind in 'biufc']

        if not target or target not in all_cols:
            target = all_cols[-1]
        features = _pick_features(train_df, feat_str)
        features = [f for f in features if f != target]

        if not features:
            send_notification("Linear Regression: no feature columns", level='warning', notif_id=_NOTIF_ID)
            return {}

        try:
            X_tr, y_tr, X_te, y_te = _prepare_Xy(train_df, test_df, features, target)
            y_tr = y_tr.astype(float)
            y_te = y_te.astype(float)
        except Exception as e:
            send_notification(f"Linear Regression: data error — {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        scaler = None
        if standardize:
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X_tr)
            if len(X_te):
                X_te = scaler.transform(X_te)

        model = LinearRegression(fit_intercept=fit_intercept)
        model.fit(X_tr, y_tr)

        r2_train = float(model.score(X_tr, y_tr))
        r2_test  = float(model.score(X_te, y_te)) if len(X_te) > 0 else float('nan')

        y_pred   = model.predict(X_te) if len(X_te) > 0 else np.array([])
        residuals = y_te - y_pred if len(y_te) > 0 else np.array([])
        rmse     = float(np.sqrt(np.mean(residuals ** 2))) if len(residuals) > 0 else float('nan')

        with plt.rc_context(_MPL_DARK):
            # ── Subplot: prédit vs réel + résidus ────────────────────────
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(w_px / 100, h_px / 100))

            if len(y_te) > 0:
                mn, mx = min(y_te.min(), y_pred.min()), max(y_te.max(), y_pred.max())
                ax1.scatter(y_te, y_pred, alpha=0.6, s=25, color='#3b82f6', edgecolors='none')
                ax1.plot([mn, mx], [mn, mx], '--', color='#f97316', lw=1.5, label='Perfect fit')
                ax1.set_xlabel('Actual')
                ax1.set_ylabel('Predicted')
                ax1.set_title(f'Predicted vs Actual  (R²={r2_test:.3f})', fontsize=9)
                ax1.legend(fontsize=8, labelcolor='#cccccc')
                ax1.grid(True)

                ax2.scatter(y_pred, residuals, alpha=0.6, s=25, color='#a855f7', edgecolors='none')
                ax2.axhline(0, color='#f97316', lw=1.5, linestyle='--')
                ax2.set_xlabel('Predicted')
                ax2.set_ylabel('Residual')
                ax2.set_title(f'Residuals  (RMSE={rmse:.3f})', fontsize=9)
                ax2.grid(True)
            else:
                ax1.text(0.5, 0.5, 'No test data', transform=ax1.transAxes,
                         ha='center', va='center', color='#aaa')
                ax2.text(0.5, 0.5, 'No test data', transform=ax2.transAxes,
                         ha='center', va='center', color='#aaa')

            fig.suptitle(f'Linear Regression  —  R² train={r2_train:.3f}  test={r2_test:.3f}', fontsize=10)
            fig.tight_layout()
            preview_img = _fig_to_bgr(fig)
            plt.close(fig)

            # ── Coefficients bar chart ────────────────────────────────────
            coefs  = model.coef_
            n_feat = len(features)
            bar_h  = max(3.0, n_feat * 0.35)
            fig_c, ax_c = plt.subplots(figsize=(max(5.0, w_px / 120), bar_h))

            colors = ['#3b82f6' if c >= 0 else '#ef4444' for c in coefs]
            ax_c.barh(range(n_feat), coefs, color=colors, alpha=0.85, edgecolor='none')
            ax_c.set_yticks(range(n_feat))
            ax_c.set_yticklabels(features, fontsize=8)
            ax_c.axvline(0, color='#888', lw=0.8)
            ax_c.set_xlabel('Coefficient')
            ax_c.set_title('Feature Coefficients'
                           + (f'  (intercept={model.intercept_:.3f})' if fit_intercept else ''),
                           fontsize=9)
            ax_c.grid(True, axis='x')
            fig_c.tight_layout()
            coef_img = _fig_to_bgr(fig_c)
            plt.close(fig_c)

        return {
            'preview':   preview_img,
            'coef_plot': coef_img,
            'r2_test':   r2_test,
            'r2_train':  r2_train,
            'rmse':      rmse,
        }


# ─── SVM Classifier ───────────────────────────────────────────────────────────

_KERNELS = ['rbf', 'linear', 'poly', 'sigmoid']

@vision_node(
    type_id='ml_svm_classifier',
    label='SVM Classifier',
    category='ML / Supervised',
    icon='Zap',
    description=(
        "Support Vector Machine. "
        "2 features → frontière de décision. N features → confusion matrix. "
        "Ajuster C (régularisation) et kernel pour comprendre les marges."
    ),
    inputs=[
        {'id': 'train', 'color': 'data', 'label': 'Train set'},
        {'id': 'test',  'color': 'data', 'label': 'Test set'},
    ],
    outputs=[
        {'id': 'preview',   'color': 'image',  'label': 'Frontière / Confusion matrix'},
        {'id': 'accuracy',  'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc', 'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'report',    'color': 'image',  'label': 'Classification report'},
    ],
    params=[
        {'id': 'features',     'label': 'Features (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'target',       'label': 'Target column',                  'type': 'string', 'default': ''},
        {'id': 'C',            'label': 'C  (régularisation)',            'type': 'float',  'default': 1.0, 'min': 0.001, 'max': 1000.0},
        {'id': 'kernel',       'label': 'Kernel',                         'type': 'enum',   'options': _KERNELS, 'default': 0},
        {'id': 'gamma',        'label': 'Gamma',                          'type': 'enum',   'options': ['scale', 'auto'], 'default': 0},
        {'id': 'degree',       'label': 'Degree (poly only)',             'type': 'int',    'default': 3, 'min': 2, 'max': 6},
        {'id': 'standardize',  'label': 'Standardize features',           'type': 'bool',   'default': True},
        {'id': 'colormap',     'label': 'Colormap',                       'type': 'enum',   'options': _CMAP_LABELS, 'default': 0},
        {'id': 'boundary_res', 'label': 'Résolution frontière',           'type': 'int',    'default': 120, 'min': 40, 'max': 300},
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLSVMClassifierNode(NodeProcessor):
    def process(self, inputs, params):
        train_df = inputs.get('train')
        test_df  = inputs.get('test')
        if train_df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.svm import SVC
        from sklearn.preprocessing import LabelEncoder, StandardScaler
        from sklearn.metrics import classification_report

        _, plt = _get_mpl()

        feat_str   = str(params.get('features', '')).strip()
        target     = str(params.get('target', '')).strip()
        C          = float(params.get('C', 1.0))
        kernel     = _KERNELS[int(params.get('kernel', 0))]
        gamma      = ['scale', 'auto'][int(params.get('gamma', 0))]
        degree     = int(params.get('degree', 3))
        standardize= bool(params.get('standardize', True))
        cmap       = _CMAPS[int(params.get('colormap', 0))]
        res        = int(params.get('boundary_res', 120))
        w_px       = int(params.get('width',  540))
        h_px       = int(params.get('height', 420))

        all_cols = list(train_df.columns)
        if not target or target not in all_cols:
            target = all_cols[-1]
        features = _pick_features(train_df, feat_str)
        features = [f for f in features if f != target]

        if not features:
            send_notification("SVM: no feature columns", level='warning', notif_id=_NOTIF_ID)
            return {}

        try:
            X_tr, y_tr_raw, X_te, y_te_raw = _prepare_Xy(train_df, test_df, features, target)
        except Exception as e:
            send_notification(f"SVM: data error — {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        le = LabelEncoder()
        y_tr = le.fit_transform(y_tr_raw.astype(str))
        y_te = le.transform(y_te_raw.astype(str)) if len(y_te_raw) else np.array([])
        classes = le.classes_

        if standardize:
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X_tr)
            if len(X_te):
                X_te = scaler.transform(X_te)

        model = SVC(C=C, kernel=kernel, gamma=gamma, degree=degree)
        model.fit(X_tr, y_tr)

        train_acc = float(model.score(X_tr, y_tr))
        test_acc  = float(model.score(X_te, y_te)) if len(X_te) > 0 else 0.0
        model_name = f"SVM ({kernel}, C={C})"

        with plt.rc_context(_MPL_DARK):
            if len(features) == 2:
                preview = _boundary_plot(model, X_tr, y_tr, X_te, y_te,
                                         features, classes, cmap, res,
                                         test_acc, model_name, w_px, h_px, plt)
            else:
                preview = _confusion_plot(model, X_te, y_te, classes, cmap,
                                          test_acc, model_name, w_px, h_px, plt)

            rep_str = (classification_report(y_te, model.predict(X_te),
                                             target_names=[str(c) for c in classes],
                                             zero_division=0)
                       if len(X_te) > 0 else "(no test data)")
            report = _text_panel(rep_str, max(w_px, 380), 260,
                                 title=f"Classification Report — {model_name}")

        return {
            'preview':   preview,
            'accuracy':  test_acc,
            'train_acc': train_acc,
            'report':    report,
        }


# ─── Decision Tree ────────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_decision_tree',
    label='Decision Tree',
    category='ML / Supervised',
    icon='GitBranch',
    description=(
        "Arbre de décision. Slider max_depth pour observer la complexité de l'arbre. "
        "Affiche l'arbre complet + bar chart des feature importances."
    ),
    inputs=[
        {'id': 'train', 'color': 'data', 'label': 'Train set'},
        {'id': 'test',  'color': 'data', 'label': 'Test set'},
    ],
    outputs=[
        {'id': 'tree_plot',  'color': 'image',  'label': 'Arbre de décision'},
        {'id': 'importance', 'color': 'image',  'label': 'Feature importances'},
        {'id': 'accuracy',   'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc',  'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'depth',      'color': 'scalar', 'label': 'Profondeur réelle'},
    ],
    params=[
        {'id': 'features',        'label': 'Features (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'target',          'label': 'Target column',                  'type': 'string', 'default': ''},
        {'id': 'max_depth',       'label': 'Max depth (0 = illimité)',        'type': 'int',    'default': 4, 'min': 0, 'max': 20},
        {'id': 'criterion',       'label': 'Criterion',                      'type': 'enum',   'options': ['gini', 'entropy', 'log_loss'], 'default': 0},
        {'id': 'min_samples_split','label': 'Min samples split',             'type': 'int',    'default': 2, 'min': 2, 'max': 50},
        {'id': 'colormap',        'label': 'Colormap (arbre)',               'type': 'enum',   'options': _CMAP_LABELS, 'default': 3},
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLDecisionTreeNode(NodeProcessor):
    def process(self, inputs, params):
        train_df = inputs.get('train')
        test_df  = inputs.get('test')
        if train_df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.tree import DecisionTreeClassifier, plot_tree
        from sklearn.preprocessing import LabelEncoder

        _, plt = _get_mpl()

        feat_str   = str(params.get('features', '')).strip()
        target     = str(params.get('target', '')).strip()
        max_depth  = int(params.get('max_depth', 4)) or None
        criteria   = ['gini', 'entropy', 'log_loss']
        criterion  = criteria[int(params.get('criterion', 0))]
        min_split  = int(params.get('min_samples_split', 2))
        cmap       = _CMAPS[int(params.get('colormap', 3))]
        w_px       = int(params.get('width',  700))
        h_px       = int(params.get('height', 480))

        all_cols = list(train_df.columns)
        if not target or target not in all_cols:
            target = all_cols[-1]
        features = _pick_features(train_df, feat_str)
        features = [f for f in features if f != target]

        if not features:
            send_notification("Decision Tree: no feature columns", level='warning', notif_id=_NOTIF_ID)
            return {}

        try:
            X_tr, y_tr_raw, X_te, y_te_raw = _prepare_Xy(train_df, test_df, features, target)
        except Exception as e:
            send_notification(f"Decision Tree: data error — {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        le = LabelEncoder()
        y_tr = le.fit_transform(y_tr_raw.astype(str))
        y_te = le.transform(y_te_raw.astype(str)) if len(y_te_raw) else np.array([])
        classes = le.classes_

        model = DecisionTreeClassifier(
            max_depth=max_depth, criterion=criterion,
            min_samples_split=min_split, random_state=42,
        )
        model.fit(X_tr, y_tr)

        train_acc  = float(model.score(X_tr, y_tr))
        test_acc   = float(model.score(X_te, y_te)) if len(X_te) > 0 else 0.0
        real_depth = float(model.get_depth())

        with plt.rc_context(_MPL_DARK):
            # ── Arbre visualisé ───────────────────────────────────────────
            n_leaves = model.get_n_leaves()
            fig_w    = max(w_px / 100, min(n_leaves * 1.4, 30.0))
            fig_h    = max(h_px / 100, min((real_depth or 4) * 1.6, 20.0))
            fig_t, ax_t = plt.subplots(figsize=(fig_w, fig_h))
            plot_tree(
                model,
                feature_names=features,
                class_names=[str(c) for c in classes],
                filled=True, rounded=True, fontsize=7,
                impurity=True, proportion=False,
                ax=ax_t,
            )
            ax_t.set_title(
                f"Decision Tree  —  depth={int(real_depth)}  leaves={n_leaves}  "
                f"acc={test_acc:.1%}  ({criterion})",
                fontsize=9,
            )
            fig_t.tight_layout()
            tree_img = _fig_to_bgr(fig_t)
            plt.close(fig_t)

            # ── Feature importances ───────────────────────────────────────
            importances = model.feature_importances_
            order       = np.argsort(importances)
            bar_h       = max(3.0, len(features) * 0.4)
            fig_i, ax_i = plt.subplots(figsize=(max(5.0, w_px / 120), bar_h))

            colors_imp = plt.cm.get_cmap(cmap)(importances[order] / (importances.max() or 1))
            ax_i.barh(range(len(features)), importances[order],
                      color=colors_imp, alpha=0.85, edgecolor='none')
            ax_i.set_yticks(range(len(features)))
            ax_i.set_yticklabels([features[i] for i in order], fontsize=8)
            ax_i.set_xlabel('Importance (Gini / Entropy)')
            ax_i.set_title('Feature Importances', fontsize=9)
            ax_i.grid(True, axis='x')
            fig_i.tight_layout()
            imp_img = _fig_to_bgr(fig_i)
            plt.close(fig_i)

        return {
            'tree_plot':  tree_img,
            'importance': imp_img,
            'accuracy':   test_acc,
            'train_acc':  train_acc,
            'depth':      real_depth,
        }
