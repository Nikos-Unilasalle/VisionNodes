# MC-paper — Known Weaknesses, Bugs and Review Exposure

Adversarial audit of the executable graph `MC-paper.vn` and the underlying VNStudio
plugin code. Written as a pre-submission checklist: every item is something a reviewer
can raise, ordered by how much of the paper it invalidates.

Companion document: `MC-paper-methods.md` (approach & protocol).

**Status 2026-09-15:**
- **BLOCKER 1 — fixed.** Accumulator patched (unnormalised σ + `scale` output, rounding
  instead of truncation), graph rewired, 10/10 tests green, no regressions.
- **BLOCKER 3 — proved, and framing option (a) adopted.** The per-pixel σ map is
  `√(P(1−P))` by identity. Replacement product built: new `sci_ensemble_stats` plugin
  (15/15 tests green) accumulating per-realisation aggregates, wired into the graph.
  Headline result becomes the ×8 gap in water-area uncertainty between i.i.d. and
  spatially correlated error models.
- **Step 5 — done.** The aggregate-uncertainty result is now measured on the real
  acquisition, not just synthetically: `sd(area)` = 72 / 117 / 254 / 577 px at
  0 / 1 / 3 / 10 px noise correlation, at a constant mean. **A units bug found on the way
  (optical bands were dB-transformed) had been making the Monte-Carlo inject essentially
  no noise** — see the note at the end of BLOCKER 3.
- **BLOCKER 2 — resolved.** Estimand fixed to a single Sentinel-2 acquisition
  (**2021-09-02 10:57:29 UTC**, tile 31UDQ, one image, 0.00 % AOI cloud, 100 % coverage —
  a 1-day window means no mosaicking at all). Year 2021 chosen so that **both** references
  align temporally. New `geo_gsw_monthly` plugin (16/16 tests) supplies a dated reference;
  new `ref_agree` node measures the validation ceiling. **Partial correction to this
  item's original severity: see below — for this AOI the temporal mismatch costs ~2.6 % of
  water area, not 28 %. The dominant reference limitation is spatial, and that finding
  replaces it as a constraint on the paper.**

Legend — **BLOCKER**: a published figure or claim is currently wrong.
**SERIOUS**: defensible only with extra experiments or a weaker claim.
**MINOR**: hygiene; fix before submission but nothing collapses.

---

## BLOCKER 1 — `acc_std` outputs a max-normalised std, not σ_P  ✅ FIXED

**Location:** `engine/plugins/sci_frame_accumulator.py`, cumulative mode 3
(*Running Std*).

```python
s = np.sqrt(self._m2 / max(self._count, 1))
m = float(s.max())
result = (s / (m + 1e-8) * 255) if m > 0 else s
```

The node emits `255 · σ / σ_max`, i.e. a **relative, scene-normalised** std map.
Downstream, `mc_conv` and `mc_cal` both divide by 255 and treat the result as σ in
probability units.

Let σ be the true per-pixel ensemble std of `P` (units of probability, range [0, 0.5]).
What the consumers actually see is:

```
σ_reported = σ_true / σ_max          (dimensionless ratio, max = 1 by construction)
SE_reported = ⟨σ_true⟩ / (σ_max · √N) = SE_true / σ_max
```

### Consequences

1. **The convergence figure (§5.7 of the methods) measures nothing.**
   The map is re-normalised so that its maximum equals exactly 255 **on every tick**.
   The scene maximum is therefore pinned for the whole run, and it cannot decrease as
   `N` grows. `SE(N)` then falls off as `1/√N` *by arithmetic construction*, regardless
   of whether the ensemble has converged. The curve is a plot of `⟨σ/σ_max⟩ / √N` — the
   numerator is a constant-ish shape factor — so it cannot fail to look like
   convergence.

2. **The stopping criterion depends on an uncontrolled quantity.**
   - If some pixel sits near `P = 0.5`, then `σ_max ≈ 0.5` and `SE` is inflated ≈ 2×;
     the wired tolerance `0.005` behaves like a true tolerance of `0.0025`
     (conservative — more realisations than needed, but not misleading).
   - If `P` is quasi-binary (the regime actually observed), `σ_max` can be small, e.g.
     `0.05` → `SE` inflated **≈ 20×** → `SE < tol` is never satisfied → the node returns
     `optimal_N = -1` and the run simply stops at `max_ticks`.

   So whether a convergence criterion exists at all is a function of `σ_max`, which is
   never reported.

3. **⟨U⟩ in `mc_cal` is not an uncertainty.**
   ```python
   sig = (d[..., 0] if d.ndim == 3 else d).astype(np.float64)
   if sig.max() > 1.5: sig = sig / 255.0
   U = float(np.mean(sig[m])); U_src = 'ensemble_std'
   ```
   The normalised map always has `max == 255`, so the branch always fires and
   `⟨U⟩ = mean(σ / σ_max)` — a dimensionless relative quantity. It is **not comparable
   across scenes, across runs, or against the `bernoulli_var` fallback
   `P(1−P)`** that the same node substitutes when the input is absent. The two code
   paths report quantities in different units under the same label.

4. **σ_true is unrecoverable downstream.** `σ_max` is destroyed by the 8-bit
   normalisation, so no consumer node can undo it. This must be fixed in the plugin.

### Fix applied

`engine/plugins/sci_frame_accumulator.py`:

- new param **`normalize`** (bool, default `True` for backwards compatibility,
  `show_if mode == 3`) — when off, Running Std emits σ directly in input units
- new output **`scale`** (scalar) on *every* mode = the input-unit value that `main == 255`
  represents, so the recovery is uniform and the legacy normalisation is no longer
  destructive: `value_in_input_units = main / 255 * scale`, hence
  `σ_P = main * scale / 255**2`
- rounding instead of truncation before the uint8 cast (also fixes MINOR 15)
- magic numbers extracted (`_MODE_STD`, `_U8_MAX`, `_DIFF_GAIN`, `_EPS`); std scaling
  factored into `_std_to_u8`

`MC-paper.vn`: `acc_std.normalize = false`; `acc_std.scale` wired into `mc_conv.f` and a
new `mc_cal.f` port; both scripts now recover σ_P via the documented formula and print a
loud warning if `scale` is absent. `mc_cal`'s fallback changed from `P(1−P)` (a variance)
to `√(P(1−P))` (a std) so both branches report the same quantity in the same units.

