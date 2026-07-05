# Monte Carlo Water-Masking Validation: Methodological Concerns and Robustness Measures

## 1. Overview

This document summarizes a validation exercise for a Monte Carlo (MC) ensemble-based water-masking method built on Sentinel-2 L2A surface reflectance and a consensus of four normalized-difference and linear spectral water indices (NDWI, MNDWI, AWEIsh, MBWI). The method perturbs the input reflectance with a simulated sensor-noise model, re-evaluates the water/non-water consensus vote at each realization, and accumulates the results into a per-pixel water probability, P. This probability is then validated against a ground truth derived from an independent global land-cover product and an independent structural-obstruction layer (bridges), so that the method can be tested anywhere without site-specific reference data.

The initial pipeline produced plausible-looking outputs, but a critical review surfaced several methodological concerns that could undermine the validity of the results if left unaddressed. Each concern is described below, followed by the measure taken to mitigate it and the quantitative outcome observed after the fix.

## 2. Concerns identified and measures taken

### 2.1 Unrealistic noise model → probability estimates that are overconfident

**Concern.** The sensor-noise model applied to the input reflectance was purely multiplicative (proportional to the signal magnitude) and spatially independent pixel-to-pixel (i.i.d.). Published radiometric characterization of Sentinel-2 L2A products indicates that (a) real sensor/atmospheric noise has a significant *additive* component that does not vanish as the signal approaches zero, and this additive floor dominates precisely over dark targets such as open water in the near-infrared and shortwave-infrared bands — exactly the bands driving water discrimination — and (b) real noise is spatially correlated over a few pixels rather than independent at each pixel. A purely multiplicative, pixel-independent model therefore *underestimates* uncertainty where it matters most, which manifested as an ensemble probability that was almost perfectly bimodal (concentrated at 0 or 1) with very little of the intermediate, genuinely uncertain range one would expect near class boundaries.

**Measure.** The noise model was revised to include (i) an additive noise floor calibrated to the order of magnitude reported for low-signal / dark-water conditions in the Sentinel-2 literature, in addition to the existing multiplicative term, and (ii) a short-range spatial correlation instead of independent per-pixel draws, better matching the correlated nature of real atmospheric and sensor noise.

**Outcome.** After the correction, the ensemble probability distribution showed markedly more realistic spread, and the number of realizations required for the ensemble mean to stabilize increased substantially — an expected and desirable consequence of no longer artificially suppressing uncertainty.

### 2.2 No stopping criterion for the size of the Monte Carlo ensemble

**Concern.** The number of MC realizations was fixed a priori without any quantitative justification, leaving open the question of whether the ensemble mean had actually converged, or whether computational effort was being wasted beyond the point of useful returns.

**Measure.** A convergence diagnostic was introduced, tracking the scene-averaged standard error of the ensemble mean (standard deviation divided by the square root of the realization count) as a function of the number of realizations, against an explicit target precision. The ensemble is run until this standard error falls below the target, or until diminishing returns make further realizations not worth the computational cost.

**Outcome.** With the corrected (more realistic) noise model, the standard error decreases smoothly and without any natural plateau — consistent with a well-behaved but genuinely noisy estimator — reinforcing the point that convergence criteria, not an arbitrarily fixed count, should govern how many realizations are run. A target precision aligned with the magnitude of the additive noise floor introduced above yielded a practical ensemble size of order 100–120 realizations.

### 2.3 Fixed, subjectively chosen classification threshold

**Concern.** The probability map P was converted to a binary water mask using a threshold value chosen by inspection rather than derived from data, with no evidence that it was actually a good operating point for the precision/recall trade-off.

**Measure.** A systematic threshold sweep was implemented, evaluating precision, recall, F1, and intersection-over-union across the full [0, 1] probability range against the independent ground truth, and selecting an operating threshold from this curve rather than by eye. Because the ensemble probability turned out to be strongly bimodal (see §2.1), the resulting performance curve is close to flat over a wide range of thresholds once the very low end is excluded; a naive maximization would arbitrarily lock onto one edge of this plateau (either a very permissive or a very conservative cutoff) depending on minor numerical noise, which is not a meaningful choice. The selection rule was therefore designed to pick a representative, centrally located point within the near-optimal plateau rather than a raw maximum, together with an explicit warning when the performance curve is too flat to constitute a sharp discriminating criterion.

