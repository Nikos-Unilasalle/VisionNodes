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
    {'id': 'out_dpi', 'label': 'Export DPI (100=screen, 300=publication)', 'type': 'int', 'default': 100, 'min': 72, 'max': 600},
    {'id': 'out_w',   'label': 'Export width px (0 = node size)',          'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
    {'id': 'out_h',   'label': 'Export height px (0 = node size)',         'type': 'int', 'default': 0,   'min': 0,  'max': 5000},
]


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


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


# ─── Train / Test Split ───────────────────────────────────────────────────────

@vision_node(
    type_id='ml_train_test_split',
    label='Train / Test Split',
    category='Machine Learning',
    icon='Scissors',
    description="Split a DataFrame into training and test sets. Connect train → model, test → evaluation.",
    inputs=[
        {'id': 'table',    'color': 'data', 'label': 'DataFrame'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'train',       'color': 'data',   'label': 'Train set'},
        {'id': 'test',        'color': 'data',   'label': 'Test set'},
        {'id': 'train_count', 'color': 'scalar', 'label': 'Train rows'},
        {'id': 'test_count',  'color': 'scalar', 'label': 'Test rows'},
        {'id': 'preview',     'color': 'image',  'label': 'Split info'},
    ],
    params=[
        {'id': '_sec_split', 'label': 'Split Config', 'type': 'section'},
        {'id': 'test_size',      'label': 'Test size (%)',              'type': 'int',    'default': 20,   'min': 5,  'max': 50},
        {'id': 'stratify_col',   'label': 'Stratify by',                'type': 'string', 'default': ''},
        {'id': 'random_state',   'label': 'Random seed',                'type': 'int',    'default': 42,   'min': 0,  'max': 9999},
        {'id': 'shuffle',        'label': 'Shuffle',                    'type': 'bool',   'default': True},
        {'id': '_sec_filter', 'label': 'Filter', 'type': 'section'},
        {'id': 'filter_col',     'label': 'Filter column (blank=none)', 'type': 'string', 'default': 'label'},
        {'id': 'filter_nodata',  'label': 'Exclude value (unlabeled)',  'type': 'float',  'default': -1.0},
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

        # Filter out unlabeled rows (e.g. label == -1) before splitting
        filter_col    = str(params.get('filter_col', 'label')).strip()
        filter_nodata = float(params.get('filter_nodata', -1.0))
        if filter_col and filter_col in df.columns:
            df = df[df[filter_col] != filter_nodata].copy()
            if len(df) == 0:
                send_notification('Train/Test Split: no labeled rows after filter', level='warning', notif_id=_NOTIF_ID)
                return {}

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

        s = inputs.get('img_size')
        w = int(s[0]) if isinstance(s, (list, tuple)) and len(s) >= 2 else int(params.get('width', 300))
        h = int(s[1]) if isinstance(s, (list, tuple)) and len(s) >= 2 else int(params.get('height', 160))
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
    category='Machine Learning',
    icon='Users',
    description=(
        "K-Nearest Neighbors classifier. "
        "2 features → decision boundary + scatter. "
        "N features → confusion matrix. "
        "Slide k to see how the boundary changes in real time."
    ),
    inputs=[
        {'id': 'train',    'color': 'data', 'label': 'Train set'},
        {'id': 'test',     'color': 'data', 'label': 'Test set'},
        {'id': 'img_size', 'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'preview',     'color': 'image',  'label': 'Decision boundary / Confusion matrix'},
        {'id': 'accuracy',    'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc',   'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'report',      'color': 'image',  'label': 'Classification report'},
        {'id': 'report_data', 'color': 'dict',   'label': 'Report dict'},
    ],
    params=[
        {'id': '_sec_data', 'label': 'Data', 'type': 'section'},
        {'id': 'features',  'label': 'Feature columns (comma-separated)',  'type': 'string', 'default': ''},
        {'id': 'target',    'label': 'Target column',                      'type': 'string', 'default': ''},
        {'id': '_sec_model', 'label': 'Model Config', 'type': 'section'},
        {'id': 'k',         'label': 'k (neighbors)',                      'type': 'int',    'default': 5,  'min': 1, 'max': 50},
        {'id': 'metric',    'label': 'Distance metric',                    'type': 'enum',   'options': _METRICS, 'default': 0},
        {'id': 'weights',   'label': 'Weights',                            'type': 'enum',   'options': ['uniform', 'distance'], 'default': 0},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'colormap',  'label': 'Colormap',                           'type': 'enum',   'options': ['tab10', 'Set1', 'Set2', 'viridis'], 'default': 0},
        {'id': 'boundary_res', 'label': 'Boundary resolution',             'type': 'int',    'default': 150, 'min': 50, 'max': 400},
        {'id': '_sec_export', 'label': 'Export', 'type': 'section'},
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
        fig_w, fig_h, dpi = _out_size(params, 540, 420, inputs=inputs)

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
                report_dict = classification_report(y_test, knn.predict(X_test),
                                                    target_names=[str(c) for c in classes],
                                                    output_dict=True, zero_division=0)
            else:
                report_dict = {}
            report_w = max(int(fig_w * dpi), 420)
            report_img = _report_panel(report_dict, report_w, 280,
                                       title=f"KNN  k={k}", plt=plt)

        return {
            'preview':     preview,
            'accuracy':    test_acc,
            'train_acc':   train_acc,
            'report':      report_img,
            'report_data': report_dict,
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


# ─── Random Forest Classifier ─────────────────────────────────────────────────

_RF_CRITERIA = ['gini', 'entropy', 'log_loss']
_RF_MAX_FEAT = ['sqrt', 'log2', 'none (all)']


@vision_node(
    type_id='ml_random_forest',
    label='Random Forest',
    category='Machine Learning',
    icon='TreePine',
    description=(
        "Random Forest classifier. "
        "Confusion matrix + per-class report. "
        "Feature importance bar chart. "
        "Slide n_estimators or max_depth to see the effect in real time."
    ),
    inputs=[
        {'id': 'train',         'color': 'data', 'label': 'Train set'},
        {'id': 'test',          'color': 'data', 'label': 'Test set'},
        {'id': 'predict_table', 'color': 'data', 'label': 'Full table (predict all pixels)'},
        {'id': 'img_size',      'color': 'list', 'label': 'Img Size'},
    ],
    outputs=[
        {'id': 'preview',      'color': 'image',  'label': 'Confusion matrix'},
        {'id': 'importance',   'color': 'image',  'label': 'Feature importance'},
        {'id': 'accuracy',     'color': 'scalar', 'label': 'Test accuracy'},
        {'id': 'train_acc',    'color': 'scalar', 'label': 'Train accuracy'},
        {'id': 'oob_score',    'color': 'scalar', 'label': 'OOB score'},
        {'id': 'report',       'color': 'image',  'label': 'Classification report'},
        {'id': 'report_data',  'color': 'dict',   'label': 'Report dict'},
        {'id': 'predictions',  'color': 'data',   'label': 'Predictions (all pixels)'},
    ],
    params=[
        {'id': '_sec_rf_data', 'label': 'Data', 'type': 'section'},
        {'id': 'features',      'label': 'Feature columns (comma-separated, blank=auto)', 'type': 'string', 'default': ''},
        {'id': 'target',        'label': 'Target column',        'type': 'string', 'default': ''},
        {'id': '_sec_rf_training', 'label': 'Training', 'type': 'section'},
        {'id': 'n_estimators',  'label': 'Num trees',            'type': 'int',    'default': 100,  'min': 1,   'max': 500},
        {'id': 'max_depth',     'label': 'Max depth  (0 = none)','type': 'int',    'default': 0,    'min': 0,   'max': 50},
        {'id': 'min_samples_split', 'label': 'Min samples split','type': 'int',    'default': 2,    'min': 2,   'max': 50},
        {'id': 'criterion',     'label': 'Criterion',            'type': 'enum',   'options': _RF_CRITERIA, 'default': 0},
        {'id': 'max_features',  'label': 'Max features / tree',  'type': 'enum',   'options': _RF_MAX_FEAT, 'default': 0},
        {'id': 'bootstrap',     'label': 'Bootstrap',            'type': 'bool',   'default': True},
        {'id': 'oob',           'label': 'OOB score (needs bootstrap)', 'type': 'bool', 'default': False},
        {'id': 'random_state',  'label': 'Random seed',          'type': 'int',    'default': 42,   'min': 0,   'max': 9999},
        {'id': '_sec_rf_display', 'label': 'Display', 'type': 'section'},
        {'id': 'colormap',      'label': 'Colormap',             'type': 'enum',   'options': ['tab10', 'Set1', 'Set2', 'viridis'], 'default': 0},
        {'id': 'top_n_feat',    'label': 'Top N features in chart', 'type': 'int', 'default': 20,   'min': 1,   'max': 100},
        {'id': '_sec_rf_export', 'label': 'Export', 'type': 'section'},
        *_EXPORT_PARAMS,
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLRandomForestNode(NodeProcessor):
    def process(self, inputs, params):
        train_df = inputs.get('train')
        test_df  = inputs.get('test')
        if train_df is None or test_df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import LabelEncoder
        from sklearn.metrics import classification_report, confusion_matrix

        _, plt = _get_mpl()

        # ── Parameters ────────────────────────────────────────────────────────
        feat_str   = str(params.get('features', '')).strip()
        target     = str(params.get('target',   '')).strip()
        n_est      = max(1, int(params.get('n_estimators', 100)))
        max_depth  = int(params.get('max_depth', 0)) or None
        min_split  = max(2, int(params.get('min_samples_split', 2)))
        criterion  = _RF_CRITERIA[int(params.get('criterion', 0))]
        max_feat_i = int(params.get('max_features', 0))
        max_feat   = [None if v == 'none (all)' else v for v in _RF_MAX_FEAT][max_feat_i]
        bootstrap  = bool(params.get('bootstrap', True))
        oob        = bool(params.get('oob', False)) and bootstrap
        seed       = int(params.get('random_state', 42))
        cmaps      = ['tab10', 'Set1', 'Set2', 'viridis']
        cmap       = cmaps[int(params.get('colormap', 0))]
        top_n      = max(1, int(params.get('top_n_feat', 20)))
        fig_w, fig_h, dpi = _out_size(params, 540, 420, inputs=inputs)

        # ── Feature / target selection ────────────────────────────────────────
        all_cols = list(train_df.columns)
        num_cols = [c for c in all_cols if train_df[c].dtype.kind in 'biufc']

        if not target or target not in all_cols:
            target = all_cols[-1]
        if feat_str:
            features = [c.strip() for c in feat_str.split(',')
                        if c.strip() in num_cols and c.strip() != target]
        else:
            features = [c for c in num_cols if c != target]

        if not features:
            send_notification("Random Forest: no feature columns found", level='warning', notif_id=_NOTIF_ID)
            return {}

        # ── Data prep ─────────────────────────────────────────────────────────
        le = LabelEncoder()
        try:
            X_train = train_df[features].values.astype(float)
            X_test  = test_df[features].values.astype(float)
            y_train = le.fit_transform(train_df[target].astype(str))
            y_test  = le.transform(test_df[target].astype(str))
        except Exception as e:
            send_notification(f"Random Forest: data error — {e}", level='error', notif_id=_NOTIF_ID)
            return {}

        mask_tr = ~np.isnan(X_train).any(axis=1)
        mask_te = ~np.isnan(X_test).any(axis=1)
        X_train, y_train = X_train[mask_tr], y_train[mask_tr]
        X_test,  y_test  = X_test[mask_te],  y_test[mask_te]

        if len(X_train) == 0:
            send_notification("Random Forest: train set empty after NaN removal", level='error', notif_id=_NOTIF_ID)
            return {}

        # ── Train ─────────────────────────────────────────────────────────────
        rf = RandomForestClassifier(
            n_estimators=n_est,
            max_depth=max_depth,
            min_samples_split=min_split,
            criterion=criterion,
            max_features=max_feat,
            bootstrap=bootstrap,
            oob_score=oob,
            random_state=seed,
            n_jobs=-1,
        )
        rf.fit(X_train, y_train)

        train_acc = float(rf.score(X_train, y_train))
        test_acc  = float(rf.score(X_test, y_test)) if len(X_test) > 0 else 0.0
        oob_score = float(rf.oob_score_) if oob else 0.0
        classes   = le.classes_

        # ── Confusion matrix ──────────────────────────────────────────────────
        with plt.rc_context(_MPL_DARK):
            preview = _plot_confusion_rf(rf, X_test, y_test, classes,
                                         cmap, test_acc, n_est, fig_w, fig_h, dpi, plt)

            # ── Feature importance chart ───────────────────────────────────────
            importance_img = _plot_feature_importance(
                rf.feature_importances_, features, top_n,
                fig_w, fig_h, dpi, plt
            )

            # ── Report panel ──────────────────────────────────────────────────
            if len(X_test) > 0:
                report_dict = classification_report(
                    y_test, rf.predict(X_test),
                    target_names=[str(c) for c in classes],
                    output_dict=True, zero_division=0,
                )
            else:
                report_dict = {}
            report_w   = max(int(fig_w * dpi), 420)
            report_img = _report_panel(
                report_dict, report_w, 280,
                title=f"Random Forest  trees={n_est}", plt=plt
            )

        # ── Predict on full table (e.g. all geo pixels) ──────────────────────
        predictions_df = None
        pred_df = inputs.get('predict_table')
        if pred_df is not None:
            try:
                import pandas as pd
                feat_cols_avail = [c for c in features if c in pred_df.columns]
                if feat_cols_avail:
                    X_pred = pred_df[feat_cols_avail].values.astype(float)
                    valid_pred = ~np.isnan(X_pred).any(axis=1)
                    pred_out = np.full(len(pred_df), -1, dtype=np.int32)
                    if valid_pred.any():
                        pred_out[valid_pred] = rf.predict(X_pred[valid_pred])
                    result_df = pred_df[['__px_idx']].copy() if '__px_idx' in pred_df.columns else pd.DataFrame()
                    result_df['prediction'] = pred_out
                    predictions_df = result_df
            except Exception as e:
                send_notification(f"Random Forest predict_table error: {e}", level='warning', notif_id=_NOTIF_ID)

        return {
            'preview':     preview,
            'importance':  importance_img,
            'accuracy':    test_acc,
            'train_acc':   train_acc,
            'oob_score':   oob_score,
            'report':      report_img,
            'report_data': report_dict,
            'predictions': predictions_df,
        }


def _plot_confusion_rf(rf, X_te, y_te, classes, cmap, test_acc, n_est,
                       fig_w, fig_h, dpi, plt):
    """Confusion matrix for Random Forest (N features)."""
    from sklearn.metrics import confusion_matrix
    out_w, out_h = int(fig_w * dpi), int(fig_h * dpi)
    if len(X_te) == 0:
        blank = np.full((out_h, out_w, 3), 22, dtype=np.uint8)
        cv2.putText(blank, "No test data", (20, out_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        return blank

    cm = confusion_matrix(y_te, rf.predict(X_te))
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

    ax.set_title(f"Random Forest  trees={n_est}  |  acc = {test_acc:.1%}", fontsize=10)
    fig.tight_layout()
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img


def _plot_feature_importance(importances: np.ndarray, feature_names: list,
                              top_n: int, fig_w: float, fig_h: float,
                              dpi: int, plt) -> np.ndarray:
    """Horizontal bar chart of RF feature importances, top N only."""
    idx = np.argsort(importances)[::-1][:top_n]
    vals  = importances[idx]
    names = [feature_names[i] for i in idx]

    # Reverse so highest bar is at top
    vals  = vals[::-1]
    names = names[::-1]

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    colors = plt.cm.get_cmap('viridis')(np.linspace(0.25, 0.85, len(vals)))
    bars = ax.barh(range(len(vals)), vals, color=colors, edgecolor='none', height=0.7)

    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel('Importance (mean decrease in impurity)')
    ax.set_title(f'Feature Importance  (top {len(vals)})', fontsize=10)
    ax.xaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    # Value labels on bars
    for bar, val in zip(bars, vals):
        ax.text(val + 0.001, bar.get_y() + bar.get_height() / 2,
                f'{val:.3f}', va='center', fontsize=7, color='#aaaaaa')

    fig.tight_layout()
    img = _fig_to_bgr(fig, dpi)
    plt.close(fig)
    return img
