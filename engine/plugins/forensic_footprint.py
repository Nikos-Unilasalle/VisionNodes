import cv2
import numpy as np
import base64
from registry import vision_node, NodeProcessor

_ZONES_4 = [
    ('Toes',     (80,  200, 120)),
    ('Forefoot', (80,  160, 240)),
    ('Arch',     (240, 160,  60)),
    ('Heel',     (240,  80,  60)),
]
_ZONES_3 = [
    ('Forefoot', (80,  200, 120)),
    ('Arch',     (80,  160, 240)),
    ('Heel',     (240,  80,  60)),
]


@vision_node(
    type_id='forensic_footprint',
    label='Footprint Forensics',
    category='analysis',
    icon='Activity',
    description=(
        'Forensic footwear analysis on a deskewed crop. '
        'Computes pressure zones, Staheli Arch Index, medial/lateral asymmetry, '
        'and pressure centroid. Connect geom_obb rotated + rotated_mask outputs.'
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask',  'color': 'mask'},
    ],
    outputs=[
        {'id': 'main',      'color': 'image'},
        {'id': 'report',    'color': 'dict'},
        {'id': 'staheli',   'color': 'scalar'},
        {'id': 'asymmetry', 'color': 'scalar'},
    ],
    params=[
        {'id': 'n_zones',    'label': 'Zones',            'type': 'enum',  'default': 0,
         'options': ['4 zones (Toes/FF/Arch/Heel)', '3 zones (FF/Arch/Heel)']},
        {'id': 'pressure_weights', 'label': 'Pressure Weights', 'type': 'bool',  'default': True},
        {'id': 'show_measurements','label': 'Width Lines',      'type': 'bool',  'default': True},
        {'id': 'alpha',      'label': 'Overlay Alpha',    'type': 'float', 'default': 0.55,
         'min': 0.0, 'max': 1.0},
    ],
    colorable=True,
)
class ForensicFootprintNode(NodeProcessor):
    def __init__(self):
        self._frame_count = 0
        self._last_preview = None

    def _encode_preview(self, img):
        try:
            h, w = img.shape[:2]
            pw = min(w, 480)
            ph = int(pw * h / w)
            pimg = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 75])
            self._last_preview = base64.b64encode(bytes(buf)).decode('utf-8')
        except Exception:
            pass

    def process(self, inputs, params):
        image = inputs.get('image')
        mask  = inputs.get('mask')

        if image is None:
            return {}

        n_zones_idx      = int(params.get('n_zones', 0))
        use_pressure     = str(params.get('pressure_weights', True)).lower() not in ('false', '0', 'no')
        show_meas        = str(params.get('show_measurements', True)).lower() not in ('false', '0', 'no')
        alpha            = float(params.get('alpha', 0.55))

        zone_defs = _ZONES_4 if n_zones_idx == 0 else _ZONES_3
        n = len(zone_defs)

        # Normalize source to BGR
        if len(image.shape) == 2:
            vis_src = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            vis_src = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        else:
            vis_src = image.copy()

        gray_img = cv2.cvtColor(vis_src, cv2.COLOR_BGR2GRAY)

        # Binary mask
        if mask is not None:
            mg = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(mg, 127, 255, cv2.THRESH_BINARY)
        else:
            _, binary = cv2.threshold(gray_img, 1, 255, cv2.THRESH_BINARY)

        ysp, xsp = np.where(binary > 0)
        if len(xsp) == 0:
            self._encode_preview(vis_src)
            return {'main': vis_src, 'report': {}, 'staheli': 0.0, 'asymmetry': 0.0,
                    'main_preview': self._last_preview}

        ymi, yma = int(np.min(ysp)), int(np.max(ysp))
        xmi, xma = int(np.min(xsp)), int(np.max(xsp))
        fh = max(1, yma - ymi)
        fw = max(1, xma - xmi)

        # Equal zone splits along Y
        bounds = [ymi + int(i * fh / n) for i in range(n + 1)]
        bounds[-1] = yma

        ov = vis_src.copy()
        metrics = {}
        zone_areas  = []
        total_area  = max(1, int(np.sum(binary > 0)))

        for i, (name, col) in enumerate(zone_defs):
            ys, ye = bounds[i], bounds[i + 1]
            zm = binary[ys:ye, xmi:xma]
            active = zm > 0
            area = int(np.sum(active))
            zone_areas.append(area)
            pct = round(100.0 * area / total_area, 1)
            metrics[name.lower() + '_area_pct'] = pct

            # Color overlay
            ov[ys:ye, xmi:xma][active] = col

            # Zone label
            fs = max(0.3, 0.55 * fw / 200)
            th = max(1, fw // 150)
            cv2.putText(ov, f'{name}: {pct}%', (xmi + 6, (ys + ye) // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), th, cv2.LINE_AA)
            if i < n - 1:
                cv2.line(ov, (xmi, ye), (xma, ye), (200, 200, 200), 1)

        # Staheli Arch Index
        if n == 4:
            arch_a     = zone_areas[2]
            non_heel   = max(1, zone_areas[1] + zone_areas[2])
        else:
            arch_a     = zone_areas[1]
            non_heel   = max(1, zone_areas[0] + zone_areas[1])
        staheli = round(arch_a / non_heel, 3)

        if staheli < 0.21:
            arch_type = 'Cavus'
        elif staheli < 0.26:
            arch_type = 'Normal'
        else:
            arch_type = 'Flat'
        metrics['staheli_arch_index'] = staheli
        metrics['arch_type']          = arch_type

        # Asymmetry: medial vs lateral halves
        mid_x = (xmi + xma) // 2
        la   = int(np.sum(binary[:, xmi:mid_x] > 0))
        ra   = int(np.sum(binary[:, mid_x:xma] > 0))
        asym = round(abs(la - ra) / max(la + ra, 1), 3)
        metrics['asymmetry_score'] = asym

        # Centroid (pressure-weighted if depth map available)
        if use_pressure:
            w_map = gray_img.astype(np.float32)
            w_map[binary == 0] = 0
            total_w = float(np.sum(w_map))
            if total_w > 0:
                cxc = int(np.sum(np.arange(w_map.shape[1]) * np.sum(w_map, axis=0)) / total_w)
                cyc = int(np.sum(np.arange(w_map.shape[0]) * np.sum(w_map, axis=1)) / total_w)
            else:
                cxc, cyc = int(np.mean(xsp)), int(np.mean(ysp))
        else:
            cxc, cyc = int(np.mean(xsp)), int(np.mean(ysp))

        metrics['centroid_x_pct'] = round(100 * (cxc - xmi) / fw, 1)
        metrics['centroid_y_pct'] = round(100 * (cyc - ymi) / fh, 1)
        metrics['total_area_px']  = total_area

        # Width measurement lines at forefoot and heel levels
        if show_meas:
            fore_y = (bounds[0] + bounds[1]) // 2
            heel_y = (bounds[-2] + bounds[-1]) // 2
            widths = {}
            for key, meas_y in [('forefoot', fore_y), ('heel', heel_y)]:
                row  = binary[meas_y, xmi:xma]
                cols = np.where(row > 0)[0]
                if len(cols) > 1:
                    lx, rx = xmi + cols[0], xmi + cols[-1]
                    cv2.line(ov, (lx, meas_y), (rx, meas_y), (255, 165, 0), max(1, fw // 200))
                    w_px = int(rx - lx)
                    fs2  = max(0.25, 0.38 * fw / 200)
                    cv2.putText(ov, f'{w_px}px', (rx + 4, meas_y),
                                cv2.FONT_HERSHEY_SIMPLEX, fs2, (255, 165, 0), 1, cv2.LINE_AA)
                    widths[key] = w_px
            if widths.get('forefoot', 0) > 0:
                metrics['heel_forefoot_ratio'] = round(widths.get('heel', 0) / widths['forefoot'], 3)

        # Axis of symmetry
        cv2.line(ov, (mid_x, ymi), (mid_x, yma), (0, 220, 220), max(1, fw // 120))

        # Pressure centroid dot
        rd = max(5, fw // 50)
        cv2.circle(ov, (cxc, cyc), rd, (0, 255, 255), -1)
        cv2.circle(ov, (cxc, cyc), rd, (0, 0, 0), 2)

        # Annotation: Staheli + asymmetry
        fs3 = max(0.3, 0.45 * fw / 200)
        th3 = max(1, fw // 180)
        line_h = int(18 * fw / 200)
        cv2.putText(ov, f'Staheli {staheli} — {arch_type}',
                    (xmi + 5, yma - 8), cv2.FONT_HERSHEY_SIMPLEX,
                    fs3, (255, 255, 100), th3, cv2.LINE_AA)
        cv2.putText(ov, f'Asym {asym}',
                    (xmi + 5, yma - 8 - line_h), cv2.FONT_HERSHEY_SIMPLEX,
                    fs3, (0, 220, 220), th3, cv2.LINE_AA)

        final = cv2.addWeighted(ov, alpha, vis_src, 1.0 - alpha, 0)

        self._frame_count += 1
        if self._frame_count % 3 == 1:
            self._encode_preview(final)

        return {
            'main':      final,
            'report':    metrics,
            'staheli':   float(staheli),
            'asymmetry': float(asym),
            'main_preview': self._last_preview,
        }
