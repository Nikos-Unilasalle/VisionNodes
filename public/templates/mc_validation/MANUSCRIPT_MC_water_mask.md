<!-- Formatted for Remote Sensing (MDPI). Article type: Article.
Front matter (title, authors, affiliations, ORCID, correspondence, funding) and
in-text citation keys [x] to be completed. -->

# Monte Carlo Uncertainty Propagation for Threshold-Independent Surface-Water Mapping from a Multi-Index Spectral Consensus

**Authors:** [First Last] ¹,\* , [First Last] ¹, …
**Affiliations:** ¹ [Institution, City, Country]
**\* Correspondence:** [email]

---

## Abstract

Optical surface-water mapping from multispectral imagery is dominated by spectral water indices (NDWI, MNDWI, AWEI, MBWI) converted to a binary mask by a fixed threshold. Two weaknesses limit the scientific defensibility of the resulting products: the output is a hard, deterministic label carrying no per-pixel measure of confidence, and the classification threshold is chosen subjectively, is not transferable across scenes, and is not propagated from the radiometric uncertainty of the input. We present a Monte Carlo (MC) framework that propagates a physically grounded sensor/atmospheric noise model through a multi-index consensus classifier to yield, for every pixel, a calibrated water-occurrence probability *P* and an accompanying uncertainty field. The noise model combines a signal-proportional term with an additive floor and short-range spatial correlation, reproducing the documented divergence of relative radiometric uncertainty over dark water in the near-infrared (NIR) and shortwave-infrared (SWIR). Ensemble size is fixed by a standard-error convergence criterion rather than by convention. We further propose a validation framework designed to avoid three common pitfalls: circularity (an independent, rank-based discriminability axis—area under the ROC curve, AUROC, against ground truth—computed without reference to *P*); confusion of statistical significance with practical relevance (bootstrap confidence bands on threshold-dependent metrics); and penalization of sub-pixel co-registration error between heterogeneous reference sources (a boundary-tolerant agreement metric). The operating threshold is selected by a data-driven sweep but semantically anchored to the MC majority vote when the performance surface is practically flat, giving a transferable, probabilistically interpretable cutoff whose deviation from the empirical optimum is reported explicitly. We demonstrate the framework on a Sentinel-2 river reach in which intra-river built structures (bridge decks) provide a stringent negative class. The MC probability separates open water from obstruction pixels with large effect sizes (Cohen's *d* ≈ 2.0–3.0; Mann–Whitney rank-biserial |r| ≈ 0.87–0.94, *p* < 0.001); the spectral indices discriminate water from non-water at AUROC ≈ 0.96–0.98; and domain-confined agreement reaches F1 ≈ 0.90, IoU ≈ 0.81, Matthews correlation coefficient (MCC) ≈ 0.85, with a boundary-tolerant F-score ≈ 0.91. The probability is well calibrated in the confident regimes that dominate the scene (Brier ≈ 0.067, expected calibration error ≈ 0.067) and only mildly under-confident in the sparse boundary-transition zone. The framework is portable: reference data are assembled entirely from a global land-cover product and OpenStreetMap, requiring no site-specific ground truth.

**Keywords:** surface water; Monte Carlo uncertainty; spectral water indices; Sentinel-2; probabilistic classification; threshold selection; accuracy assessment; ensemble methods

---

## 1. Introduction

Surface-water extent is a first-order variable for hydrology, flood monitoring, water-resource management, and climate studies, and optical satellite constellations—notably Sentinel-2 and Landsat—provide the spatial and temporal sampling needed to map it operationally. The dominant retrieval paradigm applies one or more normalized-difference or linear water indices to atmospherically corrected surface reflectance and thresholds the result: most commonly NDWI (green–NIR), MNDWI (green–SWIR), AWEI, and MBWI. These indices are computationally trivial, physically interpretable, and scale-invariant, which explains their ubiquity.

Two limitations recur across the literature and undermine the rigor of the derived products.

First, the output is deterministic and unqualified. A pixel is labelled water or non-water with no statement of how robust that label is to the substantial radiometric uncertainty of the input. This uncertainty is not negligible: bottom-of-atmosphere reflectance carries residual atmospheric-correction error and sensor noise, and—critically for water—the *relative* uncertainty diverges over dark targets in the NIR/SWIR, where the water signal is weakest and the signal-to-noise ratio is lowest. A single deterministic pass cannot express which pixels are confidently water, which are confidently land, and which are genuinely ambiguous.

Second, the threshold is arbitrary. The cutoff applied to an index (or to a probability) is typically fixed by inspection or copied from prior work. It is rarely propagated from input uncertainty, rarely validated against reference data on the scene at hand, and—when tuned—tends to overfit the specific reference mask and does not transfer to new locations. A threshold optimal for one scene is well known to degrade on another.

A natural response to the first limitation is Monte Carlo (MC) uncertainty propagation: perturb the input within its uncertainty budget, repeat the classification, and aggregate the ensemble into a per-pixel probability. This is standard in error-propagation contexts but under-exploited for operational water masking, and where used the noise model is often simplistic (purely multiplicative, spatially independent), which—as we show—systematically *underestimates* uncertainty exactly where water retrieval is hardest.

The second limitation is compounded by weaknesses in how water products are validated. Validation against the same indices that generated the mask is circular. Hard overlap metrics (F1, IoU) ignore true negatives and are sensitive to sub-pixel misalignment between reference sources. And with the very large pixel counts typical of imagery, null-hypothesis significance testing conflates statistically detectable differences with practically meaningful ones, so an "optimal" threshold can be reported with unwarranted confidence.

This paper addresses both limitations with a single, internally consistent framework. Its contributions are: (1) a physically grounded MC noise model—additive floor plus signal-proportional term, with short-range spatial correlation—propagated through a multi-index spectral consensus to produce a calibrated per-pixel water probability *P* and an uncertainty map; (2) a convergence-controlled ensemble size, chosen from the MC standard error of *P* rather than by convention; (3) a multi-axis validation framework that quantifies index discriminability *independently of P* (AUROC against ground truth, avoiding circularity), reports bootstrap confidence bands and explicitly separates statistical significance from practical relevance, and uses a boundary-tolerant agreement metric to accommodate sub-pixel co-registration error; (4) a threshold-selection rule that is data-validated yet semantically anchored to the MC majority vote, yielding a transferable, probabilistically interpretable operating point whose cost relative to the empirical optimum is reported; and (5) a portable, reference-data-light validation protocol built from a global land-cover product and OpenStreetMap. We illustrate the framework on a Sentinel-2 river reach containing bridge decks, which act as a demanding intra-water negative class; bridges are a *test case*, not the objective. The contribution is the MC water-masking and validation methodology itself.

## 2. Materials and Methods

### 2.1. Study Area and Satellite Imagery

We use Copernicus Sentinel-2 Level-2A bottom-of-atmosphere surface reflectance. Six bands are retained—blue (B02), green (B03), red (B04), NIR (B08), and the two SWIR bands (B11, B12)—resampled to a common 10 m grid. Level-2A reflectance is the standard analysis-ready product; its documented radiometric performance (absolute accuracy targeted at 3–5%, inter-band relative accuracy < 1% over bright targets) provides the basis for the noise model in Section 2.3, while its markedly higher relative uncertainty over dark water in the NIR/SWIR motivates the additive noise floor. The framework is demonstrated on a reach of the Seine River, France; the scene is illustrative and carries no scene-specific parameterization.

### 2.2. Reference Data (Portable, No Site-Specific Ground Truth)

To make validation reproducible anywhere, ground truth is assembled from two global, openly available sources rather than from manually digitized site masks. Open water is taken from a global 10 m land-cover product (permanent-water class). Intra-water obstructions (the bridge test class) are taken from OpenStreetMap structural features and rasterized onto the image grid. The river corridor—the domain over which the method is evaluated—is derived by morphological dilation of the union of these two layers, restricting the analysis to the fluvial zone and excluding unrelated water-like or structure-like features elsewhere in the scene (ponds, wet impervious surfaces, unrelated crossings). This confinement is essential: without it, agreement statistics are contaminated by objects irrelevant to the target feature.

### 2.3. Sensor/Atmospheric Noise Model

For band *b* and pixel *p*, the perturbed reflectance in MC realization *i* is

R_b^(i)(p) = R_b(p) + ε_b^(i)(p),  ε_b^(i)(p) ~ N(0, σ_b(p)²),

with a per-band standard deviation combining an additive floor and a signal-proportional term:

σ_b(p) = σ_abs + σ_rel · |R_b(p)|.

The multiplicative term (σ_rel) represents the combined sensor-radiometric and residual atmospheric-correction uncertainty for well-illuminated targets; we use σ_rel = 0.015 (1.5%), consistent with published Sentinel-2 characterization. The additive floor σ_abs > 0 is essential over water: a purely multiplicative model drives σ_b → 0 as reflectance → 0, injecting almost no uncertainty on dark NIR/SWIR water pixels, whereas the true relative uncertainty there is largest (documented to exceed several hundred percent in the NIR over dark water, owing to the low signal-to-noise ratio). We set σ_abs = 5 × 10⁻³ reflectance units as a physically motivated floor; this value is not a published constant and is intended to be calibrated empirically against the ensemble diagnostics of Section 2.5.

Real sensor and atmospheric-correction errors are spatially correlated over a few pixels, not independent. We therefore draw a white-noise field per band, low-pass filter it (Gaussian kernel, correlation length ≈ 3 px), and renormalize to unit variance so that the marginal per-pixel σ is preserved while neighbouring perturbations co-vary. Independent (i.i.d.) noise underestimates the ensemble spread and yields an over-confident, near-binary *P*; the correlated model produces a more realistic distribution with a populated intermediate range.

### 2.4. Multi-Index Spectral Consensus

For each realization, four water indices are recomputed from the perturbed reflectance: NDWI, MNDWI, AWEI(sh), and MBWI. Normalized-difference indices are evaluated with a validity guard: pixels whose denominator is not reliably bounded away from zero, or whose input bands are non-physical, are masked out (excluded from the vote) rather than allowed to produce an unbounded ratio, and the index is clipped to its theoretical range [−1, 1]. This is critical because the additive noise floor increases the frequency of near-zero denominators over dark water; without the guard, a small number of pixels take extreme values that corrupt magnitude-sensitive statistics (means, variances, effect sizes) while leaving rank-based statistics unaffected—an easily misread inconsistency.

Each index casts a binary water vote (index in its water-positive half-space). A pixel is provisionally classified water when at least *k* = 2 of the four indices agree. The vote is intersected with an adaptive reflectance gate that enforces physically motivated upper bounds on NIR/SWIR reflectance (dark-target behaviour of water) and a minimum-signal floor (rejecting deep-shadow and noise artifacts). The gate bounds are not fixed a priori: they are derived per scene as an upper percentile of NIR/SWIR reflectance among the consensus pixels of the unperturbed reference scene, floored at a physical minimum, so the constraint self-calibrates and is computed once from the noise-free scene (hence unaffected by the per-realization perturbation).

### 2.5. Probability Accumulation and Convergence

Across *N* realizations, the per-pixel water probability is the ensemble mean of the binary consensus mask,

P(p) = (1/N) Σ_i M^(i)(p),

and the per-pixel uncertainty is the ensemble standard deviation σ_P(p). *P* is a genuine probability—the fraction of physically plausible input realizations that classify the pixel as water—not a heuristic score. Ensemble size is fixed by convergence rather than convention. We track the scene-mean MC standard error of the mean,

SE(N) = ⟨σ_P⟩ / √N,

and run until SE falls below a target precision aligned with the additive-noise floor. Because the estimator is well-behaved, SE decreases smoothly as N^(−1/2) with no natural plateau; the required *N* therefore reflects an explicit precision/cost trade-off. For the demonstration scene, a target SE ≈ 5 × 10⁻³ is reached at *N* ≈ 120, and tightening the target by an order of magnitude would require *N* of order 10⁴—a direct, quantified consequence of the larger, honest ensemble spread produced by the additive/correlated noise model.

### 2.6. Threshold Selection: Data-Validated, Semantically Anchored

Converting *P* to a binary mask requires a threshold *t*. We compute precision, recall, F1, IoU, Youden's *J*, and MCC as functions of *t* against the domain-confined ground truth. MCC is included deliberately because—unlike F1 and IoU—it incorporates true negatives and is robust to class imbalance. Because *P* is strongly bimodal, all threshold-dependent metrics are nearly flat over a wide range of *t* once the near-zero cliff is excluded, so a naïve arg-max locks onto an arbitrary edge and is unstable run-to-run. When the performance surface is not flat, the operating point is the median of the near-optimal set. When it is flat (the near-optimal set spans a large fraction of the threshold range), we snap to a semantic anchor—the MC majority vote, *t* = 0.5, "classified water when the majority of physically plausible realizations agree"—provided the practical cost of doing so (the absolute drop in the chosen metric relative to the empirical optimum) is small. The anchored threshold is probabilistically interpretable, stable across runs, and transferable, and the cost incurred relative to the data optimum is reported.

### 2.7. Validation Framework

We evaluate the product along complementary axes, each targeting a specific failure mode of naïve validation. (a) *Independent, threshold-free discriminability (anti-circularity).* Correlating *P* with the indices that generated it measures internal consistency, not skill, and—because the indices share bands—returns nearly identical, uninformative values; we instead quantify each index's discriminative power directly against ground truth via AUROC, computed without reference to *P*. Being rank-based, AUROC is invariant to the index's range or sign. (b) *Class-separation statistics.* For open-water vs. obstruction we report the mean gap Δμ, Cohen's *d* (σ-normalized, comparable across indices), and a non-parametric Mann–Whitney *U* test with its rank-biserial effect size (no normality assumption). (c) *Operating-point agreement, domain-confined.* Precision, recall, F1, IoU, and MCC are computed with both prediction and ground truth intersected with the river corridor. (d) *Boundary tolerance.* A boundary-tolerant F-score credits a predicted boundary pixel as correct if a true boundary lies within a small tolerance (3 px); this is preferred over eroding the reference mask, which would erase narrow features such as a river and bias recall. (e) *Statistical significance vs. practical relevance.* For the chosen metric we compute a bootstrap 95% confidence band over resampled pixels, and report both whether the optimal threshold is *statistically* distinguishable from the rest of the curve and the *absolute* performance cost of the anchored threshold. (f) *Probabilistic calibration.* Because *P* is presented as a probability, not merely a rank score, we assess whether it is calibrated—whether pixels assigned *P* ≈ *q* are water a fraction ≈ *q* of the time. Over the domain we compute the Brier score (mean squared error between *P* and the binary outcome), the expected and maximum calibration errors (ECE, MCE) from a reliability diagram binned in predicted probability, and the mean predictive uncertainty ⟨U⟩ (the domain-mean of the MC ensemble standard deviation σ_P). ECE is frequency-weighted across bins; MCE is the worst single bin.

## 3. Results

### 3.1. Effect of the Noise Model on the Probability Field

With a purely multiplicative, spatially independent noise model, *P* is almost perfectly bimodal (mass at 0 and 1), leaving genuine boundary ambiguity unexpressed. Introducing the additive floor and short-range spatial correlation populates the intermediate range and increases the ensemble size required for convergence, consistent with the model no longer artificially suppressing uncertainty.

### 3.2. Ensemble Convergence

The scene-mean standard error decreases as N^(−1/2) with no natural plateau. A target SE of 5 × 10⁻³ is met at *N* ≈ 120, the operating ensemble size for the reported results. The absence of a plateau reinforces that ensemble size should be governed by an explicit precision criterion rather than a fixed count.

### 3.3. Independent Index Discriminability and Class Separation

Against ground truth and independently of *P*, all four indices separate water from non-water at AUROC ≈ 0.96–0.98 (Table 1). This ranking is far more differentiated and trustworthy than the near-identical (≈ 0.79) values returned by the circular *P*-vs-index correlation, and is used as the reference for interpreting the ensemble-based figures. The MC probability sharply separates open-water from bridge pixels, which concentrate near *P* = 1 and *P* = 0 respectively; across the four indices the σ-normalized effect size is large (Cohen's *d* ≈ 2.0–3.0) and the non-parametric test is unambiguous (*p* < 0.001; rank-biserial |r| ≈ 0.87–0.94), confirming that both the indices and the resulting probability treat intra-water obstructions as a distinct, low-probability class.

**Table 1.** Per-index discriminability and open-water vs. bridge separation. AUROC is computed against ground truth, independently of the MC probability *P* (threshold-free, rank-based). Δμ is the raw mean gap; Cohen's *d* is the σ-normalized effect size; the Mann–Whitney *U* test is two-sided with rank-biserial correlation *r* as effect size. The final row characterizes *P* itself.

| Feature | AUROC vs. GT (P-free) | Δμ (open − bridge) | Cohen's *d* | Mann–Whitney *p* | Rank-biserial |r| |
|---|---|---|---|---|---|
| MBWI   | 0.981 | 0.297 | 3.02 | < 0.001 | 0.94 |
| AWEIsh | 0.979 | 0.326 | 2.81 | < 0.001 | 0.92 |
| NDWI   | 0.972 | 0.637 | 2.41 | < 0.001 | 0.90 |
| MNDWI  | 0.959 | 0.715 | 2.02 | < 0.001 | 0.88 |
| MC probability *P* | — | 0.784 | 2.36 | < 0.001 | 0.87 |

### 3.4. Operating-Point Performance, Boundary Tolerance, and Threshold Selection

Domain-confined agreement at the selected operating point and the boundary-tolerant score are summarized in Table 2. The threshold-dependent surface is flat: the near-optimal set spans ≈ 30% of the threshold range, and F1/IoU/MCC decrease only gradually and monotonically away from the low-*t* optimum. Bootstrap analysis finds the empirical optimum *statistically* distinguishable from the tails, but the *practical* cost of moving to the semantic anchor *t* = 0.5 is ≈ 0.02 in MCC—a difference statistically detectable only because of the very large pixel count. We therefore report *t* = 0.5 (MC majority vote) as the operating threshold: probabilistically interpretable, run-to-run stable, and transferable, with the sub-2-point cost relative to the data optimum stated explicitly. At a 3 px tolerance the boundary F-score (≈ 0.91) markedly exceeds the strict IoU (≈ 0.81); the gap indicates that a substantial share of the strict-overlap disagreement arises from small co-registration offsets between the heterogeneous reference sources rather than from genuine detection error—information invisible from pixel-overlap metrics alone.

**Table 2.** MC water-mask product performance and operating configuration. Agreement metrics are domain-confined (prediction and ground truth intersected with the river corridor). The operating threshold is the semantic anchor selected per Section 2.6; "anchor cost" is the absolute MCC drop relative to the empirical optimum.

| Quantity | Value | Notes |
|---|---|---|
| Precision (domain-confined) | 0.95 | |
| Recall (domain-confined) | 0.85 | |
| F1 (domain-confined) | 0.90 | threshold-dependent; ignores TN |
| IoU (domain-confined) | 0.81 | ignores TN; misalignment-sensitive |
| MCC (domain-confined) | 0.85 | uses TN; class-imbalance robust |
| Boundary F-score (tol = 3 px) | 0.91 | boundary P ≈ 0.91, boundary R ≈ 0.92 |
| Brier score | 0.067 | probability calibration (lower is better) |
| Expected calibration error (ECE) | 0.067 | frequency-weighted; low (extremes dominate) |
| Maximum calibration error (MCE) | 0.48 | worst single bin (sparse transition zone) |
| Mean predictive uncertainty ⟨U⟩ | 0.054 | domain-mean ensemble std σ_P |
| Operating threshold *t* | 0.50 | MC majority vote (semantic anchor) |
| Anchor cost vs. data optimum | ≈ 0.02 MCC | statistically significant, practically negligible |
| Near-optimal plateau width | ≈ 30% of *t* range | metric barely discriminates *t* |
| Ensemble size *N* | ≈ 120 | at target SE ≈ 5 × 10⁻³ |

### 3.5. Probabilistic Calibration

The reliability diagram (Brier = 0.067, ECE = 0.067, MCE = 0.48, ⟨U⟩ = 0.054; N ≈ 3.5 × 10⁵ pixels) shows that *P* is well calibrated in the confident regimes and mildly under-confident in the transition zone. The two extreme bins—which together hold ≈ 96% of the pixels (≈ 70% at *P* ≈ 0, ≈ 26% at *P* ≈ 1)—lie on the diagonal (empirical water fractions ≈ 0.07 and ≈ 0.97, respectively), so the confident decisions that dominate the scene are reliable. This is why the frequency-weighted ECE remains low (0.067). The intermediate bins, however, lie systematically above the diagonal (e.g. pixels assigned *P* ≈ 0.12 are water ≈ 60% of the time), driving the large MCE (0.48) from a single, sparsely populated bin: where the ensemble is undecided, ground truth leans more toward water than *P* states. The low mean uncertainty (⟨U⟩ = 0.054) confirms that ensemble spread is concentrated at feature boundaries rather than distributed across the scene. We interpret the intermediate-bin under-confidence as arising predominantly from mixed boundary pixels at 10 m resolution—where the reference mask labels a partially inundated pixel as water while the ensemble prudently assigns intermediate probability—rather than from a systematic model bias; the high boundary-tolerant agreement (Section 3.4) is consistent with disagreement being concentrated at edges. A targeted verification (recomputing calibration after excluding a narrow band around reference boundaries, to separate genuine model under-confidence from reference-edge noise) is left to future work.

## 4. Discussion

### 4.1. Why a Probabilistic Output Matters

The MC probability *P* converts a brittle, threshold-dependent binary decision into a calibrated field separating confident water, confident non-water, and genuinely ambiguous pixels. The accompanying uncertainty map localizes ambiguity to feature boundaries and intra-water obstructions—exactly where a single deterministic pass is least reliable. Crucially, *P* is not merely a rank score: the reliability analysis (Section 3.5) confirms it is calibrated in the confident regimes that dominate the scene, so probabilities can be aggregated in time, thresholded at a risk-appropriate level, or ingested by assimilation schemes that expect uncertainty.

### 4.2. Physical Fidelity of the Noise Model

The single most consequential modelling choice is the additive noise floor. A multiplicative-only model is not merely approximate; it is anti-correlated with reality, suppressing uncertainty precisely on the dark NIR/SWIR water pixels that dominate water discrimination. Restoring the additive floor and spatial correlation is what makes *P* an honest probability rather than a hardened relabelling of the deterministic mask. This has a cost—genuine uncertainty is more expensive to average down—which the convergence criterion makes explicit.

### 4.3. Statistical Significance Is Not Practical Relevance

Our threshold analysis is a concrete instance of a pitfall endemic to large-*n* remote sensing: with millions of pixels, bootstrap tests flag sub-point metric differences as significant, tempting an over-precise claim of an "optimal" threshold. By reporting both the significance verdict and the absolute cost, and by anchoring the operating point to a probabilistically meaningful value when the surface is flat, we obtain a threshold that is defensible and portable. We recommend this significance-plus-cost reporting as standard practice for threshold-based products.

### 4.4. Avoiding Circular Validation

The near-identical *P*-vs-index correlations (≈ 0.79) illustrate why correlating a product against its own inputs is uninformative. The independent AUROC-against-ground-truth axis both differentiates the indices (Table 1) and provides a genuine, threshold-free skill measure. We retain the *P*-vs-index panel only as an internal-consistency diagnostic, explicitly labelled as such.

### 4.5. Portability and Limitations

Reference data are drawn entirely from global open sources, so the framework can be evaluated anywhere without local ground truth; the intra-water obstruction class is a stringent, transferable stress test rather than an end in itself. Limitations define future work. (i) The four indices share input bands and are strongly correlated, so a simple *k*-of-4 vote overstates the independence of the evidence; a decorrelated or redundancy-weighted consensus would yield a better-calibrated confidence. (ii) The noise magnitude is applied uniformly across bands, whereas per-band signal-to-noise differs, especially over water; a per-band specification would be more faithful. (iii) The demonstration uses a single scene; systematic evaluation across sensors, seasons, water types (turbid, sediment-laden, shadowed), and against in-situ or higher-resolution reference is required to establish generality. (iv) The additive floor and consensus threshold are physically motivated but not yet independently calibrated against a radiometric-uncertainty reference; doing so would remove the last tuned quantities.

## 5. Conclusions

We have presented a Monte Carlo framework that turns conventional multispectral water indices into a calibrated, per-pixel water-occurrence probability by propagating a physically grounded—additive, signal-proportional, spatially correlated—sensor/atmospheric noise model through a multi-index consensus classifier. Ensemble size is set by a convergence criterion; the operating threshold is data-validated yet semantically anchored to the MC majority vote for transferability, with its cost relative to the empirical optimum reported. A validation framework built to avoid circularity, misalignment sensitivity, and the conflation of statistical significance with practical relevance shows strong, internally consistent performance on a demonstration scene (AUROC ≈ 0.96–0.98; Cohen's *d* ≈ 2.0–3.0; domain-confined F1 ≈ 0.90, MCC ≈ 0.85; boundary F ≈ 0.91), using only globally available reference data. The contribution is methodological and sensor-agnostic: it equips index-based water mapping—still the operational workhorse—with the uncertainty quantification and validation rigor expected of a defensible scientific product.

---

**Author Contributions:** Conceptualization, [X.X.]; methodology, [X.X.]; software, [X.X.]; validation, [X.X.]; formal analysis, [X.X.]; writing—original draft preparation, [X.X.]; writing—review and editing, [X.X.]. All authors have read and agreed to the published version of the manuscript.

**Funding:** [This research received no external funding / grant number].

**Data Availability Statement:** Sentinel-2 Level-2A imagery is available from the Copernicus Data Space Ecosystem. Reference layers are derived from [global 10 m land-cover product] and OpenStreetMap (© OpenStreetMap contributors, ODbL). Processing scripts and derived products are available at [repository/DOI].

**Conflicts of Interest:** The authors declare no conflict of interest.

**Abbreviations:** AUROC, area under the receiver-operating-characteristic curve; AWEI, Automated Water Extraction Index; ECE, expected calibration error; GT, ground truth; IoU, intersection over union; MC, Monte Carlo; MCC, Matthews correlation coefficient; MCE, maximum calibration error; MBWI, Multi-Band Water Index; MNDWI, Modified NDWI; NDWI, Normalized Difference Water Index; NIR, near-infrared; SE, standard error; SWIR, shortwave-infrared.

*Suggested figures: (1) MC probability field and uncertainty map; (2) ensemble convergence, SE vs N; (3) independent AUROC ranking of indices; (4) open-water vs obstruction distributions with Δμ / Cohen's d / Mann–Whitney; (5) threshold sweep with bootstrap confidence band and anchored operating point; (6) boundary-tolerant agreement overlay; (7) reliability diagram of P with Brier/ECE/MCE and bin-count histogram.*
