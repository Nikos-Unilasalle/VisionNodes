"""
ml_training_monitor.py — Visualise les courbes train/val loss depuis un dict loss_history.
"""
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor

_MPL_DARK = {
    'figure.facecolor': '#161616',
    'axes.facecolor':   '#1e1e1e',
    'axes.edgecolor':   '#555555',
    'axes.labelcolor':  '#cccccc',
    'text.color':       '#cccccc',
    'xtick.color':      '#aaaaaa',
    'ytick.color':      '#aaaaaa',
    'grid.color':       '#333333',
    'grid.linestyle':   '--',
    'grid.linewidth':   0.5,
}


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
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img if img is not None else np.zeros((200, 420, 3), dtype=np.uint8)


def _smooth(arr: np.ndarray, window: int) -> np.ndarray:
    """Moving average smoothing via convolution."""
    if window <= 1 or len(arr) < window:
        return arr
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode='valid')


@vision_node(
    type_id='ml_training_monitor',
    label='Training Monitor',
    category='Machine Learning',
    icon='TrendingDown',
    description="Visualise les courbes de loss train/val. Affiche la meilleure epoch et les valeurs finales.",
    inputs=[
        {'id': 'loss_history', 'color': 'dict', 'label': 'Loss History'},
    ],
    outputs=[
        {'id': 'preview',           'color': 'image',  'label': 'Preview'},
        {'id': 'best_epoch',        'color': 'scalar', 'label': 'Best Epoch'},
        {'id': 'final_train_loss',  'color': 'scalar', 'label': 'Final Train Loss'},
        {'id': 'final_val_loss',    'color': 'scalar', 'label': 'Final Val Loss'},
    ],
    params=[
        {'id': 'log_scale',  'label': 'Échelle log Y',           'type': 'bool', 'default': False},
        {'id': 'show_best',  'label': 'Marquer meilleure epoch', 'type': 'bool', 'default': True},
        {'id': 'smooth',     'label': 'Lissage (fenêtre)',        'type': 'int',  'default': 1, 'min': 1, 'max': 20},
    ],
    resizable=True, min_width=300, min_height=200,
)
class MLTrainingMonitorNode(NodeProcessor):

    def process(self, inputs, params):
        history = inputs.get('loss_history')
        if not isinstance(history, dict):
            blank = np.zeros((200, 420, 3), dtype=np.uint8)
            cv2.putText(blank, 'En attente de loss_history...', (20, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)
            return {
                'preview': blank,
                'best_epoch': 0.0,
                'final_train_loss': 0.0,
                'final_val_loss': 0.0,
            }

        train_loss = np.asarray(history.get('train_loss', []), dtype=float)
        val_loss   = np.asarray(history.get('val_loss',   []), dtype=float)

        log_scale = bool(params.get('log_scale', False))
        show_best = bool(params.get('show_best', True))
        smooth_w  = max(1, int(params.get('smooth', 1)))

        # Scalaire outputs
        final_train = float(train_loss[-1]) if len(train_loss) > 0 else 0.0
        final_val   = float(val_loss[-1])   if len(val_loss)   > 0 else 0.0

        if len(val_loss) > 0:
            best_epoch = int(np.argmin(val_loss))
        elif len(train_loss) > 0:
            best_epoch = int(np.argmin(train_loss))
        else:
            best_epoch = 0

        # ── Matplotlib ──────────────────────────────────────────────────────────
        matplotlib, plt = _get_mpl()

        with matplotlib.rc_context(_MPL_DARK):
            fig, ax = plt.subplots(figsize=(7, 3.5))

            n_epochs = max(len(train_loss), len(val_loss))

            if len(train_loss) > 0:
                t_smooth = _smooth(train_loss, smooth_w)
                x_t = np.linspace(0, len(train_loss) - 1, len(t_smooth))
                ax.plot(x_t, t_smooth, color='#4a9eff', linewidth=1.8, label='Train loss', zorder=3)

            if len(val_loss) > 0:
                v_smooth = _smooth(val_loss, smooth_w)
                x_v = np.linspace(0, len(val_loss) - 1, len(v_smooth))
                ax.plot(x_v, v_smooth, color='#ff9f4a', linewidth=1.8, label='Val loss', zorder=3)

            if show_best and n_epochs > 0:
                ax.axvline(x=best_epoch, color='#44cc88', linewidth=1.5, linestyle='--',
                           label=f'Best epoch {best_epoch}', zorder=2)

            if log_scale:
                ax.set_yscale('log')

            ax.set_xlabel('Epoch')
            ax.set_ylabel('Loss')
            ax.grid(True, alpha=0.4)
            ax.legend(fontsize=8, loc='upper right')

            # Titre
            if len(val_loss) > 0:
                title = (f'Training Monitor | Epoch {best_epoch} | '
                         f'Train: {final_train:.4f} | Val: {final_val:.4f}')
            elif len(train_loss) > 0:
                title = f'Training Monitor | Epoch {best_epoch} | Train: {final_train:.4f}'
            else:
                title = 'Training Monitor | Aucune donnée'
            fig.suptitle(title, fontsize=8, color='#cccccc')

            plt.tight_layout()
            img = _fig_to_bgr(fig)
            plt.close(fig)

        return {
            'preview':          img,
            'best_epoch':       float(best_epoch),
            'final_train_loss': final_train,
            'final_val_loss':   final_val,
        }
