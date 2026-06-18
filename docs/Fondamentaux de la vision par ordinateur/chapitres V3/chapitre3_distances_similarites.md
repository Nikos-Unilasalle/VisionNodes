# Chapitre 3 — Mesurer un écart : distances et similarités

![Un personnage hésite devant plusieurs règles de mesure aux graduations différentes, chacune donnant un autre verdict sur la distance entre deux objets](../figures/fig_ch3_couverture.jpg)
*Il n'existe pas une distance, mais une famille entière, et chaque règle voit les données à sa façon. Choisir l'une plutôt qu'une autre décide de ce que « proche » veut dire.*

---

Comparer deux objets — deux descripteurs de forme du chapitre 1, deux histogrammes de couleur, deux distributions — suppose une mesure de leur écart. Mais il n'existe pas de « distance » universelle : il en existe une famille entière, et chacune voit les données à sa façon. Choisir l'une plutôt qu'une autre n'est jamais un détail technique, car ce choix décide de ce que « proche » veut dire. Ce chapitre passe en revue les distances usuelles, de la plus simple (euclidienne) aux plus structurées (Mahalanobis, Wasserstein), avec à chaque fois la même question : *qu'est-ce que je déclare important en la choisissant ?*

Le fil du chapitre tient en une phrase : **une distance déclare ce qui compte.** Elle rend certains écarts négligeables et d'autres décisifs ; elle impose une géométrie aux données avant même qu'on les compare. Comprendre une distance, c'est connaître l'hypothèse qu'elle fait dans votre dos.

### Un peu de vocabulaire avant de commencer

*   **Distance (ou métrique)** : Une mesure d'écart qui respecte quatre règles : elle est toujours positive ou nulle, s'annule uniquement si les deux objets sont identiques, est symétrique, et respecte l'**inégalité triangulaire** (le détour ne raccourcit pas le trajet).
*   **Similarité** : Une mesure de ressemblance (plus elle est grande, plus les objets se ressemblent) qui ne respecte pas nécessairement les règles géométriques d'une distance.
*   **Vecteur** : Une simple liste ordonnée de nombres (ex. : les descripteurs d'une forme, les cases d'un histogramme).

---

## 3.1 — Distances de Minkowski (L_p) : un seul bouton, trois distances

> *Du taxi en damier au vol d'oiseau, selon comment on agrège les écarts*

### L'intention

On veut comparer deux vecteurs nombre par nombre, mais sans figer d'avance la façon de combiner les écarts : tantôt en les additionnant tous, tantôt en ne retenant que le plus grand. Un seul mécanisme réglable couvrirait toute la gamme.

### La forme recherchée

