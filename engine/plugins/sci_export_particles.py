import cv2
import numpy as np
import os
import time
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='sci_export_particles',
    label='Export Particles',
    category=['out', 'scientific'],
    icon='DownloadCloud',
    description="Exports each detected particle as an individual PNG image with a transparent background.",
    inputs=[
        {'id': 'image', 'color': 'image', 'label': 'Source Image'},
        {'id': 'labels_map', 'color': 'any', 'label': 'Label Map'}
    ],
    outputs=[],
    params=[
        {'id': 'export_trigger', 'label': 'Export Now', 'type': 'toggle', 'default': False},
        {'id': 'out_dir', 'label': 'Output Folder', 'type': 'string', 'default': 'exports/particles'},
        {'id': 'prefix', 'label': 'Prefix', 'type': 'string', 'default': 'stone'},
        {'id': 'pad', 'label': 'Padding (px)', 'type': 'int', 'default': 5, 'min': 0, 'max': 100}
    ]
)
class ExportParticlesNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.last_trigger = False

    def process(self, inputs, params):
        trigger = params.get('export_trigger', False)
        
        # Detect rising edge of the toggle
        if trigger and not self.last_trigger:
            self.last_trigger = True
            
            img = inputs.get('image')
            labels = inputs.get('labels_map')
            
            if img is not None and labels is not None:
                out_dir = params.get('out_dir', 'exports/particles')
                prefix = params.get('prefix', 'stone')
                pad = int(params.get('pad', 5))
                
                # Ensure output directory exists
                if not os.path.exists(out_dir):
                    try:
                        os.makedirs(out_dir)
                    except Exception as e:
                        print(f"Export Error: Cannot create dir {out_dir} -> {e}")
                        out_dir = "."
                
                # Prepare image for BGRA
                if len(img.shape) == 2:
                    img_bgra = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
                elif img.shape[2] == 3:
                    img_bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                else:
                    img_bgra = img.copy()
                
                h, w = labels.shape[:2]
                valid_labels = np.unique(labels)
                valid_labels = valid_labels[valid_labels > 0] # exclude background
                
                timestamp = int(time.time())
                
                exported = 0
                for idx in valid_labels:
                    # Create binary mask for the current particle
                    mask = (labels == idx).astype(np.uint8)
                    
                    # Find bounding box to crop tightly
                    x, y, w_bbox, h_bbox = cv2.boundingRect(mask)
                    
                    # Apply padding
                    x_start = max(0, x - pad)
                    y_start = max(0, y - pad)
                    x_end = min(w, x + w_bbox + pad)
                    y_end = min(h, y + h_bbox + pad)
                    
                    # Crop image and mask
                    img_crop = img_bgra[y_start:y_end, x_start:x_end].copy()
                    mask_crop = mask[y_start:y_end, x_start:x_end] * 255
                    
                    # Apply mask to alpha channel
                    img_crop[:, :, 3] = mask_crop
                    
                    # Save
                    filename = os.path.join(out_dir, f"{prefix}_{timestamp}_{idx:04d}.png")
                    try:
                        cv2.imwrite(filename, img_crop)
                        exported += 1
                    except Exception as e:
                        print(f"Failed to write {filename}: {e}")
                        
                print(f"Exported {exported} particles to {out_dir}")
                
        elif not trigger:
            self.last_trigger = False
            
        return {}
