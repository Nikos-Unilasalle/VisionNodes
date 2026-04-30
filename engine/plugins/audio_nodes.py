from registry import vision_node, NodeProcessor, send_notification
import numpy as np
import cv2
import os
import base64
import sys
import subprocess
import threading
import time

# ── Dependency bootstrap ───────────────────────────────────────────────────────
try:
    import librosa
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    send_notification('Audio libs missing — installing…', progress=0.05, notif_id='audio_install')
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', 'librosa', 'soundfile', 'sounddevice'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import librosa          # noqa: F811
        import soundfile as sf  # noqa: F811
        AUDIO_AVAILABLE = True
        send_notification('Audio libs installed', progress=1.0, notif_id='audio_install')
    except Exception as e:
        send_notification(f'Audio install failed: {e}', level='error', notif_id='audio_install')

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False
    if AUDIO_AVAILABLE:
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'sounddevice'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            import sounddevice as sd  # noqa: F811
            SD_AVAILABLE = True
        except Exception:
            pass


# ── Channel split helper ───────────────────────────────────────────────────────

def _split_channels(y):
    """Return (left, right, mono) as 1D float32 arrays.

    Accepts (N,) mono or (2, N) / (N, 2) stereo.
    """
    if y is None:
        return None, None, None
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        return y, y, y
    if y.ndim == 2:
        if y.shape[0] == 2:          # (2, N) — librosa stereo format
            L, R = y[0], y[1]
        elif y.shape[1] == 2:        # (N, 2) — soundfile format
            L, R = y[:, 0], y[:, 1]
        else:
            flat = y.ravel()
            return flat, flat, flat
        mono = ((L + R) * 0.5).astype(np.float32)
        return L.astype(np.float32), R.astype(np.float32), mono
    flat = y.ravel()
    return flat, flat, flat


def _n_samples(y: np.ndarray) -> int:
    """Number of audio samples regardless of channel layout."""
    if y.ndim == 1:
        return len(y)
    return y.shape[1] if y.shape[0] == 2 else y.shape[0]


# ── Shared SD player ───────────────────────────────────────────────────────────

_sd_lock  = threading.Lock()
_sd_owner = None


class _SDPlayer:
    def __init__(self):
        self._audio             = None   # raw ndarray (mono 1D or stereo 2D)
        self._sr                = 22050
        self._n_samples         = 0
        self._duration          = 0.0
        self._play_start_sample = 0
        self._play_start_wall   = None
        self._is_playing        = False

    def load(self, audio: np.ndarray, sr: int):
        self.stop()
        self._audio     = np.asarray(audio, dtype=np.float32)
        self._sr        = int(sr)
        self._n_samples = _n_samples(self._audio)
        self._duration  = self._n_samples / sr

    @property
    def position(self) -> float:
        if self._is_playing and self._play_start_wall is not None:
            elapsed = time.time() - self._play_start_wall
            return min(self._play_start_sample / self._sr + elapsed, self._duration)
        return self._play_start_sample / self._sr

    def play(self, volume: float = 1.0):
        global _sd_owner
        if not SD_AVAILABLE or self._audio is None or self._is_playing:
            return
        start = self._play_start_sample
        y     = self._audio
        # Slice from start position, ensure C-contiguous for sounddevice
        if y.ndim == 2 and y.shape[0] == 2:          # (2, N) stereo
            chunk = np.ascontiguousarray(y[:, start:].T)   # → (N, 2)
        else:                                          # (N,) mono
            chunk = np.ascontiguousarray(y[start:])
        if volume != 1.0:
            chunk = np.clip(chunk * volume, -1.0, 1.0).astype(np.float32)
        with _sd_lock:
            _sd_owner = self
            sd.play(chunk, self._sr)
        self._play_start_wall = time.time()
        self._is_playing      = True

    def pause(self):
        global _sd_owner
        if not self._is_playing:
            return
        pos = self.position
        with _sd_lock:
            if _sd_owner is self:
                sd.stop()
                _sd_owner = None
        self._play_start_sample = int(pos * self._sr)
        self._play_start_wall   = None
        self._is_playing        = False

    def stop(self):
        global _sd_owner
        if not SD_AVAILABLE:
            return
        with _sd_lock:
            if _sd_owner is self:
                try:
                    sd.stop()
                except Exception:
                    pass
                _sd_owner = None
        self._play_start_sample = 0
        self._play_start_wall   = None
        self._is_playing        = False

    @property
    def finished(self) -> bool:
        return self._is_playing and self.position >= self._duration


