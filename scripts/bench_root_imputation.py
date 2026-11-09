#!/usr/bin/env python3
"""Synthetic-degradation benchmark for "measured + projected" root cell counts.

For each clean image:
  1. run the Root Predictive Ellipse Zoning template -> ground truth =
     cells per zone on the undamaged section;
  2. degrade the image (wash / tear / loss) at several severities and seeds;
  3. rerun the template and compare observed and imputed counts to the truth.

Two zoning modes separate the error sources:
  * fixed_zones  — damaged cells counted in the CLEAN zone masks (imputation only)
  * end_to_end   — damaged cells counted in the zones the pipeline re-derives
Two estimators:
  * raw          — A_obs = sum of segmented cell areas (formula of the draft)
  * territory    — cells grown into walls by --territory px before measuring

Usage:
  python3 scripts/bench_root_imputation.py IMG [IMG ...] --out bench_out/root_imputation
"""
import argparse
import csv
import json
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine'))
sys.path.insert(0, os.path.join(REPO, 'engine', 'tests'))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import root_bench_lib as B  # noqa: E402

TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_predictive_ellipse_zoning.vn')
ZONES = ('pith', 'vascular', 'lpsc', 'endodermis', 'inner_cortex', 'outer_cortex', 'rhizodermis')
NODE_REPORT_KEYS = ('pith', 'vascular', 'endo')
DEFAULT_SEVERITIES = (0.1, 0.2, 0.35, 0.5)
DEFAULT_SEEDS = (0, 1)

_VN = None
_ZONING = 'template'


def _init_worker(template=TEMPLATE, zoning='template'):
    global _VN, _ZONING
    _ZONING = zoning
    import vn_headless as H
    H.load_plugins()
    with open(template) as f:
        _VN = json.load(f)


class PipelineFailure(RuntimeError):
    """The template produced no usable section / cells / zones for an image."""


def _required(value, what):
    if value is None:
        raise PipelineFailure(f'pipeline produced no {what}')
    return np.asarray(value)


def _run_pipeline(path):
    import vn_headless as H
    r = H.run(_VN, {'src': {'path': path}})
    ep = r['ellipse_prop']
    if any(ep.get(f'{z}_mask') is None for z in ZONES):
        raise PipelineFailure('pipeline produced no zone masks (metaxylem anchor lost?)')
    section = _required(r['section'].get('mask'), 'section mask') > 0
    mx = _required(r['metaxylem'].get('mask'), 'metaxylem mask') > 0
    zones = {z: np.asarray(ep[f'{z}_mask']) > 0 for z in ZONES}
    if _ZONING == 'measured':
        import radial_zoning_lib as R
        gray = cv2.cvtColor(np.asarray(r['src']['main']), cv2.COLOR_BGR2GRAY)
        _, masks, _, _ = R.measure_boundaries(gray, section, mx, n_boot=0)
        zones = {z: masks.get(f'{z}_mask', np.zeros_like(section)) for z in ZONES}
    return {
        'section': section,
        'labels': _required(r['cells'].get('labels'), 'cell labels'),
        'mx': mx,
        'zones': zones,
        'node_report': r['pub_fig'].get('predictive_report') or {},
    }


def _counts(res, zones, territory, clean_lacunae=None):
    lac = clean_lacunae if clean_lacunae is not None else B.extract_cortical_lacunae(res['labels'], zones)
    exclude = res['mx'] | lac
    return {
        'raw': B.impute_counts(res['labels'], zones, exclude=exclude),
        'territory': B.impute_counts(res['labels'], zones, territory_px=territory, exclude=exclude),
    }


