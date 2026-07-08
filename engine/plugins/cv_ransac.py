import cv2
import numpy as np
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'cv_ransac'


def _to_px_pts(kp_dicts: list, img_shape: tuple) -> np.ndarray:
    """Normalized graphics keypoints → pixel coords (N, 2)."""
    h, w = img_shape[:2]
    pts = []
    for d in kp_dicts:
        rel = d.get('pts', [[0, 0]])[0]
        pts.append([rel[0] * w, rel[1] * h])
    return np.float32(pts)


def _bf_match(des1, des2, norm: int, ratio: float) -> list:
    """BF knnMatch + Lowe ratio test. Returns good DMatch list."""
    if des1 is None or des2 is None:
        return []
    if not isinstance(des1, np.ndarray) or not isinstance(des2, np.ndarray):
        return []
    if len(des1) < 2 or len(des2) < 2:
        return []
    if not des1.flags['C_CONTIGUOUS']:
        des1 = np.ascontiguousarray(des1)
    if not des2.flags['C_CONTIGUOUS']:
        des2 = np.ascontiguousarray(des2)
    try:
        matches = cv2.BFMatcher(norm).knnMatch(des1, des2, k=2)
    except cv2.error:
        return []
    good = []
    for m_set in matches:
        if len(m_set) == 2:
            m, n = m_set
            if m.distance < ratio * n.distance:
                good.append(m)
    return good


def _warp_geotiff(geo: dict, H: np.ndarray, dst_wh: tuple) -> dict:
    """Warp all bands of a geotiff dict with homography H."""
    data = geo.get('data')
    if data is None:
        return geo
    w, h = dst_wh
    if data.ndim == 2:
        warped = cv2.warpPerspective(data.astype(np.float32), H, (w, h))
    else:
        warped = np.stack(
            [cv2.warpPerspective(data[i].astype(np.float32), H, (w, h)) for i in range(data.shape[0])],
            axis=0,
        )
    return {**geo, 'data': warped, 'width': w, 'height': h}


