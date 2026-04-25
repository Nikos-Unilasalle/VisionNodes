from registry import vision_node, NodeProcessor
import cv2
import os
import time

@vision_node(
    type_id='output_movie',
    label='Movie Export',
    category='out',
    icon='Film',
    description='Records frames to MP4. Stream mode captures from pipeline; Webcam mode records directly from camera and creates a Movie node on stop.',
    inputs=[
        {'id': 'image', 'color': 'image'}
    ],
    outputs=[],
    params=[
        {'id': 'mode', 'label': 'Mode', 'type': 'enum', 'options': ['Stream Recording', 'Webcam Direct'], 'default': 0},
        {'id': 'recording', 'label': 'Recording', 'type': 'toggle', 'default': False},
        {'id': 'output_path', 'label': 'Output Path', 'type': 'string', 'default': ''},
        {'id': 'fps', 'label': 'FPS', 'type': 'number', 'default': 30},
    ]
)
class MovieExportNode(NodeProcessor):
    def __init__(self, engine=None):
        self.engine = engine
        self.writer = None
        self.was_recording = False
        self.save_path = None
        self.frame_count = 0
        self.writer_size = (640, 480)

    def _start_writer(self, img, path, fps):
        if not path:
            return
        if not path.lower().endswith('.mp4'):
            path = path + '.mp4'
        h, w = img.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(path, fourcc, float(fps), (w, h))
        self.writer_size = (w, h)
        self.save_path = path
        self.frame_count = 0
        print(f"[MovieExport] Recording started → {path} ({w}x{h} @ {fps}fps)")

    def _stop_writer(self):
        if self.writer:
            self.writer.release()
            self.writer = None
            print(f"[MovieExport] Saved {self.frame_count} frames → {self.save_path}")

    def __del__(self):
        if self.writer:
            self.writer.release()

    def process(self, inputs, params):
        mode = int(params.get('mode', 0))
        recording = bool(params.get('recording', False))
        output_path = str(params.get('output_path', '')).strip()
        fps = max(1, int(params.get('fps', 30)))

        img = inputs.get('image') if mode == 0 else inputs.get('raw_frame')

        command = None

        if recording and not self.was_recording:
            if img is not None and output_path:
                self._start_writer(img, output_path, fps)

        if recording and self.writer is not None and img is not None:
            frame = img if (len(img.shape) == 3 and img.shape[2] == 3) else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if (frame.shape[1], frame.shape[0]) != self.writer_size:
                frame = cv2.resize(frame, self.writer_size)
            self.writer.write(frame)
            self.frame_count += 1

        if not recording and self.was_recording:
            saved = self.save_path
            self._stop_writer()
            if mode == 1 and saved:
                command = {
                    'type': 'add_node',
                    'node_type': 'input_movie',
                    'params': {'path': saved, 'playing': True}
                }

        self.was_recording = recording

        out = {}
        if command:
            out['_command'] = command
        if self.frame_count > 0:
            out['frame_count'] = self.frame_count
        return out
