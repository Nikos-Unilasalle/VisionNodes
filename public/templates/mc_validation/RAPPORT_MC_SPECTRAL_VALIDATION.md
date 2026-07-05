# MC Spectral Validation — Rapport de session

Pipeline: `public/templates/mc_validation/huanghe.vn` (nom historique, **place-agnostique** — ne pas se fier au nom pour la localisation étudiée).
Template propre versionnée: `public/templates/mc_validation/mc_spectral_validation.vn` (branche `main`, commit `d00119f`).

## 1. Objectif de la pipeline

Valider un masque d'eau Monte-Carlo (consensus de 4 indices spectraux, perturbé par bruit capteur simulé) contre une vérité terrain **portable** (ESA WorldCover + OSM), sans shapefile local — testable sur n'importe quelle zone du globe.

## 2. Architecture (état actuel)

```
Copernicus CDSE (SR, B04,B03,B02,B08,B11,B12 = Red,Green,Blue,NIR,SWIR1,SWIR2)
  → geo_raster_noise (MC, sigma_rel=0.015, spatial_corr_px=3, N=163)
  → geo_spectral_indices (NDWI, MNDWI, AWEIsh, MBWI — ratios normalisés)
  → vote consensus k≥2/4 → geotiff_to_mask
  → mask_operations AND (Adaptive Gate p99 scene-adaptive)
  → sci_frame_accumulator (mode=mean) = P(water) ∈ [0,1]
  → sci_frame_accumulator (mode=std)  = incertitude MC par pixel

GT (indépendante, portable):
  geo_land_cover (WorldCover class 80 = Water)      → ow
  geo_osm_overpass (selector=["bridge"], buffer_m=12) → OSM bridges
  mask_operations OR (water ∪ bridge)                → ext
  feat_morphology_adv (Dilate, ellipse, 15px×2)       → domain (corridor élargi ~5%)

Validation (node "Index Correlation" — nom historique, fait bien plus que Spearman):
  - Spearman P vs 4 indices, par classe (All river=domain / Open water=ow / Bridge=ext&~ow)
  - Distributions Open water vs Bridge par feature (Δμ + Cohen's d, σ-normalisé)
  - AUROC indice-vs-GT (indépendant de P, non circulaire)
  - out_gt, out_ow, out_ext, out_domain exposés pour les métriques en aval

Métriques (contraintes au corridor via AND avec domain):
  - sci_mask_metrics (Precision/Recall/F1/IoU)
  - sci_boundary_f1 (tolérance 3px — misalignment GT)
  - Threshold Sweep (F1/IoU/Youden vs seuil, pick robuste)
  - MC Convergence (SE=σ/√N vs N, détecte N optimal)
```

## 3. Nodes créés / modifiés (moteur, réutilisables partout)

