# Monte-Carlo Uncertainty Propagation for Threshold-Free Surface-Water Mapping

**Methods & protocol description**
Derived from the executable graph `MC-paper.vn` (VNStudio node graph, 59 nodes / 69 edges).

---

## 1. Rationale

Optical surface-water mapping from Sentinel-2 is almost always done the same way: pick a
spectral water index (NDWI, MNDWI, AWEI, MBWI…), pick a threshold, binarise. Two
well-known weaknesses follow from that recipe.

1. **The threshold is scene-dependent and usually eyeballed.** The classic "NDWI > 0"
   rule is a convention, not a physical boundary; the empirically optimal cut moves with
   sun geometry, turbidity, sediment load, aerosol residuals and land-cover mix
   (McFeeters 1996; Xu 2006; Feyisa et al. 2014; Ji et al. 2009). Otsu-style adaptive
   thresholding (Otsu 1979; Donchyts et al. 2016) removes the hand-tuning but still
   returns a single hard cut per scene.
2. **The output is a hard binary mask with no uncertainty.** A pixel one digital count
   from the threshold is reported with the same confidence as the middle of a lake.
   Downstream users (flood extent, water-area time series, hydrological model
   calibration) receive no way to know which pixels are contested.

This study replaces the single deterministic evaluation with a **Monte-Carlo ensemble
over sensor/atmospheric noise**, producing a per-pixel water *probability* `P(water)` and
a per-pixel *uncertainty* `σ_P`, and then asks a sequence of falsifiable questions about
that probability field: is it a valid ranking? is it a *calibrated* probability? does a
threshold even matter? how many realisations are enough?

The philosophical shift: the deliverable is no longer a mask, it is a **probability field
plus a quantified uncertainty and a documented convergence criterion**. The mask becomes
one derived product among several, and the threshold that produces it becomes an object
of study rather than a hidden parameter.

---

## 2. Data and estimand

### 2.1 The estimand

**Water extent over the Seine corridor at the instant of a single Sentinel-2 acquisition:
2021-09-02, 10:57:29 UTC.**

Stating this explicitly is not pedantry — it is the difference between a validatable claim
and an unfalsifiable one. A multi-date cloud-filtered composite has no well-defined water
extent (adjacent pixels come from acquisitions months apart), so no reference can be
correct for it. A 1-day acquisition window over this AOI returns **exactly one image**, so
the problem is removed rather than mitigated:

|                     |                                                                                                                                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source              | Sentinel-2 **L2A Surface Reflectance**, read from Microsoft Planetary Computer STAC (`sentinel-2-l2a`). The Copernicus Data Space Ecosystem backend is wired as an alternative; both return the same single item for this query. |
| Item ID             | `S2A_MSIL2A_20210902T105031_R051_T31UDQ_20210903T000651`                                                                                                                                                                         |
| Acquisition         | 2021-09-02 **10:57:29 UTC**, tile **31UDQ**, orbit 51, single image                                                                                                                                                              |
| Cloud cover         | **0.00 %** over the AOI, 0.00 % tile-wide                                                                                                                                                                                        |
| AOI coverage        | **100 %**                                                                                                                                                                                                                        |
| Bands               | B04 (red), B03 (green), B02 (blue), B08 (NIR), B11 (SWIR1), **B12 (SWIR2)** — all six required; see §3.2                                                                                                                         |
| Resolution          | 10 m (SWIR resampled to the 10 m grid)                                                                                                                                                                                           |
| AOI                 | `1.8751, 48.8869, 2.2089, 49.0248` — Seine corridor downstream of Paris, 24.6 × 15.6 km, **2464 × 1564 px** (grid as delivered by the loader, EPSG:32631)                                                                        |
| Out-of-sample dates | 2021-06-14 and 2021-03-01 — same tile, same orbit, ≤ 0.03 % AOI cloud, so directly comparable (used for out-of-sample threshold selection, §5.6)                                                                                 |

### 2.2 Why 2021

The year is set by the **references**, not by the imagery. JRC Global Surface Water
MonthlyHistory — the only readily available *dated* water reference — ends at **2021-12**,
and ESA WorldCover v200 is the **2021** epoch. Placing the scene in 2021 aligns *both*
references at once rather than trading one temporal mismatch for another. 2021-09 also
sits at Seine low flow, the most hydrologically stable part of the year, so a monthly
reference best approximates an instant.

Reference availability was checked **before** committing to a date, because a dated
reference can be empty: JRC GSW observed **0.00 %** of this AOI in 2021-02 and 2021-12, and
1.20 % in 2021-07. Choosing the date from cloud statistics alone would have produced a
reference with no observations at all.

| Month | GSW valid observations | GSW water |
|---|---|---|
| 2021-03 | 96.50 % | 2.40 % |
| 2021-06 | 99.96 % | 2.18 % |
| **2021-09** | **99.59 %** | **2.37 %** |

### 2.3 Two references, and the validation ceiling

| Reference | Resolution | Temporal semantics | Role |
|---|---|---|---|
| **ESA WorldCover v200, class 80** | **10 m** | annual 2021, *permanent* water | primary — spatially matched to the prediction |
| **JRC GSW MonthlyHistory 2021-09** | 30 m | **the acquisition's month** | secondary — bounds reference error, supports the temporal claim; **not** used for boundary metrics |

Both are fetched onto the Sentinel-2 grid, so they are pixel-aligned with the prediction by construction. GSW's `water` band is **ternary** — `0 = not observed`, `1 = land`,
`2 = water` — so a separate **validity mask** is carried alongside it and all metrics are
restricted to observed pixels. Treating code 0 as land would silently convert missing
observations into false negatives.

Two independent references disagree, and that disagreement is a **ceiling on what the
validation can resolve**. Measured by the `ref_agree` node **inside the pipeline**, on the
grid the loader actually delivers (2464 × 1564 px), over the pixels GSW observed:

| | whole scene | corridor domain (as wired) |
|---|---|---|
| pixels evaluated | 3 837 487 | 333 352 |
| WorldCover class 80 | 116 839 px | 113 799 px |
| GSW 2021-09 | 90 115 px | 89 013 px |
| **IoU between the two references** | **0.7177** | **0.7308** |
| disagreement, share of union | 28.2 % | 26.9 % |
| area ratio GSW / WorldCover | 0.771 | 0.782 |
| in WorldCover only | 30 370 px | 28 165 px |
| in GSW only | 3 646 px | 3 379 px |

The corridor figure is the operative one: it is the domain the mask metrics use, and
restricting to it removes trivially dry background without changing the conclusion.

Decomposing the gap separates its two possible causes — coarse boundary sampling versus
genuine class disagreement. Dilating the coarser reference and comparing eroded cores:

| Diagnostic | whole scene | corridor |
|---|---|---|
| IoU, GSW dilated 10 m | **0.7929** (peak) | **0.8068** (peak) |
| … 20 / 30 / 40 / 50 m | 0.784 / 0.726 / 0.652 / 0.587 | 0.798 / 0.740 / 0.667 / 0.602 |
| GSW core (eroded 30 m) inside WorldCover | **0.9960** | **0.9960** |
| WorldCover core (eroded 30 m) inside GSW | **0.9741** | **0.9742** |

