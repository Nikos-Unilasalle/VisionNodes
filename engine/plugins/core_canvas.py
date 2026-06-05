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
    type_id="canvas_note",
    label="Note",
    category='canvas',
    icon="StickyNote",
    description=(
        "Sticky note. Optionally connect a text input to feed it dynamically — "
        "append mode logs each incoming string (e.g. an LLM transcript), "
        "replace mode overwrites. Leave the input unconnected for a normal "
        "hand-edited note."
    ),
    inputs=[{"id": "text", "color": "any", "label": "Text In"}],
    params=[
        {"id": "text", "label": "Text", "type": "string", "multiline": True,
         "default": "Write something..."},
        {"id": "mode", "label": "Input Mode", "type": "enum",
         "options": ["Append", "Replace"], "default": 0},
        {"id": "separator", "label": "Append Separator", "type": "string", "default": "\n\n"},
        {"id": "clear", "label": "Clear", "type": "trigger", "default": False},
    ],
)
class CanvasNoteNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._acc = None          # accumulated text (append mode)
        self._last_input = None   # dedupe guard

    def process(self, inputs, params):
        # Clear trigger resets the accumulator and blanks the note.
        if bool(params.get('clear', False)):
            self._acc = ''
            self._last_input = None
            return {"_command": {"type": "set_param", "node_id": "__self__",
                                 "params": {"text": ""}}}

        incoming = inputs.get('text')
        if incoming is None:
            return {}   # no input connected → leave the hand-edited note untouched

        if not isinstance(incoming, str):
            try:
                import json as _json
                incoming = _json.dumps(incoming, ensure_ascii=False, indent=2)
            except Exception:
                incoming = str(incoming)

        # Dedupe: only act when the input actually changes (graph re-runs each tick)
        if incoming == self._last_input:
            return {}
        self._last_input = incoming

        mode = int(params.get('mode', 0))   # 0=append, 1=replace
        if mode == 1:
            new_text = incoming
        else:
            sep = params.get('separator', '\n\n')
            if self._acc is None:
                # Seed from the current note text (skip the placeholder default)
                seed = params.get('text', '') or ''
                self._acc = '' if seed.strip() in ('', 'Write something...') else seed
            self._acc = (self._acc + sep + incoming) if self._acc else incoming
            new_text = self._acc

        return {"_command": {"type": "set_param", "node_id": "__self__",
                             "params": {"text": new_text}}}

@vision_node(
    type_id="canvas_frame",
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
