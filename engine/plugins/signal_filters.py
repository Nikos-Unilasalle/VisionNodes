"""
Signal filtering nodes — all take a scalar 'value' input and output 'filtered' scalar.
Stateful: each node maintains a buffer / internal state across frames.
Numpy-only, no scipy dependency.
"""

import numpy as np
from __main__ import vision_node, NodeProcessor

# ---------------------------------------------------------------------------
# 1. Moving Average
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_ma',
    label='Moving Average',
    category='analysis',
    icon='TrendingUp',
    description="Sliding-window mean. Reduces noise but introduces latency (window/2 frames).",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[{'id': 'window', 'min': 2, 'max': 300, 'step': 1, 'default': 15}]
)
class MovingAverageNode(NodeProcessor):
    def __init__(self):
        self.buf = []
    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        w = max(2, int(params.get('window', 15)))
        self.buf.append(v)
        if len(self.buf) > w: self.buf = self.buf[-w:]
        return {'filtered': float(np.mean(self.buf)), 'raw': v}

# ---------------------------------------------------------------------------
# 2. Exponential Moving Average (EMA)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_ema',
    label='Exp. Smoothing (EMA)',
    category='analysis',
    icon='TrendingUp',
    description="Exponential moving average. alpha=1 = no smoothing, alpha→0 = heavy smoothing.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[{'id': 'alpha', 'min': 1, 'max': 100, 'step': 1, 'default': 20}]
)
class EMANode(NodeProcessor):
    def __init__(self):
        self.state = None
    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        a = float(params.get('alpha', 20)) / 100.0
        if self.state is None: self.state = v
        self.state = a * v + (1.0 - a) * self.state
        return {'filtered': self.state, 'raw': v}

# ---------------------------------------------------------------------------
# 3. Kalman Filter (1D constant-velocity model)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_kalman',
    label='Kalman Filter',
    category='analysis',
    icon='Activity',
    description="1D Kalman filter. Q = process noise (dynamics), R = measurement noise.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[
        {'id': 'q', 'min': 0, 'max': 100, 'step': 1, 'default': 1},
        {'id': 'r', 'min': 1, 'max': 1000,'step': 1, 'default': 100},
    ]
)
class KalmanFilterNode(NodeProcessor):
    def __init__(self):
        self.x = None  # state estimate
        self.P = 1.0   # estimate covariance
    def process(self, inputs, params):
        z = float(inputs.get('value', 0.0))
        Q = float(params.get('q', 1))   / 1000.0
        R = float(params.get('r', 100)) / 100.0
        if self.x is None: self.x = z
        # Predict
        P_pred = self.P + Q
        # Update
        K = P_pred / (P_pred + R)
        self.x = self.x + K * (z - self.x)
        self.P = (1.0 - K) * P_pred
        return {'filtered': self.x, 'raw': z}

# ---------------------------------------------------------------------------
# 4. Median Filter
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_median',
    label='Median Filter',
    category='analysis',
    icon='Minus',
    description="Sliding-window median. Excellent spike/outlier rejection.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[{'id': 'window', 'min': 3, 'max': 301, 'step': 2, 'default': 11}]
)
class MedianFilterNode(NodeProcessor):
    def __init__(self):
        self.buf = []
    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        w = max(3, int(params.get('window', 11)))
        if w % 2 == 0: w += 1
        self.buf.append(v)
        if len(self.buf) > w: self.buf = self.buf[-w:]
        return {'filtered': float(np.median(self.buf)), 'raw': v}

