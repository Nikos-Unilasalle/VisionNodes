import cv2
import os
import time
from __main__ import NodeProcessor, vision_node

@vision_node(
    type_id="util_snapshot",
    label="Snapshot",
    category="util",
    icon="Camera",
    description="Captures the current frame and saves it as a new image node in the workspace.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "main", "color": "image"}],
    params=[
        {"id": "capture", "label": "Take Snapshot", "type": "trigger", "default": 0}
    ]
)
class SnapshotNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.last_capture = 0

    def process(self, inputs, params):
        img = inputs.get('image')
        capture = int(params.get('capture', 0))
        
        cmd = None
        if capture == 1 and self.last_capture == 0:
            if img is not None:
                # 1. Create directory
                snap_dir = os.path.join(os.getcwd(), "public", "snapshots")
                if not os.path.exists(snap_dir):
                    os.makedirs(snap_dir)
                
                # 2. Save image
                timestamp = int(time.time())
                filename = f"snap_{timestamp}.png"
                filepath = os.path.join(snap_dir, filename)
                cv2.imwrite(filepath, img)
                
                # 3. Prepare command for the frontend
                # Path relative to public/ for the frontend server
                cmd = {
                    "type": "add_node",
                    "id": f"snapshot_{timestamp}",
                    "node_type": "input_image",
                    "params": {"path": f"snapshots/{filename}"}
                }
        
        self.last_capture = capture
        
        return {
            "main": img,
            "_command": cmd # Internal key for logic signaling
        }
