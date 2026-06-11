# Chapitre — Moments d'image : dérivations et exemples

Au chapitre précédent, plusieurs descripteurs reposaient sur des notions laissées en suspens : l'excentricité utilisait les demi-axes d'une « ellipse équivalente », et l'on a promis des invariants capables de reconnaître une forme quelle que soit sa pose. Tout cela vient d'un même outil : les **moments d'image**. Les moments transforment une région de pixels en une poignée de nombres qui en résument la masse, la position, l'orientation et l'étalement — un peu comme une fiche d'identité chiffrée de la silhouette.

L'idée centrale est empruntée à la mécanique. Si l'on découpe le masque de l'objet dans une plaque de carton d'épaisseur uniforme, alors les moments décrivent exactement les propriétés physiques de cette plaque : sa masse, son point d'équilibre, l'axe autour duquel elle tourne le plus facilement. Cette analogie n'est pas une image vague — c'est une correspondance exacte, et tout le chapitre l'exploitera pour donner un sens concret à des formules qui, écrites brutes, paraissent abstraites.

Le fil conducteur tient en une phrase : **plus l'ordre d'un moment est élevé, plus il regarde loin du centroïde, et plus il amplifie le bruit**. L'aire (ordre 0) est très robuste ; le centroïde (ordre 1) l'est presque autant ; l'orientation (ordre 2) devient fragile pour les formes rondes ; les invariants de Hu (ordre 3) peuvent varier de moitié pour deux pixels de bruit sur le contour. Chaque section illustrera un étage de cette échelle de fragilité.

Conventions pour tout le chapitre : I(x, y) vaut 1 pour les pixels du masque et 0 ailleurs (moments **binaires**). Les mêmes formules s'appliquent telles quelles à une image en niveaux de gris : on parle alors de moments **pondérés**, et la section 2.8 montrera ce que ce changement apporte. Côté logiciel : chaque bloc de code se colle dans une node **« Python Script »**. Le masque arrive dans la variable `a`, le résultat est renvoyé dans `out_a` — un dictionnaire qu'une node **Inspecteur** affiche à l'écran. Les modules `np` (NumPy) et `cv2` (OpenCV) sont déjà disponibles, sans import.

---

## 2.1 Moments bruts

### Définition
```
M_pq = Σ_x Σ_y x^p · y^q · I(x,y)
```
Le couple (p, q) indique à quelle puissance on élève les coordonnées. La somme p + q s'appelle l'**ordre** du moment.

### L'idée

Un moment est une somme sur tous les pixels de l'objet, mais une somme où chaque pixel ne compte pas pareil : il est pesé par sa position élevée à une certaine puissance. En faisant varier les puissances p et q, on pose à la forme des questions de plus en plus précises.

L'ordre 0 ne pèse rien du tout (x⁰·y⁰ = 1) : il compte simplement les pixels. L'ordre 1 pèse chaque pixel par sa position : il dit où se trouve la masse. L'ordre 2 pèse par la position au carré : il dit comment la masse est étalée. C'est exactement la hiérarchie des grandeurs de la mécanique du solide, et la correspondance est terme à terme :

```
M₀₀ = masse totale          (= aire A pour un masque binaire)
M₁₀ = moment statique en x  (la masse, pondérée par où elle est)
M₀₁ = moment statique en y
M₂₀, M₀₂ = moments d'inertie par rapport aux axes
M₁₁ = produit d'inertie     (la masse penche-t-elle en diagonale ?)
```

Cette correspondance est précieuse : elle veut dire que toutes les propriétés des sections suivantes — centre de gravité, axes principaux — ne sont pas des recettes de vision inventées pour l'occasion, mais des résultats de mécanique que l'on connaît depuis longtemps, transposés tels quels à une image.

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

### Piège : un masque, pas une image

`cv2.moments` n'accepte qu'un tableau **2D à un seul canal**. Si l'on relie par mégarde une sortie *image* (3 canaux, BGR) à l'entrée du nœud, au lieu d'un *masque*, OpenCV s'interrompt brutalement :

