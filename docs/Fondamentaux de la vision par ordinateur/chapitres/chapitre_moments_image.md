# Chapitre — Moments d'image : dérivations et exemples

Au chapitre précédent, plusieurs descripteurs reposaient sur des notions laissées en suspens : l'excentricité utilisait les demi-axes d'une « ellipse équivalente », et l'on a promis des invariants capables de reconnaître une forme quelle que soit sa pose. Tout cela vient d'un même outil : les **moments d'image**. Les moments transforment une région de pixels en une poignée de nombres qui en résument la masse, la position, l'orientation et l'étalement — un peu comme une fiche d'identité chiffrée de la silhouette.

L'idée centrale est empruntée à la mécanique. Si l'on découpe le masque de l'objet dans une plaque de carton d'épaisseur uniforme, alors les moments décrivent exactement les propriétés physiques de cette plaque : sa masse, son point d'équilibre, l'axe autour duquel elle tourne le plus facilement. Cette analogie n'est pas une image vague — c'est une correspondance exacte, et tout le chapitre l'exploitera.

Le fil conducteur tient en une phrase : **plus l'ordre d'un moment est élevé, plus il regarde loin du centroïde, et plus il amplifie le bruit**. L'aire (ordre 0) est très robuste ; le centroïde (ordre 1) l'est presque autant ; l'orientation (ordre 2) devient fragile pour les formes rondes ; les invariants de Hu (ordre 3) peuvent varier de moitié pour deux pixels de bruit sur le contour. Chaque section illustrera un étage de cette échelle de fragilité.

Conventions pour tout le chapitre : I(x, y) vaut 1 pour les pixels du masque et 0 ailleurs (moments **binaires**). Les mêmes formules s'appliquent telles quelles à une image en niveaux de gris : on parle alors de moments **pondérés**, et la section 2.8 montrera ce que ce changement apporte.

---

## 2.1 Moments bruts

### Définition
```
M_pq = Σ_x Σ_y x^p · y^q · I(x,y)
```
Le couple (p, q) indique à quelle puissance on élève les coordonnées. La somme p + q s'appelle l'**ordre** du moment.

### L'idée

Un moment est une somme sur tous les pixels de l'objet, mais une somme où chaque pixel ne compte pas pareil : il est pesé par ses coordonnées élevées à une certaine puissance. En faisant varier les puissances p et q, on pose à la forme des questions de plus en plus précises.

L'ordre 0 ne pèse rien du tout (x⁰·y⁰ = 1) : il compte simplement les pixels. L'ordre 1 pèse chaque pixel par sa position : il dit où se trouve la masse. L'ordre 2 pèse par la position au carré : il dit comment la masse est étalée. C'est exactement la hiérarchie des grandeurs de la mécanique du solide, et la correspondance est terme à terme :

```
M₀₀ = masse totale          (= aire A pour un masque binaire)
M₁₀ = moment statique en x  (la masse, pondérée par où elle est)
M₀₁ = moment statique en y
M₂₀, M₀₂ = moments d'inertie par rapport aux axes
M₁₁ = produit d'inertie     (la masse penche-t-elle en diagonale ?)
```

