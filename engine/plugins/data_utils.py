import numpy as np
from registry import NodeProcessor, vision_node

@vision_node(
    type_id="util_landmark_selector",
    label="Landmark Selector",
    category="util",
    icon="Target",
    description="Selects specific points from a landmark list (e.g., torso from pose).",
    inputs=[{"id": "data", "color": "dict"}],
    outputs=[{"id": "data", "color": "dict"}],
    params=[
        {"id": "indices", "label": "Indices (ex: 11,12,24,23)", "type": "string", "default": "11,12,24,23"}
    ]
)
class LandmarkSelectorNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        if not data or 'landmarks' not in data:
            return {"data": {}}
        
        lms = data['landmarks']
        indices_str = params.get('indices', "11,12,24,23")
        
        try:
            # Parse indices: supports commas and spaces
            idx_list = [int(i.strip()) for i in indices_str.replace(',', ' ').split() if i.strip()]
            
            filtered_lms = []
            for idx in idx_list:
                if 0 <= idx < len(lms):
                    filtered_lms.append(lms[idx])
            
            if not filtered_lms:
                return {"data": {}}
            
            # Create a new data object following the standard detection format
            new_data = dict(data) # Copy metadata (color, etc.)
            new_data['landmarks'] = filtered_lms
            new_data['pts'] = [[p['x'], p['y']] for p in filtered_lms]
            
            # Update bounding box for the filtered points
            xs = [p['x'] for p in filtered_lms]
            ys = [p['y'] for p in filtered_lms]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            new_data['xmin'] = xmin
            new_data['ymin'] = ymin
            new_data['width'] = xmax - xmin
            new_data['height'] = ymax - ymin
            
            return {"data": new_data}
            
        except Exception as e:
            print(f"[LandmarkSelector] Error: {e}")
            return {"data": {}}
