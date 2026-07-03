"""DF Collect — accumulates DataFrames arriving over time into one concatenated DataFrame.

Generic batch-processing buffer: use with any per-tick DataFrame producer (chart digitizing,
per-frame measurements…) to build one final table before a single DF Export write.
"""
from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'df_collect'

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False


@vision_node(
    type_id='df_collect',
    label='DF Collect',
    category='DataFrame',
    icon='Layers',
    description="Accumulates incoming DataFrames into one growing table. Auto-captures whenever the "
                "'seq' input changes (e.g. a folder iterator's index) — perfect for batch pipelines. "
                "Without 'seq' connected, use the Capture trigger manually. Connect to DF Export at the end.",
    inputs=[
        {'id': 'table', 'color': 'data',   'label': 'DataFrame'},
        {'id': 'seq',   'color': 'scalar', 'label': 'Sequence (auto-capture on change)'},
    ],
    outputs=[{'id': 'data', 'color': 'data'}],
    params=[
        {'id': 'capture', 'label': 'Capture Now', 'type': 'trigger', 'default': 0},
        {'id': 'reset',   'label': 'Clear',       'type': 'trigger', 'default': 0},
    ]
)
class DFCollectNode(NodeProcessor):
    def __init__(self, engine=None):
        self.buffer = []
        self.last_seq = None
        self.last_capture = 0
        self.last_reset = 0

    def process(self, inputs, params):
        if not _PD_OK:
            send_notification("DF Collect: pandas not installed", level='error', notif_id=_NOTIF)
            return {}

        reset_trig = int(params.get('reset', 0))
        if reset_trig and not self.last_reset:
            self.buffer = []
            self.last_seq = None
        self.last_reset = reset_trig

        table = inputs.get('table')
        seq = inputs.get('seq')
        capture_trig = int(params.get('capture', 0))

        should_capture = False
        if seq is not None:
            if seq != self.last_seq:
                should_capture = True
                self.last_seq = seq
        elif capture_trig and not self.last_capture:
            should_capture = True
        self.last_capture = capture_trig

        if should_capture and isinstance(table, pd.DataFrame) and not table.empty:
            self.buffer.append(table)
            send_notification(f"DF Collect: {len(self.buffer)} tables, {sum(len(t) for t in self.buffer)} rows",
                               level='info', notif_id=_NOTIF)

        captured = len(self.buffer)
        rows = sum(len(t) for t in self.buffer)
        if not self.buffer:
            return {'data': pd.DataFrame(), 'captured': 0, 'rows': 0}
        return {'data': pd.concat(self.buffer, ignore_index=True), 'captured': captured, 'rows': rows}