Cette correspondance fait des moments un cas rare en vision : toutes les propriétés des sections suivantes (centre de gravité, axes principaux d'inertie) sont des résultats de mécanique transposés tels quels, démonstrations comprises.

### Exemple numérique — le masque jouet du chapitre

Tout le chapitre s'appuiera sur un même masque 3 × 3, assez petit pour que chaque calcul tienne sur un coin de feuille :

```
y\x   0  1  2
0     0  1  1
1     1  1  1
2     1  1  0
```

Sept pixels, avec deux coins manquants en haut à gauche et en bas à droite : la forme penche le long de la diagonale qui va du coin haut-droit au coin bas-gauche. Calculons ses moments d'ordre 0, 1 et 2.

Pour M₀₀, on compte : **M₀₀ = 7**.

Pour M₁₀ = Σ x·I, le plus simple est de compter combien de pixels se trouvent dans chaque colonne : la colonne x = 0 en contient 2, la colonne x = 1 en contient 3, la colonne x = 2 en contient 2.

```
M₁₀ = 0·(2) + 1·(3) + 2·(2) = 7
M₀₁ = 0·(2) + 1·(3) + 2·(2) = 7      (mêmes comptes par ligne, par symétrie)
```

Pour les moments d'ordre 2, on procède de la même façon avec x² et y², et pour M₁₁ on somme le produit x·y pixel par pixel :

```
M₂₀ = Σ x² = 0·(2) + 1·(3) + 4·(2) = 11
M₀₂ = Σ y² = 11                       (par symétrie)
M₁₁ = Σ x·y = (1·0)+(2·0)+(0·1)+(1·1)+(2·1)+(0·2)+(1·2) = 5
```

Ces six nombres — 7, 7, 7, 11, 11, 5 — suffiront pour tout le reste du chapitre.

### Piège : en image, y descend

En traitement d'image, l'axe y croît **vers le bas** : la ligne 0 est en haut. Toutes les formules de ce chapitre restent vraies, mais les angles d'orientation se retrouvent mesurés dans le sens horaire dans le repère image, à l'inverse du repère mathématique habituel. `cv2.moments` comme `regionprops` suivent cette convention. C'est la cause classique des orientations « à l'envers » : le calcul est juste, c'est le repère qui n'est pas celui auquel on pense.

### Code
```python
import cv2
import numpy as np

# cv2.moments calcule d'un coup tous les moments jusqu'à l'ordre 3.
# binaryImage=True : tout pixel non nul compte pour 1 (masque binaire).
m = cv2.moments(mask.astype(np.uint8), binaryImage=True)

# m est un dictionnaire. Trois familles de clés :
#   m['m00'], m['m10'], ...   : moments bruts M_pq
#   m['mu20'], m['mu11'], ... : moments centraux μ_pq (section 2.3)
#   m['nu20'], m['nu11'], ... : moments normalisés η_pq (section 2.4)
print(m['m00'], m['m10'], m['m01'])
```

---

## 2.2 Centroïde

### Définition
```
x̄ = M₁₀ / M₀₀ ,   ȳ = M₀₁ / M₀₀
```

### L'idée

Le centroïde est le point d'équilibre de la forme : l'endroit où la plaque de carton tiendrait en équilibre sur une pointe de crayon. La formule dit exactement cela : la position moyenne des pixels, c'est-à-dire la somme des positions (M₁₀) divisée par le nombre de pixels (M₀₀).

### Dérivation

Le centre de gravité se définit comme le point qui annule les moments statiques : vue depuis lui, la masse ne penche d'aucun côté. Vérifions que x̄ = M₁₀/M₀₀ a bien cette propriété. En posant x' = x − x̄ :

```
Σ x'·I = Σ (x − x̄)·I = M₁₀ − x̄·M₀₀ = M₁₀ − (M₁₀/M₀₀)·M₀₀ = 0  ∎
```

### Exemple numérique

Sur le masque jouet : x̄ = 7/7 = 1 et ȳ = 7/7 = 1. Le centroïde tombe sur le pixel central — cohérent avec la symétrie de la forme, dont les deux coins manquants se compensent.

### Applications

Le centroïde est l'ancrage de presque toute analyse spatiale. En vidéo, suivre un objet revient souvent à suivre la suite de ses centroïdes d'une image à l'autre. En astronomie, le centroïde d'une étoile sur le capteur localise la source avec une précision **inférieure au pixel** (la section 2.8 expliquera pourquoi). En recalage d'images, aligner deux acquisitions commence souvent par superposer leurs barycentres.

### Subtilité importante : le centroïde peut tomber hors de l'objet

Le point d'équilibre d'une forme n'est pas forcément dans la forme. Pour un masque en U, en croissant, ou pour deux objets reliés par un isthme fin, le centroïde tombe dans le creux — comme le centre de gravité d'un anneau, qui est au milieu du trou. Tout algorithme qui « plante un marqueur au centroïde » (marqueur de watershed, placement d'étiquette, point d'amorçage pour un modèle de segmentation) doit le vérifier :

```python
# Si le pixel au centroïde n'appartient pas au masque...
if not mask[int(round(cy)), int(round(cx))]:
    # ...on récupère les coordonnées de tous les pixels du masque
    # (np.nonzero renvoie d'abord les lignes ys, puis les colonnes xs)
    ys, xs = np.nonzero(mask)
    # ...et on remplace le centroïde par le pixel du masque le plus proche.
    i = np.argmin((xs - cx)**2 + (ys - cy)**2)
    cx, cy = xs[i], ys[i]
```

C'est pour cette raison que la transformée de distance — qui trouve le point le plus *intérieur* de la forme — est souvent préférée au centroïde pour placer une étiquette de pays sur une carte ou générer un point d'amorçage fiable.

### Piège : (x, y) ou (row, col) ?

Les bibliothèques ne rangent pas les coordonnées dans le même ordre. `cv2.moments` raisonne en (x, y) ; `regionprops.centroid` renvoie (ligne, colonne), c'est-à-dire **(ȳ, x̄)**. Mélanger les deux conventions transpose silencieusement tous les résultats — l'erreur ne se voit que sur une forme non symétrique, donc rarement sur le cas de test.

---

## 2.3 Moments centraux

### Définition
```
μ_pq = Σ_x Σ_y (x − x̄)^p · (y − ȳ)^q · I(x,y)
```

### L'idée

Les moments bruts mélangent deux informations : la forme de l'objet et l'endroit où il se trouve dans l'image. Les moments centraux séparent les deux, en mesurant les coordonnées **depuis le centroïde** plutôt que depuis le coin de l'image. La forme est décrite dans son propre repère ; sa position dans l'image ne compte plus.

La conséquence immédiate est l'**invariance par translation** — la première des trois invariances que le chapitre va construire pas à pas (translation ici, échelle en 2.4, rotation en 2.7). La preuve tient en une ligne : translater la forme de (a, b) translate son centroïde d'autant, donc les écarts (x − x̄) ne bougent pas, et μ_pq non plus. ∎

### Formules de passage

En pratique, on ne recalcule pas les μ_pq en reparcourant l'image : ils se déduisent algébriquement des moments bruts, en développant les puissances de (x − x̄). À l'ordre 2 :

```
μ₀₀ = M₀₀
μ₁₀ = μ₀₁ = 0          (par construction : c'est la définition du centroïde)
μ₂₀ = M₂₀ − x̄·M₁₀
μ₀₂ = M₀₂ − ȳ·M₀₁
μ₁₁ = M₁₁ − x̄·M₀₁
```

et à l'ordre 3, pour référence :

```
μ₃₀ = M₃₀ − 3x̄·M₂₀ + 2x̄²·M₁₀
μ₀₃ = M₀₃ − 3ȳ·M₀₂ + 2ȳ²·M₀₁
μ₂₁ = M₂₁ − 2x̄·M₁₁ − ȳ·M₂₀ + 2x̄²·M₀₁
μ₁₂ = M₁₂ − 2ȳ·M₁₁ − x̄·M₀₂ + 2ȳ²·M₁₀
```

Il n'est pas utile de mémoriser ces formules — les bibliothèques les appliquent pour vous — mais il faut savoir qu'elles existent : c'est ce qui permet de calculer tous les moments en un seul passage sur l'image.

### Exemple numérique (suite du masque jouet)
```
μ₂₀ = M₂₀ − x̄·M₁₀ = 11 − 1×7 = 4
μ₀₂ = 11 − 1×7 = 4
μ₁₁ = M₁₁ − x̄·M₀₁ = 5 − 1×7 = −2
```

Le signe de μ₁₁ se lit comme une corrélation entre x et y. Ici il est négatif : quand y augmente (on descend dans l'image), x tend à diminuer. La masse s'étire donc le long de la diagonale descendante vers la gauche — exactement ce que montre le dessin du masque, avec ses coins manquants en haut-gauche et bas-droite.

### Les moments d'ordre 3 mesurent l'asymétrie

À l'ordre 2, les écarts au centroïde sont élevés au carré : un pixel à gauche et un pixel à droite contribuent pareil. À l'ordre 3, le cube **conserve le signe** : les deux côtés ne se compensent plus, et le moment mesure de quel côté la masse penche.

```
μ₃₀ : asymétrie gauche/droite de la masse
μ₀₃ : asymétrie haut/bas
```

Un caractère manuscrit comme « e » ou « a » a une asymétrie marquée que μ₃₀ capture ; un « o » symétrique a μ₃₀ ≈ μ₀₃ ≈ 0. Ces moments d'ordre 3 sont la matière première des invariants de Hu φ₃ à φ₇ (section 2.7). Notez déjà, pour le fil conducteur, que le cube amplifie les pixels lointains bien plus que le carré : l'ordre 3 est plus expressif, mais aussi plus fragile.

---

## 2.4 Moments centraux normalisés

### Définition
```
η_pq = μ_pq / μ₀₀^γ ,   γ = (p + q)/2 + 1
```

### L'idée

Après la position (2.3), on veut maintenant oublier la **taille** : un même logo, imprimé en petit sur une étiquette ou en grand sur une façade, devrait donner les mêmes nombres. L'idée naturelle est de diviser chaque moment par une puissance de l'aire, pour que l'agrandissement se simplifie au numérateur et au dénominateur. Toute la question est : quelle puissance ? La réponse est l'exposant γ, et il vaut la peine de voir d'où il sort.

### D'où vient l'exposant γ ?

Agrandissons la forme d'un facteur s : chaque coordonnée est multipliée par s, et chaque pixel devient une zone de s² pixels (la surface croît comme le carré du facteur). Le moment μ_pq contient p + q coordonnées multipliées chacune par s, plus ce facteur de surface s² :

```
μ'_pq = s^(p+q) · s² · μ_pq = s^(p+q+2) · μ_pq
μ'₀₀ = s² · μ₀₀
```

Pour que le rapport η ne dépende plus de s, il faut que le dénominateur grossisse exactement autant que le numérateur :

```
s^(p+q+2) = (s²)^γ   ⟹   γ = (p + q + 2)/2 = (p + q)/2 + 1   ∎
```

L'exposant n'a donc rien d'arbitraire : c'est de l'analyse dimensionnelle. On exige que η soit « sans dimension », et γ tombe tout seul — un bon exercice à refaire de tête pour vérifier qu'on a compris.

### Exemple numérique

Sur le masque jouet : η₂₀ = μ₂₀/μ₀₀² = 4/49 ≈ 0,0816 (pour l'ordre 2, γ = 2). Agrandissons mentalement la forme d'un facteur 10 : elle compte désormais 700 pixels, μ₂₀ devient environ 4 × 10⁴ et μ₀₀² environ 49 × 10⁴. Le rapport reste ≈ 0,0816. C'est exactement cette stabilité qui permet de reconnaître la même forme à toutes les tailles.

### Piège : l'invariance d'échelle est exacte en continu, approchée en discret

La dérivation ci-dessus suppose qu'agrandir une forme multiplie proprement ses pixels. En réalité, une forme de 30 pixels agrandie ou réduite est re-échantillonnée sur la grille : les marches d'escalier du contour ne se transforment pas exactement, et η fluctue de quelques pourcents. L'invariance d'échelle est excellente entre une forme de 1 000 pixels et une de 100 000 ; elle se dégrade nettement sous quelques dizaines de pixels, où chaque pixel de contour pèse trop lourd.

---

## 2.5 Orientation principale

### Définition
```
θ = ½ · arctan2(2μ₁₁, μ₂₀ − μ₀₂)
```

### L'idée

L'orientation principale est l'axe le long duquel la forme s'allonge. En termes mécaniques : l'axe autour duquel la plaque de carton tourne le plus facilement, celui qui minimise le moment d'inertie. Une règle plate tourne sans effort autour de son grand axe (la masse est collée à l'axe), et difficilement autour de son petit axe (la masse en est loin) : le grand axe est l'orientation principale.

### Dérivation

On cherche l'axe passant par le centroïde qui minimise l'inertie. Pour un axe incliné d'un angle θ, l'inertie vaut :

```
J(θ) = μ₂₀·sin²θ − 2μ₁₁·sinθ·cosθ + μ₀₂·cos²θ
```

(chaque terme est la distance à l'axe, au carré, pondérée par la masse). Les identités sin²θ = (1−cos 2θ)/2 et 2 sinθ cosθ = sin 2θ permettent de tout réécrire en fonction de l'angle double :

```
J(θ) = (μ₂₀+μ₀₂)/2 − (μ₂₀−μ₀₂)/2·cos2θ − μ₁₁·sin2θ
```

On annule la dérivée dJ/dθ pour trouver le minimum :

```
(μ₂₀ − μ₀₂)·sin2θ = 2μ₁₁·cos2θ   ⟹   tan2θ = 2μ₁₁/(μ₂₀ − μ₀₂)   ∎
```

Le détail à comprendre est la présence de l'angle **double** 2θ. Un axe n'a pas de sens de parcours : θ et θ + 180° décrivent la même droite. La formule en 2θ encode naturellement cette ambiguïté, et le facteur ½ final ramène le résultat dans l'intervalle utile.

### Piège : arctan2, pas arctan

La formule s'implémente avec `arctan2(2μ₁₁, μ₂₀ − μ₀₂)` et surtout pas avec `arctan` du quotient. La fonction arctan perd le signe du dénominateur, donc le quadrant : dès que μ₂₀ < μ₀₂ (forme plus haute que large), l'orientation sort fausse de 90°. C'est une erreur silencieuse — le code tourne, les angles sont plausibles, et tout est faux pour la moitié des objets.

### Exemple numérique

Masque jouet : 2μ₁₁ = −4 et μ₂₀ − μ₀₂ = 0. Donc arctan2(−4, 0) = −90°, et **θ = −45°**. La forme est orientée le long de la diagonale descendante — ce que le signe de μ₁₁ annonçait déjà en 2.3, et qu'on vérifie d'un coup d'œil sur le dessin. (Rappel du piège 2.1 : l'angle se lit dans le repère image, y vers le bas.)

### Applications

L'orientation principale sert d'abord à **redresser** un objet avant de le reconnaître : remettre un caractère ou un code-barres à l'horizontale, aligner une empreinte digitale sur son axe, normaliser la pose d'une cellule avant classification. Elle sert aussi en tant que mesure : en microscopie, l'histogramme des orientations des fibres de collagène quantifie l'anisotropie d'un tissu ; en télédétection, celui des orientations de bâtiments révèle la trame d'une ville.

### Piège : l'orientation d'un objet rond n'existe pas

Quand μ₂₀ ≈ μ₀₂ et μ₁₁ ≈ 0 — objet rond, ou carré vu de face — la formule devient un arctan2 de (0, 0) : numériquement indéterminé. Un seul pixel de bruit fait alors basculer θ de 90°. Il faut donc toujours accompagner θ d'une mesure de fiabilité, l'**anisotropie** :

```
aniso = √((μ₂₀−μ₀₂)² + 4μ₁₁²) / (μ₂₀+μ₀₂)
```

Elle vaut 0 pour un disque et tend vers 1 pour un segment. Règle pratique : ne pas utiliser θ quand aniso < 0,2. Demander l'orientation d'un disque, c'est demander la direction d'une boule de pétanque — la question n'a pas de réponse, et l'algorithme en donnera pourtant une.

C'est la première manifestation chiffrée du fil conducteur : l'ordre 2 fonctionne très bien… sauf dans son cas dégénéré, où il devient brutalement instable.

---

## 2.6 Ellipse équivalente

### Définition

L'ellipse équivalente est l'ellipse qui a les **mêmes moments d'ordre ≤ 2** que la région : même masse, même centre, même inertie dans toutes les directions. Ses paramètres se lisent dans la matrice de covariance de la forme :

```
cov = (1/μ₀₀) · [μ₂₀  μ₁₁]
                 [μ₁₁  μ₀₂]

λ₁,₂ = (μ₂₀+μ₀₂)/(2μ₀₀) ± √( ((μ₂₀−μ₀₂)/(2μ₀₀))² + (μ₁₁/μ₀₀)² )

demi-grand axe : a = 2√λ₁
demi-petit axe : b = 2√λ₂
```

### L'idée

L'ellipse équivalente est le « résumé d'ordre 2 » de la forme : la silhouette la plus simple qui distribue sa masse de la même façon. Les valeurs propres λ₁ et λ₂ de la matrice de covariance mesurent l'étalement de la masse le long du grand axe et du petit axe ; les directions propres donnent l'orientation — on retrouve le θ de la section 2.5, calculé autrement. C'est de cette ellipse que vient l'excentricité e = √(1 − b²/a²) utilisée au chapitre 1 : la promesse est tenue.

D'où vient le facteur 2 dans a = 2√λ₁ ? Pour une ellipse pleine de demi-axes a et b, le calcul intégral du moment d'inertie donne μ₂₀/μ₀₀ = a²/4. Inverser cette relation donne a = 2√(μ₂₀/μ₀₀) dans le repère propre, donc a = 2√λ₁ en général. ∎ Le facteur 2 est propre à l'ellipse *pleine* — et c'est précisément ce qui rend le piège suivant si important.

### Exemple numérique (suite et fin du masque jouet)

```
(μ₂₀+μ₀₂)/(2μ₀₀) = 8/14 = 4/7
√(0² + (−2/7)²)  = 2/7

λ₁ = 4/7 + 2/7 = 6/7 ≈ 0,857   →  a = 2√λ₁ ≈ 1,85
λ₂ = 4/7 − 2/7 = 2/7 ≈ 0,286   →  b = 2√λ₂ ≈ 1,07
```

L'excentricité vaut e = √(1 − λ₂/λ₁) = √(1 − 1/3) ≈ 0,82 : une forme nettement allongée, le long de la diagonale θ = −45° trouvée en 2.5. Sept pixels ont suffi pour dérouler toute la chaîne : moments bruts → centroïde → moments centraux → orientation → ellipse.

### Le piège central : l'ellipse ne mesure pas la taille de l'objet

C'est probablement l'erreur la plus répandue de tout le chapitre. L'ellipse équivalente égalise les **moments**, pas les **dimensions**. Prenons un rectangle de longueur L : son moment donne μ₂₀/μ₀₀ = L²/12 (l'étalement d'une répartition uniforme), donc :

```
a = 2√(L²/12) = L/√3 ≈ 0,577·L
grand axe : 2a = 2L/√3 ≈ 1,155·L
```

Le grand axe de l'ellipse équivalente d'un rectangle **dépasse de 15 %** la longueur réelle. La raison est géométrique : pour qu'une ellipse, effilée à ses extrémités, loge autant de masse loin du centre qu'un rectangle aux bouts pleins, elle doit être plus longue que lui. D'où la règle à encadrer :

> `major_axis_length` de regionprops n'est **pas** la longueur de l'objet.

Pour mesurer la dimension réelle d'une pièce sur une chaîne de contrôle, d'une bactérie ou d'un trait, il faut le **rectangle orienté minimal** (`cv2.minAreaRect`) ou le **diamètre de Feret**. L'ellipse équivalente décrit la *répartition de masse* (orientation, excentricité) ; elle ne mesure pas. Confondre les deux usages introduit une erreur systématique de l'ordre de 15 % — du genre qui passe inaperçu pendant toute une campagne de mesures.

### Code
```python
from skimage.measure import regionprops, label

# label numérote les composantes connexes ; regionprops calcule
# leurs propriétés. [0] : on prend le premier (et ici seul) objet.
p = regionprops(label(mask))[0]

p.centroid             # ATTENTION : renvoie (ligne, colonne) = (ȳ, x̄),
                       # l'inverse de la convention (x, y) d'OpenCV.
p.orientation          # angle en radians (voir le piège ci-dessous)
p.major_axis_length    # 2a — rappel : ce N'EST PAS la longueur de l'objet
p.minor_axis_length    # 2b
p.eccentricity         # le e du chapitre 1, enfin dérivé
```

### Piège de bibliothèque : une convention d'angle qui a changé

La définition de l'angle renvoyé par `regionprops.orientation` (origine, sens de rotation) a **changé entre versions** de scikit-image. Avant toute campagne de mesures, valider la chaîne sur une forme test connue — un rectangle synthétique tracé à 30°, par exemple — et vérifier que l'angle ressorti est bien 30°. Cette vérification de trente secondes vaut une page de documentation, et elle attrape aussi les confusions d'axes de la section 2.1.

---

## 2.7 Les sept invariants de Hu

### Construction

Il reste une invariance à conquérir : la **rotation**. Les η_pq sont insensibles à la position et à la taille, mais tourner la forme les mélange entre eux. Hu (1962) a trouvé sept combinaisons des η d'ordre 2 et 3 que la rotation laisse intactes :

```
φ₁ = η₂₀ + η₀₂
φ₂ = (η₂₀ − η₀₂)² + 4η₁₁²
φ₃ = (η₃₀ − 3η₁₂)² + (3η₂₁ − η₀₃)²
φ₄ = (η₃₀ + η₁₂)² + (η₂₁ + η₀₃)²
φ₅ = (η₃₀ − 3η₁₂)(η₃₀ + η₁₂)[(η₃₀+η₁₂)² − 3(η₂₁+η₀₃)²]
   + (3η₂₁ − η₀₃)(η₂₁ + η₀₃)[3(η₃₀+η₁₂)² − (η₂₁+η₀₃)²]
φ₆ = (η₂₀ − η₀₂)[(η₃₀+η₁₂)² − (η₂₁+η₀₃)²] + 4η₁₁(η₃₀+η₁₂)(η₂₁+η₀₃)
φ₇ = (3η₂₁ − η₀₃)(η₃₀ + η₁₂)[(η₃₀+η₁₂)² − 3(η₂₁+η₀₃)²]
   − (η₃₀ − 3η₁₂)(η₂₁ + η₀₃)[3(η₃₀+η₁₂)² − (η₂₁+η₀₃)²]
```

Avec les trois invariances réunies — translation (μ), échelle (η), rotation (φ) — le vecteur (φ₁, …, φ₇) constitue une signature de la forme « pure », débarrassée de toute sa pose.

### Pourquoi ces combinaisons résistent-elles à la rotation ?

Les formules paraissent sorties d'un chapeau, mais elles cachent une idée simple, qu'on peut comprendre sans dérouler la preuve. En écrivant les coordonnées en nombres complexes (z = x + iy), une rotation de la forme ne fait que multiplier certains moments par un facteur de la forme e^{iα} — elle change leur **phase**, pas leur grandeur. Toute combinaison où les phases s'annulent entre elles est donc insensible à la rotation : c'est le cas d'un module au carré, ou d'un produit dont les phases se compensent. Les sept φ de Hu sont exactement de telles combinaisons, réécrites en moments réels — par exemple, φ₂ est le module au carré d'un moment complexe d'ordre 2.

Le détail technique importe moins que le principe : on n'a pas *cherché* sept formules au hasard, on a *construit* des quantités dont la rotation ne peut atteindre que la phase, puis éliminé la phase.

### Deux propriétés à connaître

**φ₇ change de signe en miroir.** C'est le seul des sept. Une forme et son image dans un miroir ont les mêmes φ₁ à φ₆, mais des φ₇ opposés. Précieux quand la chiralité compte — distinguer « b » de « d », « p » de « q » en reconnaissance de caractères — et à exclure du vecteur quand elle ne compte pas, sous peine de séparer artificiellement des objets identiques vus de dos.

**La dynamique est énorme.** Les φ s'étagent typiquement de 10⁻¹ à 10⁻²⁰ : comparés directement, les petits sont écrasés par les grands. On les passe toujours en échelle logarithmique signée avant toute comparaison :

```python
# log10 de la valeur absolue : ramène tous les φ à des ordres comparables.
# np.sign préserve le signe (crucial pour φ₇).
# Le +1e-30 évite log(0) pour les moments quasi nuls des formes symétriques.
hu_log = -np.sign(hu) * np.log10(np.abs(hu) + 1e-30)
```

### Exemple : reconnaissance de caractères

C'est l'application historique. Un « A » conserve sa signature (φ₁, φ₂, …) qu'il soit petit, grand, tourné ou déplacé — exactement les insensibilités voulues pour une reconnaissance robuste à l'orientation. Un « O » très symétrique a ses moments d'ordre 3 quasi nuls, donc φ₃ à φ₇ ≈ 0 ; un « R » asymétrique les a nettement non nuls. La distance entre vecteurs de Hu en échelle log (distance euclidienne — voir chapitre 3) suffit à un classifieur des plus simples.

### Hu aujourd'hui : encore utile ?

Pour la reconnaissance générale, les descripteurs appris (réseaux de neurones) dominent largement. Les moments de Hu gardent trois créneaux bien réels : (1) quand on a peu ou pas de données d'entraînement, (2) quand il faut une invariance **prouvable** et non simplement constatée — métrologie, certification industrielle —, (3) quand le budget de calcul est minuscule (capteurs embarqués). Le bon réflexe n'est pas « Hu ou réseau de neurones ? » mais « mon problème exige-t-il une garantie mathématique, ou une performance statistique ? ».

### Code
```python
m = cv2.moments(mask.astype(np.uint8), binaryImage=True)

# HuMoments prend le dictionnaire de moments et renvoie les 7 invariants
# sous forme de tableau colonne 7x1 ; flatten() le met à plat.
hu = cv2.HuMoments(m).flatten()

# Toujours passer en log signé avant de comparer (voir ci-dessus).
hu_log = -np.sign(hu) * np.log10(np.abs(hu) + 1e-30)
```

---

## 2.8 Moments pondérés par l'intensité

Toutes les formules du chapitre s'appliquent sans changement à une image en niveaux de gris : il suffit de remplacer le masque binaire par les intensités, I(x, y) = niveau de gris. Seule l'interprétation change :

```
centroïde binaire  : centre géométrique du masque
centroïde pondéré  : barycentre lumineux (tiré vers les zones claires)
```

Cet écart est exploité directement. En astronomie, une étoile s'étale sur quelques pixels avec un profil lumineux en cloche ; le centroïde pondéré par l'intensité moyenne ce profil et localise la source au **sous-pixel** — bien plus finement que le pixel le plus brillant. C'est le principe des mesures astrométriques de précision. De même, en caractérisation de faisceau laser, les moments pondérés d'ordre 2 définissent la largeur du faisceau (méthode dite D4σ : quatre fois l'écart-type de la distribution d'intensité, normalisée ISO 11146) — la définition de référence de l'industrie.

```python
# Moments binaires : géométrie pure du masque.
m_bin = cv2.moments(mask.astype(np.uint8), binaryImage=True)

# Moments pondérés : on multiplie l'image par le masque pour ne garder
# que les intensités de l'objet, et binaryImage=False pour les utiliser.
m_int = cv2.moments((gray * mask).astype(np.float32), binaryImage=False)

# Distance entre les deux centroïdes : où la lumière tire-t-elle la forme ?
shift = np.hypot(m_int['m10']/m_int['m00'] - m_bin['m10']/m_bin['m00'],
                 m_int['m01']/m_int['m00'] - m_bin['m01']/m_bin['m00'])
```

Piège associé : les moments pondérés héritent de tout ce qui affecte l'intensité — vignettage, fond non uniforme, pixels saturés. Un fond résiduel non soustrait tire le centroïde pondéré vers le centre de la fenêtre de mesure ; en astrométrie, la soustraction de fond se fait *avant* tout calcul de moment.

---

## Tableau récapitulatif — quel moment pour quelle question ?

| Question | Outil | Ordre | Invariances | Fragilité |
|---|---|---|---|---|
| Quelle est la taille de l'objet ? | M₀₀ (aire) | 0 | — | très robuste |
| Où est-il ? | centroïde M₁₀/M₀₀, M₀₁/M₀₀ | 1 | — | très robuste |
| Dans quel sens est-il orienté ? | θ (μ₁₁, μ₂₀, μ₀₂) | 2 | translation | instable si forme ronde |
| Comment sa masse est-elle répartie ? | ellipse équivalente (λ₁, λ₂) | 2 | translation | ≠ dimensions réelles |
| Est-il allongé ? | excentricité e | 2 | translation, rotation | instable si forme ronde |
| Le reconnaître à toute pose ? | Hu φ₁–φ₆ | 2–3 | translation, rotation, échelle | sensible au bruit de bord |
| Le distinguer de son miroir ? | signe de φ₇ | 3 | translation, rotation, échelle | le plus fragile de tous |
| Position sous-pixel d'une source ? | centroïde pondéré | 1 | translation | sensible au fond résiduel |

---

## Encadré — la chaîne de fiabilité

Les moments héritent de toutes les erreurs de segmentation, mais pas tous au même degré. Chaque montée en ordre élève les écarts au centroïde à une puissance de plus : les pixels du bord — précisément ceux que la segmentation place mal — pèsent de plus en plus lourd. D'où l'échelle de fragilité du chapitre :

```
ordre 0 (aire)        : erreur ∝ bruit de bord       — robuste
ordre 1 (centroïde)   : erreur sub-pixel             — très robuste
ordre 2 (orientation) : instable si forme isotrope   — filtrer par anisotropie
ordre 3 (Hu φ₃–φ₇)    : ±50 % pour 2 px de bruit     — fragile
```

La règle à retenir : **plus l'ordre est élevé, plus le moment regarde loin du centroïde, plus il amplifie le bruit de contour.** Vous connaissez peut-être déjà cette hiérarchie sous une autre forme : en statistiques, la moyenne d'un échantillon est plus stable que sa variance, elle-même plus stable que son asymétrie (skewness) puis son aplatissement (kurtosis). Ce sont les mêmes moments, appliqués à une distribution au lieu d'une image — et le parallèle, une fois vu, ne s'oublie plus.

Ce compromis prolonge la leçon du chapitre 1 : un descripteur encode un point de vue, et les moments ajoutent que **chaque supplément de détail se paie en fragilité**. L'ordre 0 voit peu mais ne se trompe jamais ; l'ordre 3 voit l'asymétrie fine mais vacille au moindre pixel. Choisir l'ordre de ses moments, c'est choisir un point d'équilibre entre ce qu'on veut voir et ce qu'on peut mesurer de façon fiable — un arbitrage que l'on retrouvera au chapitre 6, où dériver une image (l'analogue continu de monter en ordre) amplifiera le bruit exactement de la même manière.