# ── 1. Audio File Input ────────────────────────────────────────────────────────

_AUDIO_OUTPUTS = [
    {'id': 'audio', 'color': 'audio',   'label': 'Audio'},
    {'id': 'left',  'color': 'audio',   'label': 'Left'},
    {'id': 'right', 'color': 'audio',   'label': 'Right'},
    {'id': 'mono',  'color': 'audio',   'label': 'Mono'},
]

@vision_node(
    type_id='plugin_audio_input',
    label='Audio File',
    category='audio',
    icon='Music',
    description='Loads an audio file and plays it via system audio (sounddevice).',
    inputs=[],
    outputs=_AUDIO_OUTPUTS + [
        {'id': 'sr',       'color': 'scalar'},
        {'id': 'duration', 'color': 'scalar'},
        {'id': 'position', 'color': 'scalar'},
    ],
    params=[
        {'id': 'path',    'label': 'File Path',  'type': 'string', 'default': ''},
        {'id': 'playing', 'label': 'Playing',    'type': 'toggle', 'default': False},
        {'id': 'loop',    'label': 'Loop',       'type': 'toggle', 'default': False},
        {'id': 'rewind',  'label': 'Rewind',     'type': 'trigger'},
    ]
)
class AudioInputNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_path   = None
        self._left = self._right = self._mono = None
        self._sr           = 0
        self._player       = _SDPlayer()
        self._last_playing = False
        self._last_rewind  = False

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            send_notification('librosa not available', level='error', notif_id='audio_input')
            return _null_audio()

        path    = params.get('path', '').strip()
        playing = bool(params.get('playing', False))
        loop    = bool(params.get('loop',    False))
        rewind  = bool(params.get('rewind',  False))

        if path:
            full = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(full):
                root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                alt  = os.path.join(root, path)
                full = alt if os.path.exists(alt) else full

            if not os.path.exists(full):
                send_notification(f'File not found: {path}', level='error', notif_id='audio_input')
                return _null_audio()

            if full != self._cache_path:
                try:
                    send_notification(f'Loading {os.path.basename(full)}…', progress=0.1, notif_id='audio_input')
                    y_raw, sr = librosa.load(full, sr=None, mono=False)
                    self._left, self._right, self._mono = _split_channels(y_raw)
                    self._sr = int(sr)
                    self._player.load(y_raw, self._sr)  # stereo-aware; load() calls stop()
                    self._cache_path   = full
                    self._last_playing = False  # force play() re-evaluation next frame
                    ch = 'stereo' if y_raw.ndim == 2 else 'mono'
                    send_notification(
                        f'{os.path.basename(full)} — {int(sr)} Hz · {self._player._duration:.2f}s · {ch}',
                        progress=1.0, notif_id='audio_input'
                    )
                except Exception as e:
                    send_notification(f'Load error: {e}', level='error', notif_id='audio_input')
                    return _null_audio()

        if self._mono is None:
            return _null_audio()

        # Rewind (rising edge): stop → reset → play if already playing
        if rewind and not self._last_rewind:
            self._player.stop()
            if playing:
                self._player.play()
        self._last_rewind = rewind

        # Play / Pause transitions (edge-detect to avoid repeated sd.play() calls)
        if playing and not self._last_playing:
            if not self._player._is_playing:
                self._player.play()
        elif not playing and self._last_playing:
            self._player.pause()
        self._last_playing = playing

        # Loop: auto-restart when track ends
        if playing and self._player.finished:
            if loop:
                self._player.stop()
                self._player.play()

        return {
            'audio':    self._mono,
            'left':     self._left,
            'right':    self._right,
            'mono':     self._mono,
            'sr':       self._sr,
            'duration': round(self._player._duration, 3),
            'position': round(self._player.position, 3),
        }