| Node | Fichier | Changement |
|---|---|---|
| `geo_osm_overpass` | `engine/plugins/geo_osm_overpass.py` | **Nouveau.** Générique: n'importe quel tag Overpass (`["bridge"]`, `["natural"="water"]`, `["highway"]`...), rasterisé sur la grille de référence. Buffer points/lignes en CRS métrique (auto-détecte si la référence est géographique) — bug initial: buffer en degrés sur une réf EPSG:4326 noyait toute la scène, corrigé. |
| `feat_morphology_adv` | `engine/plugins/watershed_analysis.py` | Ajout **Dilate** / **Erode** (manquaient — seuls Opening/Closing/Gradient/TopHat/BlackHat existaient). Remplace le hack "Gradient" utilisé comme dilatation (marchait sur un ruban fin mais évidait les plans d'eau larges en anneau creux). |
| `filter_blob_filter` | `engine/plugins/blob_filter.py` | Ajout `circ_min/max` (circularité 4πA/P²) et `elong_min/max` (élongation via moments, invariant rotation) pour filtrer par forme, pas seulement par aire. **Fix bug**: normalisation d'entrée ne gérait pas les masques bool/0-1 → seuillage à 127 vidait tout → sortie vide. Corrigé pour bool/0-1/0-255/float. |
| `geo_raster_noise` | `engine/plugins/geo_raster_noise.py` | Ajout `spatial_corr_px` (0 = iid, >0 = bruit spatialement corrélé via blur + renormalisation variance). Le bruit capteur/atmo réel n'est pas iid — le iid sous-estime l'incertitude ensemble. |

Tous synchronisés dans les 3 dossiers `resources/engine/plugins` (release/debug/racine).

## 4. Conseil externe reçu — évalué et rejeté (avec justification)

Un avis extérieur proposait 4 changements. Verdict après lecture réelle de la pipeline:

| Proposition | Verdict | Pourquoi |
|---|---|---|
| Seuillage adaptatif au lieu de seuil statique | ❌ Rejeté | Les indices sont déjà des ratios normalisés (scale-invariant), le vote est sur le signe, et l'Adaptive Gate calcule déjà des caps p99 scène-adaptatifs. Le seuil 0.7 porte sur P (probabilité MC), pas sur la réflectance — le rendre adaptatif casserait l'interprétation probabiliste. |
| Lisser (médian/gaussien) avant seuillage | ❌ Rejeté (contresens) | Le bruit est **volontaire** (pilote l'ensemble MC). Le lisser tue la propagation d'incertitude, corrèle les tirages (casse l'iid), et la moyenne MC sur N tirages EST déjà le débruitage. |
| Éroder le GT pour tolérer le misalignment | ⚠️ Intention valide, outil dangereux | La rivière est fine — l'éroder peut l'effacer. **Fix retenu**: `sci_boundary_f1` (métrique de frontière tolérante), pas érosion du masque. |
| Normaliser les bandes uniformément entre frames (accumulateur = "temporel") | ❌ Mauvais diagnostic | L'accumulateur est Monte-Carlo (mêmes bandes de base + bruit frais à chaque tirage), pas temporel. Pas de dérive de normalisation inter-frame possible par construction. |

## 5. Améliorations câblées cette session (les 3 pistes validées)

### 5.1 Bruit spatialement corrélé
`geo_raster_noise.spatial_corr_px = 3` (px). Le bruit iid par pixel sous-estimait l'incertitude → P trop tranché (0/1 quasi partout, peu de valeurs intermédiaires, observé dans les scatter/distributions). Un bruit corrélé (blur + renorm variance, σ marginal préservé) modélise mieux l'erreur capteur/atmo réelle.

### 5.2 Convergence MC (choix de N)
Nouveau node **"MC Convergence"** (`mc_conv`): trace SE(N) = σ_scène/√N (σ via l'accumulateur std), détecte N optimal = premier N (≥ `min_n`) sous une tolérance SE. Params `TOL` et `MIN_N` exposés en entrées (`scalar_input`), pas de magic number caché.
**Résultat mesuré: N optimal = 163** (à la tolérance choisie par l'utilisateur). Aucun vrai plateau/coude (décroissance pure en 1/√N) — le choix de N est un arbitrage précision/coût explicite via la tolérance, pas un point "magique".

### 5.3 Boundary-F1 (tolérance de misalignment)
Node `sci_boundary_f1` (natif) câblé, tolérance 3px, en remplacement de l'érosion du GT proposée par le conseil externe.

## 6. Bug trouvé et corrigé en cours de route: GT non contraint au corridor

**Constat (signalé par l'utilisateur, confirmé):** `sci_mask_metrics` et `sci_boundary_f1` comparaient `pred` (P≥seuil) et `truth` (`out_gt` = tout WorldCover-eau ∪ OSM-ponts) sur **toute la scène**, pas seulement dans le corridor fluvial. Un plan d'eau urbain parasite (fontaine, toit humide, piscine mal classée) polluait les métriques alors même que le node de corrélation (Spearman/Cohen's d/AUROC) restreignait déjà correctement ses propres classes au domaine.

**Fix:** 2 nodes `mask_operations` (AND, natifs — pas de nouveau logic_python) insérés entre pred/truth et les deux nodes de métriques, contraignant les deux au `domain` (corridor dilaté) avant comparaison.
```
pred ∩ domain  → metrics.pred, boundary_f1.pred
truth ∩ domain → metrics.truth, boundary_f1.truth
```
Le node Threshold Sweep n'était pas affecté (restriction déjà faite en interne via son port `c`=domain).

## 7. Threshold Sweep — nouveau node, résultat et limite trouvée

Node **"Threshold Sweep (F1/IoU/Youden)"**: balaie P(water) 0→1, calcule Precision/Recall/F1/IoU vs seuil sur le GT (contraint au corridor), marque le seuil optimal. Params `metric` (0=F1/1=IoU/2=Youden) et `step` exposés en `scalar_input`.

**Résultat observé:** courbe avec une falaise abrupte entre t=0 et t≈0.02 (P quasi-binaire: fond exactement à 0), puis un **plateau quasi plat** de t=0.02 à t=1.0 (F1 reste ~0.88-0.89). L'argmax brut pointait sur t=0.02 — **artefact du plateau**, pas un vrai optimum (le seuil 0.7 choisi initialement était déjà dans la zone haute du plateau, F1 quasi identique).

**Fix v1 (raté):** pick "le seuil le plus haut dans une tolérance de 99%". Sur les vraies données, le plateau couvrait ~98% de la plage → ce critère dégénérait vers l'**autre extrême** (t=1.0), aussi arbitraire que la falaise à 0.02, juste inversé.

**Fix v2 (retenu):** **médiane** des seuils satisfaisant la tolérance — centre le pick au milieu du plateau, insensible aux deux bords. Testé: plateau large→milieu du plateau, pic net→proche de l'argmax réel. Ajout d'un warning si le plateau couvre >30% de la plage ("la métrique ne discrimine presque rien ici, préférer un seuil motivé par le domaine comme 0.5=majorité"). Le graphe masque la falaise near-0 (`PLOT_MIN=0.05`). `out_best` expose `raw_argmax_threshold` et `plateau_fraction` pour transparence.

**Résultat final mesuré: t=0.520, F1=0.8851** — proche du 0.7 choisi initialement à l'œil (même plateau), mais avec une sémantique plus nette ("majorité simple des tirages MC") et surtout justifié par les données plutôt que par intuition.

### 7.1 Auto-calibration du seuil P

Le seuil de `feat_threshold_adv` (node "Advanced Threshold", celui qui binarise P pour la sortie finale) était une valeur figée (179/255 ≈ 0.7). Externalisé (`paramPorts`/`externalizedParams`, même mécanisme déjà utilisé pour `max_ticks`/`target_n`/`iterations` ailleurs dans la pipeline) et branché directement sur `thr_sweep.out_optimal_threshold_255` — **le seuil se recalcule automatiquement à chaque run** au lieu d'être une constante choisie une fois. Pas de cycle: `thr_sweep` dépend de `acc_mean`/`out_gt`/`domain`, jamais de `feat_threshold_adv` lui-même.

## 8. Pistes restantes à explorer (non câblées)

| Piste | Pourquoi | Statut |
|---|---|---|
| **Indices corrélés** | Les 4 indices (NDWI, MNDWI, AWEIsh, MBWI) partagent des bandes communes → le vote k≥2/4 les traite comme indépendants, ce qui **surestime la confiance** du consensus (ils ne sont pas 4 votes indépendants). Décorréler (ACP sur les 4 indices avant vote) ou pondérer par redondance. | Non fait |
| **Validation semi-circulaire (Spearman-vs-P)** | Le panneau Spearman-vs-P corrèle P avec les indices **qui le composent** → tous proches (~0.79 observé), peu discriminant entre indices. Déjà mitigé par l'ajout de l'AUROC-vs-GT (indépendant, discrimine bien: MBWI/AWEIsh > NDWI/MNDWI au Cohen's d) — mais le panneau Spearman-vs-P reste affiché, à annoter clairement comme "cohérence interne" et non "validation indépendante". | Partiellement adressé |
| Sensibilité du seuil de vote (k=1..4 sur 4) | k=2 jamais testé contre k=1/3 — balayage similaire au threshold sweep, sur le seuil de vote plutôt que sur P. | Proposé, pas fait (priorité choisie: threshold sweep P d'abord) |
| ~~Échelle du bruit (`sigma_rel=0.015`)~~ | Voir §9 — **traité**. | ✅ Fait |
| Réglages "au jugé" sans critère objectif dispo | Taille corridor (15px × 2 iter), `min_area` blob filter (258), `buffer_m` OSM (12m) — pas de GT dédiée pour les calibrer par courbe, ajustement à l'œil sur le rendu. | Accepté tel quel |

## 9. Calibration du bruit — `sigma_abs` (plancher absolu)

**Recherche (specs ESA + littérature aquatique):** précision radiométrique L2A officielle <5% (cible 3%), <1% inter-bandes — mais valable pour cibles bien éclairées. Sur l'**eau** (signal faible, surtout NIR/SWIR), l'incertitude **relative** documentée explose (>1000% rapportés en NIR sur pixels sombres, cf. Radiometric Uncertainty Tool / littérature atmospheric-correction) car le bruit capteur a un **plancher absolu quasi-constant** alors que le signal s'effondre.

**Bug de modèle trouvé:** `sigma_abs` était à **0** → `σ_eff = sigma_rel·|value|` tend vers 0 exactement quand la réflectance tend vers 0 (eau en NIR/SWIR) — **l'inverse du comportement réel**, qui explose à cet endroit. Concrètement: le modèle sous-injectait du bruit sur les bandes qui pilotent la discrimination eau/non-eau — cause plausible additionnelle du P quasi-binaire observé (au-delà du fait que le vote soit un gate dur avant accumulation).

**Fix appliqué:** `geo_raster_noise.sigma_abs = 0.005` (plancher, en plus du `sigma_rel=0.015` existant). **Valeur estimée, pas une norme officielle** — aucune source ne documente un plancher précis en unités de réflectance pour ce cas d'usage ; point de départ raisonné à affiner empiriquement via les outils déjà en place (MC Convergence, Threshold Sweep, distributions Δμ/Cohen's d) en observant l'effet sur P.

**Non traité (hors scope, noté pour plus tard):** le bruit réel varie par bande (VNIR meilleur SNR que SWIR sur eau) — le node applique un σ uniforme à toutes les bandes. Amélioration possible: `sigma_abs`/`sigma_rel` par bande plutôt que scalaire unique.

Sources: [Sentinel-2 Radiometric Cal/Val](https://elib.dlr.de/133491/1/VH-RODA-Sentinel%202%20-%20Radiometric%20Validation.pdf) · [DQR Sentinel-2 MSI L2A juillet 2025](https://sentiwiki.copernicus.eu/__attachments/1673423/OMPC.CS.DQR.002.06-2025-Sentinel-2-MSI-L2A-DQR-July-2025-87.pdf) · [Uncertainty estimates Sentinel-2 TOA](https://www.tandfonline.com/doi/full/10.1080/22797254.2018.1471739) · [Atmospheric correction assessment coastal/inland waters](https://www.sciencedirect.com/science/article/pii/S0034425719301099)

### 9.1 Effet observé + bug NDWI/MNDWI découvert en conséquence

Après application de `sigma_abs=0.005`: **MC Convergence** montre une décroissance bien plus lente vers une tolérance stricte (0.0005, encore loin à N=175) — confirme que P a maintenant une vraie incertitude, plus quasi-binaire. **Threshold Sweep**: plateau tombé de 98% à **29%**, vraie courbe precision/recall visible, pick robuste passé à un point milieu significatif (t=0.16, F1=0.896) au lieu d'un bord dégénéré.

**Bug trouvé en creusant les distributions:** panneaux NDWI/MNDWI avec un axe **-8000 à +6000** (impossible, un NDWI est borné [-1,1]) et un **Cohen's d proche de 0** (0.02-0.04) malgré un **AUROC excellent** (0.97+) — contradiction. Cause: `geo_spectral_indices.py` calcule NDWI/MNDWI via `(a-b)/(a+b+1e-8)` **sans protection** contre un dénominateur proche de zéro (eau sombre en NIR/SWIR, précisément où le bruit ajouté est maintenant le plus fort). Quelques pixels explosent à des valeurs extrêmes → détruit moyenne/variance (Cohen's d, histogramme) mais épargne Spearman/AUROC (basés sur le rang, insensibles à la magnitude) — d'où l'incohérence exacte observée.

**Fix appliqué (natif, pas de nouveau code):** le plugin a déjà un garde-fou désactivé par défaut (`guard_invalid=False`) qui clippe à [-1,1] et NaN les pixels invalides/dénominateur quasi-nul (reproduit le script de référence `MC_water_masking_v1.py`). Activé sur le node "4 Water Indices": `guard_invalid=True`, `valid_min=-0.002` (défaut documenté). À vérifier au prochain run: distributions NDWI/MNDWI dans une plage sensée, Cohen's d cohérent avec l'AUROC.

## 10. Décisions de design à retenir (pour ne pas les redéfaire)

- **Toujours préférer un node natif existant à du `logic_python`** quand l'un couvre le besoin (ex: `mask_operations` AND pour contraindre au domaine, plutôt qu'un nouveau node Python).
- **Jamais de magic number caché dans un `logic_python`**: tout seuil/paramètre devient une entrée de port, alimentée par un `scalar_input` (ou équivalent) exposé en canvas — pattern déjà appliqué à `mc_conv` (TOL, MIN_N) et `thr_sweep` (metric, step).
- **GT toujours contrainte au domaine d'analyse** avant toute métrique — vérifier systématiquement pour tout nouveau node de scoring ajouté.
- **Nodes moteur ajoutés doivent être génériques**, pas spécifiques au cas d'usage courant (ex: `geo_osm_overpass` accepte n'importe quel tag Overpass, pas juste les ponts; `feat_morphology_adv` Dilate/Erode sert à tout node en amont, pas seulement au corridor).
- Fichier de travail `huanghe.vn` **subit un clobber de l'app** (re-sauvegarde en mémoire) — toujours vérifier l'état réel du fichier sur disque avant de ré-injecter du code, ne jamais supposer qu'un edit précédent a survécu sans relire.
