"""
ml_loss_explorer.py — visualise a training loss and its gradient (ch15).

A single pedagogical node covering the six losses of chapter 15: cross-entropy
(softmax), soft Dice, focal, smooth-L1 (Huber), IoU/GIoU and InfoNCE. It plots
the loss AND its gradient over the natural input axis of each loss, so the
reader sees where the gradient saturates, explodes or points off-target, and
how the key hyper-parameter (gamma, alpha, beta, tau) reshapes the curve.

No matplotlib dependency: the plot is drawn with OpenCV on a numpy canvas.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

_LOSSES = ['Cross-Entropy', 'Dice', 'Focal', 'Smooth L1 (Huber)', 'GIoU', 'InfoNCE']

_W, _H = 560, 360
_PADL, _PADR, _PADT, _PADB = 60, 20, 30, 40


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


class _Curve:
    """Small helper to draw labelled loss/gradient curves on a BGR canvas."""

    def __init__(self, xlabel):
        self.img = np.full((_H, _W, 3), 255, np.uint8)
        self.xlabel = xlabel

    def _px(self, xs, ys, xlim, ylim):
        x0, x1 = xlim
        y0, y1 = ylim
        gx = _PADL + (xs - x0) / (x1 - x0 + 1e-9) * (_W - _PADL - _PADR)
        gy = (_H - _PADB) - (ys - y0) / (y1 - y0 + 1e-9) * (_H - _PADT - _PADB)
        return np.stack([gx, gy], axis=1).astype(np.int32)

    def axes(self, xlim, ylim):
        c = (180, 180, 180)
        cv2.rectangle(self.img, (_PADL, _PADT), (_W - _PADR, _H - _PADB), c, 1)
        cv2.putText(self.img, self.xlabel, (_W // 2 - 30, _H - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1, cv2.LINE_AA)
        # y=0 line if in range
        y0, y1 = ylim
        if y0 < 0 < y1:
            zero = self._px(np.array([xlim[0], xlim[1]]), np.array([0.0, 0.0]), xlim, ylim)
            cv2.line(self.img, tuple(zero[0]), tuple(zero[1]), (210, 210, 210), 1)

    def plot(self, xs, ys, xlim, ylim, color, label, yoff):
        pts = self._px(xs, ys, xlim, ylim)
        cv2.polylines(self.img, [pts], False, color, 2, cv2.LINE_AA)
        cv2.putText(self.img, label, (_PADL + 8, _PADT + 18 + yoff),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    def mark(self, x, y, xlim, ylim):
        p = self._px(np.array([x]), np.array([y]), xlim, ylim)[0]
        cv2.circle(self.img, tuple(p), 5, (0, 0, 0), -1, cv2.LINE_AA)


@vision_node(
    type_id='ml_loss_explorer',
    label='Loss Explorer',
    category='Machine Learning',
    icon='TrendingDown',
    description=(
        "Plot a training loss and its gradient (ch15). Pick a loss and the node "
        "draws cost + gradient over the loss's natural input axis, marking the "
        "operating point. Sweep the hyper-parameter (gamma/alpha/beta/tau) to see "
        "the gradient saturate, explode or flatten:\n"
        "• Cross-Entropy — gradient = y_hat - y on the logit axis.\n"
        "• Dice — soft Dice vs predicted probability.\n"
        "• Focal — (1-pt)^gamma damps easy examples.\n"
        "• Smooth L1 (Huber) — L2 near 0, L1 far (vs pure L2).\n"
        "• GIoU — flat IoU loss vs sloped GIoU as boxes separate.\n"
        "• InfoNCE — positive probability and cost vs temperature tau."
    ),
    inputs=[],
    outputs=[
        {'id': 'main', 'color': 'image',  'label': 'Plot'},
        {'id': 'loss', 'color': 'scalar', 'label': 'Loss'},
        {'id': 'grad', 'color': 'scalar', 'label': 'Gradient'},
        {'id': 'data', 'color': 'dict',   'label': 'Info'},
    ],
    params=[
        {'id': 'loss', 'label': 'Loss', 'type': 'enum', 'options': _LOSSES, 'default': 0},
        {'id': 'point', 'label': 'Operating Point', 'type': 'float',
         'default': 0.5, 'min': 0.01, 'max': 0.99, 'step': 0.01},
        {'id': 'gamma', 'label': 'Focal gamma', 'type': 'float', 'default': 2.0, 'min': 0.0, 'max': 5.0, 'step': 0.5},
        {'id': 'alpha', 'label': 'Focal alpha', 'type': 'float', 'default': 0.25, 'min': 0.0, 'max': 1.0, 'step': 0.05},
        {'id': 'beta',  'label': 'Huber beta',  'type': 'float', 'default': 1.0, 'min': 0.1, 'max': 5.0, 'step': 0.1},
        {'id': 'tau',   'label': 'InfoNCE tau',  'type': 'float', 'default': 0.5, 'min': 0.05, 'max': 2.0, 'step': 0.05},
    ],
)
class LossExplorerNode(NodeProcessor):

    def process(self, inputs, params):
        loss = params.get('loss', 'Cross-Entropy')
        if isinstance(loss, (int, float)):
            loss = _LOSSES[int(loss)] if 0 <= int(loss) < len(_LOSSES) else _LOSSES[0]
        pt = float(params.get('point', 0.5))
        g = float(params.get('gamma', 2.0))
        a = float(params.get('alpha', 0.25))
        beta = float(params.get('beta', 1.0))
        tau = float(params.get('tau', 0.5))

        if loss == 'Cross-Entropy':
            img, L, G, info = self._cross_entropy(pt)
        elif loss == 'Dice':
            img, L, G, info = self._dice(pt)
        elif loss == 'Focal':
            img, L, G, info = self._focal(pt, g, a)
        elif loss == 'Smooth L1 (Huber)':
            img, L, G, info = self._huber(pt, beta)
        elif loss == 'GIoU':
            img, L, G, info = self._giou(pt)
        else:
            img, L, G, info = self._infonce(tau)

        title = f"{loss}   L={round(L,4)}   grad={round(G,4)}"
        cv2.putText(img, title, (_PADL, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 0, 0), 1, cv2.LINE_AA)
        return {'main': img, 'loss': round(float(L), 5), 'grad': round(float(G), 5),
                'data': {'loss_name': loss, **info}}

    # ── Cross-entropy on the logit axis: grad = y_hat - y (§15.1) ──
    def _cross_entropy(self, pt):
        z = np.linspace(-6, 6, 400)
        yhat = _sigmoid(z)
        L = -np.log(np.clip(yhat, 1e-6, 1.0))   # target y=1
        grad = yhat - 1.0                        # gradient on logit
        c = _Curve("logit z  (target = 1)")
        xlim, ylim = (-6, 6), (-1.2, 6.0)
        c.axes(xlim, ylim)
        c.plot(z, L, xlim, ylim, (0, 90, 200), "loss  -log(y_hat)", 0)
        c.plot(z, grad, xlim, ylim, (200, 90, 0), "grad  y_hat - y", 20)
        z0 = np.log(pt / (1 - pt))
        L0 = float(-np.log(pt)); G0 = float(pt - 1.0)
        c.mark(z0, L0, xlim, ylim)
        return c.img, L0, G0, {'y_hat': round(pt, 3)}

    # ── Soft Dice for a single positive pixel (§15.2) ──
    def _dice(self, p):
        pp = np.linspace(0.001, 1.0, 400)
        dice = 2 * pp / (pp + 1.0)
        L = 1.0 - dice
        grad = -2.0 / (pp + 1.0) ** 2            # dL/dp
        c = _Curve("predicted prob p  (object pixel, g=1)")
        xlim, ylim = (0, 1), (-2.2, 1.1)
        c.axes(xlim, ylim)
        c.plot(pp, L, xlim, ylim, (0, 90, 200), "loss  1 - 2p/(p+1)", 0)
        c.plot(pp, grad, xlim, ylim, (200, 90, 0), "grad  dL/dp", 20)
        L0 = float(1.0 - 2 * p / (p + 1)); G0 = float(-2.0 / (p + 1) ** 2)
        c.mark(p, L0, xlim, ylim)
        return c.img, L0, G0, {'p': round(p, 3)}

    # ── Focal loss vs cross-entropy (§15.3) ──
    def _focal(self, ptv, g, a):
        p = np.linspace(0.001, 1.0, 400)
        ce = -np.log(p)
        focal = a * (1 - p) ** g * (-np.log(p))
        c = _Curve("pt = prob of true class")
        xlim, ylim = (0, 1), (0, 3.0)
        c.axes(xlim, ylim)
        c.plot(p, ce, xlim, ylim, (170, 170, 170), "cross-entropy", 0)
        c.plot(p, focal, xlim, ylim, (0, 90, 200), f"focal (g={g}, a={a})", 20)
        L0 = float(a * (1 - ptv) ** g * (-np.log(ptv)))
        # gradient magnitude proxy: dL/dpt
        G0 = float(a * ((1 - ptv) ** g * (-1.0 / ptv) + g * (1 - ptv) ** (g - 1) * np.log(ptv)))
        c.mark(ptv, L0, xlim, ylim)
        ce0 = float(-np.log(ptv))
        return c.img, L0, G0, {'pt': round(ptv, 3), 'ce': round(ce0, 4),
                               'attenuation': round((1 - ptv) ** g, 4)}

    # ── Smooth L1 (Huber) vs L2 (§15.4) ──
    def _huber(self, ptv, beta):
        x = np.linspace(-3 * beta, 3 * beta, 400)
        l2 = 0.5 * x ** 2
        h = np.where(np.abs(x) < beta, 0.5 * x ** 2 / beta, np.abs(x) - 0.5 * beta)
        c = _Curve("residual x")
        xlim = (-3 * beta, 3 * beta)
        ylim = (0, float(max(h.max(), 1e-3)) * 1.1)
        c.axes(xlim, ylim)
        c.plot(x, l2, xlim, ylim, (170, 170, 170), "L2 = 0.5 x^2", 0)
        c.plot(x, h, xlim, ylim, (0, 90, 200), f"smooth L1 (beta={beta})", 20)
        # operating point: map [0.01,0.99] -> residual across range
        xr = (ptv * 2 - 1) * 3 * beta
        if abs(xr) < beta:
            L0 = 0.5 * xr ** 2 / beta; G0 = xr / beta
        else:
            L0 = abs(xr) - 0.5 * beta; G0 = float(np.sign(xr))
        c.mark(xr, L0, xlim, ylim)
        return c.img, float(L0), float(G0), {'residual': round(float(xr), 3), 'beta': beta}

    # ── IoU loss vs GIoU as two 1-D boxes separate (§15.5) ──
    def _giou(self, ptv):
        s = 2.0                                  # box side
        t = np.linspace(0.0, 4.0, 400)           # centre offset
        a0, a1 = 0.0, s
        b0 = t; b1 = t + s
        inter = np.clip(np.minimum(a1, b1) - np.maximum(a0, b0), 0, None)
        union = 2 * s - inter
        iou = inter / union
        cmin = np.minimum(a0, b0); cmax = np.maximum(a1, b1)
        cov = cmax - cmin
        giou = iou - (cov - union) / cov
        L_iou = 1 - iou
        L_giou = 1 - giou
        c = _Curve("centre offset between boxes")
        xlim, ylim = (0, 4), (0, 2.1)
        c.axes(xlim, ylim)
        c.plot(t, L_iou, xlim, ylim, (170, 170, 170), "L_IoU (flat once disjoint)", 0)
        c.plot(t, L_giou, xlim, ylim, (0, 90, 200), "L_GIoU (keeps sloping)", 20)
        toff = ptv * 4.0
        # eval at toff
        it = max(0.0, min(s, toff + s) - max(0.0, toff))
        un = 2 * s - it
        io = it / un
        cv_ = (toff + s) - 0.0
        gi = io - (cv_ - un) / cv_
        L0 = 1 - gi
        c.mark(toff, L0, xlim, ylim)
        return c.img, float(L0), float(1 - io), {'offset': round(toff, 3),
                                                 'iou': round(float(io), 4),
                                                 'giou': round(float(gi), 4)}

    # ── InfoNCE: positive prob & cost vs temperature (§15.6) ──
    def _infonce(self, tauv):
        sims = np.array([0.9, 0.3, 0.2])         # positive, neg, neg
        taus = np.linspace(0.05, 2.0, 400)
        ppos = np.array([np.exp(sims[0] / tt) / np.sum(np.exp(sims / tt)) for tt in taus])
        L = -np.log(ppos)
        c = _Curve("temperature tau")
        xlim, ylim = (0.05, 2.0), (0, 1.3)
        c.axes(xlim, ylim)
        c.plot(taus, ppos, xlim, ylim, (200, 90, 0), "p(positive)", 0)
        c.plot(taus, L, xlim, ylim, (0, 90, 200), "loss -log p(pos)", 20)
        pp0 = float(np.exp(sims[0] / tauv) / np.sum(np.exp(sims / tauv)))
        L0 = float(-np.log(pp0))
        c.mark(tauv, pp0, xlim, ylim)
        return c.img, L0, float(pp0 - 1.0), {'tau': round(tauv, 3),
                                             'p_positive': round(pp0, 4)}
