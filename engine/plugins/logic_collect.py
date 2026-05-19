import csv
import os
import time
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='logic_collect',
    label='Collect',
    category='logic',
    icon='ListPlus',
    description="Accumule des valeurs dans une liste quand la condition est vraie. Exporte en CSV à la demande.",
    inputs=[
        {'id': 'condition', 'label': 'Condition', 'color': 'boolean'},
        {'id': 'value',     'label': 'Value',     'color': 'any'},
        {'id': 'image',     'label': 'Image',     'color': 'image'},
    ],
    outputs=[
        {'id': 'list',  'label': 'List',  'color': 'list'},
        {'id': 'count', 'label': 'Count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'mode',       'label': 'Mode',      'type': 'enum',    'options': ['Every True frame', 'Rising edge only', 'Check every N frames'], 'default': 0},
        {'id': 'interval',   'label': 'Check every N',   'type': 'int',     'default': 30, 'min': 1, 'max': 500},
        {'id': 'reset',      'label': 'Reset List', 'type': 'trigger', 'default': 0},
        {'id': 'export',     'label': 'Export CSV', 'type': 'trigger', 'default': 0},
        {'id': 'filename',   'label': 'Filename',   'type': 'string',  'default': 'collected'},
        {'id': 'path',       'label': 'Folder',     'type': 'string',  'default': 'exports'},
    ]
)
class LogicCollectNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._list = []
        self._last_condition = False
        self._last_reset = 0
        self._last_export = 0
        self._cooldown = 0

    def process(self, inputs, params):
        condition = bool(inputs.get('condition', False))
        value = inputs.get('value')
        mode = int(params.get('mode', 0))
        interval = int(params.get('interval', 30))
        reset_trig = int(params.get('reset', 0))
        export_trig = int(params.get('export', 0))

        if reset_trig == 1 and self._last_reset == 0:
            self._list = []
            self._cooldown = 0
        self._last_reset = reset_trig

        if mode == 0:
            should_append = condition
        elif mode == 1:
            should_append = condition and not self._last_condition
        else:
            if self._cooldown > 0:
                self._cooldown -= 1
                should_append = False
            elif condition:
                should_append = True
                self._cooldown = interval
            else:
                should_append = False

        if should_append and value is not None:
            self._list.append(value)

        self._last_condition = condition

        if export_trig == 1 and self._last_export == 0:
            self._export_csv(params)
        self._last_export = export_trig

        return {
            'list':  list(self._list),
            'count': len(self._list),
        }

    def _export_csv(self, params):
        export_dir = params.get('path', 'exports')
        filename   = params.get('filename', 'collected')
        os.makedirs(export_dir, exist_ok=True)
        ts   = int(time.time())
        path = os.path.join(export_dir, f"{filename}_{ts}.csv")
        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['index', 'value'])
                for i, v in enumerate(self._list):
                    if isinstance(v, float):
                        writer.writerow([i, f"{v:.6f}"])
                    else:
                        writer.writerow([i, v])
            print(f"[Collect] {len(self._list)} rows → {path}")
        except Exception as e:
            print(f"[Collect] Export error: {e}")
