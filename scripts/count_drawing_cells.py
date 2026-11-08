#!/usr/bin/env python3
"""Ground-truth cell counts of a closed-wall anatomical drawing.

On a line drawing every cell is a white region enclosed by dark walls, so the
connected components of the non-wall pixels inside the section ARE the cells.
They are fed, as a label map, to the same Root Publication Figure node as the
pipeline's own segmentation, so both are binned into zones by identical code.

Sensitivity: the count is repeated over several wall thresholds and minimum
areas (anti-aliasing specks / intercellular spaces) to show how stable it is.

Usage:
  python3 scripts/count_drawing_cells.py DRAWING [--out bench_out/drawing_ground_truth]
"""
import argparse
import csv
import json
import os
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine'))
sys.path.insert(0, os.path.join(REPO, 'engine', 'tests'))

import vn_headless as H  # noqa: E402

TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_predictive_ellipse_zoning.vn')
WALL_THRESHOLDS = (110, 160, 210)
MIN_AREAS = (4, 15, 40)
REFERENCE = (160, 15)  # (wall threshold, min area) reported as ground truth
ZONES = ('pith', 'vascular', 'endo', 'inner_cortex', 'outer_cortex', 'rhizodermis')
PUB_INPUTS = {
    'image': ('cells', 'main'), 'boundary': ('section', 'mask'), 'landmarks': ('metaxylem', 'mask'),
    'pith_mask': ('ellipse_prop', 'pith_mask'), 'vascular_mask': ('ellipse_prop', 'vascular_mask'),
    'endodermis_mask': ('ellipse_prop', 'endodermis_mask'),
    'inner_cortex_mask': ('ellipse_prop', 'inner_cortex_mask'),
    'outer_cortex_mask': ('ellipse_prop', 'outer_cortex_mask'),
    'rhizodermis_mask': ('ellipse_prop', 'rhizodermis_mask'),
    'ellipse_report': ('ellipse_prop', 'report'),
}


def drawing_labels(gray, section, wall_threshold, min_area):
    """Label map of the white regions enclosed by walls inside the section."""
    free = ((gray >= wall_threshold) & section).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    # regions touching the section edge are outside space leaking in, not cells
    edge = section & ~cv2.erode(section.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    keep[np.unique(lab[edge & (lab > 0)])] = False
    remap = np.zeros(n, np.int32)
    remap[keep] = np.arange(1, keep.sum() + 1)
    return remap[lab]


def zone_counts(labels, pipe_out):
    node = H.registry.NODE_CLASS_REGISTRY['draw_root_publication']()
    inputs = {k: pipe_out[n].get(port) for k, (n, port) in PUB_INPUTS.items()}
    rep = node.process({**inputs, 'labels': labels},
                       {'use_robust_decoalescence': False, 'draw_legend': False})['predictive_report']
    return rep


def observed(rep):
    """Raw per-zone counts (no decoalescence, no imputation)."""
    keys = {'pith': 'pith_cells_observed', 'vascular': 'vascular_cells_observed',
            'endo': 'endo_cells_observed', 'inner_cortex': 'inner_cortex_observed',
            'outer_cortex': 'outer_cortex_observed', 'rhizodermis': 'rhizodermis_observed'}
    return {z: rep.get(k) for z, k in keys.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('drawing')
    ap.add_argument('--out', default=os.path.join(REPO, 'bench_out', 'drawing_ground_truth'))
    args = ap.parse_args()
    if cv2.imread(args.drawing) is None:
        ap.error(f'cannot read {args.drawing}')
    os.makedirs(args.out, exist_ok=True)

    H.load_plugins()
    with open(TEMPLATE) as f:
        vn = json.load(f)
    pipe = H.run(vn, {'src': {'path': args.drawing}})
    gray = cv2.cvtColor(pipe['src']['main'], cv2.COLOR_BGR2GRAY)
    section = np.asarray(pipe['section']['mask']) > 0

    rows = []
    for thr in WALL_THRESHOLDS:
        for amin in MIN_AREAS:
            lab = drawing_labels(gray, section, thr, amin)
            rows.append({'wall_threshold': thr, 'min_area': amin, 'cells_in_section': int(lab.max()),
                         **observed(zone_counts(lab, pipe))})
            if (thr, amin) == REFERENCE:
                vis = cv2.applyColorMap((lab * 37 % 255).astype(np.uint8), cv2.COLORMAP_HSV)
                vis[lab == 0] = 255
                cv2.imwrite(os.path.join(args.out, 'ground_truth_labels.png'), vis)

    pipe_rep = pipe['pub_fig']['predictive_report']
    with open(os.path.join(args.out, 'sensitivity.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, 'pipeline_report.json'), 'w') as f:
        json.dump(pipe_rep, f, indent=2, default=float)
    for r in rows:
        print(r)
    print('pipeline:', {k: v for k, v in pipe_rep.items() if 'cells' in k or 'decoal' in k or 'observed' in k})


if __name__ == '__main__':
    main()
