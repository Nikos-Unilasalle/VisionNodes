import cv2
import numpy as np
from registry import vision_node, NodeProcessor

HEX_PACKING = np.pi / (2 * np.sqrt(3))   # 0.9069: densest packing of equal circles
N_POS_BINS = 64


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def _item_xy(item, w, h):
    if 'cx' in item and 'cy' in item:
        return float(item['cx']), float(item['cy'])
    if item.get('pts'):
        x, y = item['pts'][0]
        return (x * w, y * h) if item.get('relative', True) else (float(x), float(y))
    if 'x' in item and 'y' in item:
        return float(item['x']), float(item['y'])
    return None


def _auto_packing(xy, radius):
    """Area fraction covered by the objects where they touch on all sides: π r² over the
    hexagonal territory √3/2 · d², d = mean distance to the 3 nearest neighbours."""
    if len(xy) < 8:
        return None, 0
    from scipy.spatial import cKDTree
    d, j = cKDTree(xy).query(xy, k=4)
    touching = (d[:, 1:] < (radius[:, None] + radius[j[:, 1:]]) * 1.35).all(1)
    if touching.sum() < 10:
        return None, int(touching.sum())
    dn = d[touching, 1:].mean(1)
    phi = np.pi * radius[touching] ** 2 / (np.sqrt(3) / 2 * dn ** 2)
    return float(np.clip(np.median(phi), 0.3, HEX_PACKING)), int(touching.sum())


def _mean_area_profile(pos_obj, area_obj, centers, bw):
    """Nadaraya–Watson estimate of the mean object area at each position (Gaussian kernel)."""
    if bw <= 0 or len(pos_obj) < 3:
        return np.full(len(centers), area_obj.mean())
    k = np.exp(-0.5 * ((centers[:, None] - pos_obj[None, :]) / bw) ** 2) + 1e-12
    return (k * area_obj).sum(1) / k.sum(1)


def _project(pos_obj, area_obj, hist, centers, bw, phi):
    """Expected number of objects tiling the zone: Σ_pixels φ / ā(position)."""
    if hist is None:
        return None
    a = _mean_area_profile(pos_obj, area_obj, centers, bw)
    return float(phi * (hist / a).sum())


