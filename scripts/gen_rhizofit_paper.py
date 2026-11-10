#!/usr/bin/env python3
"""Numbers and figures of the RhizoFit methods paper (v10), from the current RhizoFit engine.

Supersedes gen_root_paper_figures.py (v9): every count here comes from scripts/root_web_runner.py,
the engine of the web app (scale normalisation, vessel filter, faint-cell recovery, polar size
check, territory-density census, cortical cell files).

One maize section, RM12e: the original bright-field micrograph (scale bar 500 um = 395 px,
1.266 um/px), its expert drawing (ground truth) and RootScan's output on it. Resolution
independence is tested by analysing RM12e resampled at 0.5x and 2x against the same truth.

Usage: python3 scripts/gen_rhizofit_paper.py --rm12e PHOTO --rm12e-truth DRAWING --rootscan OVERLAY
"""
import argparse
import json
import os
import re
import sys

import cv2
import matplotlib

matplotlib.use('Agg')
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
import count_drawing_cells as C  # noqa: E402
import gen_root_paper_figures as G  # noqa: E402
import radial_zoning_lib as R  # noqa: E402
import root_web_runner as W  # noqa: E402

ZONES, LABELS_FR, ZONE_COLORS, ZONE_MASKS = G.ZONES, G.LABELS_FR, G.ZONE_COLORS, G.ZONE_MASKS
COL_A, COL_B, COL_GT, COL_RS = G.COL_A, G.COL_B, G.COL_GT, '#7b3294'
RM12E_UM_PER_PX = 500 / 395          # scale bar of RM12e (VNStudio Scale Bar Detect: 0.79 px/um)
RESOLUTIONS = (0.5, 2.0)             # resampling factors of the resolution-independence test
GT_THRESHOLDS = (110, 160, 210)      # wall threshold sweep for the ground-truth sensitivity
GT_MIN_AREAS = (4, 15, 40)
BENCH_DIR = os.path.join(REPO, 'bench_out', 'root_imputation_rhizofit')
SEVERITIES = G.SEVERITIES
# RootScan outputs on RM12e (colleague's run, its own scale), read from the exported tables
ROOTSCAN = {'RXSA_mm2': 0.2884106, 'TSA_mm2': 0.045241434, 'MXVA_mm2': 0.00690806, 'MX_num': 7,
              'MX_true': 3, 'AA_mm2': 0.0352133, 'percCisA': 14.4809885, 'CF_num': 11, 'CC_num': 909,
              'CC_mean_um2': 123.552895, 'CC_median_um2': 58.86932}


# --------------------------------------------------------------------------- analysis

