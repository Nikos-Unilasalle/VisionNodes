import cv2
import numpy as np
from registry import vision_node, NodeProcessor

MAX_GROUPS = 300   # above this, consecutive objects are pooled before the exact segmentation
MAX_ZONE_PORTS = 4
ZONE_COLORS = [(0x2e, 0x7d, 0x32), (0x00, 0xac, 0xc1), (0xff, 0xca, 0x28), (0xff, 0x70, 0x43),
               (0xab, 0x47, 0xbc), (0x5c, 0x6b, 0xc0)]  # RGB


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def _pool(pos, val, wt):
    """Sufficient statistics (Σw, Σwv, Σwv², mean position) for groups of consecutive objects."""
    n = len(pos)
    edges = np.linspace(0, n, min(n, MAX_GROUPS) + 1).astype(int)
    sl = [slice(a, b) for a, b in zip(edges[:-1], edges[1:]) if b > a]
    W = np.array([wt[s].sum() for s in sl])
    S1 = np.array([(wt[s] * val[s]).sum() for s in sl])
    S2 = np.array([(wt[s] * val[s] ** 2).sum() for s in sl])
    C = np.array([s.stop - s.start for s in sl])
    P = np.array([pos[s.stop - 1] for s in sl])
    return W, S1, S2, C, P


def _segment(W, S1, S2, C, k, min_items):
    """Optimal split of an ordered sequence into k contiguous segments (weighted least squares,
    dynamic programming). Returns (cost, cut indices into the group sequence)."""
    n = len(W)
    cw, c1, c2, cc = (np.r_[0, np.cumsum(a)] for a in (W, S1, S2, C))
    inf = np.inf
    cost = np.full((k + 1, n + 1), inf)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0.0
    for m in range(1, k + 1):
        for j in range(1, n + 1):
            i = np.arange(0, j)
            i = i[(cc[j] - cc[i] >= min_items) & np.isfinite(cost[m - 1, i])]
            if not len(i):
                continue
            ww = np.maximum(cw[j] - cw[i], 1e-12)
            seg = (c2[j] - c2[i]) - (c1[j] - c1[i]) ** 2 / ww
            tot = cost[m - 1, i] + seg
            a = int(np.argmin(tot))
            cost[m, j], back[m, j] = tot[a], i[a]
    if not np.isfinite(cost[k, n]):
        return inf, []
    cuts, j = [], n
    for m in range(k, 0, -1):
        j = back[m, j]
        cuts.append(j)
    return float(cost[k, n]), sorted(cuts)[1:]


def _boundaries(P, cuts):
    return [float((P[c - 1] + P[c]) / 2) if c < len(P) else float(P[-1]) for c in cuts]


def _fit(pos, val, wt, k, min_items):
    """(cuts, boundaries) of the best k-zone split, or None if k zones cannot be formed."""
    g = _pool(pos, val, wt)
    sse, cuts = _segment(*g[:4], k, min_items)
    if not np.isfinite(sse) or len(cuts) != k - 1:
        return None
    return sse, _boundaries(g[4], cuts)


