"""
ML Training — Classifiers (Train/Test Split, KNN).
Designed for the VNStudio ML formation — pedagogical focus:
- ml_train_test_split : splits a DataFrame into train/test sets
- ml_knn_classifier   : KNN with k slider, decision boundary (2 features) or
                        confusion matrix (N features), accuracy output
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_clf'

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

_METRICS = ['euclidean', 'manhattan', 'chebyshev', 'minkowski']


def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


_EXPORT_PARAMS = [
    {'id': 'out_dpi', 'label': 'DPI export (100=écran, 300=publication)', 'type': 'int', 'default': 100, 'min': 72, 'max': 600},
    {'id': 'out_w',   'label': 'Largeur export px  (0 = taille nœud)',    'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
    {'id': 'out_h',   'label': 'Hauteur export px  (0 = taille nœud)',    'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
]


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _out_size(params, default_w=540, default_h=420):
    dpi   = max(72, int(params.get('out_dpi', 100)))
    out_w = int(params.get('out_w', 0))
    out_h = int(params.get('out_h', 0))
    if out_w > 0 and out_h > 0:
        return out_w / dpi, out_h / dpi, dpi
    return int(params.get('width', default_w)) / dpi, int(params.get('height', default_h)) / dpi, dpi


# ─── Train / Test Split ───────────────────────────────────────────────────────

@vision_node(
    type_id='ml_train_test_split',
    label='Train / Test Split',
    category='ML / Data',
    icon='Scissors',
    description="Split a DataFrame into training and test sets. Connect train → model, test → evaluation.",
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'train',       'color': 'data',   'label': 'Train set'},
        {'id': 'test',        'color': 'data',   'label': 'Test set'},
        {'id': 'train_count', 'color': 'scalar', 'label': 'Train rows'},
        {'id': 'test_count',  'color': 'scalar', 'label': 'Test rows'},
        {'id': 'preview',     'color': 'image',  'label': 'Split info'},
    ],
    params=[
        {'id': 'test_size',    'label': 'Test size (%)',   'type': 'int',    'default': 20,  'min': 5,  'max': 50},
        {'id': 'stratify_col', 'label': 'Stratify by',    'type': 'string', 'default': ''},
        {'id': 'random_state', 'label': 'Random seed',    'type': 'int',    'default': 42,  'min': 0,  'max': 9999},
        {'id': 'shuffle',      'label': 'Shuffle',        'type': 'bool',   'default': True},
    ],
    resizable=True,
    min_width=260,
    min_height=160,
)
class MLTrainTestSplitNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.model_selection import train_test_split

        test_size    = int(params.get('test_size', 20)) / 100.0
        stratify_col = str(params.get('stratify_col', '')).strip()
        random_state = int(params.get('random_state', 42))
        shuffle      = bool(params.get('shuffle', True))

        stratify = df[stratify_col] if stratify_col and stratify_col in df.columns else None

        try:
            train, test = train_test_split(
                df, test_size=test_size,
                random_state=random_state,
                shuffle=shuffle,
                stratify=stratify,
            )
        except Exception as e:
            send_notification(f"Train/Test Split error: {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        w = int(params.get('width',  300))
        h = int(params.get('height', 160))
        img = np.full((h, w, 3), 22, dtype=np.uint8)
        cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
        cv2.putText(img, "Train / Test Split", (8, 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
        total = len(train) + len(test)
        pct_train = len(train) / total if total else 0
        bar_w = w - 16
        cv2.rectangle(img, (8, 38), (8 + bar_w, 54), (60, 60, 60), -1)
        cv2.rectangle(img, (8, 38), (8 + int(bar_w * pct_train), 54), (59, 130, 246), -1)
        cv2.putText(img, f"Train : {len(train)} rows  ({100*pct_train:.0f}%)",
                    (8, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 200, 255), 1, cv2.LINE_AA)
        cv2.putText(img, f"Test  : {len(test)} rows  ({100*(1-pct_train):.0f}%)",
                    (8, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 80), 1, cv2.LINE_AA)
        if stratify_col:
            cv2.putText(img, f"Stratified by: {stratify_col}",
                        (8, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1, cv2.LINE_AA)

        return {
            'train':       train,
            'test':        test,
            'train_count': float(len(train)),
            'test_count':  float(len(test)),
            'preview':     img,
        }


# ─── KNN Classifier ───────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_knn_classifier',
    label='KNN Classifier',
    category='ML / Classifiers',
    icon='Users',
    description=(
        "K-Nearest Neighbors classifier. "
        "2 features → decision boundary + scatter. "
        "N features → confusion matrix. "
        "Slide k to see how the boundary changes in real time."
    ),
    inputs=[
        {'id': 'train', 'color': 'data', 'label': 'Train set'},
        {'id': 'test',  'color': 'data', 'label': 'Test set'},
    ],
    outputs=[
        {'id': 'preview',    'color': 'image',  'label': 'Decision boundary / Confusion matrix'},
        {'id': 'accuracy',   'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc',  'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'report',     'color': 'image',  'label': 'Classification report'},
    ],
    params=[
        {'id': 'features',  'label': 'Feature columns (comma-separated)',  'type': 'string', 'default': ''},
        {'id': 'target',    'label': 'Target column',                      'type': 'string', 'default': ''},
        {'id': 'k',         'label': 'k (neighbors)',                      'type': 'int',    'default': 5,  'min': 1, 'max': 50},
        {'id': 'metric',    'label': 'Distance metric',                    'type': 'enum',   'options': _METRICS, 'default': 0},
        {'id': 'weights',   'label': 'Weights',                            'type': 'enum',   'options': ['uniform', 'distance'], 'default': 0},
        {'id': 'colormap',  'label': 'Colormap',                           'type': 'enum',   'options': ['tab10', 'Set1', 'Set2', 'viridis'], 'default': 0},
        {'id': 'boundary_res', 'label': 'Boundary resolution',             'type': 'int',    'default': 150, 'min': 50, 'max': 400},
        *_EXPORT_PARAMS,
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLKnnClassifierNode(NodeProcessor):
    def process(self, inputs, params):
        train_df = inputs.get('train')
        test_df  = inputs.get('test')
        if train_df is None or test_df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.preprocessing import LabelEncoder
        from sklearn.metrics import classification_report, confusion_matrix

        _, plt = _get_mpl()

        feat_str = str(params.get('features', '')).strip()
        target   = str(params.get('target', '')).strip()
        k        = int(params.get('k', 5))
        metric   = _METRICS[int(params.get('metric', 0))]
        weights  = ['uniform', 'distance'][int(params.get('weights', 0))]
        cmaps    = ['tab10', 'Set1', 'Set2', 'viridis']
        cmap     = cmaps[int(params.get('colormap', 0))]
        res      = int(params.get('boundary_res', 150))
        fig_w, fig_h, dpi = _out_size(params, 540, 420)

        all_cols  = list(train_df.columns)
        num_cols  = [c for c in all_cols if train_df[c].dtype.kind in 'biufc']

        # Auto-pick target (last column) and features (all numeric except target)
        if not target or target not in all_cols:
            target = all_cols[-1]
        if feat_str:
            features = [c.strip() for c in feat_str.split(',') if c.strip() in num_cols and c.strip() != target]
        else:
            features = [c for c in num_cols if c != target]

        if not features:
            send_notification("KNN: no feature columns found", level='warning', notif_id=_NOTIF_ID)
            return {}

        # Encode target labels to integers
        le = LabelEncoder()
        try:
            X_train = train_df[features].values.astype(float)
            X_test  = test_df[features].values.astype(float)
            y_train = le.fit_transform(train_df[target].astype(str))
            y_test  = le.transform(test_df[target].astype(str))
        except Exception as e:
            send_notification(f"KNN: data preparation error — {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        # Remove NaN rows
        mask_tr = ~np.isnan(X_train).any(axis=1)
        mask_te = ~np.isnan(X_test).any(axis=1)
        X_train, y_train = X_train[mask_tr], y_train[mask_tr]
        X_test,  y_test  = X_test[mask_te],  y_test[mask_te]

        if len(X_train) == 0:
            send_notification("KNN: train set is empty after NaN removal", level='error', notif_id=_NOTIF_ID)
            return {}

        knn = KNeighborsClassifier(n_neighbors=min(k, len(X_train)),
                                   metric=metric, weights=weights)
        knn.fit(X_train, y_train)

        train_acc = float(knn.score(X_train, y_train))
        test_acc  = float(knn.score(X_test,  y_test)) if len(X_test) > 0 else 0.0
        classes   = le.classes_

        # ── Main visualization ──────────────────────────────────────────────
        with plt.rc_context(_MPL_DARK):
            if len(features) == 2:
                preview = _plot_boundary(knn, X_train, y_train, X_test, y_test,
                                         features, classes, cmap, res,
                                         test_acc, k, fig_w, fig_h, dpi, plt)
            else:
                preview = _plot_confusion(knn, X_test, y_test, classes,
                                          cmap, test_acc, k, fig_w, fig_h, dpi, plt)

            # ── Classification report panel ─────────────────────────────────
            if len(X_test) > 0:
                report_str = classification_report(y_test, knn.predict(X_test),
                                                   target_names=[str(c) for c in classes],
                                                   zero_division=0)
            else:
                report_str = "(no test data)"
            report_img = _text_panel(report_str, max(int(fig_w * dpi), 380), 260,
                                     title=f"Classification Report  —  k={k}")

        return {
            'preview':   preview,
            'accuracy':  test_acc,
            'train_acc': train_acc,
            'report':    report_img,
        }


# ─── Plot helpers ─────────────────────────────────────────────────────────────

def _plot_boundary(knn, X_tr, y_tr, X_te, y_te, features, classes, cmap, res,
                   test_acc, k, fig_w, fig_h, dpi, plt):
    """2-feature decision boundary with train + test scatter overlay."""
    X_all = np.vstack([X_tr, X_te]) if len(X_te) else X_tr
    margin = (X_all.max(axis=0) - X_all.min(axis=0)) * 0.1 + 1e-6
    x0_min, x0_max = X_all[:, 0].min() - margin[0], X_all[:, 0].max() + margin[0]
    x1_min, x1_max = X_all[:, 1].min() - margin[1], X_all[:, 1].max() + margin[1]

    xx, yy = np.meshgrid(np.linspace(x0_min, x0_max, res),
                         np.linspace(x1_min, x1_max, res))
    Z = knn.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.contourf(xx, yy, Z, alpha=0.25, cmap=cmap, levels=len(classes))
    ax.contour(xx, yy, Z, colors='#555', linewidths=0.5)

    colors = plt.cm.get_cmap(cmap)(np.linspace(0, 1, len(classes)))
    for i, (cls, color) in enumerate(zip(classes, colors)):
        mask = y_tr == i
        ax.scatter(X_tr[mask, 0], X_tr[mask, 1], color=color, s=30,
                   edgecolors='white', linewidths=0.4, label=str(cls), zorder=3)
    if len(X_te):
        for i, color in enumerate(colors):
            mask = y_te == i
            ax.scatter(X_te[mask, 0], X_te[mask, 1], color=color, s=60,
                       marker='*', edgecolors='white', linewidths=0.4, zorder=4)

    ax.set_xlabel(features[0])
    ax.set_ylabel(features[1])
    ax.set_title(f"KNN  k={k}  |  test acc = {test_acc:.1%}", fontsize=10)
    ax.legend(fontsize=8, labelcolor='#cccccc', loc='best')
    fig.tight_layout()
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img


def _plot_confusion(knn, X_te, y_te, classes, cmap, test_acc, k, fig_w, fig_h, dpi, plt):
    """Confusion matrix heatmap for N-feature case."""
    from sklearn.metrics import confusion_matrix
    out_w, out_h = int(fig_w * dpi), int(fig_h * dpi)
    if len(X_te) == 0:
        blank = np.full((out_h, out_w, 3), 22, dtype=np.uint8)
        cv2.putText(blank, "No test data", (20, out_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        return blank

    cm = confusion_matrix(y_te, knn.predict(X_te))
    n  = len(classes)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(cm, cmap=cmap, aspect='auto')
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels([str(c) for c in classes], rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels([str(c) for c in classes], fontsize=8)
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')

    for i in range(n):
        for j in range(n):
            color = 'white' if cm[i, j] < cm.max() * 0.6 else 'black'
            ax.text(j, i, str(cm[i, j]), ha='center', va='center', fontsize=9, color=color)

    ax.set_title(f"Confusion Matrix  k={k}  |  acc = {test_acc:.1%}", fontsize=10)
    fig.tight_layout()
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img


def _text_panel(text: str, w: int, h: int, title: str = '') -> np.ndarray:
    img = np.full((h, w, 3), 22, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
    cv2.putText(img, title, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
    y0, line_h = 44, 15
    max_lines = (h - y0) // line_h
    for i, line in enumerate(text.split('\n')[:max_lines]):
        color = (140, 200, 255) if i == 0 else (185, 185, 185)
        cv2.putText(img, line[:90], (8, y0 + i * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
    return img
