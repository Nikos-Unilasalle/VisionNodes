"""
Signal filtering nodes.

Deux modes, un seul jeu de nodes :

* entree `value` (scalaire) — filtrage du flux, image par image. Le filtre ne
  connait que le passe : sa sortie est donc en RETARD sur le signal, de la moitie
  de la fenetre pour les filtres a noyau, davantage pour les recursifs.

* entree `list` — filtrage d'une serie deja enregistree, en CENTRE. Chaque point
  est estime avec ses voisins des deux cotes, donc sans retard. Les filtres
  recursifs, qui n'ont pas de version centree, sont appliques en aller-retour
  (une passe en avant, une passe en arriere) : les deux retards se compensent.

Quand `list` est branchee, elle a la priorite et la sortie `list` porte la serie
lissee. Numpy uniquement, pas de scipy.
"""

import numpy as np
from registry import vision_node, NodeProcessor


def _to_scalar(v, default=0.0):
    """Safely extract a Python float from any upstream value (numpy array, scalar, dict…)."""
    if v is None:
        return default
    if isinstance(v, np.ndarray):
        return float(v.flat[0]) if v.size > 0 else default
    if isinstance(v, dict):
        for key in ('value', 'scalar', 'result', 'filtered', 'raw'):
            if key in v:
                return _to_scalar(v[key], default)
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_serie(v):
    """Serie numerique depuis une liste, un tableau ou une colonne. None si rien d'exploitable."""
    if v is None:
        return None
    if isinstance(v, np.ndarray):
        arr = v.astype(np.float64).ravel()
    elif isinstance(v, (list, tuple)):
        try:
            arr = np.array([_to_scalar(x, np.nan) for x in v], dtype=np.float64)
        except Exception:
            return None
    else:
        return None
    return arr if arr.size >= 2 else None


def _borde(x, demi):
    """Prolonge la serie par reflexion.

    Sans ca, un noyau centre deborde aux deux extremites et la convolution y
    ramene des zeros : la courbe plongerait au debut et a la fin, et le premier
    episode detecte serait un artefact de bord.
    """
    if demi <= 0:
        return x
    return np.concatenate([x[demi:0:-1], x, x[-2:-demi - 2:-1]])


def _convolue_centre(x, noyau):
    demi = len(noyau) // 2
    return np.convolve(_borde(x, demi), noyau, mode='valid')[:len(x)]


def _aller_retour(x, passe):
    """Filtre recursif rendu symetrique : une passe en avant, une en arriere.

    Chaque passe decale le signal dans le temps ; les faire dans les deux sens
    annule le decalage. En contrepartie le filtrage est applique deux fois, donc
    plus fort qu'une passe simple.
    """
    return passe(passe(x)[::-1])[::-1]


class FiltreSerie:
    """Aiguillage entre le mode flux et le mode serie.

    Chaque node implemente `flux()` — son comportement historique, inchange — et
    `lisser()`, la version centree. Le mixin choisit selon ce qui est branche.
    """

    def process(self, inputs, params):
        serie = _to_serie(inputs.get('list'))
        if serie is None:
            return self.flux(inputs, params)
        lisse = np.asarray(self.lisser(serie, params), dtype=np.float64)
        return {
            'list': [float(v) for v in lisse],
            'filtered': float(lisse[-1]),
            'raw': float(serie[-1]),
        }

# ---------------------------------------------------------------------------
# 1. Moving Average
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_ma',
    label='Moving Average',
    category='signal',
    icon='TrendingUp',
    description="Sliding-window mean. Reduces noise but introduces latency (window/2 frames).",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[{'id': 'window', 'min': 2, 'max': 300, 'step': 1, 'default': 15}]
)
class MovingAverageNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.buf = []
    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
        w = max(2, int(params.get('window', 15)))
        self.buf.append(v)
        if len(self.buf) > w: self.buf = self.buf[-w:]
        return {'filtered': float(np.mean(self.buf)), 'raw': v}

    def lisser(self, x, params):
        w = max(2, int(params.get('window', 15)))
        return _convolue_centre(x, np.ones(w) / w)

# ---------------------------------------------------------------------------
# 2. Exponential Moving Average (EMA)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_ema',
    label='Exp. Smoothing (EMA)',
    category='signal',
    icon='TrendingUp',
    description="Exponential moving average. alpha=1 = no smoothing, alpha→0 = heavy smoothing.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[{'id': 'alpha', 'min': 1, 'max': 100, 'step': 1, 'default': 20}]
)
class EMANode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.state = None
    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
        a = float(params.get('alpha', 20)) / 100.0
        if self.state is None: self.state = v
        self.state = a * v + (1.0 - a) * self.state
        return {'filtered': self.state, 'raw': v}

    def lisser(self, x, params):
        a = float(params.get('alpha', 20)) / 100.0

        def passe(s):
            out = np.empty_like(s)
            etat = s[0]
            for i, v in enumerate(s):
                etat = a * v + (1.0 - a) * etat
                out[i] = etat
            return out

        return _aller_retour(x, passe)

