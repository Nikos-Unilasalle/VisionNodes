"""
ml_classification_report.py — Publication-quality classification report panel.

Takes report_data (dict from sklearn classification_report(output_dict=True)) and
optionally a conf_matrix dict (from geo_rf_classifier) and renders a two-panel figure:

  Top:    Normalized confusion matrix heatmap (row-normalized → recall on diagonal)
  Bottom: Precision / Recall / F1 / Support table, F1 cells color-coded

If conf_matrix not connected, renders the metrics table only.

Key scalars exposed:
  - f1_main  (F1 of class target A, e.g. 95 = Mangroves)
  - f1_b     (F1 of class target B, e.g. 60 = Bare/orpaillage)
  - oa       (Overall accuracy)

Typical use:
  geo_rf_classifier → report_data + conf_matrix → ml_classification_report → output_display
"""
from __future__ import annotations
import io
import numpy as np
import cv2
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'ml_cls_report'

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

_WC_DEFAULTS = '10=Trees,60=Bare,80=Water,90=Wetland,95=Mangroves'


def _parse_label_map(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in s.split(','):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            out[k.strip()] = v.strip()
    return out


@vision_node(
    type_id='ml_classification_report',
    label='Classification Report',
    category='Machine Learning',
    icon='ClipboardList',
    description=(
        "Render a publication-quality classification report from sklearn outputs. "
        "Top panel: 5×5 normalized confusion matrix (row-normalized, recall on diagonal, "
        "Blues colormap). Bottom panel: precision / recall / F1 / support table with "
        "F1 cells color-coded (green / amber / red). Target classes (e.g. 95=Mangroves, "
        "60=Bare) starred and F1 scalars exposed for pipeline thresholding. "
        "Connect report_data + conf_matrix outputs from geo_rf_classifier."
    ),
    inputs=[
        {'id': 'report_data', 'color': 'dict', 'label': 'report_data (classification_report dict)'},
        {'id': 'conf_matrix', 'color': 'data', 'label': 'conf_matrix (normalized matrix dict)'},
    ],
    outputs=[
        {'id': 'report',  'color': 'image',  'label': 'Full report panel'},
        {'id': 'f1_main', 'color': 'scalar', 'label': 'F1 class target A'},
        {'id': 'f1_b',    'color': 'scalar', 'label': 'F1 class target B'},
        {'id': 'oa',      'color': 'scalar', 'label': 'Overall accuracy'},
    ],
    params=[
        {'id': '_sec_targets', 'label': 'Target Classes', 'type': 'section'},
        {'id': 'class_target_a',    'type': 'string', 'default': '95',
         'label': 'Class target A (e.g. 95 = Mangroves)'},
        {'id': 'class_target_b',    'type': 'string', 'default': '60',
         'label': 'Class target B (e.g. 60 = Bare/orpaillage)'},
        {'id': '_sec_thresholds', 'label': 'F1 Thresholds', 'type': 'section'},
        {'id': 'f1_threshold_high', 'type': 'float',  'default': 0.85, 'min': 0.0, 'max': 1.0,
         'label': 'F1 threshold high (green ≥ this)'},
        {'id': 'f1_threshold_low',  'type': 'float',  'default': 0.75, 'min': 0.0, 'max': 1.0,
         'label': 'F1 threshold low (orange ≥ this, else red)'},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'class_labels',      'type': 'string', 'default': _WC_DEFAULTS,
         'label': 'Class labels (value=name, comma-sep)'},
        {'id': 'dpi',               'type': 'int',    'default': 110, 'min': 72, 'max': 300,
         'label': 'Output DPI'},
        {'id': 'node_note',         'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=320, min_height=200,
)
class MLClassificationReportNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        report_data = inputs.get('report_data')
        conf_matrix = inputs.get('conf_matrix')

        if not isinstance(report_data, dict):
            send_notification(
                'Classification Report: connect report_data dict from geo_rf_classifier',
                notif_id=_NOTIF,
            )
            return {}

        # ── Parse params ──────────────────────────────────────────────────────
        target_a   = str(params.get('class_target_a', '95')).strip()
        target_b   = str(params.get('class_target_b', '60')).strip()
        thr_high   = float(params.get('f1_threshold_high', 0.85))
        thr_low    = float(params.get('f1_threshold_low',  0.75))
        labels_str = str(params.get('class_labels', _WC_DEFAULTS)).strip()
        dpi        = max(72, int(params.get('dpi', 110)))
        label_map  = _parse_label_map(labels_str)

        # ── Extract metrics ───────────────────────────────────────────────────
        _skip = {'accuracy', 'macro avg', 'weighted avg'}
        class_rows: dict[str, dict] = {
            k: v for k, v in report_data.items()
            if k not in _skip and isinstance(v, dict)
        }
        oa  = float(report_data.get('accuracy', 0.0))
        f1_a = float(class_rows.get(target_a, {}).get('f1-score', 0.0))
        f1_b = float(class_rows.get(target_b, {}).get('f1-score', 0.0))

        # ── Check conf_matrix ─────────────────────────────────────────────────
        has_cm = (
            isinstance(conf_matrix, dict)
            and 'normalized' in conf_matrix
            and 'labels'     in conf_matrix
        )

        # ── Render ────────────────────────────────────────────────────────────
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            n_cls  = len(class_rows)
            tbl_h  = max(1.8, n_cls * 0.38 + 0.8)
            fig_h  = (4.2 + tbl_h) if has_cm else tbl_h + 0.6

            with plt.rc_context(_MPL_DARK):
                if has_cm:
                    fig, (ax_cm, ax_tbl) = plt.subplots(
                        2, 1, figsize=(7.5, fig_h),
                        gridspec_kw={'height_ratios': [4.2, tbl_h]},
                    )
                else:
                    fig, ax_tbl = plt.subplots(figsize=(7.5, fig_h))
                    ax_cm = None

                # ── Top: normalized confusion matrix ──────────────────────────
                if has_cm:
                    cm_norm  = np.array(conf_matrix['normalized'], dtype=float)
                    orig_cls = conf_matrix.get('original_classes', [])
                    cm_labels_raw = list(conf_matrix['labels'])

                    if orig_cls:
                        display_labels = [
                            label_map.get(str(int(c)), str(int(c)))
                            for c in orig_cls
                        ]
                    else:
                        display_labels = [label_map.get(l, l) for l in cm_labels_raw]

                    n = cm_norm.shape[0]
                    im = ax_cm.imshow(
                        cm_norm, interpolation='nearest', cmap='Blues', vmin=0, vmax=1,
                    )
                    cbar = plt.colorbar(im, ax=ax_cm, fraction=0.046, pad=0.04)
                    cbar.ax.tick_params(colors='#aaaaaa', labelsize=7)

                    ax_cm.set(
                        xticks=range(n), yticks=range(n),
                        xticklabels=display_labels,
                        yticklabels=display_labels,
                        ylabel='True label', xlabel='Predicted label',
                    )
                    ax_cm.set_title(
                        'Confusion matrix — row-normalized (diagonal = recall)',
                        fontsize=9, pad=6,
                    )
                    plt.setp(
                        ax_cm.get_xticklabels(),
                        rotation=40, ha='right', rotation_mode='anchor', fontsize=8,
                    )
                    plt.setp(ax_cm.get_yticklabels(), fontsize=8)

                    thresh = 0.5
                    for i in range(n):
                        for j in range(n):
                            val = cm_norm[i, j]
                            ax_cm.text(
                                j, i, f'{val:.2f}',
                                ha='center', va='center', fontsize=8,
                                color='white' if val > thresh else '#333333',
                                fontweight='bold' if i == j else 'normal',
                            )

                # ── Bottom: metrics table ─────────────────────────────────────
                ax_tbl.axis('off')
                col_labels = ['Class', 'Precision', 'Recall', 'F1', 'Support']
                row_data:   list[list[str]]              = []
                row_colors: list[list[str]]              = []

                for cls_key in sorted(class_rows, key=lambda k: (
                    int(k) if k.isdigit() else 0
                )):
                    metrics = class_rows[cls_key]
                    display_name = label_map.get(cls_key, cls_key)
                    star = '★ ' if cls_key in (target_a, target_b) else '   '
                    prec = float(metrics.get('precision', 0.0))
                    rec  = float(metrics.get('recall',    0.0))
                    f1   = float(metrics.get('f1-score',  0.0))
                    sup  = int(metrics.get('support', 0))

                    row_data.append([
                        f'{star}{display_name}',
                        f'{prec:.3f}', f'{rec:.3f}', f'{f1:.3f}', f'{sup:,}',
                    ])

                    if f1 >= thr_high:
                        f1_cell = '#1a4a1a'   # dark green
                    elif f1 >= thr_low:
                        f1_cell = '#4a3a10'   # dark amber
                    else:
                        f1_cell = '#4a1a1a'   # dark red

                    row_colors.append([
                        '#252525' if cls_key in (target_a, target_b) else '#1e1e1e',
                        '#1e1e1e', '#1e1e1e', f1_cell, '#1e1e1e',
                    ])

                # Macro avg + weighted avg
                for avg_key in ('macro avg', 'weighted avg'):
                    if avg_key in report_data:
                        m = report_data[avg_key]
                        row_data.append([
                            avg_key.title(),
                            f'{float(m.get("precision",  0)):.3f}',
                            f'{float(m.get("recall",     0)):.3f}',
                            f'{float(m.get("f1-score",   0)):.3f}',
                            f'{int(m.get("support",      0)):,}',
                        ])
                        row_colors.append(['#282828'] * 5)

                # Overall accuracy row
                row_data.append(['Overall Accuracy', f'{oa:.3f}', '—', '—', '—'])
                row_colors.append(['#282828'] * 5)

                tbl = ax_tbl.table(
                    cellText=row_data,
                    colLabels=col_labels,
                    cellColours=row_colors,
                    loc='center',
                    cellLoc='center',
                )
                tbl.auto_set_font_size(False)
                tbl.set_fontsize(8)
                tbl.scale(1, 1.45)

                for j in range(len(col_labels)):
                    cell = tbl[0, j]
                    cell.set_facecolor('#2a2a2a')
                    cell.set_text_props(color='#cccccc', fontweight='bold')

                for (row_idx, col_idx), cell in tbl.get_celld().items():
                    cell.set_edgecolor('#444444')
                    if row_idx > 0:
                        cell.set_text_props(color='#dddddd')

                # Legend for F1 color coding
                legend_txt = (
                    f'F1 color: ≥{thr_high:.0%} green  ·  '
                    f'≥{thr_low:.0%} amber  ·  <{thr_low:.0%} red   '
                    f'·  ★ = target class'
                )
                fig.text(0.5, 0.01, legend_txt, ha='center', fontsize=7,
                         color='#888888')

                fig.suptitle(
                    f'Classification Report  ·  OA = {oa:.1%}  ·  '
                    f'F1({label_map.get(target_a, target_a)}) = {f1_a:.3f}  ·  '
                    f'F1({label_map.get(target_b, target_b)}) = {f1_b:.3f}',
                    fontsize=9, y=0.995,
                )
                fig.tight_layout(rect=[0, 0.03, 1, 0.99])

                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi,
                            facecolor='#161616')
                buf.seek(0)
                arr = np.frombuffer(buf.read(), dtype=np.uint8)
                buf.close()
                plt.close(fig)

            report_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if report_img is None:
                raise ValueError('imdecode returned None')

        except Exception as e:
            send_notification(f'Classification Report: render error: {e}',
                              level='error', notif_id=_NOTIF)
            return {}

        send_notification(
            f'Classification Report: OA={oa:.1%}  '
            f'F1({target_a})={f1_a:.3f}  F1({target_b})={f1_b:.3f}',
            progress=1.0, notif_id=_NOTIF,
        )

        return {
            'report':  report_img,
            'f1_main': f1_a,
            'f1_b':    f1_b,
            'oa':      oa,
        }
