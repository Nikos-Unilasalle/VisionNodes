# Which Uncertainty Are We Propagating? A Monte-Carlo Audit of Index-Based Surface-Water Mapping

**Methodology section, prepared for publication.**
Companion material: `MC_PAPER_METHODS.md` (full protocol), `MC_PAPER_WEAKNESSES.md`
(adversarial audit), `mc_paper_ensemble_uncertainty.vn` (executable pipeline).

---

## Abstract

Optical surface-water mapping is routinely performed by thresholding a spectral index, and
the result is routinely reported without an uncertainty estimate. Where uncertainty *is*
estimated, it is almost always obtained by propagating radiometric (sensor) noise through
the detection chain. We report a Monte-Carlo study of a four-index voting pipeline applied
to a single Sentinel-2 L2A acquisition over the Seine corridor downstream of Paris
(2021-09-02, 10:57:29 UTC), in which three uncertainty terms are measured on the same
scene, in the same units, and compared directly.

The term usually propagated is the smallest of the three. Radiometric noise contributes an
ensemble standard deviation of 254 px to the estimated water area; sub-pixel
co-registration error contributes 1 380 px (5.4×); and the choice of decision rule —
varying the vote threshold and the gate percentile within plausible bounds — contributes
7 153 px (28×), a spread equal to 20 % of the estimate itself. We further show that the
per-pixel ensemble standard deviation, frequently published as an uncertainty map, is
mathematically redundant with the probability map it accompanies: for a binary outcome
with independent realisations it equals `√(P(1−P))` identically (measured R² = 0.9999),
and is insensitive to the spatial structure of the perturbation that dominates every
aggregate quantity.

We propose that Monte-Carlo ensembles in this setting should report the distribution of
*derived quantities* — area, perimeter, connectivity, shoreline displacement — rather than
per-pixel moments, and that any quoted interval should state which uncertainty terms it
does and does not contain.

---

## 1. Motivation

Two weaknesses are inherited by almost every index-threshold water product.

The first is that the threshold is scene-dependent and usually chosen by convention. The
canonical `NDWI > 0` rule is not a physical boundary; the empirically optimal cut moves
with sun geometry, turbidity, sediment load and land-cover mix (McFeeters, 1996; Xu, 2006;
Ji et al., 2009; Feyisa et al., 2014). Adaptive thresholding (Otsu, 1979; Donchyts et al.,
2016) removes the hand-tuning but still returns one hard cut per scene.

The second is that the output carries no uncertainty. A pixel one digital count from the
threshold is reported with the same confidence as the middle of a lake.

Monte-Carlo propagation of sensor noise is the natural response to the second weakness,
and it is the approach we began with. The contribution of this paper is the observation
that this response is incomplete in a way that is measurable and large: the resulting
interval is conditional on assumptions — a fixed decision rule, perfect geometry — each of
which costs more than the noise being propagated.

---

## 2. The estimand

A validatable claim requires a defined target. A multi-date, cloud-filtered composite has
no well-defined water extent, because adjacent pixels may originate from acquisitions
months apart; no reference can be correct for such a product. We therefore fix the
estimand as:

> **the water extent over the area of interest at the instant of a single Sentinel-2
> acquisition.**

A one-day acquisition window over this AOI returns exactly one image, so the mosaicking
problem is removed rather than mitigated.

| | |
|---|---|
| Acquisition | 2021-09-02, 10:57:29 UTC, tile 31UDQ, orbit 51, single image |
| Item | `S2A_MSIL2A_20210902T105031_R051_T31UDQ_20210903T000651` |
| Cloud cover | 0.00 % over the AOI |
| AOI | 1.8751, 48.8869, 2.2089, 49.0248 — Seine corridor, 24.6 × 15.6 km, 2464 × 1564 px at 10 m |
| Bands | B04, B03, B02, B08, B11, B12 |
| Held-out dates | 2021-06-14, 2021-03-01 — same tile, same orbit, ≤ 0.03 % AOI cloud |

**The year is set by the references, not by the imagery.** JRC Global Surface Water
MonthlyHistory — the only readily available *dated* water reference — ends at 2021-12, and
ESA WorldCover v200 is the 2021 epoch. Placing the scene in 2021 aligns both references
simultaneously rather than trading one temporal mismatch for another. September also sits
at Seine low flow, the most hydrologically stable period, so a monthly reference best
approximates an instant.