def _rows(meta, truth, res, clean_zones, territory, clean_lacunae=None):
    rows = []
    # fixed_zones: uses clean_lacunae (oracle baseline: known true biological aerenchyma)
    # end_to_end: clean_lacunae=None (realistic/blind: lacunae detected naively on the damaged image)
    for mode, zones, lac in (('fixed_zones', clean_zones, clean_lacunae), ('end_to_end', res['zones'], None)):
        for est, counts in _counts(res, zones, territory, clean_lacunae=lac).items():
            for z, c in counts.items():
                rows.append({**meta, 'mode': mode, 'estimator': est, 'zone': z,
                             'truth': truth[z], 'n_obs': c.n_obs, 'n_proj': c.n_proj,
                             'n_total': c.n_total, 'a_theo': c.a_theo, 'a_obs': c.a_obs,
                             'a_med': c.a_mean})
    rep = res['node_report']
    for key in NODE_REPORT_KEYS:
        prefix = 'endo_cells' if key == 'endo' else f'{key}_cells'
        obs_key = f'{prefix}_observed'
        if obs_key in rep:
            rows.append({**meta, 'mode': 'node', 'estimator': 'draw_root_publication',
                         'zone': key, 'truth': meta.get(f'clean_node_{key}', ''),
                         'n_obs': rep[obs_key], 'n_proj': rep.get(f'{prefix}_missing_pred', ''),
                         'n_total': rep.get(f'{prefix}_total_pred', ''),
                         'a_theo': '', 'a_obs': '', 'a_med': ''})
    return rows


def _clean_job(image_path):
    res = _run_pipeline(image_path)
    assign = B.assign_cells(res['labels'], res['zones'])
    truth = {z: sum(1 for v in assign.values() if v == z) for z in ZONES}
    rep = res['node_report']
    node_truth = {k: rep.get(('endo_cells' if k == 'endo' else f'{k}_cells') + '_observed', '')
                  for k in NODE_REPORT_KEYS}
    clean_lacunae = B.extract_cortical_lacunae(res['labels'], res['zones'])
    return image_path, res, truth, node_truth, clean_lacunae


def _damage_job(args):
    image_path, clean, truth, node_truth, kind, severity, seed, territory = args
    img = cv2.imread(image_path)
    damaged, _, achieved = B.damage_image(img, clean['section'], kind, severity, seed=seed)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cv2.imwrite(tmp_path, damaged)
        res = _run_pipeline(tmp_path)
        error = ''
    except Exception as exc:  # any crash downstream = pipeline failure for this case
        res, error = None, f'{type(exc).__name__}: {exc}'
    finally:
        os.unlink(tmp_path)
    meta = {'image': os.path.basename(image_path), 'kind': kind, 'severity': severity,
            'achieved': round(achieved, 4), 'seed': seed,
            **{f'clean_node_{k}': v for k, v in node_truth.items()}}
    if res is None:
        return [{**meta, 'mode': 'failed', 'estimator': '', 'zone': '', 'truth': '', 'n_obs': '',
                 'n_proj': '', 'n_total': '', 'a_theo': '', 'a_obs': '', 'a_med': '', 'error': error}]
    return [{**r, 'error': ''} for r in _rows(meta, truth, res, clean['zones'], territory, clean.get('lacunae'))]


def _summarise(rows):
    """Relative error of observed and total counts, summed over zones."""
    groups = {}
    for r in rows:
        if r['mode'] in ('node', 'failed'):
            continue
        key = (r['image'], r['kind'], r['severity'], r['mode'], r['estimator'])
        g = groups.setdefault(key, {'truth': 0, 'obs': 0, 'tot': 0, 'abs_zone_err': []})
        g['truth'] += r['truth']
        g['obs'] += r['n_obs']
        g['tot'] += r['n_total']
        if r['truth']:
            g['abs_zone_err'].append(abs(r['n_total'] - r['truth']) / r['truth'])
    out = []
    for (image, kind, sev, mode, est), g in sorted(groups.items()):
        out.append({'image': image, 'kind': kind, 'severity': sev, 'mode': mode, 'estimator': est,
                    'obs_err': (g['obs'] - g['truth']) / g['truth'] if g['truth'] else float('nan'),
                    'total_err': (g['tot'] - g['truth']) / g['truth'] if g['truth'] else float('nan'),
                    'zone_mape': float(np.mean(g['abs_zone_err'])) if g['abs_zone_err'] else float('nan')})
    return out


def _aggregate(summary):
    """Mean over images and seeds -> one line per (kind, severity, mode, estimator)."""
    acc = {}
    for s in summary:
        key = (s['kind'], s['severity'], s['mode'], s['estimator'])
        acc.setdefault(key, []).append(s)
    lines = []
    for key in sorted(acc):
        xs = acc[key]
        lines.append((*key, *(float(np.mean([x[m] for x in xs])) for m in ('obs_err', 'total_err', 'zone_mape'))))
    return lines


