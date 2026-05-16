import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _count_objects(mask):
    if mask is None or not isinstance(mask, np.ndarray):
        return 0
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

    unique_vals = np.unique(mask)
    if len(unique_vals) > 5:
        return int(len(unique_vals[unique_vals > 0]))

    _, labels = cv2.connectedComponents((mask > 0).astype(np.uint8))
    return int(max(0, labels.max()))


@vision_node(
    type_id='hema_hemogramme',
    label='Hemogramme',
    category='hematology',
    icon='FileText',
    description=(
        'Generates a standardized hematology report based on cell segmentation.\n\n'
        'Inputs:\n'
        '1. Erythrocytes (RBC)\n'
        '2. Neutrophils\n'
        '3. Lymphocytes\n'
        '4. Monocytes\n'
        '5. Platelets\n\n'
        'Calculates counts, relative percentages (WBC formula), and provides biological interpretation.'
    ),
    inputs=[
        {'id': 'mask_rbc', 'label': 'Erythrocytes (RBC)', 'color': 'mask'},
        {'id': 'mask_neu', 'label': 'Neutrophils',        'color': 'mask'},
        {'id': 'mask_lym', 'label': 'Lymphocytes',       'color': 'mask'},
        {'id': 'mask_mon', 'label': 'Monocytes',         'color': 'mask'},
        {'id': 'mask_plt', 'label': 'Platelets',         'color': 'mask'},
        {'id': 'calibration', 'label': 'Calibration (px/um)', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'report', 'label': 'Report Text', 'color': 'string'},
        {'id': 'main',   'label': 'Summary Table', 'color': 'image'},
        {'id': 'stats',  'label': 'Stats Dict', 'color': 'dict'},
        {'id': 'rbc_count', 'label': 'RBC', 'color': 'scalar'},
        {'id': 'wbc_count', 'label': 'WBC', 'color': 'scalar'},
        {'id': 'plt_count', 'label': 'PLT', 'color': 'scalar'},
    ],
    params=[
        {'id': 'patient_id', 'label': 'Patient ID', 'type': 'string', 'default': 'ANON-B-01'},
        {'id': 'unit_name',  'label': 'Unit Name',  'type': 'string', 'default': 'Apex Lab'},
    ],
)
class HemogrammeNode(NodeProcessor):
    def process(self, inputs, params):
        # 1. Gather counts
        rbc_count = _count_objects(inputs.get('mask_rbc'))
        neu_count = _count_objects(inputs.get('mask_neu'))
        lym_count = _count_objects(inputs.get('mask_lym'))
        mon_count = _count_objects(inputs.get('mask_mon'))
        plt_count = _count_objects(inputs.get('mask_plt'))
        
        wbc_total = neu_count + lym_count + mon_count
        
        calib = inputs.get('calibration', 1.0)
        patient = params.get('patient_id', 'Unknown')
        unit = params.get('unit_name', 'Apex Lab')

        # 2. Format WBC Differential
        if wbc_total > 0:
            neu_p = (neu_count / wbc_total) * 100
            lym_p = (lym_count / wbc_total) * 100
            mon_p = (mon_count / wbc_total) * 100
        else:
            neu_p = lym_p = mon_p = 0.0

        # 3. Generate Report Text
        report = (
            f"HEMOGRAMME REPORT - {unit}\n"
            f"-----------------------------------\n"
            f"Patient ID: {patient}\n"
            f"Scale: {calib:.4f} px/um\n"
            f"-----------------------------------\n\n"
            f"CELL COUNTS (Field Analysis):\n"
            f"- Erythrocytes (RBC): {rbc_count}\n"
            f"- Platelets (PLT):    {plt_count}\n"
            f"- Total Leucocytes:   {wbc_total}\n\n"
            f"WBC DIFFERENTIAL FORMULA:\n"
            f"- Neutrophils:  {neu_count} ({neu_p:.1f}%)\n"
            f"- Lymphocytes:  {lym_count} ({lym_p:.1f}%)\n"
            f"- Monocytes:    {mon_count} ({mon_p:.1f}%)\n\n"
        )
        
        # 4. Interpretation Logic (Heuristic)
        comment = "INTERPRETATION:\n"
        if wbc_total == 0:
            comment += "No white blood cells detected in this field."
        else:
            if neu_p > 75:
                comment += "Suspected neutrophilia (bacterial reaction?).\n"
            elif lym_p > 45:
                comment += "Suspected lymphocytosis (viral reaction?).\n"
            elif mon_p > 15:
                comment += "Suspected monocytosis (chronic inflammation?).\n"
            else:
                comment += "WBC distribution within typical ranges for this sample.\n"
        
        if rbc_count < 20:
             comment += "Low RBC density noted in this field."

        report += comment

        # 5. Create Summary Image (Table)
        img = np.full((400, 500, 3), 250, dtype=np.uint8)
        
        # Title bar
        cv2.rectangle(img, (0, 0), (500, 45), (60, 40, 40), -1)
        cv2.putText(img, f"REPORT: {patient}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        y = 80
        def draw_row(label, val, unit_str="", color=(40, 40, 40)):
            nonlocal y
            cv2.putText(img, label, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
            cv2.putText(img, f"{val} {unit_str}", (220, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.line(img, (20, y+8), (480, y+8), (230, 230, 230), 1)
            y += 35

        draw_row("RBC Count", rbc_count)
        draw_row("PLT Count", plt_count)
        draw_row("WBC Total", wbc_total, "", (180, 0, 0))
        y += 10
        draw_row("  Neutrophils", f"{neu_p:.1f}", "%")
        draw_row("  Lymphocytes", f"{lym_p:.1f}", "%")
        draw_row("  Monocytes",   f"{mon_p:.1f}", "%")
        
        # Comment box
        cv2.rectangle(img, (15, y), (485, 385), (245, 245, 245), -1)
        cv2.rectangle(img, (15, y), (485, 385), (200, 200, 200), 1)
        
        # Split comment into lines
        lines = comment.split('\n')
        for i, line in enumerate(lines):
            if i > 5: break
            cv2.putText(img, line, (25, y + 25 + i*20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)

        return {
            'report': report,
            'main': img,
            'rbc_count': rbc_count,
            'wbc_count': wbc_total,
            'plt_count': plt_count,
            'stats': {
                'rbc': rbc_count,
                'plt': plt_count,
                'wbc': wbc_total,
                'neu': f"{neu_p:.1f}",
                'lym': f"{lym_p:.1f}",
                'mon': f"{mon_p:.1f}"
            }
        }