**Outcome.** The originally chosen threshold turned out to already lie within the near-optimal operating plateau (F1 ≈ 0.88–0.90, IoU ≈ 0.78–0.81, precision ≈ 0.95–0.96, recall ≈ 0.81), confirming it was a reasonable choice, but the pipeline is no longer dependent on that manual choice: the operating threshold is now derived and re-derived from the data at each run.

### 2.4 Validation contaminated by areas outside the feature of interest

**Concern.** Because the ground truth is a global land-cover/structure product rather than a hand-drawn river mask, it inevitably includes water-like or bridge-like features anywhere in the scene — ponds, wet rooftops, unrelated water bodies, unrelated crossings — that have nothing to do with the specific river reach under study. Comparing the predicted mask against this unconstrained ground truth over the *entire* scene would penalize the method for disagreements far outside the area of interest, unrelated to its actual performance on the target feature.

**Measure.** The evaluation domain was explicitly restricted to a buffered zone around the true river extent (the union of the detected water body and known structural crossings, morphologically expanded by a margin corresponding to a small fraction of the river width) before computing any agreement statistic. Both the predicted mask and the ground truth are intersected with this domain prior to scoring.

**Outcome.** All reported precision/recall/F1/IoU figures reflect performance specifically on the river corridor, not on unrelated background features, giving a fair and interpretable assessment of the method's actual target task.

### 2.5 Sensitivity to spatial misalignment between heterogeneous ground-truth sources

**Concern.** The ground truth is assembled from more than one independent geospatial source. Even after careful co-registration, sub-pixel to few-pixel misalignment between such sources is expected, which a strict pixel-by-pixel overlap metric (e.g. plain IoU) unfairly penalizes as if it were a genuine detection error.

**Measure.** In addition to the standard pixel-overlap metrics, a boundary-tolerant agreement metric was introduced, which credits a predicted boundary pixel as correct if a true boundary pixel exists within a small tolerance distance (a few pixels), rather than requiring exact pixel coincidence. This was preferred over alternative approaches (such as eroding the ground-truth mask) because a linear feature as narrow as a river can be partially or entirely erased by erosion, which would bias recall downward for the wrong reason.

**Outcome.** The boundary-tolerant score (≈ 0.86) was meaningfully higher than the strict overlap metrics, consistent with a real but modest co-registration offset between sources rather than a substantive detection failure — information that would have been invisible from the strict IoU/F1 figures alone.

### 2.6 Risk of circular / self-referential validation

**Concern.** The primary validation approach initially correlated the ensemble probability P against the same spectral indices whose consensus vote was used to construct P in the first place. Any such correlation is, by construction, partly measuring internal consistency rather than independent discriminative skill, and — because the four indices share input bands and are highly inter-related — tends to produce very similar, high correlation values for every index, which is uninformative for ranking their relative merit.

**Measure.** A second, independent validation axis was added that evaluates each spectral index's discriminative power directly against the ground truth (via the area under the ROC curve), entirely without reference to the ensemble probability P. Because this measure is rank-based, it is also inherently robust to the numerical range or sign of the index — a desirable robustness property distinct from, and complementary to, the ensemble-based validation.

**Outcome.** The independent, ground-truth-based ranking of index discriminability (AUROC ≈ 0.96–0.98 for all four indices, ordered MBWI > AWEIsh > NDWI > MNDWI) is far more differentiated and trustworthy than the self-referential correlation, and served as the reference for interpreting the ensemble-based figures rather than the other way around. The self-referential correlation panel was retained for internal-consistency monitoring but is now explicitly documented as such, rather than presented as an independent validation result.

### 2.7 Numerical fragility of normalized-difference indices at low signal

**Concern.** Two of the four indices are defined as a ratio of a difference to a sum of two spectral bands. Over very dark targets — precisely the conditions found on open water in the near-infrared and shortwave-infrared bands, and exactly where the additive noise floor introduced in §2.1 has the largest relative effect — this ratio's denominator can approach zero, causing the computed index value to spike to physically meaningless magnitudes on a small subset of pixels. Statistics that are sensitive to the full numeric range (such as means, variances, and effect sizes) are severely distorted by even a few such outliers, while rank-based statistics (such as Spearman correlation or AUROC) are largely immune, since they depend only on relative ordering, not magnitude. This produced an apparent contradiction where the same index showed excellent independent discriminative power (AUROC) but a near-null effect-size separation between classes — a red flag that a magnitude-sensitive computation, not the underlying signal, was at fault.