@vision_node(
    type_id='sci_sample_projection',
    label='Sample Projection',
    category='analyze',
    icon='ScatterChart',
    description=(
        "Estimates how many objects fill each zone when only part of them could be measured "
        "(blurred or ambiguous areas). The clearly detected objects are a sample: their mean "
        "area, modelled as a smooth function of position (e.g. ρ), tells how much room one "
        "object takes; the zone area divided by that room, times the packing fraction, gives "
        "the expected count (stereological projection, valid for tissue-like packing).\n\n"
        "- Packing 0 = auto: measured on the sample where objects touch their neighbours.\n"
        "- Bandwidth: smoothing of the size model along the position (0 = one mean per zone).\n"
        "- 95 % intervals by bootstrap (objects resampled).\n"
        "Objects of another population (e.g. Profile Zoning outliers) can be connected to "
        "Exclude: their discs are removed from the zone areas; Count Only Inside restricts the "
        "zones to a mask (e.g. tissue minus lacunae); with no Zones connected, that mask is the "
        "single zone 1.\n"
        "Zone Names (opt., e.g. from Masks to Zones) label the per-zone dicts (detected, "
        "projected, estimated), ready for a stacked Bar Chart.\n"
        "Measured Area (opt.): the part of the zones already covered by the sampled objects "
        "(e.g. Cell Tessellation → Resolved). Its objects are then counted exactly and only the "
        "rest of the zone is projected: estimated = measured + projected.\n"
        "Completeness = detected / estimated: how much of the zone the sample really saw. "
        "Caution: if small objects are detected less often than large ones, counts are "
        "under-estimated."
    ),
    inputs=[
        {'id': 'items', 'color': 'list', 'label': 'Sampled Objects'},
        {'id': 'zones', 'color': 'markers', 'label': 'Zones (1..N)'},
        {'id': 'position', 'color': 'any', 'label': 'Position Map (opt.)'},
        {'id': 'px_per_unit', 'color': 'scalar', 'label': 'px per Unit (opt.)'},
        {'id': 'exclude', 'color': 'list', 'label': 'Exclude Objects (opt.)'},
        {'id': 'mask', 'color': 'mask', 'label': 'Count Only Inside (opt.)'},
        {'id': 'measured', 'color': 'mask', 'label': 'Measured Area (opt.)'},
        {'id': 'names', 'color': 'list', 'label': 'Zone Names (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Expected Size Map'},
        {'id': 'stats', 'color': 'dict'},
        {'id': 'total', 'color': 'scalar', 'label': 'Estimated Total'},
        {'id': 'counts', 'color': 'list', 'label': 'Estimated per Zone'},
        {'id': 'size_map', 'color': 'any', 'label': 'Expected Area Map (px²)'},
        {'id': 'packing', 'color': 'scalar', 'label': 'Packing Used'},
        {'id': 'detected_by_zone', 'color': 'dict', 'label': 'Detected per Zone'},
        {'id': 'projected_by_zone', 'color': 'dict', 'label': 'Projected per Zone'},
        {'id': 'estimated_by_zone', 'color': 'dict', 'label': 'Estimated per Zone'},
    ],
    params=[
        {'id': 'size_key', 'label': 'Size Key', 'type': 'string', 'default': 'radius'},
        {'id': 'size_kind', 'label': 'Size Is', 'type': 'enum', 'default': 0,
         'options': ['Radius (px)', 'Diameter (px)', 'Area (px²)']},
        {'id': 'position_key', 'label': 'Position Key', 'type': 'string', 'default': 'rho'},
        {'id': 'bandwidth', 'label': 'Bandwidth (position units)', 'type': 'float', 'default': 0.05, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'packing', 'label': 'Packing (0 = auto)', 'type': 'float', 'default': 0.0, 'min': 0, 'max': 1, 'step': 0.01},
        {'id': 'min_items', 'label': 'Min Objects per Zone', 'type': 'int', 'default': 5, 'min': 1, 'max': 500},
        {'id': 'n_boot', 'label': 'Bootstrap Runs', 'type': 'int', 'default': 300, 'min': 0, 'max': 5000},
        {'id': 'seed', 'label': 'Random Seed', 'type': 'int', 'default': 0},
    ],
)
class SampleProjectionNode(NodeProcessor):
    def process(self, inputs, params):
        out = {'main': None, 'stats': {}, 'total': None, 'counts': [], 'size_map': None, 'packing': None,
               'detected_by_zone': {}, 'projected_by_zone': {}, 'estimated_by_zone': {}}
        zones = inputs.get('zones')
        if zones is None and inputs.get('mask') is not None:
            zones = (np.asarray(inputs['mask']) > 0).astype(np.int32)   # the mask is the one zone
            if zones.ndim == 3:
                zones = zones.max(2)
        if zones is None:
            return out
        zones = np.asarray(zones)
        if zones.ndim == 3:
            zones = cv2.cvtColor(zones.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        zones = zones.astype(np.int32).copy()
        h, w = zones.shape
        keep = inputs.get('mask')
        if keep is not None:
            keep = keep if keep.ndim == 2 else cv2.cvtColor(keep, cv2.COLOR_BGR2GRAY)
            if keep.shape != (h, w):
                keep = cv2.resize(keep, (w, h), interpolation=cv2.INTER_NEAREST)
            zones[keep == 0] = 0
        for it in inputs.get('exclude') or []:
            xy = _item_xy(it, w, h) if isinstance(it, dict) else None
            r = _num(it.get('radius')) if isinstance(it, dict) else None
            if xy is not None and r:
                cv2.circle(zones, (int(round(xy[0])), int(round(xy[1]))), int(round(r)), 0, -1)
        measured = inputs.get('measured')
        if measured is not None:
            measured = measured if measured.ndim == 2 else cv2.cvtColor(measured, cv2.COLOR_BGR2GRAY)
            if measured.shape != (h, w):
                measured = cv2.resize(measured, (w, h), interpolation=cv2.INTER_NEAREST)
            measured = measured > 0
        pmap = inputs.get('position')
        pmap = pmap.astype(np.float32) if isinstance(pmap, np.ndarray) and pmap.shape == (h, w) else None

        kind = int(params.get('size_kind', 0))
        ks, kp = str(params.get('size_key', 'radius')), str(params.get('position_key', 'rho'))
        rows = []
        for it in inputs.get('items') or []:
            if not isinstance(it, dict):
                continue
            s, xy = _num(it.get(ks)), _item_xy(it, w, h)
            if s is None or s <= 0 or xy is None:
                continue
            x, y = int(np.clip(xy[0], 0, w - 1)), int(np.clip(xy[1], 0, h - 1))
            area = np.pi * s * s if kind == 0 else (np.pi * s * s / 4 if kind == 1 else s)
            p = _num(it.get(kp))
            if p is None and pmap is not None:
                p = float(pmap[y, x])
            rows.append((xy[0], xy[1], area, p if p is not None else 0.0, zones[y, x]))
        if not rows:
            return out
        X, Y, A, P, Z = (np.array(c) for c in zip(*rows))
        radius = np.sqrt(A / np.pi)

        phi = float(params.get('packing', 0.0))
        n_touch = 0
        if phi <= 0:
            phi, n_touch = _auto_packing(np.c_[X, Y], radius)
            phi = phi if phi is not None else 0.8
        bw = float(params.get('bandwidth', 0.05)) if pmap is not None else 0.0
        n_boot = int(params.get('n_boot', 300))
        rng = np.random.default_rng(int(params.get('seed', 0)))
        ppu = _num(inputs.get('px_per_unit'))
        min_items = int(params.get('min_items', 5))

        stats = {'packing': phi, 'packing_from_n': n_touch}
        size_map = np.zeros((h, w), np.float32)
        counts, boot_tot = [], np.zeros(max(n_boot, 0))
        total, n_obs_total, proj_total, meas_px = 0.0, 0, 0.0, 0.0
        for z in [int(v) for v in np.unique(zones) if v > 0]:
            in_zone = zones == z
            sel = Z == z
            # With a measured area, its objects are counted as such; only the rest is projected.
            base = 0
            if measured is not None:
                stats[f'zone_{z}_area_measured_px'] = float((in_zone & measured).sum())
                stats[f'zone_{z}_measured_share'] = float((in_zone & measured).sum() / max(in_zone.sum(), 1))
                meas_px += float((in_zone & measured).sum())
                in_zone = in_zone & ~measured
                base = int(sel.sum())
            n_obs = int(sel.sum())
            area_z = float((zones == z).sum())
            key = f'zone_{z}'
            stats[f'{key}_area_px'] = area_z
            stats[f'{key}_n_detected'] = n_obs
            if n_obs < min_items:
                stats[f'{key}_n_estimated'] = None
                counts.append(None)
                continue
            if not in_zone.any():
                hist, centers = np.zeros(1), np.array([0.0])
            elif bw > 0:
                pz = pmap[in_zone]
                lo, hi = float(pz.min()), float(pz.max())
                hist, edges = np.histogram(pz, bins=N_POS_BINS, range=(lo, hi + 1e-6))
                centers = (edges[:-1] + edges[1:]) / 2
            else:
                hist, centers = np.array([float(in_zone.sum())]), np.array([0.0])
            p_obj, a_obj = P[sel], A[sel]
            projected = _project(p_obj, a_obj, hist, centers, bw, phi)
            est = base + projected
            boots = base + np.array([_project(p_obj[s], a_obj[s], hist, centers, bw, phi)
                                     for s in (rng.integers(0, n_obs, n_obs) for _ in range(n_boot))])
            if n_boot:
                boot_tot += boots
            mean_area = float(a_obj.mean())
            stats[f'{key}_n_estimated'] = est
            if measured is not None:
                stats[f'{key}_n_projected'] = projected
                proj_total += projected
            if n_boot:
                stats[f'{key}_n_low'] = float(np.percentile(boots, 2.5))
                stats[f'{key}_n_high'] = float(np.percentile(boots, 97.5))
            stats[f'{key}_completeness'] = n_obs / est if est else None
            stats[f'{key}_mean_area_px'] = mean_area
            stats[f'{key}_mean_diameter_px'] = float(2 * np.sqrt(mean_area / np.pi))
            if ppu:
                stats[f'{key}_mean_diameter_unit'] = float(2 * np.sqrt(mean_area / np.pi) / ppu)
                stats[f'{key}_area_unit2'] = area_z / ppu ** 2
            counts.append(est)
            total += est
            n_obs_total += n_obs
            if bw > 0 and in_zone.any():
                prof = _mean_area_profile(p_obj, a_obj, centers, bw)
                idx = np.clip(np.searchsorted(edges, pmap[in_zone], side='right') - 1, 0, N_POS_BINS - 1)
                size_map[in_zone] = prof[idx]
            else:
                size_map[in_zone] = mean_area
        stats['total_n_detected'] = n_obs_total
        stats['total_n_estimated'] = total
        if n_boot and total:
            stats['total_n_low'] = float(np.percentile(boot_tot, 2.5))
            stats['total_n_high'] = float(np.percentile(boot_tot, 97.5))
        stats['total_completeness'] = n_obs_total / total if total else None
        if measured is not None:
            stats['total_n_projected'] = proj_total
            area_all = float((zones > 0).sum())
            stats['total_measured_share'] = meas_px / area_all if area_all else None

        diam = 2 * np.sqrt(size_map / np.pi)
        top = float(diam.max()) or 1.0
        vis = cv2.applyColorMap((np.clip(diam / top, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        vis[size_map == 0] = 0
        for x, y, r in zip(X, Y, radius):
            cv2.circle(vis, (int(round(x)), int(round(y))), int(round(r)), (255, 255, 255), 1)
        cv2.putText(vis, f'expected diameter, max {top:.1f} px', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 1, cv2.LINE_AA)
        # Per-zone dicts, keyed by zone name (Zone Names input) or 'zone k', in zone order
        names = [str(n) for n in (inputs.get('names') or [])]
        det, prj, est = {}, {}, {}
        for z in sorted({int(k.split('_')[1]) for k in stats if k.startswith('zone_') and k.endswith('_area_px')}):
            name = names[z - 1] if z - 1 < len(names) and names[z - 1] else f'zone {z}'
            if stats.get(f'zone_{z}_n_estimated') is None:
                continue
            det[name] = stats[f'zone_{z}_n_detected']
            est[name] = stats[f'zone_{z}_n_estimated']
            prj[name] = stats.get(f'zone_{z}_n_projected', est[name] - det[name])
        out.update(main=vis, stats=stats, total=total, counts=counts, size_map=size_map, packing=phi,
                   detected_by_zone=det, projected_by_zone=prj, estimated_by_zone=est)
        return out
