"""
SAM Depth-Guided — Automatic segmentation using Depth Anything V2 as a guide for SAM 2.
Detects relief peaks in the depth map and uses them as prompts for object segmentation.
"""
from registry import vision_node, NodeProcessor, send_notification
try:
    from plugins.sam_segmenter import SAMSegmenterNode
except ImportError:
    # Fallback for different path structures
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from sam_segmenter import SAMSegmenterNode

import cv2
import numpy as np
import torch

@vision_node(
    type_id='sam_depth_guided',
    label='Depth-Guided Segmenter',
    category='segmentation',
    icon='Fingerprint',
    description="Automatic stone/object segmentation using Depth Anything V2 to guide SAM 2. Finds the 'highest' points of objects and prompts SAM to segment them.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'depth', 'color': 'image', 'label': 'Depth Map'}
    ],
    outputs=[
        {'id': 'main',      'color': 'image',  'label': 'Overlay'},
        {'id': 'mask',      'color': 'mask',   'label': 'Combined Mask'},
        {'id': 'count',     'color': 'scalar', 'label': 'Object Count'},
        {'id': 'areas',     'color': 'list',   'label': 'Areas (px²)'},
        {'id': 'centroids', 'color': 'list',   'label': 'Centroids'},
        {'id': 'contours',  'color': 'list',   'label': 'Contours List'},
    ],
    params=[
        # ── Model Selection ──
        {'id': 'model', 'label': 'SAM 2 Model', 'type': 'enum', 'options': ['Tiny', 'Small', 'Base+', 'Large'], 'default': 0},
        
        # ── Relief Detection ──
        {'id': 'sensitivity', 'label': 'Relief Sensitivity', 'type': 'float', 'default': 0.5, 'min': 0.0, 'max': 1.0},
        {'id': 'max_points', 'label': 'Max Objects', 'type': 'int', 'default': 50, 'min': 1, 'max': 200},
        {'id': 'min_obj_size', 'label': 'Min Relief Size (px)', 'type': 'int', 'default': 100, 'min': 1, 'max': 10000},
        
        # ── Visuals ──
        {'id': 'overlay_opacity', 'label': 'Overlay Opacity (%)', 'type': 'number', 'default': 50, 'min': 0, 'max': 100},
    ]
)
class SAMDepthGuided(SAMSegmenterNode):
    """
    This node specializes the SAM 2 node by using a depth map to generate prompts.
    It identifies peaks in the depth map (closest parts of objects) and uses them 
    to trigger segmentation.
    """
    def process(self, inputs, params):
        image = inputs.get('image')
        depth = inputs.get('depth')
        if image is None or depth is None:
            return {
                'main': image, 'mask': None, 'count': 0, 
                'areas': [], 'centroids': [], 'contours': []
            }

        # 1. Prepare Depth Map
        if len(depth.shape) == 3:
            depth_gray = cv2.cvtColor(depth, cv2.COLOR_BGR2GRAY)
        else:
            depth_gray = depth
            
        # 2. Peak Detection via Local Maxima (Finding the highest point of each stone)
        h, w = image.shape[:2]
        sensitivity = float(params.get('sensitivity', 0.5))
        
        # Adaptive neighborhood based on image size
        k_size = int(31 * (w / 1000)) 
        if k_size % 2 == 0: k_size += 1
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        local_max = cv2.dilate(depth_gray, kernel)
        
        # Peaks are pixels equal to their local maximum
        peaks_mask = cv2.compare(depth_gray, local_max, cv2.CMP_EQ)
        
        # Filter by sensitivity (absolute depth threshold)
        # 1.0 sensitivity = 0 threshold (all peaks), 0.0 = only the absolute highest
        thresh_val = int(255 * (1.0 - sensitivity))
        _, thresholded = cv2.threshold(depth_gray, thresh_val, 255, cv2.THRESH_BINARY)
        peaks_mask = cv2.bitwise_and(peaks_mask, thresholded)
        
        # Find peak centroids
        cnts, _ = cv2.findContours(peaks_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        max_p = int(params.get('max_points', 50))
        prompts = []
        
        # Sort by depth value to get the closest stones first
        peaks_with_val = []
        for c in cnts:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                # Clip coordinates to be safe
                cx = max(0, min(w-1, cx))
                cy = max(0, min(h-1, cy))
                val = depth_gray[cy, cx]
                peaks_with_val.append((val, cx, cy))
        
        peaks_with_val.sort(key=lambda x: x[0], reverse=True)
        
        for val, cx, cy in peaks_with_val[:max_p]:
            prompts.append({'x': float(cx / w), 'y': float(cy / h), 'label': 1})
        
        if not prompts:
            # Fallback if no peaks found: return empty or try to segment the whole image?
            # Better to return empty so the user knows to adjust sensitivity
            self.report_progress(1.0, "No relief peaks detected. Adjust sensitivity.")
            return {
                'main': image, 'mask': None, 'count': 0, 
                'areas': [], 'centroids': [], 'contours': []
            }

        # 3. Use SAM Segmenter logic in Automatic mode but with our custom prompts
        # We override the automatic mode to use OUR detected peaks instead of a grid
        # Actually, SAMSegmenterNode.process doesn't support passing prompts directly 
        # in automatic mode without a lot of changes. 
        # But we can simulate a multi-prompt input by looping or by using prompt_mode=1.
        
        # We'll use the prompt_mode=1 (Multi-point) logic of the parent
        params_sam = dict(params)
        params_sam['prompt_mode'] = 1 # Multi-point
        
        # Note: the parent class process() for mode 1 only handles ONE object from multiple points.
        # If we want MULTIPLE objects (one per peak), we must loop or use the automatic logic
        # but with our points.
        
        # For masonry, it's better to segment EACH peak as an individual object.
        # So we'll iterate and combine.
        
        self.report_progress(0.1, f"Segmenting {len(prompts)} relief peaks...")
        
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        label_map = np.zeros((h, w, 3), dtype=np.uint8)
        overlay = image.copy()
        
        areas = []
        centroids = []
        all_contours = []
        
        # ── 3. Model Loading & Embedding ──
        # We always call parent logic to:
        # 1. Load/Switch the model if needed
        # 2. Compute image embedding (set_image) if the image changed
        # We use prompt_mode=0 (Box) to ensure it returns quickly after embedding
        params_init = dict(params)
        params_init['prompt_mode'] = 0 
        res = super().process({'image': image}, params_init)
        
        if self.predictor is None:
            return res

        # ── 4. Depth-Guided Prompt Generation ──
        for i, p in enumerate(prompts):
            self.report_progress(0.1 + (i / len(prompts)) * 0.8, f"Processing stone {i+1}/{len(prompts)}")
            
            # Prepare inputs for parent's single-object predict
            # We bypass the parent's full process() to avoid redundant model loading
            # and to handle multiple objects.
            
            coords = np.array([[p['x'] * w, p['y'] * h]])
            labels = np.array([1])
            
            with torch.inference_mode():
                if self.device == 'cuda':
                    with torch.autocast(self.device, dtype=torch.bfloat16):
                        masks, scores, _ = self.predictor.predict(
                            point_coords=coords,
                            point_labels=labels,
                            multimask_output=False
                        )
                else:
                    masks, scores, _ = self.predictor.predict(
                        point_coords=coords,
                        point_labels=labels,
                        multimask_output=False
                    )
            
            mask = masks[0]
            if hasattr(mask, 'cpu'): mask = mask.detach().cpu().numpy()
            mask_bool = mask > 0
            
            # Color and statistics
            area = float(np.sum(mask_bool))
            areas.append(area)
            centroids.append([p['x'] * w, p['y'] * h])
            
            m_u8 = mask_bool.astype(np.uint8) * 255
            cnts_obj, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts_obj:
                all_contours.append(cnts_obj[0].reshape(-1, 2).tolist())
                # Draw on overlay
                cv2.drawContours(overlay, [cnt_obj.astype(np.int32) for cnt_obj in cnts_obj], -1, (255, 255, 255), 1)

            # Colorize label map
            color = [
                int((i * 67 + 40) % 200 + 55),
                int((i * 137 + 80) % 200 + 55),
                int((i * 197 + 120) % 200 + 55)
            ]
            label_map[mask_bool] = color
            combined_mask[mask_bool] = 255

        # Final Blend
        opacity = float(params.get('overlay_opacity', 50)) / 100.0
        overlay = cv2.addWeighted(image, 1.0 - opacity, label_map, opacity, 0)
        
        # Add peak indicators
        for p in prompts:
            px, py = int(p['x'] * w), int(p['y'] * h)
            cv2.circle(overlay, (px, py), 3, (0, 255, 0), -1)

        self.report_progress(1.0, f"Done: {len(prompts)} objects segmented")
        
        return {
            'main': overlay,
            'mask': combined_mask,
            'count': float(len(prompts)),
            'areas': areas,
            'centroids': centroids,
            'contours': all_contours,
        }