def _outliers(val, k_mad, window, side=0):
    """Objects far from the running median of their neighbours along the (sorted) position:
    |value − local median| > k_mad × robust SD of all residuals (1.4826 × MAD)."""
    n = len(val)
    half = max(2, window // 2)
    local = np.array([np.median(val[max(0, i - half):i + half + 1]) for i in range(n)])
    res = val - local
    sd = max(1.4826 * np.median(np.abs(res - np.median(res))), 1e-6)
    dev = np.abs(res) if side == 0 else (res if side == 1 else -res)
    return dev > k_mad * sd


def _main_zone(k, edges, medians, similar, use_log):
    """(first, last) zone indices of the main zone (largest share of a disc, ∝ to² − from²),
    grown over neighbours whose median is within the `similar` ratio of its own."""
    share = [max(edges[z + 1], 0) ** 2 - max(edges[z], 0) ** 2 for z in range(k)]
    m = int(np.argmax(share))
    lim = -np.log(similar) if use_log else (1 - similar) * abs(medians[m])
    close = lambda z: abs(medians[z] - medians[m]) <= lim + 1e-9
    first, last = m, m
    while first > 0 and close(first - 1):
        first -= 1
    while last < k - 1 and close(last + 1):
        last += 1
    return first, last


def _main_rise(k, edges, medians, similar, use_log):
    """Index of the zone that starts with the largest step up of the median, among the
    boundaries up to the start of the main zone (only rises beyond the `similar` ratio count).
    When the innermost zone is itself the main zone (a finely resolved core holds most
    objects), every boundary is searched instead. None if the value never steps up."""
    first = _main_zone(k, edges, medians, similar, use_log)[0]
    last = first if first > 0 else k - 1
    best, best_step = None, 0.0
    for z in range(1, last + 1):
        step = medians[z] - medians[z - 1]
        lim = -np.log(similar) if use_log else (1 - similar) * abs(medians[z - 1])
        rel = step if use_log else step / max(abs(medians[z - 1]), 1e-9)
        if step > lim + 1e-9 and rel > best_step:
            best, best_step = z, rel
    return best


def _core_start(k, edges, medians, similar, use_log, rule):
    """First zone outside the core, by the chosen rule (0 = main zone, 1 = main rise)."""
    if rule == 1:
        return _main_rise(k, edges, medians, similar, use_log) or 0
    return _main_zone(k, edges, medians, similar, use_log)[0]


def _plot(pos, val, zone_of, bounds, lo_hi, medians, log_scale, key_pos, key_val, outlier):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4), dpi=100)
    for z in range(len(bounds) + 1):
        sel = (zone_of == z) & ~outlier
        col = np.array(ZONE_COLORS[z % len(ZONE_COLORS)]) / 255
        ax.scatter(pos[sel], val[sel], s=9, color=col, alpha=0.75, label=f'zone {z + 1}')
    if outlier.any():
        ax.scatter(pos[outlier], val[outlier], s=22, marker='x', color='#d32f2f', label='outlier')
    edges = [pos.min()] + list(bounds) + [pos.max()]
    for z, med in enumerate(medians):
        ax.hlines(med, edges[z], edges[z + 1], color='k', lw=2)
    for b, (lo, hi) in zip(bounds, lo_hi):
        ax.axvline(b, color='k', ls='--', lw=1)
        if hi > lo:
            ax.axvspan(lo, hi, color='k', alpha=0.08)
    if log_scale:
        ax.set_yscale('log')
    ax.set_xlabel(key_pos)
    ax.set_ylabel(key_val)
    ax.legend(fontsize=8, loc='best')
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
    plt.close(fig)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


