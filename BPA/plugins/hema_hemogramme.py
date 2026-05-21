import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _parse_stats(value) -> tuple[int, float, float, float]:
    """Extract (count, mean_area, mean_diam, cv_diam) from an Object Extractor stats dict."""
    if value is None:
        return 0, 0.0, 0.0, 0.0
    if isinstance(value, dict):
        count     = int(value.get('count', len(value.get('objects', []))))
        mean_area = float(value.get('mean_area', 0.0))
        mean_diam = float(value.get('mean_diam', 0.0))
        cv_diam   = float(value.get('cv_diam',   0.0))
        return count, mean_area, mean_diam, cv_diam
    # Fallback: raw scalar
    try:
        return int(value), 0.0, 0.0, 0.0
    except (TypeError, ValueError):
        return 0, 0.0, 0.0, 0.0


@vision_node(
    type_id='hema_hemogramme',
    label='Hemogramme',
    category='hematology',
    icon='FileText',
    description=(
        'Generates a standardized hematology report.\n\n'
        'Connect the "Stats" output of an Object Extractor to each input.\n'
        'Scalar counts are also accepted as fallback.\n\n'
        'RBC stats include size metrics: mean diameter (µm), anisocytosis CV%.\n'
        'WBC differential gives neutrophil/lymphocyte/monocyte percentages.'
    ),
    inputs=[
        {'id': 'rbc',  'label': 'RBC Stats',          'color': 'dict'},
        {'id': 'neu',  'label': 'Neutrophils Stats',   'color': 'dict'},
        {'id': 'lym',  'label': 'Lymphocytes Stats',   'color': 'dict'},
        {'id': 'mon',  'label': 'Monocytes Stats',     'color': 'dict'},
        {'id': 'plt',  'label': 'Platelets Stats',     'color': 'dict'},
        {'id': 'calibration', 'label': 'Calibration (px/µm)', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'report',    'label': 'Report Text',   'color': 'string'},
        {'id': 'main',      'label': 'Summary Table', 'color': 'image'},
        {'id': 'stats',     'label': 'Stats Dict',    'color': 'dict'},
        {'id': 'rbc_count', 'label': 'RBC',           'color': 'scalar'},
        {'id': 'wbc_count', 'label': 'WBC',           'color': 'scalar'},
        {'id': 'plt_count', 'label': 'PLT',           'color': 'scalar'},
    ],
    params=[
        {'id': 'patient_id', 'label': 'Patient ID', 'type': 'string', 'default': 'ANON-B-01'},
        {'id': 'unit_name',  'label': 'Unit Name',  'type': 'string', 'default': 'Apex Lab'},
    ],
)
class HemogrammeNode(NodeProcessor):
    def process(self, inputs, params):
        rbc_count, rbc_mean_area, rbc_mean_diam, rbc_cv = _parse_stats(inputs.get('rbc'))
        neu_count, *_ = _parse_stats(inputs.get('neu'))
        lym_count, *_ = _parse_stats(inputs.get('lym'))
        mon_count, *_ = _parse_stats(inputs.get('mon'))
        plt_count, *_ = _parse_stats(inputs.get('plt'))

        wbc_total = neu_count + lym_count + mon_count

        calib   = float(inputs.get('calibration') or 1.0)
        patient = params.get('patient_id', 'Unknown')
        unit    = params.get('unit_name',  'Apex Lab')

        # Convert size px → µm (calib = px/µm)
        rbc_diam_um = rbc_mean_diam / calib if calib > 0 else 0.0
        rbc_area_um = rbc_mean_area / (calib ** 2) if calib > 0 else 0.0

        if wbc_total > 0:
            neu_p = (neu_count / wbc_total) * 100
            lym_p = (lym_count / wbc_total) * 100
            mon_p = (mon_count / wbc_total) * 100
        else:
            neu_p = lym_p = mon_p = 0.0

        # ── Report text ────────────────────────────────────────────────────
        report = (
            f"HEMOGRAMME REPORT - {unit}\n"
            f"-----------------------------------\n"
            f"Patient ID: {patient}\n"
            f"Scale: {calib:.4f} px/µm\n"
            f"-----------------------------------\n\n"
            f"CELL COUNTS (Field Analysis):\n"
            f"- Erythrocytes (RBC): {rbc_count}\n"
            f"- Platelets (PLT):    {plt_count}\n"
            f"- Total Leucocytes:   {wbc_total}\n\n"
            f"RBC MORPHOMETRY:\n"
            f"- Mean diameter:  {rbc_diam_um:.2f} µm  ({rbc_mean_diam:.1f} px)\n"
            f"- Mean area:      {rbc_area_um:.2f} µm²\n"
            f"- Anisocytosis:   {rbc_cv:.1f}% CV\n\n"
            f"WBC DIFFERENTIAL FORMULA:\n"
            f"- Neutrophils:  {neu_count} ({neu_p:.1f}%)\n"
            f"- Lymphocytes:  {lym_count} ({lym_p:.1f}%)\n"
            f"- Monocytes:    {mon_count} ({mon_p:.1f}%)\n\n"
        )

        # ── Interpretation ─────────────────────────────────────────────────
        comment = "INTERPRETATION:\n"
        if wbc_total == 0:
            comment += "No WBC detected in this field.\n"
        else:
            if neu_p > 75:
                comment += "Suspected neutrophilia (bacterial reaction?).\n"
            elif lym_p > 45:
                comment += "Suspected lymphocytosis (viral reaction?).\n"
            elif mon_p > 15:
                comment += "Suspected monocytosis (chronic inflammation?).\n"
            else:
                comment += "WBC distribution within typical ranges.\n"

        if rbc_count < 20:
            comment += "Low RBC density in this field.\n"
        if rbc_diam_um > 0:
            if rbc_diam_um < 5.5:
                comment += f"Microcytosis suspected (mean Ø {rbc_diam_um:.1f} µm < 5.5).\n"
            elif rbc_diam_um > 8.5:
                comment += f"Macrocytosis suspected (mean Ø {rbc_diam_um:.1f} µm > 8.5).\n"
        if rbc_cv > 15:
            comment += f"Anisocytosis detected (CV {rbc_cv:.1f}% > 15%).\n"

        report += comment

        # ── Summary image ──────────────────────────────────────────────────
        img = np.full((480, 520, 3), 250, dtype=np.uint8)

        cv2.rectangle(img, (0, 0), (520, 45), (60, 40, 40), -1)
        cv2.putText(img, f"REPORT: {patient}", (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        y = 75

        def row(label, val, unit_str='', color=(40, 40, 40)):
            nonlocal y
            cv2.putText(img, label, (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100), 1)
            cv2.putText(img, f"{val}  {unit_str}", (230, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            cv2.line(img, (20, y + 7), (500, y + 7), (225, 225, 225), 1)
            y += 28

        row("RBC Count",       rbc_count)
        row("PLT Count",       plt_count)
        row("WBC Total",       wbc_total, color=(180, 0, 0))
        y += 4
        row("  Neutrophils",   f"{neu_p:.1f}", "%")
        row("  Lymphocytes",   f"{lym_p:.1f}", "%")
        row("  Monocytes",     f"{mon_p:.1f}", "%")
        y += 8
        row("RBC Mean Ø",      f"{rbc_diam_um:.2f}", "µm", (0, 100, 160))
        row("RBC Mean Area",   f"{rbc_area_um:.2f}", "µm²", (0, 100, 160))
        row("Anisocytosis CV", f"{rbc_cv:.1f}", "%",
            (200, 80, 0) if rbc_cv > 15 else (0, 100, 160))

        cv2.rectangle(img, (15, y), (505, 470), (245, 245, 245), -1)
        cv2.rectangle(img, (15, y), (505, 470), (200, 200, 200),  1)
        for i, line in enumerate(comment.split('\n')):
            if i > 6:
                break
            cv2.putText(img, line, (25, y + 22 + i * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (80, 80, 80), 1)

        return {
            'report':    report,
            'main':      img,
            'rbc_count': int(rbc_count),
            'wbc_count': int(wbc_total),
            'plt_count': int(plt_count),
            'stats': {
                'rbc': rbc_count, 'plt': plt_count, 'wbc': wbc_total,
                'neu': f"{neu_p:.1f}", 'lym': f"{lym_p:.1f}", 'mon': f"{mon_p:.1f}",
                'rbc_diam_um': round(rbc_diam_um, 2),
                'rbc_area_um': round(rbc_area_um, 2),
                'rbc_cv':      round(rbc_cv,      1),
            },
        }