Verification: 10/10 tests in `engine/tests/test_sci_frame_accumulator.py` (5 new,
written first and confirmed RED), `test_water_mc_pipeline.py` 3/3, full engine suite
465 passed with the same 8 pre-existing unrelated failures as before the patch
(`test_logic_python`, `test_geo_copernicus_marine`, `test_geo_netcdf_reader`).
End-to-end check on a synthetic ensemble confirms `mean_sigma_P` recovers the analytic
value. Backup of the original graph at `MC-paper.vn.bak`.

### Until fixed, retract

- the Monte-Carlo convergence figure and the `optimal_N` value
- the reported `mean_uncertainty` / ⟨U⟩
- any sentence of the form "σ_P peaks at …" or "mean uncertainty is …"
- the uncertainty-map figure's colourbar (the image itself is fine as a *relative*
  display; the scale is not absolute)

---

## BLOCKER 2 — The estimand is undefined  ✅ RESOLVED

`geo_copernicus` is wired with `mosaic_mode = 0` = **SIMPLE**, which uses
`mosaicking_order = leastCC`: the composite takes, per pixel, the **least-cloudy
acquisition** over `2024-01-01 → 2024-06-01`. Adjacent pixels can come from different
dates months apart.

The ground truth is **ESA WorldCover 2021, class 80 = permanent water bodies**.

So the study compares:

| | |
|---|---|
| Prediction | water extent of a 5-month, per-pixel least-cloud composite, 2024 |
| Reference | permanent water, 2021, from a classified product |

There is no instant in time whose water extent this pair describes. Specific failures:

- **Seasonal water** correctly detected by the pipeline is scored as a false positive,
  because the reference encodes permanence, not presence.
- **Tidal modulation** makes this severe for the Yellow River delta AOI (the alternate
  bbox stored in the node): intertidal flats change class within hours, and the
  composite mixes tide states pixel-by-pixel.
- **Three-year offset** between reference and imagery, over a river corridor with active
  channel migration and construction.
- Boundary-F1 at 3 px tolerance is being computed against a shoreline that does not
  correspond to any single acquisition.

### Required fix

Pick one:

1. **Single-date scene.** One acquisition, ideally near-cloud-free, with the exact date
   reported. Reference annotated or selected for that date.
2. **Defined composite with a matched reference.** A median composite over a short
   window, with a reference derived from JRC GSW *monthly* history for the same window,
   and explicit occurrence-threshold semantics.

Option 1 is strongly preferable for a methods paper: it removes a whole class of
objections at the cost of one figure's worth of scene selection.

### Resolution — single acquisition, 2021, both references aligned

**Estimand:** water extent over the Seine corridor at the instant of one Sentinel-2
acquisition.

A 1-day CDSE window over this AOI returns **exactly one image**, so the mosaicking problem
disappears rather than being mitigated. Verified against GEE:

| Date | Images | Sensing time (UTC) | Tile | AOI cloud | AOI coverage |
|---|---|---|---|---|---|
| **2021-09-02** | **1** | **10:57:29** | 31UDQ | **0.00 %** | **100 %** |
| 2021-06-14 | 1 | 10:57:28 | 31UDQ | 0.01 % | 100 % |
| 2021-03-01 | 1 | 10:57:27 | 31UDQ | 0.03 % | 100 % |

All three share orbit 51 and tile 31UDQ, so they are directly comparable — 2021-06-14 and
2021-03-01 become the out-of-sample dates for SERIOUS 7 at no extra cost.

**Why 2021 and not 2024.** JRC GSW MonthlyHistory — the only readily available *dated*
water reference — ends at **2021-12**. ESA WorldCover v200 is the **2021** epoch. Moving
the scene into 2021 therefore aligns *both* references at once, instead of trading one
mismatch for another. 2021-09 also sits at Seine low flow, the most hydrologically stable
part of the year, so a monthly reference best approximates an instant.

GSW MonthlyHistory coverage was checked before committing to the date — several months are
unusable because Landsat never observed them:

| Month | Valid observations | Water |
|---|---|---|
| 2021-02 | **0.00 %** | — |
| 2021-03 | 96.50 % | 2.40 % |
| 2021-06 | 99.96 % | 2.18 % |
| 2021-07 | **1.20 %** | — |
| **2021-09** | **99.59 %** | **2.37 %** |
| 2021-12 | **0.00 %** | — |

2021-09 has near-complete coverage. Had the date been chosen from cloud statistics alone,
2021-02 or 2021-12 would have produced an entirely empty reference.

### Correction: the temporal mismatch was not the dominant problem here

Measured by the `ref_agree` node **inside the pipeline**, on the grid the loader actually
delivers (2464 × 1564 px), over the pixels GSW observed:

| | whole scene | corridor domain (as wired) |
|---|---|---|
| pixels evaluated | 3 837 487 | 333 352 |
| WorldCover 2021 class 80 (10 m, annual, permanent) | 116 839 px | 113 799 px |
| GSW MonthlyHistory 2021-09 (30 m, dated) | 90 115 px | 89 013 px |
| **IoU between the two references** | **0.7177** | **0.7308** |
| disagreement, share of union | 28.2 % | 26.9 % |
| in WorldCover only | 30 370 px | 28 165 px |
| in GSW only | 3 646 px | 3 379 px |

Decomposing the gap:

| Diagnostic | whole scene | corridor |
|---|---|---|
| IoU after dilating GSW by 10 m | **0.7929** (peak) | **0.8068** (peak) |
| … by 20 / 30 / 40 / 50 m | 0.784 / 0.726 / 0.652 / 0.587 | 0.798 / 0.740 / 0.667 / 0.602 |
| GSW core (eroded 30 m) inside WorldCover | **0.9960** | **0.9960** |
| WorldCover core (eroded 30 m) inside GSW | **0.9741** | **0.9742** |

The interiors agree to 97.4–99.6 %, and the core figures are identical to four decimals in
both domains — interior agreement is a property of the products, not of the evaluation
window. **The disagreement is almost entirely boundary placement caused by GSW's 30 m
sampling**, not seasonality: only ~2.6 % of WorldCover's core is absent from the dated
reference. My original framing of this item overstated the temporal risk *for this AOI* —
the Seine near Paris is a regulated, largely permanent river, so an annual permanent-water
reference is close to correct. (It would have been severe for the tidal Yellow River delta
AOI, which is precisely why that was the riskier choice.)

### What replaces it as a constraint

**A 30 m reference cannot validate a 10 m boundary claim.** The paper's finest metric is
boundary-F1 at 3 px (= 30 m), i.e. exactly the scale at which the dated reference is
itself uncertain. So:

- **Primary reference: WorldCover 10 m** — spatially matched; its temporal error is now
  bounded at ~2.6 % of water area by the core comparison above, which is a measured number
  rather than an assumption.