```
cv2.moments … moments.cpp: error: (-5:Bad argument) Invalid image
```

La parade tient en une ligne, à placer en tête de chaque script : convertir en niveaux de gris si l'entrée a trois canaux, et garantir un `uint8` contigu. Tous les codes de ce chapitre commencent désormais par cette normalisation, sous le nom `msk`.

### Code
```python
# msk : masque nettoyé — 2D, uint8, contigu. Convertit une image BGR en gris
# si on a relié une image au lieu d'un masque (voir le piège ci-dessus).
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)

# cv2.moments calcule d'un coup tous les moments jusqu'à l'ordre 3.
# binaryImage=True : tout pixel non nul compte pour 1.
m = cv2.moments(msk, binaryImage=True)

# m est un dictionnaire à trois familles de clés :
#   'm00','m10',…    moments bruts M_pq
#   'mu20','mu11',…  moments centraux μ_pq (section 2.3)
#   'nu20','nu11',…  moments normalisés η_pq (section 2.4)
out_a = {"M00 (aire)": m["m00"], "M10": m["m10"], "M01": m["m01"],
         "M20": m["m20"], "M02": m["m02"], "M11": m["m11"]}
```

---

## 2.2 Centroïde

### Définition
```
x̄ = M₁₀ / M₀₀ ,   ȳ = M₀₁ / M₀₀
```

### L'idée

Le centroïde est le point d'équilibre de la forme : l'endroit où la plaque de carton tiendrait en équilibre sur une pointe de crayon. La formule dit exactement cela : la position moyenne des pixels, c'est-à-dire la somme des positions (M₁₀) divisée par le nombre de pixels (M₀₀). Diviser une somme par un effectif, c'est faire une moyenne — le centroïde n'est rien d'autre que la moyenne des coordonnées des pixels.

On peut vérifier que ce point a bien la propriété d'un point d'équilibre : vu depuis lui, la masse ne penche d'aucun côté, les contributions de gauche annulant exactement celles de droite. C'est précisément ce qui définit un centre de gravité.

### Exemple numérique

Sur le masque jouet : x̄ = 7/7 = 1 et ȳ = 7/7 = 1. Le centroïde tombe sur le pixel central — cohérent avec la symétrie de la forme, dont les deux coins manquants se compensent.

### Applications

Le centroïde est l'ancrage de presque toute analyse spatiale. En vidéo, suivre un objet revient souvent à suivre la suite de ses centroïdes d'une image à l'autre. En astronomie, le centroïde d'une étoile sur le capteur localise la source avec une précision **inférieure au pixel** (la section 2.8 expliquera pourquoi). En recalage d'images, aligner deux acquisitions commence souvent par superposer leurs barycentres.

### Subtilité importante : le centroïde peut tomber hors de l'objet

Le point d'équilibre d'une forme n'est pas forcément dans la forme. Pour un masque en U, en croissant, ou pour deux objets reliés par un isthme fin, le centroïde tombe dans le creux — exactement comme le centre de gravité d'un anneau, qui se situe au milieu du trou, là où il n'y a pas de matière. Tout algorithme qui « plante un marqueur au centroïde » (marqueur de watershed, placement d'étiquette, point d'amorçage pour un modèle de segmentation) doit donc le vérifier.

### Code
```python
# Calcule le centroïde et, s'il tombe hors de l'objet,
# le ramène sur le pixel du masque le plus proche.
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
m = cv2.moments(msk, binaryImage=True)
if m["m00"] > 0:
    cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    # msk[ligne, colonne] : 0 (hors objet) ou 255 (dans l'objet)
    if not msk[int(round(cy)), int(round(cx))]:
        ys, xs = np.nonzero(msk)                      # ys = lignes, xs = colonnes
        i = np.argmin((xs - cx) ** 2 + (ys - cy) ** 2)
        cx, cy = float(xs[i]), float(ys[i])
    out_a = {"cx": float(cx), "cy": float(cy)}
else:
    out_a = {"Erreur": "masque vide"}
```

