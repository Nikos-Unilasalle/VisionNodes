"""
sci_ensemble_stats.py — Monte-Carlo ensemble statistics of a binary mask.

Why this node exists
--------------------
For an ensemble whose per-realisation outcome is BINARY and whose realisations are
i.i.d., the per-pixel standard deviation is an identity, not a measurement::

    count_per_pixel ~ Binomial(N, P)   =>   sigma_P = sqrt(P*(1-P))

So a per-pixel std map (Frame Accumulator in Running Std mode) carries no information
beyond the mean map `P` itself, whatever the perturbation model looks like — spatial
correlation included, since correlation changes the covariance BETWEEN pixels while
leaving each pixel's marginal Bernoulli.

The informative quantities are per-realisation AGGREGATES. Their ensemble spread does
depend on the spatial structure of the perturbation, because correlated errors do not
cancel in a sum: for a fixed marginal probability field, the ensemble sd of total area
is several times larger under spatially correlated noise than under i.i.d. noise.

This node therefore accumulates, one value per realisation:

  * `area`            — mask pixel count (the headline quantity for extent products)
  * `perimeter`       — boundary pixel count (shape complexity / raggedness)
  * `components`      — number of connected components  (optional, `components`)
  * `largest`         — pixel count of the biggest component (optional, `components`)
  * `centroid_x/y`    — mask centroid, in pixels (positional stability)
  * `boundary_dist`   — mean distance from this realisation's boundary to a reference
                        boundary (optional, `boundary`, needs the `reference` input)

and reports, per metric, mean / sd / CV / percentile CI / min / max, plus a histogram
figure. Domain-agnostic: any mask ensemble (segmentation, thresholded detection, change
map) works, not just surface water.

Pair it with a Frame Accumulator in Running Mean mode (which gives `P`) on the same
mask stream; this node answers "how uncertain is the derived quantity", which the mean
map cannot.
"""
from __future__ import annotations

import io

import cv2
import numpy as np

from registry import vision_node, NodeProcessor

_CI_DEFAULT = 95.0
_FIG_DPI = 110
_FIG_BG = '#161616'
_FIG_FG = '#e6e6e6'
_HIST_BINS = 24
_FIG_EVERY_DEFAULT = 10   # re-render the histograms every K realisations, not every tick
_MAX_PANELS = 4          # histogram panels drawn per row
_FALLBACK_SIZE = (320, 900)

# Metric key -> human label, in display order.
_LABELS = {
    'area':          'Area (px)',
    'perimeter':     'Perimeter (px)',
    'components':    'Components',
    'largest':       'Largest component (px)',
    'centroid_x':    'Centroid x (px)',
    'centroid_y':    'Centroid y (px)',
    'boundary_dist': 'Boundary dist. to ref (px)',
}


