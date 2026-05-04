"""
Serial Port Reader — reads data from Arduino / ESP32 / any serial device.
Background thread prevents blocking the 30-fps engine loop.
Supports CSV, JSON, and raw string parsing.
"""

import json
import queue
import subprocess
import sys
import threading
import time

from registry import vision_node, NodeProcessor, send_notification

# ── Dependency bootstrap ───────────────────────────────────────────────────────
try:
    import serial
    _SERIAL_OK = True
except ImportError:
    _SERIAL_OK = False
    send_notification('pyserial missing — installing…', progress=0.05, notif_id='serial_install')
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', 'pyserial'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        import serial  # noqa: F811
        _SERIAL_OK = True
        send_notification('pyserial installed', progress=1.0, notif_id='serial_install')
    except Exception as _e:
        send_notification(f'pyserial install failed: {_e}', level='error', notif_id='serial_install')

_BAUD_RATES = [1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 230400, 500000, 921600]
_BAUD_LABELS = [str(b) for b in _BAUD_RATES]
_BAUD_DEFAULT = _BAUD_RATES.index(115200)


@vision_node(
    type_id='serial_reader',
    label='Serial Port',
    category='io',
    icon='Cpu',
    description="Reads serial data from Arduino, ESP32, or any UART device. Non-blocking background thread. Parses CSV, JSON, or raw strings.",
    inputs=[],
    outputs=[
        {'id': 'raw',     'color': 'string'},
        {'id': 'values',  'color': 'dict'},
        {'id': 'value_0', 'color': 'scalar'},
        {'id': 'value_1', 'color': 'scalar'},
        {'id': 'value_2', 'color': 'scalar'},
        {'id': 'value_3', 'color': 'scalar'},
        {'id': 'value_4', 'color': 'scalar'},
        {'id': 'value_5', 'color': 'scalar'},
        {'id': 'value_6', 'color': 'scalar'},
        {'id': 'value_7', 'color': 'scalar'},
    ],
    params=[
        {'id': 'port',      'label': 'Port',             'type': 'string', 'default': '/dev/ttyUSB0'},
        {'id': 'baud',      'label': 'Baud Rate',        'type': 'enum',   'options': _BAUD_LABELS, 'default': _BAUD_DEFAULT},
        {'id': 'parse',     'label': 'Parse Mode',       'type': 'enum',   'options': ['CSV', 'JSON', 'Raw'], 'default': 0},
        {'id': 'delimiter', 'label': 'CSV Delimiter',    'type': 'string', 'default': ','},
        {'id': 'encoding',  'label': 'Encoding',         'type': 'enum',   'options': ['utf-8', 'ascii', 'latin-1'], 'default': 0},
    ]
)
class SerialReaderNode(NodeProcessor):
    _ENCODINGS = ['utf-8', 'ascii', 'latin-1']

    def __init__(self):
        self._port    = None
        self._baud    = None
        self._thread  = None
        self._serial  = None
        self._stop    = threading.Event()
        self._queue   = queue.Queue(maxsize=128)
        self._last    = {'raw': '', 'values': {}, 'scalars': []}
        self._status  = 'disconnected'

    # ── Background reader ──────────────────────────────────────────────────────

    def _reader(self, port, baud, encoding):
        self._status = 'connecting'
        try:
            ser = serial.Serial(port, baud, timeout=1.0)
            self._serial = ser
            self._status = 'connected'
            while not self._stop.is_set():
                try:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode(encoding, errors='replace').strip()
                    if line:
                        # Keep queue bounded — drop oldest if full
                        if self._queue.full():
                            try:
                                self._queue.get_nowait()
                            except queue.Empty:
                                pass
                        self._queue.put_nowait(line)
                except serial.SerialException:
                    self._status = 'error'
                    break
                except Exception:
                    time.sleep(0.05)
        except Exception as e:
            self._status = f'error: {e}'
        finally:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
            if self._status == 'connected':
                self._status = 'disconnected'

    def _ensure_connected(self, port, baud, encoding):
        same = (
            self._port == port
            and self._baud == baud
            and self._thread is not None
            and self._thread.is_alive()
        )
        if same:
            return
        # Tear down existing thread
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._stop.clear()
        # Empty queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._port = port
        self._baud = baud
        self._thread = threading.Thread(
            target=self._reader,
            args=(port, baud, encoding),
            daemon=True,
        )
        self._thread.start()

    # ── Parsing ────────────────────────────────────────────────────────────────

    def _parse(self, line, parse_mode, delimiter):
        if parse_mode == 2:  # Raw
            return {'raw': line, 'values': {'raw': line}, 'scalars': []}

        if parse_mode == 1:  # JSON
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    data = {'value': data}
                scalars = [float(v) for v in data.values() if isinstance(v, (int, float))]
                return {'raw': line, 'values': data, 'scalars': scalars}
            except Exception:
                return {'raw': line, 'values': {}, 'scalars': []}

        # CSV (default)
        parts = line.split(delimiter)
        scalars = []
        values  = {}
        for i, p in enumerate(parts):
            stripped = p.strip()
            try:
                v = float(stripped)
                scalars.append(v)
                values[f'v{i}'] = v
            except ValueError:
                values[f'v{i}'] = stripped
        return {'raw': line, 'values': values, 'scalars': scalars}

    # ── Main process ───────────────────────────────────────────────────────────

    def process(self, inputs, params):
        if not _SERIAL_OK:
            return {
                'raw': 'pyserial not available', 'values': {},
                **{f'value_{i}': 0.0 for i in range(8)},
                'display_text': 'pyserial not installed',
            }

        port     = str(params.get('port', '/dev/ttyUSB0')).strip()
        baud_idx = min(int(params.get('baud', _BAUD_DEFAULT)), len(_BAUD_RATES) - 1)
        baud     = _BAUD_RATES[baud_idx]
        parse    = int(params.get('parse', 0))
        delim    = str(params.get('delimiter', ','))
        enc_idx  = min(int(params.get('encoding', 0)), len(self._ENCODINGS) - 1)
        encoding = self._ENCODINGS[enc_idx]

        self._ensure_connected(port, baud, encoding)

        # Drain queue — keep only latest line
        latest = None
        while True:
            try:
                latest = self._queue.get_nowait()
            except queue.Empty:
                break

        if latest is not None:
            self._last = self._parse(latest, parse, delim)

        sc = self._last.get('scalars', [])
        out = {
            'raw':          self._last.get('raw', ''),
            'values':       self._last.get('values', {}),
            'display_text': f"[{self._status}] {port} @ {baud}\n{self._last.get('raw', '')}",
        }
        for i in range(8):
            out[f'value_{i}'] = sc[i] if i < len(sc) else 0.0
        return out