C'est aussi pour cette raison que la transformée de distance — qui trouve le point le plus *intérieur* de la forme — est souvent préférée au centroïde pour placer une étiquette de pays sur une carte ou générer un point d'amorçage fiable.

### Piège : (x, y) ou (row, col) ?

Les bibliothèques ne rangent pas les coordonnées dans le même ordre. `cv2.moments` raisonne en (x, y) ; `regionprops.centroid` renvoie (ligne, colonne), c'est-à-dire **(ȳ, x̄)**. Mélanger les deux conventions transpose silencieusement tous les résultats — l'erreur ne se voit que sur une forme non symétrique, donc rarement sur le cas de test.

---

## 2.3 Moments centraux

### Définition
```
μ_pq = Σ_x Σ_y (x − x̄)^p · (y − ȳ)^q · I(x,y)
```

### L'idée

Les moments bruts mélangent deux informations : la forme de l'objet et l'endroit où il se trouve dans l'image. Les moments centraux séparent les deux, en mesurant les coordonnées **depuis le centroïde** plutôt que depuis le coin de l'image. C'est comme décrire un objet « par rapport à son propre centre » au lieu de « par rapport au coin de la pièce » : la description ne dépend plus de l'endroit où l'objet est posé.

La conséquence immédiate est l'**invariance par translation** — la première des trois invariances que le chapitre va construire pas à pas (translation ici, échelle en 2.4, rotation en 2.7). L'intuition suffit : déplacer la forme déplace son centroïde d'autant, si bien que l'écart entre chaque pixel et le centroïde, lui, ne change pas. Les μ_pq sont donc aveugles à la position.

En pratique, on ne recalcule pas les μ_pq en reparcourant l'image : la bibliothèque les déduit des moments bruts par quelques soustractions. À l'ordre 2, par exemple :

```
μ₂₀ = M₂₀ − x̄·M₁₀
μ₀₂ = M₀₂ − ȳ·M₀₁
μ₁₁ = M₁₁ − x̄·M₀₁
```

