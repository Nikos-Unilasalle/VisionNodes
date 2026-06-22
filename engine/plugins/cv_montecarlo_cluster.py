"""
cv_montecarlo_cluster.py — Monte-Carlo clustering probability heatmap.

Draws many random sub-samples of pixels *inside an optional ROI mask*, fits a
small KMeans on each draw, applies it to the whole frame and votes. The result
is a 0..1 probability map for one anchored target cluster. Restricting the draws
to a balanced ROI makes the vote expert on ambiguous transition zones instead of
being dominated by the majority background.

Fully generic: any multi-channel feature image (RGB, spectral indices, filter
banks, embeddings…) + any ROI mask. The target cluster is anchored by a
reference channel and a high/low rule, so the probability is reproducible and
never depends on KMeans' arbitrary label order.
"""

import cv2
import numpy as np

try:
    from sklearn.cluster import KMeans
    _SKLEARN_OK = True
except Exception:
    _SKLEARN_OK = False

from registry import vision_node, NodeProcessor


@vision_node(
    type_id='cv_montecarlo_cluster',
    label='Monte-Carlo Cluster',
    category='segmentation',
    icon='Dices',
    description=(
        "Probabilistic clustering by Monte-Carlo voting. Draws N random sub-samples "
        "of pixels INSIDE the ROI mask (whole frame if none), fits a small KMeans on "
        "each draw, applies it to the whole frame and votes for one anchored target "
        "cluster. Outputs a 0..1 probability heatmap, expert on ambiguous zones. "
        "Generic: any feature image (RGB, spectral indices, filter banks) + any ROI. "
        "Target cluster anchored by reference channel + high/low rule."
    ),
    resizable=True, min_width=240, min_height=200, colorable=True,
    inputs=[
        {'id': 'image', 'label': 'Features', 'color': 'image'},
        {'id': 'roi',   'label': 'ROI Mask', 'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',        'label': 'Heatmap',       'color': 'image'},
        {'id': 'probability', 'label': 'Probability',   'color': 'mask'},
        {'id': 'prob_raw',    'label': 'Prob 0..1',     'color': 'any'},
        {'id': 'stats',       'label': 'Stats',         'color': 'dict'},
    ],
    params=[
        {'id': '_sec_sampling',   'label': 'Sampling',   'type': 'section'},
        {'id': 'n_iterations', 'label': 'Iterations',      'type': 'int',  'default': 40,  'min': 5,  'max': 300},
        {'id': 'subsample',    'label': 'Subsample (%)',   'type': 'float','default': 30.0,'min': 1.0,'max': 100.0, 'step': 1.0},
        {'id': '_sec_clustering', 'label': 'Clustering', 'type': 'section'},
        {'id': 'n_clusters',   'label': 'Clusters (K)',    'type': 'int',  'default': 2,   'min': 2,  'max': 12},
        {'id': 'ref_channel',  'label': 'Anchor Channel',  'type': 'int',  'default': 0,   'min': 0,  'max': 31},
        {'id': 'anchor_rule',  'label': 'Target Cluster',  'type': 'enum', 'options': ['Highest on channel', 'Lowest on channel'], 'default': 0},
        {'id': '_sec_display',    'label': 'Display',    'type': 'section'},
        {'id': 'colormap',     'label': 'Colormap',        'type': 'enum', 'options': ['Inferno', 'Viridis', 'Jet', 'Ocean'], 'default': 0},
        {'id': 'seed',         'label': 'Random Seed',     'type': 'int',  'default': 0,   'min': 0,  'max': 9999},
    ]
)
class MonteCarloClusterNode(NodeProcessor):
    _CMAPS = [cv2.COLORMAP_INFERNO, cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_JET, cv2.COLORMAP_OCEAN]

    def process(self, inputs, params):
        img = inputs.get('image')
        roi = inputs.get('roi')
        if img is None:
            return {'main': None, 'probability': None, 'prob_raw': None, 'stats': {}}
        if not _SKLEARN_OK:
            if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn']):
                return {'main': img, 'probability': None, 'prob_raw': None, 'stats': {'error': 'scikit-learn missing'}}

        # --- feature matrix (H*W, C) ---
        if img.ndim == 2:
            feat = img[:, :, None]
        else:
            feat = img
        h, w = feat.shape[:2]
        c = feat.shape[2]
        X = feat.reshape(-1, c).astype(np.float32)
        # normalise each channel to 0..1 so no band dominates the distance
        mn = X.min(axis=0, keepdims=True)
        rng = np.ptp(X, axis=0, keepdims=True)
        rng[rng == 0] = 1.0
        Xn = (X - mn) / rng

        # --- ROI pixel pool ---
        if roi is not None:
            cmask = roi
            if cmask.ndim == 3:
                cmask = cv2.cvtColor(cmask, cv2.COLOR_BGR2GRAY)
            if cmask.shape[:2] != (h, w):
                cmask = cv2.resize(cmask, (w, h), interpolation=cv2.INTER_NEAREST)
            pool = np.flatnonzero(cmask > 0)
        else:
            pool = np.arange(h * w)
        if pool.size < 4:
            return {'main': img, 'probability': None, 'prob_raw': None, 'stats': {'error': 'ROI empty'}}

        n_iter    = int(params.get('n_iterations', 40))
        frac      = float(params.get('subsample', 30.0)) / 100.0
        k         = max(2, int(params.get('n_clusters', 2)))
        ref_ch    = min(int(params.get('ref_channel', 0)), c - 1)
        anchor_hi = int(params.get('anchor_rule', 0)) == 0
        rng_state = np.random.default_rng(int(params.get('seed', 0)))

        sample_n = max(k, int(pool.size * frac))
        votes = np.zeros(h * w, dtype=np.float32)

        for _ in range(n_iter):
            idx = rng_state.choice(pool, size=min(sample_n, pool.size), replace=False)
            km = KMeans(n_clusters=k, n_init=2, max_iter=50,
                        random_state=int(rng_state.integers(0, 1_000_000)))
            km.fit(Xn[idx])
            # anchor target = cluster whose centroid is highest/lowest on ref channel
            cen = km.cluster_centers_[:, ref_ch]
            target_lbl = int(np.argmax(cen)) if anchor_hi else int(np.argmin(cen))
            pred = km.predict(Xn)
            votes += (pred == target_lbl).astype(np.float32)

        prob = (votes / n_iter).reshape(h, w)              # 0..1
        prob_u8 = np.clip(prob * 255.0, 0, 255).astype(np.uint8)
        heat = cv2.applyColorMap(prob_u8, self._CMAPS[int(params.get('colormap', 0))])

        stats = {
            'iterations': n_iter,
            'clusters': k,
            'roi_px': int(pool.size),
            'sample_px': int(sample_n),
            'mean_prob': float(prob.mean()),
            'target_frac@0.5': float((prob >= 0.5).mean()),
        }
        return {'main': heat, 'probability': prob_u8, 'prob_raw': prob.astype(np.float32), 'stats': stats}
