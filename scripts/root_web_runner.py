"""RhizoFit: root cross-section analysis for the web app (runs natively and in Pyodide).

One call, `analyze(image_path, pixel_size_um)`, runs the Predictive Ellipse Zoning pipeline
(rhizofit_pipeline: the template's nodes as plain Python calls, no graph engine), measures the tissue boundaries on the polar unwrap (radial_zoning_lib), counts and imputes
cells in the measured zones, and returns everything the app displays:

  images   [{id, title, group, caption, png}]   step-by-step images
  charts   [{id, title, caption, png}]          matplotlib charts (dark theme)
  tables   [{id, title, columns, rows, note}]   metrics
  summary  {key: value}                         headline numbers

`bundle_zip(result)` packs images, charts and tables (CSV + JSON) into one zip.
"""
import csv
import io
import json
import os
import sys
import tempfile
import warnings
import zipfile
from functools import partial

import cv2
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(REPO, 'scripts'), os.path.join(REPO, 'engine')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cell_files_lib as CF  # noqa: E402
import cell_recovery_lib as CR  # noqa: E402
import photometry_lib as PH  # noqa: E402
import census_lib as CS  # noqa: E402
import lumen_census_lib as LC  # noqa: E402
import anchor_score_lib as AS  # noqa: E402
import damaged_region_lib as DR  # noqa: E402
import radial_zoning_lib as R  # noqa: E402
import rhizofit_pipeline as P  # noqa: E402
import vessel_edge_lib as VE  # noqa: E402

ZONES = ('pith', 'vascular', 'endo', 'inner_cortex', 'outer_cortex', 'rhizodermis')
ZONE_LABELS = ('Pith', 'Vascular cylinder', 'Endodermis', 'Inner cortex', 'Outer cortex', 'Rhizodermis')
ZONE_MASKS = ('pith_mask', 'vascular_mask', 'endodermis_mask', 'inner_cortex_mask', 'outer_cortex_mask',
              'rhizodermis_mask')
ZONE_COLORS = ('#b39ddb', '#ffd54f', '#ba68c8', '#81c784', '#ffb74d', '#64b5f6')
REPORT_KEYS = {  # observed, imputed, total, unit area
    'pith': ('pith_cells_observed', 'pith_cells_missing_pred', 'pith_cells_total_pred', 'pith_unit_area_px'),
    'vascular': ('vascular_cells_observed', 'vascular_cells_missing_pred', 'vascular_cells_total_pred',
                 'vascular_unit_area_px'),
    'endo': ('endo_cells_observed', 'endo_cells_missing_pred', 'endo_cells_total_pred', None),
    'inner_cortex': ('inner_cortex_observed', 'inner_cortex_missing_pred', 'inner_cortex_total_pred',
                     'inner_cortex_unit_area_px'),
    'outer_cortex': ('outer_cortex_observed', 'outer_cortex_missing_pred', 'outer_cortex_total_pred',
                     'outer_cortex_unit_area_px'),
    'rhizodermis': ('rhizodermis_observed', 'rhizodermis_missing_pred', 'rhizodermis_total_pred',
                    'rhizodermis_unit_area_px'),
}
BOUNDARIES = (('pith', 'Pith / vascular cylinder', 'inner edge of the metaxylem vessels', '#b39ddb'),
              ('metaxylem', 'Metaxylem ring (ρ = 1)', 'outer edge of the vessel ring (anchor)', '#66bb6a'),
              ('endo_inner', 'Endodermis, inner edge', 'outer edge minus one radial cell', '#ce93d8'),
              ('endo_outer', 'Endodermis / cortex', 'change point of the radial profiles', '#ab47bc'),
              ('cortex_transition', 'Inner / outer cortex', 'change point of the radial profiles', '#ff9800'),
              ('edge', 'Section edge', 'rho where half of the rays leave the section', '#42a5f5'))
STAGES = ('Segmenting the section', 'Measuring tissue boundaries', 'Counting cells', 'Drawing figures')
MIN_SIDE_PX = 256
STELE_ZONES = ('pith', 'vascular')   # counted by lumens (lumen_census_lib), not by closed-wall cells
WORKING_ROOT_DIAMETER_PX = 766.0  # root size of the reference micrograph the template was tuned on
MIN_ROOT_DIAMETER_PX = 150
SCALE_TOLERANCE = 0.02            # no resampling within ±2 % of the working size
BG, PANEL, FG, MUTED, GRID = '#0f1115', '#161a20', '#e6e8eb', '#9aa3ad', '#2a3038'


class AnalysisError(RuntimeError):
    """The image could not be analysed (user-facing message)."""


# --------------------------------------------------------------------------- pipeline

def _pub_params(**extra):
    return {**P.PUBLICATION_PARAMS, 'zones_from_masks': True, **extra}


def cortical_lacunae(labels, masks, mx, damaged):
    """Aerenchyma lacunae of the cortex (census_lib.lacuna_mask, one layer zone at a time).
    Damaged (torn or blurred) parts are not judged: missing tissue there is not aerenchyma."""
    out = np.zeros(np.asarray(damaged).shape, bool)
    for z in ('inner_cortex_mask', 'outer_cortex_mask'):
        out |= CS.lacuna_mask(labels, np.asarray(masks[z], bool) & ~damaged, mx)
    return out


def _publish(pipe, masks, ellipse_report, labels, pixel_size_um, mx, min_vessel_area=R.MIN_VESSEL_AREA,
             lacunae=None):
    node = P.node_class('draw_root_publication')()
    inputs = {'image': pipe['cells']['main'], 'labels': labels, 'boundary': pipe['section']['mask'],
              'landmarks': mx.astype(np.uint8) * 255, 'ellipse_report': ellipse_report,
              **{k: (v.astype(np.uint8) * 255) for k, v in masks.items()}}
    if lacunae is not None:
        inputs['lacunae'] = lacunae.astype(np.uint8) * 255
    extra = {'pixel_size_um': pixel_size_um} if pixel_size_um else {'draw_scale_bar': False}
    extra['min_vessel_area'] = int(min_vessel_area)
    out = node.process(inputs, _pub_params(**extra))
    if not out.get('predictive_report'):
        raise AnalysisError('The publication node produced no report.')
    return out


