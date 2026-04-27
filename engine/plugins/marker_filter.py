import cv2
import numpy as np
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="sci_marker_filter",
    label="Marker Filter (Area)",
    category="analysis",
    icon="Scissors",
    description="Filters markers/labels based on their pixel area. Removes objects that are too small or too large.",
    inputs=[{"id": "markers", "color": "any"}],
    outputs=[{"id": "markers", "color": "any"}, {"id": "count", "color": "scalar"}],
    params=[
        {"id": "min_area", "label": "Min Area (px)", "type": "scalar", "min": 0, "max": 1000000, "default": 200},
        {"id": "max_area", "label": "Max Area (px)", "type": "scalar", "min": 0, "max": 10000000, "default": 1000000}
    ]
)
class MarkerFilterNode(NodeProcessor):
    def process(self, inputs, params):
        markers = inputs.get('markers')
        if markers is None:
            return {"markers": None, "count": 0}
            
        # Ensure markers is integer type
        if not np.issubdtype(markers.dtype, np.integer):
            markers = markers.astype(np.int32)
            
        min_area = float(params.get('min_area', 200))
        max_area = float(params.get('max_area', 1000000))
        
        # 1. Fast area calculation using bincount
        # We handle negative labels (like -1 from watershed) by shifting or absolute
        # Actually Watershed uses -1 for boundaries. We should ignore them or handle them.
        
        # Work on a copy to avoid side effects
        filtered_markers = markers.copy()
        
        # Handle watershed boundaries (-1) if present
        has_boundaries = np.any(filtered_markers == -1)
        
        # Flatten and handle labels
        flat = filtered_markers.ravel()
        
        # bincount requires non-negative integers. 
        # Shift everything if there are negative values, or just ignore -1 for area calculation
        # Labels in connectedComponents are 0 (bg), 1, 2...
        # Labels in Watershed are -1 (boundary), 1, 2...
        
        # For simplicity and speed:
        # We only filter labels > 0.
        valid_indices = flat > 0
        if not np.any(valid_indices):
            return {"markers": filtered_markers, "count": 0}
            
        areas = np.bincount(flat[valid_indices])
        
        # Identify labels to delete (area < min or area > max)
        labels = np.where((areas < min_area) | (areas > max_area))[0]
        
        # Note: labels 0 in 'areas' result is for label 0 in 'flat[valid_indices]', 
        # but since we filtered valid_indices, labels[0] actually maps to label 0 which we don't care about.
        # np.bincount(flat[valid_indices]) returns counts for labels 0, 1, 2... up to max(flat)
        # But label 0 doesn't exist in flat[valid_indices].
        
        # Create a lookup table for speed if many labels exist
        # Or just use boolean masking for a few labels
        
        bad_labels = []
        for label_id, area in enumerate(areas):
            if label_id == 0: continue
            if area < min_area or area > max_area:
                bad_labels.append(label_id)
        
        if bad_labels:
            # Efficiently zero out bad labels
            mask = np.isin(filtered_markers, bad_labels)
            filtered_markers[mask] = 0
            
        # Count remaining valid labels
        remaining_count = np.sum(areas >= min_area) - (1 if len(areas) > 0 and areas[0] >= min_area else 0) 
        # The logic above is slightly flawed because areas[0] is not used.
        
        # Simple count:
        final_labels = np.unique(filtered_markers)
        actual_count = len(final_labels[final_labels > 0])
        
        return {
            "markers": filtered_markers,
            "count": actual_count,
            "display_text": f"Items: {actual_count}"
        }
