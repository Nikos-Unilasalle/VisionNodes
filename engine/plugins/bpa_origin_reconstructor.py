from registry import vision_node, NodeProcessor, send_notification
import numpy as np

_NULL = {
    'est_x': None, 'est_y': None, 'est_z': None,
    'error_cm': None, 'n_used': 0, 'report': None,
}


def _pixel_to_world(cx, cy, px_per_cm, img_h_px, x_t, y_t, z_t):
    """Image pixel (u=cx, v=cy top-down) → room world coords on target face."""
    u_cm = cx / px_per_cm
    v_cm = cy / px_per_cm
    height_cm = img_h_px / px_per_cm
    return np.array([
        float(x_t),
        float(y_t) + u_cm,
        float(z_t) + (height_cm - v_cm),  # v=0 is top, Z increases up
    ])


def _reconstruct(stains, px_per_cm, img_h_px, x_t, y_t, z_t):
    """
    Stringing / nearest-point-to-rays least squares.
    Returns (origin_xyz, residuals_per_stain, directions).
    """
    if len(stains) < 3:
        return None, [], []

    world_pts = np.array([
        _pixel_to_world(s['cx'], s['cy'], px_per_cm, img_h_px, x_t, y_t, z_t)
        for s in stains
    ])

    # Centroid on target YZ plane for 180° direction disambiguation
    centroid_YZ = world_pts[:, 1:].mean(axis=0)

    I3 = np.eye(3)
    sum_A  = np.zeros((3, 3))
    sum_AP = np.zeros(3)
    dirs   = []

    for i, s in enumerate(stains):
        P   = world_pts[i]
        rot = np.radians(s['rot_deg'])
        alp = np.radians(s['impact_angle_deg'])

        # Major axis in image (u right, v down) → world (Y right, Z up)
        dY =  np.cos(rot)
        dZ = -np.sin(rot)

        # Disambiguate: direction must point toward centroid on target plane
        to_centroid = centroid_YZ - P[1:]
        if dY * to_centroid[0] + dZ * to_centroid[1] < 0:
            dY, dZ = -dY, -dZ

        # X component: sin(α) = dX/|d| with |d_YZ|=1 → dX = tan(α)
        dX = np.tan(alp)
        d  = np.array([dX, dY, dZ])
        d /= np.linalg.norm(d)
        dirs.append(d)

        A = I3 - np.outer(d, d)
        sum_A  += A
        sum_AP += A @ P

    try:
        origin = np.linalg.solve(sum_A, sum_AP)
    except np.linalg.LinAlgError:
        return None, [], []

    # Residual: distance from estimated origin to each ray
    residuals = []
    for i, (P, d) in enumerate(zip(world_pts, dirs)):
        v = origin - P
        perp = v - np.dot(v, d) * d
        residuals.append(float(np.linalg.norm(perp)))

    return origin, residuals, dirs