def _report(stage, fraction, progress):
    if progress is not None:
        progress(stage, float(fraction))


def _read_bgr(image_path):
    """8-bit BGR image of the upload (alpha flattened on white, 16-bit scaled)."""
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise AnalysisError('This file could not be read as an image (use PNG, JPEG, TIFF or WebP).')
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        alpha = img[..., 3:4].astype(np.float32) / 255
        img = (img[..., :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    if min(img.shape[:2]) < MIN_SIDE_PX:
        raise AnalysisError(f'The image is too small (at least {MIN_SIDE_PX} px per side is needed).')
    return img


MAX_ANCHOR_OFFSET = 0.5  # anchor centre farther than this from the section centre (section radii): no polyarch stele
STELE_ONLY_RATIO = 0.33  # dark region under this share of the textured section: only the stele is dark (thin-walled wheat-like sections 0.27-0.31; maize >= 0.94, LAT >= 0.35)


MIN_DENSITY_CELLS = 10    # fewer observed cells than this: no density can be measured on them
CENTRAL_VESSEL_MIN = 4.0  # a single central vessel is at least this many median cell lumens
CENTRAL_DOMINANCE = 2.0   # ... and at least twice the next largest lumen of the stele (else: a ring)


def _largest_filled(mask):
    """Largest region of `mask`, holes filled (uint8 0/1); None if empty."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(np.asarray(mask).astype(np.uint8))
    if n < 2:
        return None
    region = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    cnts, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(region)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    return filled


def _equivalent_diameter(region):
    return 0.0 if region is None else float(2 * np.sqrt(region.sum() / np.pi))


def dark_and_textured(img):
    """(dark region, textured section) of an image, each the largest region with holes filled.

    The dark region is the darker part on the bright backdrop (smoothing proportional to the image
    size); the textured section is everything that is not the slide (photometry_lib's backdrop)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (0, 0), max(gray.shape) / 200)
    _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return _largest_filled(dark > 0), _largest_filled(~PH.backdrop_mask(gray))


def thin_walled(dark, textured):
    """True when only the stele is dark: a pale, thin-walled cortex around a dark stele."""
    return _equivalent_diameter(dark) < STELE_ONLY_RATIO * _equivalent_diameter(textured)


def root_diameter_px(img):
    """Equivalent diameter (px) of the root: largest dark region on the bright backdrop, holes filled.

    Every smoothing scale is a fraction of the image size, so the estimate is proportional to
    the resolution (it is what makes the analysis resolution-independent).
    On a thin-walled section (pale cortex, dark stele) the dark region is the stele alone; the root
    is then the textured region that is not the slide (photometry_lib's backdrop), which spans the
    cortex. That estimate is used only when the dark region is clearly smaller, so sections whose
    whole root is dark keep the dark-region estimate.
    """
    dark, textured = dark_and_textured(img)
    if dark is None:
        raise AnalysisError('No root section was found in the image.')
    return _equivalent_diameter(textured if thin_walled(dark, textured) else dark)


def rhizodermis_by_outline(section, layer_px):
    """Cells of the outermost layer: outline length of the section over the layer thickness."""
    cnts, _ = cv2.findContours(np.asarray(section).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts or not layer_px:
        return 0
    outline = cv2.approxPolyDP(max(cnts, key=cv2.contourArea), 1.0, True)   # pixel staircase smoothed
    return int(round(cv2.arcLength(outline, True) / layer_px))


def central_vessel(candidates, stele, lumen_area):
    """Mask of a single central metaxylem vessel: the largest vessel candidate whose centre lies in the
    stele, if it is at least CENTRAL_VESSEL_MIN median cell lumens and CENTRAL_DOMINANCE times the next
    largest candidate of the stele; else None. A polyarch stele has several vessels of similar sizes;
    a root with one large central vessel (e.g. wheat) has one that dominates."""
    n, lab, stats, cent = cv2.connectedComponentsWithStats((np.asarray(candidates) > 0).astype(np.uint8))
    stele = np.asarray(stele) > 0
    inside = [i for i in range(1, n) if stele[int(round(cent[i][1])), int(round(cent[i][0]))]]
    if not inside:
        return None
    areas = sorted(((stats[i, cv2.CC_STAT_AREA], i) for i in inside), reverse=True)
    best_area, best = areas[0]
    if best_area < CENTRAL_VESSEL_MIN * lumen_area:
        return None
    if len(areas) > 1 and best_area < CENTRAL_DOMINANCE * areas[1][0]:
        return None
    return lab == best


def stele_edge_rho(stele, ell):
    """Median rho along the outline of the stele region (the endodermis/cortex boundary)."""
    cnts, _ = cv2.findContours(np.asarray(stele).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pts = max(cnts, key=cv2.contourArea)[:, 0, :]
    rho = R.rho_field(np.asarray(stele).shape, ell)
    return float(np.median(rho[pts[:, 1], pts[:, 0]]))


def anchor_offset(section, ell):
    """Distance from the section's centroid to the anchor centre, in equivalent section radii.

    The metaxylem ring of a polyarch stele sits at the centre of the section (torn sections included:
    0.14 at most for a 60 degree sector torn away). A ring found far from it is made of other large
    lumens, e.g. cortex cells around a single central vessel, as in wheat."""
    ys, xs = np.nonzero(section)
    radius = np.sqrt(len(ys) / np.pi)
    return float(np.hypot(ell[0] - xs.mean(), ell[1] - ys.mean()) / radius)


def _normalised_upload(image_path, scale=None):
    """Upload normalised (photometry_lib) and resampled so the root spans WORKING_ROOT_DIAMETER_PX,
    as a temp PNG; returns (path, scale, photometry report).

    scale = working px per original px. The template's pixel-sized settings were tuned at
    this root size, so every resolution or magnification is analysed at the same scale.
    A given `scale` is applied as is (e.g. to analyse damaged copies in the frame of the intact image).
    """
    img, photometry = PH.normalise(_read_bgr(image_path))  # lighting gradient / weak contrast undone
    if scale is not None:
        if scale != 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        fd, out = tempfile.mkstemp(suffix='.png', prefix='root_upload_')
        os.close(fd)
        cv2.imwrite(out, img)
        return out, float(scale), photometry
    diameter = root_diameter_px(img)
    if diameter < MIN_ROOT_DIAMETER_PX:
        raise AnalysisError(f'The root is too small in the image ({diameter:.0f} px across; '
                            f'at least {MIN_ROOT_DIAMETER_PX} px are needed).')
    scale = WORKING_ROOT_DIAMETER_PX / diameter
    if abs(scale - 1) > SCALE_TOLERANCE:
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=interp)
    else:
        scale = 1.0
    fd, out = tempfile.mkstemp(suffix='.png', prefix='root_upload_')
    os.close(fd)
    cv2.imwrite(out, img)
    return out, scale, photometry


def vessel_floor(pipe):
    """Smallest vessel area (px): the ring search's own floor, twice the median cell lumen
    (`mx_floor`); R.MIN_VESSEL_AREA when the pipeline did not compute it. The single definition of
    a vessel's size used by the anchor search and every measurement after it."""
    floor = (pipe.get('mx_floor') or {}).get('result')
    return float(floor) if floor else float(R.MIN_VESSEL_AREA)


def _lumen_area(pipe):
    """Median cell lumen area (px) of the section, the reference of the anchor's size contrast."""
    med = (pipe.get('lum_med') or {}).get('median')
    if not med:
        raise AnalysisError('No cell lumen was segmented: the vessel ring cannot be judged.')
    return float(med)


def _section_of(runs):
    base = runs['stele']
    section = np.asarray(base['section'].get('mask') if base['section'].get('mask') is not None else 0) > 0
    if not section.any():
        raise AnalysisError('No root section was found in the image.')
    return section


def _boundaries(pipe, section, mx, min_vessel, n_boot, stele_edge=None):
    gray = cv2.cvtColor(pipe['src']['main'], cv2.COLOR_BGR2GRAY)
    try:
        bounds, masks, ell, prof = R.measure_boundaries(gray, section, mx, n_boot=n_boot, min_vessel_area=min_vessel,
                                                        stele_edge=stele_edge)
    except ValueError as exc:
        raise AnalysisError(f'Tissue boundaries could not be measured ({exc}).') from exc
    if anchor_offset(section, ell) > MAX_ANCHOR_OFFSET:
        raise AnalysisError('No metaxylem ring was found around the centre of the section. RhizoFit needs a '
                            'ring of at least three large metaxylem vessels (polyarch stele, as in maize, rice '
                            'or sorghum), or a single large central vessel in a dark stele (as in wheat).')
    return gray, bounds, masks, ell, prof


def _polyarch_anchor(runs, n_boot):
    """Anchor on the most plausible ring of metaxylem vessels (polyarch stele)."""
    section = _section_of(runs)
    base = runs['stele']
    min_vessel = vessel_floor(base)
    best = AS.best_anchor({k: p['mx_cand'].get('mask') for k, p in runs.items()}, _lumen_area(base), min_vessel)
    if best is None:
        raise AnalysisError('No metaxylem ring was detected: no three large round lumens lie on a circle.')
    pipe = runs[best['search']]
    anchor = {'search': best['search'], 'count': best['count'], **best['criteria']}
    return (pipe, section, best['mask'], min_vessel, anchor) + _boundaries(pipe, section, best['mask'], min_vessel, n_boot)


def _central_vessel_anchor(runs, stele, n_boot):
    """Anchor on a single large central vessel, the stele outline giving the endodermis; None if absent."""
    pipe = runs['whole']
    mx = central_vessel(pipe['mx_cand'].get('mask'), stele, _lumen_area(pipe))
    if mx is None:
        return None
    section = _section_of(runs)
    min_vessel = vessel_floor(pipe)
    edge = stele_edge_rho(stele, R.anchor_ellipse(mx))
    anchor = {'search': 'central vessel', 'count': 1}
    return (pipe, section, mx, min_vessel, anchor) + _boundaries(pipe, section, mx, min_vessel, n_boot, edge)


def run_pipeline(image_path, pixel_size_um=None, n_boot=R.N_BOOT, progress=None, scale=None, walled_lacunae=True):
    """Segmentation pipeline + measured boundaries + census. Returns the raw state used by the figures.

    `walled_lacunae` (on by default): also recognise aerenchyma lacunae enclosed by intact walls,
    which the first segmentation outlines as cells (cell_recovery_lib.remove_walled_lacunae).

    Lengths inside the state are in working pixels; `scale` converts them back to the upload.
    """
    image_path, scale, photometry = _normalised_upload(image_path, scale)
    work_pixel_um = pixel_size_um / scale if pixel_size_um else None
    try:
        work = cv2.imread(image_path)
        runs = P.run(image_path, on_step=lambda i, n, _nid: _report(STAGES[0], i / n, progress))
        try:
            found = _polyarch_anchor(runs, n_boot)
        except AnalysisError as polyarch_error:
            # no centred ring of vessels: a thin-walled root with one large central vessel (e.g. wheat)?
            dark, textured = dark_and_textured(work)
            if dark is None or textured is None or not thin_walled(dark, textured):
                raise
            runs = P.run(image_path, section=textured)
            found = _central_vessel_anchor(runs, dark, n_boot)
            if found is None:
                raise polyarch_error
    finally:
        os.remove(image_path)
    pipe, section, mx, min_vessel, anchor, gray, bounds, masks, ell, prof = found
    _report(STAGES[2], 0.0, progress)
    ellipse_report = {**R.ellipse_report(pipe['ellipse_prop']['report'], bounds), **R.anchor_report(ell)}
    labels = np.asarray(pipe['cells']['labels'])
    cortex = masks['inner_cortex_mask'] | masks['outer_cortex_mask']
    rho = R.rho_field(section.shape, ell)
    n_split = n_filled = n_walled = 0
    try:
        expected = CR.expected_area_profile(labels, rho, cortex)  # first-pass cells only
        labels, recovered, n_recovered = CR.recover_faint_cells(labels, gray, cortex)
        labels, created, n_split, n_filled = CR.check_against_polar_profile(labels, recovered, rho, cortex,
                                                                            expected)
        recovered = recovered | created
        if walled_lacunae:
            labels, n_walled, _ = CR.remove_walled_lacunae(labels, gray, cortex, rho, expected,
                                                           bounds['px_per_rho'],
                                                           background=float(np.median(gray[~section])))
        labels, _ = CR.drop_fragments(labels, rho, cortex, expected)
        recovered &= labels > 0
    except ValueError:  # no segmented cortex cell to calibrate on: keep the first pass
        recovered, n_recovered = np.zeros_like(section), 0
    damage = DR.damaged_regions(gray, section, rho, DR.phi_field(section.shape, ell), bounds['px_per_rho'])
    lacunae = cortical_lacunae(labels, masks, mx, damage['torn'] | damage['blurred'])
    pub = _publish(pipe, masks, ellipse_report, labels, work_pixel_um, mx, min_vessel, lacunae)
    try:
        cell_files = CF.cortical_cell_files(labels, section, ell, bounds['endo_outer'], bounds['rhizo_layer_px'])
    except ValueError:
        cell_files = None
    return {'pipe': pipe, 'gray': gray, 'section': section, 'mx': mx, 'bounds': bounds, 'min_vessel_area': min_vessel,
            'masks': masks, 'ell': ell, 'prof': prof, 'labels': labels, 'pub': pub,
            'recovered': recovered, 'n_recovered': n_recovered, 'cell_files': cell_files, 'n_split': n_split, 'n_filled': n_filled,
            'n_walled_lacunae': n_walled if walled_lacunae else None,
            'report': pub['predictive_report'], 'pixel_size_um': pixel_size_um, 'scale': scale,
            'rho': rho, 'photometry': photometry, 'damage': damage, 'anchor': anchor, 'lacunae': lacunae}


# --------------------------------------------------------------------------- images

def _png(img):
    ok, buf = cv2.imencode('.png', img)
    if not ok:
        raise AnalysisError('PNG encoding failed.')
    return buf.tobytes()


def _bgr(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (4, 2, 0))


def _ellipse_points(ell, rho, n=720):
    cx, cy, a, b, t = ell
    phi = np.linspace(0, 2 * np.pi, n)
    xr, yr = rho * a * np.cos(phi), rho * b * np.sin(phi)
    x = cx + np.cos(t) * xr - np.sin(t) * yr
    y = cy + np.sin(t) * xr + np.cos(t) * yr
    return np.round(np.column_stack([x, y])).astype(np.int32)


def _thickness(img):
    return max(1, round(max(img.shape[:2]) / 600))


def _img_section(st):
    img = st['pipe']['src']['main'].copy()
    cnts, _ = cv2.findContours(st['section'].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, cnts, -1, (80, 200, 120), 2 * _thickness(img), cv2.LINE_AA)
    return img


def _img_anchor(st):
    img = st['pipe']['src']['main'].copy()
    over = img.copy()
    over[st['mx']] = (90, 200, 90)
    img = cv2.addWeighted(over, 0.55, img, 0.45, 0)
    th = _thickness(img)
    cv2.polylines(img, [_ellipse_points(st['ell'], 1.0)], True, (60, 230, 60), 2 * th, cv2.LINE_AA)
    cx, cy = (int(round(v)) for v in st['ell'][:2])
    cv2.drawMarker(img, (cx, cy), (60, 60, 240), cv2.MARKER_CROSS, 18 * th, 2 * th)
    return img


def _img_rho(st):
    rho = st['rho']
    norm = np.clip(rho / max(st['bounds']['edge'], 1e-6), 0, 1)
    img = cv2.applyColorMap((norm * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
    img[~st['section']] = (21, 17, 15)
    th = _thickness(img)
    for key, _, _, col in BOUNDARIES:
        if key != 'edge':
            cv2.polylines(img, [_ellipse_points(st['ell'], st['bounds'][key])], True, _bgr(col), th, cv2.LINE_AA)
    return img


def _img_unwrap(st):
    b, step = st['bounds'], st['prof']['rho_step']
    pol = st['prof']['polar'][:int((b['edge'] + 0.05) / step)]
    img = cv2.resize(pol, (1600, pol.shape[0] * 2), interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    scale = img.shape[0] / pol.shape[0] / step
    for key, _, _, col in BOUNDARIES:
        y = int(round(b[key] * scale))
        cv2.line(img, (0, y), (img.shape[1], y), _bgr(col), 2, cv2.LINE_AA)
    return img


def _img_zones(st):
    img = st['pipe']['src']['main'].copy()
    over = img.copy()
    for mname, col in zip(ZONE_MASKS, ZONE_COLORS):
        over[st['masks'][mname]] = _bgr(col)
    img = cv2.addWeighted(over, 0.5, img, 0.5, 0)
    img[~st['section']] = st['pipe']['src']['main'][~st['section']]
    return img


def _img_recovered(st):
    img = st['pipe']['src']['main'].copy()
    rec = st['recovered']
    img[rec] = (0.55 * img[rec] + np.array([40, 160, 40]) * 0.45).astype(np.uint8)
    edges = cv2.morphologyEx(np.where(rec, st['labels'], 0).astype(np.uint16), cv2.MORPH_GRADIENT,
                             np.ones((3, 3), np.uint8)) > 0
    img[edges & rec] = (30, 150, 30)
    return img


def build_images(st):
    pipe = st['pipe']
    specs = (
        ('input', 'Input image', 'Source', 'The uploaded cross-section.', pipe['src']['main']),
        ('section', 'Section outline', 'Segmentation', 'Largest tissue region, used as the analysis domain.',
         _img_section(st)),
        ('walls', 'Cell walls', 'Segmentation', 'Multiscale ridge filter: dark walls become bright lines.',
         pipe['ridge']['main']),
        ('cells', 'Segmented cells', 'Segmentation', 'Individual cell lumens found between the walls.',
         pipe['cells']['main']),
        ('recovered', 'Recovered faint cells', 'Segmentation',
         f'{st["n_recovered"]} pale cortex cells found by a second pass (illumination flattened, dark wall '
         f'lines, watershed). Checked against the expected cell size at their ρ: {st["n_split"]} clusters split, '
         f'{st["n_filled"]} small empty regions turned into cells. What stays empty is aerenchyma.',
         _img_recovered(st)),
        ('anchor', 'Metaxylem anchor', 'Geometry',
         'Metaxylem vessels and the ellipse fitted around their ring (ρ = 1), with the stele centre.',
         _img_anchor(st)),
        ('rho', 'Elliptical coordinate ρ', 'Geometry',
         'ρ normalised by the anchor ellipse; coloured lines are the measured boundaries.', _img_rho(st)),
        ('unwrap', 'Polar unwrap (ρ, φ)', 'Geometry',
         'The section unrolled along its tilted ellipses: every tissue layer becomes a horizontal band. '
         'Lines: measured boundaries (top = centre).', _img_unwrap(st)),
        ('zones', 'Measured tissue zones', 'Results',
         'Zones from the measured boundaries; the rhizodermis follows the real section outline.',
         _img_zones(st)),
        ('publication', 'Publication figure', 'Results',
         'Cells coloured by tissue, regularised metaxylem, hatched cortical lacunae.',
         st['pub']['figure_with_legend']),
    )
    return [{'id': i, 'title': t, 'group': g, 'caption': c, 'png': _png(np.asarray(img))}
            for i, t, g, c, img in specs if img is not None]


# --------------------------------------------------------------------------- charts

def _style(ax):
    ax.set_facecolor(PANEL)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.label.set_color(FG)
    ax.xaxis.label.set_color(FG)
    ax.title.set_color(FG)
    ax.grid(color=GRID, linewidth=0.6, alpha=0.8)


def _fig(*args, **kw):
    fig, axes = plt.subplots(*args, dpi=200, facecolor=BG, **kw)
    for ax in np.atleast_1d(axes).ravel():
        _style(ax)
    return fig, axes


def _fig_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=BG, bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)
    return buf.getvalue()


def _legend(ax, **kw):
    leg = ax.legend(fontsize=8, frameon=True, **kw)
    leg.get_frame().set_facecolor(BG)
    leg.get_frame().set_edgecolor(GRID)
    for t in leg.get_texts():
        t.set_color(FG)


def _chart_profiles(st):
    prof, b = st['prof'], st['bounds']
    rho = prof['rho']
    fig, axes = _fig(3, 1, figsize=(10, 9), sharex=True)
    with np.errstate(all='ignore'), warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)  # rho rows outside the section are all-NaN
        d = np.nanmedian(prof['dark'], 1)
        series = (((d - np.nanmin(d)) / (np.nanmax(d) - np.nanmin(d)), None, 'Wall density (normalised)', False),
                  (np.nanmedian(prof['Lt'], 1) / prof['px_per_rho'], prof['Lt'] / prof['px_per_rho'],
                   'Circumferential cell size L_θ (ρ units)', True),
                  (np.nanmedian(prof['Lr'], 1) / prof['px_per_rho'], prof['Lr'] / prof['px_per_rho'],
                   'Radial cell size L_ρ (ρ units)', True))
        for ax, (m, per_sector, label, log) in zip(axes, series):
            ax.plot(rho, m, color='#4fc3f7', lw=1.4)
            if per_sector is not None:
                ax.fill_between(rho, np.nanpercentile(per_sector, 25, 1), np.nanpercentile(per_sector, 75, 1),
                                color='#4fc3f7', alpha=0.18, lw=0)
            if log:
                ax.set_yscale('log')
            ax.set_ylabel(label, fontsize=9)
            for key, name, _, col in BOUNDARIES:
                ax.axvline(b[key], color=col, lw=1.2, label=name)
                ci = b.get(f'{key}_ci')
                if ci and np.all(np.isfinite(ci)):
                    ax.axvspan(*ci, color=col, alpha=0.18, lw=0)
    axes[-1].set_xlim(0.15, b['edge'] + 0.1)
    axes[-1].set_xlabel('ρ (metaxylem ring = 1)')
    axes[0].set_title('Radial profiles (median of 16 angular sectors; band = interquartile range)', fontsize=11)
    handles, labels = axes[0].get_legend_handles_labels()
    leg = fig.legend(handles, labels, loc='lower center', ncol=3, fontsize=8.5, frameon=False)
    for t in leg.get_texts():
        t.set_color(FG)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return _fig_png(fig)


def _chart_counts(census):
    x = np.arange(len(ZONES))
    obs = np.array([census[z]['observed'] for z in ZONES])
    tot = np.array([census[z]['total'] for z in ZONES])
    fig, ax = _fig(figsize=(10, 4.6))
    ax.bar(x, obs, 0.6, color=ZONE_COLORS, edgecolor=BG, label='Observed')
    ax.bar(x, np.maximum(tot - obs, 0), 0.6, bottom=obs, facecolor='none', edgecolor=FG, hatch='////',
           linewidth=0.8, label='Imputed')
    for i, t in enumerate(tot):
        ax.text(i, max(t, obs[i]) * 1.02, f'{t}', ha='center', va='bottom', color=FG, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(ZONE_LABELS, fontsize=9, color=FG)
    ax.set_ylabel('Cells')
    ax.set_title('Cell census by tissue (observed + imputed)', fontsize=11)
    _legend(ax, loc='upper right')
    fig.tight_layout()
    return _fig_png(fig)


def _chart_areas(areas, unit, factor):
    fig, ax = _fig(figsize=(10, 4.6))
    data = [np.asarray(areas[z], float) * factor for z in ZONES]
    keep = [i for i, a in enumerate(data) if len(a)]
    bp = ax.boxplot([data[i] for i in keep], patch_artist=True, widths=0.55, showfliers=False,
                    medianprops={'color': BG, 'linewidth': 1.4},
                    whiskerprops={'color': MUTED}, capprops={'color': MUTED})
    for patch, i in zip(bp['boxes'], keep):
        patch.set_facecolor(ZONE_COLORS[i])
        patch.set_edgecolor(ZONE_COLORS[i])
    ax.set_xticks(range(1, len(keep) + 1))
    ax.set_xticklabels([ZONE_LABELS[i] for i in keep], fontsize=9, color=FG)
    ax.set_ylabel(f'Cell lumen area ({unit})')
    ax.set_title('Segmented cell size by tissue', fontsize=11)
    fig.tight_layout()
    return _fig_png(fig)


def _chart_composition(zone_area):
    total = sum(zone_area.values())
    fig, ax = _fig(figsize=(10, 2.4))
    left = 0
    for z, lab, col in zip(ZONES, ZONE_LABELS, ZONE_COLORS):
        share = 100 * zone_area[z] / max(total, 1)
        ax.barh(0, share, left=left, color=col, edgecolor=BG)
        if share > 4:
            ax.text(left + share / 2, 0, f'{lab}\n{share:.1f} %', ha='center', va='center', fontsize=8, color=BG)
        left += share
    ax.set_xlim(0, 100)
    ax.set_yticks([])
    ax.set_xlabel('% of section area')
    ax.set_title('Tissue composition of the section', fontsize=11)
    ax.grid(False)
    fig.tight_layout()
    return _fig_png(fig)


# --------------------------------------------------------------------------- metrics

def _cell_areas(labels, masks, mx):
    """Lumen area of every segmented cell, binned by the zone under its centroid (vessels excluded)."""
    n = int(labels.max())
    if n == 0:
        return {z: [] for z in ZONES}
    area = np.bincount(labels.ravel(), minlength=n + 1)
    ys, xs = np.indices(labels.shape)
    cy = np.bincount(labels.ravel(), ys.ravel(), minlength=n + 1) / np.maximum(area, 1)
    cx = np.bincount(labels.ravel(), xs.ravel(), minlength=n + 1) / np.maximum(area, 1)
    ids = np.nonzero(area[1:])[0] + 1
    r, c = np.round(cy[ids]).astype(int), np.round(cx[ids]).astype(int)
    keep = ~np.asarray(mx)[r, c]
    ids, r, c = ids[keep], r[keep], c[keep]
    return {z: area[ids[np.asarray(masks[m])[r, c]]].tolist() for z, m in zip(ZONES, ZONE_MASKS)}


def _census_territory(st):
    """Census by territory density (census_lib), by lumens in the stele (lumen_census_lib); the
    endodermis keeps its perimeter estimate.

    Torn or blurred parts of the section (damaged_region_lib) are completed from the healthy cells of
    the same layers; the zones then follow the expected section, tears restored.
    """
    rep = st['report']
    damage = st['damage']
    damaged = damage['torn'] | damage['blurred']
    masks = (R.zone_masks(st['rho'], damage['expected_section'], st['bounds']) if damage['torn'].any()
             else st['masks'])
    phi = DR.phi_field(damaged.shape, st['ell']) if damaged.any() else None
    lumens = LC.lumen_basins(st['gray'], np.asarray(st['section'], bool) & ~(np.asarray(st['mx']) > 0))
    shapes = LC.basin_shapes(lumens)
    out = {}
    for z, mname in zip(ZONES, ZONE_MASKS):
        k_unit = REPORT_KEYS[z][3]
        unit = float(rep[k_unit]) if k_unit and k_unit in rep else None
        if z == 'endo':
            obs, tot = int(rep.get('endo_cells_observed', 0)), int(rep.get('endo_cells_total_pred', 0))
        else:
            factor = (partial(DR.outline_completion, damage['expected_section'], damaged) if z == 'rhizodermis'
                      else partial(DR.polar_completion, st['labels'], masks[mname], damaged, st['mx'], st['rho'], phi))
            if z in STELE_ZONES:      # cells too small for closed walls: counted by their lumens
                obs, tot = DR.completed_count(partial(LC.zone_census, shapes=shapes), lumens, masks[mname], damaged,
                                              st['mx'], factor)
            else:
                obs, tot = DR.completed_count(CS.zone_census, st['labels'], masks[mname], damaged, st['mx'], factor,
                                              keep_lacunae=z in ('inner_cortex', 'outer_cortex'))
            if z == 'rhizodermis' and obs < MIN_DENSITY_CELLS:
                # too few epidermal cells segmented to measure a density (thin epidermis): one layer of
                # cells as wide as the layer is thick, along the outline of the section
                tot = max(obs, rhizodermis_by_outline(damage['expected_section'], st['bounds']['rhizo_layer_px']))
        out[z] = {'observed': obs, 'imputed': max(tot - obs, 0), 'total': tot, 'unit_area_px': unit}
    return out


def _census(rep):
    out = {}
    for z in ZONES:
        k_obs, k_proj, k_tot, k_unit = REPORT_KEYS[z]
        obs, tot = int(rep.get(k_obs, 0)), int(rep.get(k_tot, 0))
        out[z] = {'observed': obs, 'imputed': int(rep.get(k_proj, 0)), 'total': tot,
                  'unit_area_px': float(rep[k_unit]) if k_unit and k_unit in rep else None}
    return out


def _num(v, digits=2):
    """JSON-friendly number rounded for display (None for missing or non-finite values)."""
    if v is None:
        return None
    v = float(v)
    if not np.isfinite(v):
        return None
    return int(round(v)) if digits == 0 else round(v, digits)


def _metaxylem_vessels(mx, min_area=R.MIN_VESSEL_AREA, image=None):
    """Area and axes of every anchor vessel. With `image` (bright lumens, dark walls) the lumen edge
    is placed at half height of the lumen-to-wall drop (vessel_edge_lib); else the mask outline."""
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mx.astype(np.uint8))
    rows = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        comp = lab == i
        edge = VE.lumen_edge(image, comp) if image is not None else None
        if edge is None:
            cnts, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            outline, raw = cnts[0], float(stats[i, cv2.CC_STAT_AREA])
        else:
            outline, raw = edge.reshape(-1, 1, 2), float(cv2.contourArea(edge.reshape(-1, 1, 2)))
        (_, _), (w, h), _ = cv2.fitEllipse(outline)
        rows.append({'raw': raw, 'reg': float(np.pi * w * h / 4), 'major': float(max(w, h)), 'minor': float(min(w, h))})
    return rows


def _lumen_image(st):
    """Polarity-normalised working image (bright lumens, dark walls), or None."""
    img = P.output(st['pipe'].get('pol'), 'main')
    if img is None:
        return None
    img = np.asarray(img)
    return img[..., 0] if img.ndim == 3 else img


def _photometry_note(rep):
    """What the photometric normalisation did to the upload, in words."""
    if not rep:
        return 'none'
    done = []
    if rep.get('flat_field'):
        done.append(f"uneven lighting flattened ({100 * rep['illumination_variation']:.0f} % across the root)")
    if rep.get('stretch', 1.0) > 1.0:
        done.append(f"weak contrast stretched x{rep['stretch']:.2f}")
    return '; '.join(done) or 'none'


def _damage_note(damage):
    """Damaged parts of the section completed in the census, in words."""
    if not damage:
        return 'none'
    done = []
    if damage['torn_share'] > 0:
        done.append(f"{100 * damage['torn_share']:.0f} % torn away")
    if damage['blurred_share'] > 0:
        done.append(f"{100 * damage['blurred_share']:.0f} % out of focus")
    return '; '.join(done) or 'none'


def build_tables(st, census, zone_area, areas):
    """Metric tables; cells are raw numbers (formatted by the app) or short strings."""
    px = st['pixel_size_um']
    lin = (px if px else 1.0) / st['scale']  # working px -> µm, or -> pixels of the upload
    ar = lin * lin
    unit_l, unit_a = ('µm', 'µm²') if px else ('px', 'px²')
    b, rep, ell = st['bounds'], st['report'], st['ell']
    r_px = b['px_per_rho']
    sec_area = float(st['section'].sum())
    stele = sum(zone_area[z] for z in ('pith', 'vascular', 'endo'))
    cortex = zone_area['inner_cortex'] + zone_area['outer_cortex']
    lac = float(rep.get('lacunae_total_area_px', 0))
    vessels = _metaxylem_vessels(st['mx'], st.get('min_vessel_area', R.MIN_VESSEL_AREA), _lumen_image(st))
    obs_total = sum(c['observed'] for c in census.values())
    imp_total = sum(c['imputed'] for c in census.values())
    est_total = sum(c['total'] for c in census.values())

    summary_rows = [
        ['Cells observed', obs_total, 'cells', 'segmented in the six tissues'],
        ['Cells estimated', est_total, 'cells', 'observed + imputed (endodermis: perimeter / cell length)'],
        ['Metaxylem vessels', len(vessels), 'vessels', 'large vessels of the anchor ring'],
        ['Faint cells recovered', st['n_recovered'], 'cells', 'second-pass segmentation of pale cortex walls'],
        ['Clusters split', st['n_split'], 'regions', 'recovered regions > 2x the expected cell area at their ρ'],
        ['Lacunae reclassified', st['n_filled'], 'regions', 'empty regions of 0.4-3 expected cells: unseen cells'],
        ['Walled lacunae', st.get('n_walled_lacunae'), 'regions',
         'wall-enclosed radial sectors over 3 expected cells and 3 layers deep, as bright as the backdrop, '
         'counted as aerenchyma' if st.get('n_walled_lacunae') is not None else 'detection off'],
        ['Image correction', _photometry_note(st.get('photometry')), '', 'applied before the analysis; '
         'a correct micrograph is not modified'],
        ['Damaged section', _damage_note(st.get('damage')), '', 'of the expected section; their cells are '
         'counted from the healthy cells of the same layers (polar rows; rhizodermis by outline length)'],
        ['Section area', _num(sec_area * ar, 0), unit_a, ''],
        ['Stele share of the section', _num(100 * stele / max(sec_area, 1), 1), '%', 'pith + vascular + endodermis'],
        ['Cortex share of the section', _num(100 * cortex / max(sec_area, 1), 1), '%', 'inner + outer cortex'],
        ['Cortical cell files (CF)', _num(st['cell_files'][0], 1) if st['cell_files'] else None, 'files',
         (f'fewest touching cells crossed from the endodermis to the rhizodermis, median over the cells '
          f'under the rhizodermis, interquartile {st["cell_files"][1]:.0f}-{st["cell_files"][2]:.0f}')
         if st['cell_files'] else 'no cell chain across the cortex'],
        ['Cortical lacunae (%AA)', _num(100 * lac / max(cortex, 1), 1), '% of cortex',
         f'{int(rep.get("lacunae_count", 0))} lacunae'],
        ['Total xylem vessel area (XVA)', _num(sum(v['reg'] for v in vessels) * ar, 0), unit_a,
         'after elliptical regularisation'],
        ['Section tilt', _num(R.major_axis_tilt_deg(ell), 1), '°', 'direction of the anchor ellipse\'s major axis'],
        ['Anchor aspect ratio', _num(max(ell[2], ell[3]) / min(ell[2], ell[3]), 3), '', 'a / b'],
    ]
    bound_rows = []
    for key, name, how, _ in BOUNDARIES:
        ci = b.get(f'{key}_ci') if key != 'pith' else b['pith_range']
        lo, hi = (ci if ci is not None and np.all(np.isfinite(ci)) else (None, None))
        bound_rows.append([name, _num(b[key]), _num(lo), _num(hi), _num(b[key] * r_px * lin, 1), how])
    census_rows = []
    for z, lab in zip(ZONES, ZONE_LABELS):
        c = census[z]
        mean_area = float(np.mean(areas[z])) * ar if areas[z] else None
        dens = c['total'] / (zone_area[z] * ar * 1e-6) if px and zone_area[z] else None
        census_rows.append([lab, c['observed'], c['imputed'], c['total'], _num(mean_area, 1),
                            _num(zone_area[z] * ar, 0), _num(100 * zone_area[z] / max(sec_area, 1), 1),
                            _num(dens, 0)])
    census_rows.append(['Total', obs_total, imp_total, est_total, None, _num(sec_area * ar, 0), 100.0, None])
    vessel_rows = [[i + 1, _num(v['raw'] * ar, 0), _num(v['reg'] * ar, 0),
                    _num(2 * np.sqrt(v['reg'] / np.pi) * lin, 1), _num(v['major'] * lin, 1),
                    _num(v['minor'] * lin, 1)] for i, v in enumerate(vessels)]
    geom_rows = [
        ['Stele centre x', _num(ell[0] / st['scale'], 1), 'px'],
        ['Stele centre y', _num(ell[1] / st['scale'], 1), 'px'],
        ['Anchor semi-axis a', _num(ell[2] * lin, 1), unit_l], ['Anchor semi-axis b', _num(ell[3] * lin, 1), unit_l],
        ['ρ unit (mean anchor radius)', _num(r_px * lin, 1), unit_l],
        ['Section equivalent diameter', _num(2 * np.sqrt(sec_area / np.pi) * lin, 1), unit_l],
        ['Endodermis cell length (median)', _num(float(rep.get('endo_cell_length_measured', 0)) * lin, 1), unit_l],
        ['Endodermis thickness (one cell)', _num(b['endo_cell_rho'] * r_px * lin, 1), unit_l],
        ['Rhizodermis thickness (one cell)', _num(b['rhizo_layer_px'] * lin, 1), unit_l],
        ['Pixel size', _num(px, 4), 'µm / px'],
        ['Analysis scale', _num(st['scale'], 3), '× upload'],
    ]
    note_unit = '' if px else ' Set the pixel size to get micrometres.'
    return [
        {'id': 'summary', 'title': 'Summary', 'columns': ['Metric', 'Value', 'Unit', 'Detail'],
         'rows': summary_rows, 'note': 'Headline phenotypes of the section.' + note_unit},
        {'id': 'boundaries', 'title': 'Tissue boundaries',
         'columns': ['Boundary', 'ρ', '95 % low', '95 % high', f'Mean radius ({unit_l})', 'How it is measured'],
         'rows': bound_rows,
         'note': 'ρ = 1 on the outer edge of the metaxylem ring. Change points carry a bootstrap 95 % interval '
                 'over 16 angular sectors; the pith range spans the six vessels.'},
        {'id': 'census', 'title': 'Cell census by tissue',
         'columns': ['Tissue', 'Observed', 'Imputed', 'Estimated total', f'Mean cell area ({unit_a})',
                     f'Zone area ({unit_a})', 'Share of section (%)', 'Density (cells/mm²)'],
         'rows': census_rows,
         'note': 'Each cell owns a territory (lumen grown by a quarter of a cell diameter); the cell density of '
                 'the territories is applied to the uncovered part of the zone. Uncovered cortex regions larger '
                 'than three cells are aerenchyma. Endodermis total = perimeter / median cell length.' + note_unit},
        {'id': 'metaxylem', 'title': 'Metaxylem vessels',
         'columns': ['Vessel', f'Raw area ({unit_a})', f'Regularised area ({unit_a})',
                     f'Equivalent diameter ({unit_l})', f'Major axis ({unit_l})', f'Minor axis ({unit_l})'],
         'rows': vessel_rows, 'note': 'Raw = inside the lumen edge, placed at half height of the lumen-to-wall intensity drop; '
                         'regularised = ellipse fitted to that edge (removes notches).'},
        {'id': 'geometry', 'title': 'Section geometry', 'columns': ['Quantity', 'Value', 'Unit'],
         'rows': geom_rows,
         'note': 'Images are resampled so the root spans 766 px before analysis (resolution independence); '
                 'every value here is converted back to the uploaded image.'},
    ]


# --------------------------------------------------------------------------- entry points

def analyze(image_path, pixel_size_um=None, n_boot=R.N_BOOT, progress=None, walled_lacunae=True):
    """Full analysis of one image; see the module docstring for the result layout."""
    pixel_size_um = float(pixel_size_um) if pixel_size_um else None
    if pixel_size_um is not None and not 0 < pixel_size_um < 1000:
        raise AnalysisError('The pixel size must be a positive number of micrometres per pixel.')
    st = run_pipeline(image_path, pixel_size_um, n_boot, progress, walled_lacunae=bool(walled_lacunae))
    _report(STAGES[3], 0.0, progress)
    census = _census_territory(st)
    zone_area = {z: float(np.count_nonzero(st['masks'][m])) for z, m in zip(ZONES, ZONE_MASKS)}
    areas = _cell_areas(st['labels'], st['masks'], st['mx'])
    unit, factor = ('µm²', pixel_size_um ** 2) if pixel_size_um else ('px²', 1.0)
    charts = [
        {'id': 'profiles', 'title': 'Radial profiles and boundaries',
         'caption': 'Wall density and stereological cell sizes along ρ; vertical lines are the measured '
                    'boundaries, shaded bands their 95 % interval.', 'png': _chart_profiles(st)},
        {'id': 'counts', 'title': 'Cell census', 'caption': 'Observed and imputed cells per tissue.',
         'png': _chart_counts(census)},
        {'id': 'areas', 'title': 'Cell size by tissue', 'caption': 'Distribution of segmented lumen areas.',
         'png': _chart_areas(areas, unit, factor)},
        {'id': 'composition', 'title': 'Tissue composition', 'caption': 'Share of the section area per tissue.',
         'png': _chart_composition(zone_area)},
    ]
    tables = build_tables(st, census, zone_area, areas)
    _report(STAGES[3], 1.0, progress)
    return {'images': build_images(st), 'charts': charts, 'tables': tables,
            'summary': {'cells_observed': sum(c['observed'] for c in census.values()),
                        'cells_estimated': sum(c['total'] for c in census.values()),
                        'boundaries': {k: st['bounds'][k] for k in ('pith', 'endo_inner', 'endo_outer',
                                                                    'cortex_transition', 'edge')},
                        'pixel_size_um': pixel_size_um, 'analysis_scale': st['scale']}}


def _csv(table):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(table['columns'])
    w.writerows(table['rows'])
    return buf.getvalue()


def bundle_zip(result):
    """Zip of every image, chart and table (CSV + one JSON)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for i, item in enumerate(result['images'], 1):
            z.writestr(f'images/{i:02d}_{item["id"]}.png', item['png'])
        for i, item in enumerate(result['charts'], 1):
            z.writestr(f'charts/{i:02d}_{item["id"]}.png', item['png'])
        for t in result['tables']:
            z.writestr(f'tables/{t["id"]}.csv', _csv(t))
        z.writestr('tables/metrics.json', json.dumps(
            {'summary': result['summary'], 'tables': [{k: t[k] for k in ('id', 'title', 'columns', 'rows')}
                                                     for t in result['tables']]}, indent=1, default=float))
    return buf.getvalue()


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Analyse one root cross-section and write the results zip.')
    ap.add_argument('image')
    ap.add_argument('--pixel-size', type=float, default=None, help='µm per pixel')
    ap.add_argument('--out', default='rhizofit_results.zip')
    args = ap.parse_args()
    res = analyze(args.image, args.pixel_size, progress=lambda s, f: print(f'{s}: {f:.0%}', end='\r'))
    with open(args.out, 'wb') as fh:
        fh.write(bundle_zip(res))
    print(f'\nwrote {args.out}')
