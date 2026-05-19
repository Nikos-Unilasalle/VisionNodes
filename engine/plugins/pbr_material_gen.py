"""
PBR Material Generator — Derives material maps from a single image.
Algorithmic mode: real-time via gradient/variance analysis.
AI Enhanced mode: Depth Anything V2 Small for depth-driven normals + height.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import threading

try:
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

_NOTIF_ID = 'pbr_material_gen'
_DEPTH_MODEL_ID = 'depth-anything/Depth-Anything-V2-Small-hf'


@vision_node(
    type_id='pbr_material_gen',
    label='PBR Material Generator',
    category='cv',
    icon='Layers',
    description=(
        "Generates PBR material maps from a single image: Albedo, Normal Map, Roughness, "
        "Height, and Ambient Occlusion. "
        "Algorithmic mode runs in real-time. AI Enhanced uses Depth Anything V2 Small "
        "for higher-quality depth-based normals and height map."
    ),
    resizable=False,
    inputs=[{'id': 'image', 'color': 'image', 'label': 'Image'}],
    outputs=[
        {'id': 'albedo',    'color': 'image', 'label': 'Albedo'},
        {'id': 'normal',    'color': 'image', 'label': 'Normal Map'},
        {'id': 'roughness', 'color': 'image', 'label': 'Roughness'},
        {'id': 'height',    'color': 'image', 'label': 'Height'},
        {'id': 'ao',        'color': 'image', 'label': 'AO'},
    ],
    params=[
        {'id': 'mode', 'label': 'Mode', 'type': 'enum',
         'options': ['Algorithmic', 'AI Enhanced'], 'default': 0},
        {'id': 'normal_strength', 'label': 'Normal Strength', 'type': 'float',
         'min': 0.5, 'max': 15.0, 'default': 4.0},
        {'id': 'roughness_radius', 'label': 'Roughness Radius', 'type': 'int',
         'min': 2, 'max': 24, 'default': 6},
        {'id': 'invert_roughness', 'label': 'Invert Roughness', 'type': 'bool',
         'default': False},
        {'id': 'ao_radius', 'label': 'AO Radius', 'type': 'int',
         'min': 4, 'max': 64, 'default': 16},
    ]
)
class PBRMaterialGenNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._processor = None
        self._model = None
        self._loading = False
        self._model_ready = False
        self._failed = False
        self.device = 'cpu'
        if TRANSFORMERS_AVAILABLE:
            if torch.backends.mps.is_available():
                self.device = 'mps'
            elif torch.cuda.is_available():
                self.device = 'cuda'

    # ── AI Model Loading ──────────────────────────────────────────────────────

    def _load_model_thread(self):
        try:
            send_notification('PBR: Downloading depth model...', progress=0.1, notif_id=_NOTIF_ID)
            old_threads = torch.get_num_threads()
            torch.set_num_threads(1)
            try:
                self._processor = AutoImageProcessor.from_pretrained(_DEPTH_MODEL_ID)
                model = AutoModelForDepthEstimation.from_pretrained(_DEPTH_MODEL_ID)
                model.to(self.device)
                model.eval()
                self._model = model
            finally:
                torch.set_num_threads(old_threads)
            self._model_ready = True
            send_notification('PBR: AI model ready ✓', progress=1.0, notif_id=_NOTIF_ID)
        except Exception as e:
            self._failed = True
            send_notification(f'PBR Error: {str(e)[:120]}', level='error', notif_id=_NOTIF_ID)
        finally:
            self._loading = False

    def _ensure_model(self):
        if self._model_ready or self._loading or self._failed or not TRANSFORMERS_AVAILABLE:
            return
        self._loading = True
        threading.Thread(target=self._load_model_thread, daemon=True).start()

    def _run_depth_ai(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        inputs_proc = self._processor(images=rgb, return_tensors='pt').to(self.device)
        with torch.no_grad():
            depth = self._model(**inputs_proc).predicted_depth
        prediction = torch.nn.functional.interpolate(
            depth.unsqueeze(1), size=(h, w), mode='bicubic', align_corners=False
        )
        depth_np = prediction.squeeze().cpu().numpy()
        d_min, d_max = depth_np.min(), depth_np.max()
        if d_max > d_min:
            return (depth_np - d_min) / (d_max - d_min)
        return np.zeros((h, w), dtype=np.float32)

    # ── Map Computation ───────────────────────────────────────────────────────

    def _albedo(self, image: np.ndarray) -> np.ndarray:
        # Frequency separation: subtract low-frequency lighting, keep diffuse detail
        blur = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 64)
        mid = np.mean(blur)
        albedo = np.clip(image.astype(np.float32) - blur + mid, 0, 255)
        return albedo.astype(np.uint8)

    def _normal_from_gray(self, gray: np.ndarray, strength: float) -> np.ndarray:
        gray_f = cv2.GaussianBlur(gray.astype(np.float32) / 255.0, (0, 0), 1.5)
        return self._normals_from_float(gray_f, strength)

    def _normal_from_depth(self, depth_f: np.ndarray, strength: float) -> np.ndarray:
        smoothed = cv2.GaussianBlur(depth_f, (0, 0), 1.0)
        return self._normals_from_float(smoothed, strength)

    def _normals_from_float(self, src: np.ndarray, strength: float) -> np.ndarray:
        dx = cv2.Sobel(src, cv2.CV_32F, 1, 0, ksize=3) * strength
        dy = cv2.Sobel(src, cv2.CV_32F, 0, 1, ksize=3) * strength
        z = np.ones_like(dx)
        length = np.sqrt(dx * dx + dy * dy + z * z) + 1e-8
        nx, ny, nz = dx / length, dy / length, z / length
        # BGR output: B=Z, G=Y, R=X (standard OpenGL tangent-space encoding)
        return np.stack([
            (nz * 0.5 + 0.5) * 255,
            (ny * 0.5 + 0.5) * 255,
            (nx * 0.5 + 0.5) * 255,
        ], axis=2).astype(np.uint8)

    def _roughness(self, gray: np.ndarray, radius: int, invert: bool) -> np.ndarray:
        k = radius * 2 + 1
        g_f = gray.astype(np.float32)
        mean = cv2.blur(g_f, (k, k))
        mean_sq = cv2.blur(g_f * g_f, (k, k))
        std = np.sqrt(np.maximum(mean_sq - mean * mean, 0))
        rough = cv2.normalize(std, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        if invert:
            rough = 255 - rough
        return cv2.cvtColor(rough, cv2.COLOR_GRAY2BGR)

    def _height(self, gray: np.ndarray) -> np.ndarray:
        # Frequency separation: remove broad lighting gradient, keep surface relief
        gray_f = gray.astype(np.float32)
        low_freq = cv2.GaussianBlur(gray_f, (0, 0), 32.0)
        relief = np.clip(gray_f - low_freq + 128.0, 0, 255).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        return cv2.cvtColor(clahe.apply(relief), cv2.COLOR_GRAY2BGR)

    def _ao(self, height_gray: np.ndarray, radius: int) -> np.ndarray:
        h_f = height_gray.astype(np.float32) / 255.0
        # Multi-scale cavity: fine scales catch contact shadows, coarse catch broad AO
        scales = (max(1, radius // 4), max(2, radius // 2), radius, radius * 2)
        weights = (0.35, 0.30, 0.20, 0.15)
        occlusion = np.zeros_like(h_f)
        for sigma, w in zip(scales, weights):
            local_mean = cv2.GaussianBlur(h_f, (0, 0), float(sigma))
            # Cavity = how much lower than surroundings → occluded
            occlusion += np.clip((local_mean - h_f) * 4.0, 0.0, 1.0) * w
        # PBR convention: white = fully exposed, dark = occluded
        ao = np.power(np.clip(1.0 - occlusion, 0.0, 1.0), 0.8)
        return cv2.cvtColor((ao * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)

    # ── Main Process ──────────────────────────────────────────────────────────

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None:
            return {}

        mode = params.get('mode', 0)
        ai_mode = (int(mode) == 1) if not isinstance(mode, str) else (mode == 'AI Enhanced')
        strength = float(params.get('normal_strength', 4.0))
        rough_radius = int(params.get('roughness_radius', 6))
        invert_rough = bool(params.get('invert_roughness', False))
        ao_radius = int(params.get('ao_radius', 16))

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        albedo = self._albedo(image)
        roughness = self._roughness(gray, rough_radius, invert_rough)

        if ai_mode:
            self._ensure_model()
            if self._model_ready:
                try:
                    depth_f = self._run_depth_ai(image)
                    depth_u8 = (depth_f * 255).astype(np.uint8)
                    return {
                        'albedo':    albedo,
                        'normal':    self._normal_from_depth(depth_f, strength),
                        'roughness': roughness,
                        'height':    cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR),
                        'ao':        self._ao(depth_u8, ao_radius),
                    }
                except Exception as e:
                    print(f'[PBR] AI inference error: {e}')
                    # Fall through to algorithmic

        height_bgr = self._height(gray)
        height_gray_out = cv2.cvtColor(height_bgr, cv2.COLOR_BGR2GRAY)
        return {
            'albedo':    albedo,
            'normal':    self._normal_from_gray(gray, strength),
            'roughness': roughness,
            'height':    height_bgr,
            'ao':        self._ao(height_gray_out, ao_radius),
        }