def _null_audio():
    return {'audio': None, 'left': None, 'right': None, 'mono': None,
            'sr': 0, 'duration': 0, 'position': 0}


# ── 2. Audio → Spectrogram ────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_to_spectrogram',
    label='Audio to Spectro',
    category='audio',
    icon='Waves',
    description='Converts an audio window into a log-mel spectrogram image (dB scale).',
    inputs=[
        {'id': 'audio',    'color': 'audio'},
        {'id': 'sr',       'color': 'scalar'},
        {'id': 'position', 'color': 'scalar'},
    ],
    outputs=[
        {'id': 'image', 'color': 'image', 'label': 'Image'},
        {'id': 'raw',   'color': 'image', 'label': 'Raw'},
        {'id': 'sr',    'color': 'scalar', 'label': 'SR'},
    ],
    params=[
        {'id': 'full_file',  'label': 'Full File',   'type': 'bool',  'default': False},
        {'id': 'window_sec', 'label': 'Window (s)',  'type': 'float', 'default': 5.0,  'min': 0.5, 'max': 60.0},
        {'id': 'n_fft',      'label': 'N-FFT',       'type': 'int',   'default': 2048, 'min': 256, 'max': 8192},
        {'id': 'hop_length', 'label': 'Hop Length',  'type': 'int',   'default': 512,  'min': 64,  'max': 2048},
        {'id': 'n_mels',     'label': 'Mel Bands',   'type': 'int',   'default': 128,  'min': 32,  'max': 256},
        {'id': 'colormap',   'label': 'Colormap',    'type': 'enum',  'default': 'Magma',
         'options': ['Magma', 'Viridis', 'Inferno', 'Hot', 'Jet']},
    ]
)
class AudioToSpectrogramNode(NodeProcessor):
    CMAPS = {
        'Magma':   cv2.COLORMAP_MAGMA,
        'Viridis': cv2.COLORMAP_VIRIDIS,
        'Inferno': cv2.COLORMAP_INFERNO,
        'Hot':     cv2.COLORMAP_HOT,
        'Jet':     cv2.COLORMAP_JET,
    }

    def __init__(self):
        super().__init__()
        self._full_cache   = None
        self._full_key     = None
        self._full_loading = False

    def _make_spectro(self, y_window, sr, n_fft, hop_length, n_mels, cmap_key):
        S      = librosa.feature.melspectrogram(y=y_window, sr=sr, n_fft=n_fft,
                                                hop_length=hop_length, n_mels=n_mels)
        S_db   = librosa.power_to_db(S, ref=np.max)
        lo, hi = S_db.min(), S_db.max()
        norm   = ((S_db - lo) / max(hi - lo, 1e-6) * 255).astype(np.uint8)
        norm_f = np.flipud(norm)
        img    = cv2.applyColorMap(norm_f, self.CMAPS.get(cmap_key, cv2.COLORMAP_MAGMA))
        raw    = cv2.cvtColor(norm_f, cv2.COLOR_GRAY2BGR)
        try:
            h, w = img.shape[:2]
            pw   = max(1, int(120 * w / h))
            _, buf = cv2.imencode('.jpg', cv2.resize(img, (pw, 120)), [cv2.IMWRITE_JPEG_QUALITY, 70])
            return {'image': img, 'raw': raw, 'sr': sr, 'preview': base64.b64encode(buf).decode()}
        except Exception:
            return {'image': img, 'raw': raw, 'sr': sr}

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            return {'image': None}
        y  = inputs.get('audio')
        sr = int(inputs.get('sr', 22050) or 22050)
        if y is None:
            return {'image': None}

        _, _, y_mono = _split_channels(y)

        n_fft      = int(params.get('n_fft', 2048))
        hop_length = int(params.get('hop_length', 512))
        n_mels     = int(params.get('n_mels', 128))
        cmap_key   = params.get('colormap', 'Magma')
        full_file  = bool(params.get('full_file', False))

        if full_file:
            key = (len(y_mono), sr, n_fft, hop_length, n_mels, cmap_key)
            if key == self._full_key:
                return self._full_cache if self._full_cache is not None else {'image': None, 'raw': None, 'sr': sr}
            # New audio or params changed — recompute in background
            if not self._full_loading:
                self._full_loading = True
                self._full_key     = key
                self._full_cache   = None
                def _run(_y, _sr, _nfft, _hop, _nmels, _cmap):
                    result = self._make_spectro(_y, _sr, _nfft, _hop, _nmels, _cmap)
                    self._full_cache   = result
                    self._full_loading = False
                threading.Thread(target=_run,
                                 args=(y_mono.copy(), sr, n_fft, hop_length, n_mels, cmap_key),
                                 daemon=True).start()
            return {'image': None, 'raw': None, 'sr': sr}

        # Window mode
        position   = float(inputs.get('position') or 0.0)
        window_sec = float(params.get('window_sec', 5.0))
        end_i      = min(int((position + window_sec) * sr), len(y_mono))
        start_i    = max(0, end_i - int(window_sec * sr))
        y_window   = y_mono[start_i:end_i]
        if len(y_window) < 64:
            return {'image': None}

        return self._make_spectro(y_window, sr, n_fft, hop_length, n_mels, cmap_key)


