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
    label='Barefoot Print Forensics',
    category='analysis',
    icon='Activity',
    description=(
        'Forensic analysis of a BARE FOOT print on a deskewed crop. '
        'Computes pressure zones, foot length and width in mm, per-zone widths, '
        'Staheli Arch Index with its Cavus / Normal / Flat classification, '
        'medial-lateral asymmetry and pressure centroid.\n\n'
        'The Staheli index is the arch area divided by the non-heel area: it describes '
        'a plantar arch and is meaningless on a shoe sole. Use this on bare prints only.\n\n'
        'Connect geom_obb rotated + rotated_mask outputs, and px_per_mm from a calibration.'
    ),
    inputs=[
        {'id': 'image',      'color': 'image'},
        {'id': 'mask',       'color': 'mask'},
        {'id': 'px_per_mm',  'color': 'scalar', 'label': 'Px/mm'},
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

    @classmethod
    def _stand_upright(cls, vis, gray, binary):
        """Rotate the crop so the foot stands upright with the toes at the top.

        Returns the three arrays rotated consistently. Uses two invariants of a foot:
        it is longer than it is wide, and its widest line — the ball, at the metatarsal
        heads — lies in the toe half, never in the heel half. Comparing the two ends
        instead would be unreliable: with the toes attached, the toe end is the wider one.
        """
        def extents(b):
            ys, xs = np.where(b > 0)
            return (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))

        def rot(k):
            return (cv2.rotate(vis, k), cv2.rotate(gray, k), cv2.rotate(binary, k))

        ymi, yma, xmi, xma = extents(binary)
        if (xma - xmi) > (yma - ymi):
            vis, gray, binary = rot(cv2.ROTATE_90_CLOCKWISE)
            ymi, yma, xmi, xma = extents(binary)

        counts = np.count_nonzero(binary[ymi:yma + 1], axis=1)
        if counts.any() and int(np.argmax(counts)) > len(counts) / 2:
            vis, gray, binary = rot(cv2.ROTATE_180)
        return vis, gray, binary

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
        px_per_mm_raw    = inputs.get('px_per_mm')
        px_per_mm        = float(px_per_mm_raw) if px_per_mm_raw is not None and float(px_per_mm_raw) > 0 else 0.0
        has_calib        = px_per_mm > 0

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

        # Every zone split below runs along Y, so the foot has to stand upright in the
        # crop, toes at the top. geom_obb only guarantees the print is deskewed — a
        # diagonal print comes back lying on its side, and a print can arrive heel-first.
        # Two facts make this recoverable without asking the user: a foot is longer than
        # it is wide, and its heel end is wider than its toe end.
        vis_src, gray_img, binary = self._stand_upright(vis_src, gray_img, binary)
        ysp, xsp = np.where(binary > 0)
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
        if has_calib:
            metrics['foot_length_mm'] = round(fh / px_per_mm, 1)
            metrics['foot_width_mm']  = round(fw / px_per_mm, 1)

        # Ball width and heel width — the CBW and HBW of forensic podiatry, alongside
        # total foot length. They are computed unconditionally: Show Measurements only
        # decides whether the measuring lines are DRAWN. Gating the numbers on a display
        # option silently removed two of the four anthropometric variables.
        # CBW is the breadth at the metatarsal heads and HBW the breadth of the heel:
        # both are MAXIMUM breadths within their zone, so locate the zone by name and
        # scan it. Indexing zones by position measured across the toes in 4-zone mode.
        zone_names = [z[0] for z in zone_defs]
        widths = {}
        for key, zone_name in (('forefoot', 'Forefoot'), ('heel', 'Heel')):
            zi = zone_names.index(zone_name)
            y0, y1 = bounds[zi], bounds[zi + 1]
            band = binary[y0:y1, xmi:xma]
            if band.size == 0:
                continue
            counts = np.count_nonzero(band, axis=1)
            if not counts.any():
                continue
            best = int(np.argmax(counts))
            cols = np.where(band[best] > 0)[0]
            meas_y = y0 + best
            lx, rx = xmi + int(cols[0]), xmi + int(cols[-1])
            w_px = int(rx - lx)
            widths[key] = w_px
            metrics[key + '_width_px'] = w_px
            if has_calib:
                metrics[key + '_width_mm'] = round(w_px / px_per_mm, 1)
            if show_meas:
                cv2.line(ov, (lx, meas_y), (rx, meas_y), (255, 165, 0), max(1, fw // 200))
                fs2   = max(0.25, 0.38 * fw / 200)
                label = f'{w_px / px_per_mm:.1f}mm' if has_calib else f'{w_px}px'
                cv2.putText(ov, label, (rx + 4, meas_y),
                            cv2.FONT_HERSHEY_SIMPLEX, fs2, (255, 165, 0), 1, cv2.LINE_AA)
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
