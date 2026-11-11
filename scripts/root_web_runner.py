"""RhizoFit: root cross-section analysis for the web app (runs natively and in Pyodide).

One call, `analyze(image_path, pixel_size_um)`, runs the Predictive Ellipse Zoning template,
measures the tissue boundaries on the polar unwrap (radial_zoning_lib), counts and imputes
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

import cv2
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(REPO, 'scripts'), os.path.join(REPO, 'engine'), os.path.join(REPO, 'engine', 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cell_recovery_lib as CR  # noqa: E402
import census_lib as CS  # noqa: E402
import radial_zoning_lib as R  # noqa: E402
import vn_headless as H  # noqa: E402

TEMPLATE = os.path.join(REPO, 'public', 'templates', 'root_predictive_ellipse_zoning.vn')
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
WORKING_ROOT_DIAMETER_PX = 766.0  # root size of the reference micrograph the template was tuned on
MIN_ROOT_DIAMETER_PX = 150
SCALE_TOLERANCE = 0.02            # no resampling within ±2 % of the working size
BG, PANEL, FG, MUTED, GRID = '#0f1115', '#161a20', '#e6e8eb', '#9aa3ad', '#2a3038'


class AnalysisError(RuntimeError):
    """The image could not be analysed (user-facing message)."""


# --------------------------------------------------------------------------- pipeline

def _load_template():
    with open(TEMPLATE) as f:
        return json.load(f)


def _pub_params(vn, **extra):
    node = next(n for n in vn['nodes'] if n['id'] == 'pub_fig')
    params = {k: v for k, v in node['data']['params'].items() if k not in ('color_index', 'node_note')}
    return {**params, 'zones_from_masks': True, **extra}


def _publish(vn, pipe, masks, ellipse_report, labels, pixel_size_um, mx):
    node = H.registry.NODE_CLASS_REGISTRY['draw_root_publication']()
    inputs = {'image': pipe['cells']['main'], 'labels': labels, 'boundary': pipe['section']['mask'],
              'landmarks': mx.astype(np.uint8) * 255, 'ellipse_report': ellipse_report,
              **{k: (v.astype(np.uint8) * 255) for k, v in masks.items()}}
    extra = {'pixel_size_um': pixel_size_um} if pixel_size_um else {'draw_scale_bar': False}
    out = node.process(inputs, _pub_params(vn, **extra))
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


def root_diameter_px(img):
    """Equivalent diameter (px) of the root: largest dark region on the bright backdrop, holes filled.

    Every smoothing scale is a fraction of the image size, so the estimate is proportional to
    the resolution (it is what makes the analysis resolution-independent).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (0, 0), max(gray.shape) / 200)
    _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dark)
    if n < 2:
        raise AnalysisError('No root section was found in the image.')
    root = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    cnts, _ = cv2.findContours(root, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(root)
    cv2.drawContours(filled, cnts, -1, 1, -1)
    return float(2 * np.sqrt(filled.sum() / np.pi))


def _normalised_upload(image_path, scale=None):
    """Upload resampled so the root spans WORKING_ROOT_DIAMETER_PX, as a temp PNG; returns (path, scale).

    scale = working px per original px. The template's pixel-sized settings were tuned at
    this root size, so every resolution or magnification is analysed at the same scale.
    A given `scale` is applied as is (e.g. to analyse damaged copies in the frame of the intact image).
    """
    img = _read_bgr(image_path)
    if scale is not None:
        if scale != 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        fd, out = tempfile.mkstemp(suffix='.png', prefix='root_upload_')
        os.close(fd)
        cv2.imwrite(out, img)
        return out, float(scale)
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
    return out, scale


def run_pipeline(image_path, pixel_size_um=None, n_boot=R.N_BOOT, progress=None, scale=None, walled_lacunae=False):
    """Template + measured boundaries + census. Returns the raw state used by the figures.

    `walled_lacunae` (experimental, off by default): also recognise aerenchyma lacunae enclosed by
    intact walls, which the first segmentation outlines as cells (cell_recovery_lib.remove_walled_lacunae).

    Lengths inside the state are in working pixels; `scale` converts them back to the upload.
    """
    image_path, scale = _normalised_upload(image_path, scale)
    work_pixel_um = pixel_size_um / scale if pixel_size_um else None
    H.load_plugins()
    vn = _load_template()
    try:
        pipe = H.run(vn, {'src': {'path': image_path}},
                     on_node=lambda i, n, _nid: _report(STAGES[0], i / n, progress))
    finally:
        os.remove(image_path)
    section = np.asarray(pipe['section'].get('mask') if pipe['section'].get('mask') is not None else 0) > 0
    if not section.any():
        raise AnalysisError('No root section was found in the image.')
    mx = pipe['metaxylem'].get('mask')
    mx = R.clean_vessels(mx) if mx is not None else None
    if mx is None or not mx.any():
        raise AnalysisError('No metaxylem ring was detected: the method needs at least 5 large vessels.')
    _report(STAGES[1], 0.0, progress)
    gray = cv2.cvtColor(pipe['src']['main'], cv2.COLOR_BGR2GRAY)
    try:
        bounds, masks, ell, prof = R.measure_boundaries(gray, section, mx, n_boot=n_boot)
    except ValueError as exc:
        raise AnalysisError(f'Tissue boundaries could not be measured ({exc}).') from exc
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
                                                           bounds['px_per_rho'])
        labels, _ = CR.drop_fragments(labels, rho, cortex, expected)
        recovered &= labels > 0
    except ValueError:  # no segmented cortex cell to calibrate on: keep the first pass
        recovered, n_recovered = np.zeros_like(section), 0
    pub = _publish(vn, pipe, masks, ellipse_report, labels, work_pixel_um, mx)
    cortex_outer = bounds['edge'] - bounds['rhizo_layer_px'] / bounds['px_per_rho']
    try:
        cell_files = R.cortical_cell_files(labels, section, ell, bounds['endo_outer'], cortex_outer)
    except ValueError:
        cell_files = None
    return {'pipe': pipe, 'gray': gray, 'section': section, 'mx': mx, 'bounds': bounds,
            'masks': masks, 'ell': ell, 'prof': prof, 'labels': labels, 'pub': pub,
            'recovered': recovered, 'n_recovered': n_recovered, 'cell_files': cell_files, 'n_split': n_split, 'n_filled': n_filled,
            'n_walled_lacunae': n_walled if walled_lacunae else None,
            'report': pub['predictive_report'], 'pixel_size_um': pixel_size_um, 'scale': scale,
            'rho': rho}


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
    """Census by territory density (census_lib); the endodermis keeps its perimeter estimate."""
    rep = st['report']
    out = {}
    for z, mname in zip(ZONES, ZONE_MASKS):
        k_unit = REPORT_KEYS[z][3]
        unit = float(rep[k_unit]) if k_unit and k_unit in rep else None
        if z == 'endo':
            obs, tot = int(rep.get('endo_cells_observed', 0)), int(rep.get('endo_cells_total_pred', 0))
        else:
            obs, tot, _ = CS.zone_census(st['labels'], st['masks'][mname], st['mx'],
                                         keep_lacunae=z in ('inner_cortex', 'outer_cortex'))
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


