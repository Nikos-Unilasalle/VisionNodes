"""
sci_robust_1d.py — robust 1-D statistics for chapter 16.

Four small nodes that make the chapter's scalar-sample pedagogy runnable:
  • Scalar List    — type a list of numbers → a list port (the input source).
  • Robust Location — mean vs median, and how much the last value moves each.
  • MAD Scale       — median, MAD, calibrated sigma, modified z-scores + outlier flags.
  • M-Estimator     — Huber / Tukey influence psi curve, solved by IRLS; reports
                      the robust estimate vs least-squares and the final weights.

Everything is a 1-D sample of scalars, matching §16.1–§16.4.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor


# ── shared helpers (inlined — plugins may not import each other) ──────────────
def _as_array(vals):
    if vals is None:
        return np.array([], dtype=np.float64)
    if isinstance(vals, (int, float)):
        return np.array([float(vals)], dtype=np.float64)
    out = []
    for v in vals:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            pass
    return np.array(out, dtype=np.float64)


def _mad(x, med):
    return float(np.median(np.abs(x - med)))


def _canvas(w=520, h=200):
    return np.full((h, w, 3), 255, np.uint8)


def _numberline(img, x, markers):
    """Draw a 1-D sample as dots on a line, plus labelled marker verticals."""
    h, w = img.shape[:2]
    if x.size == 0:
        return img
    lo, hi = float(x.min()), float(x.max())
    span = (hi - lo) or 1.0
    pad = 50
    y = h - 60

    def gx(v):
        return int(pad + (v - lo) / span * (w - 2 * pad))

    cv2.line(img, (pad, y), (w - pad, y), (180, 180, 180), 1)
    for v in x:
        cv2.circle(img, (gx(v), y), 4, (150, 150, 150), -1, cv2.LINE_AA)
    palette = [(0, 120, 220), (200, 90, 0), (0, 160, 0), (160, 0, 160)]
    for i, (name, val) in enumerate(markers):
        col = palette[i % len(palette)]
        px = gx(val)
        cv2.line(img, (px, y - 40), (px, y + 12), col, 2, cv2.LINE_AA)
        cv2.putText(img, f"{name}={round(val, 3)}", (10, 24 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1, cv2.LINE_AA)
    return img


# ── Scalar List ──────────────────────────────────────────────────────────────
@vision_node(
    type_id='sci_scalar_list',
    label='Scalar List',
    category='data',
    icon='List',
    description=(
        "Type a list of numbers (comma or space separated) and output them as a "
        "list port — the input source for the robust-statistics nodes of ch16. "
        "Example: '2, 3, 5, 7, 800'."
    ),
    inputs=[],
    outputs=[
        {'id': 'list',  'color': 'list',   'label': 'Values'},
        {'id': 'count', 'color': 'scalar', 'label': 'Count'},
    ],
    params=[
        {'id': 'values', 'label': 'Values', 'type': 'string', 'default': '2, 3, 5, 7, 800'},
    ],
)
class ScalarListNode(NodeProcessor):
    def process(self, inputs, params):
        raw = str(params.get('values', ''))
        out = []
        for tok in raw.replace(';', ',').replace('\n', ',').replace(' ', ',').split(','):
            tok = tok.strip()
            if not tok:
                continue
            try:
                out.append(float(tok))
            except ValueError:
                pass
        return {'list': out, 'count': float(len(out))}


# ── Robust Location (§16.1) ──────────────────────────────────────────────────
@vision_node(
    type_id='sci_robust_location',
    label='Robust Location',
    category='measure',
    icon='Crosshair',
    description=(
        "Mean vs median of a scalar sample (§16.1). Also reports how much the "
        "LAST value moves each estimate — the mean's influence is unbounded, the "
        "median's is bounded (it only counts sides). Push one sample to a wild "
        "value: the mean drifts, the median stays put."
    ),
    inputs=[{'id': 'values', 'color': 'list', 'label': 'Values'}],
    outputs=[
        {'id': 'main',           'color': 'image',  'label': 'Overlay'},
        {'id': 'mean',           'color': 'scalar', 'label': 'Mean'},
        {'id': 'median',         'color': 'scalar', 'label': 'Median'},
        {'id': 'mean_influence', 'color': 'scalar', 'label': 'Mean shift (last val)'},
        {'id': 'data',           'color': 'dict',   'label': 'Stats'},
    ],
    params=[],
)
class RobustLocationNode(NodeProcessor):
    def process(self, inputs, params):
        x = _as_array(inputs.get('values'))
        if x.size == 0:
            return {'main': _canvas(), 'mean': 0.0, 'median': 0.0,
                    'mean_influence': 0.0, 'data': None}
        mean = float(np.mean(x))
        median = float(np.median(x))
        if x.size > 1:
            mean_wo = float(np.mean(x[:-1]))
            median_wo = float(np.median(x[:-1]))
        else:
            mean_wo, median_wo = mean, median
        img = _numberline(_canvas(), x, [('mean', mean), ('median', median)])
        return {
            'main': img,
            'mean': round(mean, 4),
            'median': round(median, 4),
            'mean_influence': round(mean - mean_wo, 4),
            'data': {'mean': round(mean, 4), 'median': round(median, 4),
                     'mean_shift_last': round(mean - mean_wo, 4),
                     'median_shift_last': round(median - median_wo, 4),
                     'n': int(x.size)},
        }


# ── MAD Scale (§16.2) ────────────────────────────────────────────────────────
@vision_node(
    type_id='sci_mad_scale',
    label='MAD Scale',
    category='measure',
    icon='Ruler',
    description=(
        "Robust scale of a scalar sample (§16.2): median, MAD, calibrated "
        "sigma_hat = 1.4826*MAD, and the modified z-score z = 0.6745*(x-median)/MAD "
        "per value, flagging |z| > 3.5 as an outlier. The MAD ignores the "
        "aberration that would blow up the classical standard deviation."
    ),
    inputs=[{'id': 'values', 'color': 'list', 'label': 'Values'}],
    outputs=[
        {'id': 'main',      'color': 'image',  'label': 'Overlay'},
        {'id': 'median',    'color': 'scalar', 'label': 'Median'},
        {'id': 'mad',       'color': 'scalar', 'label': 'MAD'},
        {'id': 'sigma_hat', 'color': 'scalar', 'label': 'Sigma_hat'},
        {'id': 'outliers',  'color': 'scalar', 'label': 'Outlier Count'},
        {'id': 'zscores',   'color': 'list',   'label': 'Modified z-scores'},
        {'id': 'data',      'color': 'dict',   'label': 'Stats'},
    ],
    params=[
        {'id': 'z_thresh', 'label': 'z Threshold', 'type': 'float', 'default': 3.5, 'min': 1.0, 'max': 10.0, 'step': 0.5},
    ],
)
class MADScaleNode(NodeProcessor):
    def process(self, inputs, params):
        x = _as_array(inputs.get('values'))
        if x.size == 0:
            return {'main': _canvas(), 'median': 0.0, 'mad': 0.0, 'sigma_hat': 0.0,
                    'outliers': 0.0, 'zscores': [], 'data': None}
        med = float(np.median(x))
        mad = _mad(x, med)
        sigma_hat = 1.4826 * mad
        zt = float(params.get('z_thresh', 3.5))
        if mad > 1e-9:
            z = 0.6745 * (x - med) / mad
        else:
            z = np.zeros_like(x)  # MAD=0 guard (§16.2 pitfall)
        flags = np.abs(z) > zt
        std = float(np.std(x))
        img = _numberline(_canvas(), x, [('median', med), ('sigma_hat', med + sigma_hat)])
        cv2.putText(img, f"classic std={round(std,2)}  (MAD sigma={round(sigma_hat,2)})",
                    (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1, cv2.LINE_AA)
        return {
            'main': img,
            'median': round(med, 4),
            'mad': round(mad, 4),
            'sigma_hat': round(sigma_hat, 4),
            'outliers': float(int(np.count_nonzero(flags))),
            'zscores': [round(float(v), 3) for v in z],
            'data': {'median': round(med, 4), 'mad': round(mad, 4),
                     'sigma_hat': round(sigma_hat, 4), 'classic_std': round(std, 4),
                     'outlier_count': int(np.count_nonzero(flags)),
                     'outlier_values': [round(float(v), 3) for v in x[flags]]},
        }


# ── M-Estimator (Huber / Tukey via IRLS) (§16.3 + §16.4) ─────────────────────
_KERNELS = ['Huber', 'Tukey']


@vision_node(
    type_id='sci_m_estimator',
    label='M-Estimator',
    category='measure',
    icon='Filter',
    description=(
        "Robust location by an M-estimator, solved by IRLS (§16.3–§16.4). Pick "
        "Huber (psi clipped at ±k, bounded but never zero) or Tukey (psi "
        "redescends to 0, outliers fully rejected). The threshold is in units of "
        "sigma_hat (MAD). Outputs the robust estimate vs least-squares, the final "
        "per-point IRLS weights, and plots the influence curve psi."
    ),
    inputs=[{'id': 'values', 'color': 'list', 'label': 'Residuals / Data'}],
    outputs=[
        {'id': 'main',        'color': 'image',  'label': 'psi Curve'},
        {'id': 'estimate',    'color': 'scalar', 'label': 'Robust Estimate'},
        {'id': 'ls_estimate', 'color': 'scalar', 'label': 'Least-Squares'},
        {'id': 'weights',     'color': 'list',   'label': 'Final Weights'},
        {'id': 'data',        'color': 'dict',   'label': 'Stats'},
    ],
    params=[
        {'id': 'kernel', 'label': 'Kernel', 'type': 'enum', 'options': _KERNELS, 'default': 0},
        {'id': 'k_sigma', 'label': 'Threshold (x sigma)', 'type': 'float', 'default': 1.345, 'min': 0.5, 'max': 8.0, 'step': 0.005},
        {'id': 'iterations', 'label': 'IRLS Iterations', 'type': 'int', 'default': 10, 'min': 1, 'max': 50},
    ],
)
class MEstimatorNode(NodeProcessor):

    @staticmethod
    def _weights(e, k, kernel):
        w = np.ones_like(e)
        ae = np.abs(e)
        if kernel == 'Tukey':
            inside = ae <= k
            w[inside] = (1.0 - (e[inside] / k) ** 2) ** 2
            w[~inside] = 0.0
        else:  # Huber
            big = ae > k
            w[big] = k / np.maximum(ae[big], 1e-9)
        return w

    def _psi_curve(self, img, k, kernel):
        w, h = img.shape[1], img.shape[0]
        pad = 50
        xs = np.linspace(-3 * k, 3 * k, 300)
        if kernel == 'Tukey':
            psi = np.where(np.abs(xs) <= k, xs * (1 - (xs / k) ** 2) ** 2, 0.0)
        else:
            psi = np.clip(xs, -k, k)
        pmax = max(abs(psi).max(), 1e-6)
        def gx(v): return int(pad + (v + 3 * k) / (6 * k) * (w - 2 * pad))
        def gy(v): return int((h - 40) - (v + pmax) / (2 * pmax) * (h - 70))
        cv2.line(img, (pad, gy(0)), (w - pad, gy(0)), (210, 210, 210), 1)
        pts = np.array([[gx(x), gy(p)] for x, p in zip(xs, psi)], np.int32)
        cv2.polylines(img, [pts], False, (0, 90, 200), 2, cv2.LINE_AA)
        cv2.putText(img, f"psi ({kernel}, k={round(k,3)})", (pad, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 90, 200), 1, cv2.LINE_AA)
        return img

    def process(self, inputs, params):
        x = _as_array(inputs.get('values'))
        kernel = params.get('kernel', 'Huber')
        if isinstance(kernel, (int, float)):
            kernel = _KERNELS[int(kernel)] if 0 <= int(kernel) < len(_KERNELS) else 'Huber'
        k_sigma = float(params.get('k_sigma', 1.345))
        iters = int(params.get('iterations', 10))

        if x.size == 0:
            return {'main': _canvas(520, 260), 'estimate': 0.0, 'ls_estimate': 0.0,
                    'weights': [], 'data': None}

        ls = float(np.mean(x))
        theta = float(np.median(x))          # robust init (never LS — §16.3)
        w = np.ones_like(x)
        for _ in range(iters):
            e = x - theta
            med = float(np.median(x))
            sigma = 1.4826 * _mad(x, med)
            if sigma < 1e-9:
                break
            k = k_sigma * sigma
            w = self._weights(e / sigma, k_sigma, kernel)  # weight on standardized resid
            sw = float(np.sum(w))
            if sw < 1e-9:
                break
            theta = float(np.sum(w * x) / sw)

        med = float(np.median(x))
        sigma = 1.4826 * _mad(x, med)
        k_plot = k_sigma if sigma < 1e-9 else k_sigma  # psi curve in sigma units
        img = self._psi_curve(_canvas(520, 260), max(k_plot, 0.5), kernel)
        cv2.putText(img, f"robust={round(theta,3)}   LS={round(ls,3)}",
                    (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        return {
            'main': img,
            'estimate': round(theta, 4),
            'ls_estimate': round(ls, 4),
            'weights': [round(float(v), 3) for v in w],
            'data': {'kernel': kernel, 'robust_estimate': round(theta, 4),
                     'ls_estimate': round(ls, 4), 'sigma_hat': round(sigma, 4),
                     'weights': [round(float(v), 3) for v in w]},
        }