- **Secondary reference: GSW MonthlyHistory** — used to *bound reference error* and to
  support the temporal claim, **not** for boundary metrics.
- **Report IoU(WC, GSW) = 0.731 in the corridor (0.718 whole-scene) and the core
  agreements 0.996 / 0.974 as the validation ceiling.** Any metric difference smaller than that envelope is inside reference noise
  and must not be interpreted. This is now computed automatically by the `ref_agree` node
  and is a required figure.
- **For any defensible boundary claim, the scene needs manual annotation** at 10 m on the
  exact acquisition. That is now *feasible* precisely because the estimand is a single
  date — it was impossible against a 5-month composite.

### Implementation

`engine/plugins/geo_gsw_monthly.py` — "GSW Monthly Water", fetches
`JRC/GSW1_4/MonthlyHistory` onto the input raster's grid.

- **`auto_date` (default on)** derives the month from the input raster's own `_dates`
  metadata, so the reference structurally cannot drift away from the imagery. Manual
  year/month remain available.
- Outputs a **separate `valid` mask**. The source band is ternary — `0 = not observed`,
  `1 = land`, `2 = water` — and treating 0 as land silently converts missing observations
  into false negatives. Metrics must restrict their domain to `valid`.
- **Fails loudly outside 1984-03 … 2021-12** rather than returning a plausible wrong mask.
  A test asserts that 2024 imagery produces `mask = None` and a coverage message.
- Reports `valid_fraction` and warns below 90 % observed.
- 16/16 tests, written first (RED confirmed), with fake `ee` / `requests` so the suite
  needs no network or credentials. Verified against real GEE on the locked scene:
  2462 × 1501 px grid, 99.6 % observed, 88 063 water px.

`ref_agree` (new `logic_python` node) — measures IoU between two references, sweeps the
dilation of the coarser one, and compares eroded cores, so the two causes of disagreement
are separated rather than conflated. Outputs the ceiling stats and a 3-panel diagnostic.
Run inside the pipeline on the delivered grid; the numbers above are its output.

Graph: `geo_copernicus` set to `2021-09-02 → 2021-09-03`, `mosaic_mode = SIMPLE`, with the
full provenance in its node note; `gsw_gt` fed from the same imagery; `ref_agree` wired to
both references plus the GSW validity mask and the corridor domain, inside a new
"Estimand & reference error" frame. All 91 edges validated against 473 real plugin
schemas: no invalid handles. Full engine suite 498 passed, same 8 pre-existing unrelated
failures.

---

## SERIOUS 3 — σ_abs was tuned to produce the desired output property  ⚠️ PREMISE RETIRED

The noise node's own annotation reads (translated): *"Without the floor, the noise tends
to 0 over water in NIR/SWIR … plausible cause of the quasi-binary P observed."*

Read adversarially: the single parameter that drives the entire uncertainty product was
adjusted until `P` stopped being degenerate. That is fitting the input model to a desired
output property, and it undercuts every uncertainty number in the paper.

> **Update — the premise was wrong.** `P` was quasi-binary because the imagery was
> arriving `10·log10`-transformed, so an `σ_abs` expressed in reflectance units perturbed
> the signal by ~0.02 % (see BLOCKER 3's closing note). With the units fixed, 7.4 % of the
> corridor is graded without touching `σ_abs`. The note that motivated the floor was
> diagnosing a symptom of a units bug, not a property of the noise model. The *physical*
> argument for an absolute floor on dark targets still stands and should be kept — but the
> "tuned to fix quasi-binary P" charge no longer applies, and the sensitivity sweep below
> is now a normal robustness check rather than a defence.

The *physical argument* for a floor is sound and should be kept — dark-target relative
uncertainty genuinely is large, and a purely multiplicative model is wrong. The problem
is the provenance of the value `0.005`.

### Required fix

- Justify `σ_abs` from an **independent** radiometric source (L2A surface-reflectance
  validation / ACIX uncertainty budgets), cited, with the derivation shown — not from the
  appearance of `P`.
- Publish a **sensitivity sweep**: ECE, Brier, F1, `plateau_fraction`, `⟨σ_P⟩` as
  functions of `σ_abs ∈ [0.001, 0.02]`, `σ_rel ∈ [0.005, 0.05]`, and correlation length
  `∈ {0, 1, 3, 10} px`. All three are already exposed as node parameters.
- State conclusions that are **invariant** across that sweep, and label any conclusion
  that is not.

---

## SERIOUS 4 — "Separates epistemic from aleatoric" is not what the design does

The adaptive gate caps are calibrated once on the unperturbed scene and frozen; `k = 2`
is fixed; the four indices are fixed; the vote rule is fixed. The ensemble therefore
measures the sensitivity of **one specific decision rule** to **one specific noise
model**.

That is not the uncertainty of the water extent. Model-form (epistemic) uncertainty is
not separated — it is **set to zero by construction**. The current wording claims a
separation the graph does not perform.

### Required fix — either

**(a) Actually measure it.** A second, nested ensemble over rule variants:
- `k ∈ {1, 2, 3}`
- index subsets (leave-one-out over the four, plus each index alone)
- gate percentile `∈ {95, 98, 99}` and the floor multiplier
- guard threshold `valid_min`

The spread across rule variants *is* the epistemic term; total uncertainty is then the
combination, and the decomposition claim becomes true.

**(b) Weaken the claim.** "Aleatoric (radiometric) uncertainty only; model-form
uncertainty is deliberately held fixed so that the ensemble spread is interpretable as a
propagated measurement uncertainty." This is honest and costs nothing, but it also means
the paper cannot claim to quantify uncertainty *of the water extent*.

---

## BLOCKER 3 — σ_P is mathematically redundant with P (proved) — ✅ ADDRESSED via option (a)

*Was SERIOUS 5 ("σ_P may be a deterministic function of P"). Upgraded after measurement:
it is not a risk, it is an identity.*

### The proof

Each realisation produces a **binary** outcome per pixel. Realisations are independent
(the noise node draws a fresh `default_rng(seed + tick)` per tick). Therefore, for a
pixel with true firing probability `p`, the per-pixel count over `N` realisations is
`Binomial(N, p)`, and the accumulator's population std (`ddof = 0`, as implemented via
Welford `M2 / count`) is

```
σ_P = √(P(1−P))        exactly, up to O(1/√N) sampling error
```

`P` is the accumulator mean. So **σ_P is a closed-form function of the value the node next
to it already outputs.** No property of the noise model can change this: the identity
follows from the outcome being binary and the realisations being i.i.d. across ticks — not
from the shape, magnitude, band structure or spatial correlation of the perturbation.

