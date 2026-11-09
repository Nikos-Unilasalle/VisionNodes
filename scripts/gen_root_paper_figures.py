#!/usr/bin/env python3
"""Numbers and figures of the root-anatomy methods paper, from real pipeline outputs.

Inputs
  A  = expert drawing (samples/root_drawing_a_hires.png, 1358x1446)
  B  = original bright-field photo of the same section (samples/root_photo_b.jpg)
  GT = closed-wall cell count of A (scripts/count_drawing_cells.py, threshold 160 / min area 15)
  bench_out/root_imputation_measured/{summary.md, runs.csv} (degradation bench, measured zoning)

Outputs (in --out)
  numbers.json                       every number quoted in the paper
  fig0_pipeline.png                  pipeline flowchart (4 stages)
  fig0_samples_ab.png                source images A | B side by side
  fig_radial_boundaries.png          polar unwraps + radial profiles + measured boundaries
  fig_ground_truth_labels.png        ground-truth cells of A
  fig1_publication_ab.png            publication renderings A | B (measured zones)
  fig5_counts_vs_truth.png           per-zone counts A, B vs ground truth
  fig6_dashboard.png                 imputed fraction, real cell areas, totals, benchmark
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
import radial_zoning_lib as R  # noqa: E402

H = C.H
SAMPLE_A = os.path.join(REPO, 'samples', 'root_drawing_a_hires.png')
SAMPLE_B = os.path.join(REPO, 'samples', 'root_photo_b.jpg')
BENCH_DIR = os.path.join(REPO, 'bench_out', 'root_imputation_measured')

ZONES = ('pith', 'vascular', 'endo', 'inner_cortex', 'outer_cortex', 'rhizodermis')
LABELS_FR = ('Moelle', 'Cyl. vasculaire', 'Endoderme', 'Cortex interne', 'Cortex externe', 'Rhizoderme')
REPORT_KEYS = {
    'pith': ('pith_cells_observed', 'pith_cells_missing_pred', 'pith_cells_total_pred', 'pith_unit_area_px'),
    'vascular': ('vascular_cells_observed', 'vascular_cells_missing_pred', 'vascular_cells_total_pred',
                 'vascular_unit_area_px'),
    'endo': ('endo_cells_observed', 'endo_cells_missing_pred', 'endo_cells_total_pred', 'endo_cell_length_measured'),
    'inner_cortex': ('inner_cortex_observed', 'inner_cortex_missing_pred', 'inner_cortex_total_pred',
                     'inner_cortex_unit_area_px'),
    'outer_cortex': ('outer_cortex_observed', 'outer_cortex_missing_pred', 'outer_cortex_total_pred',
                     'outer_cortex_unit_area_px'),
    'rhizodermis': ('rhizodermis_observed', 'rhizodermis_missing_pred', 'rhizodermis_total_pred',
                    'rhizodermis_unit_area_px'),
}
ZONE_MASKS = ('pith_mask', 'vascular_mask', 'endodermis_mask', 'inner_cortex_mask', 'outer_cortex_mask',
              'rhizodermis_mask')
ZONE_COLORS = ('#b39ddb', '#ffd54f', '#ba68c8', '#81c784', '#ffb74d', '#64b5f6')
COL_A, COL_B, COL_GT = '#4575b4', '#d73027', '#222222'
MC_LOSS = (0.10, 0.20, 0.30, 0.40, 0.50)
MC_REPS = 500
PIXEL_SIZE_B_UM = 0.5  # template default, bright-field photo B
SEVERITIES = (0.0, 0.10, 0.20, 0.35, 0.50)


def zone_table(rep):
    out = {}
    for z in ZONES:
        k_obs, k_proj, k_tot, k_unit = REPORT_KEYS[z]
        out[z] = {'obs': int(rep[k_obs]), 'proj': int(rep[k_proj]), 'total': int(rep[k_tot]),
                  'unit': float(rep[k_unit])}
    return out


def cell_areas_by_zone(labels, masks):
    """Area of every label, binned by the zone mask under its centroid (for the box plot)."""
    labels = np.asarray(labels)
    n = int(labels.max())
    if n == 0:
        return {z: [] for z in ZONES}
    area = np.bincount(labels.ravel(), minlength=n + 1)
    ys, xs = np.indices(labels.shape)
    cy = np.bincount(labels.ravel(), ys.ravel(), minlength=n + 1) / np.maximum(area, 1)
    cx = np.bincount(labels.ravel(), xs.ravel(), minlength=n + 1) / np.maximum(area, 1)
    out = {}
    for z, mname in zip(ZONES, ZONE_MASKS):
        m = np.asarray(masks[mname]) > 0
        out[z] = [int(area[i]) for i in range(1, n + 1)
                  if area[i] > 0 and m[int(round(cy[i])), int(round(cx[i]))]]
    return out


def monte_carlo(areas_by_zone, seed=0):
    """Random loss of true cells; N_proj = A_lost / mean (or median) of the survivors, per zone."""
    rng = np.random.default_rng(seed)
    zones = {z: np.asarray(a, float) for z, a in areas_by_zone.items() if len(a) >= 10}
    n_true = sum(len(a) for a in zones.values())
    rows = []
    for loss in MC_LOSS:
        err_mean, err_med = [], []
        for _ in range(MC_REPS):
            tot_mean = tot_med = 0
            for a in zones.values():
                keep = rng.random(len(a)) >= loss
                if keep.sum() < 2:
                    keep[:2] = True
                obs, lost_area = a[keep], a[~keep].sum()
                tot_mean += len(obs) + round(lost_area / obs.mean())
                tot_med += len(obs) + round(lost_area / np.median(obs))
            err_mean.append((tot_mean - n_true) / n_true * 100)
            err_med.append((tot_med - n_true) / n_true * 100)
        em, ed = np.asarray(err_mean), np.asarray(err_med)
        rows.append({'loss': loss, 'n_obs': round(n_true * (1 - loss)),
                     'mean_bias': float(em.mean()), 'mean_abs': float(np.abs(em).mean()),
                     'mean_ci': [float(np.percentile(em, 2.5)), float(np.percentile(em, 97.5))],
                     'median_bias': float(ed.mean()), 'median_ci': [float(np.percentile(ed, 2.5)),
                                                                     float(np.percentile(ed, 97.5))]})
    return {'n_true': n_true, 'reps': MC_REPS, 'rows': rows}


def bench_curves(path):
    """Mean over damage kinds, per severity, from the benchmark summary table (territory estimator)."""
    rx = re.compile(r'^\| (\w+) \| ([\d.]+) \| (\w+) \| territory \| ([+-][\d.]+)% \| ([+-][\d.]+)% \| ([\d.]+)% \|')
    acc = {}
    with open(path) as f:
        for line in f:
            m = rx.match(line)
            if not m:
                continue
            _, sev, mode, obs, tot, mape = m.groups()
            d = acc.setdefault((float(sev), mode), {'obs': [], 'tot': [], 'mape': []})
            d['obs'].append(float(obs))
            d['tot'].append(float(tot))
            d['mape'].append(float(mape))
    curves = {}
    for mode in ('fixed_zones', 'end_to_end'):
        curves[mode] = {k: [float(np.mean(acc[(s, mode)][k])) for s in SEVERITIES] for k in ('obs', 'tot', 'mape')}
    return curves


def pub_params(vn, **extra):
    node = next(n for n in vn['nodes'] if n['id'] == 'pub_fig')
    params = {k: v for k, v in node['data']['params'].items() if k not in ('color_index', 'node_note')}
    return {**params, 'zones_from_masks': True, **extra}


def publish(vn, sample, labels, image=None, **extra):
    """Publication node on measured zones: rendering + per-zone census for one label map."""
    pipe = sample['pipe']
    node = H.registry.NODE_CLASS_REGISTRY['draw_root_publication']()
    inputs = {'image': pipe['cells']['main'] if image is None else image, 'labels': labels,
              'boundary': pipe['section']['mask'], 'landmarks': pipe['metaxylem']['mask'],
              'ellipse_report': sample['ellipse_report'],
              **{k: (v.astype(np.uint8) * 255) for k, v in sample['masks'].items()}}
    out = node.process(inputs, pub_params(vn, **extra))
    if not out.get('predictive_report'):
        raise RuntimeError('publication node produced no report')
    return out


def run_sample(vn, path, rng, pixel_size_um=None):
    """Template run, then measured radial boundaries and the census on the measured zones."""
    pipe = H.run(vn, {'src': {'path': path}})
    gray = cv2.cvtColor(pipe['src']['main'], cv2.COLOR_BGR2GRAY)
    section = np.asarray(pipe['section']['mask']) > 0
    bounds, masks, ell, prof = R.measure_boundaries(gray, section, pipe['metaxylem']['mask'], rng=rng)
    sample = {'pipe': pipe, 'bounds': bounds, 'masks': masks, 'ell': ell, 'prof': prof, 'gray': gray,
              'section': section,
              'ellipse_report': R.ellipse_report(pipe['ellipse_prop']['report'], bounds)}
    extra = {'pixel_size_um': pixel_size_um} if pixel_size_um else {}
    sample['out'] = publish(vn, sample, pipe['cells']['labels'], **extra)
    sample['rep'] = sample['out']['predictive_report']
    return sample


def ground_truth(vn, sample):
    thr, amin = C.REFERENCE
    labels = C.drawing_labels(sample['gray'], sample['section'], thr, amin)
    rep = publish(vn, sample, labels, draw_legend=False)['predictive_report']
    return labels, C.observed(rep)


def fig1(sample_a, sample_b, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.2), dpi=250)
    for ax, smp, title in zip(axes, (sample_a, sample_b),
                              ('A — tracé expert (même coupe)', 'B — micrographie champ clair originale')):
        img = smp['out']['main']
        ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.axis('off')
    handles = [mpatches.Patch(facecolor=c, edgecolor='#333', label=l) for c, l in zip(ZONE_COLORS, LABELS_FR)]
    handles += [mpatches.Patch(facecolor='#e8f5e9', edgecolor='#1b5e20', label='Métaxylème (ellipses)'),
                mpatches.Patch(facecolor='white', edgecolor='#333', hatch='////', label='Lacunes (aérenchyme)')]
    fig.legend(handles=handles, loc='lower center', ncol=4, fontsize=8.5, frameon=False)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def fig5(gt, za, zb, out):
    x = np.arange(len(ZONES))
    w = 0.36
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=250)
    for off, zt, col, name in ((-w / 2, za, COL_A, 'A (tracé)'), (w / 2, zb, COL_B, 'B (photo)')):
        obs = np.array([zt[z]['obs'] for z in ZONES])
        tot = np.array([zt[z]['total'] for z in ZONES])
        proj = np.maximum(tot - obs, 0)
        ax.bar(x + off, obs, w, color=col, edgecolor='#222', linewidth=0.5, label=f'{name} : observées')
        ax.bar(x + off, proj, w, bottom=obs, facecolor='white', edgecolor=col, hatch='////', linewidth=0.8,
               label=f'{name} : imputées')
    truth = np.array([gt[z] for z in ZONES])
    ax.scatter(x, truth, marker='_', s=900, color=COL_GT, linewidths=2.2, zorder=5, label='Vérité terrain (A)')
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS_FR, fontsize=9)
    ax.set_ylabel('Cellules', fontsize=10)
    ax.spines[['top', 'right']].set_visible(False)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4)
    ax.legend(fontsize=8, ncol=3, loc='upper left', frameon=False)
    ax.set_ylim(0, max(truth.max(), max(za[z]['total'] for z in ZONES)) * 1.25)
    fig.tight_layout()
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def fig6(gt, za, zb, areas_a, curves, failures, out):
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=250)
    x = np.arange(len(ZONES))
    w = 0.36

    ax = axes[0, 0]
    for off, zt, col, name in ((-w / 2, za, COL_A, 'A (tracé)'), (w / 2, zb, COL_B, 'B (photo)')):
        frac = [100 * max(zt[z]['total'] - zt[z]['obs'], 0) / max(zt[z]['total'], 1) for z in ZONES]
        bars = ax.bar(x + off, frac, w, color=col, edgecolor='#222', linewidth=0.5, label=name)
        ax.bar_label(bars, fmt='%.0f%%', fontsize=7, padding=1)
    ax.set_title('A. Part imputée du total par zone', fontsize=10.5, fontweight='bold')
    ax.set_ylabel('% du total prédit', fontsize=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS_FR, fontsize=8, rotation=20, ha='right')
    ax.legend(fontsize=8, frameon=False)

    ax = axes[0, 1]
    data = [areas_a[z] for z in ZONES]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5, showfliers=False,
                    medianprops=dict(color='black', linewidth=1.2))
    for patch, c in zip(bp['boxes'], ZONE_COLORS):
        patch.set_facecolor(c)
    ax.set_xticks(range(1, len(ZONES) + 1))
    ax.set_xticklabels(LABELS_FR, fontsize=8, rotation=20, ha='right')
    ax.set_ylabel('Surface de la lumière (px², tracé 1358 px)', fontsize=9.5)
    ax.set_title('B. Surface des cellules segmentées par zone (A)', fontsize=10.5, fontweight='bold')

    ax = axes[1, 0]
    truth = sum(gt[z] for z in ZONES)
    names = ['B (photo)', 'A (tracé)']
    obs = [sum(zb[z]['obs'] for z in ZONES), sum(za[z]['obs'] for z in ZONES)]
    tot = [sum(zb[z]['total'] for z in ZONES), sum(za[z]['total'] for z in ZONES)]
    y = np.arange(2)
    ax.barh(y, obs, 0.45, color=['#d73027', '#4575b4'], edgecolor='#222', label='Observées')
    ax.barh(y, np.subtract(tot, obs), 0.45, left=obs, facecolor='white', edgecolor='#d95f02', hatch='////',
            label='Imputées')
    ax.axvline(truth, color=COL_GT, linestyle='--', linewidth=1.4, label=f'Vérité terrain = {truth}')
    for i in range(2):
        ax.text(tot[i] + 15, y[i], f'{tot[i]} ({(tot[i] - truth) / truth * 100:+.1f} %)', va='center', fontsize=9,
                fontweight='bold')
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9, fontweight='bold')
    ax.set_xlim(0, truth * 1.35)
    ax.set_xlabel('Cellules (hors métaxylème)', fontsize=9.5)
    ax.set_title('C. Recensement total face à la vérité terrain', fontsize=10.5, fontweight='bold')
    ax.legend(fontsize=8, loc='lower right', frameon=True)

    ax = axes[1, 1]
    sev = [100 * s for s in SEVERITIES]
    ax.plot(sev, curves['fixed_zones']['obs'], 's--', color='#7f7f7f', label='Observé seul (zones fixées)')
    ax.plot(sev, curves['fixed_zones']['tot'], 'o-', color='#2ca02c', label='Imputé, zones et lacunes oracle')
    ax.plot(sev, curves['end_to_end']['tot'], '^-', color='#1f77b4', label='Imputé, pipeline aveugle')
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


PIPELINE_STAGES = (
    ('1. Ancre invariante', '#e3ecf7', ('Image brute\ndégradée', 'Extraction des\nlumières contrastées',
                                         'Enveloppe des\nvaisseaux (k ≥ 5)', 'Ajustement d\'ellipse\n(cx, cy, a, b, θ)')),
    ('2. Frontières\nmesurées', '#e6f2e6', ('Champ elliptique ρ(x, y)\net déroulement (ρ, φ)',
                                           'Profils radiaux : densité\nde paroi, taille L_θ',
                                           'Ruptures de profil\n+ IC bootstrap',
                                           'Moelle : vaisseaux ;\nrhizoderme : contour')),
    ('3. Régularisation,\nimputation', '#fbefe0', ('Régularisation\ndes métaxylèmes', 'Libération du\nphloème absorbé',
                                                   'Lacunes corticales\n(hachures)',
                                                   'Imputation par\nsymétrie antipodale')),
    ('4. Rendu et\nmétrologie', '#efe6f5', ('Rendu graphique\nanti-aliasé 2×', 'Figure de\npublication',
                                            'Rapport\nmétrologique')),
)


def fig_pipeline(out):
    """Four-stage pipeline flowchart: one column per stage, read left to right."""
    fig, ax = plt.subplots(figsize=(7.6, 3.9), dpi=400)
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1)
    ax.axis('off')
    col_w, box_w, box_h, top = 0.90, 0.80, 0.125, 0.745
    for i, (title, color, steps) in enumerate(PIPELINE_STAGES):
        x0 = i + (1 - col_w) / 2
        ax.add_patch(mpatches.FancyBboxPatch((x0, 0.02), col_w, 0.93, boxstyle='round,pad=0,rounding_size=0.03',
                                             facecolor=color, edgecolor='#999999', linewidth=0.8))
        ax.text(i + 0.5, 0.885, title, ha='center', va='center', fontsize=9.5, fontweight='bold')
        step_dy = min(0.21, (top - 0.10) / max(len(steps) - 1, 1))
        for k, step in enumerate(steps):
            y = top - k * step_dy
            ax.add_patch(mpatches.FancyBboxPatch((i + 0.5 - box_w / 2, y - box_h / 2), box_w, box_h,
                                                 boxstyle='round,pad=0,rounding_size=0.02',
                                                 facecolor='white', edgecolor='#555555', linewidth=0.8))
            ax.text(i + 0.5, y, step, ha='center', va='center', fontsize=8.5, linespacing=1.2)
            if k:
                ax.annotate('', xy=(i + 0.5, y + box_h / 2), xytext=(i + 0.5, y + step_dy - box_h / 2),
                            arrowprops={'arrowstyle': '-|>', 'color': '#444444', 'lw': 1.0})
        if i < len(PIPELINE_STAGES) - 1:
            ax.annotate('', xy=(i + 1 + (1 - col_w) / 2 - 0.005, 0.5), xytext=(x0 + col_w + 0.005, 0.5),
                        arrowprops={'arrowstyle': 'simple,head_width=0.9,head_length=0.7',
                                    'color': '#555555', 'lw': 0})
    fig.tight_layout(pad=0.2)
    fig.savefig(out, facecolor='white', bbox_inches='tight', pad_inches=0.03)
    plt.close(fig)


def read_on_white(path):
    """RGB image; transparent pixels (alpha channel) are flattened onto white."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        alpha = img[..., 3:4].astype(np.float32) / 255
        img = (img[..., :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def fig_samples(out):
    """Source images A (expert drawing) and B (bright-field photo) side by side, same height."""
    imgs = [read_on_white(p) for p in (SAMPLE_A, SAMPLE_B)]
    h = min(im.shape[0] for im in imgs)
    imgs = [cv2.resize(im, (round(im.shape[1] * h / im.shape[0]), h), interpolation=cv2.INTER_AREA) for im in imgs]
    widths = [im.shape[1] for im in imgs]
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.2), dpi=250, gridspec_kw={'width_ratios': widths})
    titles = ('A — tracé anatomique d\'expert', 'B — micrographie optique en champ clair')
    for ax, img, title in zip(axes, imgs, titles):
        ax.imshow(img)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.axis('off')
    fig.tight_layout()
    fig.savefig(out, facecolor='white', bbox_inches='tight', pad_inches=0.05)
    plt.close(fig)


