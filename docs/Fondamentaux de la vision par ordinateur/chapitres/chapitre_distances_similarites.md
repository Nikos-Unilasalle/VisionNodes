# Chapitre — Distances et similarités : dérivations et exemples

Comparer deux objets — deux descripteurs de forme du chapitre 1, deux histogrammes de couleur, deux distributions — suppose une mesure de leur écart. Mais il n'existe pas une « distance » universelle : il en existe une famille entière, et chacune voit les données à sa façon. Choisir l'une plutôt qu'une autre n'est jamais un détail technique, car ce choix décide de ce que « proche » veut dire. Ce chapitre passe en revue les distances usuelles, de la plus simple (euclidienne) aux plus structurées (Mahalanobis, Wasserstein), avec à chaque fois la même question : *qu'est-ce que je déclare important en la choisissant ?*

Le fil conducteur tient en une phrase : **choisir une distance, c'est déclarer ce qui compte.** Une mesure rend certains écarts négligeables et d'autres décisifs ; elle impose une géométrie aux données avant même qu'on les compare. Comprendre une distance, c'est donc connaître l'hypothèse qu'elle fait dans votre dos.

Un peu de vocabulaire. Une **distance** (ou métrique) est une mesure d'écart qui respecte quatre règles de bon sens : elle n'est jamais négative ; elle vaut zéro seulement quand les deux objets sont identiques ; elle est symétrique (l'écart de x à y égale celui de y à x) ; et elle vérifie l'**inégalité triangulaire** — un détour par un troisième point ne raccourcit jamais le trajet, d(x, z) ≤ d(x, y) + d(y, z). Une **similarité** mesure au contraire la ressemblance (grande quand les objets se ressemblent) et ne respecte pas forcément ces règles. Plusieurs « distances » courantes (χ², Bhattacharyya) ne sont d'ailleurs pas de vraies métriques — on le signalera, car cela a des conséquences pratiques.

Côté logiciel : chaque bloc de code se colle dans une node **« Python Script »**. Les deux objets à comparer arrivent dans les variables `a` et `b` (des vecteurs, des histogrammes ou des ensembles de points, selon la mesure), et le résultat est renvoyé dans `out_a` — un dictionnaire qu'une node **Inspecteur** affiche. `np` (NumPy) et `cv2` (OpenCV) sont déjà disponibles ; `scipy` s'importe au besoin.

---

## 3.1 Distances de Minkowski (L_p)

### Définition
La famille L_p réunit sous une seule formule les distances les plus courantes :

```
d_p(x, y) = ( Σᵢ |xᵢ − yᵢ|^p )^(1/p)
```

- p = 1 : distance de Manhattan (L1, *city-block*)
- p = 2 : distance euclidienne (L2), la distance « à vol d'oiseau »
- p → ∞ : distance de Tchebychev (L∞)

### L'idée

Le paramètre p règle la façon dont on agrège les écarts coordonnée par coordonnée. Avec p = 1, on additionne simplement les écarts, comme un taxi qui parcourt des rues en damier (d'où le nom *Manhattan*). Avec p = 2, on prend la diagonale directe. Et plus p grandit, plus la formule ne retient que le plus grand écart : élever à une grande puissance écrase les petites différences devant la plus grande, jusqu'à ce qu'à la limite, **seule la coordonnée où l'écart est maximal compte encore**. C'est pourquoi L∞ se réduit au simple maximum des écarts, sans qu'il soit besoin de dérouler le calcul.

### Géométrie : la forme de la « boule unité »

La meilleure intuition est de dessiner l'ensemble des points situés à distance 1 de l'origine — la « boule unité » de chaque distance :

```
L1   : losange (carré tourné de 45°)
L2   : cercle
L∞   : carré aligné sur les axes
```

Plus p augmente, plus cette boule gonfle, du losange vers le carré. Cette image n'est pas qu'esthétique : les coins du losange L1 sont posés sur les axes, là où certaines coordonnées sont nulles. Une distance L1 « préfère » donc les solutions à coordonnées nulles — c'est la raison géométrique pour laquelle la régularisation Lasso, bâtie sur L1, produit des modèles parcimonieux.

### Exemple numérique

x = (1, 2, 3), y = (4, 0, 3) → écarts (3, 2, 0) :

```
L1  = 3 + 2 + 0      = 5
L2  = √(9 + 4 + 0)   = √13 ≈ 3,61
L∞  = max(3, 2, 0)   = 3
```

On retrouve toujours l'ordre L∞ ≤ L2 ≤ L1 : plus p est grand, plus la distance est petite, car on agrège les écarts de façon de plus en plus « indulgente ».

### Piège : la malédiction de la dimension

En haute dimension, les distances euclidiennes se **concentrent** : le point le plus proche et le plus lointain finissent par être presque à la même distance, et la notion de voisinage perd son sens. Concrètement, sur des descripteurs à plusieurs centaines de composantes, un « plus proche voisin » n'est plus vraiment plus proche que les autres. Deux parades : réduire d'abord la dimension (par exemple par ACP) avant de mesurer, ou employer des distances fractionnaires (p < 1) qui résistent mieux — au prix de l'inégalité triangulaire, qu'elles ne respectent plus.

### Code
```python
# a, b : deux vecteurs (listes ou tableaux) de même longueur.
x = np.asarray(a, dtype=float).ravel()
y = np.asarray(b, dtype=float).ravel()
d = np.abs(x - y)
out_a = {
    "L1 (Manhattan)":   float(d.sum()),
    "L2 (euclidienne)": float(np.linalg.norm(d)),
    "Linf (Tchebychev)": float(d.max()),
}
```

---

## 3.2 Distance de Mahalanobis

### Définition
```
d(x, y) = √( (x − y)ᵀ Σ⁻¹ (x − y) )
```
où Σ est la matrice de covariance des données — un tableau qui résume comment les dimensions varient et se corrèlent entre elles.

### L'idée

La distance euclidienne fait une hypothèse cachée : que toutes les directions se valent et que les dimensions sont indépendantes. C'est rarement vrai. Si vos données s'étirent beaucoup en largeur et peu en hauteur, un écart horizontal et un écart vertical de même longueur n'ont pas du tout la même signification.

L'analogie la plus juste est celle d'un écart « relatif à la normale du coin ». Un mètre d'écart est banal le long d'une autoroute, où les positions varient déjà beaucoup ; le même mètre est considérable en travers d'un couloir étroit, où tout le monde se tient sur une ligne. La Mahalanobis mesure l'écart non pas en mètres absolus, mais en **nombre de « variations typiques » propres à chaque direction**.

Techniquement, elle **redresse l'espace** : elle étire les directions où les données varient peu, comprime celles où elles varient beaucoup, et défait leurs corrélations, jusqu'à ce que le nuage de points devienne une boule bien ronde. Dans cet espace redressé, on mesure alors une simple distance euclidienne. Inutile de savoir comment se calcule ce redressement — il se lit dans la matrice de covariance ; il suffit de retenir l'effet : **la Mahalanobis est la distance euclidienne, mais mesurée après avoir rendu le nuage de données parfaitement isotrope.** Ses surfaces d'iso-distance ne sont plus des cercles, mais des ellipses épousant la forme du nuage.

### Exemple numérique

Prenons des données très étirées horizontalement, dix fois plus dispersées en x qu'en y (covariance Σ = diag(100, 1)). Comparons, depuis le centre, deux points pourtant à la même distance euclidienne : a = (10, 0) et b = (0, 10).

```
d_eucl(a) = d_eucl(b) = 10        (identiques pour l'euclidienne)

d_Mahal(a) = √(10² / 100) = 1     (10 dans une direction très dispersée : banal)
d_Mahal(b) = √(10² / 1)   = 10    (10 dans une direction peu dispersée : rare)
```

Pour la Mahalanobis, a est dix fois plus proche que b. Un écart de 10 dans la direction de forte variabilité est ordinaire ; le même écart dans la direction de faible variabilité est exceptionnel. C'est exactement le raisonnement de la détection d'anomalies.

### Applications

Détection d'outliers (un point au-delà de d_Mahal ≈ 3 est statistiquement suspect), classification gaussienne (comparer un point aux centres des classes revient à comparer des distances de Mahalanobis), et suivi par filtre de Kalman, où elle valide l'association entre une mesure et une prédiction.

### Piège : Σ singulière ou mal estimée

Si le nombre d'échantillons est inférieur au nombre de dimensions, la covariance Σ n'est pas inversible — et la formule explose. Parades : ajouter un petit terme à la diagonale (Σ + εI, dit *shrinkage*), utiliser une pseudo-inverse, ou un estimateur robuste (Ledoit-Wolf). La règle : ne jamais inverser une covariance estimée sur trop peu de points sans la régulariser.

### Code
```python
# a : le nuage de données (n points × d dimensions, pour estimer Σ).
# b : le point à tester. Renvoie sa distance de Mahalanobis au centre du nuage.
from scipy.spatial.distance import mahalanobis

data = np.asarray(a, dtype=float)
x    = np.asarray(b, dtype=float).ravel()
mu   = data.mean(axis=0)
cov  = np.cov(data.T)
VI   = np.linalg.inv(cov + 1e-9 * np.eye(cov.shape[0]))   # +εI : régularisation

dm = float(mahalanobis(x, mu, VI))
out_a = {
    "mahalanobis":   dm,
    "euclidienne":   float(np.linalg.norm(x - mu)),
    "anomalie (>3)": bool(dm > 3),
}
```

---

## 3.3 Similarité cosinus

### Définition
```
cos(θ) = (x · y) / (‖x‖ · ‖y‖) ∈ [−1, 1]
```
On en tire une distance : d = 1 − cos(θ).

### L'idée

La similarité cosinus est le cosinus de l'angle entre les deux vecteurs. Elle découle directement de la définition du produit scalaire, et son trait essentiel est qu'elle **ignore les longueurs pour ne regarder que les directions**. Deux vecteurs qui pointent dans le même sens ont une similarité de 1, qu'ils soient longs ou courts ; deux vecteurs perpendiculaires ont une similarité de 0.

### Quand la préférer à l'euclidienne

Chaque fois que le **profil** importe plus que l'**intensité**. L'exemple canonique est la comparaison de textes représentés par leurs fréquences de mots : un long article et son résumé partagent le même thème (même direction) mais ont des longueurs très différentes. L'euclidienne les déclarerait éloignés à cause de l'écart de taille ; le cosinus les reconnaît proches. C'est pourquoi la recherche documentaire, les systèmes de recommandation et la comparaison d'*embeddings* (de mots, d'images, de phrases) reposent presque toujours sur le cosinus.

### Lien avec l'euclidienne sur vecteurs normalisés

Il existe un pont utile entre les deux. Si l'on ramène d'abord les vecteurs à une longueur de 1 (normalisation), alors la distance euclidienne et la distance cosinus deviennent deux façons de dire la même chose :

```
d_eucl²(x, y) = 2 · (1 − cos θ)        (quand ‖x‖ = ‖y‖ = 1)
```

Sur des vecteurs normalisés, l'une croît exactement avec l'autre. D'où une habitude répandue : on normalise les embeddings avant de les indexer, ce qui permet d'utiliser un moteur de recherche euclidien rapide tout en raisonnant, au fond, en cosinus.

### Exemple numérique

x = (2, 0), y = (3, 0) : colinéaires → cos = 6 / (2·3) = 1, similarité maximale malgré des longueurs différentes. x = (1, 0), y = (0, 1) : perpendiculaires → cos = 0.

### Code
```python
# a, b : deux vecteurs (descripteurs, embeddings…).
x = np.asarray(a, dtype=float).ravel()
y = np.asarray(b, dtype=float).ravel()
na, nb = np.linalg.norm(x), np.linalg.norm(y)
cos = float(np.dot(x, y) / (na * nb)) if na and nb else 0.0
out_a = {"cosinus": cos, "distance (1-cos)": 1.0 - cos}
```

---

## 3.4 Distances entre histogrammes

Comparer des distributions discrètes — histogrammes de couleur, de gradients, sacs de mots — demande des mesures spécifiques. Soit deux histogrammes normalisés h et g (chacun de somme 1).

### Distance du χ²
```
d_χ²(h, g) = ½ Σᵢ (hᵢ − gᵢ)² / (hᵢ + gᵢ)
```

L'idée du dénominateur (hᵢ + gᵢ) est de **pondérer chaque case par son importance**. Un écart absolu de 0,05 est négligeable sur une case bien remplie (à 0,5), mais énorme sur une case presque vide (à 0,01). La χ² traite donc les cases rares comme plus discriminantes — un peu comme on s'étonne davantage d'une différence sur un événement rare que sur un événement banal. Ce n'est **pas une vraie métrique** (l'inégalité triangulaire peut échouer), mais elle est redoutablement efficace sur les histogrammes de couleur.

### Distance de Bhattacharyya
```
BC(h, g) = Σᵢ √(hᵢ · gᵢ)          (coefficient, ∈ [0, 1])
d_B(h, g) = −ln( BC(h, g) )
```

Le coefficient BC a une lecture géométrique élégante. Si l'on remplace chaque case par sa racine carrée (√hᵢ), l'histogramme devient un vecteur de longueur 1, et BC n'est alors rien d'autre que **la similarité cosinus de ces vecteurs-racines** : on retrouve la mesure de la section 3.3, transportée dans « l'espace des racines ». Cette parenté explique sa robustesse. Une variante, la distance de Hellinger √(1 − BC), est, elle, une vraie métrique.

### Exemple numérique

h = (0,5 ; 0,5 ; 0), g = (0 ; 0,5 ; 0,5) — deux histogrammes qui ne se recouvrent que sur une seule case :

```
χ²  = ½[ 0,5²/0,5 + 0 + 0,5²/0,5 ] = ½[0,5 + 0 + 0,5] = 0,5
BC  = √0 + √0,25 + √0 = 0,5   →   d_B = −ln(0,5) ≈ 0,693
```

### Piège : sensibilité au découpage en cases

Toutes ces mesures comparent les cases **une à une**. Deux histogrammes décalés d'une seule case — une teinte à peine plus rouge — sont jugés totalement différents, alors qu'ils sont perceptuellement presque identiques. C'est la faiblesse de fond des distances case-à-case, que corrige la distance de transport de la section suivante.

### Piège de bibliothèque : `cv2.compareHist` ne calcule pas ces formules

OpenCV propose `cv2.compareHist`, mais ses conventions ne coïncident pas avec les définitions ci-dessus, ce qui est une source d'erreurs classique :
- `HISTCMP_CHISQR` calcule la χ² **asymétrique** Σ(hᵢ−gᵢ)²/hᵢ, et `HISTCMP_CHISQR_ALT` vaut 2·Σ(hᵢ−gᵢ)²/(hᵢ+gᵢ) — soit **quatre fois** la formule du livre (sur notre exemple, elle renvoie 2,0 et non 0,5).
- `HISTCMP_BHATTACHARYYA` renvoie en réalité la distance de **Hellinger** √(1 − BC) (ici 0,707), et non −ln(BC).

Le code ci-dessous calcule donc les formules à la main, ce qui lève toute ambiguïté.

### Code
```python
# a, b : deux histogrammes (mêmes cases).
h = np.asarray(a, dtype=float).ravel()
g = np.asarray(b, dtype=float).ravel()
h, g = h / h.sum(), g / g.sum()              # normaliser (somme = 1)
eps = 1e-12

chi2 = 0.5 * np.sum((h - g) ** 2 / (h + g + eps))
bc   = np.sum(np.sqrt(h * g))                # coefficient de Bhattacharyya
out_a = {
    "chi2":                    float(chi2),
    "BC (Bhattacharyya)":      float(bc),
    "d_B (-ln BC)":            float(-np.log(bc + eps)),
    "Hellinger sqrt(1-BC)":    float(np.sqrt(max(0.0, 1.0 - bc))),
}
```

---

## 3.5 Distance de transport (Wasserstein / EMD)

### Définition

La *Earth Mover's Distance* (distance du « déplaceur de terre ») mesure le **coût minimal pour transformer une distribution en une autre** en déplaçant de la masse, sachant qu'on paie distance × quantité déplacée. Formellement, on cherche le plan de transport le moins coûteux ; le détail de l'optimisation importe moins que l'idée.

### L'idée fondatrice

Contrairement aux distances case-à-case, l'EMD **connaît la géométrie des cases** : déplacer de la masse vers une case voisine coûte peu, vers une case lointaine coûte cher. L'image est celle de tas de sable que l'on veut remodeler : combien de travail pour transformer un tas en un autre ? Deux histogrammes décalés d'une seule case ont une EMD petite (le coût d'un petit déplacement), là où la χ² les déclarait maximalement différents. L'EMD respecte donc la proximité perceptuelle que les mesures case-à-case ignorent.

### Cas 1-D : une formule simple

En dimension 1 — comparer deux profils, par exemple deux histogrammes de niveaux de gris — l'EMD se calcule sans aucune optimisation, à partir des **fonctions de répartition cumulées** (on additionne les cases de gauche à droite) :

```
EMD₁(h, g) = Σᵢ |H(i) − G(i)|     où H, G sont les cumuls de h, g
```

C'est l'aire entre les deux courbes cumulées — calculable d'un trait, en parcourant les cases une fois.

### Exemple numérique (cas 1-D)

h = (0,5 ; 0,5 ; 0), g = (0 ; 0,5 ; 0,5), cases équidistantes :

```
cumul H = (0,5 ; 1,0 ; 1,0)
cumul G = (0,0 ; 0,5 ; 1,0)
EMD = |0,5−0| + |1,0−0,5| + |1,0−1,0| = 0,5 + 0,5 + 0 = 1,0
```

L'EMD vaut 1 case : il faut déplacer toute la masse d'exactement un cran vers la droite. C'est une information d'« amplitude de déplacement » que la χ² (= 0,5, sans unité) ne donnait pas.

### Applications

Comparaison de couleurs perceptuellement correcte (recherche d'images par le contenu), évaluation de modèles génératifs (la distance de Wasserstein entre distribution réelle et générée fonde les WGAN), transfert de couleur entre images, comparaison de nuages de points 3-D.

### Piège : coût de calcul

Le cas général (2-D et au-delà) n'a pas de formule simple : il faut résoudre un vrai problème de transport optimal, coûteux quand les cases sont nombreuses. On recourt alors à l'approximation de Sinkhorn, rapide et parallélisable, au prix d'un léger lissage. À noter : la bibliothèque spécialisée POT (`import ot`) n'est **pas fournie** dans le moteur VNStudio ; pour rester autonome, on se limite ici au cas 1-D, qui couvre déjà la comparaison de profils.

### Code
```python
# a, b : deux histogrammes 1-D (mêmes cases équidistantes).
h = np.asarray(a, dtype=float).ravel()
g = np.asarray(b, dtype=float).ravel()
h, g = h / h.sum(), g / g.sum()

# EMD 1-D = aire entre les deux cumuls (aucune optimisation nécessaire).
emd = float(np.sum(np.abs(np.cumsum(h) - np.cumsum(g))))
out_a = {"wasserstein_1d (en cases)": emd}

# Équivalent via scipy (positions = indices de cases, poids = hauteurs) :
# from scipy.stats import wasserstein_distance
# emd = wasserstein_distance(np.arange(len(h)), np.arange(len(g)), h, g)
```

---

## 3.6 Distance de Hausdorff

### Définition

C'est une distance entre deux **ensembles** de points A et B — typiquement deux contours :

```
h(A, B) = max_{a∈A} ( min_{b∈B} d(a, b) )      (distance dirigée)
H(A, B) = max( h(A, B), h(B, A) )              (distance symétrique)
```

### L'idée

Décortiquons la formule de l'intérieur. Pour un point a de A, `min_{b∈B} d(a, b)` est sa distance à l'ensemble B, c'est-à-dire la distance à son **plus proche voisin** dans B. Puis `max_{a∈A}` retient le pire cas : le point de A le plus mal loti, le plus éloigné de tout B. La distance dirigée h(A, B) répond donc à : « quelle est la pire excursion d'un point de A hors de B ? »

On a besoin des deux directions car la mesure n'est pas symétrique : A peut être entièrement blotti contre B sans que l'inverse soit vrai. La Hausdorff symétrique prend le pire des deux sens.

### Exemple numérique

A = {(0,0), (1,0)}, B = {(0,0), (1,0), (6,0)} :

```
h(A, B) = 0   (chaque point de A est aussi dans B → distance nulle)
h(B, A) = 5   (le point isolé (6,0) de B a pour plus proche voisin dans A
               le point (1,0), à distance 5 — et non (0,0) à distance 6 !)
H(A, B) = max(0, 5) = 5
```

L'asymétrie est flagrante : A ⊂ B rend une direction nulle, tandis que le point isolé de B fait exploser l'autre. Notez bien le point délicat : la distance se mesure au **plus proche** voisin (ici (1,0)), pas à un point arbitraire de A — confondre les deux est l'erreur de calcul classique sur la Hausdorff.

### Piège : sensibilité aux valeurs aberrantes

Le « pire cas » rend la Hausdorff extrêmement sensible à un seul point aberrant : un unique pixel de bruit dans un contour peut doubler la distance. La parade standard est de remplacer le maximum par un quantile élevé (le 95ᵉ percentile, noté HD95) ou par une moyenne des distances. En segmentation médicale, on rapporte presque toujours la HD95 plutôt que la Hausdorff brute, précisément pour cette raison.

### Applications

Comparaison de contours et de formes, et surtout évaluation de segmentation, où elle complète l'IoU : l'IoU mesure le recouvrement global de surface, la Hausdorff mesure la **pire erreur de frontière**. Deux segmentations peuvent avoir le même IoU mais des Hausdorff très différentes si l'une a une excroissance lointaine.

### Code
```python
# a, b : deux ensembles de points (par ex. deux contours), forme (N, 2).
from scipy.spatial.distance import directed_hausdorff

A = np.asarray(a, dtype=float).reshape(-1, 2)
B = np.asarray(b, dtype=float).reshape(-1, 2)
hab = directed_hausdorff(A, B)[0]
hba = directed_hausdorff(B, A)[0]
out_a = {
    "hausdorff":      float(max(hab, hba)),
    "dirigee A->B":   float(hab),
    "dirigee B->A":   float(hba),
}
```

---

## Tableau récapitulatif — choisir sa mesure

| Mesure | Compare | Vraie métrique ? | Hypothèse clé / usage type |
|---|---|---|---|
| Euclidienne (L2) | vecteurs | oui | dimensions comparables et décorrélées |
| Manhattan (L1) | vecteurs | oui | favorise la parcimonie ; robuste aux outliers |
| Tchebychev (L∞) | vecteurs | oui | seule la pire coordonnée compte |
| Mahalanobis | vecteurs + Σ | oui | dimensions corrélées, d'échelles différentes |
| Cosinus | vecteurs | non (1−cos) | la direction compte, pas la longueur (embeddings, texte) |
| χ² | histogrammes | non | les cases rares pèsent plus (couleur) |
| Bhattacharyya | histogrammes | non | cosinus dans l'espace des racines ; recouvrement |
| Wasserstein / EMD | distributions | oui | la géométrie des cases compte (couleur perceptuelle, GAN) |
| Hausdorff | ensembles / contours | oui | pire écart de frontière (forme, segmentation) |

---

## Encadré — la mesure encode une hypothèse

Le fil conducteur du chapitre, déroulé d'une mesure à l'autre :

```
euclidienne   → toutes les directions se valent
Mahalanobis   → certaines directions sont plus « surprenantes » que d'autres
cosinus       → l'orientation compte, l'amplitude non
χ²            → les événements rares pèsent plus
Wasserstein   → la proximité des catégories entre elles compte
Hausdorff     → seul le pire cas compte
```

Il n'existe pas de distance universellement meilleure. Une mesure excellente sur des histogrammes de couleur (l'EMD, qui connaît la géométrie des teintes) est inadaptée à des embeddings de haute dimension (où règne le cosinus), et inversement. La première question n'est jamais « quelle est la meilleure distance ? », mais « **qu'est-ce que je veux considérer comme proche ?** » — et la réponse dicte la mesure.

C'est la même leçon que celle des chapitres précédents, vue sous un autre angle. Un descripteur (chapitre 1) choisit ce qu'il voit et ce qu'il oublie ; un moment (chapitre 2) paie chaque détail supplémentaire en fragilité ; une distance, ici, déclare ce qui mérite d'être appelé « proche ». À chaque fois, le bon outil n'est pas le plus puissant dans l'absolu, mais celui dont les hypothèses épousent le problème — un fil que l'on retrouvera au chapitre suivant, sur les métriques de segmentation, où l'on verra qu'aucune mesure unique ne capture à elle seule la qualité d'un résultat.