In particular, **spatial correlation cannot rescue it.** Correlating the noise field
changes the *covariance between pixels*; it leaves each pixel's *marginal* distribution
over realisations Bernoulli(`p`). The methods document's claim that spatial correlation is
one of two mechanisms pushing σ_P off the envelope is wrong.

### The measurement

The real `sci_frame_accumulator` was driven with a synthetic 118-realisation ensemble over
a graded latent probability field (smooth tanh ramp, so 19 % of pixels are non-saturated),
once with i.i.d. draws and once with σ = 3 px spatially correlated draws — the graph's own
setting. Output of the new `sigma_check` node:

| | i.i.d. | correlated 3 px |
|---|---|---|
| `r2_vs_bernoulli_envelope` | **0.99989** | **0.99990** |
| `relative_deviation` | 0.0087 | 0.0083 |
| `mean_bias` | +0.00024 | +0.00017 |
| `pearson_r_graded_only` | 0.99976 | 0.99977 |
| `mean_sigma_P` / `mean_envelope` | 0.07172 / 0.07149 | 0.07096 / 0.07079 |
| verdict | `REDUNDANT with P` | `REDUNDANT with P` |

Identical to four decimal places. The correlated and i.i.d. cases are indistinguishable in
the per-pixel σ map.

(The agreement of `mean_sigma_P` with `mean_envelope` also confirms the BLOCKER 1 fix
recovers σ in correct probability units: `σ_P = main · scale / 255²`.)

### What this invalidates

- The uncertainty map is **not a second product**; it is `√(P(1−P))` rendered as an image.
  It could be computed in closed form from a single deterministic run's `P`, with no
  Monte-Carlo at all.
- Contribution claim #1 of the methods document ("a per-pixel probability *and*
  uncertainty product") collapses to "a per-pixel probability".
- ⟨U⟩ in `mc_cal` is `⟨√(P(1−P))⟩`. The node's own `bernoulli_std` fallback is not a
  fallback — it is the same quantity. That the two code paths were interchangeable was the
  tell.
- The convergence criterion (BLOCKER 1) is measuring the concentration of a Binomial
  proportion, `√(P(1−P)/N)`. It is a restatement of `N`, not a diagnostic of the pipeline.

### The constructive replacement — where the Monte-Carlo actually earns its cost

The information that spatial correlation *does* carry lives in **aggregate** quantities,
which the per-pixel marginal cannot see. **Measured on the real acquisition** (full wired
pipeline, 118 realisations per correlation length, corridor domain):

| noise correlation | mean area (px) | **sd (px)** | CV | × i.i.d. |
|---|---|---|---|---|
| 0 px (i.i.d.) | 102 716.0 | **72.1** | 0.00070 | 1.00 |
| 1 px | 102 717.6 | **117.3** | 0.00114 | 1.63 |
| **3 px (as wired)** | 102 717.3 | **253.9** | 0.00247 | **3.52** |
| 10 px | 102 773.9 | **576.6** | 0.00561 | **8.00** |

The control makes this conclusive: mean area is unchanged across all four (0.06 % spread),
the mean probability over the domain is identical to four decimals (0.2796 / 0.2796 /
0.2796 / 0.2797), and the graded-pixel fraction barely moves (7.43 → 7.32 %). **The
marginal probability field is invariant while the aggregate spread varies eightfold.**

An earlier synthetic check (uniform `p = 0.5`, 400 realisations, 17.6 vs 139.9 px) gave
≈ 8× at 3 px; on the real river corridor 3 px gives 3.5× and 8× is reached at 10 px. The
mechanism reproduces and is monotonic; the magnitude depends on the correlation length and
the scene geometry, which is why it must be reported as a sweep rather than a single
number.

So the paper's uncertainty product should be **ensemble statistics of derived quantities**,
not the per-pixel std:

1. **Total water area** — ensemble distribution, mean, sd, percentile CI. Demonstrably
   sensitive to the noise's spatial structure (×8 above). Report it as a function of the
   correlation length, which turns SERIOUS 3's sensitivity sweep into a result rather than
   a defensive appendix.
2. **Shoreline positional uncertainty** — per-realisation boundary displacement
   distribution (signed distance from each realisation's boundary to the ensemble-median
   boundary). The honest version of what boundary-F1 gestures at, and the metric for which
   the missing co-registration term (SERIOUS 10) matters most.
3. **Topological / connectivity statistics** — per-realisation connected-component count,
   largest-component area, channel continuity along the reach. Binary-outcome ensembles
   carry real information here, and none of it is a function of `P`.
4. **Pre-threshold margin uncertainty** — σ of the *continuous* index values, or of the
   distance to the decision boundary (`vote_sum` margin, gate headroom), before
   binarisation. Unlike the binary outcome, the continuous margin's per-pixel variance is
   not pinned to `P(1−P)` and genuinely reflects the noise model.

Items 1–3 require accumulating **per-realisation scalars and shapes**, not per-pixel
moments — a different accumulator (an ensemble-of-statistics node) than the one currently
wired.

### Reframing options

- **(a) Keep the MC, change the product.** Headline = ensemble uncertainty of water area /
  shoreline position / connectivity, with spatial correlation length as the controlling
  parameter. The ×8 result is a genuine quantified finding, and it argues that i.i.d. error
  models — the implicit default in most of the literature — understate water-area
  uncertainty by nearly an order of magnitude. Strongest available framing.
- **(b) Keep the current product, state the identity.** Publish `P` as a calibrated
  probability (calibration + threshold-selection protocol remain real contributions), and
  state explicitly that the per-pixel std is `√(P(1−P))` and is reported for display only.
  Honest, much thinner.
- **(c) Negative result.** "Monte-Carlo propagation of radiometric noise through a k-of-4
  index vote yields a per-pixel uncertainty analytically redundant with the probability
  itself; the ensemble is informative only for aggregate quantities, where spatial error
  correlation dominates." Publishable, and the honest headline if (a) is not pursued.

**(a) is recommended.** It keeps the Monte-Carlo essential, uses the spatial-correlation
machinery already built, and produces a number (×8) that matters to users of water
products.

### Resolution — option (a) implemented

New plugin **`engine/plugins/sci_ensemble_stats.py`** ("Ensemble Statistics", category
`measure`), domain-agnostic: it accumulates one value per realisation of any binary-mask
ensemble and reports mean / sd / CV / percentile CI / min / max per metric, with
histograms.