The interiors agree to 97.4–99.6 %, and the two domains give the same core figures to
four decimals — the agreement of the water *interiors* is a property of the products, not
of the evaluation window. **The disagreement is almost entirely boundary placement driven
by GSW's 30 m sampling, not seasonality**: only ~2.6 % of WorldCover's core is absent from
the dated reference. For this AOI the annual permanent-water reference is therefore close
to correct — the Seine near Paris is a regulated, largely permanent river. (The same
comparison on a tidal delta would be expected to behave very differently; see §6.)

Three consequences, all reported rather than assumed:

1. **The temporal error of the primary reference is bounded at ~2.6 % of water area** — a
   measured quantity, not an assumption.
2. **A 30 m reference cannot validate a 10 m boundary claim.** Boundary-F1 at 3 px is
   3 px = 30 m, exactly the scale at which the dated reference is itself uncertain.
3. **Metric differences smaller than the reference envelope are not interpretable.** Any
   defensible 10 m boundary claim requires manual annotation on this acquisition — which
   is feasible *because* the estimand is a single date, and was impossible against a
   multi-month composite.

## 3. Forward model — one Monte-Carlo realisation

Each Monte-Carlo iteration is a complete, independent water-detection run on a perturbed
copy of the reflectance stack.

### 3.1 Perturbation model

Additive Gaussian noise with **two components plus spatial correlation**:

```
ρ'(x) = ρ(x) + ε(x),   ε ~ N(0, σ(x)²),   σ(x) = σ_abs + σ_rel·|ρ(x)|
σ_abs = 0.005 (reflectance units)     σ_rel = 0.015 (1.5 % proportional)
spatial correlation length = 3 px     clip_negative = false
seed = 42, drawn as seed + tick, so an N-realisation run is exactly reproducible
```

The two terms are combined **linearly, not in quadrature** — this is what the code does
and it is stated rather than idealised. Independent error contributions should strictly
combine as `√(σ_abs² + (σ_rel·ρ)²)`; the linear form is larger, negligibly so on water
(`ρ ≈ 0.005`: 0.005075 vs 0.005006) but by **≈ 34 % on bright land** (`ρ = 0.3`: 0.0095 vs
0.0071). The consequence is more false-positive flicker on bright pixels than the
radiometric budget justifies — a conservative direction for the water class, but it
inflates the apparent difficulty of the negative class and should be reported as such.

Four deliberate modelling choices, each of which changes the result materially:

- **The absolute floor `σ_abs` is the crux.** A purely multiplicative model
  (`σ ∝ ρ`) drives noise to zero over water in NIR/SWIR, because clear water
  reflectance there is nearly zero. That is exactly backwards: it is precisely on dark
  targets that the *real* radiometric uncertainty is largest, since Sentinel-2's SNR is
  specified at reference radiances and the *relative* uncertainty on dark water can
  exceed several hundred per cent. Without the floor, the ensemble degenerates to a
  quasi-binary `P` (every realisation agrees over water) and the whole uncertainty
  product collapses. `σ_abs = 0.005` is a reasoned starting point, not a standard:
  it is the same order as reported L2A surface-reflectance validation uncertainties
  (Gorroño et al. 2017; Doxani et al. 2018; Vermote et al. 2016 for the analogous
  Landsat/MODIS-class budget) and should be treated as a documented assumption, subject
  to the sensitivity analysis of §6.
- **Spatially correlated noise (3 px).** i.i.d. pixel noise is unphysical: atmospheric
  correction residuals, aerosol-retrieval error and BRDF residuals are smooth fields at
  scales of tens to hundreds of metres. Correlated noise makes realisations differ in
  *shapes* (whole boundary segments migrate) rather than in salt-and-pepper.
  It does **not** change the per-pixel `σ_P` map — correlation alters the covariance
  *between* pixels while leaving each pixel's marginal Bernoulli — but it dominates the
  uncertainty of any **aggregate** quantity: measured on this scene, the ensemble sd of
  total water area is 3.5× larger at 3 px correlation and 8× larger at 10 px than under
  i.i.d. noise, at an unchanged mean (§4.1).
- **Negative reflectance is not clipped.** Clipping at zero would bias the mean upward
  exactly on the darkest (water) pixels and silently rectify the noise distribution.

Clipping/asymmetry effects and the case for a heteroscedastic, band-correlated noise
covariance rather than a diagonal one are the natural extension of this model
(cf. GUM/Monte-Carlo propagation, JCGM 101:2008).

### 3.2 Spectral indices

Four indices are computed per realisation on the perturbed stack:

| Index | Formula as wired | Reference |
|---|---|---|
| NDWI | (GREEN − NIR)/(GREEN + NIR) | McFeeters 1996 |
| MNDWI | (GREEN − SWIR1)/(GREEN + SWIR1) | Xu 2006 |
| AWEIsh | BLUE + 2.5·GREEN − 1.5·(NIR + SWIR1) − 0.25·SWIR2 | Feyisa et al. 2014 |
| MBWI | 3·GREEN − RED − NIR − SWIR1 − SWIR2 | Wang et al. 2018 |

**The stack requires all six bands.** AWEIsh and MBWI both reference SWIR2 (B12). If the
fetch delivers fewer bands, those two expressions fail and the stack silently drops to two
indices, turning the *k*-of-4 vote below into a *k*-of-2 vote. This is not hypothetical: it
occurred in this project because one imagery backend carried a hardcoded five-band asset
list that ignored the requested band set, and it surfaced only as an unrelated
`name 'B6' is not defined` error downstream. **Any result must therefore be accompanied by
the delivered band count**, and the band count is now asserted rather than assumed.

Guarding is **asymmetric across the four indices**, and this matters for how the vote
behaves:

- **NDWI and MNDWI** go through the normalised-difference path and *are* guarded: pixels
  with non-finite inputs, near-zero denominators (`|x+y| < 1e-6`) or a reflectance below
  `valid_min` return NaN rather than a fabricated ratio, and the output is clamped to
  [−1, 1]. `valid_min = −0.05` as wired. With `σ_abs = 0.005` a −0.05 excursion is a
  ~10 σ event, so in practice this guard essentially never fires; it is protection against
  atmospheric-correction artefacts, not against the noise model.
- **AWEIsh and MBWI** are free-form linear expressions and are **not** guarded at all.
  Being linear they have no denominator to blow up, but they also never abstain. They are
  clamped to [−5, +5] rather than [−1, +1], since neither is a normalised ratio; that range
  is wide enough not to bind in practice, but it is a display/serialisation bound and not a
  physical one.

The consequence is structural, not cosmetic: over water AWEIsh > 0 and MBWI > 0 both hold
robustly, so **those two alone already reach `k = 2`**. The effective rule is closer to
`AWEIsh ∧ MBWI` than to a four-way consensus, and the two dominant indices are the ones
whose `> 0` criterion is least standard (Wang et al. threshold MBWI dynamically rather than
at zero). A further caveat: invalid data votes *against* water — `NaN > 0` evaluates to
false — so a guarded pixel is treated as evidence of land rather than as an abstention.

The claim that the four indices span complementary physics was **tested, and it does not
hold.** Spearman correlation between the four, measured in the corridor on the unperturbed
scene:

| | NDWI | MNDWI | AWEIsh | MBWI |
|---|---|---|---|---|
| **NDWI** | 1.000 | 0.867 | 0.894 | 0.758 |
| **MNDWI** | 0.867 | 1.000 | 0.881 | 0.828 |
| **AWEIsh** | 0.894 | 0.881 | 1.000 | **0.947** |
| **MBWI** | 0.758 | 0.828 | 0.947 | 1.000 |

