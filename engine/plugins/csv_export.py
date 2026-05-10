from registry import vision_node, NodeProcessor
import csv
import time
import os

_SCALAR = (int, float, str, bool, type(None))

@vision_node(
    type_id='util_csv_export',
    label='CSV Export',
    category='out',
    icon='Database',
    description="Exports data to CSV. Dynamic inputs — connect any value to add a column. Use Recording for live streams or Snapshot for single-frame capture.",
    dynamic_inputs=True,
    inputs=[],
    outputs=[],
    params=[
        {'id': 'record',          'label': 'Recording',       'type': 'toggle', 'default': False},
        {'id': 'snapshot',        'label': 'Snapshot',        'type': 'trigger', 'default': 0},
        {'id': 'filename',        'label': 'Base Name',       'type': 'string',  'default': 'capture'},
        {'id': 'path',            'label': 'Folder Path',     'type': 'string',  'default': 'exports'},
        {'id': 'auto_timestamp',  'label': 'Auto Timestamp',  'type': 'bool',    'default': True},
    ]
)
class CSVExportNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.active_file = None
        self.last_record_status = False
        self._fh = None
        self._writer = None
        self._columns = []
        self._snap_file = None
        self._snap_columns = []
        self._snap_fh = None
        self._snap_writer = None

    def _scalars(self, inputs):
        return {k: v for k, v in inputs.items() if isinstance(v, _SCALAR)}

    def _close_file(self):
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception as e:
                print(f"CSV Export: close error: {e}")
            self._fh = None
            self._writer = None
            self._columns = []

    def _make_path(self, params):
        base_name  = params.get('filename', 'capture')
        export_dir = params.get('path', 'exports')
        auto_time  = params.get('auto_timestamp', True)
        if not os.path.exists(export_dir):
            try:
                os.makedirs(export_dir)
            except Exception as e:
                print(f"CSV Export: cannot create dir {export_dir}: {e}")
                export_dir = "."
        ts = f"_{int(time.time())}" if auto_time else ""
        return os.path.join(export_dir, f"{base_name}{ts}.csv")

    def _open_stream(self, inputs, params):
        self._close_file()
        path = self._make_path(params)
        self._columns = list(self._scalars(inputs).keys())
        try:
            self._fh = open(path, 'w', newline='')
            self._writer = csv.writer(self._fh)
            self._writer.writerow(['timestamp'] + self._columns)
            self._fh.flush()
            self.active_file = path
        except Exception as e:
            print(f"CSV Export: cannot open file: {e}")
            self._close_file()

    def _write_row(self, inputs):
        if self._writer is None:
            return
        try:
            row = [f"{time.time():.6f}"] + [
                f"{v:.6f}" if isinstance(v, (int, float)) else ("" if v is None else str(v))
                for v in (inputs.get(c) for c in self._columns)
            ]
            self._writer.writerow(row)
            self._fh.flush()
        except Exception as e:
            print(f"CSV Export: write error: {e}")

    def process(self, inputs, params):
        record   = params.get('record', False)
        snapshot = params.get('snapshot', 0)

        # ── Snapshot: append one row per click; new file only on first click or column change ──
        if snapshot:
            cols = list(self._scalars(inputs).keys())
            if self._snap_writer is None or cols != self._snap_columns:
                if self._snap_fh is not None:
                    try: self._snap_fh.close()
                    except: pass
                path = self._make_path(params)
                try:
                    self._snap_fh = open(path, 'w', newline='')
                    self._snap_writer = csv.writer(self._snap_fh)
                    self._snap_writer.writerow(['timestamp'] + cols)
                    self._snap_columns = cols
                    self._snap_file = path
                    print(f"CSV Export: snapshot file → {path}")
                except Exception as e:
                    print(f"CSV Export: snapshot open error: {e}")
                    self._snap_fh = None; self._snap_writer = None
            if self._snap_writer is not None:
                try:
                    row = [f"{time.time():.6f}"] + [
                        f"{inputs[c]:.6f}" if isinstance(inputs[c], (int, float))
                        else ("" if inputs[c] is None else str(inputs[c]))
                        for c in self._snap_columns
                    ]
                    self._snap_writer.writerow(row)
                    self._snap_fh.flush()
                except Exception as e:
                    print(f"CSV Export: snapshot write error: {e}")

        # ── Streaming record ──────────────────────────────────────────────
        if record and not self.last_record_status:
            self._open_stream(inputs, params)

        if not record and self.last_record_status:
            self._close_file()

        self.last_record_status = record

        if record and self._writer is not None:
            self._write_row(inputs)

        return {}