def drawing_ground_truth(path, threshold=C.REFERENCE[0], min_area=C.REFERENCE[1]):
    """Closed-wall cells of an expert drawing (full resolution): its own section, threshold 160, min 15 px."""
    img = W._read_bgr(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    walls = (gray < C.REFERENCE[0]).astype(np.uint8)  # section outline always from the reference threshold
    closed = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    section = np.zeros_like(walls)
    cv2.drawContours(section, [max(cnts, key=cv2.contourArea)], -1, 1, -1)
    section = section.astype(bool)
    h, w = section.shape
    section[int(0.86 * h):, int(0.68 * w):] = False  # scale bar corner
    return C.drawing_labels(gray, section, threshold, min_area)


def to_working(labels, st):
    h, w = st['section'].shape
    return cv2.resize(labels.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST).astype(np.int32)


def truth_by_zone(gt_w, st):
    """Ground-truth cells per measured zone (centroid binning), metaxylem vessels excluded."""
    n = int(gt_w.max())
    area = np.bincount(gt_w.ravel(), minlength=n + 1)
    ys, xs = np.indices(gt_w.shape)
    cy = np.bincount(gt_w.ravel(), ys.ravel(), minlength=n + 1) / np.maximum(area, 1)
    cx = np.bincount(gt_w.ravel(), xs.ravel(), minlength=n + 1) / np.maximum(area, 1)
    ids = np.nonzero(area[1:])[0] + 1
    r, c = np.round(cy[ids]).astype(int), np.round(cx[ids]).astype(int)
    vessel = st['mx'][r, c] & (area[ids] > 4 * np.median(area[ids]))
    counts = {z: int(np.asarray(st['masks'][m])[r[~vessel], c[~vessel]].sum()) for z, m in zip(ZONES, ZONE_MASKS)}
    return counts, area[ids[vessel]]


def analyse(path, um_per_px, n_boot=200):
    st = W.run_pipeline(path, pixel_size_um=um_per_px, n_boot=n_boot)
    census = W._census_territory(st)
    zone_area = {z: float(np.count_nonzero(st['masks'][m])) for z, m in zip(ZONES, ZONE_MASKS)}
    areas = W._cell_areas(st['labels'], st['masks'], st['mx'])
    tables = {t['id']: t for t in W.build_tables(st, census, zone_area, areas)}
    return {'st': st, 'census': census, 'tables': tables, 'areas': areas, 'um_per_px': um_per_px,
            'work_um_per_px': um_per_px / st['scale']}


def summary_value(case, metric):
    return next(r for r in case['tables']['summary']['rows'] if r[0].startswith(metric))[1]


def zone_rows(case):
    return {z: {'obs': case['census'][z]['observed'], 'total': case['census'][z]['total']} for z in ZONES}


# --------------------------------------------------------------------------- figures

def fig_publication(cases, titles, out):
    fig, axes = plt.subplots(1, len(cases), figsize=(6 * len(cases), 6.2), dpi=250)
    for ax, case, title in zip(np.atleast_1d(axes), cases, titles):
        ax.imshow(cv2.cvtColor(case['st']['pub']['main'], cv2.COLOR_BGR2RGB))
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.axis('off')
    handles = [mpatches.Patch(facecolor=c, edgecolor='#333', label=lab) for c, lab in zip(ZONE_COLORS, LABELS_FR)]
    handles += [mpatches.Patch(facecolor='#e8f5e9', edgecolor='#1b5e20', label='Métaxylème (ellipses)'),
                mpatches.Patch(facecolor='white', edgecolor='#333', hatch='////', label='Lacunes (aérenchyme)')]
    fig.legend(handles=handles, loc='lower center', ncol=4, fontsize=8.5, frameon=False)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def fig_images(paths, titles, out):
    imgs = [G.read_on_white(p) for p in paths]
    h = min(im.shape[0] for im in imgs)
    imgs = [cv2.resize(im, (round(im.shape[1] * h / im.shape[0]), h), interpolation=cv2.INTER_AREA) for im in imgs]
    fig, axes = plt.subplots(1, len(imgs), figsize=(6 * len(imgs), 6.2), dpi=250,
                             gridspec_kw={'width_ratios': [im.shape[1] for im in imgs]})
    for ax, img, title in zip(axes, imgs, titles):
        ax.imshow(img)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.axis('off')
    fig.tight_layout()
    fig.savefig(out, facecolor='white', bbox_inches='tight', pad_inches=0.05)
    plt.close(fig)


def _crop_to_section(img, section, pad=0.04):
    ys, xs = np.nonzero(section)
    p = int(pad * max(section.shape))
    return img[max(ys.min() - p, 0):ys.max() + p, max(xs.min() - p, 0):xs.max() + p]


BOUNDARY_STYLE = G.BOUNDARY_STYLE


def fig_radial(st, gt_prof, out):
    """Polar unwrap of the section with measured boundaries, and the radial profiles they come from."""
    rho = np.arange(0, R.RHO_MAX, R.RHO_STEP)
    b = st['bounds']
    fig = plt.figure(figsize=(12, 10.5), dpi=250)
    gs = fig.add_gridspec(3, 1, height_ratios=(1.0, 1, 1), hspace=0.34)
    ax = fig.add_subplot(gs[0])
    pol = st['prof']['polar'][:int(b['edge'] / R.RHO_STEP) + 5]
    ax.imshow(pol, cmap='gray', aspect='auto', extent=(0, 360, pol.shape[0] * R.RHO_STEP, 0))
    for key, _, c in BOUNDARY_STYLE:
        ax.axhline(b[key], color=c, lw=1.4)
        if f'{key}_ci' in b:
            ax.axhspan(*b[f'{key}_ci'], color=c, alpha=0.25, lw=0)
    ax.axhline(1.0, color='#2e7d32', lw=1.0, ls='--')
    ax.axhline(b['edge'], color='#1565c0', lw=1.2, ls='--')
    ax.set_title('RM12e : déroulement polaire (ρ, φ)', fontsize=10.5, fontweight='bold')
    ax.set_xlabel('Azimut φ (°)', fontsize=9)
    ax.set_ylabel('ρ (anneau = 1)', fontsize=9)
    ax_d = fig.add_subplot(gs[1])
    ax_l = fig.add_subplot(gs[2], sharex=ax_d)
    for key, prof, c, lab in (('GT', gt_prof, COL_GT, 'Vérité terrain (cellules du tracé)'),
                              ('img', st['prof'], COL_A, 'Micrographie RM12e (image brute)')):
        with np.errstate(all='ignore'):
            if prof['dark'] is not None:
                d = np.nanmedian(prof['dark'], 1)
                ax_d.plot(rho, (d - np.nanmin(d)) / (np.nanmax(d) - np.nanmin(d)), color=c, lw=1.4, label=lab)
            lt = prof['Lt'] / prof['px_per_rho']
            ax_l.plot(rho, np.nanmedian(lt, 1), color=c, lw=2.0 if key == 'GT' else 1.4, label=lab)
            ax_l.fill_between(rho, np.nanpercentile(lt, 25, 1), np.nanpercentile(lt, 75, 1), color=c, alpha=0.12)
    for a in (ax_d, ax_l):
        for key, _, c in BOUNDARY_STYLE:
            a.axvline(b[key], color=c, lw=1.0)
        a.axvline(1.0, color='#2e7d32', lw=0.9, ls=':')
        a.grid(alpha=0.3)
        a.spines[['top', 'right']].set_visible(False)
    ax_d.set_ylabel('Densité de paroi (normalisée)', fontsize=9.5)
    ax_d.set_title('Profil radial de densité de paroi (médiane sur 16 secteurs angulaires)', fontsize=10.5,
                   fontweight='bold')
    ax_d.legend(fontsize=8, loc='upper right', frameon=True)
    ax_l.set_yscale('log')
    ax_l.set_ylabel('Taille circonférentielle\ndes cellules L_θ (unités ρ)', fontsize=9.5)
    ax_l.set_xlabel('ρ (traits verticaux : frontières mesurées)', fontsize=9.5)
    ax_l.set_title('Intercept linéaire moyen (stéréologie), bande = écart interquartile entre secteurs',
                   fontsize=10.5, fontweight='bold')
    ax_l.set_xlim(0.15, 3.0)
    ax_l.legend(fontsize=8, loc='lower right', frameon=True)
    handles = [plt.Line2D([], [], color=c, lw=2, label=lab) for _, lab, c in BOUNDARY_STYLE]
    handles += [plt.Line2D([], [], color='#2e7d32', ls='--', label='Anneau de métaxylème (ρ = 1)'),
                plt.Line2D([], [], color='#1565c0', ls='--', label='Bord de la section')]
    fig.legend(handles=handles, loc='lower center', ncol=3, fontsize=8.5, frameon=False)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.96, bottom=0.11)
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def fig_second_pass(case, out):
    """Before / after the second pass: first-pass empty cortex hatched, then recovered cells."""
    st = case['st']
    src = st['pipe']['src']['main']
    cortex = st['masks']['inner_cortex_mask'] | st['masks']['outer_cortex_mask']
    first = st['labels'].copy()
    first[st['recovered']] = 0
    before = src.copy()
    gaps = cortex & (first == 0)
    hatch = ((np.add.outer(np.arange(gaps.shape[0]), np.arange(gaps.shape[1])) % 9) < 2) & gaps
    before[gaps] = (0.55 * before[gaps] + np.array([60, 60, 220]) * 0.45).astype(np.uint8)
    before[hatch] = (40, 40, 160)
    after = W._img_recovered(st)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.2), dpi=250)
    for ax, img, title in zip(axes, (before, after),
                              ('Avant : vides du cortex après la 1re passe', 'Après : cellules pâles retrouvées')):
        ax.imshow(cv2.cvtColor(_crop_to_section(img, st['section']), cv2.COLOR_BGR2RGB))
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.axis('off')
    fig.tight_layout()
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def fig_counts(gt, cases, names, colors, out, truth_label):
    x = np.arange(len(ZONES))
    w = 0.8 / len(cases)
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=250)
    for k, (case, name, col) in enumerate(zip(cases, names, colors)):
        off = (k - (len(cases) - 1) / 2) * w
        obs = np.array([case['census'][z]['observed'] for z in ZONES])
        tot = np.array([case['census'][z]['total'] for z in ZONES])
        ax.bar(x + off, obs, w, color=col, edgecolor='#222', linewidth=0.5, label=f'{name} : observées')
        ax.bar(x + off, np.maximum(tot - obs, 0), w, bottom=obs, facecolor='white', edgecolor=col, hatch='////',
               linewidth=0.8, label=f'{name} : imputées')
    truth = np.array([gt[z] for z in ZONES])
    ax.scatter(x, truth, marker='_', s=900, color=COL_GT, linewidths=2.2, zorder=5, label=truth_label)
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS_FR, fontsize=9)
    ax.set_ylabel('Cellules', fontsize=10)
    ax.spines[['top', 'right']].set_visible(False)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax.legend(fontsize=8, ncol=3, loc='upper left', frameon=False)
    ax.set_ylim(0, max(truth.max(), max(c['census'][z]['total'] for c in cases for z in ZONES)) * 1.3)
    fig.tight_layout()
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def fig_rootscan(rootscan_img, case_r, rm12e, truth, out):
    """RootScan's own overlay on B | RhizoFit on RM12e | measured comparison on three scale-free metrics."""
    fig = plt.figure(figsize=(14, 5.6), dpi=250)
    gs = fig.add_gridspec(1, 3, width_ratios=(1, 1, 1.15), wspace=0.08)
    ax = fig.add_subplot(gs[0])
    ax.imshow(G.read_on_white(rootscan_img))
    ax.set_title('RootScan (sortie de l\'outil, RM12e)', fontsize=11, fontweight='bold')
    ax.axis('off')
    ax = fig.add_subplot(gs[1])
    st = case_r['st']
    ax.imshow(cv2.cvtColor(_crop_to_section(st['pub']['main'], st['section']), cv2.COLOR_BGR2RGB))
    ax.set_title('RhizoFit (RM12e)', fontsize=11, fontweight='bold')
    ax.axis('off')
    ax = fig.add_subplot(gs[2])
    metrics = ('Vaisseaux de\nmétaxylème', 'Files\ncorticales (CF)', 'Aérenchyme\n(% du cortex)')
    vals = {'Vérité terrain': (truth['vessels'], truth['cf'], 0.0),
            'RhizoFit': (rm12e['vessels'], rm12e['cf'], rm12e['aa']),
            'RootScan': (ROOTSCAN['MX_num'], ROOTSCAN['CF_num'], ROOTSCAN['percCisA'])}
    x = np.arange(len(metrics))
    w = 0.26
    for k, (name, col) in enumerate((('Vérité terrain', COL_GT), ('RhizoFit', COL_A), ('RootScan', COL_RS))):
        bars = ax.bar(x + (k - 1) * w, vals[name], w, color=col, label=name)
        ax.bar_label(bars, fmt='%.3g', fontsize=7.5, padding=1)
    ax.text(0 + w, ROOTSCAN['MX_num'] + 1.2, f'dont {ROOTSCAN["MX_true"]} vrais', ha='center', fontsize=7,
            color=COL_RS)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_title('Mesures indépendantes de l\'échelle', fontsize=11, fontweight='bold')
    ax.spines[['top', 'right']].set_visible(False)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax.legend(fontsize=8, frameon=False, loc='upper left')
    ax.set_ylim(0, 19)
    fig.savefig(out, facecolor='white', bbox_inches='tight', pad_inches=0.08)
    plt.close(fig)


