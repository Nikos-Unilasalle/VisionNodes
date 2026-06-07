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


_EXPORT_PARAMS = [
    {'id': 'out_dpi', 'label': 'Export DPI (100=screen, 300=publication)', 'type': 'int', 'default': 100, 'min': 72, 'max': 600},
    {'id': 'out_w',   'label': 'Export width px (0 = node size)',          'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
    {'id': 'out_h',   'label': 'Export height px (0 = node size)',         'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
]


def _out_size(params, default_w=540, default_h=420, inputs=None):
    dpi   = max(72, int(params.get('out_dpi', 100)))
    out_w = int(params.get('out_w', 0))
    out_h = int(params.get('out_h', 0))
    if out_w > 0 and out_h > 0:
        return out_w / dpi, out_h / dpi, dpi
    s = inputs.get('img_size') if inputs else None
    w = int(s[0]) if isinstance(s, (list, tuple)) and len(s) >= 2 else int(params.get('width', default_w))
    h = int(s[1]) if isinstance(s, (list, tuple)) and len(s) >= 2 else int(params.get('height', default_h))
    return w / dpi, h / dpi, dpi


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _report_panel(report_dict: dict, w: int, h: int, title: str, plt) -> np.ndarray:
    """Matplotlib-rendered classification report table."""
    classes = [k for k in report_dict
               if isinstance(report_dict[k], dict) and k not in ('macro avg', 'weighted avg')]

    col_labels = ['Class', 'Precision', 'Recall', 'F1', 'Support']
    rows = []
    for cls in classes:
        d = report_dict[cls]
        rows.append([str(cls),
                     f"{d.get('precision', 0):.2f}",
                     f"{d.get('recall', 0):.2f}",
                     f"{d.get('f1-score', 0):.2f}",
                     str(int(d.get('support', 0)))])
    if 'weighted avg' in report_dict:
        d = report_dict['weighted avg']
        rows.append(['weighted avg',
                     f"{d.get('precision', 0):.2f}",
                     f"{d.get('recall', 0):.2f}",
                     f"{d.get('f1-score', 0):.2f}",
                     str(int(d.get('support', 0)))])

    acc = report_dict.get('accuracy', None)
    dpi = 100
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi))
    ax.set_axis_off()
    fig.patch.set_facecolor('#161616')

    if rows:
        tbl = ax.table(cellText=rows, colLabels=col_labels,
                       loc='upper center', cellLoc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.scale(1, 1.6)

        for j in range(len(col_labels)):
            cell = tbl[0, j]
            cell.set_facecolor('#2a2a3a')
            cell.set_text_props(color='#a5b4fc', fontweight='bold')
            cell.set_edgecolor('#444466')

        for i, row in enumerate(rows):
            is_summary = row[0] == 'weighted avg'
            for j in range(len(col_labels)):
                cell = tbl[i + 1, j]
                cell.set_facecolor('#1e1e30' if is_summary else ('#181820' if i % 2 == 0 else '#1a1a28'))
                cell.set_edgecolor('#2a2a40')
                if is_summary:
                    cell.set_text_props(color='#888899', style='italic')
                elif j == 3:
                    f1 = float(row[3])
                    color = '#6ee7b7' if f1 >= 0.9 else '#fcd34d' if f1 >= 0.7 else '#f87171'
                    cell.set_text_props(color=color, fontweight='bold')
                else:
                    cell.set_text_props(color='#cccccc')

    full_title = f"{title}  ·  Accuracy {acc:.1%}" if acc is not None else title
    ax.set_title(full_title, fontsize=9, color='#cccccc', pad=8)
    fig.tight_layout(pad=0.5)
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
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
                   res, acc, model_name, fig_w, fig_h, dpi, plt):
    X_all  = np.vstack([X_tr, X_te]) if len(X_te) else X_tr
    margin = (X_all.max(axis=0) - X_all.min(axis=0)) * 0.12 + 1e-6
    xx, yy = np.meshgrid(
        np.linspace(X_all[:, 0].min() - margin[0], X_all[:, 0].max() + margin[0], res),
        np.linspace(X_all[:, 1].min() - margin[1], X_all[:, 1].max() + margin[1], res),
    )
    Z = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
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
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img