The correlation matrix has eigenvalues **3.73, 0.16, 0.09, 0.02** — 93 % of the variance in
a single component. The effective number of independent indices is **2.0** (Li & Ji) or
**1.51** (Cheverud–Nyholt), against a nominal four.

The vote is dominated by one index. **AWEIsh agrees with the final *k*-of-2 verdict
99.92 % of the time**, and in 94.0 % of detected water AWEIsh and MBWI alone already reach
`k = 2`. The vote-sum histogram in the corridor is almost perfectly bimodal — 246 794
pixels with no index voting water, 84 685 with all four, and only 11 062 in the contested
2–3 band.

Leave-one-out and single-index ablation, deterministic on the unperturbed scene:

| rule | IoU | MCC | precision | recall |
|---|---|---|---|---|
| **all four, k = 2 (as wired)** | **0.7911** | **0.8412** | 0.9763 | 0.8066 |
| all four, k = 1 | 0.8152 | 0.8558 | 0.9581 | 0.8453 |
| all four, k = 3 | 0.7678 | 0.8266 | 0.9876 | 0.7752 |
| all four, k = 4 | 0.7207 | 0.7931 | 0.9914 | 0.7252 |
| drop NDWI (k = 2 of 3) | 0.7760 | 0.8304 | 0.9782 | 0.7896 |
| drop MNDWI (k = 2 of 3) | 0.7830 | 0.8372 | 0.9855 | 0.7921 |
| drop AWEIsh (k = 2 of 3) | 0.7678 | 0.8266 | 0.9876 | 0.7753 |
| drop MBWI (k = 2 of 3) | 0.7910 | 0.8411 | 0.9763 | 0.8065 |
| **AWEIsh alone** | **0.7917** | **0.8414** | 0.9753 | 0.8078 |
| MNDWI alone | 0.7806 | 0.8305 | 0.9637 | 0.8043 |
| MBWI alone | 0.7633 | 0.8238 | 0.9895 | 0.7695 |
| NDWI alone | 0.7603 | 0.8198 | 0.9826 | 0.7706 |

**A single index matches the four-index consensus** — AWEIsh alone scores 0.7917 IoU
against the vote's 0.7911. Removing MBWI changes the result by 0.0001. The consensus is
not adding information; it is re-measuring the same quantity four times.

Two consequences the paper must carry rather than bury:

1. **The decision rule should be described as "a multi-index vote dominated by AWEIsh",
   not as independent corroboration.** The physics-complementarity argument is falsified
   on this scene.
2. **`k = 2` is not the best operating point.** `k = 1` scores higher on both IoU (0.8152)
   and MCC (0.8558). The wired `k = 2` buys precision (0.976 vs 0.958) at a larger cost in
   recall. That is a defensible trade-off for a water product, but it is a choice, and it
   should be reported as one rather than presented as consensus logic.

### 3.3 Decision rule — multi-index vote ∧ adaptive reflectance gate

A pixel is water in a given realisation iff **both** conditions hold:

**(a) Multi-index vote.** At least **k = 2 of 4** indices are positive
(`Σ 1[index > 0] ≥ 2`), evaluated as `(1*(B1>0)+1*(B2>0)+1*(B3>0)+1*(B4>0)) >= 2` on the
four-band index stack — which is why a missing band silently weakens the rule (§3.2). No index is privileged and no index-specific magic threshold is
introduced; the sign convention of each index is its own published water criterion.
Requiring agreement between two physically distinct index families suppresses the
characteristic failure modes of each (NDWI over built-up shadow, MNDWI over dark
vegetation).

**(b) Adaptive reflectance gate.** The pixel must additionally satisfy upper caps in
NIR, SWIR1 and SWIR2 — a *physical* plausibility condition (water absorbs strongly
beyond ~900 nm), which rejects shadows and dark asphalt that can pass index tests.
The caps are **derived from the scene, not fixed**:

1. On the **unperturbed** stack, compute the consensus set (pixels with vote ≥ 2).
2. Cap for each of NIR/SWIR1/SWIR2 = the **99th percentile** of that band over the
   consensus set, floored at 2× a conservative fixed default
   (NIR 0.12 / SWIR1 0.06 / SWIR2 0.05).
3. If fewer than 500 consensus pixels exist, fall back to the fixed defaults and record
   `adaptive = false`.
4. Caps are **frozen for the entire Monte-Carlo run** (cached against a signature of the
   base scene) and then applied to the **perturbed** bands.

Freezing the caps is essential for interpretability: if the gate re-derived itself from
each noisy realisation, the ensemble would mix *decision-rule* variability with
*measurement* variability and `σ_P` would no longer be a propagated measurement
uncertainty. This is the separation of epistemic from aleatoric uncertainty made
operational at the level of the graph wiring.

A brightness *floor* was tried and deliberately removed: any minimum-signal condition
deletes pure dark open water, which is the primary target.

---

## 4. Ensemble accumulation

`N` realisations are accumulated per pixel. In the wired configuration the driver's
`max_ticks` parameter is 200, but a connected scalar overrides it with **118**, and the
same scalar sets the mean accumulator's target, so `N = 118`. That value is hand-set and
does not come from the stopping criterion of §5.7 — a point the paper should resolve rather
than leave as an inconsistency.

- **Mean accumulator** → `P(water) = (1/N) Σ_i m_i(x)`, the fraction of realisations
  classifying the pixel as water. Stored as an 8-bit image; `P` is recovered as
  `value/255`.
- **Std accumulator** → `σ_P(x)`, the per-pixel ensemble standard deviation.
  **Caveat (see `MC-paper-weaknesses.md`, BLOCKER 3): this is not an independent
  product.** Because each realisation's per-pixel outcome is binary and realisations are
  i.i.d., the per-pixel count is `Binomial(N, P)` and therefore
  `σ_P = √(P(1−P))` identically, up to `O(1/√N)` sampling error. Measured
  `R² = 0.9999` against that envelope, unchanged by spatial correlation. The map is a
  deterministic transform of `P`; it highlights the contested pixels (it peaks at
  `P = 0.5`) but carries no information `P` does not already carry.
  The informative ensemble quantities are **aggregate**: the ensemble sd of total water
  area differs by a factor ≈ 8 between i.i.d. and 3 px-correlated noise, which the
  per-pixel map cannot see.

  Note that `σ_P` is recovered from the accumulator's 8-bit output as
  `σ_P = main · scale / 255²` (the node emits `scale`); the graph runs the std
  accumulator with `normalize = false`.

The standard error of the scene-mean probability is `SE = ⟨σ_P⟩ / √N`.

### 4.1 Ensemble statistics of derived quantities — the uncertainty product

Because the per-pixel std is an identity (`√(P(1−P))`, see above), the paper's uncertainty
product is the **ensemble distribution of per-realisation aggregates**, accumulated by a
dedicated node (`sci_ensemble_stats`) on the same mask stream that feeds the mean
accumulator. One value is stored per realisation, per metric:

| Metric | What it answers |
|---|---|
| `area` | Uncertainty of total water extent — the headline hydrological quantity |
| `perimeter` | Shoreline raggedness / shape stability under perturbation |
| `components` | Does the channel fragment in some realisations? |
| `largest` | Is the main water body stable, or does it split? |
| `centroid_x/y` | Positional stability of the detected water |
| `boundary_dist` | Mean distance from each realisation's boundary to the reference boundary — shoreline positional error, with both its bias (mean) and its spread (sd) |

