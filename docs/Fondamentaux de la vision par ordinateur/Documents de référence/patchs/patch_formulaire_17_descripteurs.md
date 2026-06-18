# Patch du formulaire maître — ajout de la section 17
## Descripteurs locaux et appariement

> **Mode d'emploi.** Bloc à insérer dans `0_-_formulaire_vision_ordinateur.md`, à la fin (après la section 16, Statistiques robustes), au format terse du formulaire : énoncé + glose d'une ligne. Il couvre le maillon détection→description→appariement→filtrage, jusqu'ici éclaté entre les sections 3, 5, 6, 8 et 16.
>
> **Renvoi à ajouter** en §5.3 (DoG) : « extrema dans l'espace d'échelle → §17 ». Et en §6.5–6.6 (Harris/Shi-Tomasi) : « détection alimentant la description → §17 ».

---

## 17. Descripteurs locaux et appariement

### Échelle caractéristique (espace d'échelle)
```
réponse(x,y,σ) = σ² · ∇²[G_σ * I](x,y)        (LoG normalisé en échelle)
DoG ≈ (k−1)σ² · ∇²G_σ * I                       (approximation rapide, §5.3)
```
Extremum en (x,y,σ) = position + échelle d'un blob. Pour un blob d'écart-type s, le pic tombe à σ = s. Test de courbure (rapport des valeurs propres de la hessienne < r ≈ 10) pour rejeter les contours.

### HOG (histogramme de gradients orientés)
```
par pixel : ‖∇I‖ , θ = arctan2(Iᵧ, Iₓ) mod 180°
cellule   : histogramme 9 bins × 20°, vote = magnitude
bloc      : normalisation L2 (atténue l'éclairage)
```
Invariant à l'éclairage (gradient + normalisation), non invariant en rotation. Détection à pose connue (piétons).

### SIFT (descripteur 128-D)
```
1. orientation dominante : pic de l'histogramme 36 bins des gradients
2. descripteur : grille 4×4 × 8 orientations = 128 composantes (référentiel tourné)
3. normalisation L2 → clip à 0,2 → re-normalisation L2
```
Invariant en similitude + robuste à l'éclairage. RootSIFT : √composantes (après L1) puis L2 = distance de Hellinger, gain quasi gratuit.

### ORB / BRIEF (descripteur binaire)
```
bitᵢ = 1 si I(aᵢ) < I(bᵢ) sinon 0      (n ≈ 256 paires fixées)
distance : Hamming = popcount(d₁ XOR d₂)
```
ORB = FAST + BRIEF orienté (rotation via centroïde, §2). Léger et rapide (32 octets), moins discriminant que SIFT. Temps réel, SLAM.

### Ratio test de Lowe
```
accepter ⟺ d₁ / d₂ < τ        (τ ≈ 0,8 ; d₁, d₂ = 1er et 2e plus proches voisins)
```
Mesure la distinctivité d'un appariement, pas sa justesse. Rejette les structures répétées. ~90 % des faux appariements éliminés pour ~5 % de vrais perdus.

### Appariement → modèle robuste
```
N = log(1−p) / log(1−wⁿ)        n = 4 pour une homographie (§8, §16)
```
RANSAC sur les correspondances filtrées → homographie/fondamentale. w = 0,5 → 72 itérations ; w = 0,3 → 567. Le ratio test, en élevant w, effondre le coût de RANSAC.

---

## Mise à jour de l'état d'avancement (`INSTRUCTIONS_STYLE_PROJET.md`, §9)

Ajouter à la liste des sections :

```
17. Descripteurs locaux et appariement — ✅ (`chapitre_17_descripteurs_locaux.md`)
```

Et, si les sections 11–16 sont désormais rédigées, passer leurs ⬜ en ✅ (le suivi semble en retard sur l'état réel du manuscrit).
