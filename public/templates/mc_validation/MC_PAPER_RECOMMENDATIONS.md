# Recommendations on framing and next steps

Written after a full audit of the pipeline and a parameter-level review of the
MC-WISP methodology draft. All figures below are measured on the reference acquisition
(2021-09-02, tile 31UDQ, Seine corridor) and are reproducible from
`mc_paper_ensemble_uncertainty.vn`.

---

## 1. What is the paper about?

This is the decision that governs everything else, and the measurements have already
settled it.

| possible framing | what the measurements say |
|---|---|
| "a better water mask" | **Not defensible.** Otsu on MNDWI — one line of code — comes within 0.024 IoU. That is 118 realisations for 2.4 points. |
| "a probabilistic product" | **Fragile.** MCE = 0.598. `P` ranks well and calibrates badly. Without recalibration, the word *probability* is exposed. |
| "uncertainty quantification for water products" | **Solid, and new.** |

**Recommendation: reframe entirely around the uncertainty decomposition, and lead with the
negative results.**

The headline of this paper is that *the term everyone propagates is the smallest of the
three*: radiometric 254 px < co-registration 1 380 px < model form 7 153 px. That finding
is a service to the community, it is robust, and it has not been published. The mask is a
by-product.

A corollary: keep `σ_P = √(P(1−P))` prominent, not in a footnote. People publish these
per-pixel uncertainty maps. Saying so is useful.

---

## 2. Three claims to drop or to earn

**The four-index consensus.** AWEIsh alone scores 0.7917 against the four-index vote's
0.7911. Two honest options: reduce to one index (simpler, defensible), or **keep all four
and publish the redundancy as a result**. I recommend the second — *"multi-index consensus
is universally assumed; we measure it and it does not hold"* is a contribution. What is not
tenable is keeping four indices *while claiming* they corroborate one another.

**The scene-adaptive gate — now tested, and the result is worse than "inert".**

On the reference scene the gate removes 1.71 % of what the vote proposes. That looked like
"untested rather than useless", because the scene was selected for 0.00 % cloud and the
gate is, spectrally, a bright-surface rejector: the pixels it removes are 10–28× brighter
in every band, and only 0.2 % of them are ground-truth water.

Running it on cloudy acquisitions over the same AOI shows the opposite of the hoped-for
result:

| date | cloud | vote fires on | adaptive NIR cap | adaptive gate removes | fixed caps would remove |
|---|---|---|---|---|---|
| 2021-09-02 | 0 % | 2.7 % | 0.4365 | 1.71 % | 10.30 % |
| 2021-04-28 | 30 % | 29.0 % | **1.1848** | **1.91 %** | **94.21 %** |
| 2021-08-08 | 40 % | 31.4 % | **1.2224** | **2.33 %** | **95.62 %** |
| 2021-05-03 | 59 % | 58.2 % | **1.2208** | **2.00 %** | **99.03 %** |

**The self-calibration is hijacked by the population it exists to reject.** Clouds pass the
*k*-of-2 vote, so they enter the consensus set Ω, so the 99th percentile of Ω is computed
over clouds, so the cap is set at cloud brightness. The adaptive NIR cap reaches
1.18–1.22 — **above the physical maximum reflectance of 1.0** — making the condition
`ρ_NIR < c_n` vacuously true. The gate switches itself off exactly when it is needed.

Note also that the pipeline carries **no cloud mask** (SCL is not used, and the draft does
not mention one). The gate is implicitly serving that role, and failing at it.

**A fix, tested.** Build Ω under the *fixed* caps before taking the percentile, so bright
pixels cannot calibrate the gate:

| date | cap now | cap with pre-filtered Ω | removes now | removes with fix |
|---|---|---|---|---|
| 2021-09-02 | 0.4365 | 0.2400 | 1.71 % | 8.07 % |
| 2021-04-28 | 1.1848 | 0.2400 | 1.91 % | **92.02 %** |
| 2021-08-08 | 1.2224 | 0.2400 | 2.33 % | **94.21 %** |
| 2021-05-03 | 1.2208 | 0.2400 | 2.00 % | **98.40 %** |

**But the fix exposes a second problem.** With a clean Ω the raw 99th percentile is
0.060 / 0.094 / 0.105 / 0.109 across the four scenes — always below the floor
`m·c_fix = 0.24`. The floor therefore always dominates and **the percentile never binds**:
once the consensus set is correct, the "adaptive" path does not adapt.

So the design principle *"we make self-calibration tuning-free"* is not currently supported.
Two honest routes: lower `m` so the percentile can actually bind and show it tracks
something real across scenes; or drop the adaptivity, keep fixed caps, and gain a simpler
method that demonstrably works (94–99 % removal on cloudy scenes). **Either way, add a
cloud mask** — the gate should not be doing that job by accident.

This is a better outcome than the section being a liability: a diagnosed failure mode with
a measured fix is a contribution. But it must be reported, not quietly repaired.

**The product-agnostic SR/Rrs claim.** As it stands this is a liability rather than an
asset: unvalidated, and precisely where the reported confusion lives. But **the test that
would turn it into an asset is trivial** — run both products and verify that the vote maps
are identical and the gates near-identical. Half a day. Until that is done, I would remove
the claim from §2.1 rather than defend it.

---

## 3. The highest-return experiment

**A second scene of a different nature.**

Everything currently rests on the Seine near Paris: a regulated, largely permanent river
with dark, clear water. That is the easy case, and it is why an annual reference proves
adequate.

The Yellow River delta — the AOI originally considered — would test exactly the fragile
conclusions: tidal modulation, heavy sediment load, rarely clear water. On such a scene the
gate might become useful again, the index redundancy might break, and the reference's
temporal error might cease to be 2.6 %.

**The result is informative either way.** If the conclusions hold, generality is
demonstrated. If they break, you have a quantified domain limit — which is worth more than
an assumed generality.

---

## 4. On SR vs Rrs specifically

Do not bury this in a parameter table. The correct formulation, in one sentence:

> *The indices, the vote and `σ_rel` are scale-invariant; `σ_abs`, the fixed gate caps, the
> validity floor and the clip bounds are not, and convert by `Rrs = ρ/π`.*

And add the equality assertion as a **validation requirement**, not a remark. That is what
will stop the bug returning — all the more so because the dangerous branch is the fixed
fallback, which engages only below 500 consensus pixels: rare during development, likely in
production.

Details and the per-parameter conversion table are in `MC_PAPER_SR_VS_RRS.md`.

---

## 5. Order of work

1. **Reframe the abstract and introduction around the decomposition** — half a day, and it
   is what changes the paper's fate.
2. Fix the six SR/Rrs points in the review note.
3. Run the SR/Rrs equality test — cheap, and it makes the product-agnostic claim legitimate.
4. Add the contrasting second scene.
5. Post-hoc recalibration of `P` (isotonic, fitted out-of-sample) — or accept "confidence
   score" and drop the word *probability*.

Items 1–3 are mechanical and can be done immediately. Item 4 is a scientific-scope
judgement and belongs to the authors.

---

## A caveat worth keeping in view

This audit was adversarial by construction. It looked for what does not hold; it did not
look for what does. The gate section is the case in point. "Nearly inert on this scene" meant *not yet tested
where it would matter* — so it was tested, and the answer turned out to be a structural
defect with a measured fix, which is worth more than either the original complaint or the
original design. The distinction between *refuted* and *not yet demonstrated* is what made
that experiment worth running rather than assuming either outcome.
