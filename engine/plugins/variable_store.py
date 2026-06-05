"""
Variable — a stateful accumulator / register.

Holds a value across graph runs. Two data inputs:
- append : each new value arriving here is added to the store
- replace: each new value arriving here overwrites the store

Outputs the value as text (joined), as a list, and a count. Useful for
collecting LLM turns, logging events, building lists incrementally, etc.
"""
from registry import vision_node, NodeProcessor
import json


@vision_node(
    type_id='variable_store',
    label='Variable',
    category='data',
    icon='Variable',
    description=(
        "Stateful accumulator. Connect to 'append' to add values one by one, "
        "or 'replace' to overwrite. Outputs the collected value as joined text, "
        "as a list, and a count. Press Clear to reset."
    ),
    inputs=[
        {'id': 'append',  'color': 'any',    'label': 'Append'},
        {'id': 'replace', 'color': 'any',    'label': 'Replace'},
        {'id': 'reset',   'color': 'scalar', 'label': 'Reset (>0.5)'},
    ],
    outputs=[
        {'id': 'text',  'color': 'string', 'label': 'Text (joined)'},
        {'id': 'list',  'color': 'list',   'label': 'List'},
        {'id': 'count', 'color': 'scalar', 'label': 'Count'},
        {'id': 'last',  'color': 'string', 'label': 'Last'},
    ],
    params=[
        {'id': 'separator', 'label': 'Text Separator', 'type': 'string', 'default': '\n'},
        {'id': 'clear',     'label': 'Clear', 'type': 'trigger', 'default': False},
        {'id': 'max_items', 'label': 'Max Items (0=unlimited)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 10000},
    ],
    colorable=True,
)
class VariableStoreNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._items: list = []
        self._last_append = None
        self._last_replace = None
        self._prev_reset = 0.0

    def _coerce(self, v):
        if isinstance(v, str):
            return v
        if isinstance(v, (int, float, bool)):
            return v
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)

    def _emit(self, params):
        sep = params.get('separator', '\n')
        text_items = [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
                      for x in self._items]
        return {
            'text':  sep.join(text_items),
            'list':  list(self._items),
            'count': float(len(self._items)),
            'last':  text_items[-1] if text_items else '',
        }

    def process(self, inputs, params):
        # Reset: trigger param OR reset port rising edge
        reset_now = bool(params.get('clear', False))
        try:
            r = float(inputs.get('reset', 0) or 0)
        except (TypeError, ValueError):
            r = 0.0
        if r > 0.5 and self._prev_reset <= 0.5:
            reset_now = True
        self._prev_reset = r
        if reset_now:
            self._items = []
            self._last_append = None
            self._last_replace = None
            return self._emit(params)

        max_items = int(params.get('max_items', 0))

        # Replace: overwrite store when the replace input changes
        rep = inputs.get('replace')
        if rep is not None:
            key = self._coerce(rep)
            if key != self._last_replace:
                self._last_replace = key
                self._items = [self._coerce(rep)]

        # Append: add when the append input changes
        app = inputs.get('append')
        if app is not None:
            key = self._coerce(app)
            if key != self._last_append:
                self._last_append = key
                self._items.append(self._coerce(app))
                if max_items > 0 and len(self._items) > max_items:
                    self._items = self._items[-max_items:]

        return self._emit(params)
