import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='util_visual_overlay',
    label='Visual Overlay',
    category='visualize',
    icon='Layout',
    description="Superimposes AI detections (YOLO, MediaPipe, etc.) over an image. Connect detection lists to the 'data' inputs.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'data', 'color': 'any'},
        {'id': 'data_2', 'color': 'any'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}]
)
class VisualOverlayNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image', inputs.get('main', inputs.get('raw_frame')))
        if img is None: return {"main": None}
        res = img.copy()
        if len(res.shape) == 2: res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)
        h, w = res.shape[:2]
        
        # Default styling for detections
        col = (0, 255, 0)
        thick = 2
        
        for key, data in inputs.items():
            if data is None or key == 'image': continue
            
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict): continue
                
                # Check for standard detection box (xmin, ymin, width, height)
                if 'xmin' in item and 'ymin' in item:
                    x1 = int(item['xmin'] * w)
                    y1 = int(item['ymin'] * h)
                    
                    if 'width' in item and 'height' in item:
                        x2 = x1 + int(item['width'] * w)
                        y2 = y1 + int(item['height'] * h)
                    elif 'xmax' in item and 'ymax' in item:
                        x2 = int(item['xmax'] * w)
                        y2 = int(item['ymax'] * h)
                    else:
                        continue
                        
                    # Draw box
                    cv2.rectangle(res, (x1, y1), (x2, y2), col, thick)
                    
                    # Draw label
                    label = item.get('label', item.get('class', ''))
                    conf = item.get('confidence', item.get('score'))
                    if conf is not None:
                        label += f" {float(conf):.2f}"
                    
                    if label:
                        cv2.putText(res, label, (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
                                    
                # Support for landmarks if present
                if 'landmarks' in item:
                    for lm in item['landmarks']:
                        lx, ly = int(lm['x'] * w), int(lm['y'] * h)
                        cv2.circle(res, (lx, ly), 2, (0, 0, 255), -1)
        
        return {"main": res}