# ---------------------------------------------------------------------------
# 5. Savitzky-Golay Smoothing
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_savgol',
    label='Savitzky-Golay',
    category='analysis',
    icon='Spline',
    description="Polynomial least-squares smoothing. Preserves peak shapes. window must be > polyorder.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[
        {'id': 'window',    'min': 5, 'max': 101, 'step': 2, 'default': 11},
        {'id': 'polyorder', 'min': 1, 'max': 6,   'step': 1, 'default': 2},
    ]
)
class SavitzkyGolayNode(NodeProcessor):
    def __init__(self):
        self.buf = []
        self._coeffs = None
        self._sig = None

    @staticmethod
    def _sg_coeffs(window, poly):
        half = window // 2
        x = np.arange(-half, half + 1, dtype=np.float64)
        A = np.vander(x, poly + 1, increasing=True)
        try:
            coeffs = np.linalg.lstsq(A, np.eye(window), rcond=None)[0][0]
        except Exception:
            coeffs = np.ones(window) / window
        return coeffs

    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        w = int(params.get('window', 11))
        if w % 2 == 0: w += 1
        w = max(5, w)
        p = min(int(params.get('polyorder', 2)), w - 2)
        sig = (w, p)
        if sig != self._sig:
            self._coeffs = self._sg_coeffs(w, p)
            self._sig = sig
        self.buf.append(v)
        if len(self.buf) > w: self.buf = self.buf[-w:]
        if len(self.buf) < w:
            return {'filtered': v, 'raw': v}
        return {'filtered': float(np.dot(self._coeffs, self.buf)), 'raw': v}

# ---------------------------------------------------------------------------
# 6. Low-pass IIR Filter (1st-order RC)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_lowpass',
    label='Low-pass Filter',
    category='analysis',
    icon='WavesLadder',
    description="1st-order IIR low-pass. cutoff in mHz, fps in Hz. Attenuates frequencies above cutoff.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[
        {'id': 'cutoff', 'min': 1,  'max': 5000, 'step': 1, 'default': 1000},
        {'id': 'fps',    'min': 1,  'max': 120,  'step': 1, 'default': 30},
    ]
)
class LowpassFilterNode(NodeProcessor):
    def __init__(self):
        self.state = None
        self._sig = None
        self._r = None
    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        cut_hz = float(params.get('cutoff', 1000)) / 1000.0
        fps    = max(1.0, float(params.get('fps', 30)))
        sig = (cut_hz, fps)
        if sig != self._sig:
            self._r = 1.0 - np.exp(-2.0 * np.pi * cut_hz / fps)
            self._sig = sig
        if self.state is None: self.state = v
        self.state = (1.0 - self._r) * self.state + self._r * v
        return {'filtered': self.state, 'raw': v}

# ---------------------------------------------------------------------------
# 7. Holt-Winters (Double Exponential Smoothing — level + trend)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_holt',
    label='Holt-Winters',
    category='analysis',
    icon='TrendingUp',
    description="Double exponential smoothing. Tracks level AND trend. alpha=smoothing, beta=trend.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'trend', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[
        {'id': 'alpha', 'min': 1, 'max': 100, 'step': 1, 'default': 20},
        {'id': 'beta',  'min': 1, 'max': 100, 'step': 1, 'default': 10},
    ]
)
class HoltWintersNode(NodeProcessor):
    def __init__(self):
        self.L = None  # level
        self.T = 0.0   # trend
    def process(self, inputs, params):
        v  = float(inputs.get('value', 0.0))
        al = float(params.get('alpha', 20)) / 100.0
        be = float(params.get('beta',  10)) / 100.0
        if self.L is None:
            self.L = v
        else:
            L_prev = self.L
            self.L = al * v + (1.0 - al) * (self.L + self.T)
            self.T = be * (self.L - L_prev) + (1.0 - be) * self.T
        return {'filtered': self.L + self.T, 'trend': self.T, 'raw': v}

# ---------------------------------------------------------------------------
# 8. Gaussian Smoothing (buffer convolution)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_gaussian',
    label='Gaussian Smooth',
    category='analysis',
    icon='Bell',
    description="Convolves signal buffer with a Gaussian kernel. sigma controls spread.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[
        {'id': 'window', 'min': 3, 'max': 101, 'step': 2, 'default': 15},
        {'id': 'sigma',  'min': 1, 'max': 50,  'step': 1, 'default': 5},
    ]
)
class GaussianSmoothNode(NodeProcessor):
    def __init__(self):
        self.buf = []
        self._kernel = None
        self._sig = None

    @staticmethod
    def _gauss_kernel(w, sigma):
        half = w // 2
        x = np.arange(-half, half + 1, dtype=np.float64)
        k = np.exp(-0.5 * (x / sigma) ** 2)
        return k / k.sum()

    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        w = int(params.get('window', 15))
        if w % 2 == 0: w += 1
        s = float(params.get('sigma', 5))
        sig = (w, s)
        if sig != self._sig:
            self._kernel = self._gauss_kernel(w, s)
            self._sig = sig
        self.buf.append(v)
        if len(self.buf) > w: self.buf = self.buf[-w:]
        if len(self.buf) < w:
            return {'filtered': v, 'raw': v}
        return {'filtered': float(np.dot(self._kernel, self.buf)), 'raw': v}

