"""
ml_unet_grid.py — U-Net convolutif pour la reconstruction de grilles géospatiales 3D (T×H×W).

Architecture encodeur-décodeur avec skip connections. Gère les NaN (masque océan).
Entraîné avec PyTorch Lightning dans un thread séparé.
"""
import io
import threading
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_unet_grid'

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

_COLORMAPS = ['viridis', 'plasma', 'jet', 'inferno']


def _draw_progress_bar(img: np.ndarray, epoch: int, total: int,
                       train_loss: float | None, val_loss: float | None) -> np.ndarray:
    """Overlay une barre de progression OpenCV sur img (in-place, retourne img)."""
    h, w = img.shape[:2]
    bar_h   = 28
    margin  = 12
    bar_y   = h - bar_h - margin
    bar_x0  = margin
    bar_x1  = w - margin
    bar_w   = bar_x1 - bar_x0

    # Fond semi-transparent
    overlay = img.copy()
    cv2.rectangle(overlay, (0, bar_y - 18), (w, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    # Barre fond
    cv2.rectangle(img, (bar_x0, bar_y), (bar_x1, bar_y + bar_h), (55, 55, 55), -1)
    cv2.rectangle(img, (bar_x0, bar_y), (bar_x1, bar_y + bar_h), (90, 90, 90), 1)

    # Remplissage
    progress = epoch / max(total, 1)
    fill_w   = int(bar_w * progress)
    if fill_w > 0:
        # Dégradé bleu → cyan
        for i in range(fill_w):
            t = i / max(fill_w - 1, 1)
            b = int(200 + 55 * t)
            g = int(100 + 100 * t)
            r = int(40 + 20 * t)
            cv2.line(img, (bar_x0 + i, bar_y + 1), (bar_x0 + i, bar_y + bar_h - 2), (r, g, b), 1)

    # Texte epoch
    pct_str = f'{int(progress * 100)}%'
    cv2.putText(img, pct_str, (bar_x0 + fill_w // 2 - 14, bar_y + bar_h - 7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1, cv2.LINE_AA)

    # Texte métriques (au-dessus de la barre)
    parts = [f'Epoch {epoch}/{total}']
    if train_loss is not None and not (train_loss != train_loss):  # not NaN
        parts.append(f'train={train_loss:.5f}')
    if val_loss is not None and not (val_loss != val_loss):
        parts.append(f'val={val_loss:.5f}')
    cv2.putText(img, '  '.join(parts), (bar_x0, bar_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 210, 255), 1, cv2.LINE_AA)

    return img


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
    return img if img is not None else np.zeros((200, 640, 3), dtype=np.uint8)


# ─── Architecture U-Net ───────────────────────────────────────────────────────

def _build_unet_classes():
    """Importe torch et retourne les classes U-Net (évite import toplevel)."""
    import torch
    import torch.nn as nn

    class _UNetConvBlock(nn.Module):
        """Double convolution : Conv2d → BN → ReLU × 2"""
        def __init__(self, in_ch, out_ch):
            super().__init__()
            self.block = nn.Sequential(
                nn.Conv2d(in_ch,  out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.block(x)

    class _UNetModel(nn.Module):
        """U-Net 1→1 canal avec skip connections.

        Pour n_levels=3, base_channels=16 :
          Encoder : 1→16, 16→32, 32→64 (MaxPool2d entre chaque)
          Bottleneck : 64→128
          Decoder : 128 up→64+64=128→64, 64 up→32+32=64→32, 32 up→16+16=32→16
          Final : 16→1 (Conv2d 1×1)
        """
        def __init__(self, base_channels=16, n_levels=3):
            super().__init__()
            self.n_levels = n_levels
            bc = base_channels

            # Encodeur
            self.encoders = nn.ModuleList()
            self.pools    = nn.ModuleList()
            in_ch = 1
            for i in range(n_levels):
                out_ch = bc * (2 ** i)
                self.encoders.append(_UNetConvBlock(in_ch, out_ch))
                self.pools.append(nn.MaxPool2d(2))
                in_ch = out_ch

            # Bottleneck
            btn_ch = bc * (2 ** n_levels)
            self.bottleneck = _UNetConvBlock(in_ch, btn_ch)

            # Décodeur
            self.upconvs  = nn.ModuleList()
            self.decoders = nn.ModuleList()
            in_ch = btn_ch
            for i in range(n_levels - 1, -1, -1):
                skip_ch = bc * (2 ** i)
                self.upconvs.append(nn.ConvTranspose2d(in_ch, skip_ch, 2, stride=2))
                self.decoders.append(_UNetConvBlock(skip_ch * 2, skip_ch))
                in_ch = skip_ch

            # Sortie
            self.final_conv = nn.Conv2d(in_ch, 1, 1)

        def forward(self, x):
            skips = []
            cur   = x
            for enc, pool in zip(self.encoders, self.pools):
                cur = enc(cur)
                skips.append(cur)
                cur = pool(cur)

            cur = self.bottleneck(cur)

            for up, dec, skip in zip(self.upconvs, self.decoders, reversed(skips)):
                cur = up(cur)
                # Ajuster dimensions si besoin
                if cur.shape != skip.shape:
                    dh = skip.shape[2] - cur.shape[2]
                    dw = skip.shape[3] - cur.shape[3]
                    cur = torch.nn.functional.pad(cur, [0, dw, 0, dh])
                cur = torch.cat([cur, skip], dim=1)
                cur = dec(cur)

            return self.final_conv(cur)

    return _UNetConvBlock, _UNetModel


def _build_lightning_module(_UNetModel):
    """Crée la classe LightningModule après import pl."""
    try:
        import pytorch_lightning as pl
    except ImportError:
        import lightning.pytorch as pl
    import torch
    import torch.nn as nn

    class _UNetLightningModule(pl.LightningModule):
        def __init__(self, model, lr=1e-3):
            super().__init__()
            self.model = model
            self.lr    = lr

        def forward(self, x):
            return self.model(x)

        def training_step(self, batch, batch_idx):
            x, y = batch
            loss = torch.nn.functional.mse_loss(self(x), y)
            self.log('train_loss', loss, on_epoch=True, on_step=False)
            return loss

        def validation_step(self, batch, batch_idx):
            x, y = batch
            loss = torch.nn.functional.mse_loss(self(x), y)
            self.log('val_loss', loss, on_epoch=True, on_step=False)

        def configure_optimizers(self):
            opt = torch.optim.Adam(self.parameters(), lr=self.lr)
            sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=5, factor=0.5)
            return {
                'optimizer': opt,
                'lr_scheduler': {'scheduler': sched, 'monitor': 'val_loss'},
            }

    return _UNetLightningModule


# ─── Node ─────────────────────────────────────────────────────────────────────

@vision_node(
    type_id='ml_unet_grid',
    label='U-Net Grid',
    category='Machine Learning',
    icon='Layers',
    description=(
        "U-Net convolutif pour la reconstruction de grilles géospatiales (T×H×W). "
        "Entraînement PyTorch Lightning dans un thread. Gère les NaN (masque océan)."
    ),
    inputs=[
        {'id': 'grids', 'color': 'any',  'label': 'Grids (T×H×W)'},
        {'id': 'meta',  'color': 'dict', 'label': 'Meta (optionnel)'},
    ],
    outputs=[
        {'id': 'reconstructed', 'color': 'any',    'label': 'Reconstructed'},
        {'id': 'preview',       'color': 'image',  'label': 'Preview'},
        {'id': 'mse',           'color': 'scalar', 'label': 'MSE'},
        {'id': 'loss_history',  'color': 'dict',   'label': 'Loss History'},
        {'id': 'model_bundle',  'color': 'dict',   'label': 'Model Bundle'},
    ],
    params=[
        {'id': 'n_latent',      'label': 'Canaux de base (n_latent)', 'type': 'int',   'default': 16,   'min': 4,     'max': 256},
        {'id': 'n_levels',      'label': 'Niveaux U-Net',             'type': 'int',   'default': 3,    'min': 1,     'max': 5},
        {'id': 'n_epochs',      'label': 'Epochs',                    'type': 'int',   'default': 30,   'min': 5,     'max': 300},
        {'id': 'batch_size',    'label': 'Batch size',                'type': 'int',   'default': 8,    'min': 1,     'max': 64},
        {'id': 'learning_rate', 'label': 'Learning rate',             'type': 'float', 'default': 0.001},
        {'id': 'val_split',     'label': 'Val split',                 'type': 'float', 'default': 0.2},
        {'id': 'colormap',      'label': 'Colormap',                  'type': 'enum',
         'options': ['Viridis', 'Plasma', 'Jet', 'Inferno'], 'default': 0},
        {'id': 'train',         'label': 'Entraîner',                 'type': 'trigger'},
    ],
    resizable=True, min_width=300, min_height=200,
)
class MLUNetGridNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._state          = 'idle'
        self._thread         = None
        self._lock           = threading.Lock()
        self._model          = None
        self._config         = {}
        self._reconstructed  = None
        self._mse            = None
        self._loss_history   = {'train_loss': [], 'val_loss': []}
        self._preview_cache  = None
        self._norm_mean      = 0.0
        self._norm_std       = 1.0
        self._training_key   = None
        self._progress_msg   = ''
        self._current_epoch  = 0
        self._total_epochs   = 0
        self._last_train_loss = None
        self._last_val_loss   = None

    # ── Clé d'entraînement ──────────────────────────────────────────────────

    @staticmethod
    def _make_key(grids, params):
        return (
            grids.shape,
            int(params.get('n_latent',      16)),
            int(params.get('n_levels',       3)),
            int(params.get('n_epochs',      30)),
            int(params.get('batch_size',     8)),
            float(params.get('learning_rate', 0.001)),
            float(params.get('val_split',    0.2)),
        )

    # ── Inférence (callable depuis le thread et depuis process) ─────────────

    def _update_cache(self, model, grids_orig, grids_proc, nan_mask, mean_val, std_val, H, W):
        """Inférence sur toutes les frames, mise à jour thread-safe de l'état."""
        import torch

        model.eval()
        with torch.no_grad():
            x   = torch.tensor(grids_proc[:, np.newaxis, :, :], dtype=torch.float32)
            out = model(x).squeeze(1).numpy()

        # Recadrer
        out = out[:, :H, :W]

        # Dénormaliser
        recon = out * std_val + mean_val

        # Ré-appliquer NaN
        recon = np.where(nan_mask, np.nan, recon)

        mse = float(np.nanmean((grids_orig - recon) ** 2))

        with self._lock:
            self._reconstructed = recon
            self._mse           = mse

    # ── Thread d'entraînement ────────────────────────────────────────────────

    def _train_thread(self, grids_orig, params):
        try:
            import torch
            from torch.utils.data import DataLoader, TensorDataset, random_split
            try:
                import pytorch_lightning as pl
            except ImportError:
                import lightning.pytorch as pl

            _, _UNetModel = _build_unet_classes()
            _UNetLightningModule = _build_lightning_module(_UNetModel)

            n_latent  = int(params.get('n_latent',      16))
            n_levels  = int(params.get('n_levels',       3))
            n_epochs  = int(params.get('n_epochs',      30))
            batch_size = int(params.get('batch_size',    8))
            lr        = float(params.get('learning_rate', 0.001))
            val_split = float(params.get('val_split',   0.2))

            T, H, W = grids_orig.shape

            # ── Normalisation ──────────────────────────────────────────────
            nan_mask   = np.isnan(grids_orig)
            valid_vals = grids_orig[~nan_mask]
            mean_val   = float(np.mean(valid_vals)) if len(valid_vals) > 0 else 0.0
            std_val    = float(np.std(valid_vals))  if len(valid_vals) > 0 else 1.0
            if std_val == 0.0:
                std_val = 1.0

            grids_filled = np.where(nan_mask, 0.0, grids_orig)
            grids_norm   = (grids_filled - mean_val) / std_val

            # ── Padding ────────────────────────────────────────────────────
            factor  = 2 ** n_levels
            H_pad   = ((H + factor - 1) // factor) * factor
            W_pad   = ((W + factor - 1) // factor) * factor
            pad_h   = H_pad - H
            pad_w   = W_pad - W
            if pad_h > 0 or pad_w > 0:
                grids_norm = np.pad(grids_norm, ((0, 0), (0, pad_h), (0, pad_w)), mode='reflect')

            # ── Dataset ────────────────────────────────────────────────────
            X   = torch.tensor(grids_norm[:, np.newaxis, :, :], dtype=torch.float32)
            ds  = TensorDataset(X, X)  # auto-encodeur : entrée = cible
            n_val = max(1, int(len(X) * val_split))
            n_train = len(X) - n_val
            if n_train < 1:
                n_train = 1
                n_val   = len(X) - 1 if len(X) > 1 else 1
            train_ds, val_ds = random_split(
                ds, [n_train, n_val],
                generator=torch.Generator().manual_seed(42),
            )
            train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
            val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)

            # ── Modèle ─────────────────────────────────────────────────────
            unet   = _UNetModel(base_channels=n_latent, n_levels=n_levels)
            module = _UNetLightningModule(model=unet, lr=lr)

            loss_history = {'train_loss': [], 'val_loss': []}

            with self._lock:
                self._total_epochs   = n_epochs
                self._current_epoch  = 0

            # ── Callback ───────────────────────────────────────────────────
            class _ProgressCallback(pl.Callback):
                def on_train_epoch_end(cb_self, trainer, pl_module):
                    epoch   = trainer.current_epoch + 1   # 1-based
                    metrics = trainer.callback_metrics
                    tl = float(metrics.get('train_loss', float('nan')))
                    vl = float(metrics.get('val_loss',   float('nan')))
                    vl_or_none = None if np.isnan(vl) else vl

                    loss_history['train_loss'].append(tl)
                    if vl_or_none is not None:
                        loss_history['val_loss'].append(vl_or_none)

                    with self._lock:
                        self._current_epoch   = epoch
                        self._last_train_loss = None if np.isnan(tl) else tl
                        self._last_val_loss   = vl_or_none
                        self._loss_history    = {k: list(v) for k, v in loss_history.items()}
                        self._norm_mean       = mean_val
                        self._norm_std        = std_val
                        self._progress_msg    = (
                            f'Epoch {epoch}/{n_epochs} — train={tl:.5f}'
                            + (f' val={vl:.5f}' if vl_or_none is not None else '')
                        )

                    # Mise à jour inférence toutes les 5 epochs ou dernière epoch
                    if epoch % 5 == 0 or epoch == n_epochs:
                        self._update_cache(
                            unet, grids_orig, grids_norm, nan_mask, mean_val, std_val, H, W,
                        )

            trainer = pl.Trainer(
                max_epochs=n_epochs,
                callbacks=[_ProgressCallback()],
                enable_progress_bar=False,
                enable_model_summary=False,
                log_every_n_steps=1,
            )
            trainer.fit(module, train_loader, val_loader)

            # ── Mise à jour finale ─────────────────────────────────────────
            self._update_cache(unet, grids_orig, grids_norm, nan_mask, mean_val, std_val, H, W)

            with self._lock:
                self._model    = unet
                self._config   = {
                    'n_latent': n_latent,
                    'n_levels': n_levels,
                    'H': H,
                    'W': W,
                }
                self._norm_mean    = mean_val
                self._norm_std     = std_val
                self._loss_history = {k: list(v) for k, v in loss_history.items()}
                self._state        = 'done'

            mse = self._mse or 0.0
            send_notification(f'U-Net entraîné ! MSE={mse:.5f}', level='info', notif_id=_NOTIF_ID)

        except Exception as exc:
            with self._lock:
                self._state = 'error'
            send_notification(f'Erreur U-Net : {exc}', level='error', notif_id=_NOTIF_ID)

    # ── process ─────────────────────────────────────────────────────────────

    def process(self, inputs, params):
        if not self.ensure_packages(
            ['torch', 'pytorch_lightning'],
            pip_names=['torch', 'pytorch-lightning'],
            notif_id=_NOTIF_ID,
        ):
            return {}

        grids = inputs.get('grids')
        if grids is None or not isinstance(grids, np.ndarray) or grids.ndim != 3:
            return {}

        trigger = int(params.get('train', 0))

        with self._lock:
            state       = self._state
            current_key = self._training_key

        new_key = self._make_key(grids, params)

        if trigger == 1 and state != 'training' and (
            current_key is None or current_key != new_key or state in ('idle', 'error')
        ):
            with self._lock:
                self._state          = 'training'
                self._training_key   = new_key
                self._loss_history   = {'train_loss': [], 'val_loss': []}
                self._progress_msg   = 'Démarrage U-Net...'
                self._model          = None
                self._reconstructed  = None
                self._mse            = None
                self._current_epoch  = 0
                self._total_epochs   = int(params.get('n_epochs', 30))
                self._last_train_loss = None
                self._last_val_loss   = None

            self._thread = threading.Thread(
                target=self._train_thread,
                args=(grids.copy(), dict(params)),
                daemon=True,
            )
            self._thread.start()

        with self._lock:
            state          = self._state
            progress_msg   = self._progress_msg
            model          = self._model
            recon          = self._reconstructed
            mse            = self._mse
            loss_history   = {k: list(v) for k, v in self._loss_history.items()}
            norm_mean      = self._norm_mean
            norm_std       = self._norm_std
            config         = dict(self._config)
            current_epoch  = self._current_epoch
            total_epochs   = self._total_epochs
            last_tl        = self._last_train_loss
            last_vl        = self._last_val_loss

        if state == 'training' and progress_msg:
            send_notification(progress_msg, level='info', notif_id=_NOTIF_ID + '_prog')

        if model is None:
            # Avant la première inférence intermédiaire : barre de progression seule
            blank = np.zeros((200, 640, 3), dtype=np.uint8)
            if state == 'training' and total_epochs > 0:
                _draw_progress_bar(blank, current_epoch, total_epochs, last_tl, last_vl)
            else:
                msg = "Cliquez 'Entraîner' pour lancer l'entraînement"
                cv2.putText(blank, msg, (10, 105), cv2.FONT_HERSHEY_SIMPLEX,
                            0.42, (150, 150, 150), 1, cv2.LINE_AA)
            return {
                'preview':      blank,
                'loss_history': loss_history,
            }

        # ── Preview matplotlib ───────────────────────────────────────────────
        cmap_idx  = int(params.get('colormap', 0))
        cmap_name = _COLORMAPS[cmap_idx] if cmap_idx < len(_COLORMAPS) else 'viridis'
        n_latent  = int(params.get('n_latent', 16))
        n_levels  = int(params.get('n_levels',  3))

        state_str = {'idle': 'idle', 'training': 'training', 'done': 'done', 'error': 'error'}.get(state, state)

        matplotlib, plt = _get_mpl()
        with matplotlib.rc_context(_MPL_DARK):
            if loss_history.get('train_loss'):
                fig, (ax_img, ax_loss) = plt.subplots(1, 2, figsize=(10, 3.5))
            else:
                fig, ax_img = plt.subplots(1, 1, figsize=(5, 3.5))
                ax_loss = None

            # Panel gauche : reconstruction frame 0
            if recon is not None and recon.ndim == 3 and recon.shape[0] > 0:
                ax_img.imshow(recon[0], cmap=cmap_name, aspect='auto')
                mse_str = f'{mse:.5f}' if mse is not None else '?'
                ax_img.set_title(f'Reconstruction (MSE={mse_str})', fontsize=9)
            else:
                ax_img.set_title('Entraînement en cours...', fontsize=9)
            ax_img.axis('off')

            # Panel droit : courbes loss
            if ax_loss is not None and loss_history.get('train_loss'):
                tl = loss_history['train_loss']
                vl = loss_history.get('val_loss', [])
                ax_loss.plot(tl, color='#4a9eff', linewidth=1.5, label='Train')
                if vl:
                    ax_loss.plot(vl, color='#ff9f4a', linewidth=1.5, label='Val')
                ax_loss.set_xlabel('Epoch')
                ax_loss.set_ylabel('Loss')
                ax_loss.legend(fontsize=8)
                ax_loss.grid(True, alpha=0.4)

            fig.suptitle(
                f'U-Net Grid | {state_str} | k={n_latent} L={n_levels}',
                fontsize=9, color='#cccccc',
            )
            plt.tight_layout()
            preview = _fig_to_bgr(fig)
            plt.close(fig)

        # Barre de progression overlay quand entraînement en cours
        if state == 'training' and total_epochs > 0:
            _draw_progress_bar(preview, current_epoch, total_epochs, last_tl, last_vl)

        model_bundle = {
            'model':      model,
            'config':     config,
            'model_type': 'unet_grid',
            'norm_mean':  norm_mean,
            'norm_std':   norm_std,
        }

        result = {
            'preview':      preview,
            'loss_history': loss_history,
            'model_bundle': model_bundle,
        }
        if recon is not None:
            result['reconstructed'] = recon
            result['mse']           = float(mse) if mse is not None else 0.0

        return result
