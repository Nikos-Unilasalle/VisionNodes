"""
ml_table_mask_filter.py — Filter a pixel DataFrame by a binary spatial mask.

Keeps only rows whose pixel index (__px_idx) falls within the mask (value > 0).
Use after geo_bands_to_table to restrict inference to water/ROI pixels only.
Requires __px_idx column (produced by geo_bands_to_table or ml_synthetic_regression_data).
"""
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'table_mask_filter'


@vision_node(
    type_id='ml_table_mask_filter',
    label='Table Mask Filter',
    category='ml',
    icon='Filter',
    description=(
        "Filter a pixel DataFrame using a binary spatial mask. "
        "Keeps only rows whose __px_idx falls in mask-positive pixels. "
        "Use to restrict ML inference to water/ROI pixels and avoid "
        "nonsensical predictions on land, clouds, or nodata areas."
    ),
    inputs=[
        {'id': 'table', 'color': 'data', 'label': 'Full pixel table (__px_idx required)'},
        {'id': 'mask',  'color': 'mask', 'label': 'Binary mask (255=keep, 0=discard)'},
    ],
    outputs=[
        {'id': 'table',          'color': 'data',   'label': 'Filtered table'},
        {'id': 'n_kept',         'color': 'scalar', 'label': 'Rows kept'},
        {'id': 'n_dropped',      'color': 'scalar', 'label': 'Rows dropped'},
        {'id': 'preview',        'color': 'image',  'label': 'Filter stats'},
    ],
    params=[],
    resizable=True, min_width=240, min_height=140,
)
class TableMaskFilterNode(NodeProcessor):

    def process(self, inputs, params):
        if not self.ensure_packages(['pandas'], notif_id=_NOTIF):
            return {}
        import pandas as pd

        df   = inputs.get('table')
        mask = inputs.get('mask')

        if not isinstance(df, pd.DataFrame):
            send_notification('TableMaskFilter: waiting for TABLE input', notif_id=_NOTIF)
            return {}

        if '__px_idx' not in df.columns:
            send_notification('TableMaskFilter: no __px_idx column', level='error', notif_id=_NOTIF)
            return {'table': df, 'n_kept': float(len(df)), 'n_dropped': 0.0}

        if not isinstance(mask, np.ndarray):
            # No mask connected — pass through
            return {
                'table':     df,
                'n_kept':    float(len(df)),
                'n_dropped': 0.0,
                'preview':   self._panel([f'No mask — pass-through', f'Rows: {len(df):,}']),
            }

        # Flatten mask to 1D
        m = mask[:, :, 0] if mask.ndim == 3 else mask
        mask_flat = m.ravel().astype(np.uint8)

        idx     = df['__px_idx'].values.astype(int)
        in_mask = (idx >= 0) & (idx < len(mask_flat)) & (mask_flat[idx] > 0)

        df_out   = df[in_mask].copy()
        n_kept   = int(in_mask.sum())
        n_drop   = int((~in_mask).sum())

        send_notification(
            f'TableMaskFilter: kept {n_kept:,} / {len(df):,} rows ({n_drop:,} masked out)',
            progress=1.0, notif_id=_NOTIF,
        )

        lines = [
            f'Input rows: {len(df):,}',
            f'Kept (mask > 0): {n_kept:,}',
            f'Dropped: {n_drop:,}',
            f'Ratio: {n_kept/max(len(df),1)*100:.1f}% kept',
        ]
        return {
            'table':     df_out,
            'n_kept':    float(n_kept),
            'n_dropped': float(n_drop),
            'preview':   self._panel(lines),
        }

    @staticmethod
    def _panel(lines: list, w: int = 300, h: int = 120) -> np.ndarray:
        img = np.full((h, w, 3), 22, dtype=np.uint8)
        cv2.rectangle(img, (0, 0), (w, 26), (45, 45, 45), -1)
        cv2.putText(img, 'Table Mask Filter', (8, 17), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.line(img, (0, 26), (w, 26), (80, 80, 80), 1)
        for i, line in enumerate(lines[:(h - 36) // 15]):
            color = (140, 200, 255) if i == 0 else (185, 185, 185)
            cv2.putText(img, str(line)[:48], (8, 44 + i * 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
        return img