Reference availability was verified *before* the date was fixed. JRC GSW observed 0.00 %
of this AOI in 2021-02 and 2021-12 and 1.20 % in 2021-07; selecting a date on cloud
statistics alone would have yielded a reference with no observations at all. 2021-09 has
99.59 % coverage.

---

## 3. Forward model

### 3.1 Perturbation

Each realisation perturbs the reflectance stack and runs the complete detection chain:

```
ρ'(x) = ρ(x) + ε(x),   ε ~ N(0, σ(x)²),   σ(x) = σ_abs + σ_rel·|ρ(x)|
σ_abs = 0.005     σ_rel = 0.015     correlation length = 3 px     seed = 42 + tick
```

Three choices are load-bearing.

**An absolute noise floor is required.** A purely multiplicative model drives σ to zero
over water in NIR and SWIR, where clear-water reflectance is near zero. This is
physically backwards: it is on dark targets that relative radiometric uncertainty is
largest. Without the floor the ensemble degenerates.

**Noise is spatially correlated.** Independent pixel noise is unphysical — atmospheric
correction residuals, aerosol retrieval error and BRDF residuals are smooth fields at
scales of tens to hundreds of metres. As shown in §5, this choice is the controlling
variable of the aggregate uncertainty and has no effect whatsoever on the per-pixel one.

**Negative reflectance is not clipped.** Clipping at zero would bias the mean upward on
precisely the darkest (water) pixels and rectify the noise distribution.

The two σ terms are combined linearly rather than in quadrature. This is the conservative
direction — it overstates σ by ≈ 34 % at ρ = 0.3 and is indistinguishable over water — and
is stated rather than idealised; the quadrature alternative yields an area sd of 223 px
against 254 px, a 12 % difference in the uncertainty estimate and none in the mask.

### 3.2 Decision rule

Four indices are computed per realisation: NDWI (McFeeters, 1996), MNDWI (Xu, 2006),
AWEIsh (Feyisa et al., 2014) and MBWI (Wang et al., 2018). A pixel is classified as water
when at least two of the four are positive **and** a scene-adaptive reflectance gate is
satisfied — upper caps in NIR, SWIR1 and SWIR2 derived as the 99th percentile of each band
over the scene's consensus pixels.

**The gate caps are calibrated once on the unperturbed scene and frozen.** This is
essential: were the gate to re-derive itself per realisation, the ensemble spread would
mix decision-rule variability with measurement variability, and could not be interpreted
as a propagated measurement uncertainty. The separation is what makes the comparison in
§6 possible.

---

## 4. The per-pixel uncertainty map is not an uncertainty map

The natural product of such an ensemble is the per-pixel mean `P` and the per-pixel
standard deviation `σ_P`, the latter published as an uncertainty map. We show this second
product carries no information.

Each realisation produces a **binary** per-pixel outcome, and realisations are
independent. The per-pixel count over `N` realisations is therefore `Binomial(N, P)`, and

```
σ_P = √(P(1−P))     identically, up to O(1/√N) sampling error
```

`σ_P` is a closed-form function of the map beside it. No property of the noise model can
change this: the identity follows from the outcome being binary and the realisations being
independent, not from the shape, magnitude or spatial structure of the perturbation.

In particular, **spatial correlation cannot rescue it.** Correlating the noise field alters
the covariance *between* pixels while leaving each pixel's marginal distribution
Bernoulli. Measured against the analytic envelope: R² = 0.99989 under independent noise and
R² = 0.99990 under 3 px correlated noise — indistinguishable to four decimal places.

A per-pixel Monte-Carlo standard-deviation map published for a binary classifier is
`√(P(1−P))` rendered as an image.

---

## 5. What the ensemble does measure

The information that spatial correlation carries lives in **aggregate** quantities, which a
per-pixel marginal cannot see. Under independent noise, per-pixel errors cancel in a sum;
under correlated noise, whole patches move together and no cancellation occurs.

118 realisations per correlation length, evaluated on the river corridor:

| noise correlation | mean area (px) | **sd (px)** | CV | × i.i.d. |
|---|---|---|---|---|
| 0 px (independent) | 102 716.0 | **72.1** | 0.00070 | 1.00 |
| 1 px | 102 717.6 | **117.3** | 0.00114 | 1.63 |
| 3 px | 102 717.3 | **253.9** | 0.00247 | 3.52 |
| 10 px | 102 773.9 | **576.6** | 0.00561 | **8.00** |