def _metaxylem_vessels(mx):
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mx.astype(np.uint8))
    rows = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < R.MIN_VESSEL_AREA:
            continue
        cnts, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        (_, _), (w, h), _ = cv2.fitEllipse(cnts[0])
        rows.append({'raw': float(stats[i, cv2.CC_STAT_AREA]), 'reg': float(np.pi * w * h / 4),
                     'major': float(max(w, h)), 'minor': float(min(w, h))})
    return rows


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
    vessels = _metaxylem_vessels(st['mx'])
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
         'wall-enclosed radial sectors over 3 expected cells and 3 layers deep, counted as aerenchyma'
         if st.get('n_walled_lacunae') is not None else 'detection off (experimental option)'],
        ['Section area', _num(sec_area * ar, 0), unit_a, ''],
        ['Stele share of the section', _num(100 * stele / max(sec_area, 1), 1), '%', 'pith + vascular + endodermis'],
        ['Cortex share of the section', _num(100 * cortex / max(sec_area, 1), 1), '%', 'inner + outer cortex'],
        ['Cortical cell files (CF)', _num(st['cell_files'][0], 1) if st['cell_files'] else None, 'files',
         (f'median over rays from the endodermis to the rhizodermis, interquartile '
          f'{st["cell_files"][1]:.0f}-{st["cell_files"][2]:.0f}') if st['cell_files'] else 'no complete ray'],
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
         'rows': vessel_rows, 'note': 'Regularised = ellipse fitted to the lumen (removes notches).'},
        {'id': 'geometry', 'title': 'Section geometry', 'columns': ['Quantity', 'Value', 'Unit'],
         'rows': geom_rows,
         'note': 'Images are resampled so the root spans 766 px before analysis (resolution independence); '
                 'every value here is converted back to the uploaded image.'},
    ]


# --------------------------------------------------------------------------- entry points

def analyze(image_path, pixel_size_um=None, n_boot=R.N_BOOT, progress=None, walled_lacunae=False):
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