def bench_failures(runs_csv):
    """'n/N runs (x %), m/M at severity >= 0.35' from the benchmark runs table."""
    import csv
    runs = {}
    with open(runs_csv) as f:
        for r in csv.DictReader(f):
            if r['kind'] == 'clean':
                continue
            key = (r['image'], r['kind'], r['severity'], r['seed'])
            runs[key] = runs.get(key, False) or r['mode'] == 'failed'
    n, k = len(runs), sum(runs.values())
    hi = {key: v for key, v in runs.items() if float(key[2]) >= 0.35}
    return f'{k}/{n} runs ({100 * k / n:.0f} %), {sum(hi.values())}/{len(hi)} à sévérité ≥ 0,35'


BOUNDARY_STYLE = (('pith', 'Moelle (bord interne des vaisseaux)', '#8e7cc3'),
                  ('endo_inner', 'Endoderme, bord interne (−1 cellule)', '#ba68c8'),
                  ('endo_outer', 'Endoderme / cortex', '#7b1fa2'),
                  ('cortex_transition', 'Transition corticale', '#e65100'))


def fig_radial(sample_a, sample_b, gt_prof, out):
    """Polar unwraps of A and B with measured boundaries, and the radial profiles they come from."""
    rho = np.arange(0, R.RHO_MAX, R.RHO_STEP)
    fig = plt.figure(figsize=(12, 10.5), dpi=250)
    gs = fig.add_gridspec(3, 2, height_ratios=(1.15, 1, 1), hspace=0.32, wspace=0.12)
    for col, (smp, title) in enumerate(((sample_a, 'A — tracé'), (sample_b, 'B — micrographie'))):
        ax = fig.add_subplot(gs[0, col])
        b = smp['bounds']
        edge = b['edge']
        pol = smp['prof']['polar'][:int(edge / R.RHO_STEP) + 5]
        ax.imshow(pol, cmap='gray', aspect='auto', extent=(0, 360, pol.shape[0] * R.RHO_STEP, 0))
        for key, _, c in BOUNDARY_STYLE:
            ax.axhline(b[key], color=c, lw=1.4)
            if f'{key}_ci' in b:
                ax.axhspan(*b[f'{key}_ci'], color=c, alpha=0.25, lw=0)
        ax.axhline(1.0, color='#2e7d32', lw=1.0, ls='--')
        ax.axhline(edge, color='#1565c0', lw=1.2, ls='--')
        ax.set_title(f'{title} : déroulement polaire (ρ, φ)', fontsize=10.5, fontweight='bold')
        ax.set_xlabel('Azimut φ (°)', fontsize=9)
        if col == 0:
            ax.set_ylabel('ρ (anneau de métaxylème = 1)', fontsize=9)
    styles = (('GT', gt_prof, COL_GT, 'Vérité terrain A (cellules comptées)'),
              ('A', sample_a['prof'], COL_A, 'A (tracé, image brute)'),
              ('B', sample_b['prof'], COL_B, 'B (micrographie, image brute)'))
    ax_d = fig.add_subplot(gs[1, :])
    ax_l = fig.add_subplot(gs[2, :], sharex=ax_d)
    for key, prof, c, lab in styles:
        with np.errstate(all='ignore'):
            if prof['dark'] is not None:
                d = np.nanmedian(prof['dark'], 1)
                ax_d.plot(rho, (d - np.nanmin(d)) / (np.nanmax(d) - np.nanmin(d)), color=c, lw=1.4, label=lab)
            lt = prof['Lt'] / prof['px_per_rho']
            m = np.nanmedian(lt, 1)
            ax_l.plot(rho, m, color=c, lw=2.0 if key == 'GT' else 1.4, label=lab)
            ax_l.fill_between(rho, np.nanpercentile(lt, 25, 1), np.nanpercentile(lt, 75, 1), color=c, alpha=0.12)
    for ax in (ax_d, ax_l):
        for smp, ls in ((sample_a, '-'), (sample_b, '--')):
            for key, _, c in BOUNDARY_STYLE:
                ax.axvline(smp['bounds'][key], color=c, lw=1.0, ls=ls)
        ax.axvline(1.0, color='#2e7d32', lw=0.9, ls=':')
        ax.grid(alpha=0.3)
        ax.spines[['top', 'right']].set_visible(False)
    ax_d.set_ylabel('Densité de paroi (normalisée)', fontsize=9.5)
    ax_d.set_title('Profil radial de densité de paroi (médiane sur 16 secteurs angulaires)', fontsize=10.5,
                   fontweight='bold')
    ax_d.legend(fontsize=8, loc='upper right', frameon=True)
    ax_l.set_yscale('log')
    ax_l.set_ylabel('Taille circonférentielle\ndes cellules L_θ (unités ρ)', fontsize=9.5)
    ax_l.set_xlabel('ρ (traits pleins : frontières mesurées sur A ; tiretés : sur B)', fontsize=9.5)
    ax_l.set_title('Intercept linéaire moyen (stéréologie), bande = écart interquartile entre secteurs',
                   fontsize=10.5, fontweight='bold')
    ax_l.set_xlim(0.15, 3.0)
    ax_l.legend(fontsize=8, loc='lower right', frameon=True)
    handles = [plt.Line2D([], [], color=c, lw=2, label=lab) for _, lab, c in BOUNDARY_STYLE]
    handles += [plt.Line2D([], [], color='#2e7d32', ls='--', label='Anneau de métaxylème (ρ = 1)'),
                plt.Line2D([], [], color='#1565c0', ls='--', label='Bord de la section')]
    fig.legend(handles=handles, loc='lower center', ncol=3, fontsize=8.5, frameon=False)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.96, bottom=0.11)
    fig.savefig(out, facecolor='white')
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(REPO, 'bench_out', 'paper_figures'))
    ap.add_argument('--bench', default=BENCH_DIR, help='benchmark output dir (summary.md, runs.csv)')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    H.load_plugins()
    with open(C.TEMPLATE) as f:
        vn = json.load(f)
    rng = np.random.default_rng(0)
    smp_b = run_sample(vn, SAMPLE_B, rng)
    # same section at another magnification: scale A's pixel size by the metaxylem-ring ratio
    ring_ratio = (smp_b['pipe']['ellipse_prop']['report']['major_axis']
                  / H.run(vn, {'src': {'path': SAMPLE_A}})['ellipse_prop']['report']['major_axis'])
    smp_a = run_sample(vn, SAMPLE_A, rng, PIXEL_SIZE_B_UM * ring_ratio)
    rep_a, rep_b = smp_a['rep'], smp_b['rep']
    gt_labels, gt = ground_truth(vn, smp_a)
    gt_prof = R.polar_profiles(smp_a['gray'], smp_a['section'], smp_a['ell'], labels=gt_labels)
    za, zb = zone_table(rep_a), zone_table(rep_b)
    areas_true = cell_areas_by_zone(gt_labels, smp_a['masks'])
    areas_a = cell_areas_by_zone(smp_a['pipe']['cells']['labels'], smp_a['masks'])
    curves = bench_curves(os.path.join(args.bench, 'summary.md'))
    failures = bench_failures(os.path.join(args.bench, 'runs.csv'))
    misc_keys = ('lacunae_total_area_px', 'metaxylem_vessels_completed', 'metaxylem_raw_area_px',
                 'metaxylem_total_area_px', 'stele_tilt_deg')
    numbers = {
        'ring_ratio_B_over_A': ring_ratio,
        'boundaries_A': smp_a['bounds'], 'boundaries_B': smp_b['bounds'],
        'ground_truth': gt, 'ground_truth_total': sum(gt.values()), 'gt_cells_in_section': int(gt_labels.max()),
        'A': za, 'B': zb,
        'A_misc': {k: rep_a.get(k) for k in misc_keys}, 'B_misc': {k: rep_b.get(k) for k in misc_keys},
        'ellipse_A': smp_a['pipe']['ellipse_prop']['report'], 'ellipse_B': smp_b['pipe']['ellipse_prop']['report'],
        'monte_carlo_true_cells': monte_carlo(areas_true),
        'bench_curves': curves, 'bench_failures': failures,
    }
    with open(os.path.join(args.out, 'numbers.json'), 'w') as f:
        json.dump(numbers, f, indent=1, default=float)

    fig_pipeline(os.path.join(args.out, 'fig0_pipeline.png'))
    fig_samples(os.path.join(args.out, 'fig0_samples_ab.png'))
    fig_radial(smp_a, smp_b, gt_prof, os.path.join(args.out, 'fig_radial_boundaries.png'))
    fig1(smp_a, smp_b, os.path.join(args.out, 'fig1_publication_ab.png'))
    fig5(gt, za, zb, os.path.join(args.out, 'fig5_counts_vs_truth.png'))
    fig6(gt, za, zb, areas_a, curves, failures, os.path.join(args.out, 'fig6_dashboard.png'))
    gt_vis = cv2.applyColorMap((gt_labels * 37 % 255).astype(np.uint8), cv2.COLORMAP_HSV)
    gt_vis[gt_labels == 0] = 255
    cv2.imwrite(os.path.join(args.out, 'fig_ground_truth_labels.png'), gt_vis)
    print(json.dumps({k: numbers[k] for k in ('boundaries_A', 'boundaries_B', 'ground_truth', 'A', 'B')},
                     default=float))
    print(json.dumps(numbers['monte_carlo_true_cells'], default=float))


if __name__ == '__main__':
    main()
