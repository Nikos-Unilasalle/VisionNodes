"""
ml_model_loader.py — Charge un model bundle PyTorch depuis disque et applique l'inférence sur des grilles.
"""
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_model_loader'


def _apply_bundle_to_grids(bundle, grids):
    """Applique un model bundle sur des grilles numpy (T,H,W). Retourne (reconstructed, mse)."""
    import torch

    model = bundle.get('model')
    if model is None:
        return None, None

    config    = bundle.get('config', {})
    norm_mean = float(bundle.get('norm_mean', 0.0))
    norm_std  = float(bundle.get('norm_std',  1.0))

    if norm_std == 0.0:
        norm_std = 1.0

    grids = np.array(grids, dtype=np.float32)
    T, H, W = grids.shape

    # NaN mask
    nan_mask = np.isnan(grids)
    grids_filled = np.where(nan_mask, 0.0, grids)

    # Normaliser
    grids_norm = (grids_filled - norm_mean) / norm_std

    # Déterminer n_levels pour le padding
    n_levels = int(config.get('n_levels', 3))
    factor   = 2 ** n_levels
    H_pad    = ((H + factor - 1) // factor) * factor
    W_pad    = ((W + factor - 1) // factor) * factor

    # Padder
    pad_h = H_pad - H
    pad_w = W_pad - W
    if pad_h > 0 or pad_w > 0:
        grids_norm = np.pad(grids_norm, ((0, 0), (0, pad_h), (0, pad_w)), mode='reflect')

    # Inférence
    model_type = bundle.get('model_type', '')
    model.eval()
    with torch.no_grad():
        x = torch.tensor(grids_norm[:, np.newaxis, :, :], dtype=torch.float32)  # (T,1,H_pad,W_pad)
        out = model(x)                                                            # (T,1,H_pad,W_pad)
        out_np = out.squeeze(1).numpy()                                           # (T,H_pad,W_pad)

    # Recadrer au dimensions originales
    out_np = out_np[:, :H, :W]

    # Dénormaliser
    recon = out_np * norm_std + norm_mean

    # Ré-appliquer masque NaN
    recon = np.where(nan_mask, np.nan, recon)

    # MSE
    diff  = grids - recon
    mse   = float(np.nanmean(diff ** 2))

    return recon, mse


@vision_node(
    type_id='ml_model_loader',
    label='Model Loader',
    category='Machine Learning',
    icon='FolderOpen',
    description="Charge un model bundle PyTorch depuis disque. Applique l'inférence sur des grilles si connecté.",
    inputs=[
        {'id': 'grids', 'color': 'any', 'label': 'Grids (T×H×W) — optionnel'},
    ],
    outputs=[
        {'id': 'model_bundle',  'color': 'dict',   'label': 'Model Bundle'},
        {'id': 'reconstructed', 'color': 'any',    'label': 'Reconstructed'},
        {'id': 'mse',           'color': 'scalar', 'label': 'MSE'},
        {'id': 'status',        'color': 'dict',   'label': 'Status'},
    ],
    params=[
        {'id': 'path', 'label': 'Chemin du modèle', 'type': 'string',  'default': 'model.pt'},
        {'id': 'load', 'label': 'Recharger',         'type': 'trigger'},
    ],
    resizable=True, min_width=220, min_height=130,
)
class MLModelLoaderNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._bundle     = None
        self._loaded_path = ''
        self._error      = ''

    def process(self, inputs, params):
        if not self.ensure_packages(['torch'], pip_names=['torch'], notif_id=_NOTIF_ID):
            return {'status': {'loaded': False, 'error': 'torch manquant'}}

        import torch

        path    = str(params.get('path', 'model.pt')).strip() or 'model.pt'
        trigger = int(params.get('load', 0))

        need_load = (
            trigger == 1
            or self._bundle is None
            or self._loaded_path != path
        )

        if need_load:
            try:
                self._bundle      = torch.load(path, map_location='cpu', weights_only=False)
                self._loaded_path = path
                self._error       = ''
                send_notification(
                    f'Modèle chargé depuis {path}',
                    level='info',
                    notif_id=_NOTIF_ID,
                )
            except Exception as exc:
                self._bundle = None
                self._error  = str(exc)
                send_notification(f'Erreur chargement modèle : {exc}', level='error', notif_id=_NOTIF_ID)

        if self._bundle is None:
            return {
                'status': {'loaded': False, 'path': path, 'error': self._error},
            }

        # Status de base
        model_type = self._bundle.get('model_type', 'unknown')
        config     = self._bundle.get('config', {})
        status = {
            'loaded':     True,
            'path':       self._loaded_path,
            'model_type': model_type,
            'config':     config,
        }

        grids = inputs.get('grids')

        if grids is not None and isinstance(grids, np.ndarray) and grids.ndim == 3:
            recon, mse = _apply_bundle_to_grids(self._bundle, grids)
            if recon is not None:
                return {
                    'model_bundle':  self._bundle,
                    'reconstructed': recon,
                    'mse':           mse if mse is not None else 0.0,
                    'status':        status,
                }

        return {
            'model_bundle': self._bundle,
            'mse':          0.0,
            'status':       status,
        }