**Measure.** The affected indices were computed with the validity safeguard already anticipated by the underlying reference methodology: pixels where the denominator is not reliably bounded away from zero, or where an input band is non-physical, are excluded from the computation (rather than allowed to produce an unbounded ratio), and the index is clipped to its theoretically valid range.

**Outcome.** After the fix, the previously affected indices show effect sizes (Cohen's d ≈ 2.0–2.4) consistent with, and of the same order as, the other two indices (≈ 2.8–3.0) and with their already-good AUROC scores — resolving the contradiction and confirming that the earlier discrepancy was a numerical artifact rather than a real property of the index.

### 2.8 Physical plausibility constraint on candidate water pixels (pre-existing safeguard, confirmed consistent)

**Design note.** Independently of the multi-index consensus vote, the pipeline applies an adaptive reflectance gate that restricts candidate water pixels using scene-derived, physically motivated upper bounds on near-infrared and shortwave-infrared reflectance — bands on which water is spectrally dark but bare soil, built-up surfaces, dense vegetation, or haze/cloud artifacts are not — together with a minimum-signal floor that rejects deep-shadow and sensor-noise artifacts. Rather than fixed a priori, these bounds are derived adaptively from each scene itself (the upper percentile of near-infrared/shortwave-infrared reflectance among pixels already agreed upon by the multi-index consensus, floored at a physically motivated minimum), so the constraint self-calibrates without manual tuning and generalizes across sites.

**Relevance to this review.** This mechanism directly complements the noise-model and index-numerical-stability corrections described above (§2.1, §2.7): it explicitly suppresses spectrally dark or unusually bright non-water land cover that the spectral indices alone could misclassify as water, and it was verified to remain internally consistent after the sensor-noise model revision (its bounds are computed from the unperturbed reference scene, not from individual noisy realizations, so they are unaffected by the noise-floor correction).

## 3. Residual limitations and suggested future work

- **Index redundancy in the consensus rule.** The four spectral indices share input bands and are strongly correlated; a simple majority vote implicitly treats them as four independent pieces of evidence, which overstates the statistical confidence of the consensus. A decorrelation or redundancy-aware weighting scheme would give a better-calibrated confidence estimate.
- **Sensitivity of the consensus threshold itself.** The number of indices required to agree for a pixel to be classified as water was fixed by convention and not swept against the ground truth the way the final probability threshold was; doing so would clarify whether the chosen consensus rule is actually optimal.
- **Uniform noise magnitude across spectral bands.** The revised noise model (§2.1) applies the same relative and additive noise terms to every band, whereas real per-band signal-to-noise characteristics differ (visible bands typically have better signal-to-noise than shortwave-infrared over water). A per-band noise specification would be more physically faithful.
- **Threshold plateau flatness.** Because the ensemble probability is strongly bimodal, the precision/recall trade-off curve used to select the operating threshold is very flat over a wide range, meaning the "optimal" threshold carries limited statistical weight beyond confirming that a wide range of thresholds perform comparably well. This is reported transparently rather than presented as a sharp, high-confidence optimum.

## 4. Summary of final quantitative results

| Metric | Value |
|---|---|
| MC ensemble size (convergence-based) | ≈ 110–120 realizations |
| Classification threshold (data-driven, within a broad near-optimal plateau) | ≈ 0.15–0.5 (P scale) |
| Precision (domain-constrained) | ≈ 0.95–0.96 |
| Recall (domain-constrained) | ≈ 0.81 |
| F1 (domain-constrained) | ≈ 0.88–0.90 |
| IoU (domain-constrained) | ≈ 0.78–0.81 |
| Boundary-tolerant F-score | ≈ 0.86 |
| Index discriminability vs. ground truth, AUROC (independent of ensemble) | 0.96–0.98 across all four indices (MBWI > AWEIsh > NDWI > MNDWI) |
| Open-water vs. obstruction pixel separation, Cohen's d | ≈ 2.0–3.0 across all four indices (consistent order of magnitude after §2.7 fix) |
| Rank correlation between ensemble probability and indices, open water vs. obstruction pixels | Consistently higher on open water (≈ 0.65–0.80) than on obstruction pixels (≈ 0.45–0.50) across all indices, confirming the ensemble appropriately downweights confidence over ambiguous/obstructed pixels |