Metrics: `area`, `perimeter`, `components`, `largest`, `centroid_x/y`, and
`boundary_dist` (mean distance from each realisation's boundary to a reference boundary —
optional `reference` input, so shoreline error is measured with both its bias and its
spread).

Design points:

- **Percentile CI over realisations**, not a bootstrap over pixels. Each realisation is a
  genuinely independent draw, so these intervals are immune to SERIOUS 8's spatial-
  autocorrelation objection — unlike every pixel-level interval currently in the paper.
- Memory `O(N · metrics)`: one float per metric per realisation, never `N` frames. Storing
  the series (rather than streaming moments) is what makes percentile CIs and histograms
  possible at all.
- Histogram render is **throttled** to a stride (`fig_every`, default 10) plus a forced
  redraw when `target_n` is reached. A matplotlib render per tick cost ~0.4 s and
  dominated a 120-realisation run — the test suite went from 100 s to 13.8 s after
  throttling, and a 200-draw production run would otherwise have wasted ~80 s on figures.
- Auto-reset on upstream tick drop (same idiom as the Frame Accumulator) and on a mid-run
  grid change, so incomparable areas are never mixed.
- `None` mask inputs are not counted as zero-area realisations.

Graph wiring in `MC-paper.vn`: `mask_and.mask` → `ens_stats.mask` (the per-realisation
mask, same stream as both accumulators), `noise.tick` → `ens_stats.tick`,
`landcover_gt.mask` → `ens_stats.reference` (boundary displacement against ground truth),
and the same teleported `target_n` scalar the mean accumulator uses — which also fixes
the asymmetric-`target_n` half of MINOR 18 for this node. Outputs to a data inspector
and a display, inside a new "Ensemble uncertainty — the informative product" frame.

Verification: 15/15 tests in `engine/tests/test_sci_ensemble_stats.py`, written first and
confirmed RED. The suite pins the substantive behaviour, not just plumbing — including
`test_correlated_noise_inflates_area_spread_over_iid`, which asserts the ×3-or-more sd gap
that the paper's headline claim rests on. Full engine suite: 481 passed, same 8
pre-existing unrelated failures. All 84 graph edges validated against the 472 real plugin
schemas: no invalid handles.

**Done:** the sweep is above. One discovery it depended on, worth recording because it
invalidates every Monte-Carlo number produced before it:

> **The Monte-Carlo was injecting no noise at all.** `stac_to_db` is labelled
> "STAC: SAR → dB" and defaults to on, but it was applied to *every* non-categorical STAC
> collection. Sentinel-2 L2A therefore arrived as `10·log10(DN)` — values in 20–42 rather
> than reflectance in [0, 1]. An additive `σ_abs = 0.005` specified in reflectance units
> then perturbs a 20–42 dB signal by about 0.02 %. Every spectral index was also being
> computed on log-transformed data, and the gate's reflectance-unit fallback caps were
> meaningless against that range.
>
> **This, not a missing noise floor, is why `P` came out quasi-binary** — which retires
> the most attackable sentence in SERIOUS 3. With correct units, 7.4 % of the corridor is
> graded (0.02 < P < 0.98) without any tuning of `σ_abs`.
>
> A second defect compounded it: the cache signature recorded the raw `to_db` *request*
> rather than the transform actually applied, so fixing the transform did not move the
> key and a cache hit kept serving the old product. Both are fixed, with tests.

## SERIOUS 6 — The evaluation domain is derived from the ground truth

The analysis domain is the GT water mask, small-object-filtered (`min_area = 258 px`) and
**dilated** (elliptical SE, size 15, 2 iterations). Consequences:

1. **False positives away from water are invisible.** A pixel wrongly classed as water in
   a wet field or a building shadow 2 km from the river is outside the domain and never
   counted. That is precisely the real-world failure mode of index-based water mapping,
   and the protocol is blind to it by construction.
2. **All metrics are a function of an arbitrary morphological parameter.** Change the
   dilation from 15 to 31 and every precision / F1 / MCC / balanced-accuracy number
   moves, monotonically. The reported values have no meaning without that parameter, and
   no sensitivity to it is reported.
3. **Using the reference to define the evaluation universe biases toward the reference.**
   The negative class becomes "land within ~5 % margin of GT water", which is the easiest
   possible negative set for a shoreline problem, *and* the hardest for boundary metrics
   — the two effects do not cancel and their net sign is unknown.

### Required fix

- Report each metric at several dilation radii (e.g. 0, 5, 15, 31 px) **and** on the
  whole scene, as a table.
- Add an explicit **false-positive audit outside the corridor**: count and map predicted
  water that lies beyond the largest dilation. This is a required figure, not an
  appendix.

---

## SERIOUS 7 — The threshold is selected on the same ground truth used to score it

`thr_sweep` maximises F1/IoU/Youden/MCC against the GT, and the mask metrics in the
results are then computed at that threshold against the same GT, on the same scene. The
reported scores are in-sample and optimistically biased.

The semantic anchor at `t = 0.5` mitigates this **only when it actually fires** (plateau
> 30 % *and* anchor cost ≤ 0.03); otherwise the plateau-median pick is still GT-fitted.

There is no held-out scene anywhere in the protocol.

### Required fix

- Select the threshold on scene A, evaluate on scene B (and report both directions).
- Or spatial block cross-validation within one scene: partition into blocks larger than
  the noise correlation length, fit `t` on some blocks, score on the rest.
- Report the in-sample / out-of-sample gap explicitly. For a paper whose thesis is
  "thresholds are the problem", the transferability of the chosen threshold *is* the
  result.

---

## SERIOUS 8 — Spatial autocorrelation invalidates every p-value and CI

Pixels at 10 m in a river corridor are strongly autocorrelated; the noise model itself
imposes a 3 px correlation length on top of the scene's own structure. The effective
sample size is plausibly 10²–10³, not the 10⁵–10⁶ pixels being fed to the tests.

Therefore:

- **Mann–Whitney p-values are meaningless** as inference. (They are also a function of
  the 20 000-pixel subsample cap, i.e. of a performance parameter.)
- **The bootstrap CI is not a CI.** Pixels are resampled independently, ignoring
  autocorrelation, which *understates* the width.
- `threshold_statistically_distinguishable` (true iff < 50 % of thresholds fall inside
  the best CI) is therefore near-always true and carries no information.

Additionally, the code comment is factually wrong:

```python
_BOOT_MAX_PX = 40000   # subsample cap (perf only); CI width is set by class sizes, not this
```

