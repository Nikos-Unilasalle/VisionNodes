# Patch de contenu — Chapitre 14 : ajout de la section Modèles de bruit
## Section fondatrice (Poisson–Gauss)

> **Mode d'emploi.** Patch de **contenu** au format des sections du chapitre. Il comble un manque transversal : le livre invoque « le bruit » à de nombreux chapitres (le moment d'ordre élevé l'amplifie, ch. 2 ; dériver l'amplifie, ch. 6 ; un filtre est un a priori contre lui, ch. 5) sans jamais en poser de modèle. Cette section fonde le terme.
>
> **Placement recommandé : nouvelle section 14.1**, en tête du chapitre Qualité d'image — on ne peut pas mesurer une dégradation sans modèle de ce qui dégrade. Les sections MSE/PSNR, SSIM, entropie reculent d'un cran.
>
> **Renvois entrants à ajouter** : ch. 2 (« le bruit qu'amplifie le moment d'ordre élevé suit le modèle du §14.1 »), ch. 6 (idem pour la dérivée), ch. 5 (« le filtre choisi suppose un modèle de bruit — voir §14.1 »).

---

## Section 14.1 — Modèles de bruit (Poisson–Gauss)

On parle du bruit comme d'un voile gris uniforme posé sur l'image. C'est faux deux fois. Le bruit dominant en imagerie n'est pas additif et n'est pas uniforme : il **dépend du signal**, parce qu'il vient pour l'essentiel du comptage des photons eux-mêmes. Une zone claire est, en valeur absolue, plus bruitée qu'une zone sombre. Le fil de la section est là : un modèle de bruit est un a priori sur la façon dont la mesure s'écarte de la vérité, et le débruiteur que l'on choisit ne fait qu'épouser ce modèle. Tout le reste du chapitre mesure des écarts ; ici on dit de quelle nature ils sont.

### 14.1.1 Bruit de grenaille (Poisson)

**Définition.** Un capteur compte des photons. Sur un temps d'exposition donné, le nombre de photons reçus par un pixel d'éclairement moyen `λ` (en électrons) est une variable aléatoire de Poisson :

```
P(k) = λᵏ e^(−λ) / k!     E[k] = λ ,  Var[k] = λ
```

**Dérivation — variance = moyenne.** Pour une loi de Poisson, la fonction génératrice donne `Var = λ = E[k]`. La conséquence pratique se lit sur le rapport signal/bruit :

```
SNR = E[k] / √Var[k] = λ / √λ = √λ
```

Le SNR croît comme la racine du signal. ∎ Doubler l'exposition multiplie le SNR par `√2`, pas par 2 : c'est la raison physique pour laquelle on n'efface jamais le bruit en « éclairant un peu plus ».

**Ce que ça mesure / l'angle mort.** Compter des photons revient à compter des gouttes dans un seau sous la pluie : un seau plus rempli a reçu plus de gouttes, mais son comptage fluctue aussi davantage en valeur absolue, et de moins en moins en proportion. C'est tout `σ = √λ`. Le bruit de grenaille est **multiplicatif en écart-type** (`σ = √λ`) et incompressible : il est inscrit dans la lumière, pas dans l'électronique. On ne peut pas l'« enlever » par un meilleur capteur, seulement en collectant plus de photons (temps, ouverture, binning). L'angle mort classique : croire qu'une image sombre est « propre » parce qu'elle a peu de bruit en valeur absolue. Elle a peu de bruit *et* peu de signal — son SNR est mauvais (`√16 = 4` pour 16 photons).

### 14.1.2 Bruit de lecture (Gaussien additif)

**Définition.** L'électronique de lecture ajoute un terme gaussien d'écart-type `σ_r` (en électrons), **indépendant du signal** :

```
n_lecture ~ N(0, σ_r²)
```

C'est le plancher de bruit : ce qui reste quand `λ → 0`. Il domine dans les zones sombres et les courtes expositions ; il est négligeable dès que `λ ≫ σ_r²`.

### 14.1.3 Le modèle Poisson–Gauss et la loi de variance affine

**Définition.** En combinant les deux sources, la mesure (en électrons) a pour moyenne `λ` et pour variance la somme des deux :

```
Var(I) = λ + σ_r²                     (en électrons²)
```

En sortie de convertisseur, avec un gain `g` (ADU par électron) et `I = g·λ`, on obtient la forme universellement utilisée — la **loi de variance affine** :

```
σ²(I) = a·I + b      avec   a = g  (pente, part Poisson)   b = g²·σ_r²  (plancher, part lecture)
```

C'est l'équation de la *photon transfer curve* : on la trace en mesurant variance contre moyenne sur des zones plates de luminosités croissantes ; la pente donne le gain, l'ordonnée à l'origine donne le bruit de lecture.

**Exemple numérique (vérifié).** Capteur de bruit de lecture `σ_r = 5 e⁻`. Deux pixels :

| Zone | Signal `λ` (e⁻) | Var = λ + σ_r² | σ | SNR = λ/σ | Régime |
|---|---|---|---|---|---|
| Claire | 900 | 900 + 25 = **925** | 30,4 | **29,6** | grenaille (900 ≫ 25) |
| Sombre | 16 | 16 + 25 = **41** | 6,4 | **2,5** | lecture (25 > 16) |