# ── 3. Waveform Visualizer ────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_waveform',
    label='Waveform View',
    category='audio',
    icon='Activity',
    description='Renders the audio waveform as an image.',
    inputs=[{'id': 'audio', 'color': 'audio'}],
    outputs=[{'id': 'image', 'color': 'image'}],
    params=[
        {'id': 'width',  'label': 'Width',  'type': 'int',   'default': 640,     'min': 128, 'max': 2048},
        {'id': 'height', 'label': 'Height', 'type': 'int',   'default': 200,     'min': 64,  'max': 1024},
        {'id': 'color',  'label': 'Color',  'type': 'color', 'default': '#6366F1'},
    ]
)
class AudioWaveformNode(NodeProcessor):
    def process(self, inputs, params):
        y = inputs.get('audio')
        if y is None:
            return {'image': None}

        # Accept any channel layout, display mono
        _, _, y = _split_channels(y)

        W = max(1, int(params.get('width',  640)))
        H = max(1, int(params.get('height', 200)))

        hex_color = params.get('color', '#6366F1').lstrip('#')
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except Exception:
            r, g, b = 99, 102, 241

        img = np.zeros((H, W, 3), dtype=np.uint8)
        n   = len(y)
        if n == 0:
            return {'image': img}

        mid        = H // 2
        col_starts = np.linspace(0, n, W + 1).astype(int)
        col_starts[-1] = n
        seg_starts = np.minimum(col_starts[:-1], n - 1)

        y_f     = np.clip(y, -1.0, 1.0)
        col_min = np.minimum.reduceat(y_f, seg_starts)
        col_max = np.maximum.reduceat(y_f, seg_starts)

        lo_arr = np.clip((mid + col_min * mid).astype(int), 0, H - 1)
        hi_arr = np.clip((mid + col_max * mid).astype(int), 0, H - 1)
        swap   = lo_arr > hi_arr
        lo_arr[swap], hi_arr[swap] = hi_arr[swap].copy(), lo_arr[swap].copy()

        bgr = (b, g, r)
        for x in range(W):
            img[lo_arr[x]:hi_arr[x] + 1, x] = bgr
        img[mid, :] = (min(b+40,255), min(g+40,255), min(r+40,255))

        try:
            _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return {'image': img, 'preview': base64.b64encode(buf).decode()}
        except Exception:
            return {'image': img}