def _failures(rows):
    out = {}
    for r in rows:
        if r['mode'] == 'failed':
            key = (r['kind'], r['severity'])
            out[key] = out.get(key, 0) + 1
    return out


def _write_markdown(path, lines, truths, failures):
    with open(path, 'w') as f:
        f.write('# Root imputation benchmark (synthetic degradation)\n\n')
        f.write('Ground truth = per-zone cell counts on the undamaged image.\n\n')
        for img, t in truths.items():
            f.write(f'- `{img}`: ' + ', '.join(f'{z}={n}' for z, n in t.items()) + '\n')
        f.write('\n`obs_err` / `total_err` = (count − truth)/truth summed over zones; '
                '`zone_mape` = mean |total − truth|/truth per zone. Mean over images and seeds.\n\n')
        f.write('| damage | severity | mode | estimator | obs_err | total_err | zone_mape |\n')
        f.write('|---|---|---|---|---|---|---|\n')
        for kind, sev, mode, est, oe, te, zm in lines:
            f.write(f'| {kind} | {sev:.2f} | {mode} | {est} | {oe:+.1%} | {te:+.1%} | {zm:.1%} |\n')
        f.write('\n## Pipeline failures (runs with no usable output)\n\n')
        if not failures:
            f.write('None.\n')
        for (kind, sev), n in sorted(failures.items()):
            f.write(f'- {kind} @ {sev:.2f}: {n} run(s)\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('images', nargs='+')
    ap.add_argument('--out', default=os.path.join(REPO, 'bench_out', 'root_imputation'))
    ap.add_argument('--kinds', nargs='+', default=list(B.DAMAGE_KINDS), choices=B.DAMAGE_KINDS)
    ap.add_argument('--severities', nargs='+', type=float, default=list(DEFAULT_SEVERITIES))
    ap.add_argument('--seeds', nargs='+', type=int, default=list(DEFAULT_SEEDS))
    ap.add_argument('--territory', type=int, default=2, help='wall half-width in px for the territory estimator')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--zoning', choices=('template', 'measured'), default='template',
                    help='zone masks: the template\'s elliptic shells, or measured radial boundaries')
    ap.add_argument('--template', default=TEMPLATE,
                    help='.vn to benchmark; must expose section, cells, metaxylem, ellipse_prop, pub_fig nodes')
    args = ap.parse_args()

    for p in args.images:
        if cv2.imread(p) is None:
            ap.error(f'cannot read image {p}')
    os.makedirs(args.out, exist_ok=True)

    with ProcessPoolExecutor(args.workers, initializer=_init_worker, initargs=(args.template, args.zoning)) as pool:
        cleans = list(pool.map(_clean_job, args.images))
        rows, truths, jobs = [], {}, []
        for path, res, truth, node_truth, clean_lacunae in cleans:
            truths[os.path.basename(path)] = truth
            meta = {'image': os.path.basename(path), 'kind': 'clean', 'severity': 0.0, 'achieved': 0.0,
                    'seed': 0, **{f'clean_node_{k}': v for k, v in node_truth.items()}}
            rows += [{**r, 'error': ''} for r in _rows(meta, truth, res, res['zones'], args.territory, clean_lacunae)]
            light = {'section': res['section'], 'zones': res['zones'], 'lacunae': clean_lacunae}
            jobs += [(path, light, truth, node_truth, k, s, sd, args.territory)
                     for k, s, sd in product(args.kinds, args.severities, args.seeds)]
        for i, job_rows in enumerate(pool.map(_damage_job, jobs), 1):
            rows += job_rows
            print(f'[{i}/{len(jobs)}] done', flush=True)

    with open(os.path.join(args.out, 'runs.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), restval='')
        w.writeheader()
        w.writerows(rows)
    lines = _aggregate(_summarise(rows))
    _write_markdown(os.path.join(args.out, 'summary.md'), lines, truths, _failures(rows))
    print(f'wrote {args.out}/runs.csv and summary.md')


if __name__ == '__main__':
    main()
