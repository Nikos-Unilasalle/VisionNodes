import numpy as np
import cv2
import io
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'viz_grid_compare'

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
    type_id='viz_grid_compare',
    label='Grid Compare Dashboard',
    category='Machine Learning',
    icon='Eye',
    description=(
        "Compare visuellement deux grilles spatiales (Réel vs Reconstruit). "
        "Affiche les cartes côte à côte ainsi que la carte de différence d'erreur absolue."
    ),
    inputs=[
        {'id': 'original',      'color': 'any',    'label': 'Original'},
        {'id': 'reconstructed', 'color': 'any',    'label': 'Reconstructed'},
    ],
    outputs=[
        {'id': 'preview',       'color': 'image',  'label': 'Preview'},
        {'id': 'frame_mse',     'color': 'scalar', 'label': 'MSE frame'},
        {'id': 'frame_psnr',    'color': 'scalar', 'label': 'PSNR frame'},
    ],
    params=[
        {'id': 'frame_idx',     'label': 'Index Frame / Temps',     'type': 'int',    'default': 0, 'min': 0, 'max': 50000},
        {'id': 'colormap',      'label': 'Palette Couleur',          'type': 'enum',   'options': ['Viridis', 'Plasma', 'Jet', 'Inferno'], 'default': 0},
    ]
)
class GridCompareDashboardNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key = None
        self._cache_result = None

    def process(self, inputs, params):
        orig = inputs.get('original')
        recon = inputs.get('reconstructed')

        if orig is None or recon is None:
            return {}

        if not isinstance(orig, np.ndarray) or not isinstance(recon, np.ndarray):
            send_notification("Grid Compare: Les entrées doivent être des tableaux NumPy", level='error', notif_id=_NOTIF_ID)
            return {}

        if orig.shape != recon.shape:
            send_notification(f"Grid Compare: Dimensions différentes (orig: {orig.shape}, recon: {recon.shape})", level='error', notif_id=_NOTIF_ID)
            return {}

        T, H, W = orig.shape
        frame_idx = int(params.get('frame_idx', 0))
        frame_idx = max(0, min(frame_idx, T - 1))
        colormap_idx = int(params.get('colormap', 0))

        cache_key = (id(orig), id(recon), frame_idx, colormap_idx)
        if cache_key == self._cache_key and self._cache_result is not None:
            return self._cache_result

        # Extract frames
        f_orig = orig[frame_idx]
        f_recon = recon[frame_idx]

        # Calculate metrics for this frame
        diff = f_orig - f_recon
        valid_mask = ~np.isnan(diff)
        n_valid = np.sum(valid_mask)

        if n_valid == 0:
            frame_mse = 0.0
            frame_psnr = 0.0
            diff_vis = np.zeros((H, W), dtype=np.uint8)
        else:
            valid_diff = diff[valid_mask]
            frame_mse = float(np.mean(valid_diff ** 2))
            
            # PSNR calculation
            max_val = float(np.nanmax(f_orig) - np.nanmin(f_orig))
            if max_val == 0:
                max_val = 1.0
            frame_psnr = 10 * np.log10((max_val ** 2) / (frame_mse + 1e-10))

            # Abs diff map
            abs_diff = np.abs(diff)
            # Stretch absolute error for visualization
            valid_abs = abs_diff[valid_mask]
            amax = valid_abs.max()
            if amax == 0:
                diff_vis = np.zeros_like(abs_diff, dtype=np.uint8)
            else:
                diff_vis = np.clip(abs_diff / amax * 255, 0, 255)
                diff_vis[~valid_mask] = 0
                diff_vis = diff_vis.astype(np.uint8)

        # Colorspace helper for original and reconstructed
        def make_color(grid):
            valid = grid[~np.isnan(grid)]
            if valid.size == 0:
                return np.zeros((H, W, 3), dtype=np.uint8)
            p2, p98 = np.percentile(valid, (2, 98))
            if p98 == p2:
                stretched = np.zeros_like(grid, dtype=np.uint8)
            else:
                stretched = np.clip((grid - p2) / (p98 - p2) * 255, 0, 255)
            
            nan_mask = np.isnan(grid)
            if stretched.dtype != np.uint8:
                stretched[nan_mask] = 0
                stretched = stretched.astype(np.uint8)

            cmaps = [
                cv2.COLORMAP_VIRIDIS,
                cv2.COLORMAP_PLASMA,
                cv2.COLORMAP_JET,
                cv2.COLORMAP_INFERNO
            ]
            cmap = cmaps[min(colormap_idx, len(cmaps) - 1)]
            color_img = cv2.applyColorMap(stretched, cmap)
            color_img[nan_mask] = [40, 40, 40]  # land mask
            return cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

        orig_rgb = make_color(f_orig)
        recon_rgb = make_color(f_recon)

        # Apply colormap to absolute error (Hot or Inferno works best for error)
        diff_colored = cv2.applyColorMap(diff_vis, cv2.COLORMAP_HOT)
        diff_colored[~valid_mask] = [40, 40, 40]
        diff_rgb = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)

        _, plt = _get_mpl()
        fig = None
        try:
            with plt.rc_context(_MPL_DARK):
                fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 3.5))

                ax1.imshow(orig_rgb)
                ax1.set_title('Original Grid', fontsize=9)
                ax1.axis('off')

                ax2.imshow(recon_rgb)
                ax2.set_title('Reconstructed Grid', fontsize=9)
                ax2.axis('off')

                ax3.imshow(diff_rgb)
                ax3.set_title('Absolute Error Map', fontsize=9)
                ax3.axis('off')

                fig.suptitle(
                    f"Comparaison Frame {frame_idx}/{T-1}  |  "
                    f"MSE: {frame_mse:.5f}  |  PSNR: {frame_psnr:.2f} dB",
                    fontsize=10
                )
                fig.tight_layout()
                preview_img = _fig_to_bgr(fig, dpi=100)
        finally:
            if fig is not None:
                plt.close(fig)

        result = {
            'preview': preview_img,
            'frame_mse': frame_mse,
            'frame_psnr': frame_psnr,
        }
        self._cache_key = cache_key
        self._cache_result = result
        return result
