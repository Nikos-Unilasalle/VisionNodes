"""
ml_pytorch_trainer.py — Entraîneur PyTorch Lightning générique.

L'utilisateur définit un LightningModule et une fonction make_dataloaders dans le champ code.
L'entraînement tourne dans un thread daemon séparé.
"""
import threading
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_pytorch_trainer'

DEFAULT_CODE = '''\
"""
Définissez ici votre LightningModule ET la fonction make_dataloaders.

Variables disponibles dans le contexte :
  - data    : dict reçu en entrée du nœud
  - params  : dict des paramètres (n_epochs, lr, batch_size, etc.)
  - torch, nn, F, pl : déjà importés

Deux éléments OBLIGATOIRES :
  1. class MyModule(pl.LightningModule) avec training_step, validation_step, configure_optimizers
  2. def make_dataloaders(data, params) -> (module, train_loader, val_loader)
"""
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl
from torch.utils.data import DataLoader, TensorDataset, random_split
import torch


class MyModule(pl.LightningModule):
    def __init__(self, input_dim=10, latent_dim=4, lr=0.001):
        super().__init__()
        self.save_hyperparameters()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 32), nn.ReLU(), nn.Linear(32, latent_dim))
        self.decoder = nn.Sequential(nn.Linear(latent_dim, 32), nn.ReLU(), nn.Linear(32, input_dim))

    def forward(self, x):
        return self.decoder(self.encoder(x))

    def training_step(self, batch, batch_idx):
        x = batch[0]
        loss = F.mse_loss(self(x), x)
        self.log(\'train_loss\', loss, on_epoch=True, on_step=False)
        return loss

    def validation_step(self, batch, batch_idx):
        x = batch[0]
        self.log(\'val_loss\', F.mse_loss(self(x), x), on_epoch=True, on_step=False)

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams.lr)


def make_dataloaders(data, params):
    # data doit contenir \'X\' (array numpy ou tensor)
    X = torch.tensor(data[\'X\'], dtype=torch.float32)
    ds = TensorDataset(X)
    n_val = max(1, int(len(X) * 0.2))
    train_ds, val_ds = random_split(ds, [len(X) - n_val, n_val],
                                    generator=torch.Generator().manual_seed(42))
    bs = int(params.get(\'batch_size\', 16))
    input_dim = X.shape[1] if X.ndim > 1 else 1
    lr = float(params.get(\'learning_rate\', 0.001))
    module = MyModule(input_dim=input_dim, latent_dim=4, lr=lr)
    return module, DataLoader(train_ds, batch_size=bs, shuffle=True, num_workers=0), \\
           DataLoader(val_ds, batch_size=bs, num_workers=0)
'''