# ---------------------------------------------------------------------------
# 3. Kalman Filter (1D constant-velocity model)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_kalman',
    label='Kalman Filter',
    category='signal',
    icon='Activity',
    description="1D Kalman filter. Q = process noise (dynamics), R = measurement noise.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[
        {'id': 'q', 'min': 0, 'max': 100, 'step': 1, 'default': 1},
        {'id': 'r', 'min': 1, 'max': 1000,'step': 1, 'default': 100},
    ]
)
class KalmanFilterNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.x = None  # state estimate
        self.P = 1.0   # estimate covariance
    def flux(self, inputs, params):
        z = _to_scalar(inputs.get('value'))
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

    def lisser(self, x, params):
        Q = float(params.get('q', 1)) / 1000.0
        R = float(params.get('r', 100)) / 100.0

        def passe(s):
            out = np.empty_like(s)
            etat, P = s[0], 1.0
            for i, z in enumerate(s):
                P_pred = P + Q
                K = P_pred / (P_pred + R)
                etat = etat + K * (z - etat)
                P = (1.0 - K) * P_pred
                out[i] = etat
            return out

        return _aller_retour(x, passe)

# ---------------------------------------------------------------------------
# 4. Median Filter
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_median',
    label='Median Filter',
    category='signal',
    icon='Minus',
    description="Sliding-window median. Excellent spike/outlier rejection.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[{'id': 'window', 'min': 3, 'max': 301, 'step': 2, 'default': 11}]
)
class MedianFilterNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.buf = []
    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
        w = max(3, int(params.get('window', 11)))
        if w % 2 == 0: w += 1
        self.buf.append(v)
        if len(self.buf) > w: self.buf = self.buf[-w:]
        return {'filtered': float(np.median(self.buf)), 'raw': v}

    def lisser(self, x, params):
        w = max(3, int(params.get('window', 11)))
        if w % 2 == 0:
            w += 1
        demi = w // 2
        borde = _borde(x, demi)
        vues = np.lib.stride_tricks.sliding_window_view(borde, w)
        return np.median(vues, axis=1)[:len(x)]

# ---------------------------------------------------------------------------
# 5. Savitzky-Golay Smoothing
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_savgol',
    label='Savitzky-Golay',
    category='signal',
    icon='Spline',
    description="Polynomial least-squares smoothing. Preserves peak shapes. window must be > polyorder.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[
        {'id': 'window',    'min': 5, 'max': 101, 'step': 2, 'default': 11},
        {'id': 'polyorder', 'min': 1, 'max': 6,   'step': 1, 'default': 2},
    ]
)
class SavitzkyGolayNode(FiltreSerie, NodeProcessor):
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

    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
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

    def lisser(self, x, params):
        w = int(params.get('window', 11))
        if w % 2 == 0:
            w += 1
        w = max(5, w)
        p = min(int(params.get('polyorder', 2)), w - 2)
        # Les memes coefficients qu'en flux : ils estiment deja la valeur au
        # CENTRE de la fenetre, puisque l'abscisse y est centree sur zero.
        return _convolue_centre(x, self._sg_coeffs(w, p)[::-1])

# ---------------------------------------------------------------------------
# 6. Low-pass IIR Filter (1st-order RC)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_lowpass',
    label='Low-pass Filter',
    category='signal',
    icon='WavesLadder',
    description="1st-order IIR low-pass. cutoff in mHz, fps in Hz. Attenuates frequencies above cutoff.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[
        {'id': 'cutoff', 'min': 1,  'max': 5000, 'step': 1, 'default': 1000},
        {'id': 'fps',    'min': 1,  'max': 120,  'step': 1, 'default': 30},
    ]
)
class LowpassFilterNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.state = None
        self._sig = None
        self._r = None
    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
        cut_hz = float(params.get('cutoff', 1000)) / 1000.0
        fps    = max(1.0, float(params.get('fps', 30)))
        sig = (cut_hz, fps)
        if sig != self._sig:
            self._r = 1.0 - np.exp(-2.0 * np.pi * cut_hz / fps)
            self._sig = sig
        if self.state is None: self.state = v
        self.state = (1.0 - self._r) * self.state + self._r * v
        return {'filtered': self.state, 'raw': v}

    def lisser(self, x, params):
        cut_hz = float(params.get('cutoff', 1000)) / 1000.0
        fps = max(1.0, float(params.get('fps', 30)))
        r = 1.0 - np.exp(-2.0 * np.pi * cut_hz / fps)

        def passe(s):
            out = np.empty_like(s)
            etat = s[0]
            for i, v in enumerate(s):
                etat = (1.0 - r) * etat + r * v
                out[i] = etat
            return out

        return _aller_retour(x, passe)

