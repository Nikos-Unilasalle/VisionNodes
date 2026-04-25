import cv2
import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="sci_marker_analysis",
    label="Marker Analysis",
    category="analysis",
    icon="Hash",
    description="Extracts data (ID, coordinates, area) from a label map (markers) and overlays IDs.",
    inputs=[{"id": "markers", "color": "any"}, {"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "data_list", "color": "list"}, {"id": "count", "color": "scalar"}],
    params=[
        {"id": "show_labels", "label": "Show IDs", "type": "enum", "options": ["No", "Yes"], "default": 1},
        {"id": "show_points", "label": "Show Centroids", "type": "enum", "options": ["No", "Yes"], "default": 1},
        {"id": "font_scale", "label": "Font Scale", "type": "scalar", "min": 0.1, "max": 2.0, "default": 0.6},
        {"id": "thickness", "label": "Thickness", "type": "scalar", "min": 1, "max": 5, "default": 1},
        {"id": "coord_type", "label": "Coordinates", "type": "enum", "options": ["Relative (0-1)", "Pixels"], "default": 0},
        {"id": "text_color", "label": "Text Color", "type": "enum", "options": ["Green", "Red", "Blue", "White", "Black", "Yellow"], "default": 0}
    ]
)
class MarkerAnalysisNode(NodeProcessor):
    def process(self, inputs, params):
        markers = inputs.get('markers')
        img = inputs.get('image')
        
        if markers is None:
            return {"main": img, "data_list": [], "count": 0}
            
        # Ensure markers is int32
        if markers.dtype != np.int32:
            markers = markers.astype(np.int32)
            
        h, w = markers.shape[:2]
        
        # Visualization setup
        if img is not None:
            out_img = img.copy()
            if len(out_img.shape) == 2:
                out_img = cv2.cvtColor(out_img, cv2.COLOR_GRAY2BGR)
        else:
            out_img = np.zeros((h, w, 3), dtype=np.uint8)
            
        show_labels = int(params.get('show_labels', 1)) == 1
        show_points = int(params.get('show_points', 1)) == 1
        font_scale = float(params.get('font_scale', 0.6))
        thickness = int(params.get('thickness', 1))
        is_relative = int(params.get('coord_type', 0)) == 0
        
        color_idx = int(params.get('text_color', 0))
        bgr_colors = [(0, 255, 0), (0, 0, 255), (255, 0, 0), (255, 255, 255), (0, 0, 0), (0, 255, 255)]
        hex_colors = ["#00ff00", "#ff0000", "#0000ff", "#ffffff", "#000000", "#ffff00"]
        color = bgr_colors[min(color_idx, len(bgr_colors)-1)]
        color_hex = hex_colors[min(color_idx, len(hex_colors)-1)]
        
        # Efficiently extract stats
        # Watershed markers: -1 is boundary, 1, 2, 3... are labels.
        # connectedComponents markers: 0 is background, 1, 2, 3... are labels.
        
        data_list = []
        labels = np.unique(markers)
        
        # Exclude background/boundaries
        # We usually care about labels > 0
        valid_labels = labels[labels > 0]
        count = len(valid_labels)
        
        for label_id in valid_labels:
            # Get mask for this label
            # Note: For many labels, this is the slowest part.
            # But it's robust for any label map.
            item_mask = (markers == label_id).astype(np.uint8)
            M = cv2.moments(item_mask)
            
            if M["m00"] > 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                area = float(M["m00"])
                
                # Prepare data
                x_final = cx / w if is_relative else cx
                y_final = cy / h if is_relative else cy
                
                data_list.append({
                    "id": int(label_id),
                    "label": f"#{label_id}",
                    "x": float(x_final),
                    "y": float(y_final),
                    "area": area,
                    "center": {"x": float(cx/w), "y": float(cy/h)},
                    "_type": "graphics",
                    "shape": "point",
                    "pts": [[float(cx/w), float(cy/h)]],
                    "relative": True,
                    "color": color_hex
                })
                
                # Overlay
                px, py = int(cx), int(cy)
                if show_points:
                    cv2.circle(out_img, (px, py), 3, color, -1)
                if show_labels:
                    cv2.putText(out_img, str(label_id), (px + 5, py - 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        
        return {
            "main": out_img,
            "data_list": data_list,
            "count": count,
            "display_text": f"Islands: {count}"
        }
