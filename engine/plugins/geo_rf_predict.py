"""
geo_rf_predict.py — Predict-only RF classifier (uses model from geo_rf_classifier)

Takes a feature stack + trained model bundle (.joblib loaded from disk),
predicts class for every pixel. Same feature schema as training is required:
band count, band order, dtype.

Designed for bi-temporal classification:

  geo_rf_classifier (train on 2024) ──model──┐
                                              ├──→ geo_rf_predict ──→ classmap_2018
  Stack 2018 features ─────────────features──┘

Notes:
  - No training data needed — model is loaded from .joblib (saved by classifier)
  - Feature stack MUST have same band count and band order as the training set
  - NaN pixels are replaced with 0 before prediction (consistent with training path)
"""
from __future__ import annotations
import os

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'geo_rf_predict'

# WorldCover-ish class palette (BGR) — matches geo_rf_classifier
_PALETTE = {
    10:  (0, 100, 0),       20: (34, 187, 255),    30: (76, 255, 255),
    40:  (255, 150, 240),   50: (0, 0, 250),       60: (180, 180, 180),
    70:  (240, 240, 240),   80: (200, 100, 0),     90: (160, 150, 0),
    95:  (117, 207, 0),    100: (160, 230, 250),
}


def _colorize(class_map: np.ndarray, classes: list[int]) -> np.ndarray:
    """Map class values to BGR colors."""
    h, w = class_map.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)
    for cls in classes:
        bgr = _PALETTE.get(int(cls), (128, 128, 128))
        out[class_map == cls] = bgr
    return out


@vision_node(
    type_id='geo_rf_predict',
    label='RF Predict',
    category='Machine Learning',
    icon='Brain',
    description=(
        'Predict-only RF classifier — applies a model trained by geo_rf_classifier '
        'to a new feature stack. Designed for bi-temporal classification: '
        'train once on 2024 features+labels, predict on 2018 features. '
        'Feature band count + order MUST match training. Reads model from .joblib '
        'saved by geo_rf_classifier.'
    ),
    inputs=[
        {'id': 'features', 'color': 'geotiff', 'label': 'Feature stack (same schema as training)'},
        {'id': 'model',    'color': 'dict',    'label': 'Trained model bundle from geo_rf_classifier'},
    ],
    outputs=[
        {'id': 'classification', 'color': 'geotiff', 'label': 'Classification map'},
        {'id': 'preview',        'color': 'image',   'label': 'Classification RGB'},
        {'id': 'confidence',     'color': 'image',   'label': 'Confidence map'},
    ],
    params=[
        {'id': 'node_note', 'type': 'string', 'default': '',
         'label': 'Note'},
    ],
    resizable=True, min_width=280, min_height=160,
)
class GeoRFPredictNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        if not self.ensure_packages(['joblib', 'sklearn'],
                                    pip_names=['joblib', 'scikit-learn'],
                                    notif_id=_NOTIF):
            return {}
        import joblib

        feat_geo = inputs.get('features')
        model    = inputs.get('model')

        if not isinstance(feat_geo, dict) or feat_geo.get('bands') is None:
            send_notification('RF Predict: connect features (geotiff)',
                              notif_id=_NOTIF)
            return {}
        if not isinstance(model, dict) or 'path' not in model:
            send_notification('RF Predict: connect model bundle from geo_rf_classifier',
                              notif_id=_NOTIF)
            return {}

        model_path = model['path']
        if not os.path.exists(model_path):
            send_notification(
                f'RF Predict: model file not found: {model_path}. '
                f'Re-run geo_rf_classifier to regenerate.',
                level='error', notif_id=_NOTIF,
            )
            return {}

        # ── Load model bundle ─────────────────────────────────────────────────
        try:
            bundle = joblib.load(model_path)
        except Exception as e:
            send_notification(f'RF Predict: failed to load model: {e}',
                              level='error', notif_id=_NOTIF)
            return {}

        rf            = bundle['rf']
        le            = bundle['label_encoder']
        train_bands   = bundle['band_names']
        classes       = bundle['classes']

        # ── Extract features ──────────────────────────────────────────────────
        bands = feat_geo['bands']
        if bands.ndim == 2:
            bands = bands[np.newaxis]
        C, fH, fW = bands.shape

        n_features_expected = rf.n_features_in_
        if C != n_features_expected:
            send_notification(
                f'RF Predict: feature count mismatch — model expects '
                f'{n_features_expected} bands, got {C}. '
                f'Training bands: {train_bands}',
                level='error', notif_id=_NOTIF,
            )
            return {}

        send_notification(
            f'RF Predict: predicting {fH * fW:,} pixels with {C} features '
            f'({len(classes)} classes)…',
            progress=0.1, notif_id=_NOTIF,
        )

        # ── Predict (chunked to keep RAM bounded) ─────────────────────────────
        X_all = bands.reshape(C, -1).T.astype(np.float32)
        CHUNK = 500_000
        n_pix = X_all.shape[0]
        pred_enc  = np.zeros(n_pix, dtype=np.int32)
        conf_flat = np.zeros(n_pix, dtype=np.float32)

        for start in range(0, n_pix, CHUNK):
            end   = min(start + CHUNK, n_pix)
            chunk = X_all[start:end]
            chunk = np.where(np.isfinite(chunk), chunk, 0.0)
            proba = rf.predict_proba(chunk)
            pred_enc[start:end]  = rf.predict(chunk)
            conf_flat[start:end] = proba.max(axis=1)

            send_notification(
                f'RF Predict: {end:,}/{n_pix:,} px',
                progress=0.1 + 0.85 * (end / n_pix),
                notif_id=_NOTIF,
            )

        pred_classes = le.inverse_transform(pred_enc)
        class_map = pred_classes.reshape(fH, fW).astype(np.int32)
        conf_map  = conf_flat.reshape(fH, fW)

        # ── Visualize ─────────────────────────────────────────────────────────
        preview = _colorize(class_map, classes)
        conf_u8 = (conf_map * 255).clip(0, 255).astype(np.uint8)
        conf_bgr = cv2.applyColorMap(conf_u8, cv2.COLORMAP_TURBO)

        # ── Build geo dict ────────────────────────────────────────────────────
        out_geo = {
            'bands':     class_map[np.newaxis].astype(np.float32),
            'crs':       feat_geo.get('crs'),
            'transform': feat_geo.get('transform'),
            'count':     1,
            'height':    fH,
            'width':     fW,
            'dtype':     'float32',
            'preview':   preview,
        }

        send_notification(
            f'RF Predict: done — {fH}×{fW} px  ({len(classes)} classes)',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'classification': out_geo,
            'preview':        preview,
            'confidence':     conf_bgr,
        }
