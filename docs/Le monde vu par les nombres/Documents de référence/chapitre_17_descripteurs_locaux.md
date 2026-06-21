# Chapitre — Descripteurs locaux et appariement : dérivations et exemples

Deux photographies d'une même façade, prises de deux endroits, à deux heures. Un même angle de fenêtre y figure deux fois — mais pas avec les mêmes pixels : l'échelle a changé, l'appareil a tourné, le soleil a baissé. Reconnaître que ces deux taches de pixels désignent le même point du monde est le problème central de la mise en correspondance, et il est à la racine du panorama, de la reconstruction 3D, du SLAM et du suivi. Ce chapitre construit la chaîne complète qui le résout : **détecter** des points stables, les **décrire** par un vecteur, **apparier** ces vecteurs entre deux images, puis **filtrer** les erreurs par un modèle géométrique robuste.

**Fil conducteur du chapitre.** Un descripteur est l'invariance qu'on s'autorise. Il jette délibérément ce qui change d'une vue à l'autre — la position, la taille, l'orientation, le gain de lumière — pour ne retenir que ce qui identifie le point. Sa qualité ne se mesure pas à ce qu'il enregistre, mais à ce qu'il sait ignorer sans perdre le pouvoir de distinguer.

**Liens avec les chapitres précédents.** La détection s'appuie sur les coins de Harris et Shi-Tomasi (§6.5–6.6) et sur la différence de gaussiennes (§5.3), restée jusqu'ici annoncée comme « base de SIFT » sans être dépliée. L'appariement se mesure avec les distances du chapitre 3 — euclidienne pour les descripteurs réels, Hamming pour les binaires, cosinus pour les embeddings. Le filtrage final renvoie à RANSAC (§16.1) et à l'homographie (§8.3). Et le fil rejoint celui du chapitre 1 : décrire une forme, ou décrire un point-clé, c'est dans les deux cas garder une chose en en jetant une autre.

---

## 17.1 Le problème de l'appariement

### Définition

Apparier, c'est, pour chaque point-clé `p` de l'image A décrit par un vecteur `f(p)`, trouver dans l'image B le point `q` dont le descripteur `g(q)` est le plus proche :

```
match(p) = argmin_q  d( f(p), g(q) )
```

Tout le travail consiste à construire `f` et `g` pour que cette distance soit petite entre vrais homologues et grande partout ailleurs, **malgré** les transformations qui séparent A et B.

### Justification — pourquoi les pixels bruts ne suffisent pas

Le candidat naïf prend pour descripteur le patch de pixels lui-même et pour distance la somme des carrés des écarts (SSD). Il échoue dès la première transformation. Un patch et sa copie tournée de 30°, agrandie de 20 %, ou simplement éclaircie d'un gain `1,3`, produisent un SSD énorme alors que c'est le même point. Le descripteur doit donc être **invariant** à un ensemble explicite de transformations. Le cahier des charges classique :

```
translation : acquise en extrayant f autour de points-clés (pas sur une grille fixe)
échelle     : §17.2 (échelle caractéristique)
rotation    : §17.4 (orientation dominante), §17.5 (BRIEF orienté)
éclairage   : gradients (tuent l'offset) + normalisation (tue le gain) — §17.3
```

### Ce que ça mesure / l'angle mort

On n'obtient jamais l'invariance gratuitement. Chaque invariance ajoutée rend le descripteur aveugle à une dimension du signal, donc moins discriminant : un descripteur invariant en rotation ne peut plus distinguer un motif de sa version tournée, même quand cette distinction serait utile. Les descripteurs classiques visent l'invariance **similitude** (translation + rotation + échelle) plus une robustesse photométrique. Ils ne couvrent ni le changement de point de vue **affine ou perspectif** marqué, ni les déformations non rigides : c'est le domaine des variantes affines (ASIFT) et, aujourd'hui, des méthodes apprises (§17.8).

### Exemple numérique

Un patch `P` et le même patch éclairci d'un gain `1,3` puis assombri d'un offset `−10`. Le SSD pixel à pixel mesure une différence massive là où il ne devrait rien voir : un patch de valeur moyenne 100 donne, après `1,3·P − 10`, un écart moyen de `0,3·100 − 10 = 20` par pixel, soit un SSD de `20² = 400` par pixel, des milliers sur le patch entier. Or c'est le même point, sous une autre lumière. Le gradient, lui, est insensible à l'offset (`∇(I−10) = ∇I`) et ne garde du gain qu'un facteur global que la normalisation efface.