# ── 4. Frequency Filter ───────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_freq_filter',
    label='Freq Filter',
    category='audio',
    icon='Filter',
    description='Low-pass / High-pass / Band-pass / Band-stop Butterworth IIR filter.',
    inputs=[
        {'id': 'audio', 'color': 'audio'},
        {'id': 'sr',    'color': 'scalar'},
    ],
    outputs=_AUDIO_OUTPUTS + [{'id': 'sr', 'color': 'scalar'}],
    params=[
        {'id': 'filter_type', 'label': 'Type',           'type': 'enum', 'default': 'Low-pass',
         'options': ['Low-pass', 'High-pass', 'Band-pass', 'Band-stop']},
        {'id': 'low_hz',  'label': 'Low Cut (Hz)',  'type': 'int', 'default': 100,  'min': 1, 'max': 20000},
        {'id': 'high_hz', 'label': 'High Cut (Hz)', 'type': 'int', 'default': 4000, 'min': 1, 'max': 20000},
        {'id': 'order',   'label': 'Filter Order',  'type': 'int', 'default': 5,    'min': 1, 'max': 10},
    ]
)
class AudioFreqFilterNode(NodeProcessor):
    def process(self, inputs, params):
        y  = inputs.get('audio')
        sr = int(inputs.get('sr', 22050) or 22050)
        if y is None:
            return {'audio': None, 'left': None, 'right': None, 'mono': None, 'sr': sr}

        _, _, y_mono = _split_channels(y)

        ftype   = params.get('filter_type', 'Low-pass')
        low_hz  = float(params.get('low_hz',  100))
        high_hz = float(params.get('high_hz', 4000))
        order   = int(params.get('order', 5))
        nyq     = sr / 2.0
        low_hz  = min(max(low_hz,  1.0), nyq - 1)
        high_hz = min(max(high_hz, 1.0), nyq - 1)

        try:
            from scipy.signal import butter, sosfilt
            if ftype == 'Low-pass':
                sos = butter(order, low_hz  / nyq, btype='low',      output='sos')
            elif ftype == 'High-pass':
                sos = butter(order, high_hz / nyq, btype='high',     output='sos')
            elif ftype == 'Band-pass':
                lo, hi = sorted([low_hz / nyq, high_hz / nyq])
                lo = max(lo, 1e-4); hi = min(hi, 1 - 1e-4)
                sos = butter(order, [lo, hi], btype='band',      output='sos')
            else:
                lo, hi = sorted([low_hz / nyq, high_hz / nyq])
                lo = max(lo, 1e-4); hi = min(hi, 1 - 1e-4)
                sos = butter(order, [lo, hi], btype='bandstop',  output='sos')
            result = sosfilt(sos, y_mono).astype(np.float32)
        except Exception as e:
            send_notification(f'FreqFilter error: {e}', level='error', notif_id='audio_filter')
            result = y_mono

        L, R, M = _split_channels(result)
        return {'audio': result, 'left': L, 'right': R, 'mono': M, 'sr': sr}


# ── 5. Pitch Shift ────────────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_pitch_shift',
    label='Pitch Shift',
    category='audio',
    icon='Music',
    description='Shifts pitch by N semitones without changing duration. Processed once per change.',
    inputs=[
        {'id': 'audio', 'color': 'audio'},
        {'id': 'sr',    'color': 'scalar'},
    ],
    outputs=_AUDIO_OUTPUTS + [{'id': 'sr', 'color': 'scalar'}],
    params=[
        {'id': 'semitones', 'label': 'Semitones', 'type': 'float', 'default': 0.0, 'min': -24, 'max': 24},
    ]
)
class AudioPitchShiftNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._loading   = False
        self._cache_out = None
        self._cache_key = None

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            return {'audio': None, 'left': None, 'right': None, 'mono': None, 'sr': 0}
        y     = inputs.get('audio')
        sr    = int(inputs.get('sr', 22050) or 22050)
        steps = float(params.get('semitones', 0.0))

        if y is None:
            return {'audio': None, 'left': None, 'right': None, 'mono': None, 'sr': sr}

        _, _, y_mono = _split_channels(y)

        if steps == 0.0:
            L, R, M = _split_channels(y_mono)
            return {'audio': y_mono, 'left': L, 'right': R, 'mono': M, 'sr': sr}

        key = (id(y), len(y_mono), steps, sr)
        if key != self._cache_key and not self._loading:
            self._loading   = True
            self._cache_out = None
            send_notification('PitchShift: processing…', progress=0.1, notif_id='audio_pitch')
            def _run(arr, _sr, _steps, _key):
                try:
                    result = librosa.effects.pitch_shift(arr, sr=_sr, n_steps=_steps).astype(np.float32)
                    self._cache_out = result
                    self._cache_key = _key
                    send_notification('PitchShift: done', progress=1.0, notif_id='audio_pitch')
                except Exception as e:
                    send_notification(f'PitchShift error: {e}', level='error', notif_id='audio_pitch')
                finally:
                    self._loading = False
            threading.Thread(target=_run, args=(y_mono, sr, steps, key), daemon=True).start()

        out = self._cache_out if self._cache_out is not None else y_mono
        L, R, M = _split_channels(out)
        return {'audio': out, 'left': L, 'right': R, 'mono': M, 'sr': sr}