Each metric is reported as mean / sd / **coefficient of variation** / percentile CI
(95 % by default) / min / max, with histograms. The CI is a **percentile interval over
actual realisations**, not a bootstrap over pixels — so unlike the pixel-level intervals
of §5.2 and §5.6 it does not assume pixel independence and is not corrupted by spatial
autocorrelation. Each realisation is one genuinely independent draw from the noise model.

**Why these carry information the mean map does not.** A per-pixel marginal cannot see
error *correlation*. An aggregate can. Under i.i.d. pixel noise the per-pixel errors
cancel in a sum; under spatially correlated noise whole patches move together and no
cancellation occurs.

Measured on the real acquisition — the full wired pipeline, 118 realisations per
correlation length, corridor domain:

| noise correlation | mean area (px) | **sd (px)** | CV | × i.i.d. | 95 % CI width (px) |
|---|---|---|---|---|---|
| 0 px (i.i.d.) | 102 716.0 | **72.1** | 0.00070 | 1.00 | 280 |
| 1 px | 102 717.6 | **117.3** | 0.00114 | 1.63 | 427 |
| **3 px (as wired)** | 102 717.3 | **253.9** | 0.00247 | **3.52** | 952 |
| 10 px | 102 773.9 | **576.6** | 0.00561 | **8.00** | 2 098 |

The control is what makes this conclusive. Across all four runs the **mean area is
unchanged** (102 716 → 102 774, a spread of 0.06 %), the **mean probability over the
domain is identical to four decimals** (0.2796 / 0.2796 / 0.2796 / 0.2797), and the
fraction of graded pixels barely moves (7.43 / 7.41 / 7.39 / 7.32 %). The marginal
probability field is invariant while the ensemble spread of the derived quantity varies
**eightfold**. That is the theoretical claim of §4 made visible: per-pixel marginals
cannot see error correlation, aggregates can.

Other aggregates move in the same direction and carry their own physical reading:

| corr | perimeter | components | boundary distance to GT (px) |
|---|---|---|---|
| 0 px | 28 406 ± 74 | 2584 ± 28 | 24.1 ± 0.2 |
| 1 px | 26 956 ± 84 | 2346 ± 26 | 24.9 ± 0.2 |
| 3 px | 26 068 ± 108 | 2246 ± 28 | 25.3 ± 0.3 |
| 10 px | 25 903 ± 170 | 2241 ± 40 | 25.5 ± 0.5 |

Mean perimeter *falls* as correlation rises (28 406 → 25 903) and the component count
falls with it: correlated error produces smoother, less speckled boundaries, where i.i.d.
error shreds them. The *spread* of every one of these grows — perimeter sd 74 → 170,
component sd 28 → 40, boundary-distance sd 0.2 → 0.5.

This is the study's central quantitative claim: **error models that assume spatial
independence — the implicit default in most index-based water mapping — understate the
uncertainty of water-area estimates by a factor of 3.5 at a 3 px correlation length and
8 at 10 px.** The correlation length is therefore not a nuisance parameter to be defended
in an appendix; it is the controlling variable of the result, and area uncertainty is
reported as a function of it. What the noise model does *not* change is the mask itself —
so a paper reporting only masks and per-pixel probabilities would have found nothing here.

Implementation notes: memory is `O(N · metrics)` (one float per metric per realisation,
never `N` frames), the histogram figure is redrawn on a stride rather than every tick
(a matplotlib render per realisation would dominate a several-hundred-draw run), the
ensemble auto-resets when the upstream driver's tick drops, and a mid-run grid change
resets rather than mixing incomparable areas.

---

## 5. Validation protocol

The validation is deliberately layered, because each layer answers a different objection.
Notably, **two of the five layers require no threshold at all**, which is the point: a
probability field must be validated as a probability field before any mask is defended.

### 5.1 Layer 1 — Threshold-independent rank agreement (Spearman)

Spearman rank correlation between `P(water)` and each spectral index, computed separately
for three pixel classes:

| Class | Definition |
|---|---|
| **All river** | the analysis domain = ground-truth water **dilated** (elliptical SE, size 15, 2 iterations ≈ 5 % corridor margin), after small-object removal (`min_area = 258 px`) |
| **Open water** | ground-truth water |
| **Land** | domain ∧ ¬water — non-water land/sediment inside the corridor |

Rank correlation is used rather than Pearson because the `P`–index relation is monotone
but strongly non-linear (saturating), and because ranks are invariant to the arbitrary
scaling of AWEIsh/MBWI. Scatter panels (≤ 4000 points subsampled per class, fixed seed)
accompany the bar chart so the *shape* of the relation — not just a coefficient — is
visible.

Restricting to a dilated corridor rather than the whole tile is a substantive choice: a
full-scene evaluation is dominated by trivially-dry pixels far from any water, which
inflates every metric and hides the only errors that matter, the ones at the water/land
transition. This is the same concern that motivates boundary-aware metrics (§5.4).

### 5.2 Layer 2 — Class separation with effect size and a non-parametric test

Per feature (`P` itself, plus each index), open-water vs land distributions are compared:

- **Δμ** — raw mean gap.
- **Cohen's *d*** — pooled-σ-normalised effect size, so features on different scales are
  comparable.
- **Mann–Whitney *U*** two-sided test with **rank-biserial correlation** as effect size —
  non-parametric, no normality assumption (index distributions are heavily skewed and
  bimodal). Groups are subsampled to 20 000 px (fixed seed) for tractability.

Effect size is reported alongside the *p*-value on purpose: with 10⁵–10⁶ pixels every
comparison is "significant", so *p* alone is uninformative and reporting it alone would
be a textbook misuse (Sullivan & Feinn 2012). Pixels are also spatially autocorrelated,
so *p*-values must be read as descriptive, not as valid inference on independent samples
(Clifford et al. 1989) — the effect sizes carry the argument.

### 5.3 Layer 3 — Non-circular index ranking (AUROC, *P*-free)

The Spearman layer measures agreement between `P` and the indices — but `P` is *built*
from those indices, so a high correlation is partly circular. To break the circularity,
the discriminability of **each index against the ground truth** is computed directly as
**AUROC** (water vs non-water inside the corridor), never touching `P`. AUROC is computed
from the rank-sum identity (Mann–Whitney equivalence) and oriented to ≥ 0.5.

This gives an independent ranking of index quality on this scene, against which the
ensemble's implicit weighting can be judged.

### 5.4 Layer 4 — Mask-level metrics (threshold-dependent)

Once a threshold is chosen (§5.6), the binary mask is scored against ground truth:

- **Overall accuracy** `OA = (TP+TN)/N`, **plus balanced accuracy**
  `= mean(recall_water, recall_land)`, `recall_water`, `recall_land` and the full
  confusion matrix, evaluated **inside the corridor**. OA is reported *with* its
  companion precisely because water is rare: a mask predicting "no water everywhere"
  already scores very high OA, so OA alone is close to meaningless under class imbalance.
- **IoU / F1 / precision / recall** via the mask-metrics node, with overlay
  (α = 0.45, IoU threshold 0.5).
- **Boundary F1** with a 3-pixel tolerance (Csurka et al. 2013; Perazzi et al. 2016).
  Region metrics like IoU are dominated by the large interior of water bodies and are
  nearly blind to shoreline placement; boundary F1 scores exactly the shoreline, which is
  where a 10 m sensor and a Monte-Carlo ensemble actually disagree. The 3 px tolerance
  acknowledges that ground truth (WorldCover, itself a classified product) is not
  sub-pixel accurate.