**The control is what makes this conclusive.** Across all four runs the mean area is
unchanged (0.06 % spread), the mean probability over the domain is identical to four
decimal places (0.2796 / 0.2796 / 0.2796 / 0.2797), and the graded-pixel fraction barely
moves (7.43 → 7.32 %). The marginal probability field is invariant while the ensemble
spread of the derived quantity varies eightfold.

Other aggregates carry their own physical reading. Mean perimeter *falls* as correlation
rises (28 406 → 25 903 px) and the connected-component count with it: correlated error
produces smooth boundaries where independent error shreds them. The *spread* of every
aggregate grows — perimeter sd 74 → 170, component sd 28 → 40.

We therefore report the ensemble distribution of area, perimeter, connectivity, centroid
and shoreline displacement, with percentile confidence intervals taken **over realisations**.
Unlike pixel bootstraps, these intervals are not corrupted by spatial autocorrelation,
because each realisation is a genuinely independent draw.

---

## 6. Three uncertainty terms, compared

The gate freeze of §3.2 isolates the radiometric term. Measuring the other two on the same
scene, in the same units:

| term | sd of water area | ratio |
|---|---|---|
| **radiometric noise** — the term usually propagated | **254 px** | **1×** |
| co-registration, 0.5 px sub-pixel shift | **1 380 px** | **5.4×** |
| model form — 13 plausible rule variants | **7 153 px** | **28×** |

**Co-registration.** Multi-temporal registration error for a 10 m sensor is of order one
pixel (Storey et al., 2016; Skakun et al., 2017) and is the dominant displacement term for
any boundary metric. Adding a per-realisation rigid sub-pixel translation multiplies every
aggregate's spread by 4–10×: boundary-displacement sd ×4.2, area sd ×5.4, perimeter sd ×10.
The effect saturates between 0.5 and 1.0 px — half a pixel already decorrelates the
realisations — so it behaves as a threshold, not a tunable parameter.

**Model form.** Varying the vote threshold (`k ∈ {1,2,3}`), the gate percentile
(`∈ {95,98,99}`) and the index subset (leave-one-out) across 13 combinations yields water
areas from 92 485 px to 113 516 px: a 21 031 px range, **20 % of the estimate**, driven
entirely by choices that are conventionally left undocumented.

**Consequence.** A study propagating sensor noise alone reports an interval approximately
28× narrower than the spread induced by defensible alternative analyses of the same data.
This does not invalidate the radiometric analysis; it relocates it. The correct statement
is that radiometric noise contributes 254 px of area uncertainty *conditional on a fixed
decision rule and perfect geometry*, and that relaxing either assumption dominates it.

---

## 7. Validation, and its ceiling

### 7.1 Two references, and their disagreement

The prediction is scored against **ESA WorldCover v200 class 80** (10 m, annual, permanent
water) as the spatially matched primary reference, and against **JRC GSW MonthlyHistory
2021-09** (30 m, dated) as the temporally matched secondary. Both are resampled onto the
Sentinel-2 grid. The GSW `water` band is ternary — 0 = not observed, 1 = land, 2 = water —
so a separate validity mask is carried and all metrics are restricted to observed pixels;
treating code 0 as land would convert missing observations into false negatives.

Two independent references disagree, and that disagreement bounds what the validation can
resolve. Over the corridor:

| | IoU | interpretation |
|---|---|---|
| WorldCover vs GSW, as delivered | **0.7308** | they differ on 27 % of their union |
| after dilating GSW by 10 m | 0.8068 | peak — the gap is boundary sampling |
| GSW core (eroded 30 m) inside WorldCover | **0.9960** | interiors agree |
| WorldCover core inside GSW | **0.9742** | interiors agree |

The interiors agree to 97–99.6 %, and the core figures are identical to four decimal places
whether computed on the corridor or the whole scene. **The disagreement is almost entirely
boundary placement caused by GSW's 30 m sampling, not seasonality**: only ~2.6 % of
WorldCover's core is absent from the dated reference.

Three consequences are reported rather than assumed. The temporal error of the primary
reference is bounded at ~2.6 % of water area — a measured quantity. A 30 m reference
cannot validate a 10 m boundary claim. And metric differences smaller than the reference
envelope are not interpretable; any defensible 10 m boundary claim requires manual
annotation on this acquisition, which is feasible *because* the estimand is a single date.