# ---------------------------------------------------------------------------
# 9. LOESS / LOWESS (local weighted polynomial regression, degree 1)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_loess',
    label='LOESS / LOWESS',
    category='analysis',
    icon='Spline',
    description="Local regression smoother. span = fraction of points used for each estimate.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[{'id': 'span', 'min': 5, 'max': 100, 'step': 1, 'default': 30}]
)
class LOESSNode(NodeProcessor):
    def __init__(self):
        self.buf = []

    @staticmethod
    def _tricubic(u):
        u = np.clip(np.abs(u), 0, 1)
        return (1.0 - u ** 3) ** 3

    def process(self, inputs, params):
        v = float(inputs.get('value', 0.0))
        span = max(5, int(params.get('span', 30)))
        self.buf.append(v)
        if len(self.buf) > span * 2: self.buf = self.buf[-span * 2:]
        n = len(self.buf)
        if n < 3:
            return {'filtered': v, 'raw': v}
        x = np.arange(n, dtype=np.float64)
        y = np.array(self.buf, dtype=np.float64)
        # Estimate at last point using local span
        x0 = x[-1]
        k = max(3, min(span, n))
        dists = np.abs(x - x0)
        max_d = np.sort(dists)[k - 1] + 1e-10
        w = self._tricubic(dists / max_d)
        # Weighted linear regression
        W = np.diag(w)
        A = np.column_stack([np.ones(n), x])
        try:
            ATA = A.T @ W @ A
            ATb = A.T @ W @ y
            coeffs = np.linalg.solve(ATA, ATb)
            est = coeffs[0] + coeffs[1] * x0
        except Exception:
            est = v
        return {'filtered': float(est), 'raw': v}

# ---------------------------------------------------------------------------
# 10. Particle Filter (1D, random-walk state model)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_particle',
    label='Particle Filter',
    category='analysis',
    icon='Sparkles',
    description="Sequential Monte Carlo estimator. particles = N hypotheses about the true state.",
    inputs=[{'id': 'value', 'color': 'scalar'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'}],
    params=[
        {'id': 'particles',   'min': 10, 'max': 500, 'step': 10, 'default': 100},
        {'id': 'process_std', 'min': 1,  'max': 200, 'step': 1,  'default': 10},
        {'id': 'meas_std',    'min': 1,  'max': 500, 'step': 1,  'default': 50},
    ]
)
class ParticleFilterNode(NodeProcessor):
    def __init__(self):
        self.particles = None
        self.weights   = None

    def process(self, inputs, params):
        z     = float(inputs.get('value', 0.0))
        N     = max(10, int(params.get('particles', 100)))
        p_std = float(params.get('process_std', 10)) / 100.0
        m_std = float(params.get('meas_std',    50)) / 100.0

        if self.particles is None or len(self.particles) != N:
            self.particles = np.full(N, z)
            self.weights   = np.ones(N) / N

        # Predict: random walk
        self.particles += np.random.randn(N) * p_std

        # Update: Gaussian likelihood
        diff = self.particles - z
        log_w = -0.5 * (diff / (m_std + 1e-10)) ** 2
        log_w -= log_w.max()
        self.weights = np.exp(log_w)
        self.weights /= self.weights.sum()

        # Estimate
        est = float(np.dot(self.weights, self.particles))

        # Resample (systematic)
        cumsum = np.cumsum(self.weights)
        positions = (np.arange(N) + np.random.uniform()) / N
        indices = np.searchsorted(cumsum, positions)
        self.particles = self.particles[indices]
        self.weights = np.ones(N) / N

        return {'filtered': est, 'raw': z}
