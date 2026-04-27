import sys, os, csv, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from registry import NODE_SCHEMAS, NODE_CLASS_REGISTRY, vision_node, NodeProcessor

# Force plugin to register
import importlib.util
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'csv_export.py')
_spec = importlib.util.spec_from_file_location('plugins.csv_export', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CSVExportNode = NODE_CLASS_REGISTRY['util_csv_export']


def _make_params(tmp_dir, record=True):
    return {
        'record': record,
        'filename': 'test',
        'path': tmp_dir,
        'auto_timestamp': False,
    }


def test_file_created_on_record_start():
    with tempfile.TemporaryDirectory() as d:
        node = CSVExportNode()
        node.process({}, _make_params(d, record=True))
        files = os.listdir(d)
        assert len(files) == 1
        assert files[0].endswith('.csv')


def test_header_written_once():
    with tempfile.TemporaryDirectory() as d:
        node = CSVExportNode()
        params = _make_params(d)
        for _ in range(3):
            node.process({'val_1': 1.0}, params)
        path = os.path.join(d, 'test.csv')
        with open(path) as f:
            rows = list(csv.reader(f))
        assert rows[0][0] == 'timestamp'  # single header row
        assert len(rows) == 4  # header + 3 data rows


def test_file_handle_stays_open_across_frames():
    with tempfile.TemporaryDirectory() as d:
        node = CSVExportNode()
        params = _make_params(d)
        for i in range(5):
            node.process({'val_1': float(i)}, params)
        path = os.path.join(d, 'test.csv')
        with open(path) as f:
            rows = list(csv.reader(f))
        assert len(rows) == 6  # header + 5 rows


def test_file_closed_on_record_stop():
    with tempfile.TemporaryDirectory() as d:
        node = CSVExportNode()
        params_on = _make_params(d, record=True)
        params_off = _make_params(d, record=False)
        node.process({}, params_on)
        node.process({}, params_on)
        node.process({}, params_off)
        assert node._fh is None


def test_no_file_when_not_recording():
    with tempfile.TemporaryDirectory() as d:
        node = CSVExportNode()
        node.process({}, _make_params(d, record=False))
        assert os.listdir(d) == []