The bootstrap resamples `_n` **after** capping, so `_n = 40000` and the CI width *is* set
by the cap. If the true domain holds 500 k pixels, the CI is inflated by ≈ √12.5 ≈ 3.5×.
Two errors of opposite sign (cap inflates, independence assumption deflates) of unknown
relative magnitude — the interval is uninterpretable.

### Required fix

- **Block bootstrap**: resample contiguous blocks sized at ≥ 10× the correlation length,
  not individual pixels.
- Remove the subsample cap, or keep it and correct the interval for the sampling fraction
  — and fix the comment either way.
- Report an effective sample size (e.g. from a variogram or Moran's I) and present all
  p-values as descriptive only, with effect sizes carrying the argument.

---

## SERIOUS 9 — "k-of-4, no index privileged" is false; two unguarded indices dominate

Two separate problems compound.

**(a) The guard applies to only two of the four indices.** In
`geo_spectral_indices`, `guard_invalid` / `valid_min` is applied inside `_norm_index`,
which serves **NDWI and MNDWI only**. `AWEIsh` and `MBWI` are free-form expressions
(`expr1`, `expr2`) — linear combinations with no division, never NaN'd by the guard.

Over water, AWEIsh > 0 and MBWI > 0 both hold robustly. **Those two alone reach `k = 2`.**
The vote therefore reduces in practice to ≈ `AWEIsh ∧ MBWI`, with NDWI and MNDWI
contributing only in marginal pixels. The "four-index consensus" framing overstates what
the rule does.

**(b) The two dominant indices have the least standard criteria.** `AWEIsh > 0` follows
Feyisa et al., but is sensitive to the reflectance scaling convention. `MBWI > 0` is
*not* the published criterion — Wang et al. use a dynamic/Otsu threshold on MBWI, not
zero. So the rule that effectively decides the mask rests on a threshold the paper
elsewhere argues against using.

**(c) The four indices are highly correlated.** NDWI, AWEIsh and MBWI all use NIR;
NDWI, MNDWI, AWEIsh and MBWI all use GREEN. A `k`-of-4 vote over strongly correlated
tests is close to a single test with jitter, not an independent consensus. The
"complementary physics" claim needs evidence.

**(d) Invalid data votes "not water".** `NaN > 0` evaluates to `False` in the band-calc
expression, so a missing/guarded index is counted as evidence *against* water rather
than as unknown. Asymmetric treatment of missing data. (With the wired
`valid_min = -0.05` and `σ_abs = 0.005` the guard essentially never fires, so the
present bias is negligible — but the design is wrong and becomes a real bias at a
tighter `valid_min`, e.g. the `-0.002` default.)

### Required fix

- Report the **4×4 index correlation matrix** and an effective number of independent
  votes.
- **Ablation**: `k ∈ {1,2,3,4}`, and leave-one-out over the four indices. Show how much
  each index actually contributes to the mask.
- Either guard all four consistently or state that AWEIsh/MBWI are unguarded and why.
- Replace `MBWI > 0` with the published criterion, or justify zero explicitly.
- Make missing data a third state (abstain) rather than a "no" vote.

---

## SERIOUS 10 — The dominant uncertainty source for the headline metric is missing

The noise model covers radiometric perturbation only. Not modelled:

- **Geometric / co-registration uncertainty.** Sentinel-2 multi-temporal
  co-registration error is of order one 10 m pixel. For a river 10–50 m wide, this is
  the **dominant** contributor to shoreline placement uncertainty.
- Cloud / cirrus / shadow mask uncertainty (the composite is cloud-filtered; that filter
  has error).
- BRDF and adjacency effects near the land/water boundary — mixed pixels are exactly the
  contested class.
- Reference-product error (see MINOR 16).

The paper reports **boundary-F1 at 3 px tolerance** as its finest-grained metric while
omitting the error term that dominates at that scale. A reviewer working on
co-registration will raise this immediately.

### Required fix

Add a sub-pixel geometric perturbation to the ensemble (random sub-pixel shift, or a
smooth warp field, per realisation). This is cheap to implement in the same forward
model and it directly targets the metric under discussion. If it is not added, state the
omission and argue why the reported boundary uncertainty is a lower bound.

---

## SERIOUS 11 — Missing baselines

Currently the only intended comparison is "MC vs bypass" (ensemble vs one deterministic
run). That is insufficient to place the method.

Needed:

- **Otsu on MNDWI** (or NDWI) — the standard adaptive-threshold baseline.
- **Cross-comparison against an independent product** (JRC GSW, and WorldCover treated
  as prediction rather than truth) to characterise reference disagreement.
- **A supervised baseline** if any labelled data exists for the scene.

And the honest risk: if `F1_MC ≈ F1_single-run`, then the contribution collapses to the
uncertainty map, which loops back to **SERIOUS 5**. That outcome is still publishable —
"Monte-Carlo propagation of radiometric noise does not change the mask, and here is the
quantified reason" is a real negative result — but it is a different paper and should be
framed as one from the start.

---

## SERIOUS 12 — Quasi-binary P makes the threshold-free claim trivially true

If `plateau_fraction` is large (the observed regime), then the metric is nearly flat
across `t` and the choice of threshold genuinely does not matter — but that is because
`P` is degenerate, not because the method solved the thresholding problem. The
interesting regime (informative, graded `P`) and the observed regime are different.

`plateau_fraction` must be a **headline reported number**, not a warning printed to the
console. If it is ~0.9, the honest title of the result is "under this noise model the
ensemble barely changes the mask", and the paper's contribution must be restated
accordingly.

---

## MINOR 13 — `anchor_cost` is measured against a value the code calls an artifact

```python
raw_best_i = int(np.argmax(target))
...
anchor_cost = float(target[raw_best_i] - target[anchor_i])
```

The code's own comment says `raw_best_i` "lands on the first point right after a sharp
initial cliff … an artifact, not a meaningful cutoff". Yet the decision of whether to
snap to the semantic anchor is made by comparing against exactly that artifactual
maximum. A spuriously high `raw_best` can push `anchor_cost` above
`ANCHOR_COST_MAX = 0.03` and block a snap that should happen.

**Fix:** measure the anchor cost against the plateau-median pick (the value that would
otherwise be used), not against the raw argmax.

---

## MINOR 14 — ECE with 12 equal-width bins on a quasi-binary P

With `P` concentrated near 0 and 1, most of the 12 equal-width bins are empty or nearly
so, and ECE is carried by the two extreme bins. ECE is known to be biased and strongly
binning-dependent (Kumar et al. 2019; Nixon et al. 2019; Roelofs et al. 2022).

**Fix:** equal-mass (adaptive) bins, report ECE for several bin counts, and add a
debiased or kernel-based estimator. Keep the reliability diagram with the bin-population
histogram — that part is already right and it is what makes the emptiness visible.

---

## MINOR 15 — uint8 truncation biases P downward  ✅ FIXED

`sci_frame_accumulator` returns `result.clip(0, 255).astype(np.uint8)`, which **truncates**
rather than rounds. Systematic downward bias on `P` of up to `1/255 ≈ 0.0039`, mean
≈ 0.002. Small, but the same order as a good ECE, and free to fix.

**Fixed** in the BLOCKER 1 patch: all modes now go through `_as_u8`, which rounds
(`np.rint`) before clipping and casting.

Related: `P` is quantised to 1/255 = 0.0039 while `N = 118` gives a natural granularity
of 1/118 = 0.0085, so quantisation is not the limiting resolution — but it becomes so if
`N` exceeds 255.

---

## MINOR 16 — Reference-product error is unmodelled  ✅ QUANTIFIED

WorldCover class 80 is itself a classification with finite accuracy (≈ 75 % class-wise
in the published validation), produced at 10 m from a different year. JRC GSW occurrence
carries its own temporal semantics and its own error. Treating either as *truth* without
an error term means all reported precision/recall are conditional on a reference whose
error is comparable to the effect being measured.

**Done.** Both references are now fetched on the same grid and their disagreement is
measured by the `ref_agree` node: IoU = 0.7308 in the corridor domain (0.7177 whole-scene), i.e. they differ on ~27 % of
their union, while their eroded cores agree at 0.9960 / 0.9742. See BLOCKER 2's resolution — the gap is
boundary sampling (GSW at 30 m), not class disagreement. The practical consequence is a
**validation ceiling**: reported metric differences below that envelope are not
interpretable, and a defensible 10 m boundary claim requires manual annotation on the
single locked acquisition.

---

## MINOR 17 — Linear rather than quadrature combination of noise terms

`engine/plugins/geo_raster_noise.py`:

```python
sigma = sigma_abs + sigma_rel * np.abs(bands)
```

Independent error contributions combine in quadrature, not linearly. At `ρ = 0.3`:
linear `0.0095` vs quadrature `√(0.005² + (0.015·0.3)²) = 0.0071` → **σ overstated by
≈ 34 % on bright pixels**. Over water (`ρ ≈ 0.005`) the difference is negligible
(`0.005075` vs `0.005006`).

Net effect: more false-positive flicker on bright land than the noise budget justifies,
which inflates the apparent discrimination difficulty on the negative class.

**Fix:** either switch to `sqrt(sigma_abs**2 + (sigma_rel*|ρ|)**2)`, or keep the linear
form and state it as a deliberately conservative choice. Do not leave it unstated — the
methods document currently writes it as `⊕` (quadrature), which does not match the code.

---

## MINOR 18 — Asymmetric accumulator configuration

| Node | `cumulative` | `target_n` | `window` |
|---|---|---|---|
| `acc_mean` | true | 118 (via teleport) | 64 (inactive) |
| `acc_std` | true | **0 = unlimited** | 16 (inactive) |

`noise.max_ticks = 118` stops the driver, so in the nominal run both freeze together.
But if the graph ticks beyond 118 for any reason (manual resume, re-tick), `acc_mean` is
frozen at `N = 118` while `acc_std` keeps integrating. `P` and `σ_P` would then come from
different sample sizes — and `mc_conv` reads `N` from **`acc_std.frame_count`**, so the
convergence curve would use the wrong `N` for the `P` being reported.

**Fix:** set both `target_n` from the same source (the teleported scalar).

---

## MINOR 19 — Duplicate / legacy edges

- `mask_and.mask` → `acc_mean` on **both** `image__image` and `any__image`
- `filter_threshold` → `filter_blob_filter` on **both** `main` and `mask__mask`
- **Two** edges into `corr_dilate.any__mask` (from `filter_blob_filter.main` and
  `filter_blob_filter.mask__main`)

Whichever resolves last wins. Harmless today, a silent behaviour change the next time
port resolution order changes.

**Fix:** delete the redundant edges.

---

## MINOR 20 — Unexplained magic numbers

| Parameter | Value | Issue |
|---|---|---|
| `sweep_boot` | `202.74` | slider artifact; rounds to 203 replicates |
| `min_area` (blob filter) | `258 px` | no stated provenance |
| `max_ticks` | `118` | not derived from the convergence criterion it is supposed to satisfy |
| `corr_dilate` size / iterations | `15` / `2` | described as "≈ 5 % corridor margin" — show the computation |
| `ANCHOR_COST_MAX` | `0.03` | reasonable, but arbitrary and outcome-determining |

Reviewers read these as evidence of tuning. Round them, or state where each came from.
`max_ticks = 118` is the worst offender: the paper's own convergence criterion should
*determine* `N`, so a hand-set value contradicts §5.7.

---

## MINOR 21 — The decision rule is implemented twice, with different guards

`adaptive_gate`'s internal `_votesum` reimplements the four-index vote in order to select
consensus pixels for cap calibration, using `BAND_MIN = -0.002` and `DEN_MIN = 1e-6`.
The production vote path (`geo_spectral_indices` → `geo_band_calc`) uses
`valid_min = -0.05`, and does not guard AWEIsh/MBWI at all.

So the caps are calibrated against a **slightly different rule** than the one they gate.
No bias engine today (the calibration runs on the unperturbed scene, where guards rarely
fire), but a guaranteed source of drift: any change to the production rule silently fails
to propagate to the calibration.

**Fix:** single source of truth for the vote rule; the gate should consume the same
index stack the vote does.

---

## MINOR 22 — The corridor domain is not wired to three of the five validation nodes

| Node | domain input | status |
|---|---|---|
| `mc_conv` | `c` | connected (`corr_dilate`) |
| `overall_acc` | `c` | connected (`corr_dilate`) |
| `thr_sweep` | `c` | **unconnected** → whole scene |
| `mc_cal` | `c` | **unconnected** → whole scene |
| index correlation | `e` | **unconnected** → whole scene |

Each unconnected node falls back to `np.ones(...)`, i.e. the full tile. Since the scene
is dominated by trivially dry pixels, this inflates the threshold sweep, the calibration
metrics and the Spearman/AUROC figures relative to the corridor-restricted ones — and
makes them non-comparable to `overall_acc`, which *is* restricted.

**Fix (blocking for the figures):** wire `corr_dilate.mask` to `thr_sweep.c`,
`mc_cal.c` and the index-correlation node's `e`, then regenerate everything. Or run both
domains deliberately and report the pair (see SERIOUS 6).

---

## What holds up

Not everything is a problem. These are genuine strengths and should be defended:

- **Freezing the gate caps on the unperturbed scene.** Correct and well-motivated: if the
  gate re-derived itself per realisation, the ensemble would mix decision-rule
  variability into what is meant to be a measurement-uncertainty estimate.
- **Spatially correlated noise.** i.i.d. pixel noise is unphysical and produces
  over-confident ensembles. The blur-then-renormalise implementation preserves the
  marginal σ correctly.
- **Removing the brightness floor** from the gate, with the reason recorded in a comment
  (a floor deletes pure dark open water, the primary target).
- **Plateau detection + semantic anchor with a *reported* cost.** Rare and honest: the
  trade-off between GT-fitted optimality and transferability is made explicit instead of
  being buried in an argmax.
- **Refusing the two obvious degenerate picks** (raw argmax on the cliff; highest-`t`
  within tolerance → `t ≈ 1`) with the reasoning written down.
- **Metric hygiene**: MCC alongside F1/IoU, balanced accuracy alongside OA, boundary-F1
  alongside region metrics, effect sizes alongside p-values, reliability diagram with the
  bin-population histogram underneath.
- **The P-free AUROC layer** genuinely breaks the circularity of validating `P` against
  the indices `P` is built from.
- **Guarded normalised differences** (NaN rather than a fabricated ratio near the
  denominator zero-crossing) — for the two indices where it is applied.
- **Reproducibility**: all seeds fixed (noise 42, scatter 0, MWU 0, bootstrap 12345),
  GT fetched on the Sentinel-2 grid, exact-affine reprojection on the JRC path,
  defensive shape assertions rather than silent broadcasting.
- **Whole protocol as one executable graph** — figures regenerate from the wiring.

---

## Recommended order of attack

Ordered so that the cheapest decision-relevant work comes first.

1. ~~**Patch `sci_frame_accumulator`**~~ — **DONE.** Unnormalised σ + `scale` output,
   rounding instead of truncation, graph rewired, 10/10 tests green, no regressions.
   The convergence figure and ⟨U⟩ still need regenerating from a real run.
   *(BLOCKER 1, MINOR 15)*
2. ~~**Scatter σ_P vs √(P(1−P)/N)**~~ — **DONE, and the answer is negative.** The
   `sigma_check` node is wired into the graph. σ_P is redundant with `P` by identity, not
   by accident, and spatial correlation does not change it. *(BLOCKER 3)*
3. ~~**Decide the framing**~~ — **DONE: option (a).** `sci_ensemble_stats` built, tested
   (15/15) and wired: per-realisation area / perimeter / components / centroid /
   boundary displacement, with percentile CIs over realisations. *(BLOCKER 3)*
4. ~~**Define the estimand**~~ — **DONE.** Single acquisition 2021-09-02 10:57:29 UTC,
   both references temporally aligned, reference error measured on the delivered grid (IoU
   0.731 in-corridor, cores 0.996 / 0.974). *(BLOCKER 2)*
5. **Run the ensemble node on the real scene**, then sweep `sd(area)` and
   `sd(boundary_dist)` against the noise correlation length (0, 1, 3, 10 px). This is the
   paper's main figure, and it converts SERIOUS 3's defensive sensitivity analysis into
   the result.
6. **Wire the domain everywhere**, then report metrics at several dilation radii plus a
   false-positive audit outside the corridor. *(MINOR 22, SERIOUS 6)*
7. **Second scene** → out-of-sample threshold; report the in/out-of-sample gap.
   *(SERIOUS 7)*
8. **σ_abs sensitivity sweep** and **k / index ablation**. *(SERIOUS 3, 4, 9)*
9. **Block bootstrap** + effective sample size; downgrade all pixel-level p-values to
   descriptive. Note the ensemble node's percentile CIs are already immune to this.
   *(SERIOUS 8)*
10. **Baselines**: Otsu/MNDWI, JRC cross-comparison. *(SERIOUS 11)*
11. **Sub-pixel geometric perturbation** in the forward model. *(SERIOUS 10)* — more
    valuable now than before, since it feeds straight into `boundary_dist`, a metric the
    ensemble node already reports.
12. **Hygiene sweep**: MINOR 13–14, 16–17, 19–22.

Steps 1–4 are done: all three blockers are closed. The per-pixel uncertainty product
turned out to be an identity and has been replaced; the estimand is a single locked
acquisition with both references aligned and their disagreement measured.

**Step 5 is now the critical path** — running the ensemble node on the real scene and
sweeping `sd(area)` against the noise correlation length. That produces the paper's
headline figure. Everything after it is hardening.

One standing constraint from step 4: the reference envelope (IoU 0.731 in-corridor between the
two references, cores agreeing at 0.974–0.996) caps what the mask metrics can resolve. Area and
ensemble-spread claims are unaffected — they are the ones the paper now leads with — but a
defensible 10 m *boundary* claim needs manual annotation on the locked acquisition.

## Additional references for the fixes

- Kumar, A., Liang, P., Ma, T. (2019). Verified uncertainty calibration. *NeurIPS*.
- Nixon, J., Dusenberry, M., Zhang, L., et al. (2019). Measuring calibration in deep learning. *CVPR Workshops*.
- Roelofs, R., Cain, N., Shlens, J., Mozer, M.C. (2022). Mitigating bias in calibration error estimation. *AISTATS*.
- Künsch, H.R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics* 17(3), 1217–1241. (block bootstrap)
- Lahiri, S.N. (2003). *Resampling Methods for Dependent Data.* Springer.
- Roberts, D.R., Bahn, V., Ciuti, S., et al. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography* 40(8), 913–929. (spatial block CV)
- Legendre, P. (1993). Spatial autocorrelation: trouble or new paradigm? *Ecology* 74(6), 1659–1673.
- Storey, J., Roy, D.P., Masek, J., et al. (2016). A note on the temporary misregistration of Landsat-8 OLI and Sentinel-2 MSI imagery. *Remote Sensing of Environment* 186, 121–122. (co-registration)
- Skakun, S., Roger, J.-C., Vermote, E., et al. (2017). Automatic sub-pixel co-registration of Landsat-8 OLI and Sentinel-2A MSI images. *International Journal of Digital Earth* 10(12), 1253–1269.
- Kumar, S.V., Dirmeyer, P.A., et al. — see also Heuvelink (1998), *Error Propagation in Environmental Modelling with GIS*, Taylor & Francis, for the epistemic/aleatoric split in geospatial propagation.
