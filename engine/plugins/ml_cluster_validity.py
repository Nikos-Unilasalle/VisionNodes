"""
ML — Cluster Validity Indices.

ml_cluster_validity : score a clustering to help choose / maximise k.
    Takes a DataFrame holding feature columns + a cluster-label column
    (e.g. the `table` output of ml_kmeans, which appends a `cluster` column).
    Computes three internal validity indices:

      - Calinski-Harabasz : between/within dispersion ratio.  HIGHER = better.
      - Davies-Bouldin    : avg cluster similarity.            LOWER  = better.
      - Dunn              : min inter / max intra distance.    HIGHER = better.

    Sweep k externally (one node per k, or feed different cluster columns)
    and compare the scores to pick the elbow / best partition.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_cluster_validity'


def _get_mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return matplotlib, plt


def _fig_to_bgr(fig, dpi=100) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    buf.seek(0)
    arr = np.frombuffer(buf.read(), dtype=np.uint8)
    buf.close()
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _pick_features(df, feat_str, exclude):
    num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc' and c != exclude]
    if feat_str:
        sel = [c.strip() for c in feat_str.split(',') if c.strip() in num_cols]
        return sel if sel else num_cols
    return num_cols


def _dunn_index(X, labels) -> float:
    """Dunn index = min inter-cluster distance / max intra-cluster diameter.

    Centroid-based variant for tractability: inter = distance between
    centroids, intra = max distance of a point to its own centroid (x2).
    HIGHER is better.
    """
    uniq = np.unique(labels)
    if len(uniq) < 2:
        return 0.0
    centroids = np.array([X[labels == c].mean(axis=0) for c in uniq])

    # max intra-cluster diameter (worst spread of any cluster)
    max_intra = 0.0
    for i, c in enumerate(uniq):
        pts = X[labels == c]
        if len(pts) == 0:
            continue
        d = np.linalg.norm(pts - centroids[i], axis=1)
        max_intra = max(max_intra, float(d.max()) * 2.0)
    if max_intra <= 0:
        return 0.0

    # min inter-cluster centroid distance
    min_inter = np.inf
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            min_inter = min(min_inter, float(np.linalg.norm(centroids[i] - centroids[j])))

    return float(min_inter / max_intra) if np.isfinite(min_inter) else 0.0


@vision_node(
    type_id='ml_cluster_validity',
    label='Cluster Validity',
    category='Machine Learning',
    icon='Gauge',
    description=(
        "Score a clustering to choose k. Feed a DataFrame with a cluster-label "
        "column (e.g. ml_kmeans table output). Outputs Calinski-Harabasz (↑ better), "
        "Davies-Bouldin (↓ better) and Dunn (↑ better). Compare across k to pick the best."
    ),
    inputs=[
        {'id': 'table', 'color': 'data', 'label': 'DataFrame + cluster'},
    ],
    outputs=[
        {'id': 'calinski_harabasz', 'color': 'scalar', 'label': 'Calinski-Harabasz ↑'},
        {'id': 'davies_bouldin',    'color': 'scalar', 'label': 'Davies-Bouldin ↓'},
        {'id': 'dunn',              'color': 'scalar', 'label': 'Dunn ↑'},
        {'id': 'preview',           'color': 'image',  'label': 'Scores'},
        {'id': 'df_meta',           'color': 'dict',   'label': 'Scores dict'},
    ],
    params=[
        {'id': 'cluster_col',  'label': 'Cluster column',                  'type': 'string', 'default': 'cluster', 'hints': 'df_columns'},
        {'id': 'features',     'label': 'Features (blank = all numeric)',   'type': 'string', 'default': '', 'hints': 'df_columns'},
        {'id': 'standardize',  'label': 'Standardize features',            'type': 'bool',   'default': True},
        {'id': 'show_plot',    'label': 'Show score bars',                 'type': 'bool',   'default': True},
    ],
    resizable=True,
    min_width=300,
    min_height=220,
)
class MLClusterValidityNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score
        from sklearn.preprocessing import StandardScaler

        cluster_col = str(params.get('cluster_col', 'cluster')).strip()
        feat_str    = str(params.get('features', '')).strip()
        standardize = bool(params.get('standardize', True))
        show_plot   = bool(params.get('show_plot', True))

        if cluster_col not in df.columns:
            send_notification(f"Cluster Validity: column '{cluster_col}' not found", level='warning', notif_id=_NOTIF_ID)
            return {}

        features = _pick_features(df, feat_str, exclude=cluster_col)
        if not features:
            send_notification("Cluster Validity: no numeric features found", level='warning', notif_id=_NOTIF_ID)
            return {}

        valid_mask = df[features].notna().all(axis=1) & df[cluster_col].notna()
        X      = df[features][valid_mask].values.astype(float)
        labels = df[cluster_col][valid_mask].values

        n_clusters = len(np.unique(labels))
        if n_clusters < 2 or len(X) <= n_clusters:
            send_notification(f"Cluster Validity: need ≥2 clusters and >k samples (k={n_clusters})", level='warning', notif_id=_NOTIF_ID)
            return {}

        if standardize:
            X = StandardScaler().fit_transform(X)

        ch   = float(calinski_harabasz_score(X, labels))
        db   = float(davies_bouldin_score(X, labels))
        dunn = _dunn_index(X, labels)

        scores = {'calinski_harabasz': ch, 'davies_bouldin': db, 'dunn': dunn, 'k': n_clusters}

        preview = None
        if show_plot:
            _, plt = _get_mpl()
            names  = ['Calinski-H ↑', 'Davies-B ↓', 'Dunn ↑']
            vals   = [ch, db, dunn]
            colors = ['#5b9cf6', '#f59e0b', '#34d399']
            with plt.rc_context({
                'figure.facecolor': '#161616', 'axes.facecolor': '#1e1e1e',
                'text.color': '#cccccc', 'axes.labelcolor': '#cccccc',
                'xtick.color': '#aaaaaa', 'ytick.color': '#aaaaaa',
                'axes.edgecolor': '#555555',
            }):
                fig, ax = plt.subplots(figsize=(4.4, 3.0))
                bars = ax.bar(names, vals, color=colors, alpha=0.9, edgecolor='none')
                for b, v in zip(bars, vals):
                    ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                            f'{v:.3g}', ha='center', va='bottom', fontsize=8, color='#eeeeee')
                ax.set_title(f'Cluster validity  (k={n_clusters})', fontsize=9)
                ax.margins(y=0.18)
                fig.tight_layout()
                preview = _fig_to_bgr(fig)
                plt.close(fig)

        return {
            'calinski_harabasz': ch,
            'davies_bouldin':    db,
            'dunn':              dunn,
            'preview':           preview,
            'df_meta':           scores,
        }