@vision_node(
    type_id='sci_ensemble_stats',
    label='Ensemble Statistics',
    category='measure',
    icon='Sigma',
    description=(
        "Monte-Carlo ensemble statistics of a binary mask: accumulates ONE value per "
        "realisation (area, perimeter, connected components, largest component, "
        "centroid, boundary distance to a reference) and reports mean / sd / CV / "
        "percentile CI / min / max per metric, with histograms.\n\n"
        "Use this instead of a per-pixel std map. For a binary outcome with i.i.d. "
        "realisations the per-pixel std is exactly sqrt(P(1-P)) — a deterministic "
        "function of the mean map, carrying no extra information. Aggregate quantities "
        "DO carry information: their ensemble spread reflects the spatial structure of "
        "the perturbation, because correlated errors fail to cancel in a sum."
    ),
    inputs=[
        {'id': 'mask',      'color': 'mask',   'label': 'Realisation mask'},
        {'id': 'tick',      'color': 'scalar', 'label': 'Upstream tick (auto-reset on 0)'},
        {'id': 'reference', 'color': 'mask',   'label': 'Reference mask (boundary dist.)'},
    ],
    outputs=[
        {'id': 'main',        'color': 'image',  'label': 'Histograms'},
        {'id': 'stats',       'color': 'dict',   'label': 'Per-metric ensemble stats'},
        {'id': 'area_mean',   'color': 'scalar', 'label': 'Mean area (px)'},
        {'id': 'area_sd',     'color': 'scalar', 'label': 'Ensemble sd of area (px)'},
        {'id': 'area_cv',     'color': 'scalar', 'label': 'Coefficient of variation'},
        {'id': 'frame_count', 'color': 'scalar', 'label': 'Realisations accumulated'},
        {'id': 'done',        'color': 'scalar', 'label': 'Reached Target N (0/1)'},
    ],
    params=[
        {'id': 'target_n', 'label': 'Target N (0 = unlimited)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 1_000_000, 'step': 1},
        {'id': 'ci', 'label': 'CI (%)', 'type': 'float',
         'default': _CI_DEFAULT, 'min': 50.0, 'max': 99.9, 'step': 0.5},
        {'id': 'fig_every', 'label': 'Redraw histograms every N realisations', 'type': 'int',
         'default': _FIG_EVERY_DEFAULT, 'min': 1, 'max': 1000, 'step': 1},
        {'id': 'components', 'label': 'Connected components (slower)', 'type': 'bool',
         'default': True},
        {'id': 'boundary', 'label': 'Boundary distance to reference', 'type': 'bool',
         'default': False},
        {'id': 'reset', 'label': '↺ Reset Ensemble', 'type': 'trigger', 'default': 0},
        {'id': 'node_note', 'label': 'Note', 'type': 'string', 'default': ''},
    ],
    resizable=True, min_width=260, min_height=180,
)
class EnsembleStatsNode(NodeProcessor):
    """Per-realisation aggregate accumulator.

    Memory is O(N · metrics): one float per metric per realisation, not one frame, so a
    few hundred realisations over a full scene stay negligible. The stored series is
    what makes percentile CIs and histograms possible — a streaming moment accumulator
    could not produce either.
    """

    def __init__(self):
        super().__init__()
        self._series: dict[str, list[float]] = {}
        self._count = 0
        self._shape: tuple[int, int] | None = None
        self._last_reset = 0.0
        self._last_tick: float | None = None
        self._fig: np.ndarray | None = None       # cached histogram render
        self._fig_at = 0                          # realisation count of that render

    # ---- state ---------------------------------------------------------------

    def _reset_state(self) -> None:
        self._series = {}
        self._count = 0
        self._shape = None
        self._fig = None
        self._fig_at = 0

    @staticmethod
    def _to_binary(mask: np.ndarray) -> np.ndarray:
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        return (mask > 127).astype(np.uint8)

    @staticmethod
    def _boundary(binary: np.ndarray) -> np.ndarray:
        """Inner boundary ring, via morphological erosion."""
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        return binary - cv2.erode(binary, kernel, iterations=1)

    # ---- per-realisation measurement ----------------------------------------

    def _measure(self, binary: np.ndarray, reference: np.ndarray | None,
                 want_components: bool, want_boundary: bool) -> dict[str, float]:
        area = float(binary.sum())
        edge = self._boundary(binary)
        out: dict[str, float] = {'area': area, 'perimeter': float(edge.sum())}

        if want_components:
            n_labels, labels = cv2.connectedComponents(binary, connectivity=8)
            # label 0 is background; an empty mask yields a single background label
            counts = np.bincount(labels.ravel())[1:] if n_labels > 1 else np.array([])
            out['components'] = float(counts.size)
            out['largest'] = float(counts.max()) if counts.size else 0.0

        if area > 0:
            ys, xs = np.nonzero(binary)
            out['centroid_x'] = float(xs.mean())
            out['centroid_y'] = float(ys.mean())

        if want_boundary and reference is not None:
            ref_edge = self._boundary(reference)
            if ref_edge.any() and edge.any():
                # Distance from every pixel to the nearest reference-boundary pixel,
                # sampled on this realisation's own boundary.
                dist = cv2.distanceTransform((1 - ref_edge).astype(np.uint8),
                                             cv2.DIST_L2, 3)
                out['boundary_dist'] = float(dist[edge > 0].mean())

        return out

    # ---- ensemble summary ----------------------------------------------------

    @staticmethod
    def _summarise(values: list[float], ci: float) -> dict[str, float | int]:
        arr = np.asarray(values, dtype=np.float64)
        mean = float(arr.mean())
        sd = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        half = (100.0 - ci) / 2.0
        return {
            'n': int(arr.size),
            'mean': round(mean, 4),
            'sd': round(sd, 4),
            'cv': round(sd / abs(mean), 5) if mean else 0.0,
            'ci_lo': round(float(np.percentile(arr, half)), 4),
            'ci_hi': round(float(np.percentile(arr, 100.0 - half)), 4),
            'min': round(float(arr.min()), 4),
            'max': round(float(arr.max()), 4),
        }

    # ---- figure -------------------------------------------------------------

    def _render(self, stats: dict[str, dict], ci: float) -> np.ndarray:
        keys = [k for k in _LABELS if k in stats]
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            cols = min(len(keys), _MAX_PANELS) or 1
            rows = max((len(keys) + cols - 1) // cols, 1)
            fig, axes = plt.subplots(rows, cols, figsize=(3.4 * cols, 2.7 * rows),
                                     dpi=_FIG_DPI, facecolor=_FIG_BG, squeeze=False)
            for ax, key in zip(axes.ravel(), keys):
                s = stats[key]
                ax.hist(self._series[key], bins=_HIST_BINS, color='#4da3ff', alpha=0.85)
                ax.axvline(s['mean'], color='#ffb454', lw=1.4, label=f"mean {s['mean']:.4g}")
                ax.axvline(s['ci_lo'], color=_FIG_FG, lw=0.9, ls='--')
                ax.axvline(s['ci_hi'], color=_FIG_FG, lw=0.9, ls='--',
                           label=f"{ci:g}% CI")
                ax.set_title(f"{_LABELS[key]}\nsd={s['sd']:.4g}  CV={s['cv']:.4g}",
                             fontsize=8, color=_FIG_FG)
                ax.tick_params(colors=_FIG_FG, labelsize=7)
                ax.set_facecolor(_FIG_BG)
                for spine in ax.spines.values():
                    spine.set_color('#555555')
                ax.legend(fontsize=6, facecolor=_FIG_BG, labelcolor=_FIG_FG,
                          edgecolor='#555555')
            for ax in axes.ravel()[len(keys):]:
                ax.axis('off')
            fig.suptitle(f'Monte-Carlo ensemble statistics — N = {self._count}',
                         fontsize=10, color=_FIG_FG)
            fig.tight_layout(rect=[0, 0, 1, 0.94])

            buf = io.BytesIO()
            fig.savefig(buf, format='png', facecolor=_FIG_BG, dpi=_FIG_DPI)
            buf.seek(0)
            arr = np.frombuffer(buf.read(), dtype=np.uint8)
            buf.close()
            plt.close(fig)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError('imdecode returned None')
            return img
        except Exception as exc:                          # matplotlib absent or broken
            img = np.zeros((*_FALLBACK_SIZE, 3), np.uint8)
            cv2.putText(img, f'figure unavailable: {exc}'[:70], (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            for i, key in enumerate(keys):
                s = stats[key]
                cv2.putText(img, f"{key}: mean={s['mean']:.4g} sd={s['sd']:.4g}",
                            (10, 80 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                            (180, 220, 255), 1)
            return img

    # ---- engine entry point -------------------------------------------------

    def _empty(self) -> dict:
        return {'main': None, 'stats': {}, 'area_mean': 0.0, 'area_sd': 0.0,
                'area_cv': 0.0, 'frame_count': self._count, 'done': 0.0}

    def process(self, inputs, params):
        # Edge-triggered reset button.
        do_reset = float(params.get('reset', 0) or 0)
        if do_reset > 0.5 and self._last_reset <= 0.5:
            self._reset_state()
        self._last_reset = do_reset

        # Auto-reset when the upstream Monte-Carlo driver restarts (its tick drops).
        tick = inputs.get('tick')
        if tick is not None:
            tick = float(tick)
            if self._last_tick is not None and tick < self._last_tick:
                self._reset_state()
            self._last_tick = tick

        mask = inputs.get('mask')
        if mask is None:
            return self._empty() if not self._count else self._report(params)

        binary = self._to_binary(mask)

        # A resolution change makes previously accumulated areas incomparable.
        if self._shape is not None and binary.shape != self._shape:
            self._reset_state()
        self._shape = binary.shape

        target_n = int(params.get('target_n', 0) or 0)
        reached = target_n > 0 and self._count >= target_n
        if not reached:
            reference = inputs.get('reference')
            ref_bin = self._to_binary(reference) if reference is not None else None
            if ref_bin is not None and ref_bin.shape != binary.shape:
                ref_bin = None                       # never compare across grids
            measured = self._measure(
                binary, ref_bin,
                bool(params.get('components', True)),
                bool(params.get('boundary', False)),
            )
            # Immutable-style update: rebuild the series dict rather than mutating in place.
            self._series = {k: [*self._series.get(k, []), v] for k, v in measured.items()}
            self._count += 1
            reached = target_n > 0 and self._count >= target_n

        return self._report(params, reached)

    def _report(self, params, reached: bool = False) -> dict:
        if not self._count or not self._series:
            return self._empty()

        ci = float(params.get('ci', _CI_DEFAULT))
        stats = {k: self._summarise(v, ci) for k, v in self._series.items()}
        area = stats.get('area', {'mean': 0.0, 'sd': 0.0, 'cv': 0.0})

        # Rendering a matplotlib figure costs ~0.4 s; doing it on every tick would
        # dominate a several-hundred-realisation run. Redraw on a stride, on the first
        # realisation, and once the target is reached — serve the cache otherwise.
        every = max(int(params.get('fig_every', _FIG_EVERY_DEFAULT) or 1), 1)
        if (self._fig is None or reached
                or self._count - self._fig_at >= every):
            self._fig = self._render(stats, ci)
            self._fig_at = self._count

        return {
            'main':        self._fig,
            'stats':       stats,
            'area_mean':   float(area['mean']),
            'area_sd':     float(area['sd']),
            'area_cv':     float(area['cv']),
            'frame_count': self._count,
            'done':        1.0 if reached else 0.0,
        }
