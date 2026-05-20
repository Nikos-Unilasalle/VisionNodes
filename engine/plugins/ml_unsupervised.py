"""
ML Training — Unsupervised Learning (K-Means, PCA).
Designed for the VNStudio ML formation.

ml_kmeans : K-Means clustering with k slider.
            - 2 features  → direct scatter + decision regions
            - N features  → PCA 2D projection for display
            Outputs: DataFrame + cluster label, inertia, silhouette score.

ml_pca    : Principal Component Analysis.
            - Scatter PC1 vs PC2 (colored by any column)
            - Explained variance bar chart with cumulative curve
            - Standardisation optionnelle (StandardScaler)
            Outputs: projected DataFrame, scatter, variance plot, PC1/PC2 variance %.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_unsup'

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


def _pick_features(df, feat_str):
    """Return list of numeric feature columns from comma-separated string or all numeric."""
    num_cols = [c for c in df.columns if df[c].dtype.kind in 'biufc']
    if feat_str:
        sel = [c.strip() for c in feat_str.split(',') if c.strip() in num_cols]
        return sel if sel else num_cols
    return num_cols


# ─── K-Means ──────────────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_kmeans',
    label='K-Means',
    category='ML / Unsupervised',
    icon='Target',
    description=(
        "K-Means clustering. Slide k to watch clusters form in real time. "
        "2 features → direct scatter + regions. N features → PCA 2D projection. "
        "Outputs inertia + silhouette score for elbow/quality analysis."
    ),
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'table',      'color': 'data',   'label': 'DataFrame + cluster'},
        {'id': 'preview',    'color': 'image',  'label': 'Clusters'},
        {'id': 'inertia',    'color': 'scalar', 'label': 'Inertia (WCSS)'},
        {'id': 'silhouette', 'color': 'scalar', 'label': 'Silhouette score'},
    ],
    params=[
        {'id': 'features',     'label': 'Features (blank = all numeric)', 'type': 'string', 'default': ''},
        {'id': 'k',            'label': 'k  (clusters)',   'type': 'int',  'default': 3, 'min': 2, 'max': 20},
        {'id': 'init',         'label': 'Init method',     'type': 'enum', 'options': ['k-means++', 'random'], 'default': 0},
        {'id': 'max_iter',     'label': 'Max iterations',  'type': 'int',  'default': 300, 'min': 10, 'max': 1000},
        {'id': 'random_state', 'label': 'Random seed',     'type': 'int',  'default': 42,  'min': 0,  'max': 9999},
        {'id': 'colormap',     'label': 'Colormap',        'type': 'enum', 'options': _CMAP_LABELS, 'default': 0},
        {'id': 'show_regions', 'label': 'Show regions',    'type': 'bool', 'default': True},
        {'id': 'boundary_res', 'label': 'Region resolution', 'type': 'int', 'default': 120, 'min': 40, 'max': 300},
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLKMeansNode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.decomposition import PCA

        _, plt = _get_mpl()

        feat_str     = str(params.get('features', '')).strip()
        k            = int(params.get('k', 3))
        init         = ['k-means++', 'random'][int(params.get('init', 0))]
        max_iter     = int(params.get('max_iter', 300))
        random_state = int(params.get('random_state', 42))
        cmap         = _CMAPS[int(params.get('colormap', 0))]
        show_regions = bool(params.get('show_regions', True))
        res          = int(params.get('boundary_res', 120))
        w_px         = int(params.get('width',  540))
        h_px         = int(params.get('height', 420))

        features = _pick_features(df, feat_str)
        if not features:
            send_notification("K-Means: no numeric features found", level='warning', notif_id=_NOTIF_ID)
            return {}

        X = df[features].dropna().values.astype(float)
        if len(X) < k:
            send_notification(f"K-Means: need ≥ k={k} samples (got {len(X)})", level='warning', notif_id=_NOTIF_ID)
            return {}

        km = KMeans(n_clusters=k, init=init, max_iter=max_iter,
                    random_state=random_state, n_init=10)
        labels  = km.fit_predict(X)
        inertia = float(km.inertia_)
        sil     = float(silhouette_score(X, labels)) if k > 1 and len(X) > k else 0.0

        # Attach cluster label to a copy of the (non-NaN) rows
        df_out = df[features].dropna().copy()
        df_out['cluster'] = labels

        # ── Visualisation ──────────────────────────────────────────────────
        use_pca = len(features) != 2
        if use_pca:
            pca2   = PCA(n_components=2, random_state=random_state)
            X_vis  = pca2.fit_transform(X)
            ax_labels = ('PC1', 'PC2')
            centers_vis = pca2.transform(km.cluster_centers_)
        else:
            X_vis       = X
            ax_labels   = tuple(features)
            centers_vis = km.cluster_centers_

        with plt.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(w_px / 100, h_px / 100))

            if show_regions:
                margin = (X_vis.max(axis=0) - X_vis.min(axis=0)) * 0.12 + 1e-6
                x0r = np.linspace(X_vis[:, 0].min() - margin[0], X_vis[:, 0].max() + margin[0], res)
                x1r = np.linspace(X_vis[:, 1].min() - margin[1], X_vis[:, 1].max() + margin[1], res)
                xx, yy = np.meshgrid(x0r, x1r)
                if use_pca:
                    grid_orig = pca2.inverse_transform(np.c_[xx.ravel(), yy.ravel()])
                    Z = km.predict(grid_orig).reshape(xx.shape)
                else:
                    Z = km.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
                ax.contourf(xx, yy, Z, alpha=0.20, cmap=cmap, levels=k)
                ax.contour(xx, yy, Z, colors='#555', linewidths=0.5)

            colors = plt.cm.get_cmap(cmap)(np.linspace(0, 1, k))
            for i, color in enumerate(colors):
                mask = labels == i
                ax.scatter(X_vis[mask, 0], X_vis[mask, 1], color=color,
                           s=28, alpha=0.8, edgecolors='none', label=f'Cluster {i}')

            ax.scatter(centers_vis[:, 0], centers_vis[:, 1],
                       c='white', s=180, marker='X', edgecolors='black',
                       linewidths=0.8, zorder=5, label='Centroids')

            ax.set_xlabel(ax_labels[0])
            ax.set_ylabel(ax_labels[1])
            suffix = '  (PCA projection)' if use_pca else ''
            ax.set_title(f"K-Means  k={k}  |  inertia={inertia:.1f}  sil={sil:.3f}{suffix}", fontsize=9)
            ax.legend(fontsize=7, labelcolor='#cccccc', loc='best',
                      markerscale=1.2, framealpha=0.4)
            ax.grid(True)
            fig.tight_layout()
            img = _fig_to_bgr(fig)
            plt.close(fig)

        return {
            'table':      df_out,
            'preview':    img,
            'inertia':    inertia,
            'silhouette': sil,
        }


# ─── PCA ──────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_pca',
    label='PCA',
    category='ML / Unsupervised',
    icon='Aperture',
    description=(
        "Principal Component Analysis. "
        "Reduces dimensionality, shows PC1 vs PC2 scatter and explained variance chart. "
        "Connect hue column to colour by class or cluster."
    ),
    inputs=[{'id': 'table', 'color': 'data', 'label': 'DataFrame'}],
    outputs=[
        {'id': 'transformed',   'color': 'data',   'label': 'Projected DataFrame'},
        {'id': 'scatter',       'color': 'image',  'label': 'PC1 vs PC2'},
        {'id': 'variance_plot', 'color': 'image',  'label': 'Explained variance'},
        {'id': 'pc1_variance',  'color': 'scalar', 'label': 'PC1 variance %'},
        {'id': 'pc2_variance',  'color': 'scalar', 'label': 'PC2 variance %'},
    ],
    params=[
        {'id': 'features',     'label': 'Features (blank = all numeric)',  'type': 'string', 'default': ''},
        {'id': 'n_components', 'label': 'Components to compute',           'type': 'int',    'default': 5, 'min': 2, 'max': 20},
        {'id': 'standardize',  'label': 'Standardize (StandardScaler)',    'type': 'bool',   'default': True},
        {'id': 'hue_col',      'label': 'Color by column',                 'type': 'string', 'default': ''},
        {'id': 'colormap',     'label': 'Colormap',                        'type': 'enum',   'options': _CMAP_LABELS, 'default': 0},
        {'id': 'alpha',        'label': 'Opacity',                         'type': 'float',  'default': 0.75, 'min': 0.1, 'max': 1.0, 'step': 0.05},
        {'id': 'dot_size',     'label': 'Dot size',                        'type': 'int',    'default': 30,   'min': 5,   'max': 200},
        {'id': 'show_loadings','label': 'Show loadings (biplot)',           'type': 'bool',   'default': False},
    ],
    resizable=True,
    min_width=320,
    min_height=260,
)
class MLPCANode(NodeProcessor):
    def process(self, inputs, params):
        df = inputs.get('table')
        if df is None:
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        _, plt = _get_mpl()

        feat_str      = str(params.get('features', '')).strip()
        n_components  = int(params.get('n_components', 5))
        standardize   = bool(params.get('standardize', True))
        hue_col       = str(params.get('hue_col', '')).strip()
        cmap          = _CMAPS[int(params.get('colormap', 0))]
        alpha         = float(params.get('alpha', 0.75))
        s             = int(params.get('dot_size', 30))
        show_loadings = bool(params.get('show_loadings', False))
        w_px          = int(params.get('width',  540))
        h_px          = int(params.get('height', 420))

        features = _pick_features(df, feat_str)
        if len(features) < 2:
            send_notification("PCA: need ≥ 2 numeric features", level='warning', notif_id=_NOTIF_ID)
            return {}

        sub = df[features].dropna()
        X   = sub.values.astype(float)
        n_comp = min(n_components, len(features), len(X))

        if standardize:
            scaler = StandardScaler()
            X = scaler.fit_transform(X)

        pca      = PCA(n_components=n_comp)
        X_pca    = pca.fit_transform(X)
        var_ratio = pca.explained_variance_ratio_

        # Rebuild as DataFrame
        pc_cols   = [f'PC{i+1}' for i in range(n_comp)]
        df_pca    = sub.reset_index(drop=True).copy()
        for i, col in enumerate(pc_cols):
            df_pca[col] = X_pca[:, i]

        pc1_var = float(var_ratio[0]) * 100
        pc2_var = float(var_ratio[1]) * 100 if n_comp >= 2 else 0.0

        # ── Scatter PC1 vs PC2 ───────────────────────────────────────────
        with plt.rc_context(_MPL_DARK):
            fig_s, ax_s = plt.subplots(figsize=(w_px / 100, h_px / 100))

            if hue_col and hue_col in df.columns:
                hue_vals = df[hue_col].iloc[sub.index].reset_index(drop=True)
                classes  = hue_vals.unique()[:20]
                colors   = plt.cm.get_cmap(cmap)(np.linspace(0, 1, len(classes)))
                for cls, color in zip(classes, colors):
                    mask = hue_vals == cls
                    ax_s.scatter(X_pca[mask, 0], X_pca[mask, 1],
                                 color=color, alpha=alpha, s=s,
                                 edgecolors='none', label=str(cls))
                ax_s.legend(fontsize=8, labelcolor='#cccccc', title=hue_col,
                            title_fontsize=8, loc='best', framealpha=0.4)
            else:
                ax_s.scatter(X_pca[:, 0], X_pca[:, 1], alpha=alpha, s=s,
                             c=np.arange(len(X_pca)), cmap=cmap, edgecolors='none')

            if show_loadings and n_comp >= 2:
                scale = np.abs(X_pca).max() * 0.8
                for i, feat in enumerate(features[:8]):  # max 8 arrows for readability
                    ax_s.annotate('', xy=(pca.components_[0, i] * scale,
                                          pca.components_[1, i] * scale),
                                  xytext=(0, 0),
                                  arrowprops=dict(arrowstyle='->', color='#f97316', lw=1.2))
                    ax_s.text(pca.components_[0, i] * scale * 1.08,
                              pca.components_[1, i] * scale * 1.08,
                              feat, fontsize=7, color='#f97316', ha='center')

            ax_s.axhline(0, color='#444', lw=0.5)
            ax_s.axvline(0, color='#444', lw=0.5)
            ax_s.set_xlabel(f'PC1  ({pc1_var:.1f}% var)')
            ax_s.set_ylabel(f'PC2  ({pc2_var:.1f}% var)')
            ax_s.set_title(f'PCA — {n_comp} components  |  {pc1_var+pc2_var:.1f}% var (PC1+PC2)', fontsize=9)
            ax_s.grid(True)
            fig_s.tight_layout()
            scatter_img = _fig_to_bgr(fig_s)
            plt.close(fig_s)

            # ── Explained variance bar chart ──────────────────────────────
            fig_v, ax_v = plt.subplots(figsize=(max(4.0, n_comp * 0.7), 3.2))
            xs       = np.arange(1, n_comp + 1)
            colors_v = plt.cm.get_cmap('viridis')(np.linspace(0.3, 0.9, n_comp))
            ax_v.bar(xs, var_ratio * 100, color=colors_v, alpha=0.85, edgecolor='none')
            cumulative = np.cumsum(var_ratio) * 100
            ax_v.plot(xs, cumulative, 'o--', color='#f97316', lw=1.5, ms=4, label='Cumulative')
            ax_v.axhline(80, color='#555', lw=0.8, linestyle=':')
            ax_v.axhline(95, color='#888', lw=0.8, linestyle=':')
            ax_v.set_xlabel('Principal Component')
            ax_v.set_ylabel('Explained variance (%)')
            ax_v.set_title('Explained Variance by Component', fontsize=9)
            ax_v.set_xticks(xs)
            ax_v.set_xticklabels([f'PC{i}' for i in xs], fontsize=8)
            ax_v.legend(fontsize=8, labelcolor='#cccccc', framealpha=0.4)
            ax_v.set_ylim(0, 105)
            ax_v.grid(True, axis='y')
            fig_v.tight_layout()
            var_img = _fig_to_bgr(fig_v)
            plt.close(fig_v)

        return {
            'transformed':   df_pca,
            'scatter':        scatter_img,
            'variance_plot':  var_img,
            'pc1_variance':   pc1_var,
            'pc2_variance':   pc2_var,
        }