# ── 6. Time Stretch ───────────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_time_stretch',
    label='Time Stretch',
    category='audio',
    icon='Zap',
    description='Stretches or compresses audio duration without affecting pitch. Processed once per change.',
    inputs=[
        {'id': 'audio', 'color': 'audio'},
        {'id': 'sr',    'color': 'scalar'},
    ],
    outputs=_AUDIO_OUTPUTS + [{'id': 'sr', 'color': 'scalar'}],
    params=[
        {'id': 'rate', 'label': 'Speed Rate', 'type': 'float', 'default': 1.0, 'min': 0.1, 'max': 4.0},
    ]
)
class AudioTimeStretchNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._loading   = False
        self._cache_out = None
        self._cache_key = None

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            return {'audio': None, 'left': None, 'right': None, 'mono': None, 'sr': 0}
        y    = inputs.get('audio')
        sr   = int(inputs.get('sr', 22050) or 22050)
        rate = float(params.get('rate', 1.0))

        if y is None:
            return {'audio': None, 'left': None, 'right': None, 'mono': None, 'sr': sr}

        _, _, y_mono = _split_channels(y)

        if rate == 1.0:
            L, R, M = _split_channels(y_mono)
            return {'audio': y_mono, 'left': L, 'right': R, 'mono': M, 'sr': sr}

        key = (id(y), len(y_mono), rate)
        if key != self._cache_key and not self._loading:
            self._loading   = True
            self._cache_out = None
            send_notification('TimeStretch: processing…', progress=0.1, notif_id='audio_stretch')
            def _run(arr, _rate, _key):
                try:
                    result = librosa.effects.time_stretch(arr, rate=_rate).astype(np.float32)
                    self._cache_out = result
                    self._cache_key = _key
                    send_notification('TimeStretch: done', progress=1.0, notif_id='audio_stretch')
                except Exception as e:
                    send_notification(f'TimeStretch error: {e}', level='error', notif_id='audio_stretch')
                finally:
                    self._loading = False
            threading.Thread(target=_run, args=(y_mono, rate, key), daemon=True).start()

        out = self._cache_out if self._cache_out is not None else y_mono
        L, R, M = _split_channels(out)
        return {'audio': out, 'left': L, 'right': R, 'mono': M, 'sr': sr}


# ── 7. Audio Info ─────────────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_info',
    label='Audio Info',
    category='audio',
    icon='Activity',
    description='Computes RMS energy, peak amplitude, and zero-crossing rate.',
    inputs=[
        {'id': 'audio', 'color': 'audio'},
        {'id': 'sr',    'color': 'scalar'},
    ],
    outputs=[
        {'id': 'rms',     'color': 'scalar'},
        {'id': 'peak',    'color': 'scalar'},
        {'id': 'zcr',     'color': 'scalar'},
        {'id': 'samples', 'color': 'scalar'},
    ],
    params=[]
)
class AudioInfoNode(NodeProcessor):
    def process(self, inputs, params):
        y = inputs.get('audio')
        if y is None:
            return {'rms': 0.0, 'peak': 0.0, 'zcr': 0.0, 'samples': 0}
        _, _, y_mono = _split_channels(y)
        rms  = float(np.sqrt(np.mean(y_mono ** 2)))
        peak = float(np.max(np.abs(y_mono)))
        zcr  = float(np.mean(librosa.feature.zero_crossing_rate(y_mono)[0])) if AUDIO_AVAILABLE else 0.0
        return {'rms': round(rms, 6), 'peak': round(peak, 6), 'zcr': round(zcr, 6),
                'samples': _n_samples(np.asarray(y))}