#### Domain sensitivity — measured, not assumed

The evaluation domain is the ground truth dilated by a chosen radius, so every mask
metric is a function of that radius. Measured on the primary acquisition (N = 118, 3 px
noise correlation, threshold fixed at the value selected on the wired 15 px corridor):

| domain | pixels | IoU | F1 | precision | recall | MCC | own t* |
|---|---|---|---|---|---|---|---|
| GT only | 113 827 | 0.8606 | 0.9251 | 1.0000 | 0.8606 | n/a | 0.02 |
| + 5 px | 207 230 | 0.8353 | 0.9102 | 0.9667 | 0.8600 | 0.8197 | 0.02 |
| **+ 15 px (wired)** | 349 074 | **0.8249** | **0.9041** | 0.9574 | 0.8564 | **0.8631** | 0.02 |
| + 31 px | 552 694 | 0.8135 | 0.8971 | 0.9462 | 0.8529 | 0.8731 | 0.02 |
| whole scene | 3 853 696 | 0.7333 | 0.8461 | 0.8436 | 0.8487 | 0.8412 | **0.30** |

Three things this settles:

1. **IoU spans 13 points** (0.861 → 0.733) purely as a function of the evaluation window.
   A reported IoU is meaningless without its domain, which is why the table is published
   rather than a single figure.
2. **Recall is essentially constant** (0.853–0.861) while precision falls from 1.000 to
   0.844. Widening the domain adds only false positives — the corridor is not hiding
   missed water, it is hiding spurious water.
3. **The selected threshold is itself domain-dependent**: 0.02 inside any corridor, 0.30
   on the whole scene. Threshold selection and domain choice are not independent, and
   reporting one without the other is incomplete.

MCC is **undefined on the GT-only domain**: with the domain equal to the truth there are
no true negatives and the denominator vanishes. That is a property of the metric, not a
result, and it is why the corridor cannot be tightened to zero.

#### False positives beyond the corridor

Restricting to a corridor makes distant false positives invisible, so they are audited
separately. Predicted water lying **outside the widest (31 px) corridor**:

| | |
|---|---|
| pixels | 13 715 — **11.5 % of all predicted water** |
| connected components | 3 099 |
| largest component | 305 px |
| components above 100 px | 6 |

The share is not negligible, but its shape is: 3 099 components averaging 4 px each, with
nothing resembling a spurious lake. This is speckle, not systematic misclassification, and
a minimum-area filter would remove most of it at a known cost in recall. Reporting the
component-size distribution rather than the bare percentage is what separates those two
diagnoses.

The same scoring is intended to be run with the Monte-Carlo stage bypassed
(single deterministic evaluation), so the comparison "MC vs no MC" is measured on
identical metrics and the same domain.

### 5.5 Layer 5 — Probability calibration

The strongest claim in the paper is that `P` is a *probability*, not a score. That claim
is tested, not asserted:

- **Brier score** — mean squared error between `P` and the binary outcome (Brier 1950).
- **Reliability diagram** over 12 equal-width bins of `P`, with the bin-population
  histogram underneath (DeGroot & Fienberg 1983; Niculescu-Mizil & Caruana 2005).
- **ECE** (population-weighted mean |accuracy − confidence|) and **MCE** (worst bin)
  (Guo et al. 2017).
- **⟨U⟩**, mean uncertainty, taken from the MC ensemble std map when available, falling
  back to the Bernoulli predictive variance `P(1−P)`.

A well-ranked but poorly calibrated `P` would show high AUROC with a reliability curve far
from the diagonal. **That is what happens.** Measured on the primary acquisition, in the
corridor (n = 338 172):

| | |
|---|---|
| Brier score | 0.0668 |
| ECE (12 equal-width bins) | 0.0670 |
| ECE (equal-mass bins) | 0.0670 |
| **MCE (worst bin)** | **0.5981** |
| ⟨U⟩ | 0.0268 |

ECE of 0.067 is modest, but **MCE of 0.60 means the worst-populated bin is 60 percentage
points away from the diagonal**. `P` orders pixels well and is badly calibrated as a
probability: a pixel at `P ≈ 0.6` is not water 60 % of the time.

The equal-mass recomputation makes the reason visible. Asking for 12 quantile bins yields
**only 2 distinct bins**, because `P` is concentrated on a handful of values — the
vote-sum histogram of §3.2 shows why, with 98 % of corridor pixels at vote 0 or vote 4.
There is not enough spread in `P` for a 12-bin reliability curve to mean anything.

So the honest claim is **"`P` is a calibrated-in-rank confidence score, not a calibrated
probability"**, and the paper should not describe it as the latter. Post-hoc
recalibration (isotonic or Platt, fitted out-of-sample) is the obvious remedy and is not
attempted here. Reporting both ECE variants and the realised bin count, rather than a
single ECE, is what exposes this — a lone ECE of 0.067 would have read as a pass. Note that the ECE
computed here is an *empirical spatial frequency* over pixels in the corridor: it is a
statement about how often pixels at `P ≈ q` are labelled water in this scene, and it
inherits any bias in the reference product.

### 5.6 Threshold selection as a measurement, not a choice

The final mask threshold is **not** hand-set. A sweep over `t ∈ [0, 1]` (step 0.02)
recomputes the full confusion matrix at every `t` and reports precision, recall, F1, IoU,
Youden's J and MCC. **MCC is the metric being optimised** in the wired configuration
(selector = 3); the others are reported alongside so the trade-off is visible. MCC is included because, unlike F1 and IoU, it uses all four
confusion cells including true negatives and is the appropriate balanced summary under
class imbalance (Matthews 1975; Chicco & Jurman 2020).

The selection rule is the methodologically interesting part, and it is built to be robust
to the failure mode that actually occurs:

1. **Plateau detection.** Collect every `t` scoring ≥ 99 % of the maximum;
   `plateau_fraction` = that share of the range. Because `P` is close to binary, the
   metric curve is a cliff near 0 followed by a near-flat plateau — the raw `argmax`
   lands on the first point after the cliff, which is an artifact of the cliff, not a
   meaningful cut.
2. **Neither extreme is acceptable.** Taking the highest `t` within tolerance degenerates
   to `t ≈ 1` when the whole range is flat — equally arbitrary. The fallback is therefore
   the **median of the tolerance-satisfying thresholds**, which centres the pick inside
   whatever plateau exists.
3. **Semantic anchor.** When the plateau exceeds 30 % of the range, the sweep prefers
   `t = 0.5` — the Monte-Carlo **majority vote**, a threshold with a meaning independent
   of this scene's ground truth and therefore transferable — *provided* the cost of
   snapping is small (≤ 0.03 metric points absolute). The cost is **always reported**,
   so the trade-off between GT-fitted optimality and transferability is explicit rather
   than buried.
4. **Bootstrap 95 % CI.** Optional resampling of domain pixels with replacement
   (≈ 203 replicates as wired, ≤ 40 000 px subsample, fixed seeds) puts a confidence
   band around the metric-vs-threshold curve and reports
   `frac_thresholds_within_best_CI` and a boolean
   `threshold_statistically_distinguishable` (true iff < 50 %). The explicit stance in
   the code is that statistical distinguishability is **not** the snapping criterion:
   with 10⁵ pixels a sub-point difference is significant yet practically irrelevant, so
   the decision is made on **absolute score cost**. (The bootstrap resamples pixels
   independently, which ignores spatial autocorrelation and therefore *understates* the
   CI width — a known conservative-in-the-wrong-direction caveat worth stating in the
   paper.)