@vision_node(
    type_id='sci_profile_zoning',
    label='Profile Zoning',
    category='analyze',
    icon='SplitSquareHorizontal',
    description=(
        "Splits objects into contiguous zones along a position (e.g. ρ from Radial "
        "Coordinates, depth, distance) so that a measured value (size, intensity…) is as "
        "homogeneous as possible inside each zone. The split is optimal (dynamic programming on "
        "the ordered objects); with Zones = 0 the number of zones is chosen by BIC "
        "(adding a zone must pay for itself). Objects can be weighted by a confidence key.\n\n"
        "Boundary uncertainty is estimated by bootstrap (objects resampled): the plot shades "
        "the 90 % interval of each boundary and the Membership map gives, for every pixel, the "
        "probability that it belongs to the zone it is assigned to. Connect a position map to "
        "get the zone map and zone masks.\n\n"
        "Robust fit: objects far from the running median of their neighbours along the position "
        "(Outlier Cut × robust SD) are set aside before zoning; they come out as Outliers, often a population of their "
        "own (e.g. vessels among cells).\n\n"
        "Main zone = the zone covering most of a disc (share ∝ to² − from²), grown over its "
        "neighbours whose median is within the Merge ratio.\n"
        "Core Is: everything inside the main zone, or everything inside the main rise — the "
        "boundary, inside the main zone, where the value steps up the most (e.g. small stele "
        "cells → larger cortex cells, even with a large-celled pith at the centre). "
        "The core edge and its bootstrap interval are in the stats."
    ),
    inputs=[
        {'id': 'items', 'color': 'list', 'label': 'Objects'},
        {'id': 'position', 'color': 'any', 'label': 'Position Map (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Profile Plot'},
        {'id': 'zones', 'color': 'markers', 'label': 'Zone Labels (1..N)'},
        {'id': 'membership', 'color': 'any', 'label': 'Membership (0–1)'},
        {'id': 'items', 'color': 'list', 'label': 'Objects + zone'},
        {'id': 'inliers', 'color': 'list', 'label': 'Typical Objects'},
        {'id': 'outliers', 'color': 'list', 'label': 'Outliers'},
        {'id': 'boundaries', 'color': 'list'},
        {'id': 'stats', 'color': 'dict'},
        {'id': 'count', 'color': 'scalar', 'label': 'Zones'},
        {'id': 'core', 'color': 'mask', 'label': 'Core'},
        {'id': 'core_edge', 'color': 'scalar', 'label': 'Core Edge (position)'},
        *({'id': f'zone_{i}', 'color': 'mask'} for i in range(1, MAX_ZONE_PORTS + 1)),
    ],
    params=[
        {'id': 'position_key', 'label': 'Position Key', 'type': 'string', 'default': 'rho'},
        {'id': 'value_key', 'label': 'Value Key', 'type': 'string', 'default': 'radius'},
        {'id': 'weight_key', 'label': 'Weight Key (empty = equal)', 'type': 'string', 'default': 'score'},
        {'id': 'log_values', 'label': 'Log Values', 'type': 'bool', 'default': True},
        {'id': 'zones', 'label': 'Zones (0 = auto)', 'type': 'int', 'default': 0, 'min': 0, 'max': 8},
        {'id': 'max_zones', 'label': 'Max Zones (auto)', 'type': 'int', 'default': 6, 'min': 1, 'max': 8},
        {'id': 'outlier_mad', 'label': 'Outlier Cut (× robust SD, 0 = off)', 'type': 'float', 'default': 3.0, 'min': 0, 'max': 10, 'step': 0.5},
        {'id': 'outlier_side', 'label': 'Outliers', 'type': 'enum', 'default': 0,
         'options': ['Above and below', 'Above only', 'Below only']},
        {'id': 'min_items', 'label': 'Min Objects per Zone', 'type': 'int', 'default': 12, 'min': 2, 'max': 500},
        {'id': 'core_rule', 'label': 'Core Is', 'type': 'enum', 'default': 0,
         'options': ['Inside the main zone', 'Inside the main rise']},
        {'id': 'similar', 'label': 'Main Zone Merge (median ratio)', 'type': 'float', 'default': 0.8, 'min': 0.3, 'max': 1, 'step': 0.05},
        {'id': 'n_boot', 'label': 'Bootstrap Runs', 'type': 'int', 'default': 50, 'min': 0, 'max': 500},
        {'id': 'seed', 'label': 'Random Seed', 'type': 'int', 'default': 0},
    ],
)
class ProfileZoningNode(NodeProcessor):
    def process(self, inputs, params):
        out = {'main': None, 'zones': None, 'membership': None, 'items': [], 'inliers': [], 'outliers': [], 'boundaries': [],
               'core': None, 'core_edge': None,
               'stats': {}, 'count': 0, **{f'zone_{i}': None for i in range(1, MAX_ZONE_PORTS + 1)}}
        kp, kv = str(params.get('position_key', 'rho')), str(params.get('value_key', 'radius'))
        kw = str(params.get('weight_key', '') or '').strip()
        use_log = bool(params.get('log_values', True))
        rows = []
        for it in inputs.get('items') or []:
            if not isinstance(it, dict):
                continue
            p, v = _num(it.get(kp)), _num(it.get(kv))
            w = _num(it.get(kw)) if kw else 1.0
            if p is None or v is None or (use_log and v <= 0):
                continue
            rows.append((p, np.log(v) if use_log else v, np.clip(w if w is not None else 1.0, 0.2, 5.0), it))
        min_items = int(params.get('min_items', 12))
        if len(rows) < min_items:
            return out
        rows.sort(key=lambda r: r[0])
        pos = np.array([r[0] for r in rows])
        val = np.array([r[1] for r in rows])
        wt = np.array([r[2] for r in rows])
        n = len(rows)

        fixed = int(params.get('zones', 0))
        k_mad = float(params.get('outlier_mad', 3.0))

        def choose(p_, v_, w_):
            if fixed > 0:
                f = _fit(p_, v_, w_, fixed, min_items)
                return (fixed, f[1]) if f else None
            best = None
            for k_try in range(1, int(params.get('max_zones', 6)) + 1):
                f = _fit(p_, v_, w_, k_try, min_items)
                if f is None:
                    break
                # 3 parameters per zone (level, spread, boundary): BIC on the weighted residuals
                bic = len(p_) * np.log(max(f[0], 1e-12) / w_.sum()) + 3 * k_try * np.log(len(p_))
                if best is None or bic < best[0]:
                    best = (bic, k_try, f[1])
            return best[1:] if best else None

        # robust fit: objects unlike their neighbours along the position are set aside first
        # (a different population, e.g. vessels among cells), then the zones are fitted
        outlier = _outliers(val, k_mad, 2 * min_items + 1, int(params.get('outlier_side', 0))) if k_mad > 0 else np.zeros(n, bool)
        res = choose(pos[~outlier], val[~outlier], wt[~outlier])
        if res is None:
            return out
        k, bounds = res
        inl = ~outlier
        n_in = int(inl.sum())

        # bootstrap: same number of zones, inlier objects resampled
        rng = np.random.default_rng(int(params.get('seed', 0)))
        boots, boot_core = [], []
        pi, vi, wi = pos[inl], val[inl], wt[inl]
        similar = float(params.get('similar', 0.8))
        core_rule = int(params.get('core_rule', 0))
        for _ in range(int(params.get('n_boot', 50)) if k > 1 else 0):
            s = np.sort(rng.integers(0, n_in, n_in))
            f = _fit(pi[s], vi[s], wi[s], k, min_items)
            if f is None:
                continue
            boots.append(f[1])
            # core edge of this resample, found by the same main-zone rule
            zb = np.searchsorted(f[1], pi[s], side='right')
            if all((zb == z).any() for z in range(k)):
                eb = [float(pi[s].min())] + f[1] + [float(pi[s].max())]
                fb = _core_start(k, eb, [float(np.median(vi[s][zb == z])) for z in range(k)], similar, use_log,
                                 core_rule)
                if fb > 0:
                    boot_core.append(eb[fb])
        boots = np.array(boots, dtype=float).reshape(len(boots), k - 1)
        lo_hi = [(float(np.percentile(boots[:, i], 5)), float(np.percentile(boots[:, i], 95)))
                 if len(boots) else (b, b) for i, b in enumerate(bounds)]

        zone_of = np.searchsorted(bounds, pos, side='right')
        to_val = np.exp if use_log else (lambda x: x)
        medians = [float(np.median(val[(zone_of == z) & inl])) for z in range(k)]
        stats = {'zones': k, 'objects': n, 'outliers': int(outlier.sum())}
        edges = [float(pos.min())] + bounds + [float(pos.max())]
        for z in range(k):
            sel = (zone_of == z) & inl
            vz = to_val(val[sel])
            stats[f'zone_{z + 1}_from'] = edges[z]
            stats[f'zone_{z + 1}_to'] = edges[z + 1]
            stats[f'zone_{z + 1}_n'] = int(sel.sum())
            stats[f'zone_{z + 1}_median_{kv}'] = float(np.median(vz))
            stats[f'zone_{z + 1}_outliers'] = int(((zone_of == z) & outlier).sum())
        first, last = _main_zone(k, edges, medians, similar, use_log)
        stats['main_zone_from'], stats['main_zone_to'] = first + 1, last + 1
        stats[f'main_zone_median_{kv}'] = float(to_val(np.median(val[(zone_of >= first) & (zone_of <= last) & inl])))
        c0 = _core_start(k, edges, medians, similar, use_log, core_rule)
        core_edge = edges[c0] if c0 > 0 else None
        stats['core_edge'] = core_edge
        if c0 > 0 and boot_core:
            stats['core_edge_low'] = float(np.percentile(boot_core, 5))
            stats['core_edge_high'] = float(np.percentile(boot_core, 95))
        elif c0 > 0:
            stats['core_edge_low'] = stats['core_edge_high'] = core_edge
        for i, (b, (lo, hi)) in enumerate(zip(bounds, lo_hi), start=1):
            stats[f'boundary_{i}'] = b
            stats[f'boundary_{i}_low'] = lo
            stats[f'boundary_{i}_high'] = hi

        out.update(
            main=_plot(pos, to_val(val), zone_of, bounds, lo_hi, [to_val(m) for m in medians], use_log, kp, kv, outlier),
            items=[{**r[3], 'zone': int(z) + 1, 'outlier': bool(o)} for r, z, o in zip(rows, zone_of, outlier)],
            inliers=[{**r[3], 'zone': int(z) + 1} for r, z, o in zip(rows, zone_of, outlier) if not o],
            outliers=[{**r[3], 'zone': int(z) + 1} for r, z, o in zip(rows, zone_of, outlier) if o],
            boundaries=bounds, stats=stats, count=k, core_edge=core_edge)

        pmap = inputs.get('position')
        if isinstance(pmap, np.ndarray) and pmap.ndim == 2:
            pm = pmap.astype(np.float32)
            inside = np.isfinite(pm) & (pm >= 0)
            zones = np.where(inside, np.searchsorted(bounds, np.nan_to_num(pm), side='right') + 1, 0).astype(np.int32)
            if len(boots):
                # probability that a pixel falls in its assigned zone, over bootstrap partitions
                agree = np.zeros(pm.shape, np.float32)
                for b in boots:
                    agree += np.searchsorted(b, np.nan_to_num(pm), side='right') + 1 == zones
                membership = np.where(inside, agree / len(boots), 0).astype(np.float32)
            else:
                membership = inside.astype(np.float32)
            out.update(zones=zones, membership=membership)
            if core_edge is not None:
                out['core'] = (inside & (pm < core_edge)).astype(np.uint8) * 255
            for z in range(1, MAX_ZONE_PORTS + 1):
                out[f'zone_{z}'] = (zones == z).astype(np.uint8) * 255 if z <= k else None
        return out