def _confusion_plot(model, X_te, y_te, classes, cmap, acc, model_name, fig_w, fig_h, dpi, plt):
    from sklearn.metrics import confusion_matrix
    if len(X_te) == 0:
        bh, bw = int(fig_h * dpi), int(fig_w * dpi)
        blank = np.full((bh, bw, 3), 22, dtype=np.uint8)
        cv2.putText(blank, "No test data", (20, bh // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        return blank

    cm = confusion_matrix(y_te, model.predict(X_te))
    n  = len(classes)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
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
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img


# ─── Linear Regression ────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_linear_regression',
    label='Linear Regression',
    category='Machine Learning',
    icon='TrendingUp',
    description=(
        "Linear regression: predicted vs actual scatter, residuals, "
        "and feature coefficients bar chart. "
        "Outputs: train/test R², RMSE."
    ),
    inputs=[
        {'id': 'train',    'color': 'data', 'label': 'Train set'},
        {'id': 'test',     'color': 'data', 'label': 'Test set'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'preview',    'color': 'image',  'label': 'Predicted vs Actual + Residuals'},
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
        *_EXPORT_PARAMS,
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
        fig_w, fig_h, dpi = _out_size(params, 600, 420, inputs=inputs)

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
            X_tr, y_tr_raw, X_te, y_te_raw = _prepare_Xy(train_df, test_df, features, target)
            
            if y_tr_raw.dtype.kind in 'OSU' or (len(y_te_raw) and y_te_raw.dtype.kind in 'OSU'):
                from sklearn.preprocessing import LabelEncoder
                le = LabelEncoder()
                y_tr = le.fit_transform(y_tr_raw.astype(str)).astype(float)
                y_te = le.transform(y_te_raw.astype(str)).astype(float) if len(y_te_raw) > 0 else np.array([], dtype=float)
            else:
                y_tr = y_tr_raw.astype(float)
                y_te = y_te_raw.astype(float)
                
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
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(fig_w, fig_h))

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
            preview_img = _fig_to_bgr(fig, dpi)
            plt.close(fig)

            # ── Coefficients bar chart ────────────────────────────────────
            coefs  = model.coef_
            n_feat = len(features)
            bar_h  = max(3.0, n_feat * 0.35)
            fig_c, ax_c = plt.subplots(figsize=(max(5.0, fig_w * dpi / 120), bar_h))

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
            coef_img = _fig_to_bgr(fig_c, dpi)
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
    category='Machine Learning',
    icon='Zap',
    description=(
        "Support Vector Machine. "
        "2 features → decision boundary. N features → confusion matrix. "
        "Adjust C (regularization) and kernel to explore margins."
    ),
    inputs=[
        {'id': 'train',    'color': 'data', 'label': 'Train set'},
        {'id': 'test',     'color': 'data', 'label': 'Test set'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'preview',     'color': 'image',  'label': 'Decision Boundary / Confusion Matrix'},
        {'id': 'accuracy',    'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc',   'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'report',      'color': 'image',  'label': 'Classification report'},
        {'id': 'report_data', 'color': 'dict',   'label': 'Report dict'},
    ],
    params=[
        {'id': 'features',     'label': 'Features (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'target',       'label': 'Target column',                  'type': 'string', 'default': ''},
        {'id': 'C',            'label': 'C (regularization)',             'type': 'float',  'default': 1.0, 'min': 0.001, 'max': 1000.0},
        {'id': 'kernel',       'label': 'Kernel',                         'type': 'enum',   'options': _KERNELS, 'default': 0},
        {'id': 'gamma',        'label': 'Gamma',                          'type': 'enum',   'options': ['scale', 'auto'], 'default': 0},
        {'id': 'degree',       'label': 'Degree (poly only)',             'type': 'int',    'default': 3, 'min': 2, 'max': 6},
        {'id': 'standardize',  'label': 'Standardize features',           'type': 'bool',   'default': True},
        {'id': 'colormap',     'label': 'Colormap (tree)',                'type': 'enum',   'options': _CMAP_LABELS, 'default': 0},
        {'id': 'boundary_res', 'label': 'Boundary resolution',            'type': 'int',    'default': 120, 'min': 40, 'max': 300},
        *_EXPORT_PARAMS,
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
        fig_w, fig_h, dpi = _out_size(params, 540, 420, inputs=inputs)

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
                                         test_acc, model_name, fig_w, fig_h, dpi, plt)
            else:
                preview = _confusion_plot(model, X_te, y_te, classes, cmap,
                                          test_acc, model_name, fig_w, fig_h, dpi, plt)

            if len(X_te) > 0:
                report_dict = classification_report(y_te, model.predict(X_te),
                                                    target_names=[str(c) for c in classes],
                                                    output_dict=True, zero_division=0)
            else:
                report_dict = {}
            report_w = max(int(fig_w * dpi), 420)
            report = _report_panel(report_dict, report_w, 280,
                                   title=model_name, plt=plt)

        return {
            'preview':     preview,
            'accuracy':    test_acc,
            'train_acc':   train_acc,
            'report':      report,
            'report_data': report_dict,
        }


# ─── Decision Tree ────────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_decision_tree',
    label='Decision Tree',
    category='Machine Learning',
    icon='GitBranch',
    description=(
        "Decision Tree. Use max_depth slider to control model complexity. "
        "Plots the full decision tree and feature importances."
    ),
    inputs=[
        {'id': 'train',    'color': 'data', 'label': 'Train set'},
        {'id': 'test',     'color': 'data', 'label': 'Test set'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'tree_plot',  'color': 'image',  'label': 'Decision Tree Plot'},
        {'id': 'importance', 'color': 'image',  'label': 'Feature Importances'},
        {'id': 'accuracy',   'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc',  'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'depth',      'color': 'scalar', 'label': 'Actual depth'},
    ],
    params=[
        {'id': 'features',        'label': 'Features (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'target',          'label': 'Target column',                  'type': 'string', 'default': ''},
        {'id': 'max_depth',       'label': 'Max depth (0 = unlimited)',      'type': 'int',    'default': 4, 'min': 0, 'max': 20},
        {'id': 'criterion',       'label': 'Criterion',                      'type': 'enum',   'options': ['gini', 'entropy', 'log_loss'], 'default': 0},
        {'id': 'min_samples_split','label': 'Min samples split',             'type': 'int',    'default': 2, 'min': 2, 'max': 50},
        {'id': 'colormap',        'label': 'Colormap (tree)',                'type': 'enum',   'options': _CMAP_LABELS, 'default': 3},
        *_EXPORT_PARAMS,
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
        fig_w, fig_h, dpi = _out_size(params, 700, 480, inputs=inputs)

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
            n_leaves  = model.get_n_leaves()
            tree_figw = max(fig_w, min(n_leaves * 1.4, 30.0))
            tree_figh = max(fig_h, min((real_depth or 4) * 1.6, 20.0))
            fig_t, ax_t = plt.subplots(figsize=(tree_figw, tree_figh))
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
            tree_img = _fig_to_bgr(fig_t, dpi)
            plt.close(fig_t)

            # ── Feature importances ───────────────────────────────────────
            importances = model.feature_importances_
            order       = np.argsort(importances)
            bar_h       = max(3.0, len(features) * 0.4)
            fig_i, ax_i = plt.subplots(figsize=(max(5.0, fig_w * dpi / 120), bar_h))

            colors_imp = plt.cm.get_cmap(cmap)(importances[order] / (importances.max() or 1))
            ax_i.barh(range(len(features)), importances[order],
                      color=colors_imp, alpha=0.85, edgecolor='none')
            ax_i.set_yticks(range(len(features)))
            ax_i.set_yticklabels([features[i] for i in order], fontsize=8)
            ax_i.set_xlabel('Importance (Gini / Entropy)')
            ax_i.set_title('Feature Importances', fontsize=9)
            ax_i.grid(True, axis='x')
            fig_i.tight_layout()
            imp_img = _fig_to_bgr(fig_i, dpi)
            plt.close(fig_i)

        return {
            'tree_plot':  tree_img,
            'importance': imp_img,
            'accuracy':   test_acc,
            'train_acc':  train_acc,
            'depth':      real_depth,
        }
