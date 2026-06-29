# Rapport — Pipeline Monte-Carlo water-mask (Seine)

Date : 2026-06-28 · Templates : `mc_water_mask.vn`, `15-53.vn`

Résumé des modifications apportées au pipeline de masquage d'eau probabiliste
(MC sur Rrs ACOLITE Sentinel-2), côté moteur (plugins) et côté templates.

---

## 1. Changements moteur (plugins Python)

### 1.1 `geo_raster_noise` (driver Monte-Carlo)
Fichier : `engine/plugins/geo_raster_noise.py`

| Ajout | Rôle |
|-------|------|
| `max_ticks` (Target N, 0 = ∞) | Après N réalisations → `_running=False`. Le moteur met le nœud en cache → **CPU idle**. « fais 100 passes et arrête-toi ». |
| `reset` (bouton / trigger) | Front montant → `tick=0`, reprend le run. |
| sortie scalaire `tick` | Numéro de réalisation, propagé en aval (auto-reset de la chaîne). |

Mécanisme : seul un nœud *realtime source* peut stopper la boucle (le moteur teste
`proc._paused` pour le rendre cacheable). L'auto-stop **doit** donc vivre sur le noise,
pas sur l'accumulateur. Reproductible : `seed + tick`.

### 1.2 `sci_frame_accumulator`
Fichier : `engine/plugins/sci_frame_accumulator.py`

| Ajout / changement | Rôle |
|--------------------|------|
| mode `cumulative` (défaut **ON**) | Agrège **toutes** les frames depuis reset via Welford (mémoire O(1), ne stocke pas N scènes) → estimation N-échantillons **stable** de P(water). L'ancienne fenêtre glissante faisait dériver P sur les 64 dernières frames. |
| `target_n` | Plafond optionnel (0 = illimité ; le noise pilote l'arrêt). |
| `reset` : bool → **trigger** (bouton) | Demande #2 utilisateur. |
| entrée `tick` | Auto-clear quand le tick amont retombe → **un seul bouton Reset (sur le noise) réinitialise toute la chaîne**. |
| sortie `done` (0/1) | Signal « N atteint » (info/metrics — **ne pas** recâbler vers le noise : cycle interdit, Kahn supprimerait les nœuds). |
| std mode | Vraie variance `sqrt(M2/n)` (= U = P(1−P)). |

Tests : `engine/tests/test_sci_frame_accumulator.py` (5) + `test_geo_raster_noise.py`
(+2). Suite complète : **419 passed**.

---

## 2. Tuning des paramètres (physique télédétection + jeu d'indices du papier)

Identique sur les deux templates.

### 2.1 `noise` — budget d'incertitude réaliste
```
sigma_rel : 0.02  → 0.015     # papier : 1.5 % (S2 + ACOLITE)
sigma_abs : 0.005 → 0.001     # 0.005 sr⁻¹ noyait l'eau sombre (~50–100 % bruit)
seed      : 42  (reproductible ; mettre -1 pour des IC inter-runs)
max_ticks : 100
```

### 2.2 `idx` — 4 indices max-indépendants = jeu du papier
```
Avant : [NDWI, MNDWI, AWEInsh, AWEIsh]   # 2 AWEI ≈ 0.9 corrélés → 1 vote gaspillé
Après : [NDWI, MNDWI, AWEIsh,  MBWI]
  expr1 AWEIsh = BLUE + 2.5*GREEN - 1.5*(NIR + SWIR) - 0.25*B6   # variante anti-ombre (Paris urbain)
  expr2 MBWI   = 2*GREEN - RED - NIR - SWIR - B6                 # indépendant (rouge + 2 SWIR), robuste turbide
```
NDWI/MNDWI activés par toggles. SWIR = SWIR1 (B5), B6 = SWIR2.

### 2.3 `vote` — consensus (inchangé, conforme papier k≥2)
```
(1*(B1>0)+1*(B2>0)+1*(B3>0)+1*(B4>0)) >= 2
```
B1..B4 = [NDWI, MNDWI, AWEIsh, MBWI], tous « eau > 0 ».

### 2.4 `nir_gate` — contrainte physique turbide-aware (gain principal)
```
Avant : (B4 < 0.01) & (B2 > 0.003)                          # NIR seul, trop strict
Après : (B4 < 0.025) & (B5 < 0.018) & (B6 < 0.014) & (B2 > 0.002)
```
Clé : le sédiment **lève le NIR mais pas le SWIR**. On relâche NIR (garde l'eau turbide)
et on serre sur SWIR1/SWIR2 (vrais discriminants eau ; la terre/bâti est haute dans les
deux). `B2>0.002` = plancher bas-signal (rejette ombre/bruit). Bornes alignées papier
(0.030 / 0.018 / 0.014).

### 2.5 `acc_mean` (P) et `acc_std` (U)
```
mode 0 (mean = P_water) / mode 3 (std = U)
cumulative : true,  target_n : 0,  reset : 0
```

### 2.6 `topo` (geo_persistence) — binarisation finale sans seuil
```
min_persistence : 0.15 → 0.0   # auto-détection du plus grand gap du spectre de persistance
max_pixels      : 500k → 1M    # sécurité reach complet
feature : maxima (bright), connectivity : 8
```

---

## 3. Câblage ajouté

Les deux templates :
- `noise.scalar__tick → acc_mean.scalar__tick`
- `noise.scalar__tick → acc_std.scalar__tick`

`15-53.vn` uniquement :
- ajout du nœud `acc_std` (MC Uncertainty, mode 3) pour parité
- `mask_and.mask → acc_std.image`

---

## 4. Bugs corrigés (spécifiques à `15-53.vn`)

1. **`acc_mean reset:true`** → `0`. Reset permanent = buffer vidé à chaque tick →
   l'accumulateur n'accumulait **jamais**, P(water) ne pouvait pas se former.
2. **Double arête `pred` dans `metrics`** : `topo→metrics` **et** `filter→metrics`
   arrivaient sur `mask__pred`. Supprimé la directe ; gardé
   `topo → mask_filter_area(fill_holes) → metrics` (masque sans trous internes).

---

## 5. Rappel d'usage / piège

- **Lancer** : ▶ Start sur `noise` → 100 passes → stop auto. **Reset** = bouton sur `noise`
  (réinitialise toute la chaîne).
- **`metrics.pred` = masque binaire** (`acc_mean → topo → filter`), **jamais `acc_std`**.
  La carte U (std) est la variance de Bernoulli : ≈ 0 partout sauf un liseré aux berges →
  binarisée à >127 elle donne un masque **vide** → `FN = toute la GT` (symptôme observé :
  IoU=Dice=0, FN=174009). U sert à *visualiser* l'incertitude et à l'analyse
  bridge/eau libre, pas à scorer.

---

## 6. Reste à faire (prochaines étapes recommandées)

- **Baseline déterministe** (noise OFF, 1 réalisation) → comparer P-MC vs masque seuil-fixe.
- **Analyse bridge** : distribution P/U sur polygones de ponts vs eau libre (Δ séparation).
- **Spearman** par indice vs P(water) + binning quantile (sensibilité).
- Réconcilier le texte du papier avec l'implémentation (N=100, σ=1.5 %, persistence vs seuil 0.70).
