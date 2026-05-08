from registry import vision_node, NodeProcessor

class _PassThrough(dict):
    """Returns the single pass-through value for any key — supports dynamic fan-out outputs."""
    def __init__(self, val):
        self._val = val
        super().__init__({'out': val, 'main': val, 'image': val, 'data': val})
    def get(self, key, default=None): return self._val
    def __getitem__(self, key): return self._val
    def __contains__(self, key): return True

@vision_node(
    type_id="note",
    label="Note",
    category='canvas',
    icon="StickyNote",
    description="Adds a textual annotation or comment to the workspace.",
    params=[{"id": "text", "label": "Text", "type": "string", "multiline": True, "default": "Write something..."}]
)
class NoteNode(NodeProcessor):
    def process(self, inputs, params): return {}

@vision_node(
    type_id="group_frame",
    label="Frame",
    category='canvas',
    icon="Square",
    description="Groups multiple nodes visually inside a frame."
)
class FrameNode(NodeProcessor):
    def process(self, inputs, params): return {}

@vision_node(
    type_id="reroute",
    label="Reroute",
    category='canvas',
    icon="GitCommit",
    description="Helper to organize connection lines and fan out signals.",
    inputs=[{"id": "in", "color": "any"}],
    outputs=[{"id": "out", "color": "any"}]
)
class RerouteNode(NodeProcessor):
    def process(self, inputs, params):
        val = inputs.get('in')
        return _PassThrough(val)
