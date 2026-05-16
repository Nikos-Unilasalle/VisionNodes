import cv2
import numpy as np
import os
import time
from registry import NodeProcessor, vision_node, send_notification

@vision_node(
    type_id="util_snapshot",
    label="Snapshot",
    category='utility',
    icon="Camera",
    description="Captures the current frame and saves it as a new image node in the workspace.",
    inputs=[
        {"id": "image", "label": "Image", "color": "image"},
    ],
    outputs=[
        {"id": "main", "color": "image"},
    ],
    params=[
        {"id": "capture", "label": "Take Snapshot", "type": "trigger", "default": 0},
        {"id": "save_to_disk", "label": "Save as Pict", "type": "trigger", "default": 0}
    ]
)
class SnapshotNode(NodeProcessor):
    def __init__(self, engine=None):
        super().__init__()
        self.last_capture = 0
        self._call_count = 0

    def process(self, inputs, params):
        self._call_count += 1
        
        # Resolve image: connected input > raw_frame fallback
        img = inputs.get('image')
        if img is None:
            img = inputs.get('raw_frame')

        capture = int(params.get('capture', 0))

        # Log every 60th call + every time capture changes to avoid spam
        if self._call_count % 60 == 1 or capture != self.last_capture:
            print(f"[Snapshot] call#{self._call_count} capture={capture} last={self.last_capture} "
                  f"img={'OK ' + str(img.shape) if isinstance(img, np.ndarray) else 'None'} "
                  f"keys={list(inputs.keys())}")

        cmd = None

        # Rising-edge detection: trigger only on 0→1 transition
        if capture == 1 and self.last_capture == 0:
            print(f"[Snapshot] ===== TRIGGER FIRED =====")
            if img is None:
                print(f"[Snapshot] ERROR: No image available (no input connected, no webcam)")
                send_notification("Snapshot: aucune image disponible. Connectez une source.", level='error')
            else:
                try:
                    # Robust path resolution: find project root relative to this file
                    # File is in engine/plugins/snapshot.py -> root is 2 levels up
                    plugin_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(plugin_dir))
                    snap_dir = os.path.join(project_root, "public", "snapshots")

                    if not os.path.exists(snap_dir):
                        os.makedirs(snap_dir, exist_ok=True)
                        print(f"[Snapshot] Created directory: {snap_dir}")

                    # Use millisecond precision to avoid collisions
                    timestamp_ms = int(time.time() * 1000)
                    filename = f"snap_{timestamp_ms}.png"
                    snap_path = os.path.join(snap_dir, filename)

                    # Ensure image is writable BGR
                    save_img = img.copy()
                    if save_img.ndim == 2:
                        save_img = cv2.cvtColor(save_img, cv2.COLOR_GRAY2BGR)
                    elif save_img.ndim == 3 and save_img.shape[2] == 4:
                        save_img = cv2.cvtColor(save_img, cv2.COLOR_BGRA2BGR)

                    res = cv2.imwrite(snap_path, save_img)
                    print(f"[Snapshot] imwrite -> {res}  path={snap_path}")

                    if res:
                        # Use ABSOLUTE path so ImageInput can always find it
                        cmd = {
                            "id": f"snapshot_{timestamp_ms}",
                            "type": "add_node",
                            "node_type": "input_image",
                            "params": {"path": snap_path}
                        }
                        print(f"[Snapshot] Command ready: {cmd}")
                        send_notification(f"Snapshot capturé : {filename}", level='info')
                    else:
                        send_notification("Erreur écriture snapshot", level='error')
                        print(f"[Snapshot] imwrite FAILED for {snap_path}")

                except Exception as e:
                    print(f"[Snapshot] EXCEPTION: {e}")
                    import traceback
                    traceback.print_exc()
                    send_notification(f"Erreur Snapshot: {e}", level='error')

        self.last_capture = capture

        return {
            "main": img,
            "_command": cmd
        }