@vision_node(
    type_id='cv_ransac',
    label='RANSAC Homography',
    category='keypoints',
    icon='GitMerge',
    description=(
        "Homography / affine estimation between two matched, feature-detected images. "
        "Matches SIFT/ORB descriptors, then estimates H either robustly (RANSAC, "
        "rejects outlier matches) or with the Ordinary method (no outlier rejection "
        "— a single bad match can wreck the fit, ch8 §8.7). "
        "Warp Image 1 into Image 2's reference frame. "
        "Optional GeoTIFF input: warps all bands with H (attach ref GeoTIFF's transform separately)."
    ),
    inputs=[
        {'id': 'kp1',     'color': 'list',    'label': 'Keypoints 1'},
        {'id': 'kp2',     'color': 'list',    'label': 'Keypoints 2'},
        {'id': 'des1',    'color': 'any',     'label': 'Descriptors 1'},
        {'id': 'des2',    'color': 'any',     'label': 'Descriptors 2'},
        {'id': 'img1',    'color': 'image',   'label': 'Image 1 (source)'},
        {'id': 'img2',    'color': 'image',   'label': 'Image 2 (reference)'},
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'GeoTIFF bands (optional)'},
    ],
    outputs=[
        {'id': 'warped',      'color': 'image',   'label': 'Warped (img1 → img2)'},
        {'id': 'overlay',     'color': 'image',   'label': 'Inlier match overlay'},
        {'id': 'homography',  'color': 'any',     'label': 'H matrix (3×3 list)'},
        {'id': 'inliers',     'color': 'scalar',  'label': 'Inlier count'},
        {'id': 'geotiff_out', 'color': 'geotiff', 'label': 'GeoTIFF warped'},
    ],
    params=[
        {'id': 'norm',          'label': 'Descriptor norm',  'type': 'enum',
         'options': ['L2 — SIFT/SURF', 'Hamming — ORB/BRIEF'], 'default': 0},
        {'id': 'ratio',         'label': "Lowe's ratio",     'type': 'float',
         'min': 0.5, 'max': 1.0, 'step': 0.01, 'default': 0.75},
        {'id': 'ransac_thresh', 'label': 'RANSAC threshold', 'type': 'float',
         'min': 0.5, 'max': 20.0, 'step': 0.5, 'default': 5.0},
        {'id': 'min_inliers',   'label': 'Min inliers',      'type': 'int',
         'min': 4, 'max': 500, 'default': 10},
        {'id': 'model',         'label': 'Model',            'type': 'enum',
         'options': ['Homography (8-DOF)', 'Partial Affine (4-DOF)'], 'default': 0},
        {'id': 'method',        'label': 'Estimation Method', 'type': 'enum',
         'options': ['RANSAC (robust)', 'Ordinary (Least Squares)'], 'default': 0},
        {'id': 'max_display',   'label': 'Max drawn matches','type': 'int',
         'min': 1, 'max': 300, 'default': 60},
    ],
    colorable=True,
)
class RansacHomographyNode(NodeProcessor):
    def process(self, inputs: dict, params: dict) -> dict:
        img1 = inputs.get('img1')
        img2 = inputs.get('img2')
        kp1  = inputs.get('kp1') or []
        kp2  = inputs.get('kp2') or []
        des1 = inputs.get('des1')
        des2 = inputs.get('des2')
        geo  = inputs.get('geotiff')

        _empty = {'warped': img1, 'overlay': img1, 'homography': None,
                  'inliers': 0.0, 'geotiff_out': geo}

        if img1 is None or img2 is None:
            return _empty
        if not kp1 or not kp2:
            send_notification('RANSAC: connect keypoints from a detector', level='warning', notif_id=_NOTIF)
            return _empty

        norm_idx = int(params.get('norm', 0))
        norm     = cv2.NORM_L2 if norm_idx == 0 else cv2.NORM_HAMMING
        ratio    = float(params.get('ratio', 0.75))
        thresh   = float(params.get('ransac_thresh', 5.0))
        min_in   = int(params.get('min_inliers', 10))
        model    = int(params.get('model', 0))
        ordinary = int(params.get('method', 0)) == 1
        max_disp = int(params.get('max_display', 60))

        # Match descriptors with BF + Lowe ratio test
        good = _bf_match(des1, des2, norm, ratio)
        needed = max(4, min_in)

        if len(good) < needed:
            send_notification(
                f'RANSAC: {len(good)} matches — need ≥ {needed}',
                level='warning', notif_id=_NOTIF,
            )
            return {**_empty, 'inliers': float(len(good))}

        # Convert to pixel coords
        px1 = _to_px_pts(kp1, img1.shape)
        px2 = _to_px_pts(kp2, img2.shape)

        src_pts = np.float32([px1[m.queryIdx] for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([px2[m.trainIdx] for m in good]).reshape(-1, 1, 2)

        # Estimate geometric model. "Ordinary" skips outlier rejection entirely —
        # every matched point (including any bad one) is used, demonstrating how
        # a single wrong correspondence can wreck a non-robust fit (ch8 §8.7).
        if model == 0:  # Homography
            if ordinary:
                H = cv2.findHomography(src_pts, dst_pts, 0)[0]
                mask = np.ones((len(good), 1), dtype=np.uint8)
            else:
                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, thresh)
        else:           # Partial Affine (rotation + scale + translation)
            aff_method = cv2.LMEDS if ordinary else cv2.RANSAC
            H_aff, mask = cv2.estimateAffinePartial2D(
                src_pts, dst_pts, method=aff_method, ransacReprojThreshold=thresh,
            )
            H = np.vstack([H_aff, [0, 0, 1]]) if H_aff is not None else None

        if H is None or mask is None:
            send_notification('RANSAC: failed to estimate transform', level='warning', notif_id=_NOTIF)
            return _empty

        inlier_flags = mask.ravel().tolist()
        inlier_count = int(sum(inlier_flags))

        if inlier_count < min_in:
            send_notification(
                f'RANSAC: {inlier_count} inliers < min {min_in} — result may be unreliable',
                level='warning', notif_id=_NOTIF,
            )

        # Warp img1 into img2's coordinate space
        h2, w2 = img2.shape[:2]
        warped = cv2.warpPerspective(img1, H, (w2, h2))

        # Inlier match overlay
        inliers_good = [m for m, ok in zip(good, inlier_flags) if ok]
        cv_kp1 = [cv2.KeyPoint(float(p[0]), float(p[1]), 1.0) for p in px1]
        cv_kp2 = [cv2.KeyPoint(float(p[0]), float(p[1]), 1.0) for p in px2]
        overlay = cv2.drawMatches(
            img1, cv_kp1, img2, cv_kp2,
            inliers_good[:max_disp], None,
            matchColor=(0, 220, 80),
            singlePointColor=(80, 80, 80),
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        )
        # Inlier count label on overlay
        cv2.putText(overlay, f'Inliers: {inlier_count}/{len(good)}',
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 80), 1, cv2.LINE_AA)

        geo_out = _warp_geotiff(geo, H, (w2, h2)) if geo is not None else None

        return {
            'warped':      warped,
            'overlay':     overlay,
            'homography':  H.tolist(),
            'inliers':     float(inlier_count),
            'geotiff_out': geo_out,
        }