### Piège d'implémentation

Normaliser le patch brut (centrer-réduire ses intensités) corrige le gain et l'offset, mais **pas** la rotation ni l'échelle, qui sont les transformations dominantes en pratique. C'est le piège du débutant : un patch centré-réduit reste un mauvais descripteur. L'invariance géométrique se gagne par la construction du descripteur (orientation, échelle), pas par un post-traitement des valeurs.

### Schéma de nœuds

```
[Patch P] ──[gain 1,3 ; offset −10]──> [SSD] ⟹ grand (faux négatif)
[Patch P] ──[∇ (gradient)]──> [magnitude]  insensible à l'offset
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.1.*

---

## 17.2 Échelle caractéristique (espace d'échelle)

### Définition

Pour qu'un descripteur soit invariant en échelle, il faut d'abord décider **à quelle taille** observer un point-clé. On cherche cette taille dans l'espace d'échelle : on convolue l'image par des gaussiennes de `σ` croissants et on repère les extrema du **laplacien de gaussienne normalisé** dans le volume `(x, y, σ)` :

```
réponse(x,y,σ) = σ² · ∇²[G_σ * I](x,y)         (LoG normalisé en échelle)
DoG(x,y,σ)     = (G_{kσ} − G_σ) * I  ≈  (k−1)σ² · ∇²G_σ * I   (approximation rapide, §5.3)
```

Un extremum en `(x₀, y₀, σ₀)` donne la position du blob **et** son échelle caractéristique `σ₀`.

### Dérivation — pourquoi le facteur `σ²`

Sans normalisation, la réponse du LoG à une structure décroît mécaniquement quand `σ` augmente : l'amplitude de `∇²G_σ` est en `1/σ²`. Une recherche d'extremum sur `σ` ne trouverait alors jamais de maximum, la réponse chutant monotonement. Multiplier par `σ²` compense exactement cette décroissance et fait apparaître un vrai pic. Pour un blob gaussien d'écart-type `s`, ce pic tombe à `σ₀ = s` : l'opérateur « résonne » avec la structure quand son échelle égale celle du blob. ∎

### Ce que ça mesure / l'angle mort

Le détecteur se comporte comme un diapason : il vibre le plus fort quand son échelle propre coïncide avec la taille de la structure rencontrée, et reste presque sourd aux autres. L'extremum de LoG répond fort aux structures **isotropes** (blobs, coins arrondis). Il répond aussi, à tort, le long des **contours** rectilignes, où la courbure transverse crée une réponse parasite. SIFT élimine ces faux positifs par un test sur la matrice hessienne du DoG : on rejette les points dont le rapport des valeurs propres dépasse un seuil (typiquement `r = 10`, soit un rapport de courbures principales `> 10`), exactement comme le critère de Harris séparait coins et contours (§6.5).

### Exemple numérique (vérifié)

Un blob gaussien synthétique d'écart-type `s = 6` pixels. On balaie `σ` de 2 à 12 et on lit la réponse du LoG normalisé en son centre :

```
σ :  2 ... 4 ...  6  ... 8 ... 12
réponse normalisée croît, atteint son MAXIMUM à σ = 6.00, puis décroît
```

L'échelle caractéristique détectée vaut `σ₀ = 6,00`, soit exactement la taille du blob. Un descripteur extrait sur un voisinage proportionnel à `σ₀` sera donc le même que l'image soit grande ou petite : l'invariance d'échelle naît de cette mesure, pas d'un réglage manuel.

### Piège d'implémentation

Deux paramètres décident de tout : le **nombre d'octaves** (jusqu'où agrandir `σ`) et le **nombre d'échelles par octave**. Trop peu d'échelles par octave et l'extremum tombe entre deux niveaux échantillonnés, l'échelle est mal localisée. Par ailleurs, ne pas oublier l'élimination des réponses de contour : un détecteur de blobs nu (`skimage.feature.blob_log` sans seuil de courbure) renvoie quantité de points le long des arêtes, inutilisables pour l'appariement.

### Schéma de nœuds

```
[Image] ──> [Espace d'échelle : DoG sur σ croissants] ──> [Extrema (x,y,σ)]
        ──> [Test de courbure (rejet des contours)] ──> [Points-clés + échelle σ₀]
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.2.*

---

## 17.3 HOG — histogramme de gradients orientés

### Définition

Le descripteur HOG découpe une région en cellules, et résume chaque cellule par un **histogramme des orientations du gradient**, pondéré par la magnitude. Les histogrammes sont ensuite normalisés par blocs :

```
pour chaque pixel : magnitude ‖∇I‖ , orientation θ = arctan2(Iᵧ, Iₓ)  (non signée : θ mod 180°)
cellule  : histogramme à 9 bins de 20°, vote = magnitude
bloc     : concaténer les cellules voisines, normaliser en L2 (atténue les variations d'éclairage)
```

### Dérivation — d'où viennent les invariances

Deux gestes portent toute la robustesse. Travailler sur le **gradient** annule l'offset d'éclairage : ajouter une constante à l'image ne change pas `∇I`. **Normaliser** chaque bloc annule le gain : multiplier l'image par un facteur multiplie magnitudes et norme du bloc par le même facteur, qui se simplifie. La tolérance géométrique vient du **binning spatial** : un détail peut bouger de quelques pixels à l'intérieur d'une cellule sans changer l'histogramme, puisque seul compte le comptage agrégé. ∎

### Ce que ça mesure / l'angle mort

HOG décrit la **distribution locale des orientations de bord**. Son angle mort est frappant : il n'est **pas** invariant en rotation. Tourner l'image décale circulairement tous les histogrammes. C'est un choix assumé — HOG a été conçu pour la détection de piétons, où la posture est debout et l'orientation connue. Pour apparier des vues quelconques, il faut ajouter une étape d'orientation, ce que fait SIFT (§17.4).

### Exemple numérique (calculable à la main, vérifié)

Une cellule 8×8 traversée par un dégradé clair-sombre régulier en diagonale (intensité croissant vers le bas-droite, par pas de 10). Les différences centrées donnent en chaque pixel intérieur :

```
Iₓ = +10 , Iᵧ = +10   ⟹   ‖∇I‖ = √(10² + 10²) = 14,14   θ = arctan2(10,10) = 45°
```

Les 36 pixels intérieurs ont tous le même gradient. Le vote total `36 × 14,14 = 509,1` tombe entièrement dans le bin `[40°, 60°)` :

```
bin   [0,20) [20,40) [40,60) [60,80) ... [160,180)
vote     0      0     509,1     0    ...      0
```

L'orientation moyenne pondérée vaut `45,0°` : l'histogramme a localisé sans ambiguïté la direction du bord. Sur une vraie image, les votes se répartissent sur plusieurs bins voisins, ce qui mène droit au piège suivant.

### Piège d'implémentation

L'affectation **dure** au bin le plus proche (utilisée ci-dessus pour la clarté) crée des **aliasing** : un gradient à 39° et un à 41° tombent dans deux bins différents alors qu'ils sont quasi identiques. Les implémentations sérieuses font une **interpolation trilinéaire** (en orientation et en position) pour répartir chaque vote entre bins adjacents. Autre piège : orientations **non signées** (0–180°, un bord clair→sombre et sombre→clair comptent pareil) contre **signées** (0–360°). HOG standard est non signé ; s'en écarter change le descripteur. Enfin, linéariser l'image (§7.5) avant le calcul des gradients : un encodage gamma fausse les magnitudes.

### Schéma de nœuds

```
[Image] ──> [Gradient (mag, θ)] ──> [Histogrammes 9 bins par cellule 8×8]
        ──> [Normalisation par bloc 2×2 (L2)] ──> [Descripteur HOG]
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.3.*

---

## 17.4 SIFT — le descripteur de référence

### Définition

SIFT assemble les briques précédentes en un descripteur invariant en similitude et robuste à l'éclairage. À chaque point-clé détecté dans l'espace d'échelle (§17.2) :

```
1. orientation dominante : histogramme à 36 bins des orientations du gradient
   dans un voisinage proportionnel à σ ; le pic donne l'orientation de référence
2. descripteur : grille 4×4 de sous-régions, chacune résumée par un histogramme
   à 8 orientations  ⟹  4 × 4 × 8 = 128 composantes
3. normalisation : L2, puis clip des composantes > 0,2, puis re-normalisation L2
```

### Dérivation — comment chaque invariance est acquise

L'invariance d'**échelle** vient de l'extraction sur un voisinage proportionnel à `σ₀`, l'échelle caractéristique. L'invariance de **rotation** vient du référentiel tourné : on mesure toutes les orientations du descripteur **relativement** à l'orientation dominante, si bien qu'une rotation de l'image laisse le descripteur inchangé. Décrire un point dans son référentiel propre revient à décrire un bâtiment depuis sa façade : peu importe la rue par laquelle on est arrivé, la description ne change pas. L'invariance à l'**éclairage** vient de la normalisation (gain) et du gradient (offset). Le clip à `0,2` ajoute une robustesse aux éclairages **non linéaires** : un changement de lumière qui sature quelques gradients ne doit pas dominer le vecteur, donc on plafonne chaque composante avant de re-normaliser. ∎

### Ce que ça mesure / l'angle mort

SIFT capture la **structure locale des gradients dans un référentiel propre au point**. Ses limites : il suppose une transformation **similitude** locale, et se dégrade sous un fort changement de point de vue affine ou perspectif (la grille 4×4 ne suit pas le cisaillement). Les scènes à **texture répétée** (carrelage, fenêtres identiques) produisent des descripteurs presque égaux en de nombreux points, que l'appariement aura du mal à départager — c'est précisément ce que le ratio test (§17.6) sait détecter.

### Exemple numérique

Soit le point-clé dont l'histogramme d'orientation à 36 bins pique à `40°` : l'orientation de référence est `40°`. Un gradient mesuré à `85°` dans l'image sera enregistré, dans le descripteur, à `85° − 40° = 45°`. Si l'image entière tourne de `30°`, l'orientation dominante devient `70°` et ce même gradient, désormais à `115°`, est enregistré à `115° − 70° = 45°` : valeur identique. Le descripteur n'a pas bougé. Sur la grille 4×4×8, une sous-région où tous les gradients pointent à 45° relatif concentre son vote dans un seul des 8 bins, comme l'exemple HOG du §17.3, et le vecteur final compte 128 composantes normalisées à `‖f‖₂ = 1`.

### Piège d'implémentation

SIFT a longtemps vécu dans `opencv-contrib` pour raisons de brevet ; le brevet ayant expiré, il est revenu dans le module principal (`cv2.SIFT_create()` depuis OpenCV 4.4). Le descripteur est un vecteur **flottant** L2-normalisé : l'apparier avec une distance de Hamming n'a aucun sens (réservée aux binaires, §17.5). Une amélioration quasi gratuite, **RootSIFT** : remplacer la distance euclidienne par la distance de Hellinger revient à prendre la racine carrée des composantes (après normalisation L1) puis à apparier en L2 ; gain de robustesse notable, deux lignes de code.

### Schéma de nœuds

```
[Point-clé (DoG, §17.2)] ──> [Orientation dominante (hist. 36 bins)]
        ──> [Grille 4×4 × 8 orientations = 128-D] ──> [Norm L2 → clip 0,2 → Norm L2]
        ──> [Descripteur SIFT]      (option : RootSIFT = √ après L1)
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.4.*

---

## 17.5 ORB et BRIEF — descripteurs binaires

### Définition

Quand la vitesse prime (temps réel, embarqué), on remplace le vecteur de 128 flottants par une **chaîne de bits**. BRIEF fixe à l'avance `n` paires de positions `(aᵢ, bᵢ)` dans le patch et pose un bit par paire :

```
bitᵢ = 1 si I(aᵢ) < I(bᵢ) , sinon 0          (n = 256 bits typiquement)
distance entre deux descripteurs : Hamming (nombre de bits différents, §3)
```

ORB ajoute à BRIEF ce qui lui manque : des points-clés FAST, une **orientation** (via le centroïde d'intensité du patch) qui fait tourner le motif d'échantillonnage, et un choix appris des paires pour les rendre décorrélées.

### Dérivation — pourquoi c'est rapide

Un descripteur binaire se compare par un `XOR` suivi d'un comptage de bits (`popcount`), deux instructions matérielles. Comparer un million de paires se fait en quelques millisecondes, là où la distance euclidienne sur 128 flottants demande un ordre de grandeur de plus. L'orientation d'ORB rétablit l'invariance en rotation que BRIEF seul n'a pas : on calcule l'angle `θ = arctan2(m₀₁, m₁₀)` à partir des moments d'ordre 1 du patch (§2), puis on applique cette rotation aux paires d'échantillonnage avant de comparer. ∎

### Ce que ça mesure / l'angle mort

ORB mesure un **motif de comparaisons d'intensités**, robuste et léger, mais moins discriminant et moins tolérant aux grands changements d'échelle ou de point de vue que SIFT. C'est l'arbitrage du chapitre : on échange du pouvoir de distinction et de la robustesse contre de la vitesse et une empreinte mémoire minuscule (32 octets contre 512 pour SIFT).

### Exemple numérique (vérifié)

Deux descripteurs sur 8 bits (un jouet ; en pratique 256) :

```
d1 = 1 0 1 1 0 0 1 0
d2 = 1 1 1 0 0 0 1 1
xor  0 1 0 1 0 0 0 1   ⟹   distance de Hamming = 3 bits sur 8
```

Trois bits diffèrent : les descripteurs sont proches mais pas identiques. Sur 256 bits, un seuil d'acceptation typique se situe autour de 50–64 bits de différence.

### Piège d'implémentation

Le piège classique : apparier des descripteurs binaires avec une distance euclidienne. Il **faut** `cv2.BFMatcher(cv2.NORM_HAMMING)`, sinon le matcher compare des octets comme des réels et les résultats n'ont aucun sens. Pour de très grandes bases, on remplace la force brute par du LSH (hachage sensible à la localité), seul index efficace pour la distance de Hamming.

### Schéma de nœuds

```
[Image] ──> [FAST (points-clés)] ──> [Orientation (centroïde, §2)]
        ──> [BRIEF orienté (256 bits)] ──> [Descripteur binaire]
[d₁] ──[XOR + popcount]──> [d₂] : distance de Hamming
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.5.*

---

## 17.6 Appariement et ratio test de Lowe

### Définition

Une fois les descripteurs calculés des deux côtés, on apparie chaque point de A à son plus proche voisin dans B. Le test décisif n'est pas la distance absolue mais le **rapport** entre le plus proche et le deuxième plus proche voisin :

```
soit d₁ = distance au 1er voisin , d₂ = distance au 2e voisin
accepter le match  ⟺  d₁ / d₂ < τ        (Lowe : τ ≈ 0,8)
```

### Dérivation — pourquoi un rapport, pas un seuil

Un seuil absolu sur `d₁` est impossible à régler : il varie avec le point, la scène, le descripteur. Le rapport est auto-étalonné. Un appariement **correct** met en jeu un point distinctif : son vrai homologue est nettement plus proche que tout autre candidat, donc `d₁ ≪ d₂` et le rapport est petit. Un appariement **ambigu** — texture répétée, point peu distinctif — a plusieurs candidats presque équidistants, donc `d₁ ≈ d₂` et le rapport approche 1. Le seuil `0,8` vient de l'analyse de Lowe : il élimine environ 90 % des faux appariements en ne sacrifiant que ~5 % des vrais. ∎

### Ce que ça mesure / l'angle mort

Le ratio test mesure la **distinctivité** d'un appariement, pas sa justesse. Un bon appariement est une clé qui n'ouvre qu'une serrure ; un appariement ambigu est un passe-partout qui en ouvre deux presque aussi bien, et sur lequel on ne peut donc rien parier. Son angle mort est le revers de sa force : sur une structure **légitimement répétée** (une rangée de fenêtres identiques), il rejette des appariements qui sont en réalité corrects, simplement parce qu'ils ne sont pas uniques. Dans ce cas, on relâche `τ` et l'on s'en remet davantage au filtrage géométrique (§17.7).

### Exemple numérique (vérifié)

Deux appariements, descripteurs L2-normalisés :

```
point net     : d₁ = 0,32 , d₂ = 0,51   ⟹   ratio = 0,63 < 0,8   ACCEPTÉ
texture répétée: d₁ = 0,45 , d₂ = 0,49   ⟹   ratio = 0,92 ≥ 0,8   REJETÉ
```

Le premier point a un homologue franc ; le second a un quasi-jumeau ailleurs dans l'image, le test le met de côté. Le ratio test fait ici, en une division, le tri qu'un seuil absolu n'aurait jamais réussi : `0,45` est une petite distance, et pourtant l'appariement est mauvais.

### Piège d'implémentation

Utiliser `knnMatch(..., k=2)` pour disposer des deux voisins, **jamais** `match()` qui n'en rend qu'un. Ne pas combiner ratio test et `crossCheck=True` : ils visent le même but par des moyens incompatibles, on choisit l'un ou l'autre. Pour les descripteurs binaires, l'index FLANN doit être configuré en mode LSH, sinon il retombe sur des paramètres pensés pour des vecteurs réels.

### Schéma de nœuds

```
[Descripteurs A] ──> [k-NN (k=2) dans B] ──> [d₁, d₂]
        ──> [Ratio d₁/d₂ < 0,8 ?] ──oui──> [Appariement retenu]
                                   ──non──> [Rejeté (ambigu)]
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.6.*

---

## 17.7 Des correspondances au modèle : RANSAC et homographie

### Définition

Même après le ratio test, des appariements erronés subsistent. On estime alors le modèle géométrique qui relie les deux vues — pour un plan ou une rotation pure de caméra, une **homographie** `H` (§8.3) — en rejetant les aberrants par RANSAC (§16.1) :

```
tirer 4 correspondances au hasard  →  estimer H (DLT)  →  compter les inliers
                                       (‖x' − H·x‖ < seuil)
répéter, garder le H au plus grand consensus, ré-estimer sur tous ses inliers
```

### Dérivation — le coût du pré-filtrage se lit dans le nombre d'itérations

Le nombre d'essais nécessaires pour tirer au moins un échantillon sans aberrant suit la formule du §16.1, avec `n = 4` (taille minimale pour une homographie) :

```
N = log(1 − p) / log(1 − wⁿ)        p = 0,99 (confiance) , w = ratio d'inliers
```

La dépendance en `w` est brutale, et c'est tout l'enjeu :

```
w = 0,7  →  N = 17 itérations
w = 0,5  →  N = 72 itérations
w = 0,3  →  N = 567 itérations
```

Tirer quatre correspondances sans aberrant dans un lot à moitié faux, c'est espérer une main sans joker dans un jeu qui en compte un sur deux : possible, mais il faut redistribuer souvent. Faire passer le ratio d'inliers de 0,3 à 0,5 divise le travail de RANSAC par huit. Voilà pourquoi le ratio test du §17.6, qui augmente `w` en jetant les mauvais appariements avant RANSAC, n'est pas un luxe : il rend l'étape robuste praticable. ∎

### Ce que ça mesure / l'angle mort

RANSAC trouve le modèle **dominant**. Quand la scène contient plusieurs plans (donc plusieurs homographies), il n'en capture qu'un et traite les autres comme du bruit ; il faut alors l'appliquer en séquence. Il échoue aussi sur les configurations **dégénérées** — quatre points presque alignés ne définissent pas une homographie stable.

### Exemple numérique

Après ratio test, 200 appariements dont 100 corrects (`w = 0,5`). Avec `p = 0,99` et `n = 4`, RANSAC a besoin de `N = 72` tirages pour avoir 99 % de chances d'en réussir un sans aberrant. Chaque tirage coûte une estimation d'homographie sur 4 points et un comptage d'inliers sur 200 — quelques dizaines de milliers d'opérations en tout, négligeable. Sans le ratio test, si `w` tombe à 0,3, il en faudrait 567 : huit fois plus, pour le même résultat.

### Piège d'implémentation

`cv2.findHomography(pts1, pts2, cv2.RANSAC, ransacReprojThreshold)` renvoie aussi un **masque** d'inliers — l'utiliser pour compter et visualiser les bons appariements. Le seuil de reprojection est en **pixels** et dépend de la résolution : trop serré, il rejette de bons appariements ; trop lâche, il avale des aberrants. Normaliser les coordonnées des points (centrage et mise à l'échelle de Hartley) avant la DLT stabilise l'estimation, ce que fait OpenCV en interne mais pas une implémentation maison naïve.

### Schéma de nœuds

```
[Appariements filtrés] ──> [RANSAC : tirer 4 pts → estimer H → compter inliers]
        ──(répéter N fois)──> [Meilleur H + masque d'inliers] ──> [ré-estimation sur inliers]
```

*Schéma à produire ; script de référence en Annexe 1, §A1‑17.7.*

---

## 17.8 L'état de l'art

Les descripteurs appris ont rejoint, puis dépassé, SIFT sur les cas difficiles. **SuperPoint** apprend conjointement détection et description en une passe ; **DISK** optimise les descripteurs de bout en bout par politique de gradient ; les méthodes **sans détecteur** comme **LoFTR** apparient directement des champs denses, là où les points-clés manquent (surfaces lisses, faible texture) ; et des **appariems neuronaux** comme SuperGlue ou LightGlue raisonnent globalement sur l'ensemble des correspondances au lieu de les traiter une à une.

Chaque famille a son créneau. SIFT et ORB restent d'excellents choix pour beaucoup de pipelines de reconstruction (SfM) et de SLAM : interprétables, sans données d'entraînement, robustes sur des scènes texturées et bien éclairées, et frugaux. Les méthodes apprises prennent l'avantage sous changement de point de vue extrême, faible texture ou éclairage hostile, au prix d'un GPU et d'un entraînement. Le pipeline de ce chapitre — détecter, décrire, apparier, filtrer — n'a pas été remplacé ; ses quatre étapes ont été, une à une, confiées à des réseaux.

---

## Tableau récapitulatif

| Descripteur | Invariances acquises | Ce qu'il jette | Dimension | Distance | Créneau |
|---|---|---|---|---|---|
| Patch brut | aucune (ou gain/offset si normalisé) | rien | k² pixels | SSD / L2 | inutilisable hors translation pure |
| HOG | éclairage (offset + gain) | rotation, échelle | ~3780 (fenêtre) | L2 | détection à pose connue (piétons) |
| SIFT | similitude + éclairage | rotation, échelle, gain, offset | 128 (float) | L2 / Hellinger | référence générale, SfM, panoramas |
| ORB / BRIEF | similitude (rotation par steering) | idem SIFT, moins discriminant | 256 bits | Hamming | temps réel, embarqué, SLAM léger |
| Appris (SuperPoint, LoFTR…) | jusqu'à l'affine/perspectif appris | selon l'entraînement | variable | L2 / cosinus | point de vue extrême, faible texture |

| Filtre | Rôle | Paramètre clé | Angle mort |
|---|---|---|---|
| Ratio test de Lowe | rejeter les appariements ambigus | `τ ≈ 0,8` | rejette les structures répétées légitimes |
| RANSAC + homographie | imposer un modèle géométrique global | seuil de reprojection (px) | un seul modèle dominant ; configs dégénérées |

---

## Encadré final

Tout ce chapitre tient dans une décision prise quatre fois : que faut-il ignorer ? On ignore la position en n'extrayant qu'aux points-clés, l'échelle en mesurant l'échelle caractéristique, la rotation en travaillant dans un référentiel tourné, le gain et l'offset par le gradient et la normalisation. Ce que le descripteur jette n'est pas une perte : c'est exactement ce qui changeait d'une vue à l'autre, et qui l'empêchait de reconnaître un même point. Un bon descripteur survit au déplacement de la caméra parce qu'il a appris d'avance à ne pas regarder ce que la caméra modifie.

La même logique relie les quatre étapes. Le ratio test élève le ratio d'inliers, ce qui effondre le nombre d'itérations de RANSAC : un bon tri en amont rend la robustesse en aval presque gratuite — la chute de 567 à 72 essais le chiffre. C'est, sous un autre nom, ce que l'on retrouve depuis le premier chapitre : bien poser la représentation laisse peu de travail au reste. Le chapitre 16 a donné l'estimateur ; ce chapitre lui a donné des correspondances assez propres pour qu'il converge.
