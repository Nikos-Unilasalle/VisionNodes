"""
BPA Batch Evaluator — runs the full BPA pipeline on every sample in the Attinger dataset.

Pipeline per sample:
  1. Parse .txt metadata (origin, target coords, blood properties)
  2. Load .jpg at configurable scale
  3. Detect stains (LAB-A + HSV-V segmentation, ellipse fitting)
  4. Reconstruct 3D origin via stringing (least-squares ray intersection)
  5. Compute Euclidean error vs ground-truth origin

Output: pandas DataFrame with one row per sample, ready for VNStudio
DataFrame/ML nodes (scatter plot, histogram, CSV export).

Accuracy note:
  The Attinger dataset has two series:
    HP_19–HP_34: origin ~190 cm from target → stains nearly circular (impact ~80–90°).
                 Ellipse aspect ratio is unreliable at low resolution.
                 Recommend scale ≥ 0.3 for these samples, but processing is slow.
    HP_50–HP_63: origin ~60 cm from target → impact ~45–65°.
                 Reliable detection and reconstruction at scale 0.2–0.3.
"""

from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import math
import re
import os

# ---------------------------------------------------------------------------
# Inline detection + reconstruction (mirrors bpa_stain_detector + bpa_origin_reconstructor)
# to avoid inter-plugin imports

_FULL_RES_PX_PER_CM = 236.2  # 600 dpi


def _parse_metadata(txt_path: str) -> dict:
    t = open(txt_path, errors='replace').read()

    def _f(pat):
        m = re.search(pat, t, re.I)
        return float(m.group(1)) if m else None

    d = {
        'x_o': _f(r'x_o\s*=\s*([\d.]+)'),
        'y_o': _f(r'y_o\s*=\s*([\d.]+)'),
        'z_o': _f(r'z_o\s*=\s*([\d.]+)'),
        'x_t': _f(r'x_[tp]\s*=\s*([\d.]+)'),
        'y_t': _f(r'y_[tp]\s*=\s*([\d.]+)'),
        'z_t': _f(r'z_[tp]\s*=\s*([\d.]+)'),
        'dowel_angle': _f(r'Dowel Angle\s*:\s*([\d.]+)'),
        'hematocrit':  _f(r'Hematocrit\s*=\s*([\d.]+)'),
        'blood_volume':_f(r'Blood Volume\s*=\s*([\d.]+)'),
        'room_temp':   _f(r'Room Temp\s*=\s*([\d.]+)'),
        'room_humidity':_f(r'Room Humidity\s*=\s*([\d.]+)'),
        'double_origin': bool(re.search(r'double spatter|double origin', t, re.I)),
    }
    # Double-origin: second x_o value
    m2 = re.search(r'x_o\s*=\s*[\d.]+\s*cm,\s*and\s*([\d.]+)', t, re.I)
    d['x_o2'] = float(m2.group(1)) if m2 else None
    return d


