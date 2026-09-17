# SR vs Rrs in MC-WISP: which parameters need converting, and which do not

Response to the reviewer note on `MC-WISP_Methodology_RSE-style.docx`
(*"please check for the Surface reflectance SR and Rrs — it's making huge confusion"*).

The note is correct, and the confusion has a precise structure that the current draft does
not state. Everything below is measured on the reference acquisition
(2021-09-02, tile 31UDQ, Seine corridor) unless marked analytic.

---

## 1. The structure: the pipeline is half scale-invariant

`Rrs = ρ_w / π` (the repository's own ACOLITE node implements exactly this). So moving from
SR to Rrs is a division of every band by π ≈ 3.1416. The algorithm splits cleanly in two:

**Scale-invariant — needs no conversion, and must not be given one:**

| component | why |
|---|---|
| NDWI, MNDWI | normalised differences; a common factor cancels exactly |
| AWEIsh, MBWI | homogeneous linear forms compared against **zero**; dividing by π preserves the sign |
| the *k*-of-4 vote | a function of those four signs only |
| `σ_rel` | dimensionless multiplier |

Verified: applying the vote to the SR stack and to the same stack divided by π gives
**105 086 water pixels in both cases** — bit-identical outside NaN cells.

**Scale-dependent — must be converted, or the term silently changes meaning:**

| component | SR | Rrs (= SR/π) |
|---|---|---|
| gate caps `c_b^fix` (NIR / SWIR1 / SWIR2) | 0.120 / 0.060 / 0.050 | **0.0382 / 0.0191 / 0.0159** |
| `σ_abs` | 5×10⁻³ | **1.59×10⁻³ sr⁻¹** |
| index validity floor `ρ_min,idx` | see §4 | see §4 |
| clip bounds `[ρ_min, ρ_max]` | see §5 | see §5 |
| low-signal floor `τ_sig` | 0.003 | 9.5×10⁻⁴ |

**This is the single sentence the draft is missing.** Section 2.1 says the algorithm is
"product-agnostic… differing only in the product-specific parameters given alongside each
equation", which is right in spirit, but it never says *why* those particular parameters
are product-specific while others are not. A reader cannot tell whether a given constant
was converted deliberately or left unconverted by oversight — which is exactly the
confusion being reported.

---

## 2. `σ_abs` and `σ_rel` are documented the wrong way round

Section 2.3 states:

> *"We fix σ_abs = 5×10⁻³ reflectance units… We set σ_rel = 1.5 % for surface reflectance,
> and fix both constants once and apply them identically at every site."*

`σ_abs` carries units and is given **without a product qualifier**. `σ_rel` is
dimensionless and is given **with one**. That is backwards on both counts.

Why it matters, measured on the reference scene:

| product | median NIR, water | median NIR, land | σ_abs / water signal |
|---|---|---|---|
| SR | 0.0294 | 0.2996 | **17.0 %** |
| Rrs, σ_abs unconverted | 0.0094 | 0.0954 | **53.4 %** |

The same number is **π times more aggressive** in Rrs. Against the GLORIA reference range
for Rrs (0.0001–0.05 sr⁻¹, per this repository's ACOLITE node), an unconverted
σ_abs = 0.005 sr⁻¹ is **50× the low end of the entire physical range** and 10 % of the high
end — it would swamp the water signal it is meant to perturb.

**Suggested wording:** state σ_abs as a product-specific constant with both values
(5×10⁻³ for SR, 1.59×10⁻³ sr⁻¹ for Rrs, related by 1/π), and state σ_rel once as
dimensionless and therefore common to both.

---

## 3. The gate caps: the Rrs values are internally inconsistent

Section 2.2 gives `c_b^fix` as 0.12 / 0.06 / 0.05 (SR) and 0.030 / 0.018 / 0.014 sr⁻¹
(Rrs). Checked against the π conversion:

| band | SR | SR/π | draft's Rrs | deviation |
|---|---|---|---|---|
| NIR | 0.120 | 0.0382 | 0.030 | **−21 %** |
| SWIR1 | 0.060 | 0.0191 | 0.018 | −6 % |
| SWIR2 | 0.050 | 0.0159 | 0.014 | −12 % |

SWIR1 is consistent; NIR and SWIR2 are not. Either they were derived independently — in
which case the derivation should be given, since a reader will otherwise assume π — or
they are rounding drift, in which case they should be the exact conversions.

**Why the consequence is severe.** Using the SR caps on Rrs data:

| configuration | fraction of scene passing the gate |
|---|---|
| SR data + SR caps (correct) | **2.65 %** |
| Rrs data + Rrs caps (draft) | 2.58 % |
| **Rrs data + SR caps (the confusion)** | **40.48 %** |

An unconverted cap makes the gate **15.3× more permissive**: it stops rejecting dark
non-water surfaces, which is its entire purpose. The failure is silent — the mask simply
grows, with no error and no flag.

### 3b. A related finding: the adaptive branch makes the gate nearly inert here

The three rows above use the **fixed fallback** caps, which is the branch the unit
mismatch would hit. On the reference scene the *adaptive* branch is the one that runs, and
it is far looser:

| | NIR | SWIR1 | SWIR2 |
|---|---|---|---|
| adaptive caps (99th pct of consensus pixels) | 0.4365 | 0.3437 | 0.2893 |
| fixed fallback | 0.1200 | 0.0600 | 0.0500 |
| ratio | **3.6×** | **5.7×** | **5.8×** |

Consequence for the mask:

| rule | water pixels | gate's effect |
|---|---|---|
| vote alone (`k ≥ 2`) | 105 087 | — |
| **vote ∧ adaptive gate (operative)** | **103 292** | removes **1.71 %** |
| vote ∧ fixed-cap gate | 94 267 | would remove 10.30 % |

The gate passes **89.8 %** of the scene under adaptive caps against 2.7 % under the fixed
ones. So on this acquisition the gate removes 1.7 % of what the vote proposes: the mask is
very nearly the vote alone.

Two implications for the text. First, describing the gate as *the* mechanism that
suppresses dark non-water surfaces overstates what it does on a scene with a large, bright
consensus set — the claim should be conditioned, or the percentile revisited. Second, and
more importantly for the units question: **the branch where the SR/Rrs mismatch bites is
the fallback, which engages only when fewer than 500 consensus pixels are found.** That is
a rare branch on ordinary scenes and a likely one on small, cloudy or mostly-dry AOIs — the
worst profile for a unit bug, because it will pass every test on the scenes you develop
against and fail on the scenes you deploy to.

---

## 4. The index validity floor: check the sign convention

Section 2.2 gives `ρ_min,idx` = **0.0 for SR** and **−0.002 for Rrs**.

Two observations.

**(a) The current implementation uses −0.05 for SR**, not 0.0. On the reference scene the
choice is immaterial — at SR, zero water pixels are censored at any of 0.0, −0.002 or
−0.05, because the darkest water NIR/green sits well above zero. So this is a
documentation/implementation mismatch to reconcile, not an error in the results.

**(b) The floor becomes material in Rrs, and in the direction that matters.** Because a
guarded index returns NaN and *"a guarded index returning NaN votes against water"*, any
censoring is a systematic bias against the water class, not symmetric noise. Analytically,
for the median water SWIR1 pixel:

| configuration | median water SWIR1 | P(perturbed ≤ 0) |
|---|---|---|
| SR, σ_abs = 0.005 | 0.01850 | 0.01 % |
| **Rrs, σ_abs unconverted** | 0.00589 | **11.9 %** |
| Rrs, σ_abs converted (÷π) | 0.00589 | 0.01 % |

With an unconverted σ_abs and a floor at exactly 0.0, roughly **one in eight water pixels
would be censored per band per realisation** — and each censored index votes against
water. Converting σ_abs removes the problem entirely. The two parameters interact, so they
should be discussed together rather than in separate subsections.

*(Implementation note, now fixed: the gate's internal copy of the vote rule used
`BAND_MIN = −0.002` — the draft's **Rrs** floor — inside an **SR** pipeline, apparently
carried over from an Rrs context. It has been changed to −0.05 to match the production
guard. Verified inert: consensus set 105 087 px and identical caps before and after, for
the reason in (a). It stayed harmless by luck, not by design.)*

---

## 5. The clip bounds contradict a deliberate design choice, and the Rrs range is unphysical

Section 2.3 clips perturbed reflectance to `[0, 1]` for SR and `[−0.01, 0.5]` for Rrs.

**(a) The SR bound reintroduces a bias the pipeline removes on purpose.** Clipping at zero
truncates the noise distribution from below on precisely the darkest pixels — open water —
and therefore biases their ensemble mean upward. The current configuration sets
`clip_negative = false` for exactly this reason, and the methods document argues the point
explicitly. If the draft intends clipping, it contradicts the implementation; if it does
not, the equation should read `ρ_min = −∞` or the clip should be dropped from Eq. (6).

**(b) `Rrs_max = 0.5 sr⁻¹` is an order of magnitude beyond any water target.** Typical
Rrs spans 0.0001–0.05 sr⁻¹; even very turbid sediment-laden water rarely exceeds
~0.1 sr⁻¹. A ceiling of 0.5 sr⁻¹ never binds, so it is harmless — but it reads as an SR
bound that was carried across without conversion (0.5/π ≈ 0.16 would be the converted
form, still high). Worth either justifying or tightening.

---

## 6. Two internal contradictions in the draft, unrelated to units

Found while checking the above; flagging them since they affect the same section.

**(a) `τ_sig` appears in Eq. (5) and is denied in the next sentence.** Equation (5) includes
the low-signal condition `ρ_g + ρ_n > τ_sig` with `τ_sig = 0.003`, and the paragraph
immediately following states *"We impose no lower brightness floor, because open water is
the darkest target in the scene and such a floor would remove genuinely dark clear water
together with shadow."* The implementation agrees with the **prose**: the floor was
deliberately removed, with that reasoning recorded in the source. **Equation (5) should
drop the `τ_sig` term.** (If it is retained, note that `τ_sig` is also scale-dependent and
its Rrs value would be 9.5×10⁻⁴.)

**(b) The convergence criterion is honestly described but should say what it cannot do.**
Section 2.4 already notes that `SE(N)` falls as `N^-1/2` "with no natural plateau" and is
therefore a precision/cost trade-off. That is right, and worth keeping. It is a direct
consequence of the σ_P identity in Section 2.3: since `σ_P = √(P(1−P))` exactly,
`SE(N) = ⟨√(P(1−P))⟩/√N` is a restatement of `N` and contains no information about whether
the *spatial* process has stabilised. The draft's aggregate-statistics diagnostic is the
right companion; consider making the logical link between the two sections explicit, since
a reader may otherwise read Eq. (11) as a convergence test.

---

## 7. Suggested minimal edits

1. **Add one sentence to §2.1** stating that indices, the vote and `σ_rel` are
   scale-invariant, while gate caps, `σ_abs`, `ρ_min,idx`, `τ_sig` and the clip bounds are
   not — and that the latter are converted by `Rrs = ρ/π`.
2. **§2.3**: give `σ_abs` for both products (5×10⁻³ / 1.59×10⁻³ sr⁻¹); give `σ_rel` once,
   unqualified.
3. **§2.2, Eq. (4)**: either use the exact conversions (0.0382 / 0.0191 / 0.0159) or state
   the independent derivation of 0.030 / 0.018 / 0.014.
4. **§2.2, Eq. (5)**: remove the `τ_sig` term to match the prose and the implementation.
5. **§2.3, Eq. (6)**: reconcile the clip bounds with `clip_negative = false`, and justify
   or tighten `Rrs_max`.
6. **§2.2**: reconcile `ρ_min,idx` for SR (draft 0.0, implementation −0.05) and note that
   it interacts with `σ_abs`, since a NaN vote is a vote against water.
7. **Consider a validation requirement**: because the vote is scale-invariant but the gate
   is not, running the pipeline on both products and comparing should yield *identical
   vote maps* and *near-identical gates*. That equality is a cheap, strong unit test for
   the product-agnostic claim — and it would have caught every issue above.

---

## Reference values, for the table in §2.7

| parameter | SR | Rrs (sr⁻¹) | scale-invariant? |
|---|---|---|---|
| index thresholds `t_j` | 0 | 0 | ✔ yes |
| consensus count `k` | 2 | 2 | ✔ yes |
| `σ_rel` | 0.015 | 0.015 | ✔ yes |
| `σ_abs` | 5.00×10⁻³ | 1.59×10⁻³ | ✘ convert |
| gate cap NIR | 0.120 | 0.0382 | ✘ convert |
| gate cap SWIR1 | 0.060 | 0.0191 | ✘ convert |
| gate cap SWIR2 | 0.050 | 0.0159 | ✘ convert |
| gate percentile `q`, floor multiple `m` | 99, 2 | 99, 2 | ✔ yes |
| `ρ_min,idx` | −0.05 (impl.) | −0.0159 | ✘ convert |
| `τ_sig` (if retained) | 0.003 | 9.5×10⁻⁴ | ✘ convert |
| correlation length `l` | 3 px | 3 px | ✔ yes |
| threshold grid, anchor, `δ_max` | 0.02, 0.5, 0.03 | same | ✔ yes |

The adaptive path (Eq. 4) is itself scale-invariant — a percentile of the scene's own
consensus pixels rescales with the data — so only the **fixed fallback** bounds need
converting. That is worth stating, because it means the confusion only bites when a scene
has fewer than 500 consensus pixels and the fallback engages: **a rare branch, which is
the worst kind of unit bug to carry.**
