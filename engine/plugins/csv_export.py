from registry import vision_node, NodeProcessor
import csv
import time
import os

@vision_node(
    type_id='util_csv_export',
    label='CSV Export',
    category='out',
    icon='Database',
    description="Expote les données vers un fichier CSV. Un nouveau fichier est créé à chaque activation.",
    inputs=[
        {'id': 'val_1', 'color': 'any'},
        {'id': 'val_2', 'color': 'any'},
        {'id': 'val_3', 'color': 'any'},
        {'id': 'val_4', 'color': 'any'},
        {'id': 'val_5', 'color': 'any'},
        {'id': 'val_6', 'color': 'any'},
        {'id': 'val_7', 'color': 'any'},
        {'id': 'val_8', 'color': 'any'}
    ],
    outputs=[],
    params=[
        {'id': 'record', 'label': 'Recording', 'type': 'toggle', 'default': False},
        {'id': 'filename', 'label': 'Base Name', 'type': 'string', 'default': 'capture'},
        {'id': 'path', 'label': 'Folder Path', 'type': 'string', 'default': 'exports'},
        {'id': 'auto_timestamp', 'label': 'Auto Timestamp', 'type': 'bool', 'default': True}
    ]
)
class CSVExportNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.active_file = None
        self.last_record_status = False
        self._fh = None
        self._writer = None

    def _close_file(self):
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception as e:
                print(f"CSV Export: close error: {e}")
            self._fh = None
            self._writer = None

    def process(self, inputs, params):
        record = params.get('record', False)

        if record and not self.last_record_status:
            self._close_file()
            base_name = params.get('filename', 'capture')
            export_dir = params.get('path', 'exports')
            auto_time = params.get('auto_timestamp', True)

            if not os.path.exists(export_dir):
                try:
                    os.makedirs(export_dir)
                except Exception as e:
                    print(f"CSV Export Error: Cannot create dir {export_dir} -> {e}")
                    export_dir = "."

            ts = f"_{int(time.time())}" if auto_time else ""
            self.active_file = os.path.join(export_dir, f"{base_name}{ts}.csv")

            try:
                self._fh = open(self.active_file, 'w', newline='')
                self._writer = csv.writer(self._fh)
                header = ['timestamp'] + [f'val_{i}' for i in range(1, 9)]
                self._writer.writerow(header)
                self._fh.flush()
            except Exception as e:
                print(f"CSV Export: cannot open file: {e}")
                self._close_file()

        if not record and self.last_record_status:
            self._close_file()

        self.last_record_status = record

        if not record or self._writer is None:
            return {}

        try:
            vals = [f"{time.time():.6f}"]
            for i in range(1, 9):
                v = inputs.get(f'val_{i}')
                if v is None:
                    vals.append("")
                elif isinstance(v, (int, float)):
                    vals.append(f"{v:.6f}")
                else:
                    vals.append(str(v))
            self._writer.writerow(vals)
            self._fh.flush()
        except Exception as e:
            print(f"Erreur d'écriture CSV: {e}")

        return {}