The chosen threshold is then fed back into the graph as the operating point of the
advanced-threshold node, so every mask metric in §5.4 is computed at a threshold that was
*derived*, with its selection rule, plateau width and anchor cost on the record.

#### Out-of-sample transfer

The threshold is selected on 2021-09-02 and applied unchanged to two held-out
acquisitions — same tile (31UDQ), same orbit (51), so directly comparable. Selection by
raw argmax in all three cases, for a like-for-like comparison:

| date | held out | IoU @ t\* | MCC @ t\* | own t\* | MCC @ own t\* | transfer cost |
|---|---|---|---|---|---|---|
| 2021-09-02 | — | 0.8249 | 0.8631 | 0.02 | 0.8631 | — |
| **2021-06-14** | **yes** | 0.7708 | 0.8231 | 0.02 | 0.8231 | **0.0000** |
| **2021-03-01** | **yes** | 0.8726 | 0.8999 | 0.02 | 0.8999 | **0.0000** |

**The threshold transfers at zero cost**: each held-out date selects exactly the same
value it was given. That is the in-sample/out-of-sample gap the protocol was built to
expose, and here it is empirically nil.

Two honest qualifications:

- The agreement is partly structural. At raw argmax the selected value sits at the bottom
  of the range on every scene, so identical selection is less informative than it looks.
  The comparison under the graph's plateau-median rule (`t = 0.08` on the primary scene)
  has not been run on the held-out dates and should be, since that is the rule the paper
  actually proposes.
- **Accuracy does not transfer even though the threshold does.** MCC ranges 0.823–0.900
  and IoU 0.771–0.873 across the three dates, a spread several times larger than anything
  threshold selection contributes. Scene conditions, not the cutoff, dominate
  performance variance — which is an argument for reporting multiple dates rather than
  for tuning the threshold harder.

#### What the rule actually selects on this scene

Measured on the primary acquisition (MCC, step 0.02, wired 15 px corridor):

| t | 0.02 | 0.10 | 0.30 | 0.50 | 0.70 | 0.90 | 0.98 |
|---|---|---|---|---|---|---|---|
| MCC | **0.8621** | 0.8564 | 0.8477 | 0.8397 | 0.8285 | 0.7967 | 0.7499 |

| quantity | value |
|---|---|
| raw argmax | t = 0.02, MCC 0.8621 |
| plateau fraction (within 99 % of max) | **0.157** |
| plateau median — **what the rule selects** | **t = 0.08, MCC 0.8575** |
| semantic anchor (majority vote) | t = 0.50, MCC 0.8397 |
| anchor cost | 0.0223 |

The plateau covers 15.7 % of the range, **below the 30 % trigger**, so the rule does not
snap to the anchor: it returns the plateau median, `t = 0.08`. The raw argmax at 0.02 is
rejected as the cliff artifact it is, at a cost of 0.005 MCC.

This is worth recording because it reverses an earlier reading. The code carries a warning
for a "flat metric" that "barely discriminates", written when the curve was nearly
featureless. With the imagery in correct reflectance units (§3.2) the curve has real
structure — MCC falls monotonically by 11 points from t = 0.02 to t = 0.98 — and the flat-
metric warning no longer fires. **The degenerate threshold curve was a symptom of the unit
bug, not a property of the method.**

### 5.7 Convergence — how many realisations are enough?

> **Caveat, see `MC-paper-weaknesses.md` BLOCKER 3:** because `σ_P = √(P(1−P))` is an
> identity, `SE = ⟨σ_P⟩/√N` reduces to `√(P(1−P)/N)` and falls off as `1/√N` regardless
> of the pipeline's behaviour. It is a restatement of `N`, not a convergence diagnostic.
> The convergence criterion that carries meaning is the stabilisation of the **ensemble
> aggregate statistics** of §4.1 — `sd(area)`, `sd(boundary_dist)` — which are not
> functions of `P`. The `SE` machinery below is retained because it still bounds the
> sampling error of `P` itself, but it must not be presented as evidence that the
> ensemble has converged.

`SE(N) = ⟨σ_P⟩ / √N` is tracked over ticks (one point per distinct `N`, history reset
when a new run starts) and plotted on a log axis. **Optimal `N`** = the first `N ≥ N_min`
(wired: 5) with `SE < tol` (wired: 0.005; code default 0.01). This converts the ensemble
size from an arbitrary round number into a **reported stopping criterion with a stated
tolerance in probability units** — the standard practice for Monte-Carlo uncertainty
propagation (JCGM 101:2008 §7.9 adaptive procedure).

---

### 5.8 Baselines

A probability field is only worth its cost against something simpler.

| method | IoU | MCC | precision | recall |
|---|---|---|---|---|
| **Monte-Carlo ensemble, t = 0.02** | **0.8249** | **0.8631** | — | — |
| Otsu on MNDWI | 0.7947 | 0.8342 | 0.9264 | 0.8483 |
| AWEIsh > 0 (published rule) | 0.7910 | 0.8406 | 0.9743 | 0.8078 |
| **same rule, single deterministic run (MC bypassed)** | **0.7911** | **0.8412** | 0.9763 | 0.8066 |
| MNDWI > 0 (published rule) | 0.7798 | 0.8296 | 0.9625 | 0.8043 |
| MBWI > 0 | 0.7633 | 0.8238 | 0.9895 | 0.7695 |
| NDWI > 0 | 0.7602 | 0.8197 | 0.9825 | 0.7706 |
| Otsu on AWEIsh | 0.5852 | 0.6127 | 0.5892 | 0.9886 |
| Otsu on NDWI | 0.5741 | 0.5873 | 0.5973 | 0.9365 |
| Otsu on MBWI | 0.4518 | 0.4230 | 0.4523 | 0.9977 |

**The Monte-Carlo ensemble does win**, by +0.034 IoU and +0.022 MCC over the identical
rule run once without noise. The mechanism is the regularisation effect of §6: averaging
perturbed realisations fills gaps and suppresses speckle.

But the margin must be stated honestly. The nearest baseline is **one line of code** —
Otsu on MNDWI, 0.7947 IoU — and the ensemble beats it by 0.030 IoU. A reader is entitled
to ask whether 118 realisations are worth three IoU points, and the answer for a
mask-only application is probably no. **The case for the ensemble is the uncertainty it
quantifies, not the mask it produces** — which is the same conclusion §4.1 reaches from
the other direction.

Otsu behaves erratically on three of the four indices (IoU 0.45–0.59, recall ≈ 0.99,
precision ≈ 0.5): inside a river corridor the histogram is not bimodal, so Otsu's
assumption fails and it cuts far too low. That is itself an argument for the paper's
thesis about thresholds — but it also means "Otsu" is not a single baseline, it is four
very different ones, and reporting only the best would be cherry-picking.

## 6. Reproducibility, and what the design deliberately exposes

- **All seeds fixed**: noise 42 (drawn as `seed + tick`, so realisation *i* is
  reproducible individually), scatter subsampling 0, Mann–Whitney 0, bootstrap 12345,
  bootstrap subsample 0.
- **Full acquisition provenance recorded**: STAC item ID, sensing time, tile, orbit and
  the delivered band list, not just the date range. This is not bookkeeping — a backend in
  this project silently delivered five of six requested bands, which would have produced a
  *k*-of-2 vote reported as *k*-of-4 with nothing in the output to reveal it (§3.2).
  Delivered band count is now recorded with every run.