(et des formules analogues, plus longues, existent à l'ordre 3 — inutile de les retenir). Il faut surtout savoir qu'elles existent : c'est ce qui permet de tout calculer en un seul passage sur l'image.

### Exemple numérique (suite du masque jouet)
```
μ₂₀ = 11 − 1×7 = 4
μ₀₂ = 11 − 1×7 = 4
μ₁₁ = 5 − 1×7 = −2
```

Le signe de μ₁₁ se lit comme une tendance : il est négatif, ce qui signifie que lorsque y augmente (on descend dans l'image), x tend à diminuer. La masse s'étire donc le long de la diagonale descendante vers la gauche — exactement ce que montre le dessin du masque, avec ses coins manquants en haut-gauche et bas-droite.

### Les moments d'ordre 3 mesurent l'asymétrie

À l'ordre 2, les écarts au centroïde sont élevés au carré : un pixel à gauche et un pixel à droite contribuent pareil, le carré effaçant le signe. À l'ordre 3, le cube **conserve le signe** : les deux côtés ne se compensent plus, et le moment mesure de quel côté la masse penche.

```
μ₃₀ : asymétrie gauche/droite de la masse
μ₀₃ : asymétrie haut/bas
```

Un caractère manuscrit comme « e » ou « a » a une asymétrie marquée que μ₃₀ capture ; un « o » symétrique a μ₃₀ ≈ μ₀₃ ≈ 0. Ces moments d'ordre 3 sont la matière première des invariants de Hu (section 2.7). Notez déjà, pour le fil conducteur, que le cube amplifie les pixels lointains bien plus que le carré : l'ordre 3 est plus expressif, mais aussi plus fragile.

### Code
```python
# Les moments centraux sont déjà dans le dictionnaire renvoyé par cv2.moments.
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
m = cv2.moments(msk, binaryImage=True)
out_a = {"mu20": m["mu20"], "mu02": m["mu02"], "mu11": m["mu11"],
         "mu30": m["mu30"], "mu03": m["mu03"]}
```

---

## 2.4 Moments centraux normalisés

### Définition
```
η_pq = μ_pq / μ₀₀^γ ,   γ = (p + q)/2 + 1
```

### L'idée

Après la position (2.3), on veut maintenant oublier la **taille** : un même logo, imprimé en petit sur une étiquette ou en grand sur une façade, devrait donner les mêmes nombres. L'image juste est celle de deux photos d'un même objet, l'une de près, l'autre de loin : on aimerait une mesure qui les déclare identiques.

L'astuce est de diviser chaque moment par une puissance de l'aire. Pourquoi ça marche ? Quand on agrandit une forme, son moment grossit, mais son aire grossit aussi. Si on choisit la bonne puissance de l'aire au dénominateur, les deux grossissements se compensent exactement et le rapport ne bouge plus. Tout l'enjeu est donc de trouver cette « bonne puissance » : c'est le rôle de l'exposant γ.

On peut le sentir sans calcul : agrandir une forme d'un facteur 2 multiplie son aire par 4 (la surface croît comme le carré), et gonfle un moment d'autant plus que son ordre est élevé. L'exposant γ = (p + q)/2 + 1 est précisément réglé pour que numérateur et dénominateur enflent à la même vitesse. Ce n'est pas un nombre choisi au hasard : c'est la seule valeur qui rende η insensible au zoom.

### Exemple numérique

Sur le masque jouet : η₂₀ = μ₂₀/μ₀₀² = 4/49 ≈ 0,0816 (pour l'ordre 2, γ = 2). Agrandissons mentalement la forme d'un facteur 10 : elle compte désormais 700 pixels, μ₂₀ devient environ 4 × 10⁴ et μ₀₀² environ 49 × 10⁴. Le rapport reste ≈ 0,0816. C'est exactement cette stabilité qui permet de reconnaître la même forme à toutes les tailles.

### Piège : l'invariance d'échelle est exacte en théorie, approchée en pratique

Le raisonnement ci-dessus suppose qu'agrandir une forme multiplie proprement ses pixels. En réalité, une petite forme agrandie est re-dessinée sur la grille : les marches d'escalier du contour ne se transforment pas exactement, et η fluctue de quelques pourcents. L'invariance d'échelle est excellente entre une forme de 1 000 pixels et une de 100 000 ; elle se dégrade nettement sous quelques dizaines de pixels, où chaque pixel de contour pèse trop lourd.

### Code
```python
# Les moments normalisés sont déjà dans le dictionnaire renvoyé par cv2.moments.
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
m = cv2.moments(msk, binaryImage=True)
out_a = {"nu20": m["nu20"], "nu02": m["nu02"], "nu11": m["nu11"]}
```

---

## 2.5 Orientation principale

### Définition
```
θ = ½ · arctan2(2μ₁₁, μ₂₀ − μ₀₂)
```

### L'idée

L'orientation principale est l'axe le long duquel la forme s'allonge. L'analogie mécanique est parlante : c'est l'axe autour duquel la plaque de carton tourne le plus facilement. Pensez à une règle plate. Elle pivote sans effort autour de son grand axe — la matière est collée contre l'axe — et difficilement autour de son petit axe, où la matière en est éloignée. Le grand axe, celui de la rotation facile, est l'orientation de la forme.

On obtient θ en cherchant cet axe « de moindre effort » qui passe par le centroïde. Le calcul, qu'on ne déroule pas ici, combine les trois moments d'ordre 2 (μ₂₀, μ₀₂ et μ₁₁) pour aboutir à la formule ci-dessus. Un point mérite cependant d'être compris, car il explique la forme de la formule : on y trouve l'angle **double** 2θ, et non θ. La raison est qu'un axe n'a pas de sens de parcours — une règle orientée à 30° ou à 30° + 180° pointe dans la même direction. Travailler avec 2θ encode naturellement cette ambiguïté, et le facteur ½ final ramène le résultat dans l'intervalle utile.

### Piège : arctan2, pas arctan

La formule s'implémente avec `arctan2(2μ₁₁, μ₂₀ − μ₀₂)` et surtout pas avec `arctan` du quotient. La fonction `arctan` perd le signe du dénominateur, donc le quadrant : dès que μ₂₀ < μ₀₂ (forme plus haute que large), l'orientation sort fausse de 90°. C'est une erreur silencieuse — le code tourne, les angles sont plausibles, et tout est faux pour la moitié des objets.

### Exemple numérique

Masque jouet : 2μ₁₁ = −4 et μ₂₀ − μ₀₂ = 0. Donc arctan2(−4, 0) = −90°, et **θ = −45°**. La forme est orientée le long de la diagonale descendante — ce que le signe de μ₁₁ annonçait déjà en 2.3, et qu'on vérifie d'un coup d'œil sur le dessin. (Rappel du piège 2.1 : l'angle se lit dans le repère image, y vers le bas.)

### Applications

L'orientation principale sert d'abord à **redresser** un objet avant de le reconnaître : remettre un caractère ou un code-barres à l'horizontale, aligner une empreinte digitale sur son axe, normaliser la pose d'une cellule avant classification. Elle sert aussi en tant que mesure : en microscopie, l'histogramme des orientations des fibres de collagène quantifie l'anisotropie d'un tissu ; en télédétection, celui des orientations de bâtiments révèle la trame d'une ville.

### Piège : l'orientation d'un objet rond n'existe pas

Quand la forme est ronde (ou carrée vue de face), elle s'étale autant dans toutes les directions : il n'y a plus d'axe privilégié, et la formule devient indéterminée. Un seul pixel de bruit fait alors basculer θ de 90°. Demander l'orientation d'un disque, c'est demander dans quelle direction pointe une boule de pétanque — la question n'a pas de réponse, et l'algorithme en donnera pourtant une.

Il faut donc toujours accompagner θ d'une mesure de fiabilité, l'**anisotropie**, qui dit à quel point la forme a réellement une direction dominante :

```
aniso = √((μ₂₀−μ₀₂)² + 4μ₁₁²) / (μ₂₀+μ₀₂)
```

Elle vaut 0 pour un disque (aucune direction privilégiée) et tend vers 1 pour un segment (une seule direction). Règle pratique : ne pas faire confiance à θ quand aniso < 0,2. C'est la première manifestation chiffrée du fil conducteur : l'ordre 2 fonctionne très bien… sauf dans son cas dégénéré, où il devient brutalement instable.

### Code
```python
# Renvoie l'orientation ET sa fiabilité (anisotropie).
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
m = cv2.moments(msk, binaryImage=True)
mu20, mu02, mu11 = m["mu20"], m["mu02"], m["mu11"]
denom = mu20 + mu02
if denom > 0:
    theta = 0.5 * np.arctan2(2 * mu11, mu20 - mu02)       # radians, repère image
    aniso = np.sqrt((mu20 - mu02) ** 2 + 4 * mu11 ** 2) / denom
    out_a = {"orientation_deg": float(np.degrees(theta)),
             "anisotropie": float(aniso),
             "fiable": bool(aniso >= 0.2)}
else:
    out_a = {"Erreur": "masque vide"}
```

---

## 2.6 Ellipse équivalente

### Définition
```
demi-grand axe : a = 2√λ₁
demi-petit axe : b = 2√λ₂
excentricité   : e = √(1 − λ₂/λ₁)
```
où λ₁ et λ₂ sont les deux **étalements** de la forme (voir ci-dessous).

### L'idée

L'ellipse équivalente est le « résumé » le plus simple d'une silhouette : l'ellipse qui répartit sa masse exactement comme la forme réelle — même centre, même orientation, même façon de s'étaler. C'est la forme la plus dépouillée qui « pèse » comme l'originale.

Pour la trouver, on reprend l'image du nuage de points du chapitre 1. Une silhouette est une nuée de pixels ; on cherche les deux directions privilégiées de ce nuage : celle où il s'étale le plus (le grand axe) et celle, perpendiculaire, où il s'étale le moins (le petit axe). Deux nombres mesurent ces étalements — appelons-les λ₁ (le grand) et λ₂ (le petit). Inutile de savoir les calculer ; il suffit de retenir ce qu'ils disent : **λ₁, c'est de combien la forme s'étire dans sa direction la plus longue ; λ₂, dans sa direction la plus courte.** Les demi-axes de l'ellipse s'en déduisent, et l'excentricité, e = √(1 − λ₂/λ₁), n'est rien d'autre que la comparaison des deux étalements — c'est exactement l'excentricité promise au chapitre 1, enfin reliée à sa source. Quand les deux étalements sont égaux (forme ronde), e tombe à 0 ; quand le petit devient minuscule face au grand (forme en aiguille), e tend vers 1.

### Exemple numérique (suite et fin du masque jouet)

En combinant μ₂₀ = 4, μ₀₂ = 4 et μ₁₁ = −2, on obtient les deux étalements :

```
λ₁ ≈ 0,857   →  demi-grand axe a = 2√λ₁ ≈ 1,85
λ₂ ≈ 0,286   →  demi-petit axe b = 2√λ₂ ≈ 1,07

excentricité : e = √(1 − λ₂/λ₁) = √(1 − 1/3) ≈ 0,82
```

Une forme nettement allongée, le long de la diagonale θ = −45° trouvée en 2.5. Sept pixels ont suffi pour dérouler toute la chaîne : moments bruts → centroïde → moments centraux → orientation → ellipse.

### Le piège central : l'ellipse ne mesure pas la taille de l'objet

C'est probablement l'erreur la plus répandue de tout le chapitre. L'ellipse équivalente égalise la **répartition de masse**, pas les **dimensions**. Le grand axe de l'ellipse équivalente d'un rectangle **dépasse d'environ 15 % la longueur réelle** du rectangle. L'intuition : pour qu'une ellipse, effilée à ses extrémités, loge autant de masse loin du centre qu'un rectangle dont les bouts sont pleins, elle doit être plus longue que lui. D'où la règle à encadrer :

> `axis_major_length` de regionprops n'est **pas** la longueur de l'objet.

Pour mesurer la dimension réelle d'une pièce sur une chaîne de contrôle, d'une bactérie ou d'un trait, il faut le **rectangle orienté minimal** (`cv2.minAreaRect`) ou le **diamètre de Feret**. L'ellipse équivalente décrit la *répartition de masse* (orientation, excentricité) ; elle ne mesure pas. Confondre les deux usages introduit une erreur systématique de l'ordre de 15 % — du genre qui passe inaperçu pendant toute une campagne de mesures.

### Code
```python
# regionprops donne l'ellipse équivalente clé en main.
from skimage.measure import regionprops, label

msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
props = regionprops(label(msk > 0))
if props:
    p = props[0]
    out_a = {
        "centroide (y,x)": [float(v) for v in p.centroid],  # (ligne, colonne) !
        "orientation_rad": float(p.orientation),
        "grand_axe (2a)":  float(p.axis_major_length),      # ≠ longueur réelle
        "petit_axe (2b)":  float(p.axis_minor_length),
        "excentricite":    float(p.eccentricity),           # le e du chapitre 1
    }
else:
    out_a = {"Erreur": "masque vide"}
```

### Piège de bibliothèque : des noms et une convention qui ont changé

scikit-image a fait évoluer cette partie de son interface. Les propriétés s'appellent désormais `axis_major_length` / `axis_minor_length` (les anciens noms `major_axis_length` / `minor_axis_length` sont dépréciés), et la **convention d'angle** de `orientation` (origine, sens de rotation) a elle aussi changé entre versions. Avant toute campagne de mesures, validez la chaîne sur une forme test connue — un rectangle synthétique tracé à 30°, par exemple — et vérifiez que l'angle ressorti est bien celui attendu. Cette vérification de trente secondes vaut une page de documentation, et elle attrape aussi les confusions d'axes de la section 2.1.

---

## 2.7 Les sept invariants de Hu

### L'idée

Il reste une invariance à conquérir : la **rotation**. Les η_pq sont insensibles à la position et à la taille, mais tourner la forme les mélange entre eux. Hu (1962) a trouvé sept combinaisons des moments d'ordre 2 et 3 que la rotation laisse intactes. Réunis aux invariances précédentes — translation (μ), échelle (η), rotation (φ) — ces sept nombres (φ₁, …, φ₇) constituent une **signature de la forme « pure »**, débarrassée de toute sa pose : la même pour un objet petit ou grand, déplacé ou tourné.

L'analogie utile est celle d'une empreinte digitale de la forme. Peu importe l'angle sous lequel on présente l'objet, sa signature de Hu reste la même — comme on reconnaît une chanson quelle que soit la tonalité dans laquelle on la chante.

### Pourquoi ces combinaisons résistent-elles à la rotation ?

Les formules (sept expressions touffues mêlant les η) paraissent sorties d'un chapeau, et il n'est pas utile de les reproduire ni de les mémoriser : les bibliothèques s'en chargent. Ce qu'il faut comprendre, c'est qu'elles n'ont pas été *trouvées* au hasard mais *construites* pour une raison précise. Quand on tourne une forme, ses moments changent d'une façon très régulière : c'est seulement l'« angle » de certaines quantités qui bouge, pas leur taille. Hu a assemblé les η de manière que cet angle s'élimine de lui-même — un peu comme la longueur d'un vecteur ne change pas quand on le fait pivoter, même si ses coordonnées, elles, changent. Ce qui reste après élimination de l'angle est, par construction, insensible à la rotation.

### Deux propriétés à connaître

**φ₇ change de signe en miroir.** C'est le seul des sept. Une forme et son reflet dans un miroir ont les mêmes φ₁ à φ₆, mais des φ₇ opposés. Précieux quand la chiralité compte — distinguer « b » de « d », « p » de « q » en reconnaissance de caractères — et à exclure du vecteur quand elle ne compte pas, sous peine de séparer artificiellement des objets identiques vus de dos.

**La dynamique est énorme.** Les φ s'étagent typiquement de 10⁻¹ à 10⁻²⁰ : comparés directement, les petits sont écrasés par les grands. On les ramène toujours à des ordres de grandeur comparables en passant par le logarithme (en préservant le signe, crucial pour φ₇) avant toute comparaison.

### Exemple : reconnaissance de caractères

C'est l'application historique. Un « A » conserve sa signature qu'il soit petit, grand, tourné ou déplacé — exactement les insensibilités voulues pour une reconnaissance robuste. Un « O » très symétrique a ses moments d'ordre 3 quasi nuls, donc φ₃ à φ₇ ≈ 0 ; un « R » asymétrique les a nettement non nuls. La distance entre deux signatures de Hu (en échelle log — voir chapitre 3) suffit à un classifieur des plus simples.

### Hu aujourd'hui : encore utile ?

Pour la reconnaissance générale, les descripteurs appris (réseaux de neurones) dominent largement. Les moments de Hu gardent trois créneaux bien réels : (1) quand on a peu ou pas de données d'entraînement, (2) quand il faut une invariance **prouvable** et non simplement constatée — métrologie, certification industrielle —, (3) quand le budget de calcul est minuscule (capteurs embarqués). Le bon réflexe n'est pas « Hu ou réseau de neurones ? » mais « mon problème exige-t-il une garantie mathématique, ou une performance statistique ? ».

### Code
```python
# Renvoie les 7 invariants de Hu en échelle log signée.
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
m = cv2.moments(msk, binaryImage=True)

# HuMoments renvoie les 7 invariants ; flatten() les met à plat.
hu = cv2.HuMoments(m).flatten()

# log10 de la valeur absolue : ramène tous les φ à des ordres comparables.
# np.sign préserve le signe (crucial pour φ₇). Le +1e-30 évite log(0).
hu_log = -np.sign(hu) * np.log10(np.abs(hu) + 1e-30)
out_a = {f"phi{i+1}": float(v) for i, v in enumerate(hu_log)}
```

---

## 2.8 Moments pondérés par l'intensité

Toutes les formules du chapitre s'appliquent sans changement à une image en niveaux de gris : il suffit de remplacer le masque binaire par les intensités, I(x, y) = niveau de gris. Seule l'interprétation change :

```
centroïde binaire  : centre géométrique du masque
centroïde pondéré  : barycentre lumineux (tiré vers les zones claires)
```

L'image mentale : le masque binaire traite tous les pixels comme aussi « lourds » les uns que les autres, tandis que la version pondérée rend les pixels clairs plus lourds que les pixels sombres. Le point d'équilibre se déplace alors vers les zones lumineuses.

Cet écart est exploité directement. En astronomie, une étoile s'étale sur quelques pixels avec un profil lumineux en cloche ; le centroïde pondéré moyenne ce profil et localise la source au **sous-pixel** — bien plus finement que le simple pixel le plus brillant. C'est le principe des mesures astrométriques de précision. De même, en caractérisation de faisceau laser, les moments pondérés d'ordre 2 définissent la largeur du faisceau (méthode D4σ, norme ISO 11146) — la définition de référence de l'industrie.

### Code
```python
# a : masque (entrée 1).  b : image en niveaux de gris ou couleur (entrée 2).
# Mesure de combien la lumière déplace le centroïde par rapport au masque seul.
msk = np.ascontiguousarray(a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), np.uint8)
m_bin = cv2.moments(msk, binaryImage=True)
gray = b if (b is not None and b.ndim == 2) else cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

# On ne garde que les intensités de l'objet (gray là où le masque est allumé).
m_int = cv2.moments(gray.astype(np.float32) * (msk > 0), binaryImage=False)

if m_bin["m00"] > 0 and m_int["m00"] > 0:
    shift = float(np.hypot(
        m_int["m10"] / m_int["m00"] - m_bin["m10"] / m_bin["m00"],
        m_int["m01"] / m_int["m00"] - m_bin["m01"] / m_bin["m00"]))
    out_a = {"decalage_centroides_px": shift}
else:
    out_a = {"Erreur": "masque ou image vide"}
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

La règle à retenir : **plus l'ordre est élevé, plus le moment regarde loin du centroïde, plus il amplifie le bruit de contour.** Vous connaissez peut-être déjà cette hiérarchie sous une autre forme : en statistiques, la moyenne d'un échantillon est plus stable que sa variance, elle-même plus stable que son asymétrie (skewness) puis son aplatissement (kurtosis). Ce sont les mêmes moments, appliqués à une distribution de nombres au lieu d'une image — et le parallèle, une fois vu, ne s'oublie plus.

Ce compromis prolonge la leçon du chapitre 1 : un descripteur encode un point de vue, et les moments ajoutent que **chaque supplément de détail se paie en fragilité**. L'ordre 0 voit peu mais ne se trompe jamais ; l'ordre 3 voit l'asymétrie fine mais vacille au moindre pixel. Choisir l'ordre de ses moments, c'est choisir un point d'équilibre entre ce qu'on veut voir et ce qu'on peut mesurer de façon fiable — un arbitrage que l'on retrouvera au chapitre 6, où dériver une image (l'analogue continu de monter en ordre) amplifiera le bruit exactement de la même manière.
