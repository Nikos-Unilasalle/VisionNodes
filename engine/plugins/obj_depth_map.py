"""
OBJ Depth Map — loads a 3D .obj file and generates a normalized depth map.

Algorithm (numpy rasterizer — no dependency on trimesh camera/ray API):
  1. Load via trimesh (vertices + faces only)
  2. Centering + normalization to unit scale
  3. Camera rotation: azimuth (Y) then elevation (X)
  4. Perspective projection (FOV 60°)
  5. Z-buffer via triangle rasterization (vectorized barycentric coordinates per face)
  6. Normalization [0,1] → close = white; background = black
  7. Optional colormap (OpenCV)

Cache by (path, mtime, parameters).
"""
from registry import vision_node, NodeProcessor
import numpy as np
import os
import base64
import traceback

_NULL = {'depth': None, 'path': '', '_thumb': None}
_CACHE: dict = {}


def _cv2_cmap(name):
    import cv2
    return {
        'jet':     cv2.COLORMAP_JET,
        'magma':   cv2.COLORMAP_MAGMA,
        'inferno': cv2.COLORMAP_INFERNO,
        'plasma':  cv2.COLORMAP_PLASMA,
        'viridis': cv2.COLORMAP_VIRIDIS,
        'hot':     cv2.COLORMAP_HOT,
    }.get(name, cv2.COLORMAP_MAGMA)


def _rotation_y(angle_rad: float) -> np.ndarray:
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def _rotation_x(angle_rad: float) -> np.ndarray:
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def _render(obj_path, img_w, img_h, azimuth_deg, elevation_deg, colormap_name):
    import cv2

    if not os.path.isfile(obj_path):
        return None, f"file not found: {obj_path}"

    try:
        mtime = os.path.getmtime(obj_path)
    except OSError as exc:
        return None, str(exc)

    key = (obj_path, mtime, img_w, img_h, azimuth_deg, elevation_deg, colormap_name)
    if key in _CACHE:
        return _CACHE[key], None

    # --- Mesh Loading ---
    try:
        import trimesh
    except ImportError:
        return None, "trimesh not found — run: npm run setup"

    try:
        geo = trimesh.load(obj_path, force='mesh', process=False)
    except Exception as exc:
        return None, f"trimesh.load: {exc}"

    if not hasattr(geo, 'faces') or len(geo.faces) == 0:
        return None, "no faces found in the mesh"

    verts = np.array(geo.vertices, dtype=np.float64)  # (V, 3)
    faces = np.array(geo.faces,    dtype=np.int32)     # (F, 3)

    # --- Centering + normalization ---
    verts -= verts.mean(axis=0)
    scale = np.abs(verts).max()
    if scale > 0:
        verts /= scale

    # --- Camera Rotation ---
    az = np.radians(azimuth_deg)
    el = np.radians(elevation_deg)
    R = _rotation_x(el) @ _rotation_y(az)
    vc = (R @ verts.T).T  # (V, 3) in camera space

    # --- Perspective Projection ---
    # Camera at z = -cam_dist, looking towards +z
    cam_dist = 2.5
    zc = vc[:, 2] + cam_dist          # depth from camera (>0 = in front)
    zc = np.where(zc > 1e-4, zc, 1e-4)

    fov_half = np.radians(30.0)       # FOV 60°
    f = (min(img_w, img_h) / 2.0) / np.tan(fov_half)

    cx, cy = img_w / 2.0, img_h / 2.0
    xp = f * vc[:, 0] / zc + cx      # screen x
    yp = -f * vc[:, 1] / zc + cy     # screen y (inverted Y axis)

    # --- Z-buffer Rasterization ---
    depth_buf = np.full((img_h, img_w), np.inf, dtype=np.float32)

    # Projected vertices per face (F, 3) each
    ax, ay, az_f = xp[faces[:, 0]], yp[faces[:, 0]], zc[faces[:, 0]]
    bx, by, bz_f = xp[faces[:, 1]], yp[faces[:, 1]], zc[faces[:, 1]]
    cx_f, cy_f, cz_f = xp[faces[:, 2]], yp[faces[:, 2]], zc[faces[:, 2]]

    for i in range(len(faces)):
        x0, y0, z0 = ax[i], ay[i], az_f[i]
        x1, y1, z1 = bx[i], by[i], bz_f[i]
        x2, y2, z2 = cx_f[i], cy_f[i], cz_f[i]

        xmin = max(0,        int(np.floor(min(x0, x1, x2))))
        xmax = min(img_w-1,  int(np.ceil( max(x0, x1, x2))))
        ymin = max(0,        int(np.floor(min(y0, y1, y2))))
        ymax = min(img_h-1,  int(np.ceil( max(y0, y1, y2))))

        if xmin > xmax or ymin > ymax:
            continue

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-10:
            continue

        xs = np.arange(xmin, xmax + 1, dtype=np.float32)
        ys = np.arange(ymin, ymax + 1, dtype=np.float32)
        px, py = np.meshgrid(xs, ys)

        w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / denom
        w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / denom
        w2 = 1.0 - w0 - w1

        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue

        z_interp = (w0 * z0 + w1 * z1 + w2 * z2).astype(np.float32)

        ry = (py[inside] + 0.5).astype(int)
        rx = (px[inside] + 0.5).astype(int)
        ry = np.clip(ry, 0, img_h - 1)
        rx = np.clip(rx, 0, img_w - 1)
        zi = z_interp[inside]

        # Write to z-buffer (keeps the minimum = closest)
        np.minimum.at(depth_buf, (ry, rx), zi)

    # --- Normalization ---
    valid = np.isfinite(depth_buf)
    if not valid.any():
        return None, "no visible pixels (check camera orientation)"

    d_min = float(depth_buf[valid].min())
    d_max = float(depth_buf[valid].max())

    norm = np.zeros((img_h, img_w), dtype=np.float32)
    if d_max > d_min:
        norm[valid] = 1.0 - (depth_buf[valid] - d_min) / (d_max - d_min)
    else:
        norm[valid] = 1.0

    depth_u8 = (norm * 255).astype(np.uint8)

    if colormap_name and colormap_name != 'none':
        result = cv2.applyColorMap(depth_u8, _cv2_cmap(colormap_name))
    else:
        result = cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR)

    _CACHE.clear()
    _CACHE[key] = result
    return result, None


