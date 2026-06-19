# Chapitre 6 — Là où l'image bascule : gradients et contours

![Un randonneur, boussole en main, sur un paysage en relief dont l'altitude est l'intensité de l'image ; les contours sont des falaises](../figures/fig_ch6_couverture.jpg)
*Si l'intensité était une altitude, l'image deviendrait un paysage. Le gradient pointe la plus forte pente, les contours sont ses falaises — et le moindre caillou de bruit s'y fait passer pour un sommet.*

---

Un contour, c'est l'endroit où l'intensité change brusquement : la frontière entre une cellule et le fond d'une boîte de Petri, le bord d'une pièce usinée sous une caméra de contrôle, la crête d'un relief sur une image satellite. Détecter ces frontières, c'est mesurer la **dérivée** de l'image — la dérivée étant l'outil mathématique qui mesure la vitesse de changement. Là où la valeur des pixels saute, elle est grande ; là où l'image est uniforme, elle est nulle.

Mais mesurer un changement a un coût immédiat : toute dérivée amplifie le bruit. Un pixel un peu trop clair, à cause d'un photon parasite, crée une variation locale que la dérivée repère avec la même ardeur qu'un vrai bord. C'est le fil du chapitre : **dériver amplifie le bruit ; tout détecteur de contours dose lissage et dérivation.** Chaque outil ici — du simple gradient au pipeline de Canny, du tenseur de structure aux détecteurs de coins — est une réponse particulière à cette tension entre voir les vraies variations et ignorer les fausses.

Le chapitre s'appuie sur le chapitre 5 : lisser efface les variations rapides, dériver les exalte. Détecter un contour proprement revient à laisser passer les variations des vraies structures tout en bloquant celles du bruit. La gaussienne, rencontrée au chapitre 5 comme outil de lissage, joue ici un rôle central.

### Un peu de vocabulaire avant de commencer

*   **Gradient** : Le vecteur qui indique la direction de la plus forte hausse d'intensité et le taux de cette variation.
*   **Dérivées partielles (Ix, Iy)** : Les variations de luminosité mesurées dans les deux directions principales (horizontale `Ix` et verticale `Iy`).
*   **Magnitude (norme du gradient)** : La force de la variation d'intensité (la raideur de la pente), calculée à partir des dérivées partielles.
*   **Orientation (angle du gradient)** : La direction perpendiculaire au contour, pointant vers la zone la plus claire.

---

## 6.1 — Le gradient d'image : la boussole de la pente

> *Une flèche qui pointe vers la plus forte montée d'intensité*

### L'intention

On veut, en chaque pixel, savoir deux choses : y a-t-il une variation d'intensité ici, et dans quelle direction ? La première répond « y a-t-il un contour ? », la seconde « comment est-il orienté ? ».

### La forme recherchée

Si l'image était une carte de relief où l'intensité joue le rôle de l'altitude, on cherche en chaque point la flèche de plus forte pente — comme la boussole d'un randonneur pointant vers le sommet le plus proche. Cette flèche, le **gradient**, a une direction (vers où l'intensité monte le plus vite) et une longueur (à quelle vitesse). Sur un bord net entre sombre et clair, elle pointe perpendiculairement au bord et sa longueur est élevée ; dans une région uniforme, elle est de longueur nulle. Les contours sont les falaises de cette carte.

### La formule

```
∇I = (Iₓ, Iᵧ)                          (le gradient : deux composantes)
magnitude :   ‖∇I‖ = √(Iₓ² + Iᵧ²)       → « y a-t-il un contour ici ? »
orientation : θ = arctan2(Iᵧ, Iₓ)        → « dans quelle direction ? »
```

Le symbole ∇ (« nabla ») désigne le gradient ; Iₓ est la variation d'intensité dans le sens horizontal, Iᵧ dans le sens vertical. La **magnitude** (la longueur de la flèche) est leur combinaison à la Pythagore ; l'**orientation** est l'angle de la flèche. Sur une grille de pixels, on approche ces variations par des **différences finies** — la différence entre un pixel et son voisin. La version la plus précise est la différence « centrée » : on compare le voisin de droite au voisin de gauche, ce qui place le contour exactement au bon endroit, sans décalage d'un demi-pixel. ∎

### Exemple

Ligne d'intensités `[10, 10, 10, 80, 90, 90, 90]`. La variation centrée en chaque point (moitié de l'écart entre voisins) :

```
position 3 (la marche) : (80 − 10) / 2 = 35   (gradient fort, la frontière est ici)
position 1 (zone plate) : (10 − 10) / 2 = 0    (aucune variation)
position 5 (zone plate) : (90 − 90) / 2 = 0    (aucune variation)
```

### Piège — la bonne arc-tangente

L'orientation se calcule avec `arctan2`, une variante de l'arc tangente qui tient compte du quadrant — elle distingue un bord montant vers la droite d'un bord descendant vers la gauche, là où la simple `arctan` les confondrait (erreur de 180°). C'est l'erreur n°1 des détecteurs faits maison. À noter aussi : en image, l'axe vertical descend (la ligne 0 est en haut), si bien que les angles se lisent dans le sens horaire.

### Dans VNStudio

Canvas : `Image Source` → `Grayscale` → `Sobel Gradient` → `Output Display`. Le nœud sort la carte de magnitude (les contours s'allument en clair) et, dans l'inspecteur, le gradient moyen et maximal ainsi que le nombre de pixels au-dessus d'un seuil de contour.

---

## 6.2 — Sobel et Scharr : dériver en lissant de travers

> *Mesurer la pente sur trois lignes à la fois, pas une seule*

### L'intention

La simple différence centrée ne lit qu'une seule ligne de pixels : le bruit d'une ligne suffit à fausser la mesure. On veut dériver sans laisser une ligne isolée décider seule.

### La forme recherchée

On réintroduit du lissage là où on combat le bruit : on dérive dans une direction tout en **lissant perpendiculairement**, sur plusieurs lignes. Le pochoir de Sobel le fait en un seul geste — c'est un pochoir 3×3 qui, lu de gauche à droite, prend la différence (pour dériver), et qui, lu de haut en bas, fait une moyenne pondérée des trois lignes (pour lisser). Le poids (1, 2, 1) donne plus d'importance à la ligne centrale, la plus fiable.

### La formule

```
Sₓ = [−1  0  +1]      Sᵧ = [−1  −2  −1]
     [−2  0  +2]            [ 0   0   0]
     [−1  0  +1]            [+1  +2  +1]
```

Sₓ détecte les bords verticaux (variation horizontale), Sᵧ les bords horizontaux. La variante **Scharr** remplace le poids (1, 2, 1) par (3, 10, 3), réglé pour que la réponse soit la même quelle que soit l'orientation du bord — un bord à 45° donne alors la même magnitude qu'un bord à 0°. Pour des mesures d'angle précises (l'inclinaison d'une pièce en vision industrielle, l'orientation de fibres en microscopie), Scharr est préférable. ∎

### Exemple

Petit carré 3×3 avec un bord vertical net (gauche sombre = 0, droite claire = 100). On applique Sₓ au pixel central :

```
Sₓ * centre = 0 (colonne gauche) + 0 (colonne centre) + (100+200+100) (colonne droite) = 400
Sᵧ * centre = (−100) + 0 + (100) = 0
```

Le gradient vaut 400 en horizontal, 0 en vertical : il pointe à l'horizontale, perpendiculaire au bord vertical — exactement attendu.

### Piège — garder les valeurs négatives

Un bord clair→sombre donne une variation négative. Si l'on stocke le résultat en nombres entiers non signés, ces valeurs négatives sont écrasées à zéro et l'on rate tous les bords descendants. On calcule donc en nombres à virgule, et on ne prend la valeur absolue qu'au moment d'afficher.

### Dans VNStudio

Canvas : `Image Source` → `Grayscale` → `Sobel Gradient` (ou `Scharr Gradient`) → `Output Display`. Le nœud calcule en interne en nombres à virgule et expose au choix Sobel ou Scharr ; l'inspecteur compare leurs magnitudes maximales sur la même image.

---

## 6.3 — Le détecteur de Canny : un pipeline qui ose le compromis

> *Lisser, dériver, affiner à un pixel, puis relier ce qui se prolonge*

### L'intention

On veut des contours qui satisfont trois exigences à la fois : peu de faux contours, des contours bien placés, et un seul pixel de large (pas un ruban épais). Aucun pochoir seul n'y parvient.

### La forme recherchée

Canny (1986) n'est pas un pochoir mais un **enchaînement** en cinq étapes, chacune dosant la tension dérivation/bruit :

```
1. Lissage gaussien         → réduire le bruit avant de dériver (σ fixe l'échelle)
2. Gradient (Sobel)         → magnitude et orientation en chaque pixel
3. Suppression non-maximale → amincir les contours à 1 pixel de large
4. Double seuillage         → classer fort / faible / rejeté
5. Hystérésis               → relier les contours faibles aux forts
```

L'étape clé est la **suppression non-maximale**. Le gradient brut donne des contours épais, car la transition s'étale sur plusieurs colonnes. On ne garde un pixel que s'il est le plus fort de ses voisins *dans la direction du gradient* : on regarde les deux voisins de part et d'autre, et si le pixel central n'est pas le plus intense des trois, on le supprime. Le contour est ainsi réduit à sa crête, large d'un pixel — comme on ne garde que le point culminant d'une pente.

### Le double seuil et l'hystérésis

Un seuil unique pose un dilemme : trop haut, on coupe les portions faibles d'un vrai contour ; trop bas, on garde le bruit. L'**hystérésis** tranche avec deux seuils :

```
pixel > seuil haut          → contour certain (gardé d'office)
pixel < seuil bas           → rejeté
entre les deux              → gardé seulement s'il touche un pixel certain
```

L'idée : un pixel faible isolé est probablement du bruit, mais un pixel faible qui **prolonge un contour fort** est probablement la suite du même bord. On se sert du voisinage comme preuve de réalité.

### Exemple

Chaîne de magnitudes le long d'un contour candidat, seuil bas = 50, seuil haut = 100 :

```
...  30    60    80   120    70    55    40  ...
     rej    ?     ?   sûr     ?     ?   rej
```

Le pixel à 120 est certain. Ceux à 80, 70, 55, 60 sont entre les deux seuils et conservés, car reliés en chaîne au pixel certain. Ceux à 30 et 40 (sous 50) sont rejetés, ce qui coupe la chaîne. Résultat : un contour continu de 60 à 120. En lecture de plaques d'immatriculation, ce mécanisme préserve les bords des lettres même sous éclairage inégal : les portions sombres d'un bord survivent grâce aux portions bien éclairées qui les entourent.

### Réglage — trois paramètres liés

Canny a trois réglages : le σ du flou et les deux seuils. Augmenter σ détecte les gros contours et ignore les détails fins — voulu, mais à choisir en connaissance de cause. Une heuristique commode fixe les deux seuils autour de la valeur médiane de l'image (un peu en dessous, un peu au-dessus), ce qui s'adapte tout seul au contraste général.

### Paramètres opérationnels (VNStudio / Python)

Dans le nœud `Canny` (ou via `cv2.Canny` en Python), la détection repose sur trois paramètres fondamentaux :

*   **Taille du noyau Sobel (`apertureSize`)** :
    *   Dans VNStudio, ce paramètre correspond au champ **Sobel Aperture** ; en Python (OpenCV), il se nomme `apertureSize` dans `cv2.Canny`.
    *   Configure la taille de la grille (généralement 3×3 ou 5×5) utilisée pour estimer les dérivées partielles horizontales et verticales. Une grille plus grande lisse davantage les variations de pente et résiste mieux au bruit, au détriment de la précision de localisation des contours.
*   **Seuil bas et Seuil haut (`threshold1`, `threshold2`)** :
    *   Dans VNStudio, ces paramètres correspondent aux curseurs **Low Threshold** et **High Threshold** ; en Python (OpenCV), ils correspondent aux arguments `threshold1` et `threshold2` dans `cv2.Canny`.
    *   Ces deux seuils contrôlent le processus d'hystérésis. La règle empirique recommandée par Canny est d'utiliser un rapport de **1:2 ou 1:3** entre le seuil bas et le seuil haut (ex. : `seuil_bas = 50`, `seuil_haut = 150`). Un seuil haut trop faible génère de fausses alertes (bruit pris pour des contours) ; un seuil bas trop élevé brise les contours continus en une multitude de petits segments disjoints.
*   **Formule de magnitude (`L2gradient`)** :
    *   Dans VNStudio, ce paramètre correspond à la case à cocher **L2 Gradient** ; en Python (OpenCV), il correspond à l'argument `L2gradient` dans `cv2.Canny`.
    *   Un paramètre booléen. Réglé sur `True`, il utilise la formule euclidienne exacte pour la magnitude du gradient. Réglé sur `False`, il applique l'approximation absolue plus rapide `|Gx| + |Gy|` qui convient aux applications en temps réel.

### Dans VNStudio

Dans votre canvas :
`Image Source` ──> `Grayscale` ──> `Canny Edge Detector` ──> `Output Display`.

En ajustant les deux curseurs de seuils dans l'inspecteur, vous pouvez observer directement la mécanique de l'hystérésis : augmenter le seuil haut élimine les détails de texture parasites, tandis que diminuer le seuil bas reconnecte les lignes de contours interrompues. Le nœud expose également l'option de calcul automatique par la médiane et l'inspecteur affiche la densité de pixels de contour pour faciliter le réglage.

**Exercice de dépannage :** L'exercice consiste à inverser les seuils dans le nœud **Canny Edge Detector** en réglant **Low Threshold** sur 150 et **High Threshold** sur 50. Le lecteur observe que l'hystérésis est rompue : les contours deviennent extrêmement fragmentés et la plupart disparaissent. Cela s'explique par le fait qu'aucun point de départ solide (supérieur au seuil haut) ne peut être raccordé à une chaîne de points de confiance (supérieurs au seuil bas), puisque le seuil bas est plus restrictif que le seuil haut.

---

## 6.4 — Le tenseur de structure : plat, bord ou coin ?

> *Le détective qui observe toute la zone, pas une seule empreinte*

### L'intention

Le gradient décrit un pixel isolé. On veut caractériser un **voisinage** entier : est-ce une région plate, un bord, ou un coin ? Cela demande de rassembler l'information de plusieurs pixels.

### La forme recherchée

Comme un détective qui observe toute une zone du sol — pour savoir si quelqu'un est passé, dans quelle direction, à quelle vitesse — plutôt qu'une seule empreinte. On rassemble les gradients du voisinage et on en tire deux nombres résumant l'étalement des directions de variation : ce sont les **valeurs propres**, déjà rencontrées au §1.3 et au §2.6 sous le même nom. Inutile de savoir les calculer ; il suffit de lire ce qu'elles disent. Notons-les λ₁ (la plus grande) et λ₂ (la plus petite) :

```
λ₁ ≈ λ₂ ≈ 0      → région plate (aucune variation, fond uniforme)
λ₁ ≫ λ₂ ≈ 0      → contour (forte variation dans une seule direction)
λ₁ ≈ λ₂ ≫ 0      → coin ou texture (variation dans toutes les directions)
```

### La formule

On calcule, pour chaque pixel, les gradients horizontaux `Iₓ` et verticaux `Iᵧ`, puis on accumule sur tout son voisinage trois quantités précises : `Iₓ²`, `Iᵧ²`, et leur produit `IₓIᵧ`, pondérées par une cloche gaussienne (chapitre 5). Le résultat est un petit tableau 2×2 — le **tenseur de structure** :

```
T = [  somme(Iₓ²)    somme(IₓIᵧ)  ]
    [  somme(IₓIᵧ)   somme(Iᵧ²)   ]
```

Pour comprendre intuitivement pourquoi nous construisons ce tableau avec ces multiplications, posons les choses :
1. **Pourquoi élever au carré (`Iₓ²` et `Iᵧ²`) ?** Si nous nous contentions d'additionner les gradients bruts dans une zone, un gradient pointant vers la droite (`Iₓ = 10`) et un gradient pointant vers la gauche (`Iₓ = −10`) s'annuleraient mutuellement lors de la sommation. L'algorithme conclurait que la zone est plate (somme nulle) alors qu'elle contient des lignes verticales très contrastées ! Élever les gradients au carré garantit que les variations sont comptées positivement et s'additionnent toujours sans jamais s'annuler.
2. **À quoi sert le produit croisé (`IₓIᵧ`) ?** Il sert d'indicateur de direction diagonale (la corrélation). Si les gradients horizontaux et verticaux varient en même temps et dans le même sens (un bord oblique), le produit `IₓIᵧ` sera très fort. S'ils varient indépendamment (bruit) ou de façon purement orthogonale (bords horizontaux ou verticaux stricts), la somme de ce produit tendra vers zéro.

Les deux valeurs propres de ce tableau `T` (notées `λ₁` et `λ₂`) correspondent aux longueurs des demi-axes de l'ellipse qui décrit la distribution des gradients, de la même manière qu'au chapitre 2 sur les moments. Un contour n'a qu'une seule direction de variation (une grande et une petite valeur propre) ; un coin n'en a aucune de privilégiée (deux grandes). La pondération gaussienne plutôt qu'une fenêtre carrée évite les artefacts de bord et traite toutes les directions équitablement ; sa largeur fixe l'échelle des structures détectées. ∎

### Dans VNStudio

Canvas : `Image Source` → `Grayscale` → `Structure Tensor` → `Output Display`. Le nœud colore chaque pixel selon le cas diagnostiqué (plat / bord / coin) d'après ses deux valeurs propres, ce qui donne à voir la géométrie locale d'un coup d'œil.

---

## 6.5 — Coins : Harris et Shi-Tomasi

> *Reconnaître un coin sans calculer ses valeurs propres une à une*

### L'intention

Un coin — point où deux contours se rencontrent — est précieux car **reproductible** : photographiez le même objet sous deux angles, les coins restent, là où les bords droits peuvent disparaître. En suivi de mouvement, reconstruction 3D, assemblage de panoramas, ce sont les repères qu'on retrouve d'une image à l'autre. On veut les détecter sans calculer explicitement les valeurs propres en chaque pixel, ce qui serait coûteux.

### La forme recherchée

Deux raccourcis d'algèbre donnent les valeurs propres *indirectement*, par deux quantités faciles à calculer à partir du tenseur de structure : leur **produit** et leur **somme**.

```
produit des valeurs propres = λ₁ · λ₂
somme   des valeurs propres = λ₁ + λ₂
```

Un indicateur bâti sur ces deux quantités suffit à distinguer les trois cas, sans jamais isoler λ₁ et λ₂ :

```
indicateur grand et positif  ⟺  λ₁, λ₂ tous deux grands  ⟺  coin
indicateur négatif           ⟺  une valeur propre domine  ⟺  contour
indicateur proche de zéro    ⟺  les deux petites          ⟺  région plate
```

### La formule

```
Harris :      R = (produit) − k · (somme)²     k ≈ 0.04–0.06
Shi-Tomasi :  R = la plus petite des deux valeurs propres
```

Chez **Harris**, le terme retranché pénalise le cas « une seule grande valeur propre » (un simple bord) pour ne garder que les vrais coins ; le réglage k dose la sévérité. **Shi-Tomasi** propose plus simple encore : prendre directement la plus petite des deux valeurs propres. Si elle est grande, c'est que les deux directions varient fortement — un bon coin à suivre. C'est le critère par défaut pour choisir les points qu'un suivi de mouvement va traquer.

Les deux sont **invariants en rotation** (un coin reste un coin si on tourne l'image) mais **pas invariants à l'échelle** : un coin vu de loin peut ressembler à une texture. Cette limite a motivé les détecteurs multi-échelles comme SIFT, qui cherche les coins à plusieurs niveaux de flou à la fois — une réponse plus élaborée au même fil. ∎

### Exemple

Trois voisinages, avec les valeurs propres de leur tenseur :

```
région plate : λ₁=2,   λ₂=1   → Harris ≈ 1,55 (faible)   Shi = 1  (faible) → pas un coin
contour      : λ₁=100, λ₂=2   → Harris ≈ −320 (négatif)  Shi = 2  (faible) → contour
coin         : λ₁=80,  λ₂=70  → Harris ≈ 4475 (fort +)   Shi = 70 (fort)   → coin
```

Les deux critères donnent le même diagnostic : seul le troisième voisinage est un coin.

### Dans VNStudio

Canvas : `Image Source` → `Grayscale` → `Harris Corners` (ou `Good Features To Track`) → `Output Display`. Le nœud marque les coins détectés sur l'image et l'inspecteur en donne le nombre ; un réglage de sensibilité fait varier combien de coins ressortent.

---

## Tableau récapitulatif — du gradient à la structure

| Outil | Ce qu'il mesure | Angle mort | Usage typique |
|---|---|---|---|
| Gradient ∇I | variation locale (force et direction) | sensible au bruit — dériver = amplifier | carte de magnitude, orientation locale |
| Sobel / Scharr | gradient robuste (lissage intégré) | contours épais, pas de connexité | première estimation, entrée d'autres outils |
| Canny | contours fins, connectés, bien placés | trois paramètres liés (σ, deux seuils) | détection généraliste, OCR, vision industrielle |
| Tenseur de structure | géométrie locale (plat / bord / coin) | coûteux par pixel, paramètre d'échelle | analyse de texture, entrée de Harris |
| Harris | coins stables (invariant rotation) | pas invariant à l'échelle | homographie, mosaïque, suivi |
| Shi-Tomasi | coins optimaux pour le suivi | idem Harris | suivi de mouvement, SLAM |

---

## Encadré final — la vraie question n'est pas s'il faut lisser, mais à quelle échelle

Tout le chapitre tourne autour d'une même tension :

```
dériver  → révèle les variations, mais amplifie le bruit
lisser   → supprime le bruit,     mais émousse les variations
```

Chaque outil dose ces deux opérations antagonistes : le gradient pur dérive à nu (sensibilité maximale au bruit), Sobel/Scharr intègrent un lissage transversal, Canny applique un flou explicite avant de dériver puis relie par hystérésis, le tenseur de structure moyenne les gradients sur un voisinage, et le LoG/DoG du chapitre 5 fait du lissage l'opérateur même. La question de conception n'est jamais « faut-il lisser ? » mais « à quelle échelle ? ». Le σ du lissage fixe la taille des structures qu'on verra : petit σ pour les détails fins (nervures d'une feuille, micro-fissures de contrôle qualité), grand σ pour les contours saillants des grandes structures (bâtiments en télédétection, organes en imagerie médicale).

Comme un descripteur du chapitre 1 ou un filtre du chapitre 5, choisir cette échelle encode une hypothèse sur ce qui compte : un petit σ déclare que les variations au niveau du pixel sont significatives, un grand σ que seules les structures de plusieurs pixels méritent attention. Le chapitre 10 retrouvera ce lien entre échelle et représentation, où changer de point de vue permettra de lire la même image à plusieurs résolutions à la fois.

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch6_couverture` | chapeau | Illustration : randonneur + boussole sur un paysage-intensité, contours = falaises | JPG/PNG |
| `fig_ch6_01_gradient_pente` | 6.1 | Surface d'intensité 3D + flèche gradient pointant la plus forte pente | SVG |
| `fig_ch6_02_sobel_factor` | 6.2 | Sobel : un pochoir qui dérive dans un sens et lisse dans l'autre | SVG |
| `fig_ch6_03_canny_nms` | 6.3 | Avant/après suppression non-maximale : ruban épais → crête 1 px | SVG |
| `fig_ch6_04_hysteresis` | 6.3 | Chaîne de magnitudes, double seuil, propagation par connexité | SVG |
| `fig_ch6_05_tenseur` | 6.4 | Trois voisinages (plat / bord / coin) + leurs valeurs propres | SVG |
| `fig_ch6_06_harris_plan` | 6.5 | Plan (somme, produit) avec zones coin / contour / plat | SVG |