Dans la zone claire, le bruit de lecture (`25`) est négligeable devant la grenaille (`900`) : le SNR suit `√λ`. Dans la zone sombre, c'est l'inverse — le plancher de lecture domine et abîme le SNR bien plus que ne le ferait la seule grenaille (`√16 = 4` deviendrait `2,5`). En ADU avec `g = 0,5` : pixel clair `I = 450`, `σ² = 0,5·450 + 0,5²·25 = 225 + 6,25 = 231,25` ; pixel sombre `I = 8`, `σ² = 4 + 6,25 = 10,25`. Les deux lectures de la loi affine concordent.

### 14.1.4 Stabilisation de variance (Anscombe)

**Idée.** La plupart des débruiteurs (et toute la théorie du seuillage en ondelettes) supposent un bruit gaussien d'écart-type **constant**. Or ici `σ` dépend de `I`. La transformée d'Anscombe rend la variance ≈ constante :

```
f(x) = 2·√(x + 3/8)        ⟹  Var[f(x)] ≈ 1  pour tout λ (Poisson pur)
```

**Vérification (simulation).** Variance après transformée, sur des Poisson de moyennes très différentes :

```
λ =   4  → Var(x) ≈   4    → Var(Anscombe) ≈ 1.00
λ =  30  → Var(x) ≈  30    → Var(Anscombe) ≈ 1.00
λ = 100  → Var(x) ≈ 100    → Var(Anscombe) ≈ 1.00
λ = 900  → Var(x) ≈ 900    → Var(Anscombe) ≈ 1.00
```

Le protocole standard : Anscombe → débruitage gaussien (BM3D, ondelettes, ou même un simple filtre) → **inverse exact non biaisé** d'Anscombe. L'angle mort : l'inverse naïf `(f/2)² − 3/8` introduit un biais aux faibles comptes ; on utilise la formule d'inverse non biaisée de Makitalo–Foi, sous peine de noircir les zones sombres.

### 14.1.5 Estimer le bruit — le lien avec les statistiques robustes

**Définition.** Sur une image réelle, on ne connaît pas `σ`. L'estimateur de Donoho le lit sur les coefficients de détail les plus fins (ondelette HH du premier niveau), via la MAD du chapitre 16 :

```
σ̂ = MAD(coeffs HH) / 0,6745        (0,6745 = Φ⁻¹(3/4), facteur de cohérence gaussienne)
```

La MAD est insensible aux quelques coefficients qui portent de vrais contours : elle ne mesure que le fond aléatoire. C'est exactement la robustesse du §16.3 appliquée à la mesure du bruit lui-même — le voile statistique qu'on traque depuis le chapitre 2 se chiffre ici avec l'outil du chapitre 16.

### Piège d'implémentation

- **Travailler en espace linéaire.** La loi de variance affine n'est vraie que sur le signal **linéaire** (proportionnel aux photons). Sur une image encodée en gamma (sRGB, `γ ≈ 1/2,2`, ch. 7), la non-linéarité tord la relation variance/moyenne : le bruit des zones sombres est amplifié, celui des claires écrasé. Estimer `σ` ou tracer la photon transfer curve sur une image gamma donne des paramètres faux. Linéariser d'abord.
- **Saturation et clipping.** Le modèle Poisson casse aux deux bords : à 0 (les valeurs négatives sont coupées, ce qui biaise la moyenne des zones sombres) et à la saturation du puits (la variance s'effondre, le pixel n'est plus aléatoire). Exclure ces pixels de toute estimation.
- **Le bruit n'est pas blanc après dématriçage.** Le dématriçage (demosaicing) d'un capteur Bayer **corréle** spatialement le bruit : la MAD sur ondelettes le sous-estime alors, car une partie du bruit a migré vers les basses fréquences. Estimer sur le RAW quand on le peut.
- **`skimage` et l'échelle.** `random_noise` et les utilitaires supposent une image en `float ∈ [0,1]` ; un `σ` pensé en ADU n'a aucun sens après `img_as_float`. Fixer l'échelle avant de poser un `σ`.

### Schéma de nœuds

```
[Signal linéaire λ] ──> [Poisson (grenaille) + Gauss (lecture)] ──> [Image bruitée]
        ──> [Anscombe : Var ≈ 1] ──> [Débruitage gaussien] ──> [Anscombe⁻¹ non biaisé]
[Image inconnue] ──> [MAD des détails fins (ondelette, ch.16)] ──> [σ̂]
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑14.1.*

---

## Ligne à ajouter au tableau récapitulatif du chapitre 14

| Notion | Ce qu'elle modélise | Angle mort | Loi | Usage |
|---|---|---|---|---|
| Bruit Poisson–Gauss | Grenaille (signal) + lecture (plancher) | Vrai seulement en espace linéaire ; casse à 0 et à saturation | `σ²(I) = a·I + b` | Choisir l'exposition, calibrer un capteur, paramétrer un débruiteur |

## Raccord à l'encadré final du chapitre

> « Le bruit amplifie le moment d'ordre élevé », « dériver amplifie le bruit » : ces phrases, posées aux chapitres 2 et 6, désignent toutes la même quantité — la variance `a·I + b` de cette section. Elle n'est ni constante ni séparée du signal : elle monte avec la lumière et plafonne dans l'ombre. Mesurer la qualité d'une image, c'est d'abord savoir contre quel hasard on la compare. Le PSNR et le SSIM qui suivent supposent ce modèle sans le dire ; le débruiteur qu'on leur oppose n'est qu'un pari sur sa forme.
