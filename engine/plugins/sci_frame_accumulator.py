import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_MODES = ['Running Mean', 'Running Max', 'Running Min', 'Running Std', 'Temporal Diff']

@vision_node(
    type_id='sci_frame_accumulator',
    label='Frame Accumulator',
    category=['analysis', 'scientific'],
    icon='Film',
    description="Accumulate frames over time: mean (noise reduction), std (motion map), temporal diff, running max/min.",
    inputs=[{'id': 'image', 'color': 'any'}],
    outputs=[
        {'id': 'main',        'color': 'image',  'label': 'Result'},
        {'id': 'frame_count', 'color': 'scalar', 'label': 'Buffer Size'},
    ],
    params=[
        {'id': 'mode',   'label': 'Mode',           'type': 'enum', 'options': _MODES, 'default': 0},
        {'id': 'window', 'label': 'Window (frames)', 'type': 'int',  'default': 16, 'min': 2, 'max': 128},
        {'id': 'reset',  'label': 'Reset Buffer',    'type': 'bool', 'default': False},
    ]
)
class FrameAccumulatorNode(NodeProcessor):
    def __init__(self):
        self._buffer = []
        self._last_reset = False

    def process(self, inputs, params):
        img    = inputs.get('image')
        do_reset = bool(params.get('reset', False))

        # Edge-triggered reset: clear only on False→True transition
        if do_reset and not self._last_reset:
            self._buffer = []
        self._last_reset = do_reset

        if img is None:
            return {'main': None, 'frame_count': 0}

        if img.dtype != np.uint8:
            img = (img * 255).clip(0, 255).astype(np.uint8) if img.max() <= 1.1 else img.clip(0, 255).astype(np.uint8)

        window = int(params.get('window', 16))
        mode   = int(params.get('mode', 0))

        self._buffer.append(img.astype(np.float32))
        if len(self._buffer) > window:
            self._buffer.pop(0)

        stack = np.stack(self._buffer, axis=0)

        if mode == 0:   # Running Mean
            result = np.mean(stack, axis=0)
        elif mode == 1: # Running Max
            result = np.max(stack, axis=0)
        elif mode == 2: # Running Min
            result = np.min(stack, axis=0)
        elif mode == 3: # Running Std — normalized to 0-255
            s = np.std(stack, axis=0)
            m = float(s.max())
            result = (s / (m + 1e-8) * 255) if m > 0 else s
        else:           # Temporal Diff
            if len(self._buffer) >= 2:
                result = np.abs(self._buffer[-1] - self._buffer[-2]) * 4.0
            else:
                result = stack[0]

        return {
            'main':        result.clip(0, 255).astype(np.uint8),
            'frame_count': len(self._buffer),
        }
