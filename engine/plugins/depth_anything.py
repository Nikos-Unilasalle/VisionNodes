"""
Depth Anything V2 — Monocular Depth Estimation.
Provides high-quality depth maps from single images, useful for 3D analysis, 
masonry joint detection, and surface relief visualization.
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import threading
import torch
import os

try:
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

_NOTIF_ID = 'depth_anything'

_MODELS = {
    'Small (Fast)': 'depth-anything/Depth-Anything-V2-Small-hf',
    'Base': 'depth-anything/Depth-Anything-V2-Base-hf',
    'Large': 'depth-anything/Depth-Anything-V2-Large-hf',
}
_MODEL_NAMES = list(_MODELS.keys())

@vision_node(
    type_id='depth_anything_v2',
    label='Depth Estimator',
    category='analysis',
    icon='BoxSelect',
    description=(
        "State-of-the-art monocular depth estimation powered by Depth Anything V2 (TikTok/ByteDance). "
        "Generates a relief map where brightness typically represents proximity. "
        "Ideal for scientific analysis of textures, masonry, and architectural features."
    ),
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'depth', 'color': 'image', 'label': 'Depth Map'},
        {'id': 'overlay', 'color': 'image', 'label': 'Colormap'},
    ],
    params=[
        {'id': 'model', 'label': 'Model Size', 'type': 'enum', 
         'options': _MODEL_NAMES, 'default': 0},
        {'id': 'colormap', 'label': 'Colormap', 'type': 'enum', 
         'options': ['Inferno', 'Magma', 'Viridis', 'Plasma', 'Grayscale'], 'default': 0},
    ]
)
class DepthAnythingNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.processor = None
        self.model = None
        self.current_model_name = ""
        self._loading = False
        self._failed = set()

        # Device detection
        self.device = 'cpu'
        if TRANSFORMERS_AVAILABLE:
            if torch.backends.mps.is_available():
                self.device = 'mps'
            elif torch.cuda.is_available():
                self.device = 'cuda'
            print(f"[Depth] Using device: {self.device}")

    def _load_model_thread(self, model_name):
        """Load the Depth Anything model in a background thread."""
        try:
            repo_id = _MODELS.get(model_name)
            if not repo_id:
                return

            send_notification(
                f"Depth: Downloading {model_name}...", 
                progress=0.1, notif_id=_NOTIF_ID
            )
            
            # Limit CPU threads during heavy model loading to avoid UI lag
            old_threads = torch.get_num_threads()
            torch.set_num_threads(1)
            
            try:
                # Load processor and model
                self.processor = AutoImageProcessor.from_pretrained(repo_id)
                model = AutoModelForDepthEstimation.from_pretrained(repo_id)
                
                # Move to accelerator
                model.to(self.device)
                model.eval()
                self.model = model
            finally:
                torch.set_num_threads(old_threads)

            self.current_model_name = model_name
            send_notification(
                f"Depth: {model_name} ready ✓", 
                progress=1.0, notif_id=_NOTIF_ID
            )
        except Exception as e:
            self._failed.add(model_name)
            print(f"[Depth] Model load FAILED: {e}")
            send_notification(
                f"Depth Error: {str(e)[:120]}", 
                level='error', notif_id=_NOTIF_ID
            )
        finally:
            self._loading = False

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None:
            return {}

        if not TRANSFORMERS_AVAILABLE:
            send_notification(
                'Depth: pip install transformers timm',
                level='error', notif_id=_NOTIF_ID
            )
            return {'depth': image, 'overlay': image}

        # ── 1. Model Loading ──
        model_idx = int(params.get('model', 0))
        model_name = _MODEL_NAMES[min(model_idx, len(_MODEL_NAMES) - 1)]

        if model_name != self.current_model_name:
            if not self._loading and model_name not in self._failed:
                self._loading = True
                self.model = None
                threading.Thread(
                    target=self._load_model_thread, 
                    args=(model_name,), 
                    daemon=True
                ).start()
            return {'depth': image, 'overlay': image}

        if self.model is None:
            return {}

        # ── 2. Inference ──
        try:
            h, w = image.shape[:2]
            self.report_progress(0.2, "Depth: Estimating...")

            # Convert BGR (OpenCV) to RGB (Transformers)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Pre-process
            inputs_proc = self.processor(images=rgb, return_tensors="pt").to(self.device)
            
            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs_proc)
                # Depth Anything V2 returns relative depth
                depth = outputs.predicted_depth

            # Resize to original resolution
            prediction = torch.nn.functional.interpolate(
                depth.unsqueeze(1),
                size=(h, w),
                mode="bicubic",
                align_corners=False,
            )
            
            depth_np = prediction.squeeze().cpu().numpy()
            
            # ── 3. Normalization & Colormapping ──
            # Normalize to 0-1 range
            d_min, d_max = depth_np.min(), depth_np.max()
            if d_max > d_min:
                depth_norm = (depth_np - d_min) / (d_max - d_min)
            else:
                depth_norm = np.zeros_like(depth_np)
            
            # Convert to uint8 for visualization
            depth_u8 = (depth_norm * 255).astype(np.uint8)
            
            # Apply chosen colormap
            cm_name = params.get('colormap', 'Inferno')
            if cm_name == 'Grayscale':
                overlay = cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR)
            else:
                cm_map = {
                    'Inferno': cv2.COLORMAP_INFERNO,
                    'Magma': cv2.COLORMAP_MAGMA,
                    'Viridis': cv2.COLORMAP_VIRIDIS,
                    'Plasma': cv2.COLORMAP_PLASMA
                }
                overlay = cv2.applyColorMap(depth_u8, cm_map.get(cm_name, cv2.COLORMAP_INFERNO))

            self.report_progress(1.0, "Depth: Done")
            return {
                'depth': cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR),
                'overlay': overlay
            }
        except Exception as e:
            print(f"[Depth] Inference error: {e}")
            self.report_progress(1.0, "Depth: Error")
            return {}
