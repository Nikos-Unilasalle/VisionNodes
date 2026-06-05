"""
ml_model_saver.py — Sauvegarde un model bundle PyTorch sur disque.
"""
import os
from registry import vision_node, NodeProcessor, send_notification

_NOTIF_ID = 'ml_model_saver'


@vision_node(
    type_id='ml_model_saver',
    label='Model Saver',
    category='Machine Learning',
    icon='Save',
    description="Sauvegarde un model bundle PyTorch (dict) sur disque. Déclencher avec le trigger 'save'.",
    inputs=[
        {'id': 'model_bundle', 'color': 'dict', 'label': 'Model Bundle'},
    ],
    outputs=[
        {'id': 'status', 'color': 'dict', 'label': 'Status'},
    ],
    params=[
        {'id': 'path', 'label': 'Chemin de sauvegarde', 'type': 'string', 'default': 'model.pt'},
        {'id': 'save', 'label': 'Sauvegarder',          'type': 'trigger'},
    ],
    resizable=True, min_width=220, min_height=120,
)
class MLModelSaverNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._last_save_path = ''
        self._last_save_size = 0.0
        self._last_saved = False

    def process(self, inputs, params):
        if not self.ensure_packages(['torch'], pip_names=['torch'], notif_id=_NOTIF_ID):
            return {'status': {'saved': False, 'path': '', 'size_mb': 0.0, 'error': 'torch manquant'}}

        import torch

        bundle = inputs.get('model_bundle')
        trigger = int(params.get('save', 0))
        path = str(params.get('path', 'model.pt')).strip() or 'model.pt'

        if trigger == 1:
            if bundle is None:
                send_notification('Aucun modèle connecté à ml_model_saver', level='warning', notif_id=_NOTIF_ID)
                return {
                    'status': {
                        'saved': False,
                        'path': path,
                        'size_mb': 0.0,
                        'error': 'bundle is None',
                    }
                }

            try:
                parent = os.path.dirname(os.path.abspath(path))
                if parent:
                    os.makedirs(parent, exist_ok=True)

                torch.save(bundle, path)

                size_mb = os.path.getsize(path) / (1024 * 1024)
                self._last_save_path = path
                self._last_save_size = size_mb
                self._last_saved = True

                send_notification(
                    f'Modèle sauvegardé → {path} ({size_mb:.2f} MB)',
                    level='info',
                    notif_id=_NOTIF_ID,
                )

            except Exception as exc:
                send_notification(f'Erreur sauvegarde modèle : {exc}', level='error', notif_id=_NOTIF_ID)
                return {
                    'status': {
                        'saved': False,
                        'path': path,
                        'size_mb': 0.0,
                        'error': str(exc),
                    }
                }

        return {
            'status': {
                'saved': self._last_saved,
                'path':    self._last_save_path,
                'size_mb': round(self._last_save_size, 3),
            }
        }
