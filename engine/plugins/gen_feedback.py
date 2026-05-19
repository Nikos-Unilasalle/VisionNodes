import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='gen_feedback',
    label='Feedback',
    category='utility',
    icon='RefreshCw',
    description="Outputs the previous frame's image. Essential for iterative algorithms (reaction-diffusion, cellular automata, blur loops). Output lags input by exactly 1 frame.",
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'init',  'color': 'image'},
        {'id': 'reset', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'prev', 'color': 'image'},
    ],
    params=[
        {'id': 'width',  'label': 'Width (init)',  'type': 'int', 'default': 512, 'min': 16, 'max': 2048},
        {'id': 'height', 'label': 'Height (init)', 'type': 'int', 'default': 512, 'min': 16, 'max': 2048},
    ]
)
class FeedbackNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._stored = None
        self._prev_reset = 0.0

    def process(self, inputs, params):
        image = inputs.get('image')
        init  = inputs.get('init')
        reset_raw = inputs.get('reset', 0)

        try:
            reset = float(reset_raw) if reset_raw is not None else 0.0
        except (TypeError, ValueError):
            reset = 0.0

        if reset > 0.5 and self._prev_reset <= 0.5:
            self._stored = None
        self._prev_reset = reset

        # Output: stored frame (or init/zeros on first frame)
        if self._stored is None:
            if init is not None:
                out = init.astype(np.float32).copy()
            elif image is not None:
                out = np.zeros_like(image, dtype=np.float32)
            else:
                w = int(params.get('width', 512))
                h = int(params.get('height', 512))
                out = np.zeros((h, w), dtype=np.float32)
        else:
            out = self._stored

        # Store current input for next frame
        if image is not None:
            self._stored = image.astype(np.float32).copy()

        return {'prev': out}
