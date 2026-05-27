# Guyane Phase 1 — Literature notes (Task #9)

Five anchor papers for the **mangrove dynamics + orpaillage upstream** project.
Focus: what each paper claims, what gap remains, what we can exploit.

---

## 1. Anthony et al. 2010 — *Earth-Science Reviews* 103, 99–121
**"The Amazon-influenced muddy coast of South America: a review of mud-bank–shoreline interactions"**

### Claim
The Guianas coast (1500 km from Amapá BR to Orinoco VE) is reshaped by ~20 giant mud banks (~30 km long, 5 km wide) migrating westward at ~1 km/yr, sourced from the Amazon (~750 Mt/yr suspended load injected into the longshore current).

### Key numbers
- Mud bank wavelength: ~50 km
- Migration rate: ~1.0–1.5 km/yr westward
- Inter-bank zones: erosional, sandy
- Mud accretion → mangrove colonization in 5–10 yr

### Gap we exploit
Paper is a synthesis up to 2008. No annual mapping. Our S1 + S2 fusion at 10/20 m can deliver **annual coastal change vectors for 2018–2024** — first reproducible product since this synthesis.

---

## 2. Proisy et al. 2018 + Proisy et al. 2021
**Mangroves as a natural early-warning system of erosion on open muddy coasts in French Guiana** (HAL hal-03136875)

### Claim
- C-band SAR (Sentinel-1) cross-polarized (VH) channel correlates with mangrove canopy biomass; co-pol (VV) tracks structure / flooding.
- Mangrove fronts respond to mud-bank arrival/departure on a 1–5 yr lag.
- A canopy roughness index from VV/VH discriminates colonizing vs mature stands.

### Method
- Mostly visual + manual digitisation
- LiDAR campaigns 2008, 2014 for biomass calibration
- No reproducible code or pipeline published

### Gap we exploit
- Their 2009 LiDAR ground truth not reproducible at scale → we substitute with GMW v3 (Bunting 2022) for label, ESA WorldCover for cover validation.
- Their "early warning" framing is conceptual; we operationalise it as a per-annual change-detection layer integrated in a node graph.

---

## 3. Walcker et al. 2015 — *Journal of Biogeography*
**Fluctuations in the extent of mangroves driven by multi-decadal changes in North Atlantic waves**

### Claim
- French Guiana mangroves cover ~75% of the 350 km coastline.
- Net mangrove area oscillates ±20% over decades, driven by **trade-wind wave climate (NAO-correlated)** rather than local human pressure.
- Expansion threshold: mud must dewater / consolidate above critical topography.

### Gap we exploit
- Their dataset stops 2014; **2015–2024 not covered**.
- They use Landsat (30 m) — we deliver 10 m S2 + S1 fusion → smaller mud-bank tongues resolved.
- They never correlated this with anthropogenic upstream pressure (orpaillage). Our A+C scope directly addresses that.

---

## 4. Hammond et al. 2007 — Conservation Biology
**Causes and consequences of a tropical forest gold rush in the Guiana Shield**

### Claim
- Small-scale gold mining ("orpaillage", garimpo): hydraulic monitor + suction dredging + mercury amalgamation.
- Each pit injects 50–500 t/d of sediment + 0.3–1.5 g Hg per kg gold into headwater streams.
- Estimated 60% of French Guiana orpaillage in the 2000s was illegal.

### Key impacts measurable from RS
- Direct: forest patches cleared, often <5 ha (sub-Landsat-pixel) but visible at 10 m S2.
- Indirect: **turbidity plumes propagating down-stream** for 100+ km, weeks after the disturbance event.
- Mercury: not visible from RS but co-varies with suspended sediment.

### Gap we exploit
- Most monitoring relies on overflights (ONF Observatoire Mine Or, costly) or annual MapBiomas classes (lag).
- We propose a **continuous Sentinel-1 + Sentinel-2 detection layer**: S1 sees the bare ground signature year-round; S2 confirms when cloud-free.
- Coupled to downstream Hub'Eau turbidity stations → quantitative cause/effect chain (orpaillage area↑ at month *t* → turbidity↑ at month *t+δ*).

---

## 5. Bunting et al. 2022 — *Remote Sensing* 14, 3657
**Global Mangrove Extent Change 1996–2020: Global Mangrove Watch Version 3.0**

### Method
- L-band SAR (JERS-1 1996, ALOS 2007–10, ALOS-2 2015+) for baseline + change.
- Sentinel-2 optical: 4 indices (NDVI, NDWI, MNDWI, NDII), each thresholded; counts across the year define non-mangrove masks.
- Random Forest classifier on combined feature stack.
- Overall accuracy 95.2%, mangrove producer's accuracy 94.0%.

### Why it's our ground-truth backbone
- **Available 2010–2020 annual**, 10 m, free Zenodo download.
- French Guiana coast already classified — our model is validated against an independent reference.
- Recent product (2022 paper, v3 data 2020) → operational standard.

### Gap we exploit
- GMW v3 stops at 2020. **2021–2024 unmapped**.
- GMW does not couple mangrove change with upstream pressure.
- GMW uses fixed thresholds; we test whether learned (RF/GP) thresholds at 10 m improve detection of narrow colonising stands.

---

## Synthesis — what our paper claims that nobody else has

1. **First annual S1+S2 fusion product for the Guianese coast 2018–2024** at 10/20 m, fully reproducible (VNStudio graph + Zenodo data).
2. **Quantitative link between upstream orpaillage activity (MapBiomas / S2) and downstream Sinnamary mouth turbidity (Naïades) + mangrove front state (S1 backscatter)** — three sources, one causal chain.
3. **GMW v3 extension 2021–2024** as a byproduct, validated against ONF coastline surveys.
4. **Methodological contribution**: visual-programming graph as a reproducibility primitive for multi-sensor, multi-temporal environmental remote sensing — direct continuation of our turbidity proof-of-concept.

---

## Sources

- [Anthony et al. 2010 Earth-Sci Rev (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0012825210001200)
- [Proisy et al. — mangroves as erosion early warning (HAL)](https://hal.science/hal-03136875)
- [Walcker et al. 2015 — NAO-driven mangrove fluctuations (ResearchGate)](https://www.researchgate.net/publication/281145431_Fluctuations_in_the_extent_of_mangroves_driven_by_multi-decadal_changes_in_North_Atlantic_waves)
- [WWF Guianas — gold mining impact report (PDF)](https://www.wwf.fr/sites/default/files/doc-2022-11/Gold%20mining%20impact%20on%20forest%20&%20freshwater%20of%20the%20Guiana%20Shield%20-%20ECOSEO%20Project.pdf)
- [Bunting et al. 2022 GMW v3 — MDPI Remote Sensing](https://www.mdpi.com/2072-4292/14/15/3657)
- [Influence of small-scale gold mining on French Guiana streams (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1470160X1100224X)
- [Physical habitat changes from logging & mining FG (KMAE)](https://www.kmae-journal.org/articles/kmae/pdf/2014/04/kmae140043.pdf)