# ── 8. Spectrogram → Audio (Griffin-Lim) ─────────────────────────────────────

@vision_node(
    type_id='plugin_spectrogram_to_audio',
    label='Spectro to Audio',
    category='audio',
    icon='Volume2',
    description='Reconstructs audio from a spectrogram image via Griffin-Lim (trigger to run).',
    inputs=[
        {'id': 'image', 'color': 'image', 'label': 'Image (colorized)'},
        {'id': 'raw',   'color': 'image', 'label': 'Raw (preferred)'},
        {'id': 'sr',    'color': 'scalar', 'label': 'SR (overrides param)'},
    ],
    outputs=_AUDIO_OUTPUTS + [{'id': 'sr', 'color': 'scalar'}],
    params=[
        {'id': 'sr',         'label': 'Sample Rate',   'type': 'int', 'default': 22050},
        {'id': 'n_fft',      'label': 'N-FFT',         'type': 'int', 'default': 2048},
        {'id': 'hop_length', 'label': 'Hop Length',    'type': 'int', 'default': 512},
        {'id': 'iterations', 'label': 'GL Iterations', 'type': 'int', 'default': 32, 'min': 4, 'max': 128},
        {'id': 'run',        'label': 'Reconstruct',    'type': 'trigger'},
    ]
)
class SpectrogramToAudioNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._last_trigger = False
        self._cache_audio  = None
        self._cache_sr     = 22050
        self._loading      = False

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            return {'audio': None, 'left': None, 'right': None, 'mono': None, 'sr': 0}

        trigger = bool(params.get('run', False))
        new_trigger = trigger and not self._last_trigger
        self._last_trigger = trigger

        if new_trigger and not self._loading:
            # Prefer 'raw' (clean grayscale mel) over colorized 'image'
            _raw = inputs.get('raw')
            img = _raw if _raw is not None else inputs.get('image')
            if img is not None:
                _sr_in = inputs.get('sr')
                sr         = int(_sr_in) if _sr_in is not None else int(params.get('sr', 22050))
                n_fft      = int(params.get('n_fft', 2048))
                hop_length = int(params.get('hop_length', 512))
                iters      = int(params.get('iterations', 32))
                self._loading = True
                send_notification('Griffin-Lim: reconstructing…', progress=0.1, notif_id='audio_gl')

                def _run(image, _sr, _nfft, _hop, _iters):
                    try:
                        # Convert to grayscale then flip back to low-freq-first order
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
                        gray = np.flipud(gray)   # undo the display flip → low freq at row 0

                        # gray: shape (n_mels, t), values 0-255 normalized dB
                        n_mels = gray.shape[0]
                        S_db   = (gray.astype(np.float32) / 255.0) * 80.0 - 80.0
                        S_pow  = librosa.db_to_power(S_db)   # power mel spectrogram

                        # mel_to_audio properly inverts mel filter → STFT → Griffin-Lim
                        # n_mels inferred from S_pow.shape[0]; don't pass explicitly
                        y = librosa.feature.inverse.mel_to_audio(
                            S_pow, sr=_sr, n_fft=_nfft, hop_length=_hop, n_iter=_iters
                        )
                        self._cache_audio = y.astype(np.float32)
                        self._cache_sr    = _sr
                        send_notification('Griffin-Lim: done', progress=1.0, notif_id='audio_gl')
                    except Exception as e:
                        send_notification(f'GriffinLim error: {e}', level='error', notif_id='audio_gl')
                    finally:
                        self._loading = False

                threading.Thread(target=_run, args=(img, sr, n_fft, hop_length, iters), daemon=True).start()

        out = self._cache_audio
        L, R, M = _split_channels(out)
        return {'audio': out, 'left': L, 'right': R, 'mono': M, 'sr': self._cache_sr}