def _detect_stains(img_bgr, px_per_cm, a_thresh=5, val_max=230, blur_r=3,
                   min_mm=1.5, max_mm=30.0, min_aspect=0.1, filter_outliers=True):
    blur_k = blur_r | 1
    blurred = cv2.GaussianBlur(img_bgr, (blur_k, blur_k), 0)

    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    a_ch = lab[:, :, 1].astype(np.int16) - 128
    hsv  = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    mask = cv2.bitwise_and(
        (a_ch > a_thresh).astype(np.uint8) * 255,
        (hsv[:, :, 2] < val_max).astype(np.uint8) * 255,
    )
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)

    px_per_mm   = px_per_cm / 10.0
    min_area_px = max(5, int(math.pi * (min_mm * px_per_mm / 2) ** 2))
    max_area_px = int(math.pi * (max_mm * px_per_mm / 2) ** 2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    stains = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px or area > max_area_px or len(cnt) < 5:
            continue
        (cx, cy), (ax1, ax2), rot = cv2.fitEllipse(cnt)
        minor, major = min(ax1, ax2), max(ax1, ax2)
        if major < 3:
            continue
        asp = minor / major
        if asp < min_aspect:
            continue
        stains.append({
            'cx': float(cx), 'cy': float(cy),
            'rot_deg': float(rot),
            'impact_angle_deg': math.degrees(math.asin(min(1.0, asp))),
            'aspect': float(asp),
        })

    if filter_outliers and len(stains) >= 6:
        cx_arr = np.array([s['cx'] for s in stains])
        cy_arr = np.array([s['cy'] for s in stains])
        dists  = np.sqrt((cx_arr - np.median(cx_arr))**2 + (cy_arr - np.median(cy_arr))**2)
        thresh = np.median(dists) + 2.5 * dists.std()
        stains = [s for s, d in zip(stains, dists) if d <= thresh]

    return stains


def _reconstruct_origin(stains, px_per_cm, img_h_px, x_t, y_t, z_t,
                        residual_cutoff_cm=30.0, min_stains=3):
    if len(stains) < min_stains:
        return None, None

    height_cm = img_h_px / px_per_cm
    I3 = np.eye(3)

    def world_pt(s):
        u_cm = s['cx'] / px_per_cm
        v_cm = s['cy'] / px_per_cm
        return np.array([float(x_t), float(y_t) + u_cm, float(z_t) + (height_cm - v_cm)])

    world_pts = [world_pt(s) for s in stains]
    centroid_YZ = np.array(world_pts)[:, 1:].mean(axis=0)

    def build_system(pts, stn):
        sA, sAP = np.zeros((3, 3)), np.zeros(3)
        for P, s in zip(pts, stn):
            rot = np.radians(s['rot_deg'])
            alp = np.radians(s['impact_angle_deg'])
            dY, dZ = np.cos(rot), -np.sin(rot)
            to_c = centroid_YZ - P[1:]
            if dY * to_c[0] + dZ * to_c[1] < 0:
                dY, dZ = -dY, -dZ
            dX = np.tan(alp)
            d = np.array([dX, dY, dZ]); d /= np.linalg.norm(d)
            A = I3 - np.outer(d, d)
            sA += A; sAP += A @ P
        return sA, sAP

    # Pass 1: all stains
    try:
        origin = np.linalg.solve(*build_system(world_pts, stains))
    except np.linalg.LinAlgError:
        return None, None

    # Compute residuals (distance from origin to each ray)
    residuals = []
    for P, s in zip(world_pts, stains):
        rot = np.radians(s['rot_deg'])
        alp = np.radians(s['impact_angle_deg'])
        dY, dZ = np.cos(rot), -np.sin(rot)
        to_c = centroid_YZ - P[1:]
        if dY * to_c[0] + dZ * to_c[1] < 0:
            dY, dZ = -dY, -dZ
        dX = np.tan(alp)
        d = np.array([dX, dY, dZ]); d /= np.linalg.norm(d)
        v = origin - P
        residuals.append(float(np.linalg.norm(v - np.dot(v, d) * d)))

    # Pass 2: remove outliers
    filtered  = [(P, s) for P, s, r in zip(world_pts, stains, residuals) if r <= residual_cutoff_cm]
    if len(filtered) >= min_stains:
        pts2, stn2 = zip(*filtered)
        try:
            origin = np.linalg.solve(*build_system(list(pts2), list(stn2)))
        except np.linalg.LinAlgError:
            pass
        n_used = len(filtered)
    else:
        n_used = len(stains)

    return origin, n_used


# ---------------------------------------------------------------------------

@vision_node(
    type_id='bpa_batch_evaluator',
    label='BPA Batch Evaluator',
    category='forensics',
    icon='BarChart3',
    description=(
        "Runs the full BPA pipeline (detection + 3D origin reconstruction) on all samples "
        "in an Attinger dataset folder. Outputs a pandas DataFrame with per-sample results "
        "for error analysis, visualisation, and CSV export.\n\n"
        "Accuracy note — two series in the dataset:\n"
        "• HP_19–HP_34: origin ~190 cm from target, stains nearly circular → need scale ≥ 0.3\n"
        "• HP_50–HP_63: origin ~60 cm from target, impact ~50–65° → reliable at scale 0.2–0.3"
    ),
    inputs=[],
    outputs=[
        {'id': 'results',  'color': 'data',   'label': 'Results DataFrame'},
        {'id': 'n_ok',     'color': 'scalar', 'label': 'Samples OK'},
        {'id': 'mean_err', 'color': 'scalar', 'label': 'Mean Error (cm)'},
        {'id': 'report',   'color': 'dict',   'label': 'Summary Dict'},
    ],
    params=[
        {'id': 'dataset_path', 'type': 'string', 'default': '',
         'label': 'Dataset Folder',
         'description': 'Path to the Attinger dataset root (contains HP_19/, HP_50/, …)'},
        {'id': 'load_scale', 'type': 'float', 'default': 0.2,
         'min': 0.05, 'max': 1.0, 'step': 0.05,
         'label': 'Load Scale',
         'description': 'Image downscale factor. 0.2 = 47 px/cm (good balance speed/accuracy).'},
        {'id': 'a_threshold', 'type': 'int', 'default': 5, 'min': 1, 'max': 60,
         'label': 'LAB-A Threshold'},
        {'id': 'val_max',  'type': 'int', 'default': 230, 'min': 80, 'max': 255,
         'label': 'Max HSV-V'},
        {'id': 'min_stain_mm', 'type': 'float', 'default': 1.5, 'min': 0.2, 'max': 20.0,
         'label': 'Min Stain Ø (mm)'},
        {'id': 'max_stain_mm', 'type': 'float', 'default': 30.0, 'min': 1.0, 'max': 100.0,
         'label': 'Max Stain Ø (mm)'},
        {'id': 'residual_cutoff', 'type': 'float', 'default': 30.0, 'min': 1.0, 'max': 200.0,
         'label': 'Outlier Cutoff (cm)'},
        {'id': 'trigger', 'type': 'trigger', 'default': False, 'label': 'Run Batch'},
    ],
)
class BPABatchEvaluatorNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_key = None
        self._cache_df  = None
        self._cache_summary = None

    def process(self, inputs, params):
        try:
            import pandas as pd
        except ImportError:
            send_notification('BPA Batch: pandas required — pip install pandas', level='error', notif_id='bpa_batch')
            return {'results': None, 'n_ok': 0, 'mean_err': None, 'report': None}

        dataset_path = params.get('dataset_path', '').strip()
        if not dataset_path or not os.path.isdir(dataset_path):
            return {'results': None, 'n_ok': 0, 'mean_err': None, 'report': None}

        scale         = float(params.get('load_scale', 0.2))
        a_thresh      = int(params.get('a_threshold', 5))
        val_max       = int(params.get('val_max', 230))
        min_mm        = float(params.get('min_stain_mm', 1.5))
        max_mm        = float(params.get('max_stain_mm', 30.0))
        res_cutoff    = float(params.get('residual_cutoff', 30.0))

        cache_key = (dataset_path, scale, a_thresh, val_max, min_mm, max_mm, res_cutoff)
        if cache_key == self._cache_key and self._cache_df is not None:
            return {'results': self._cache_df, 'n_ok': self._cache_summary['n_ok'],
                    'mean_err': self._cache_summary['mean_err'], 'report': self._cache_summary}

        samples = sorted(
            s for s in os.listdir(dataset_path)
            if s.startswith('HP_') and os.path.isdir(os.path.join(dataset_path, s))
        )

        send_notification(f'BPA Batch: {len(samples)} samples — scale={scale}…',
                          progress=0.0, notif_id='bpa_batch')

        rows = []
        for i, sid in enumerate(samples):
            send_notification(f'BPA Batch: {sid} ({i+1}/{len(samples)})',
                              progress=(i + 0.5) / len(samples), notif_id='bpa_batch')

            sample_dir = os.path.join(dataset_path, sid)
            txt_path   = os.path.join(sample_dir, f'{sid}.txt')
            img_path   = os.path.join(sample_dir, f'{sid}.jpg')

            if not os.path.isfile(txt_path) or not os.path.isfile(img_path):
                rows.append({'sample_id': sid, 'status': 'missing_file'})
                continue

            try:
                meta = _parse_metadata(txt_path)
            except Exception as e:
                rows.append({'sample_id': sid, 'status': f'parse_error:{e}'})
                continue

            # Load image at scale
            img = cv2.imread(img_path)
            if img is None:
                rows.append({'sample_id': sid, 'status': 'imread_failed'})
                continue

            new_w = max(1, int(img.shape[1] * scale))
            new_h = max(1, int(img.shape[0] * scale))
            img_s = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            px_per_cm = _FULL_RES_PX_PER_CM * scale

            # Detect stains
            stains = _detect_stains(img_s, px_per_cm,
                                    a_thresh=a_thresh, val_max=val_max,
                                    min_mm=min_mm, max_mm=max_mm)

            x_t = meta.get('x_t')
            y_t = meta.get('y_t')
            z_t = meta.get('z_t')
            x_o = meta.get('x_o')
            y_o = meta.get('y_o')
            z_o = meta.get('z_o')

            row = {
                'sample_id':     sid,
                'blood_volume':  meta.get('blood_volume'),
                'dowel_angle':   meta.get('dowel_angle'),
                'hematocrit':    meta.get('hematocrit'),
                'room_temp':     meta.get('room_temp'),
                'room_humidity': meta.get('room_humidity'),
                'double_origin': meta.get('double_origin', False),
                'gt_x': x_o, 'gt_y': y_o, 'gt_z': z_o,
                'target_x': x_t, 'target_y': y_t, 'target_z': z_t,
                'n_stains': len(stains),
                'mean_impact_deg': round(float(np.mean([s['impact_angle_deg'] for s in stains])), 2) if stains else None,
            }

            if None in (x_t, y_t, z_t) or len(stains) < 3:
                row.update({'est_x': None, 'est_y': None, 'est_z': None,
                            'error_cm': None, 'status': 'insufficient_stains'})
            else:
                origin, n_used = _reconstruct_origin(
                    stains, px_per_cm, new_h, x_t, y_t, z_t,
                    residual_cutoff_cm=res_cutoff)

                if origin is None:
                    row.update({'est_x': None, 'est_y': None, 'est_z': None,
                                'error_cm': None, 'status': 'reconstruction_failed'})
                else:
                    est_x, est_y, est_z = float(origin[0]), float(origin[1]), float(origin[2])
                    error_cm = None
                    if None not in (x_o, y_o, z_o):
                        error_cm = float(np.linalg.norm(origin - np.array([x_o, y_o, z_o])))
                    row.update({
                        'est_x': round(est_x, 1),
                        'est_y': round(est_y, 1),
                        'est_z': round(est_z, 1),
                        'n_used': n_used,
                        'error_cm': round(error_cm, 1) if error_cm is not None else None,
                        'status': 'ok',
                    })

            rows.append(row)

        df = pd.DataFrame(rows)

        ok   = df[df['status'] == 'ok']
        errs = ok['error_cm'].dropna()
        summary = {
            'n_total':      len(samples),
            'n_ok':         len(ok),
            'n_failed':     len(df) - len(ok),
            'mean_err':     round(float(errs.mean()), 1) if len(errs) else None,
            'median_err':   round(float(errs.median()), 1) if len(errs) else None,
            'std_err':      round(float(errs.std()), 1) if len(errs) > 1 else None,
            'min_err':      round(float(errs.min()), 1) if len(errs) else None,
            'max_err':      round(float(errs.max()), 1) if len(errs) else None,
            'scale_used':   scale,
        }

        send_notification(
            f'BPA Batch done — {len(ok)}/{len(samples)} OK  '
            f'mean_err={summary["mean_err"]} cm  median={summary["median_err"]} cm',
            progress=1.0, notif_id='bpa_batch'
        )

        self._cache_key     = cache_key
        self._cache_df      = df
        self._cache_summary = summary

        return {
            'results':  df,
            'n_ok':     summary['n_ok'],
            'mean_err': summary['mean_err'],
            'report':   summary,
        }