def bench_curves(path, estimator='census'):
    rx = re.compile(r'^\| (\w+) \| ([\d.]+) \| (\w+) \| ' + estimator +
                    r' \| ([+-][\d.]+)% \| ([+-][\d.]+)% \| ([\d.]+)% \|')
    acc = {}
    with open(path) as f:
        for line in f:
            m = rx.match(line)
            if m:
                _, sev, mode, obs, tot, mape = m.groups()
                d = acc.setdefault((float(sev), mode), {'obs': [], 'tot': [], 'mape': []})
                for k, v in (('obs', obs), ('tot', tot), ('mape', mape)):
                    d[k].append(float(v))
    return {mode: {k: [float(np.mean(acc[(s, mode)][k])) if (s, mode) in acc else float('nan') for s in SEVERITIES]
                   for k in ('obs', 'tot', 'mape')} for mode in ('fixed_zones', 'end_to_end')}


def fig_dashboard(gt, case, areas, um, resolution, curves, failures, out):
    """(A) imputed share per zone, (B) cell areas, (C) total vs truth at three resolutions, (D) bench."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=250)
    x = np.arange(len(ZONES))
    ax = axes[0, 0]
    zt = zone_rows(case)
    frac = [100 * max(zt[z]['total'] - zt[z]['obs'], 0) / max(zt[z]['total'], 1) for z in ZONES]
    bars = ax.bar(x, frac, 0.6, color=ZONE_COLORS, edgecolor='#222', linewidth=0.5)
    ax.bar_label(bars, fmt='%.0f%%', fontsize=7.5, padding=1)
    ax.set_title('A. Part estimée en plus des cellules observées', fontsize=10.5, fontweight='bold')
    ax.set_ylabel('% du total estimé', fontsize=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS_FR, fontsize=8, rotation=20, ha='right')

    ax = axes[0, 1]
    bp = ax.boxplot([np.asarray(areas[z], float) * um ** 2 for z in ZONES], patch_artist=True, widths=0.5,
                    showfliers=False, medianprops=dict(color='black', linewidth=1.2))
    for patch, c in zip(bp['boxes'], ZONE_COLORS):
        patch.set_facecolor(c)
    ax.set_xticks(range(1, len(ZONES) + 1))
    ax.set_xticklabels(LABELS_FR, fontsize=8, rotation=20, ha='right')
    ax.set_ylabel('Surface de la lumière (µm²)', fontsize=9.5)
    ax.set_title('B. Surface des cellules segmentées par zone', fontsize=10.5, fontweight='bold')

    ax = axes[1, 0]
    truth = sum(gt[z] for z in ZONES)
    labels = [f'{f:g}×' for f, _, _ in resolution]
    obs = [o for _, o, _ in resolution]
    tot = [t for _, _, t in resolution]
    y = np.arange(len(resolution))
    ax.barh(y, obs, 0.5, color=COL_A, edgecolor='#222', label='Observées')
    ax.barh(y, np.subtract(tot, obs), 0.5, left=obs, facecolor='white', edgecolor='#d95f02', hatch='////',
            label='Estimées en plus')
    ax.axvline(truth, color=COL_GT, linestyle='--', linewidth=1.4, label=f'Vérité terrain = {truth}')
    for i in range(len(resolution)):
        ax.text(tot[i] + 12, y[i], f'{tot[i]} ({(tot[i] - truth) / truth * 100:+.1f} %)', va='center', fontsize=9,
                fontweight='bold')
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9, fontweight='bold')
    ax.set_ylabel('Rééchantillonnage de RM12e', fontsize=9.5)
    ax.set_xlim(0, truth * 1.35)
    ax.set_xlabel('Cellules (hors métaxylème)', fontsize=9.5)
    ax.set_title('C. Recensement total selon la résolution', fontsize=10.5, fontweight='bold')
    ax.legend(fontsize=8, loc='lower right', frameon=True)

    ax = axes[1, 1]
    sev = [100 * s for s in SEVERITIES]
    ax.plot(sev, curves['fixed_zones']['obs'], 's--', color='#7f7f7f', label='Observé seul')
    ax.plot(sev, curves['fixed_zones']['tot'], 'o-', color='#2ca02c', label='Estimé, zones de l\'image intacte')
    ax.plot(sev, curves['end_to_end']['tot'], '^-', color='#1f77b4', label='Estimé, pipeline aveugle')
    ax.axhline(0, color='#333', linestyle=':', linewidth=0.8)
    ax.set_xticks(sev)
    ax.set_xticklabels([f'{s:.0f} %' for s in sev])
    ax.set_xlabel('Sévérité de la dégradation synthétique', fontsize=9.5)
    ax.set_ylabel('Erreur sur le total (%)', fontsize=9.5)
    ax.set_title('D. Banc de dégradation (runs réussis)', fontsize=10.5, fontweight='bold')
    ax.text(0.98, 0.97, f'Ancre perdue : {failures}', transform=ax.transAxes, ha='right', va='top', fontsize=8,
            color='#b2182b', bbox=dict(boxstyle='round,pad=0.3', facecolor='#fee0d2', edgecolor='#b2182b'))
    ax.legend(fontsize=8, loc='lower left', frameon=True)
    for a in axes.ravel():
        a.spines[['top', 'right']].set_visible(False)
        a.yaxis.grid(True, linestyle='--', alpha=0.4)
    fig.tight_layout()
    fig.savefig(out, facecolor='white')
    plt.close(fig)


# --------------------------------------------------------------------------- main

def gt_sensitivity(truth_path, st):
    """Ground-truth zone counts over the wall-threshold / min-area sweep (relative range per zone)."""
    rows = []
    for thr in GT_THRESHOLDS:
        for amin in GT_MIN_AREAS:
            counts, _ = truth_by_zone(to_working(drawing_ground_truth(truth_path, thr, amin), st), st)
            rows.append({'threshold': thr, 'min_area': amin, **counts})
    ref = next(r for r in rows if (r['threshold'], r['min_area']) == C.REFERENCE)
    spread = {z: 100 * max(abs(r[z] - ref[z]) for r in rows) / max(ref[z], 1) for z in ZONES}
    return rows, spread


def lt_agreement(case, gt_w):
    """Agreement of L_theta measured on the raw image with L_theta of the ground-truth label map."""
    st = case['st']
    gt_prof = R.polar_profiles(None, st['section'], st['ell'], labels=gt_w)
    rho = np.arange(0, R.RHO_MAX, R.RHO_STEP)
    with np.errstate(all='ignore'):
        a = np.nanmedian(st['prof']['Lt'], 1)
        g = np.nanmedian(gt_prof['Lt'], 1)
    sel = (rho > 0.2) & (rho < st['bounds']['edge'] - 0.05) & np.isfinite(a) & np.isfinite(g)
    e = np.log(a[sel] / g[sel])
    return gt_prof, {'corr': float(np.corrcoef(np.log(a[sel]), np.log(g[sel]))[0, 1]),
                     'median_ratio': float(np.exp(np.median(e))), 'mean_abs_log': float(np.mean(np.abs(e)))}


def resolution_test(photo, truth_full, um):
    """RM12e resampled by RESOLUTIONS: estimated totals and per-zone errors against the same truth."""
    import tempfile
    rows = []
    img = cv2.imread(photo)
    for f in RESOLUTIONS:
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        cv2.imwrite(path, cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC))
        try:
            st = W.run_pipeline(path, pixel_size_um=um / f, n_boot=0)
        finally:
            os.remove(path)
        gt_f = cv2.resize(truth_full.astype(np.float32), None, fx=f, fy=f,
                          interpolation=cv2.INTER_NEAREST).astype(np.int32)
        gt_z, _ = truth_by_zone(to_working(gt_f, st), st)
        census = W._census_territory(st)
        rows.append({'factor': f, 'observed': sum(c['observed'] for c in census.values()),
                     'total': sum(c['total'] for c in census.values()), 'truth': sum(gt_z.values()),
                     'zone_mape': float(np.mean([abs(census[z]['total'] - gt_z[z]) / gt_z[z] * 100 for z in ZONES])),
                     'boundaries': {k: st['bounds'][k] for k in ('pith', 'endo_outer', 'cortex_transition', 'edge')},
                     'vessels': len(W._metaxylem_vessels(st['mx'])), 'cell_files': st['cell_files']})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rm12e', required=True)
    ap.add_argument('--rm12e-truth', required=True)
    ap.add_argument('--rootscan', required=True, help='RootScan overlay image of RM12e (its own output)')
    ap.add_argument('--bench', default=BENCH_DIR)
    ap.add_argument('--out', default=os.path.join(REPO, 'bench_out', 'paper_v10'))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for p in (args.rm12e, args.rm12e_truth, args.rootscan):
        if cv2.imread(p) is None:
            ap.error(f'cannot read {p}')

    case = analyse(args.rm12e, RM12E_UM_PER_PX)
    st = case['st']
    gt_full = drawing_ground_truth(args.rm12e_truth)
    gt_w = to_working(gt_full, st)
    gt, gt_vessels = truth_by_zone(gt_w, st)
    sens_rows, sens_spread = gt_sensitivity(args.rm12e_truth, st)
    gt_prof, lt_stats = lt_agreement(case, gt_w)
    b = st['bounds']
    truth_cf = R.cortical_cell_files(gt_w, st['section'], st['ell'], b['endo_outer'],
                                     b['edge'] - b['rhizo_layer_px'] / b['px_per_rho'])
    um2 = case['work_um_per_px'] ** 2
    areas_true = G.cell_areas_by_zone(gt_w, st['masks'])
    ga_cortex = np.concatenate([np.asarray(areas_true[z], float) for z in ('inner_cortex', 'outer_cortex')]) * um2
    curves = bench_curves(os.path.join(args.bench, 'summary.md'))
    failures = G.bench_failures(os.path.join(args.bench, 'runs.csv'))
    section_mm2 = float(st['section'].sum()) * um2 / 1e6
    res_rows = resolution_test(args.rm12e, gt_full, RM12E_UM_PER_PX)
    res_rows.insert(1, {'factor': 1.0, 'observed': sum(c['observed'] for c in case['census'].values()),
                        'total': sum(c['total'] for c in case['census'].values()), 'truth': sum(gt.values()),
                        'zone_mape': float(np.mean([abs(case['census'][z]['total'] - gt[z]) / gt[z] * 100
                                                    for z in ZONES])),
                        'boundaries': {k: b[k] for k in ('pith', 'endo_outer', 'cortex_transition', 'edge')},
                        'vessels': len(case['tables']['metaxylem']['rows']), 'cell_files': st['cell_files']})

    numbers = {
        'um_per_px': RM12E_UM_PER_PX, 'scale': st['scale'],
        'census': case['census'], 'boundaries': b, 'cell_files': st['cell_files'],
        'n_recovered': st['n_recovered'], 'n_split': st['n_split'], 'n_filled': st['n_filled'],
        'summary': case['tables']['summary']['rows'], 'geometry': case['tables']['geometry']['rows'],
        'metaxylem': case['tables']['metaxylem']['rows'], 'tilt_deg': R.major_axis_tilt_deg(st['ell']),
        'aspect': max(st['ell'][2:4]) / min(st['ell'][2:4]),
        'truth': gt, 'truth_total': sum(gt.values()), 'truth_cf': truth_cf,
        'truth_vessel_areas_um2': (np.sort(gt_vessels) * um2).tolist(),
        'truth_cortex_cell_um2': {'n': len(ga_cortex), 'mean': float(ga_cortex.mean()),
                                  'median': float(np.median(ga_cortex))},
        'truth_sensitivity': {'rows': sens_rows, 'max_rel_change_pct': sens_spread},
        'lt_vs_truth': lt_stats, 'section_mm2': section_mm2, 'resolution_test': res_rows,
        'rootscan': {**ROOTSCAN, 'area_factor_to_true_scale': section_mm2 / ROOTSCAN['RXSA_mm2']},
        'monte_carlo_true_cells': G.monte_carlo(areas_true),
        'bench_curves': curves, 'bench_failures': failures,
    }
    with open(os.path.join(args.out, 'numbers.json'), 'w') as f:
        json.dump(numbers, f, indent=1, default=float)

    out = lambda name: os.path.join(args.out, name)  # noqa: E731
    G.fig_pipeline(out('fig0_pipeline.png'))
    fig_images((args.rm12e, args.rm12e_truth),
               ('RM12e — micrographie originale', 'RM12e — tracé d\'expert (vérité terrain)'), out('fig1_sources.png'))
    fig_publication((case,), ('RM12e — rendu RhizoFit',), out('fig2_publication.png'))
    fig_radial(st, gt_prof, out('fig3_radial_boundaries.png'))
    fig_second_pass(case, out('fig4_second_pass.png'))
    vis = cv2.applyColorMap((gt_full * 37 % 255).astype(np.uint8), cv2.COLORMAP_HSV)
    vis[gt_full == 0] = 255
    cv2.imwrite(out('fig5_ground_truth.png'), vis)
    fig_counts(gt, (case,), ('RhizoFit',), (COL_A,), out('fig6_counts.png'), 'Vérité terrain (tracé d\'expert)')
    fig_rootscan(args.rootscan, case, {'vessels': len(case['tables']['metaxylem']['rows']),
                                       'cf': st['cell_files'][0], 'aa': summary_value(case, 'Cortical lacunae')},
                 {'vessels': len(gt_vessels), 'cf': truth_cf[0]}, out('fig7_rootscan.png'))
    fig_dashboard(gt, case, case['areas'], case['work_um_per_px'],
                  [(r['factor'], r['observed'], r['total']) for r in res_rows], curves, failures,
                  out('fig8_dashboard.png'))
    print(json.dumps({k: numbers[k] for k in ('truth', 'truth_cf', 'lt_vs_truth', 'section_mm2')}, default=float))
    print({z: (v['observed'], v['total']) for z, v in case['census'].items()}, st['cell_files'])
    for r in res_rows:
        print(r)


if __name__ == '__main__':
    main()