# ── 9. Speaker Out ────────────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_playback',
    label='Speaker Out',
    category=['audio', 'out'],
    icon='Volume2',
    description='Receives processed audio and streams it to the browser via Web Audio API.',
    inputs=[
        {'id': 'audio', 'color': 'audio'},
        {'id': 'sr',    'color': 'scalar'},
    ],
    outputs=[
        {'id': 'position', 'color': 'scalar'},
        {'id': 'duration', 'color': 'scalar'},
    ],
    params=[
        {'id': 'playing', 'label': 'Playing', 'type': 'toggle',  'default': False},
        {'id': 'loop',    'label': 'Loop',    'type': 'toggle',  'default': False},
        {'id': 'rewind',  'label': 'Rewind',  'type': 'trigger'},
    ]
)
class AudioPlaybackNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._player       = _SDPlayer()
        self._cache_key    = None
        self._last_playing = False
        self._last_rewind  = False
        self._auto_stopped = False

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            return {'position': 0, 'duration': 0}

        y       = inputs.get('audio')
        sr      = int(inputs.get('sr', 22050) or 22050)
        playing = bool(params.get('playing', False))
        loop    = bool(params.get('loop',    False))
        rewind  = bool(params.get('rewind',  False))

        if y is None:
            return {'position': 0, 'duration': 0}

        _, _, y_mono = _split_channels(y)

        key = (len(y_mono), sr)
        if key != self._cache_key:
            self._player.load(y_mono, sr)
            self._cache_key    = key
            self._last_playing = False
            self._auto_stopped = False

        # Rewind (rising edge) — clears auto-stop flag
        if rewind and not self._last_rewind:
            self._player.stop()
            self._auto_stopped = False
            if playing:
                self._player.play()
        self._last_rewind = rewind

        # Play / Pause transitions
        if playing and not self._last_playing:
            if not self._player._is_playing and not self._auto_stopped:
                self._player.play()
        elif not playing and self._last_playing:
            self._player.pause()
            self._auto_stopped = False
        self._last_playing = playing

        _command = None
        if playing and self._player.finished:
            if loop:
                self._player.stop()
                self._player.play()
            else:
                self._player.stop()        # reset position to 0
                self._last_playing = False
                self._auto_stopped = True
                _command = {'type': 'set_param', 'node_id': '__self__', 'params': {'playing': False}}

        result = {
            'position': round(self._player.position, 3),
            'duration': round(self._player._duration, 3),
        }
        if _command:
            result['_command'] = _command
        return result


# ── 10. Audio Export ───────────────────────────────────────────────────────────

@vision_node(
    type_id='plugin_audio_export',
    label='Audio Export',
    category='audio',
    icon='Download',
    description='Saves audio data to a .wav file on disk.',
    inputs=[
        {'id': 'audio', 'color': 'audio'},
        {'id': 'sr',    'color': 'scalar'},
    ],
    outputs=[],
    params=[
        {'id': 'path',     'label': 'Output Path', 'type': 'string',  'default': 'output.wav'},
        {'id': 'save_now', 'label': 'Save Now',    'type': 'trigger'},
    ]
)
class AudioExportNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._last_trigger = False

    def process(self, inputs, params):
        if not AUDIO_AVAILABLE:
            return {}
        y       = inputs.get('audio')
        sr      = int(inputs.get('sr', 22050) or 22050)
        path    = params.get('path', 'output.wav')
        trigger = bool(params.get('save_now', False))

        if trigger and not self._last_trigger and y is not None:
            try:
                _, _, y_mono = _split_channels(y)
                full = os.path.abspath(os.path.expanduser(path))
                sf.write(full, y_mono, sr)
                send_notification(f'Saved: {os.path.basename(full)}', progress=1.0, notif_id='audio_export')
            except Exception as e:
                send_notification(f'Export error: {e}', level='error', notif_id='audio_export')

        self._last_trigger = trigger
        return {}