- **References are fetched onto the Sentinel-2 grid**, so no resampling of the reference is
  needed; the dated reference carries an explicit **validity mask** (its source band is
  ternary, with `0 = not observed`) and all metrics are restricted to observed pixels.
  Requesting a month outside the dataset's 1984-03 … 2021-12 coverage fails loudly instead
  of returning a plausible empty mask.
- **Defensive shape handling** everywhere (common-extent crop, explicit assertions on grid
  mismatch) — the code refuses to compare misaligned grids rather than silently
  broadcasting them.
- **The whole protocol is one executable graph**, so figures and numbers are regenerated
  from the wiring rather than from a chain of ad-hoc scripts.

Known caveats the paper should state rather than hide:

1. **`σ_abs` is the most consequential free parameter, and performance cannot be used to
   choose it.** Sweep on the primary acquisition (N = 118, 3 px correlation, 15 px
   corridor), now that the imagery is in reflectance units:

   | σ_abs | mean area (px) | sd (px) | graded pixels | mean P | t* | MCC | IoU |
   |---|---|---|---|---|---|---|---|
   | 0.0010 | 103 304 | 77.4 | 1.71 % | 0.2738 | 0.02 | 0.8487 | 0.8031 |
   | 0.0025 | 103 196 | 129.7 | 3.38 % | 0.2733 | 0.02 | 0.8552 | 0.8127 |
   | **0.0050 (wired)** | **102 717** | **253.9** | **7.19 %** | 0.2712 | 0.02 | **0.8631** | **0.8249** |
   | 0.0100 | 101 150 | 482.9 | 16.63 % | 0.2639 | 0.02 | 0.8717 | 0.8391 |
   | 0.0200 | 98 794 | 855.4 | 34.34 % | 0.2429 | 0.14 | 0.8743 | 0.8424 |

   **IoU and MCC increase monotonically with the assumed noise, across the whole tested
   range** — IoU 0.803 → 0.842, MCC 0.849 → 0.874, with no interior optimum. The
   mechanism is straightforward: averaging more perturbed realisations regularises the
   mask, filling gaps and suppressing speckle, which improves agreement with a 10 m
   reference.

   The consequence is a methodological constraint, not a tuning opportunity.
   **Choosing `σ_abs` by maximising accuracy would drive it arbitrarily high**, so it must
   be fixed from independent radiometric evidence and the curve reported — which is what
   this table is for. Conclusions are *not* invariant to it: 4 IoU points and an
   elevenfold range in ensemble spread (77 → 855 px) across a plausible interval. Mean
   area also falls by 4.4 % as σ rises, so the estimate itself is mildly noise-dependent.

   The other two parameters are unswept: `σ_rel` and the band-space correlation structure.
   The noise correlation *length* is swept in §4.1, where it is the controlling variable
   of the headline result.
2. The noise model is diagonal in band space. Real atmospheric-correction residuals are
   correlated across bands, which would change index-level variance.
3. Reference-product error is **measured, not assumed** (§2.3): the two references agree
   at IoU 0.7308 in the corridor domain (0.7177 whole-scene) and 0.974–0.996 in their
   eroded cores. The residual is a
   validation ceiling, and it is reported alongside every mask metric. The unresolved part
   is that neither reference is annotated at 10 m on the acquisition itself, so boundary
   claims remain limited by reference resolution rather than by the method.

4. **Transferability is untested.** The finding that an annual permanent-water reference
   is adequate here rests on the Seine being a regulated, largely permanent river. On a
   tidal or strongly seasonal system the temporal term would likely dominate instead of
   being ~2.6 %, and the reference choice would have to change. One AOI, one date — every
   number in this paper should be read as conditional on that.
5. **The vote is not the four-way consensus it appears to be.** Three of four indices use
   NIR, all four use GREEN, and the two unguarded linear indices reach `k = 2` unaided
   (§3.2). Until the correlation matrix and the leave-one-out ablation are reported, the
   decision rule should be described as "a multi-index vote", not as independent
   corroboration.
6. **Noise terms combine linearly rather than in quadrature** (§3.1), overstating σ by
   ≈ 34 % on bright land. Conservative for the water class, but it inflates the apparent
   difficulty of the negative class.
7. **The decision rule exists in two implementations.** The adaptive gate re-derives the
   vote internally to select its calibration pixels, using a different validity floor
   (−0.002) from the production path (−0.05). No bias today, since calibration runs on the
   unperturbed scene where neither guard fires, but the duplication will drift.
8. Pixel-level `p`-values and bootstrap CIs ignore spatial autocorrelation and are
   reported as descriptive statistics. The ensemble percentile CIs of §4.1 are not
   affected — realisations are genuinely independent.
9. In the wired graph the corridor domain is connected to the convergence and
   overall-accuracy nodes; the threshold-sweep, calibration and index-correlation nodes
   fall back to the whole-scene domain when that input is left unconnected. For the
   published figures the domain should be wired consistently to all five, since a
   whole-scene domain inflates every metric for the reason given in §5.1.

---

## 7. Claimed contributions

1. **Quantified uncertainty of the derived water quantities** — total area, shoreline
   position, connectivity — obtained by Monte-Carlo propagation of a physically motivated
   (spatially correlated, floored) reflectance-noise model through a complete detection
   pipeline, with percentile CIs taken over independent realisations rather than over
   correlated pixels. The headline result: **assuming spatially independent radiometric
   error understates water-area uncertainty by a factor of 3.5 to 8**, depending on the
   correlation length assumed, at identical marginal probabilities.

   **Measured on the real acquisition** (§4.1): 118 realisations per correlation length
   through the full wired pipeline. `sd(area)` = 72.1 / 117.3 / 253.9 / 576.6 px at
   0 / 1 / 3 / 10 px correlation — **×3.5 at the wired 3 px, ×8.0 at 10 px** — while the
   mean area and the mean probability field stay constant to four decimals. The invariance
   of the mean under an eightfold change in aggregate spread is the cleanest available
   demonstration that the effect is real and that per-pixel products cannot see it.

   *Negative companion result, reported explicitly:* the **per-pixel** ensemble std is
   `√(P(1−P))` by identity for any binary-outcome ensemble with i.i.d. realisations, and
   is therefore not an uncertainty product at all — it is a deterministic transform of
   the probability map, unaffected by the noise model's spatial structure. Measured
   `R² = 0.9999` against that envelope (see `MC-paper-weaknesses.md`, BLOCKER 3). Papers
   publishing per-pixel MC std maps for binary classifiers are publishing `√(P(1−P))`.

2. **A per-pixel water probability** `P`, rather than a single hard mask.
3. **A threshold-free validation protocol** (rank correlation, effect sizes with a
   non-parametric test, *P*-free AUROC) that evaluates the probability field before any
   binarisation, plus a **calibration assessment** (Brier/ECE/MCE, reliability diagram)
   that tests whether `P` deserves to be called a probability.
4. **Threshold selection turned into a reported measurement**: plateau-aware selection
   with an explicit semantic anchor at the majority vote, a bootstrap confidence band,
   and a published anchor cost — replacing the eyeballed cut that the literature has
   largely normalised.
