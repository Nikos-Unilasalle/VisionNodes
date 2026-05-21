"""
OBJ Depth Map — charge un fichier .obj 3D et génère une carte de profondeur normalisée.

Algorithme :
  1. Chargement via trimesh, centrage + normalisation à l'échelle unitaire
  2. Caméra positionnée par azimut / élévation, projection perspective
  3. Ray casting vectorisé (trimesh.ray) → distances par pixel
  4. Normalisation [0,1] → proche = blanc; fond = noir
  5. Colormap optionnelle (OpenCV)

Résultat mis en cache par (chemin, mtime, paramètres) pour éviter tout recalcul.
"""
from registry import vision_node, NodeProcessor
import numpy as np
import os
import base64

_NULL = {'depth': None, 'path': ''}
_CACHE: dict = {}

_MPL_CMAPS = {
    'jet':     None,   # cv2.COLORMAP_JET
    'magma':   None,
    'inferno': None,
    'plasma':  None,
    'viridis': None,
    'hot':     None,
}


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


def _render(obj_path, img_w, img_h, azimuth_deg, elevation_deg, colormap_name):
    import cv2
    try:
        import trimesh
    except ImportError:
        return None

    if not os.path.isfile(obj_path):
        return None

    try:
        mtime = os.path.getmtime(obj_path)
    except OSError:
        return None

    key = (obj_path, mtime, img_w, img_h, azimuth_deg, elevation_deg, colormap_name)
    if key in _CACHE:
        return _CACHE[key]

    # Load mesh
    try:
        geo = trimesh.load(obj_path, force='mesh', process=False)
    except Exception:
        return None

    if not hasattr(geo, 'faces') or len(geo.faces) == 0:
        return None

    # Center + unit scale
    geo = geo.copy()
    geo.vertices -= geo.bounding_box.centroid
    ext = float(geo.bounding_box.extents.max())
    if ext > 0:
        geo.apply_scale(1.0 / ext)

    # Camera setup
    scene = geo.scene()
    try:
        scene.set_camera(
            angles=[np.radians(elevation_deg), 0.0, np.radians(azimuth_deg)],
            distance=2.5,
            center=[0.0, 0.0, 0.0],
        )
    except Exception:
        pass
    scene.camera.resolution = [img_w, img_h]

    # Generate rays
    try:
        origins, vectors, pixels = scene.camera_rays()
    except Exception:
        return None

    # Ray-mesh intersection (vectorised)
    try:
        loc, ray_idx, _ = trimesh.ray.ray_triangle.RayMeshIntersector(geo) \
            .intersects_location(origins, vectors, multiple_hits=False)
    except Exception:
        return None

    depth_buf = np.zeros((img_h, img_w), dtype=np.float32)

    if len(loc) > 0:
        cam_pos = np.asarray(scene.camera_transform[:3, 3], dtype=np.float32)
        dists = np.linalg.norm(loc - cam_pos, axis=1).astype(np.float32)
        hit_px = pixels[ray_idx]
        d_min, d_max = dists.min(), dists.max()
        norm_d = 1.0 - (dists - d_min) / (d_max - d_min + 1e-8)
        mask = (
            (hit_px[:, 0] >= 0) & (hit_px[:, 0] < img_w) &
            (hit_px[:, 1] >= 0) & (hit_px[:, 1] < img_h)
        )
        hp = hit_px[mask]
        nv = norm_d[mask]
        depth_buf[hp[:, 1], hp[:, 0]] = nv

    depth_u8 = (depth_buf * 255).astype(np.uint8)

    if colormap_name and colormap_name != 'none':
        result = cv2.applyColorMap(depth_u8, _cv2_cmap(colormap_name))
    else:
        result = cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR)

    _CACHE.clear()
    _CACHE[key] = result
    return result


@vision_node(
    type_id='obj_depth_map',
    label='OBJ Depth Map',
    category='3d',
    icon='Box',
    description=(
        "Charge un fichier .obj 3D (drag & drop) et génère une carte de profondeur "
        "normalisée. Proche de la caméra = blanc. Fond = noir. "
        "Azimut et élévation permettent de faire pivoter la caméra autour de la mesh."
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
        {'id': 'img_w',     'label': 'Width (px)',    'type': 'int',     'default': 512,
         'min': 64,  'max': 2048},
        {'id': 'img_h',     'label': 'Height (px)',   'type': 'int',     'default': 512,
         'min': 64,  'max': 2048},
        {'id': 'azimuth',   'label': 'Azimuth (°)',   'type': 'int',     'default': 0,
         'min': -180, 'max': 180},
        {'id': 'elevation', 'label': 'Elevation (°)', 'type': 'int',     'default': 30,
         'min': -90,  'max': 90},
        {'id': 'colormap',  'label': 'Colormap',      'type': 'enum',    'default': 'none',
         'options': ['none', 'magma', 'inferno', 'plasma', 'viridis', 'jet', 'hot']},
    ],
)
class ObjDepthMapNode(NodeProcessor):
    def process(self, inputs, params):
        obj_path = str(params.get('obj_path') or '').strip()
        if not obj_path:
            return _NULL

        depth = _render(
            obj_path=obj_path,
            img_w=max(64, int(params.get('img_w', 512))),
            img_h=max(64, int(params.get('img_h', 512))),
            azimuth_deg=float(params.get('azimuth', 0)),
            elevation_deg=float(params.get('elevation', 30)),
            colormap_name=str(params.get('colormap', 'none')),
        )
        _thumb = None
        if depth is not None:
            import cv2
            _, buf = cv2.imencode('.jpg', depth, [cv2.IMWRITE_JPEG_QUALITY, 75])
            _thumb = base64.b64encode(buf).decode('utf-8')
        return {'depth': depth, 'path': obj_path, '_thumb': _thumb}
