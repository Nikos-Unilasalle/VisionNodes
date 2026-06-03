import numpy as np
import cv2
import io
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'grid_pca'

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

@vision_node(
    type_id='ml_grid_pca',
    label='Spatial PCA (EOF)',
    category='Machine Learning',
    icon='Activity',
    description=(
        "Applique une ACP spatiale (EOF) sur un tenseur de grilles 3D. "
        "Reconstruit les grilles et extrait les modes spatiaux principaux."
    ),
    inputs=[
        {'id': 'grids',       'color': 'any',    'label': 'Grids (T x H x W)'},
        {'id': 'meta',        'color': 'dict',   'label': 'Meta (optional)'},
    ],
    outputs=[
        {'id': 'reconstructed', 'color': 'any',    'label': 'Reconstructed'},
        {'id': 'modes',         'color': 'any',    'label': 'Modes (EOF)'},
        {'id': 'preview',       'color': 'image',  'label': 'Aperçu & Variance'},
        {'id': 'mse',           'color': 'scalar', 'label': 'MSE global'},
    ],
    params=[
        {'id': 'n_components',  'label': 'Composantes principales (k)',  'type': 'int',    'default': 10, 'min': 1, 'max': 100},
        {'id': 'standardize',   'label': 'Centrer et Réduire',           'type': 'bool',   'default': True},
        {'id': 'detrend',       'label': 'Dé-tendance temporelle',      'type': 'enum',   'options': ['None', 'Constant (mean)', 'Linear'], 'default': 1},
        {'id': 'cos_lat',       'label': 'Pondération Latitude (cos lat)','type': 'bool',   'default': False},
        {'id': 'solver',        'label': 'Solveur PCA',                 'type': 'enum',   'options': ['auto', 'full', 'arpack', 'randomized'], 'default': 0},
        {'id': 'colormap',      'label': 'Palette Couleur (Modes)',      'type': 'enum',   'options': ['Viridis', 'Plasma', 'Jet', 'Inferno'], 'default': 3},
    ]
)
class SpatialGridPCANode(NodeProcessor):
    def process(self, inputs, params):
        grids = inputs.get('grids')
        meta = inputs.get('meta')
        if grids is None:
            return {}

        if not isinstance(grids, np.ndarray) or len(grids.shape) != 3:
            send_notification("Spatial PCA: L'entrée doit être un tableau NumPy 3D (T, H, W)", level='error', notif_id=_NOTIF_ID)
            return {}

        if not self.ensure_packages(['sklearn'], pip_names=['scikit-learn'], notif_id=_NOTIF_ID):
            return {}

        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        n_components = int(params.get('n_components', 10))
        standardize = bool(params.get('standardize', True))
        detrend_idx = int(params.get('detrend', 1))
        cos_lat_weighting = bool(params.get('cos_lat', False))
        solver_idx = int(params.get('solver', 0))
        colormap_idx = int(params.get('colormap', 3))

        detrend_opts = ['None', 'Constant (mean)', 'Linear']
        detrend_val = detrend_opts[min(detrend_idx, len(detrend_opts) - 1)]

        solver_opts = ['auto', 'full', 'arpack', 'randomized']
        solver_val = solver_opts[min(solver_idx, len(solver_opts) - 1)]

        T, H, W = grids.shape
        n_components = min(n_components, T, H * W)

        # 1. Flatten spatial grid dimensions
        X_flat = grids.reshape(T, H * W)

        # 2. Extract land/ocean mask: find pixels that are never NaN across all time steps
        valid_pixel_mask = ~np.isnan(X_flat).any(axis=0)
        n_valid = np.sum(valid_pixel_mask)

        if n_valid == 0:
            send_notification("Spatial PCA: Aucun pixel valide (non-NaN) trouvé", level='error', notif_id=_NOTIF_ID)
            return {}

        X_valid = X_flat[:, valid_pixel_mask].copy()

        # 3. Apply latitude cosine weighting if enabled
        lat_min = None
        lat_max = None
        if meta and isinstance(meta, dict):
            lat_min = meta.get('lat_min')
            lat_max = meta.get('lat_max')

        if cos_lat_weighting and lat_min is not None and lat_max is not None:
            # Reconstruct the latitude vector for height H
            lat_vector = np.linspace(lat_min, lat_max, H)
            weights = np.sqrt(np.cos(np.radians(lat_vector)))
            weights_2d = np.tile(weights[:, np.newaxis], (1, W))
            weights_flat = weights_2d.flatten()[valid_pixel_mask]
            # Avoid division by zero
            weights_flat = np.maximum(weights_flat, 1e-5)
        else:
            weights_flat = np.ones(n_valid)

        # 4. Detrending
        trends = None
        means = np.mean(X_valid, axis=0)

        if detrend_val == 'Constant (mean)':
            X_detrend = X_valid - means
        elif detrend_val == 'Linear':
            t_axis = np.arange(T)
            A = np.vstack([t_axis, np.ones(T)]).T
            coefs, _, _, _ = np.linalg.lstsq(A, X_valid, rcond=None)
            trends = A @ coefs
            X_detrend = X_valid - trends
        else:
            X_detrend = X_valid.copy()

        # 5. Standardize
        scaler = None
        if standardize:
            scaler = StandardScaler()
            X_proc = scaler.fit_transform(X_detrend)
        else:
            X_proc = X_detrend.copy()

        # Apply weights to standardized data before PCA
        X_weighted = X_proc * weights_flat

        # 6. Fit PCA
        pca = PCA(n_components=n_components, svd_solver=solver_val, random_state=42)
        X_proj = pca.fit_transform(X_weighted)

        # 7. Reconstruct
        X_recon_weighted = pca.inverse_transform(X_proj)
        
        # Remove weights
        X_recon_proc = X_recon_weighted / weights_flat

        if standardize and scaler is not None:
            X_recon_detrend = scaler.inverse_transform(X_recon_proc)
        else:
            X_recon_detrend = X_recon_proc

        if detrend_val == 'Constant (mean)':
            X_recon_valid = X_recon_detrend + means
        elif detrend_val == 'Linear' and trends is not None:
            X_recon_valid = X_recon_detrend + trends
        else:
            X_recon_valid = X_recon_detrend

        # Rebuild full 2D grids (maintaining land NaNs)
        grids_recon = np.full((T, H * W), np.nan)
        grids_recon[:, valid_pixel_mask] = X_recon_valid
        grids_recon = grids_recon.reshape(T, H, W)

        # Calculate global MSE
        mse = float(np.nanmean((grids - grids_recon) ** 2))

        # Reconstruct spatial modes (EOF)
        components = pca.components_  # Shape: (n_components, n_valid)
        modes = np.full((n_components, H * W), np.nan)
        modes[:, valid_pixel_mask] = components
        modes = modes.reshape(n_components, H, W)

        # 8. Visualisation (Explained Variance + PC1 spatial mode)
        var_ratio = pca.explained_variance_ratio_
        _, plt = _get_mpl()

        with plt.rc_context(_MPL_DARK):
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.5))

            # Left plot: explained variance
            xs = np.arange(1, len(var_ratio) + 1)
            ax1.bar(xs, var_ratio * 100, color='#3b82f6', alpha=0.8)
            ax1.plot(xs, np.cumsum(var_ratio) * 100, 'o--', color='#f97316', ms=4, label='Cumul')
            ax1.set_xlabel('Principal Component')
            ax1.set_ylabel('Variance expliquée (%)')
            ax1.set_title('Variance Expliquée', fontsize=9)
            ax1.grid(True)
            ax1.legend(fontsize=7, labelcolor='#cccccc')

            # Right plot: EOF Mode 1 map
            mode1 = modes[0]
            valid_m1 = mode1[~np.isnan(mode1)]
            if valid_m1.size > 0:
                p2, p98 = np.percentile(valid_m1, (2, 98))
                if p98 == p2:
                    mode1_vis = np.zeros_like(mode1, dtype=np.uint8)
                else:
                    mode1_vis = np.clip((mode1 - p2) / (p98 - p2) * 255, 0, 255)
            else:
                mode1_vis = np.zeros((H, W), dtype=np.uint8)

            nan_mask = np.isnan(mode1)
            if mode1_vis.dtype != np.uint8:
                mode1_vis[nan_mask] = 0
                mode1_vis = mode1_vis.astype(np.uint8)

            cmaps = [
                cv2.COLORMAP_VIRIDIS,
                cv2.COLORMAP_PLASMA,
                cv2.COLORMAP_JET,
                cv2.COLORMAP_INFERNO
            ]
            cmap = cmaps[min(colormap_idx, len(cmaps) - 1)]
            mode1_colored = cv2.applyColorMap(mode1_vis, cmap)
            mode1_colored[nan_mask] = [40, 40, 40]

            mode1_rgb = cv2.cvtColor(mode1_colored, cv2.COLOR_BGR2RGB)
            ax2.imshow(mode1_rgb)
            ax2.set_title('Mode spatial 1 (EOF1)', fontsize=9)
            ax2.axis('off')

            fig.suptitle(f"Spatial PCA (k={n_components})  |  MSE Reconstruction: {mse:.4f}", fontsize=10)
            fig.tight_layout()
            preview_img = _fig_to_bgr(fig, dpi=100)
            plt.close(fig)

        return {
            'reconstructed': grids_recon,
            'modes': modes,
            'preview': preview_img,
            'mse': mse,
        }