### 7.2 Threshold selection as a measurement

The operating threshold is not hand-set. A sweep over `t ∈ [0,1]` recomputes the full
confusion matrix and reports precision, recall, F1, IoU, Youden's J and MCC, the last being
the selector: unlike F1 and IoU it uses all four confusion cells and is the appropriate
balanced summary under class imbalance (Matthews, 1975; Chicco & Jurman, 2020).

The selection rule is plateau-aware. Because `P` is concentrated, the raw argmax lands on
the first point after a sharp cliff near zero — an artifact, not a cutoff. Taking the
highest `t` within tolerance degenerates to `t ≈ 1` when the curve is flat end to end. The
rule therefore takes the **median of the tolerance-satisfying thresholds**, and snaps to a
semantic anchor (`t = 0.5`, the ensemble majority vote) only when the plateau exceeds 30 %
of the range *and* the cost of snapping is under 0.03 metric points — with that cost always
reported.

On this scene the plateau covers 15.7 % of the range, below the trigger, so the rule
returns the plateau median `t = 0.08`, rejecting the raw argmax at 0.02 at a cost of 0.005
MCC.

### 7.3 Intervals that account for autocorrelation

Pixels in a river corridor are spatially autocorrelated, and the noise model adds a
correlation length of its own, so resampling individual pixels overstates the available
information. The sweep resamples contiguous **30 px blocks** (≥ 10× the correlation
length), preserving local structure and yielding a defensible effective sample size
(Künsch, 1989; Lahiri, 2003).

| resampling | n | 95 % CI on MCC | width |
|---|---|---|---|
| pixel (naive) | 338 172 pixels | [0.8569, 0.8604] | 0.0035 |
| **block, 30 px** | **642 blocks** | **[0.8504, 0.8635]** | **0.0131** |

**The effective sample size is 642, not 338 172 — 527× smaller — and the honest interval is
3.7× wider.** The conclusion survives: 21.6 % of thresholds fall inside the best
threshold's interval, so the selected cutoff remains distinguishable. But it survives a
test that was previously not being performed.

### 7.4 Domain dependence

The evaluation domain is the ground truth dilated by a chosen radius, so every mask metric
is a function of that radius. IoU spans **13 points** — 0.861 restricted to ground-truth
water, 0.733 on the whole scene — while recall stays essentially constant (0.853–0.861) and
precision falls from 1.000 to 0.844. Widening the domain adds only false positives. The
selected threshold is domain-dependent too (0.02 in any corridor, 0.30 whole-scene), so
domain and threshold are not independent choices.

A reported IoU without its evaluation domain is not interpretable, and we publish the table
rather than a single figure. False positives beyond the widest corridor amount to 11.5 % of
predicted water but consist of 3 099 components averaging 4 px, the largest 305 px — speckle,
not spurious water bodies. The component-size distribution, not the bare percentage, is what
makes this diagnosable.

---

## 8. Results that constrain the method

Three findings constrain how the pipeline may be described.

**The four-index consensus is not a consensus.** Spearman correlation among the indices
ranges 0.758–0.947; the correlation matrix has eigenvalues 3.73 / 0.16 / 0.09 / 0.02, with
93 % of variance in one component, and the effective number of independent indices is 2.0
(Li & Ji, 2005) or 1.51 (Cheverud, 2001). AWEIsh agrees with the final verdict 99.92 % of
the time, and AWEIsh alone scores IoU 0.7917 against the four-index vote's 0.7911.
Removing MBWI changes IoU by 0.0001. The rule should be described as a multi-index vote
dominated by one index, not as independent corroboration.

**The assumed noise level cannot be chosen from performance.** Sweeping σ_abs from 0.001 to
0.02 raises IoU monotonically from 0.803 to 0.842 with no interior optimum: averaging more
perturbed realisations regularises the mask, filling gaps and suppressing speckle. Any
performance criterion would therefore drive σ_abs to the top of whatever range is searched.
It must be fixed from independent radiometric evidence and the sensitivity curve published.
Conclusions are not invariant to it — four IoU points and an elevenfold range in ensemble
spread across a plausible interval.