Le réglage est un exposant, noté p, qui décide du poids relatif des grands et des petits écarts. À p = 1, on additionne les écarts tels quels, comme un taxi parcourant des rues en damier (d'où le nom *Manhattan*). À p = 2, on prend la diagonale directe, le vol d'oiseau — la distance ordinaire. Plus p grandit, plus élever à cette puissance écrase les petits écarts devant le plus grand, jusqu'à ce que **seul le plus grand écart compte encore** : c'est la limite L∞, le simple maximum.

L'image la plus parlante est la **boule unité** — l'ensemble des points situés exactement à distance 1 de l'origine. Sa forme change avec p :

```
L1   : losange (carré tourné de 45°)
L2   : cercle
L∞   : carré aligné sur les axes
```

Plus p augmente, plus cette boule gonfle, du losange vers le carré. Ce n'est pas qu'esthétique : les coins du losange L1 sont posés sur les axes, là où certaines coordonnées sont nulles. Une distance L1 « préfère » donc les solutions à coordonnées nulles — la raison géométrique pour laquelle certaines méthodes d'apprentissage bâties sur L1 produisent des modèles parcimonieux (où beaucoup de coefficients valent exactement zéro).

### La formule

```
d_p(x, y) = ( Σᵢ |xᵢ − yᵢ|^p )^(1/p)
```

Le symbole Σ additionne sur toutes les coordonnées ; les barres |…| sont la valeur absolue (l'écart compté positivement, qu'on aille de x vers y ou l'inverse). On élève chaque écart à la puissance p, on somme, puis on prend la racine p-ième pour revenir à une échelle de longueur. Les trois cas :

- p = 1 : distance de Manhattan (L1, *city-block*)
- p = 2 : distance euclidienne (L2)
- p → ∞ : distance de Tchebychev (L∞) ∎

### Exemple chiffré

x = (1, 2, 3), y = (4, 0, 3) → écarts (3, 2, 0) :

```
L1  = 3 + 2 + 0      = 5
L2  = √(9 + 4 + 0)   = √13 ≈ 3,61
L∞  = max(3, 2, 0)   = 3
```

On retrouve toujours l'ordre L∞ ≤ L2 ≤ L1 : plus p est grand, plus la distance est petite, car on agrège les écarts de façon de plus en plus indulgente.

### Limite — la malédiction de la dimension

En haute dimension (des vecteurs à plusieurs centaines de nombres), un phénomène déroutant se produit : les distances euclidiennes se **concentrent**. Le point le plus proche et le plus lointain finissent presque à la même distance, et la notion de voisinage perd son sens — un « plus proche voisin » n'est plus vraiment plus proche que les autres. Deux parades : réduire d'abord le nombre de dimensions (en projetant les vecteurs sur leurs axes les plus informatifs) avant de mesurer, ou employer des distances fractionnaires (p < 1) qui résistent mieux — au prix de l'inégalité triangulaire, qu'elles ne respectent plus.

### Dans VNStudio

Canvas : `Vector A` + `Vector B` → `Distance Metrics` → `Inspector`. Le nœud calcule L1, L2 et L∞ simultanément et les affiche côte à côte, ce qui rend visible l'ordre L∞ ≤ L2 ≤ L1 sur n'importe quelle paire de vecteurs.

---

## 3.2 — Distance de Mahalanobis : compter en variations typiques

> *Un mètre d'écart, banal sur l'autoroute, énorme en travers d'un couloir*

### L'intention

La distance euclidienne suppose en secret que toutes les directions se valent et que les axes sont indépendants. C'est rarement vrai. On voudrait une distance qui tienne compte de la dispersion propre à chaque direction : un écart doit compter peu là où les données varient déjà beaucoup, et beaucoup là où elles varient peu.

### La forme recherchée

L'image juste est celle d'un écart « relatif à la normale du lieu ». Un mètre d'écart est banal le long d'une autoroute, où les positions varient déjà beaucoup ; le même mètre est considérable en travers d'un couloir étroit, où tout le monde se tient sur une ligne. La **distance de Mahalanobis** mesure l'écart non pas en mètres absolus, mais en **nombre de variations typiques** propres à chaque direction.

Pour savoir « combien les données varient dans chaque direction », on a besoin d'un résumé : la **matrice de covariance**, notée Σ. C'est un petit tableau de nombres qui dit, pour un nuage de points, à quel point il s'étire dans chaque direction et si deux directions varient ensemble. Inutile de savoir la calculer ; il suffit de retenir qu'elle décrit la forme du nuage. Munie de Σ, la Mahalanobis **redresse l'espace** : elle étire les directions où les données varient peu, comprime celles où elles varient beaucoup, et défait leurs corrélations, jusqu'à ce que le nuage devienne une boule bien ronde. Dans cet espace redressé, on mesure une simple distance euclidienne. Ses lignes d'égale distance ne sont donc plus des cercles, mais des ellipses qui épousent la forme du nuage.

### La formule

```
d(x, y) = √( (x − y)ᵀ Σ⁻¹ (x − y) )
```

Le détail des symboles importe peu : Σ⁻¹ (l'« inverse » de la covariance) est l'outil qui réalise le redressement, et le reste est une distance euclidienne dans l'espace ainsi redressé. En clair : c'est la distance ordinaire, mais mesurée après avoir rendu le nuage de données parfaitement rond. ∎

### Exemple chiffré

Données très étirées horizontalement, dix fois plus dispersées en x qu'en y. Depuis le centre, comparons deux points à la même distance euclidienne : a = (10, 0) et b = (0, 10).

```
d_eucl(a) = d_eucl(b) = 10        (identiques pour l'euclidienne)

d_Mahal(a) = √(10² / 100) = 1     (10 dans une direction très dispersée : banal)
d_Mahal(b) = √(10² / 1)   = 10    (10 dans une direction peu dispersée : rare)
```

Pour la Mahalanobis, a est dix fois plus proche que b. Un écart de 10 dans la direction de forte variabilité est ordinaire ; le même dans la direction de faible variabilité est exceptionnel. C'est exactement le raisonnement de la détection d'anomalies (un point au-delà de 3 variations typiques est statistiquement suspect), de la classification, et du suivi par filtre de Kalman, où elle valide l'association entre une mesure et une prédiction.

### Piège — une covariance mal estimée

Si l'on a moins de points que de dimensions, le tableau de covariance ne peut pas être « inversé » (l'opération de redressement devient impossible) et la formule explose. Trois parades : ajouter un petit terme stabilisateur, employer une version approchée, ou un estimateur robuste. La règle : ne jamais redresser l'espace à partir d'une covariance estimée sur trop peu de points sans la stabiliser, sous peine d'un résultat faux et silencieux.

### Dans VNStudio

Canvas : `Point Cloud` + `Test Point` → `Mahalanobis` → `Inspector`. Le nœud estime la covariance sur le nuage fourni, redresse l'espace, et affiche la distance de Mahalanobis du point testé ainsi qu'un drapeau « anomalie » quand elle dépasse trois variations typiques.

---

## 3.3 — Similarité cosinus : la direction, pas la longueur

> *Un long article et son résumé pointent dans le même sens*

### L'intention

Parfois, c'est le **profil** d'un vecteur qui importe, pas son **intensité**. Un long article et son résumé parlent du même thème, mais le premier est bien plus « long » que le second. On veut une mesure qui les reconnaisse proches malgré l'écart de taille.

### La forme recherchée

On regarde l'angle entre les deux vecteurs et on ignore leurs longueurs. Deux vecteurs qui pointent dans le même sens sont parfaitement semblables, qu'ils soient longs ou courts ; deux vecteurs perpendiculaires (à angle droit) sont étrangers l'un à l'autre. La mesure naturelle de cet alignement est le **cosinus** de l'angle entre eux : il vaut 1 quand ils pointent exactement dans le même sens, 0 quand ils sont perpendiculaires, −1 quand ils sont opposés.

### La formule

```
cos(θ) = (x · y) / (‖x‖ · ‖y‖) ∈ [−1, 1]
```

Le point « `x · y` » désigne le **produit scalaire** entre deux vecteurs, et `‖x‖` est la longueur (ou norme) du vecteur `x`.

Pour vous représenter le produit scalaire mentalement, dessinez deux flèches partant du même coin sur une table :
1. **L'image de l'ombre portée** : Imaginez qu'une lampe est placée verticalement au-dessus du deuxième vecteur. Le produit scalaire `x · y` mesure la longueur de « l'ombre » projetée par le premier vecteur sur le second, multipliée par la longueur de ce second vecteur. C'est une mesure directe de leur complicité géométrique.
2. **Le calcul pas à pas** : Pratiquement, on multiplie les coordonnées des deux vecteurs face à face, puis on additionne tout : `x₁·y₁ + x₂·y₂ + ...`. Si les deux vecteurs ont des composantes fortes aux mêmes endroits, la somme explose ; s'ils s'évitent (l'un a des valeurs là où l'autre a des zéros), le produit scalaire tombe à zéro.
3. **Le rôle du dénominateur** : Puisque cette ombre portée dépend de la taille des flèches, diviser par le produit de leurs longueurs `‖x‖ · ‖y‖` permet d'annuler cet effet d'échelle. Il ne reste que la pure direction : le cosinus de l'angle `θ` formé par les deux flèches.

On en tire une distance : `d = 1 − cos(θ)`. Deux vecteurs alignés (cos = 1) ont une distance de 0 ; à angle droit (cos = 0), une distance de 1.

C'est pourquoi la recherche documentaire, les systèmes de recommandation et la comparaison d'*embeddings* (des vecteurs qui résument un mot, une image ou une phrase) reposent presque toujours sur le cosinus : l'euclidienne déclarerait l'article et son résumé éloignés à cause de l'écart de taille, le cosinus les reconnaît proches. ∎

### Le pont avec l'euclidienne

Si l'on ramène d'abord les vecteurs à une longueur de 1 (on dit qu'on les **normalise**), distance euclidienne et distance cosinus deviennent deux façons de dire la même chose : l'une croît exactement avec l'autre. D'où une habitude répandue : on normalise les embeddings avant de les ranger dans un index, ce qui permet d'utiliser un moteur de recherche euclidien rapide tout en raisonnant, au fond, en cosinus.

### Exemple chiffré

x = (2, 0), y = (3, 0) : colinéaires → cos = 6 / (2·3) = 1, similarité maximale malgré des longueurs différentes. x = (1, 0), y = (0, 1) : perpendiculaires → cos = 0.

### Dans VNStudio

Canvas : `Vector A` + `Vector B` → `Cosine Similarity` → `Inspector`. L'inspecteur affiche le cosinus et la distance 1 − cos ; mettre à l'échelle l'un des vecteurs (le multiplier par 10) montre que le cosinus ne bouge pas, contrairement à une distance euclidienne.

---

## 3.4 — Distances entre histogrammes : pondérer les cases

> *On s'étonne plus d'un écart sur un événement rare que sur un banal*

Un **histogramme** compte combien d'éléments tombent dans chaque case (par exemple, combien de pixels ont chaque teinte). Comparer des histogrammes — de couleur, de gradients, de mots — demande des mesures spécifiques. Soit deux histogrammes h et g, chacun normalisé pour que la somme de ses cases vaille 1 (ce sont alors des proportions).

### 3.4.1 — Distance du χ² : pondérer selon la rareté

#### L'intention
Comparer deux histogrammes en donnant plus d'importance aux variations survenant dans les cases rarement remplies. Un écart absolu de 0,05 n'a pas la même valeur sur une couleur dominante que sur une teinte rare.

#### La forme recherchée
On veut pondérer l'écart au carré de chaque case par l'inverse de son remplissage moyen. L'analogie est statistique : on s'étonne davantage d'une différence sur un événement rare (case presque vide) que sur un événement banal (case pleine). Pour relativiser l'écart, la forme utilise un rapport comparant la différence au carré à la somme des deux hauteurs de case, ce qui amortit le poids des cases très remplies (voir la forme `a/b`, annexe C).

#### La formule
```
d_χ²(h, g) = ½ Σᵢ (hᵢ − gᵢ)² / (hᵢ + gᵢ)
```
(χ² se lit « khi-deux ».) Ce n'est pas une vraie métrique (l'inégalité triangulaire peut échouer), mais elle est très efficace sur les histogrammes de couleur.

### 3.4.2 — Distance de Bhattacharyya : mesurer le recouvrement

#### L'intention
Mesurer à quel point deux distributions de probabilité ou deux histogrammes normalisés se recouvrent, c'est-à-dire la part d'information qu'ils partagent.

#### La forme recherchée
On cherche une forme qui vaut 1 si les deux histogrammes coïncident parfaitement, et 0 s'ils sont disjoints. L'idée est de remplacer chaque valeur de case par sa racine carrée. L'histogramme se transforme ainsi en un vecteur géométrique de longueur 1. Mesurer le recouvrement revient alors simplement à calculer le produit scalaire (la similarité cosinus, §3.3) de ces vecteurs-racines.

#### La formule
```
BC(h, g) = Σᵢ √(hᵢ · gᵢ)          (coefficient, ∈ [0, 1])
d_B(h, g) = −ln( BC(h, g) )
```

---

### 3.4.3 — Exemple chiffré

h = (0,5 ; 0,5 ; 0), g = (0 ; 0,5 ; 0,5) — deux histogrammes qui ne se recouvrent que sur une seule case :

```
χ²  = ½[ 0,5²/0,5 + 0 + 0,5²/0,5 ] = ½[0,5 + 0 + 0,5] = 0,5
BC  = √0 + √0,25 + √0 = 0,5   →   d_B = −ln(0,5) ≈ 0,693
```

### Limite — la sensibilité au découpage en cases

Toutes ces mesures comparent les cases **une à une**, sans savoir lesquelles sont voisines. Deux histogrammes décalés d'une seule case — une teinte à peine plus rouge — sont jugés totalement différents, alors qu'ils sont perceptuellement presque identiques. C'est la faiblesse de fond des distances case-à-case, que corrige la distance de transport de la section suivante.

### Paramètres opérationnels (VNStudio / Python)

Dans le nœud `Histogram Distance` (ou via `cv2.compareHist` en Python), le comportement de la comparaison est déterminé par les options suivantes :

*   **Type de comparaison (`method`)** :
    *   Dans VNStudio, ce paramètre correspond au menu déroulant **Comparison Method** ; en Python (OpenCV), il se nomme `method` dans la fonction `cv2.compareHist`.
    *   `cv2.HISTCMP_CHISQR` (Chi-Square) : Applique la formule du khi-deux. Utile pour comparer les histogrammes de teintes de couleur en donnant plus de poids aux teintes rares. La valeur est positive et vaut 0 en cas de ressemblance parfaite.
    *   `cv2.HISTCMP_BHATTACHARYYA` (ou `HISTCMP_HELLINGER`) : Mesure le recouvrement global. C'est la mesure la plus stable pour comparer des distributions de probabilité car elle est bornée entre 0 (identité parfaite) et 1 (vecteurs totalement disjoints).
    *   `cv2.HISTCMP_CORREL_CORRELATION` : Calcule le coefficient de corrélation linéaire. Il vaut 1 pour des histogrammes identiques, 0 pour des formes indépendantes et -1 en cas d'opposition complète.
*   **Normalisation préalable** :
    *   Il est indispensable que les deux histogrammes soient préalablement normalisés pour que la somme de leurs cases vaille 1,0 (via le paramètre de normalisation du nœud `Histogram`). Sans cela, comparer un petit patch d'image à une grande image donnerait des distances énormes basées uniquement sur la différence du nombre total de pixels.

### Dans VNStudio

Dans votre canvas :
`Image A` ──> `Histogram` ──┐
                          ├──> `Histogram Distance` ──> `Inspector`.
`Image B` ──> `Histogram` ──┘

Le nœud `Histogram Distance` compare les deux distributions normalisées. Il calcule en parallèle les métriques définies ci-dessus et permet à l'utilisateur de sélectionner dans l'inspecteur le type de comparaison adapté à son problème (Chi-Square pour les détails rares, Bhattacharyya pour la stabilité globale).

**Exercice de dépannage (échec contrôlé) :** L'exercice consiste à charger deux images identiques, à en décaler une d'un seul pixel, puis à mesurer leur distance Euclidienne L2 pixel à pixel via un nœud `Vector Distance`. Le lecteur constate dans l'inspecteur que la distance L2 saute immédiatement d'une valeur nulle à un score massif, alors que les images paraissent indiscernables à l'œil. Cela met en évidence la fragilité extrême des métriques de comparaison directe pixel par pixel par rapport au moindre décalage spatial.

---

## 3.5 — Distance de transport (Wasserstein / EMD) : le coût du déménagement

> *Combien de travail pour remodeler un tas de sable en un autre*

### L'intention

Les distances case-à-case (§3.4) ignorent la proximité des cases entre elles : un décalage d'une seule teinte les déclare maximalement différentes. On veut une mesure qui **connaisse la géométrie des cases** — où déplacer de la masse vers une case voisine coûte peu, vers une case lointaine coûte cher.

### La forme recherchée

L'image fondatrice est celle de **tas de sable** que l'on veut remodeler. Combien de travail pour transformer un tas en un autre, sachant qu'on paie distance × quantité déplacée ? La *Earth Mover's Distance* — la distance du « déplaceur de terre » — mesure ce **coût minimal de transport**. Deux histogrammes décalés d'une seule case ont une EMD petite (le coût d'un petit déplacement), là où la χ² les déclarait maximalement différents. L'EMD respecte la proximité perceptuelle que les mesures case-à-case ignorent.

### La formule — le cas 1-D, sans optimisation

En dimension 1 — comparer deux profils, par exemple deux histogrammes de niveaux de gris — l'EMD se calcule sans aucune optimisation, à partir des **cumuls** des deux histogrammes. Le cumul, en chaque case, est le total de tout ce qui précède (on additionne les cases de gauche à droite) :

```
EMD₁(h, g) = Σᵢ |H(i) − G(i)|     où H, G sont les cumuls de h, g
```

C'est l'aire entre les deux courbes cumulées, calculable d'un trait en parcourant les cases une fois. ∎

### Exemple chiffré (cas 1-D)

h = (0,5 ; 0,5 ; 0), g = (0 ; 0,5 ; 0,5), cases équidistantes :

```
cumul H = (0,5 ; 1,0 ; 1,0)
cumul G = (0,0 ; 0,5 ; 1,0)
EMD = |0,5−0| + |1,0−0,5| + |1,0−1,0| = 0,5 + 0,5 + 0 = 1,0
```

L'EMD vaut 1 case : il faut déplacer toute la masse d'un cran vers la droite. C'est une information d'« amplitude de déplacement » que la χ² (= 0,5, sans unité) ne donnait pas. On la retrouve dans la comparaison de couleurs perceptuellement correcte, l'évaluation de modèles génératifs (la distance de Wasserstein fonde les WGAN), le transfert de couleur, la comparaison de nuages de points 3-D.

### Limite — le coût de calcul au-delà de 1-D

Le cas général (2-D et au-delà) n'a pas de formule simple : il faut résoudre un vrai problème de transport optimal, coûteux quand les cases sont nombreuses. On recourt alors à des approximations rapides, au prix d'un léger lissage. On se limite ici au cas 1-D, qui couvre déjà la comparaison de profils.

### Dans VNStudio

Canvas : `Histogram A` + `Histogram B` → `Wasserstein 1D` → `Inspector`. Le nœud affiche l'EMD en nombre de cases, et superpose les deux courbes cumulées dont l'aire entre elles *est* la distance — ce qui donne à voir directement le « déplacement » à effectuer.

---

## 3.6 — Distance de Hausdorff : le pire écart de frontière

> *La pire excursion d'un point hors de l'autre ensemble*

### L'intention

On compare deux **ensembles** de points — typiquement deux contours — et on veut chiffrer non pas leur recouvrement moyen, mais leur **pire désaccord** : à quel point un contour peut-il s'éloigner de l'autre, dans le cas le plus défavorable ?

### La forme recherchée

On construit la mesure de l'intérieur. Pour un point a du premier ensemble, sa distance à l'ensemble B est la distance à son **plus proche voisin** dans B. On retient ensuite le pire cas : le point de A le plus mal loti, le plus éloigné de tout B. Cette « distance dirigée » répond à : « quelle est la pire excursion d'un point de A hors de B ? » Comme A peut être entièrement blotti contre B sans que l'inverse soit vrai, on prend le pire des deux sens.

### La formule

```
h(A, B) = max_{a∈A} ( min_{b∈B} d(a, b) )      (distance dirigée)
H(A, B) = max( h(A, B), h(B, A) )              (distance symétrique)
```

Le `min` cherche le plus proche voisin (la plus petite distance), le `max` retient le pire cas (la plus grande de ces distances). La distance symétrique prend le pire des deux sens. ∎

### Exemple chiffré

A = {(0,0), (1,0)}, B = {(0,0), (1,0), (6,0)} :

```
h(A, B) = 0   (chaque point de A est aussi dans B → distance nulle)
h(B, A) = 5   (le point isolé (6,0) de B a pour plus proche voisin dans A
               le point (1,0), à distance 5 — et non (0,0) à distance 6 !)
H(A, B) = max(0, 5) = 5
```

L'asymétrie est flagrante : A entièrement contenu dans B rend une direction nulle, tandis que le point isolé de B fait exploser l'autre. La distance se mesure au **plus proche** voisin (ici (1,0)), pas à un point quelconque de A — confondre les deux est l'erreur de calcul classique.

### Sensibilité — un seul point aberrant suffit

Le « pire cas » rend la Hausdorff extrêmement sensible à un point aberrant : un unique pixel de bruit dans un contour peut doubler la distance. La parade standard remplace le maximum par un quantile élevé (le 95ᵉ percentile, noté HD95 : on ignore les 5 % de points les plus mal lotis) ou par une moyenne. En segmentation médicale, on rapporte presque toujours la HD95 plutôt que la Hausdorff brute. Elle complète l'IoU (chapitre 4) : l'IoU mesure le recouvrement global de surface, la Hausdorff mesure la pire erreur de frontière. Deux segmentations peuvent avoir le même IoU mais des Hausdorff très différentes si l'une a une excroissance lointaine.

### Dans VNStudio

Canvas : `Contour A` + `Contour B` → `Hausdorff Distance` → `Inspector`. Le nœud affiche la distance symétrique, les deux distances dirigées, et trace le segment du « pire » point à son plus proche voisin, ce qui localise immédiatement le désaccord maximal.

---

## Tableau récapitulatif — choisir sa mesure

| Mesure | Compare | Vraie métrique ? | Hypothèse clé / usage type |
|---|---|---|---|
| Euclidienne (L2) | vecteurs | oui | dimensions comparables et indépendantes |
| Manhattan (L1) | vecteurs | oui | favorise la parcimonie ; robuste aux aberrations |
| Tchebychev (L∞) | vecteurs | oui | seule la pire coordonnée compte |
| Mahalanobis | vecteurs + covariance | oui | dimensions corrélées, d'échelles différentes |
| Cosinus | vecteurs | non (1−cos) | la direction compte, pas la longueur (embeddings, texte) |
| χ² | histogrammes | non | les cases rares pèsent plus (couleur) |
| Bhattacharyya | histogrammes | non | cosinus dans l'espace des racines ; recouvrement |
| Wasserstein / EMD | distributions | oui | la géométrie des cases compte (couleur perceptuelle, GAN) |
| Hausdorff | ensembles / contours | oui | pire écart de frontière (forme, segmentation) |

---

## Encadré final — chaque mesure cache une hypothèse

Le fil du chapitre se déroule d'une mesure à l'autre :

```
euclidienne   → toutes les directions se valent
Mahalanobis   → certaines directions sont plus « surprenantes » que d'autres
cosinus       → l'orientation compte, l'amplitude non
χ²            → les événements rares pèsent plus
Wasserstein   → la proximité des catégories entre elles compte
Hausdorff     → seul le pire cas compte
```

Il n'existe pas de distance universellement meilleure. L'EMD, qui connaît la géométrie des teintes, excelle sur des histogrammes de couleur et se révèle inadaptée à des embeddings de haute dimension, où règne le cosinus ; et inversement. La question utile n'est pas « quelle est la meilleure distance ? » mais « qu'est-ce que je veux considérer comme proche ? », et la réponse dicte la mesure.

Un descripteur (chapitre 1) garde une chose et en jette une autre ; un moment (chapitre 2) paie chaque détail supplémentaire en fragilité ; une distance déclare ce qui mérite d'être appelé proche. Le chapitre 4 prolongera la question sur les métriques de segmentation, où l'on verra qu'aucune mesure unique ne capture à elle seule la qualité d'un résultat.

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch3_couverture` | chapeau | Illustration : personnage face à plusieurs règles graduées différemment, verdicts divergents | JPG/PNG |
| `fig_ch3_01_boules_unite` | 3.1 | Les trois boules unité superposées : losange (L1), cercle (L2), carré (L∞) | SVG |
| `fig_ch3_02_mahalanobis` | 3.2 | Nuage étiré + ellipses d'égale distance ; deux points équidistants en euclidien, très inégaux en Mahalanobis | SVG |
| `fig_ch3_03_cosinus` | 3.3 | Deux vecteurs de longueurs très différentes, même direction → cos = 1 | SVG |
| `fig_ch3_04_case_a_case` | 3.4 / 3.5 | Deux histogrammes décalés d'une case : χ² maximal vs EMD minimale | SVG |
| `fig_ch3_05_hausdorff` | 3.6 | Deux contours, flèche vers le point le plus mal loti, asymétrie des deux sens | SVG |
