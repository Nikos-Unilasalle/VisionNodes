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

**The scene-adaptive gate.** It removes 1.71 % of what the vote proposes. A methods
section describing an elaborate mechanism that does nothing is a magnet for reviewers.
Either show it matters on a harder scene, or simplify it away. Do not leave it described as
*the* mechanism that suppresses dark non-water surfaces.

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
look for what does. That the gate is nearly inert **on this scene** does not mean it is
useless — it means it has not yet been tested where it would matter.

That is the difference between *refuted* and *not yet demonstrated*, and the paper is
stronger for not conflating them.