5. **A stated Monte-Carlo stopping criterion** instead of an arbitrary ensemble size —
   applied to the quantity that actually converges. `SE = ⟨σ_P⟩/√N` is *not* a usable
   criterion: since `σ_P = √(P(1−P))` identically, that expression reduces to
   `√(P(1−P)/N)` and decreases as `1/√N` by arithmetic, whatever the pipeline does. The
   criterion is instead applied to the **ensemble statistics of the aggregates**: stop
   when the running estimate of `sd(area)` (and of the boundary-displacement sd) is
   stable to within a stated tolerance across added realisations. That is a genuine
   convergence test, because those quantities are not closed-form functions of `P`.
6. **A measured decomposition of the two uncertainty terms — and the finding that the
   one usually propagated is the smaller one.** The scene-adaptive gate is calibrated once
   on the unperturbed scene and frozen, so the ensemble spread is radiometric
   (aleatoric) uncertainty alone. Quantifying the model-form (epistemic) term separately,
   as the spread of the deterministic result across 13 plausible rule variants
   (`k ∈ {1,2,3}` × gate percentile `∈ {95,98,99}`, plus each leave-one-out index subset):

   | term | sd of water area |
   |---|---|
   | aleatoric — radiometric noise, wired settings | **253.9 px** |
   | epistemic — rule variants, `k = 2` only | **3 875 px** (15×) |
   | epistemic — all 13 variants | **7 153 px** (**28×**) |

   Area ranges from 92 485 px (`k = 3`, 95th-percentile caps) to 113 516 px (`k = 1`,
   99th-percentile caps) — a 21 031 px spread, **20 % of the estimate**.

   **Model-form uncertainty exceeds radiometric uncertainty by more than an order of
   magnitude.** A study that propagates only sensor noise — the standard framing, and the
   one this pipeline started from — reports an interval roughly 28× too narrow. This does
   not invalidate the aleatoric analysis; it relocates it. The correct statement is that
   radiometric noise contributes 254 px of area uncertainty *conditional on a fixed
   decision rule*, and that the choice of rule contributes far more.

---

## References

**Water indices and thresholding**
- McFeeters, S.K. (1996). The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features. *Int. J. Remote Sensing* 17(7), 1425–1432.
- Xu, H. (2006). Modification of normalised difference water index (NDWI) to enhance open water features in remotely sensed imagery. *Int. J. Remote Sensing* 27(14), 3025–3033.
- Feyisa, G.L., Meilby, H., Fensholt, R., Proud, S.R. (2014). Automated Water Extraction Index: A new technique for surface water mapping using Landsat imagery. *Remote Sensing of Environment* 140, 23–35.
- Wang, X., Xie, S., Zhang, X., et al. (2018). A robust Multi-Band Water Index (MBWI) for automated extraction of surface water from Landsat 8 OLI imagery. *Int. J. Applied Earth Observation and Geoinformation* 68, 73–91.
- Ji, L., Zhang, L., Wylie, B. (2009). Analysis of dynamic thresholds for the Normalized Difference Water Index. *Photogrammetric Engineering & Remote Sensing* 75(11), 1307–1317.
- Otsu, N. (1979). A threshold selection method from gray-level histograms. *IEEE Trans. Systems, Man, and Cybernetics* 9(1), 62–66.
- Donchyts, G., Schellekens, J., Winsemius, H., et al. (2016). A 30 m resolution surface water mask including estimation of positional and thematic differences using Landsat 8, SRTM and OpenStreetMap. *Remote Sensing* 8(5), 386.

**Reference datasets**
- Pekel, J.-F., Cottam, A., Gorelick, N., Belward, A.S. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature* 540, 418–422. (JRC Global Surface Water)
- Zanaga, D., Van De Kerchove, R., Daems, D., et al. (2022). ESA WorldCover 10 m 2021 v200. Zenodo.

**Radiometric / atmospheric-correction uncertainty**
- Gorroño, J., Banks, A.C., Fox, N.P., Underwood, C. (2017). Radiometric inter-sensor cross-calibration uncertainty using a traceable high-accuracy reference hyperspectral imager. *ISPRS J. Photogrammetry and Remote Sensing* 130, 393–417.
- Doxani, G., Vermote, E., Roger, J.-C., et al. (2018). Atmospheric Correction Inter-Comparison Exercise. *Remote Sensing* 10(2), 352.
- Vermote, E., Justice, C., Claverie, M., Franch, B. (2016). Preliminary analysis of the performance of the Landsat 8/OLI land surface reflectance product. *Remote Sensing of Environment* 185, 46–56.

**Monte-Carlo uncertainty propagation**
- JCGM 101:2008. *Evaluation of measurement data — Supplement 1 to the GUM: Propagation of distributions using a Monte Carlo method.* BIPM.
- Heuvelink, G.B.M., Burrough, P.A., Stein, A. (1989). Propagation of errors in spatial modelling with GIS. *Int. J. Geographical Information Systems* 3(4), 303–322.
- Kennedy, M.C., O'Hagan, A. (2001). Bayesian calibration of computer models. *JRSS B* 63(3), 425–464.

**Metrics, calibration, statistics**
- Brier, G.W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review* 78(1), 1–3.
- DeGroot, M.H., Fienberg, S.E. (1983). The comparison and evaluation of forecasters. *The Statistician* 32, 12–22.
- Niculescu-Mizil, A., Caruana, R. (2005). Predicting good probabilities with supervised learning. *ICML*.
- Guo, C., Pleiss, G., Sun, Y., Weinberger, K.Q. (2017). On calibration of modern neural networks. *ICML*. (ECE / MCE)
- Matthews, B.W. (1975). Comparison of the predicted and observed secondary structure of T4 phage lysozyme. *Biochimica et Biophysica Acta* 405(2), 442–451.
- Chicco, D., Jurman, G. (2020). The advantages of the Matthews correlation coefficient (MCC) over F1 score and accuracy in binary classification evaluation. *BMC Genomics* 21, 6.
- Youden, W.J. (1950). Index for rating diagnostic tests. *Cancer* 3(1), 32–35.
- Mann, H.B., Whitney, D.R. (1947). On a test of whether one of two random variables is stochastically larger than the other. *Annals of Mathematical Statistics* 18(1), 50–60.
- Hanley, J.A., McNeil, B.J. (1982). The meaning and use of the area under a ROC curve. *Radiology* 143(1), 29–36.
- Sullivan, G.M., Feinn, R. (2012). Using effect size — or why the *p* value is not enough. *J. Graduate Medical Education* 4(3), 279–282.
- Clifford, P., Richardson, S., Hémon, D. (1989). Assessing the significance of the correlation between two spatial processes. *Biometrics* 45(1), 123–134.
- Efron, B., Tibshirani, R.J. (1993). *An Introduction to the Bootstrap.* Chapman & Hall.

**Boundary-aware segmentation metrics**
- Csurka, G., Larlus, D., Perronnin, F. (2013). What is a good evaluation measure for semantic segmentation? *BMVC*.
- Perazzi, F., Pont-Tuset, J., McWilliams, B., et al. (2016). A benchmark dataset and evaluation methodology for video object segmentation. *CVPR*. (boundary F-measure)

**Uncertainty in EO classification**
- Kendall, A., Gal, Y. (2017). What uncertainties do we need in Bayesian deep learning for computer vision? *NeurIPS*. (aleatoric vs epistemic)
- Foody, G.M. (2002). Status of land cover classification accuracy assessment. *Remote Sensing of Environment* 80(1), 185–201.
- Olofsson, P., Foody, G.M., Herold, M., et al. (2014). Good practices for estimating area and assessing accuracy of land change. *Remote Sensing of Environment* 148, 42–57.