# ---------------------------------------------------------------------------
# 7. Holt-Winters (Double Exponential Smoothing — level + trend)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_holt',
    label='Holt-Winters',
    category='signal',
    icon='TrendingUp',
    description="Double exponential smoothing. Tracks level AND trend. alpha=smoothing, beta=trend.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'trend', 'color': 'scalar'},
             {'id': 'raw', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    params=[
        {'id': 'alpha', 'min': 1, 'max': 100, 'step': 1, 'default': 20},
        {'id': 'beta',  'min': 1, 'max': 100, 'step': 1, 'default': 10},
    ]
)
class HoltWintersNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.L = None  # level
        self.T = 0.0   # trend
    def flux(self, inputs, params):
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

    def lisser(self, x, params):
        al = float(params.get('alpha', 20)) / 100.0
        be = float(params.get('beta', 10)) / 100.0

        def passe(s):
            out = np.empty_like(s)
            L, T = s[0], 0.0
            for i, v in enumerate(s):
                L_prec = L
                L = al * v + (1.0 - al) * (L + T)
                T = be * (L - L_prec) + (1.0 - be) * T
                out[i] = L + T
            return out

        return _aller_retour(x, passe)

# ---------------------------------------------------------------------------
# 8. Gaussian Smoothing (buffer convolution)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_gaussian',
    label='Gaussian Smooth',
    category='signal',
    icon='Bell',
    description="Convolves signal buffer with a Gaussian kernel. sigma controls spread.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[
        {'id': 'window', 'min': 3, 'max': 101, 'step': 2, 'default': 15},
        {'id': 'sigma',  'min': 1, 'max': 50,  'step': 1, 'default': 5},
    ]
)
class GaussianSmoothNode(FiltreSerie, NodeProcessor):
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

    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
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

    def lisser(self, x, params):
        w = int(params.get('window', 15))
        if w % 2 == 0:
            w += 1
        return _convolue_centre(x, self._gauss_kernel(w, float(params.get('sigma', 5))))

# ---------------------------------------------------------------------------
# 9. LOESS / LOWESS (local weighted polynomial regression, degree 1)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_loess',
    label='LOESS / LOWESS',
    category='signal',
    icon='Spline',
    description="Local regression smoother. span = fraction of points used for each estimate.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[{'id': 'span', 'min': 5, 'max': 100, 'step': 1, 'default': 30}]
)
class LOESSNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.buf = []

    @staticmethod
    def _tricubic(u):
        u = np.clip(np.abs(u), 0, 1)
        return (1.0 - u ** 3) ** 3

    def flux(self, inputs, params):
        v = _to_scalar(inputs.get('value'))
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

    def lisser(self, x, params):
        span = max(5, int(params.get('span', 30)))
        n = len(x)
        k = max(3, min(span, n))
        t = np.arange(n, dtype=np.float64)
        out = np.empty(n)
        for i in range(n):
            # Voisinage des DEUX cotes du point estime, au lieu du seul passe.
            dep, fin = max(0, i - k // 2), min(n, i + k // 2 + 1)
            xi, yi = t[dep:fin], x[dep:fin]
            d = np.abs(xi - t[i])
            wgt = self._tricubic(d / (d.max() + 1e-10))
            A = np.column_stack([np.ones(len(xi)), xi])
            try:
                W = np.diag(wgt)
                coef = np.linalg.solve(A.T @ W @ A, A.T @ W @ yi)
                out[i] = coef[0] + coef[1] * t[i]
            except Exception:
                out[i] = x[i]
        return out

# ---------------------------------------------------------------------------
# 10. Particle Filter (1D, random-walk state model)
# ---------------------------------------------------------------------------
@vision_node(
    type_id='plugin_filter_particle',
    label='Particle Filter',
    category='signal',
    icon='Sparkles',
    description="Sequential Monte Carlo estimator. particles = N hypotheses about the true state.",
    inputs=[{'id': 'value', 'color': 'scalar'}, {'id': 'list', 'color': 'list'}],
    outputs=[{'id': 'filtered', 'color': 'scalar'}, {'id': 'raw', 'color': 'scalar'},
             {'id': 'list', 'color': 'list'}],
    params=[
        {'id': 'particles',   'min': 10, 'max': 500, 'step': 10, 'default': 100},
        {'id': 'process_std', 'min': 1,  'max': 200, 'step': 1,  'default': 10},
        {'id': 'meas_std',    'min': 1,  'max': 500, 'step': 1,  'default': 50},
    ]
)
class ParticleFilterNode(FiltreSerie, NodeProcessor):
    def __init__(self):
        self.particles = None
        self.weights   = None

    def flux(self, inputs, params):
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

    def lisser(self, x, params):
        N = max(10, int(params.get('particles', 100)))
        p_std = float(params.get('process_std', 10)) / 100.0
        m_std = float(params.get('meas_std', 50)) / 100.0

        def passe(s):
            out = np.empty_like(s)
            part = np.full(N, s[0])
            for i, z in enumerate(s):
                part = part + np.random.randn(N) * p_std
                log_w = -0.5 * ((part - z) / (m_std + 1e-10)) ** 2
                log_w -= log_w.max()
                w = np.exp(log_w)
                w /= w.sum()
                out[i] = float(np.dot(w, part))
                cum = np.cumsum(w)
                part = part[np.searchsorted(cum, (np.arange(N) + np.random.uniform()) / N)]
            return out

        return _aller_retour(x, passe)