@vision_node(
    type_id='bpa_origin_reconstructor',
    label='BPA Origin Reconstructor',
    category='forensics',
    icon='Target',
    description=(
        "3D blood origin reconstruction via stringing / least-squares ray intersection. "
        "Each stain defines a 3D ray (impact angle + ellipse rotation). "
        "Finds the point closest to all rays. Compares with ground truth."
    ),
    inputs=[
        {'id': 'stains',     'color': 'dict',   'label': 'Stains Data'},
        {'id': 'px_per_cm',  'color': 'scalar', 'label': 'px/cm'},
        {'id': 'height_px',  'color': 'scalar', 'label': 'Image Height (px)'},
        {'id': 'x_t',        'color': 'scalar', 'label': 'Target X (cm)'},
        {'id': 'y_t',        'color': 'scalar', 'label': 'Target Y (cm)'},
        {'id': 'z_t',        'color': 'scalar', 'label': 'Target Z (cm)'},
        {'id': 'x_o',        'color': 'scalar', 'label': 'GT Origin X (cm)'},
        {'id': 'y_o',        'color': 'scalar', 'label': 'GT Origin Y (cm)'},
        {'id': 'z_o',        'color': 'scalar', 'label': 'GT Origin Z (cm)'},
    ],
    outputs=[
        {'id': 'est_x',    'color': 'scalar', 'label': 'Est. X (cm)'},
        {'id': 'est_y',    'color': 'scalar', 'label': 'Est. Y (cm)'},
        {'id': 'est_z',    'color': 'scalar', 'label': 'Est. Z (cm)'},
        {'id': 'error_cm', 'color': 'scalar', 'label': 'Error (cm)'},
        {'id': 'n_used',   'color': 'scalar', 'label': 'Stains Used'},
        {'id': 'report',   'color': 'dict',   'label': 'Report'},
    ],
    params=[
        {'id': 'residual_cutoff', 'label': 'Outlier Cutoff (cm)', 'type': 'float',
         'default': 30.0, 'min': 1.0, 'max': 200.0, 'step': 1.0},
        {'id': 'min_stains', 'label': 'Min Stains', 'type': 'int',
         'default': 5, 'min': 3, 'max': 50},
    ],
)
class BPAOriginReconstructorNode(NodeProcessor):
    def process(self, inputs, params):
        stains_data = inputs.get('stains')
        px_per_cm   = inputs.get('px_per_cm')
        height_px   = inputs.get('height_px')
        x_t = inputs.get('x_t')
        y_t = inputs.get('y_t')
        z_t = inputs.get('z_t')

        if not stains_data or not px_per_cm or not height_px:
            return _NULL
        if x_t is None or y_t is None or z_t is None:
            return _NULL

        stains = stains_data.get('stains', [])
        if len(stains) < int(params.get('min_stains', 5)):
            send_notification(f'BPA Recon: need ≥{params.get("min_stains",5)} stains, got {len(stains)}',
                              level='warning', notif_id='bpa_recon')
            return _NULL

        cutoff = float(params.get('residual_cutoff', 30.0))

        # Pass 1: full set
        origin, residuals, _ = _reconstruct(stains, px_per_cm, height_px, x_t, y_t, z_t)
        if origin is None:
            return _NULL

        # Pass 2: remove outliers above residual cutoff
        filtered = [s for s, r in zip(stains, residuals) if r <= cutoff]
        if len(filtered) >= int(params.get('min_stains', 5)):
            origin, residuals, _ = _reconstruct(filtered, px_per_cm, height_px, x_t, y_t, z_t)
            stains_used = filtered
        else:
            stains_used = stains

        if origin is None:
            return _NULL

        est_x, est_y, est_z = float(origin[0]), float(origin[1]), float(origin[2])

        # Ground truth comparison
        x_o = inputs.get('x_o')
        y_o = inputs.get('y_o')
        z_o = inputs.get('z_o')
        error_cm = None
        if x_o is not None and y_o is not None and z_o is not None:
            gt = np.array([float(x_o), float(y_o), float(z_o)])
            error_cm = float(np.linalg.norm(origin - gt))

        report = {
            'est_origin_cm':   [round(est_x,2), round(est_y,2), round(est_z,2)],
            'gt_origin_cm':    [x_o, y_o, z_o] if x_o is not None else None,
            'error_cm':        round(error_cm, 2) if error_cm is not None else None,
            'n_total_stains':  len(stains),
            'n_used_stains':   len(stains_used),
            'n_outliers':      len(stains) - len(stains_used),
            'mean_residual_cm': round(float(np.mean(residuals)), 2) if residuals else None,
            'max_residual_cm':  round(float(np.max(residuals)),  2) if residuals else None,
        }

        msg = (f'BPA Recon: est=({est_x:.1f},{est_y:.1f},{est_z:.1f})'
               + (f'  err={error_cm:.1f}cm' if error_cm else '')
               + f'  n={len(stains_used)}')
        send_notification(msg, notif_id='bpa_recon')

        return {
            'est_x':    round(est_x, 2),
            'est_y':    round(est_y, 2),
            'est_z':    round(est_z, 2),
            'error_cm': round(error_cm, 2) if error_cm is not None else None,
            'n_used':   len(stains_used),
            'report':   report,
        }