@vision_node(
    type_id='ml_pytorch_trainer',
    label='PyTorch Trainer',
    category='Machine Learning',
    icon='Cpu',
    description="Entraîneur PyTorch Lightning générique — définissez votre LightningModule dans le champ code.",
    inputs=[
        {'id': 'data', 'color': 'dict', 'label': 'Data (dict)'},
    ],
    outputs=[
        {'id': 'model_bundle',  'color': 'dict', 'label': 'Model Bundle'},
        {'id': 'loss_history',  'color': 'dict', 'label': 'Loss History'},
        {'id': 'status',        'color': 'dict', 'label': 'Status'},
    ],
    params=[
        {'id': 'code',          'label': 'Code Python',      'type': 'code',   'default': DEFAULT_CODE},
        {'id': 'n_epochs',      'label': 'Epochs',           'type': 'int',    'default': 30, 'min': 1, 'max': 300},
        {'id': 'patience',      'label': 'Early stop patience', 'type': 'int', 'default': 10, 'min': 1, 'max': 50},
        {'id': 'learning_rate', 'label': 'Learning rate',    'type': 'float',  'default': 0.001},
        {'id': 'batch_size',    'label': 'Batch size',       'type': 'int',    'default': 16, 'min': 1, 'max': 256},
        {'id': 'accelerator',   'label': 'Accélérateur',     'type': 'enum',
         'options': ['cpu', 'gpu (si dispo)', 'auto'], 'default': 2},
        {'id': 'train',         'label': 'Entraîner',        'type': 'trigger'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class MLPyTorchTrainerNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._state         = 'idle'   # idle | training | done | error
        self._thread        = None
        self._lock          = threading.Lock()
        self._model_bundle  = None
        self._loss_history  = {'train_loss': [], 'val_loss': []}
        self._progress_msg  = ''
        self._epoch         = 0
        self._error_msg     = ''

    # ── Thread d'entraînement ────────────────────────────────────────────────

    def _train_thread(self, data, params, code):
        try:
            import torch
            try:
                import pytorch_lightning as pl
            except ImportError:
                import lightning.pytorch as pl
            from pytorch_lightning.callbacks import EarlyStopping

            # ── Exécuter le code utilisateur ──────────────────────────────────
            namespace = {
                'data':   data,
                'params': params,
                'torch':  torch,
                'nn':     torch.nn,
                'F':      torch.nn.functional,
                'pl':     pl,
                'np':     np,
            }
            exec(compile(code, '<trainer_code>', 'exec'), namespace)  # noqa: S102

            make_dataloaders_fn = namespace.get('make_dataloaders')
            if make_dataloaders_fn is None:
                raise ValueError("La fonction 'make_dataloaders' est introuvable dans le code.")

            module, train_loader, val_loader = make_dataloaders_fn(data, params)

            if not isinstance(module, pl.LightningModule):
                raise TypeError("make_dataloaders doit retourner un pl.LightningModule en premier élément.")

            n_epochs = int(params.get('n_epochs', 30))
            patience = int(params.get('patience', 10))
            acc_idx  = int(params.get('accelerator', 2))
            acc_map  = {0: 'cpu', 1: 'gpu', 2: 'auto'}
            accelerator = acc_map.get(acc_idx, 'auto')

            loss_history = {'train_loss': [], 'val_loss': []}

            # ── Callback de progression ──────────────────────────────────────
            class _ProgressCallback(pl.Callback):
                def __init__(cb_self):
                    super().__init__()

                def on_train_epoch_end(cb_self, trainer, pl_module):
                    epoch = trainer.current_epoch
                    metrics = trainer.callback_metrics
                    tl = float(metrics.get('train_loss', float('nan')))
                    vl = float(metrics.get('val_loss', float('nan')))

                    loss_history['train_loss'].append(tl)
                    if not np.isnan(vl):
                        loss_history['val_loss'].append(vl)

                    with self._lock:
                        self._loss_history  = {k: list(v) for k, v in loss_history.items()}
                        self._epoch         = epoch
                        self._progress_msg  = (
                            f'Epoch {epoch + 1}/{n_epochs} — '
                            f'train={tl:.4f}'
                            + (f' val={vl:.4f}' if not np.isnan(vl) else '')
                        )

            early_stop = EarlyStopping(
                monitor='val_loss',
                patience=patience,
                mode='min',
                verbose=False,
            )
            progress_cb = _ProgressCallback()

            trainer = pl.Trainer(
                max_epochs=n_epochs,
                accelerator=accelerator,
                callbacks=[early_stop, progress_cb],
                enable_progress_bar=False,
                enable_model_summary=False,
                log_every_n_steps=1,
                logger=False,
            )
            trainer.fit(module, train_loader, val_loader)

            # ── Fin de l'entraînement ─────────────────────────────────────────
            final_val = loss_history['val_loss'][-1] if loss_history['val_loss'] else float('nan')
            bundle = {
                'model':       module,
                'config':      {
                    'n_epochs':      n_epochs,
                    'learning_rate': float(params.get('learning_rate', 0.001)),
                    'batch_size':    int(params.get('batch_size', 16)),
                },
                'model_type':  'custom',
                'loss_history': {k: list(v) for k, v in loss_history.items()},
            }

            with self._lock:
                self._model_bundle = bundle
                self._loss_history = {k: list(v) for k, v in loss_history.items()}
                self._state        = 'done'

            msg = f'Training terminé — val_loss={final_val:.4f}' if not np.isnan(final_val) \
                  else 'Training terminé'
            send_notification(msg, level='info', notif_id=_NOTIF_ID)

        except Exception as exc:
            with self._lock:
                self._state     = 'error'
                self._error_msg = str(exc)
            send_notification(f'Erreur training : {exc}', level='error', notif_id=_NOTIF_ID)

    # ── process ─────────────────────────────────────────────────────────────

    def process(self, inputs, params):
        if not self.ensure_packages(
            ['torch', 'pytorch_lightning'],
            pip_names=['torch', 'pytorch-lightning'],
            notif_id=_NOTIF_ID,
        ):
            return {
                'status': {'state': 'error', 'epoch': 0, 'message': 'torch ou pytorch_lightning manquant'}
            }

        data    = inputs.get('data') or {}
        trigger = int(params.get('train', 0))
        code    = str(params.get('code', DEFAULT_CODE))

        with self._lock:
            state = self._state

        if trigger == 1 and state != 'training':
            with self._lock:
                self._state        = 'training'
                self._loss_history = {'train_loss': [], 'val_loss': []}
                self._epoch        = 0
                self._progress_msg = 'Démarrage...'
                self._model_bundle = None

            self._thread = threading.Thread(
                target=self._train_thread,
                args=(data, dict(params), code),
                daemon=True,
            )
            self._thread.start()

        with self._lock:
            state        = self._state
            epoch        = self._epoch
            progress_msg = self._progress_msg
            loss_history = {k: list(v) for k, v in self._loss_history.items()}
            bundle       = self._model_bundle
            error_msg    = self._error_msg

        if state == 'training' and progress_msg:
            send_notification(progress_msg, level='info', notif_id=_NOTIF_ID + '_prog')

        status = {
            'state':   state,
            'epoch':   epoch,
            'message': error_msg if state == 'error' else progress_msg,
        }

        result = {'status': status, 'loss_history': loss_history}
        if bundle is not None:
            result['model_bundle'] = bundle

        return result