**`P` is well ranked but poorly calibrated.** Brier 0.0668 and ECE 0.067 appear acceptable,
but MCE is 0.598: the worst-populated bin sits 60 percentage points from the diagonal.
Requesting 12 equal-mass bins yields only 2 distinct bins, because `P` is concentrated. We
therefore describe `P` as a calibrated-in-rank confidence score, not as a calibrated
probability. Post-hoc recalibration is the obvious remedy and is not attempted here.
Reporting both ECE variants and the realised bin count, rather than a single ECE, is what
exposes this; a lone ECE of 0.067 would have read as a pass.

**Benchmarking.**

| method | IoU | MCC |
|---|---|---|
| **Monte-Carlo ensemble, `t = 0.08`** | **0.8185** | **0.8575** |
| Otsu on MNDWI | 0.7947 | 0.8342 |
| same rule, single deterministic run | 0.7911 | 0.8412 |
| AWEIsh > 0 | 0.7910 | 0.8406 |

The ensemble outperforms the identical rule evaluated once without noise by +0.027 IoU and
+0.016 MCC. However, Otsu on MNDWI — a single line of code — reaches 0.7947 IoU against the
ensemble's 0.8185, a margin of 0.024. One hundred and eighteen
realisations for 2.4 IoU points is not a defensible case for the ensemble as a *mask
producer*. The case for the ensemble is the uncertainty it quantifies. (Otsu is erratic on
the other three indices, IoU 0.45–0.59, because a river corridor's histogram is not
bimodal and its core assumption fails; all four variants are reported rather than the
best.)

---

## 9. Reproducibility

The entire protocol is one executable graph, so every figure and number is regenerated
from the wiring rather than from a chain of ad-hoc scripts. All seeds are fixed. Both
references are fetched onto the Sentinel-2 grid, so no resampling of the prediction is
required. Full acquisition provenance — item identifier, sensing time, tile, orbit and the
**delivered band count** — is recorded with every run; during this study one loader
silently delivered five of six requested bands, which would have produced a two-index vote
reported as a four-index vote with nothing in the output to reveal it.

A parameter-by-parameter reconciliation between this text and the graph file is provided in
`MC_PAPER_METHODS.md` §6b.

---

## 10. Limitations

Stated deliberately, since several are material.

1. **One AOI, three dates, one river type.** The Seine near Paris is regulated and largely
   permanent — the easy case, and the reason an annual reference proves adequate here. A
   tidal or strongly seasonal system would likely behave very differently, and the
   reference choice would have to change.
2. **The noise model is diagonal in band space.** Real atmospheric-correction residuals are
   correlated across bands, which would alter index-level variance. `σ_rel` is unswept.
3. **`P` is not recalibrated.** MCE 0.598.
4. **Boundary claims remain limited by reference resolution**, not by the method. Neither
   reference is annotated at 10 m on the acquisition itself.
5. **Pixel-level non-parametric tests elsewhere in the protocol remain descriptive.** The
   blocking correction of §7.3 was applied to the threshold sweep only. Effect sizes carry
   the argument in the remaining comparisons.
6. **The epistemic ensemble of §6 spans 13 rule variants**, which is a sample of plausible
   analyses, not an exhaustive space. The 28× ratio should be read as a lower bound on
   model-form uncertainty, not an estimate of it.

---

## 11. Recommendations

For studies reporting Monte-Carlo uncertainty on binary remote-sensing products:

1. **Do not publish a per-pixel ensemble standard-deviation map** as an uncertainty
   product for a binary classifier. It is `√(P(1−P))`. Publish the distribution of the
   derived quantities the user actually needs.
2. **State which uncertainty terms an interval contains.** An interval from radiometric
   propagation alone should say so, because on this scene it is 1/28th of the spread
   induced by defensible alternative rules.
3. **Include a geometric term** whenever a boundary metric is reported. At 10 m,
   co-registration dominates radiometry by 5×.
4. **Take bootstrap intervals over blocks, or over realisations** — never over individual
   pixels of an autocorrelated scene.
5. **Report the evaluation domain with every mask metric**, and audit false positives
   outside it.
6. **Define the estimand before choosing the reference**, and check that the reference has
   observations for the chosen period before committing to it.

---

## References

McFeeters, S.K. (1996). The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features. *International Journal of Remote Sensing*, 17(7), 1425–1432.

Xu, H. (2006). Modification of normalised difference water index (NDWI) to enhance open water features in remotely sensed imagery. *International Journal of Remote Sensing*, 27(14), 3025–3033.

Ji, L., Zhang, L. & Wylie, B. (2009). Analysis of dynamic thresholds for the Normalized Difference Water Index. *Photogrammetric Engineering & Remote Sensing*, 75(11), 1307–1317.

