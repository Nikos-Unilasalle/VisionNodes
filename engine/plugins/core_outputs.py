import cv2
from registry import vision_node, NodeProcessor

def flatten_groups(node_list, edge_list, prefix=''):
    """Utility to flatten grouped node outputs into a single list of results."""
    # Placeholder for recursive group expansion logic if needed
    return node_list

@vision_node(
    type_id="output_display",
    label="Display Output",
    category='out',
    icon="Monitor",
    description="Final visualization node. Renders the image stream to the UI.",
    inputs=[{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}],
    outputs=[]
)
class DisplayOutput(NodeProcessor):
    def process(self, inputs, params):
        res = inputs.get('main')
        mask = inputs.get('mask')
        if res is None: return {"main": None}
        if len(res.shape) == 2: res = cv2.cvtColor(res, cv2.COLOR_GRAY2BGR)
        if mask is not None:
            if mask.shape[:2] != res.shape[:2]:
                mask = cv2.resize(mask, (res.shape[1], res.shape[0]))
            overlay = res.copy()
            m_bin = mask if len(mask.shape) == 2 else cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            overlay[m_bin > 0] = [0, 0, 255]
            res = cv2.addWeighted(overlay, 0.4, res, 0.6, 0)
        return {"main": res}