@vision_node(
    type_id='obj_depth_map',
    label='OBJ Depth Map',
    category='3d',
    icon='Box',
    description=(
        "Loads a 3D .obj file (drag & drop) and generates a normalized depth map. "
        "Close to the camera = white. Background = black. "
        "Azimuth and elevation allow rotating the camera around the mesh."
    ),
    resizable=True,
    min_width=240,
    min_height=200,
    colorable=True,
    inputs=[],
    outputs=[
        {'id': 'depth', 'color': 'image',  'label': 'Depth Map'},
        {'id': 'path',  'color': 'string', 'label': 'File Path'},
    ],
    params=[
        {'id': 'obj_path',  'label': 'OBJ File',     'type': 'string',  'default': ''},
        {'id': '_sec_render', 'label': 'Render Size', 'type': 'section'},
        {'id': 'img_w',     'label': 'Width (px)',    'type': 'int',     'default': 512,
         'min': 64,  'max': 2048},
        {'id': 'img_h',     'label': 'Height (px)',   'type': 'int',     'default': 512,
         'min': 64,  'max': 2048},
        {'id': '_sec_camera', 'label': 'Camera', 'type': 'section'},
        {'id': 'azimuth',   'label': 'Azimuth (°)',   'type': 'int',     'default': 0,
         'min': -180, 'max': 180},
        {'id': 'elevation', 'label': 'Elevation (°)', 'type': 'int',     'default': 30,
         'min': -90,  'max': 90},
        {'id': '_sec_display', 'label': 'Display', 'type': 'section'},
        {'id': 'colormap',  'label': 'Colormap',      'type': 'enum',    'default': 'none',
         'options': ['none', 'magma', 'inferno', 'plasma', 'viridis', 'jet', 'hot']},
    ],
)
class ObjDepthMapNode(NodeProcessor):
    def process(self, inputs, params):
        obj_path = str(params.get('obj_path') or '').strip()
        if not obj_path:
            return _NULL

        try:
            depth, err = _render(
                obj_path=obj_path,
                img_w=max(64, int(params.get('img_w', 512))),
                img_h=max(64, int(params.get('img_h', 512))),
                azimuth_deg=float(params.get('azimuth', 0)),
                elevation_deg=float(params.get('elevation', 30)),
                colormap_name=str(params.get('colormap', 'none')),
            )
        except Exception:
            err = traceback.format_exc()
            depth = None

        thumb = None
        if depth is not None:
            import cv2
            _, buf = cv2.imencode('.jpg', depth, [cv2.IMWRITE_JPEG_QUALITY, 75])
            thumb = base64.b64encode(buf).decode('utf-8')

        return {
            'depth': depth,
            'path':  obj_path,
            '_thumb': thumb,
            '_error': err,
        }