Feyisa, G.L., Meilby, H., Fensholt, R. & Proud, S.R. (2014). Automated Water Extraction Index: a new technique for surface water mapping using Landsat imagery. *Remote Sensing of Environment*, 140, 23–35.

Wang, X., Xie, S., Zhang, X. et al. (2018). A robust Multi-Band Water Index (MBWI) for automated extraction of surface water from Landsat 8 OLI imagery. *International Journal of Applied Earth Observation and Geoinformation*, 68, 73–91.

Otsu, N. (1979). A threshold selection method from gray-level histograms. *IEEE Transactions on Systems, Man, and Cybernetics*, 9(1), 62–66.

Donchyts, G., Schellekens, J., Winsemius, H. et al. (2016). A 30 m resolution surface water mask including estimation of positional and thematic differences. *Remote Sensing*, 8(5), 386.

Pekel, J.-F., Cottam, A., Gorelick, N. & Belward, A.S. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature*, 540, 418–422.

Zanaga, D., Van De Kerchove, R., Daems, D. et al. (2022). *ESA WorldCover 10 m 2021 v200*. Zenodo.

JCGM 101:2008. *Evaluation of measurement data — Supplement 1 to the GUM: propagation of distributions using a Monte Carlo method.* BIPM.

Heuvelink, G.B.M., Burrough, P.A. & Stein, A. (1989). Propagation of errors in spatial modelling with GIS. *International Journal of Geographical Information Systems*, 3(4), 303–322.

Matthews, B.W. (1975). Comparison of the predicted and observed secondary structure of T4 phage lysozyme. *Biochimica et Biophysica Acta*, 405(2), 442–451.

Chicco, D. & Jurman, G. (2020). The advantages of the Matthews correlation coefficient (MCC) over F1 score and accuracy in binary classification evaluation. *BMC Genomics*, 21, 6.

Brier, G.W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, 78(1), 1–3.

Guo, C., Pleiss, G., Sun, Y. & Weinberger, K.Q. (2017). On calibration of modern neural networks. *ICML*.

Kumar, A., Liang, P. & Ma, T. (2019). Verified uncertainty calibration. *NeurIPS*.

Nixon, J., Dusenberry, M., Zhang, L. et al. (2019). Measuring calibration in deep learning. *CVPR Workshops*.

Künsch, H.R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics*, 17(3), 1217–1241.

Lahiri, S.N. (2003). *Resampling Methods for Dependent Data.* Springer.

Clifford, P., Richardson, S. & Hémon, D. (1989). Assessing the significance of the correlation between two spatial processes. *Biometrics*, 45(1), 123–134.

Li, J. & Ji, L. (2005). Adjusting multiple testing in multilocus analyses using the eigenvalues of a correlation matrix. *Heredity*, 95, 221–227.

Cheverud, J.M. (2001). A simple correction for multiple comparisons in interval mapping genome scans. *Heredity*, 87, 52–58.

Storey, J., Roy, D.P., Masek, J. et al. (2016). A note on the temporary misregistration of Landsat-8 OLI and Sentinel-2 MSI imagery. *Remote Sensing of Environment*, 186, 121–122.

Skakun, S., Roger, J.-C., Vermote, E. et al. (2017). Automatic sub-pixel co-registration of Landsat-8 OLI and Sentinel-2A MSI images. *International Journal of Digital Earth*, 10(12), 1253–1269.

Gorroño, J., Banks, A.C., Fox, N.P. & Underwood, C. (2017). Radiometric inter-sensor cross-calibration uncertainty using a traceable high-accuracy reference hyperspectral imager. *ISPRS Journal of Photogrammetry and Remote Sensing*, 130, 393–417.

Doxani, G., Vermote, E., Roger, J.-C. et al. (2018). Atmospheric Correction Inter-Comparison Exercise. *Remote Sensing*, 10(2), 352.

Csurka, G., Larlus, D. & Perronnin, F. (2013). What is a good evaluation measure for semantic segmentation? *BMVC*.

Olofsson, P., Foody, G.M., Herold, M. et al. (2014). Good practices for estimating area and assessing accuracy of land change. *Remote Sensing of Environment*, 148, 42–57.

Kendall, A. & Gal, Y. (2017). What uncertainties do we need in Bayesian deep learning for computer vision? *NeurIPS*.
