"""
ml_model_loader.py — Charge un model bundle PyTorch depuis disque et applique l'inférence sur des grilles.
"""
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_model_loader'


def _rebuild_model(bundle):
    """Reconstruit l'objet modèle PyTorch depuis un bundle.

    Supporte deux formes :
      - bundle['state_dict'] + model_type (forme sérialisable recommandée)
      - bundle['model'] : objet modèle direct (compat. ascendante en mémoire)
    """
    model = bundle.get('model')
    if model is not None:
        return model

    state_dict = bundle.get('state_dict')
    if state_dict is None:
        return None

    model_type = bundle.get('model_type', '')
    config     = bundle.get('config', {})

    if model_type == 'unet_grid':
        from ml_unet_grid import rebuild_unet
        model = rebuild_unet(config)
        model.load_state_dict(state_dict)
        return model

    return None


def _apply_bundle_to_grids(bundle, grids):
    """Applique un model bundle sur des grilles numpy (T,H,W). Retourne (reconstructed, mse)."""
    import torch

    model = _rebuild_model(bundle)
    if model is None:
        return None, None

    config    = bundle.get('config', {})
    norm_mean = float(bundle.get('norm_mean', 0.0))
    norm_std  = float(bundle.get('norm_std',  1.0))

    if norm_std == 0.0:
        norm_std = 1.0

    grids = np.array(grids, dtype=np.float32)
    T, H, W = grids.shape

    # NaN mask — normaliser PUIS remplir la terre à 0 (= moyenne), comme à
    # l'entraînement (sinon la terre part à -mean/std et fausse l'inférence).
    nan_mask   = np.isnan(grids)
    grids_norm = (grids - norm_mean) / norm_std
    grids_norm = np.where(nan_mask, 0.0, grids_norm).astype(np.float32)

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

    # MSE (océan uniquement)
    diff  = grids - recon
    mse   = float(np.nanmean(diff ** 2))

    return recon, mse


@vision_node(
    type_id='ml_model_loader',
    label='Model Loader',
    category='Machine Learning',
    icon='FolderOpen',
    description="Loads a PyTorch model bundle from disk and applies inference on spatial grids if connected.",
    inputs=[
        {'id': 'grids', 'color': 'any', 'label': 'Grids (T×H×W) — optional'},
    ],
    outputs=[
        {'id': 'model_bundle',  'color': 'dict',   'label': 'Model Bundle'},
        {'id': 'reconstructed', 'color': 'any',    'label': 'Reconstructed'},
        {'id': 'mse',           'color': 'scalar', 'label': 'MSE'},
        {'id': 'status',        'color': 'dict',   'label': 'Status'},
    ],
    params=[
        {'id': 'path', 'label': 'Model path', 'type': 'string',  'default': 'model.pt'},
        {'id': 'load', 'label': 'Reload',     'type': 'trigger'},
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
            return {'status': {'loaded': False, 'error': 'torch missing'}}

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
                    f'Model loaded from {path}',
                    level='info',
                    notif_id=_NOTIF_ID,
                )
            except Exception as exc:
                self._bundle = None
                self._error  = str(exc)
                send_notification(f'Error loading model: {exc}', level='error', notif_id=_NOTIF_ID)

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
