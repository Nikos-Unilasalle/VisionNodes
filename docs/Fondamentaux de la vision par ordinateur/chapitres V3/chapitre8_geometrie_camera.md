# Chapitre 8 — Géométrie de la caméra : projeter, perdre, retrouver

![Un homme sérieux, mètre en main, aligne une foule bigarrée sur une droite](../figures/fig_ch8_couverture.jpg)
*Capturer le monde en image, c'est l'aligner de force sur une surface plate. Quelque chose se perd dans l'opération. Ce chapitre explique quoi, pourquoi, et comment le récupérer.*

---

Dans l'allégorie de la caverne de Platon, des prisonniers enchaînés ne voient que des ombres projetées sur un mur — ils ne connaissent du monde que cette représentation aplatie. Ils peuvent en déduire des formes, des tailles relatives, des mouvements, mais la troisième dimension leur est à jamais cachée. Une caméra fait exactement la même chose : elle projette un espace à trois dimensions sur un rectangle de pixels, et la profondeur disparaît dans l'opération. Deux objets de tailles différentes, placés à des distances différentes, peuvent produire exactement la même image.

Le fil du chapitre tient en une phrase : **une caméra encode une perte précise, et la connaître permet de l'inverser.** La profondeur, sacrifiée à la prise de vue, n'est pas perdue au hasard : elle suit une mécanique exacte. Les sections 8.1 et 8.2 décrivent cette mécanique de la perte ; les sections 8.3 à 8.7 construisent les outils qui la compensent — calibration, homographie, géométrie épipolaire, stéréovision, correction de distorsion.

### Un peu de vocabulaire avant de commencer

*   **Coordonnées homogènes** : Une représentation des points 2D par trois valeurs `(X, Y, W)` et 3D par quatre valeurs `(X, Y, Z, W)`. La coordonnée réelle est obtenue en divisant par le facteur d'échelle `W`.
*   **Matrice de projection (P)** : Une grille de nombres de taille 3×4 qui transforme mathématiquement un point de l'espace 3D en son équivalent 2D sur le capteur.
*   **Calibration** : L'estimation des paramètres internes de la caméra (focale, centre optique) pour modéliser précisément comment elle déforme et projette le monde.

---

## 8.1 — Coordonnées homogènes : linéariser la projection

> *Reporter une retenue, pour calculer proprement et ne diviser qu'à la fin*

![fig_ch8_obs1_homogeneous](../figures/fig_ch8_obs1_homogeneous.pdf)

### L'intention

Quand on veut fusionner deux images d'une même scène — assembler un panorama, recaler un plan sur une photo aérienne, incruster un objet 3D en réalité augmentée —, on doit calculer comment un pixel de la première image correspond à un pixel de la seconde. Cette correspondance implique une division par la profondeur, et une division rend tout **non-linéaire** : on ne peut plus chaîner les calculs en multipliant des matrices. On voudrait une écriture qui garde la projection linéaire d'un bout à l'autre.

### La forme recherchée

L'astuce consiste à ajouter une troisième coordonnée fictive, W, à chaque point, et à ne diviser par W qu'au tout dernier moment. C'est le geste de la **retenue** en arithmétique : on ne résout pas la division tout de suite, on la met de côté pour continuer à calculer proprement. En attendant, toutes les opérations deviennent des multiplications matricielles — rapides, chaînables, inversibles —, ce qui ouvre la porte à toute l'algèbre linéaire.

### La formule

```
Point image en coordonnées homogènes : (u·W,  v·W,  W)
Pour lire le résultat final : diviser par W  →  (u, v)
```

Le triplet `(6, 8, 2)` représente le même point que `(3, 4, 1)` ou `(30, 40, 10)` : tous donnent (3, 4) après division. Cette classe d'équivalence — tous les multiples d'un même triplet — constitue un **point projectif**. ∎

### Ce qu'elle permet en plus — les points à l'infini

Ce formalisme représente les *points à l'infini*, impossibles à écrire en coordonnées ordinaires. Deux rails parallèles convergent en image vers un point de fuite, qui s'écrit simplement `(x, y, 0)` en homogène (un W nul, donc une division par zéro escamotée). Ce point se calcule, s'extrait, s'utilise — pour détecter l'horizon, estimer la géométrie d'une route, redresser une image prise en biais.

### Subtilité — toujours diviser par W avant de lire

Après une chaîne de multiplications matricielles, W ne vaut plus nécessairement 1. Lire les deux premières coordonnées sans diviser par W produit des positions aberrantes, sans aucun message d'erreur — un résultat faux et silencieux. La division finale fait partie de l'opération, pas d'une étape optionnelle.

---

## 8.2 — Le modèle sténopé : du monde réel au pixel

> *L'ombre portée d'un point ne dit plus à quelle distance il était*

### L'intention

En contrôle qualité industriel, on veut mesurer en millimètres la taille d'un défaut visible dans l'image. Convertir des pixels en millimètres suppose de connaître exactement comment la caméra a transformé la scène en image. Ce modèle de la transformation s'appelle le **modèle sténopé** (*pinhole*).

### La forme recherchée

Le chemin d'un point du monde jusqu'à un pixel traverse trois étapes successives, qu'on visualise l'une après l'autre :

```
monde → repère caméra  :  [R | t]         (où est la caméra, comment orientée)
repère caméra → image  :  division par Z  (la perte de profondeur)
image → pixels         :  K               (focale, centre optique, unités)
```

La matrice **K** est le **passeport de la caméra** : elle traduit les coordonnées géométriques en pixels, dans les unités propres à ce capteur précis. Deux caméras de même focale en millimètres mais aux capteurs de tailles différentes ont des K différentes — comme deux pays qui mesurent la même route, l'un en miles, l'autre en kilomètres.

### La formule

En coordonnées homogènes (§8.1), les trois étapes s'écrivent comme un seul produit matriciel :

```
s · [u  v  1]ᵀ  =  K · [R | t] · [X  Y  Z  1]ᵀ
```

**`[R | t]` — la pose de la caméra.** R est la rotation (l'inclinaison de la caméra), t la translation (sa position). Ensemble, ils expriment les coordonnées du monde dans le repère de la caméra.

**La division par Z — la perte centrale.** Un point à `(Xc, Yc, Zc)` dans le repère caméra projette selon `x = f·Xc/Zc`. La profondeur Zc devient le facteur d'échelle `s` de l'équation : présent dans les calculs, mais inconnu depuis l'extérieur. C'est lui qu'on cherchera à récupérer tout au long du chapitre.

**`K` — les paramètres intrinsèques.**

```
K = [ fx   0   cx ]
    [  0  fy   cy ]
    [  0   0    1 ]
```

- **fx, fy** : la focale en pixels (distance focale ÷ taille physique d'un pixel)
- **cx, cy** : le centre optique — là où l'axe optique touche le capteur ∎

### Exemple

f = 500 px, centre (320, 240). Un point à Zc = 2 m, décalé de 30 cm sur le côté et 10 cm en hauteur :

```
u = 500 × 0,3 / 2,0 + 320 = 395 px
v = 500 × 0,1 / 2,0 + 240 = 265 px
```

Un objet deux fois plus petit à Zc = 1 m projette au même pixel 395. Deux scènes radicalement différentes, une image identique : la perte de profondeur incarnée.

---

## 8.3 — Calibration : apprendre à sa caméra ses propres règles

> *Sans calibration, un pixel ne mesure rien*

### L'intention

Dès qu'on veut sortir des pixels pour obtenir des grandeurs physiques — millimètres, degrés, mètres —, il faut connaître K et les coefficients de distorsion (§8.7) de sa caméra. C'est la **calibration**. Sans elle, comparer deux caméras, fusionner des images ou mesurer des distances réelles est hors de portée.

### La forme recherchée

On photographie un damier dont les cases ont des dimensions connues, sous des angles et des distances variés — c'est la méthode de **Zhang (2000)**. Pour chaque photo, on détecte les coins du damier au sous-pixel. Chaque photo fournit une relation (une homographie, §8.4) entre le plan du damier et l'image, qui impose des contraintes sur K. Avec 10 à 20 poses diversifiées, le système se résout, puis se raffine en minimisant l'erreur de reprojection (§8.7).

### La formule

Le résultat de la calibration est un jeu de paramètres ; voici une sortie typique pour un capteur Sony 1/2.3" :

```
fx = 1412 px,  fy = 1410 px,  cx = 964 px,  cy = 546 px
k1 = −0,32,    k2 = +0,11   (distorsion radiale)
RMS = 0,28 px
```

Le RMS (erreur de reprojection, §8.7) chiffre la qualité de l'ajustement, en pixels. ∎

### Réglage — diversifier les poses

Des poses toutes frontales et centrées laissent certains paramètres mal contraints — notamment la distorsion et le rapport fx/fy. Incliner le damier, le placer dans les coins de l'image et varier les distances lève ces ambiguïtés. Un RMS supérieur à 0,5 px traduit en général une couverture insuffisante des poses, pas un défaut de détection des coins.

### Dans VNStudio

Canvas : `Camera Input` → `Checkerboard Detector` → `Camera Calibration`. L'inspecteur affiche le RMS en direct à chaque nouvelle pose ajoutée, et exporte K au format JSON.

---

## 8.4 — L'homographie : corriger la perspective d'une surface plane

> *Redresser le regard oblique de la caméra sur une table, un sol, une affiche*

### L'intention

Une caméra de surveillance en hauteur, inclinée sur un sol d'entrepôt, déforme les caisses par la perspective : les rectangles deviennent des trapèzes. On veut une vue de dessus aux vraies proportions, pour mesurer des distances au sol ou suivre des objets.

### La forme recherchée

Pour vous représenter l'homographie mentalement, imaginez que vous projetez une diapositive contenant un quadrillage rectangulaire parfait sur un mur :
1. **La déformation projective** : Si le projecteur est bien perpendiculaire au mur, le quadrillage reste rectangulaire. Mais si vous inclinez le projecteur de biais, ou si le mur est de guingois, le quadrillage se déforme : les rectangles deviennent des trapèzes, et les lignes parallèles semblent converger vers un point de fuite.
2. **Le rôle de l'homographie** : L'homographie `H` est la formule mathématique (matrice 3×3) qui modélise exactement cette déformation géométrique d'un plan vers un autre. Elle agit comme un redresseur virtuel : elle calcule comment distordre l'image inclinée pour la ramener à sa forme rectangulaire d'origine, vue de dessus.

Cette transformation est rigoureuse et pixel à pixel, mais elle exige une contrainte stricte. Elle n'est valide que dans deux situations précises :
1. **Une scène plane** : Tous les objets photographiés résident sur un même plan physique (comme une affiche au mur, une table, ou un sol d'entrepôt plat). S'il y a du relief (ex. : des boîtes en volume posées sur le sol), l'homographie va les coucher et les étirer artificiellement.
2. **Une rotation pure de la caméra** : La caméra pivote sur son propre centre sans aucun déplacement dans l'espace (comme lorsqu'on prend un panorama). Dans ce cas, même si la scène a du relief, la perspective ne change pas d'une vue à l'autre et l'homographie reste exacte.

Hors de ces deux cas, la relation entre deux vues implique une parallaxe 3D et relève de la géométrie épipolaire (§8.5).

### La formule

```
x'  ∼  H · x          (H : matrice 3×3, 8 degrés de liberté)
```

`x` et `x'` sont des points homogènes dans chacune des deux images. 8 degrés de liberté : **4 correspondances de points** suffisent à déterminer H. En pratique on en utilise davantage, avec RANSAC pour rejeter les correspondances erronées.

La raison de fond : pour les points d'un plan Z = 0, la colonne de R associée à Z disparaît du produit K·[R|t]. Il reste une matrice 3×3 — exactement H. La perte de profondeur devient ici un avantage : pour un plan, Z est connu (nul), donc le terme problématique s'annule de lui-même. ∎

### Exemple

Vue aérienne d'un parking depuis une caméra inclinée à 45°. Quatre coins de la zone d'intérêt sont identifiés dans l'image, leurs coordonnées métriques au sol connues → H se calcule → chaque image est redressée en vue de dessus. Les véhicules deviennent mesurables en mètres.

### Dans VNStudio

Canvas : `Camera Input` → `Feature Matching` → `Find Homography (RANSAC)` → `Warp Perspective` → `Output`. L'inspecteur affiche le nombre d'inliers : un bon H dépasse généralement 80 % d'inliers sur des correspondances ORB filtrées.

---

## 8.5 — La géométrie épipolaire : chercher en ligne, pas en surface

> *Un ami au concert décrit ce qu'il voit : on restreint la recherche à une rangée*

### L'intention

Un robot équipé de deux caméras latérales détecte un obstacle dans l'image gauche. Pour en calculer la distance, il doit retrouver ce même point dans l'image droite et mesurer son décalage. Chercher dans toute l'image droite est coûteux et produit beaucoup d'erreurs. On veut réduire cette recherche.

### La forme recherchée

Imaginez qu'un ami vous appelle d'un concert et décrive ce qu'il voit — « un homme en rouge, au troisième rang ». Vous ignorez sa place exacte, mais vous savez que son champ de vision correspond à une certaine rangée de sièges de votre côté : vous restreignez la recherche à cette rangée, pas à toute la salle.

C'est exactement le mécanisme de la géométrie épipolaire. Un pixel de l'image gauche correspond à un *rayon* dans l'espace 3D — une droite partant du centre optique, de profondeur inconnue. Ce rayon, vu depuis la caméra droite, se projette en une ligne dans l'image droite : la **ligne épipolaire**. Le point cherché se trouve forcément sur cette ligne. La perte de profondeur — l'incertitude sur la position le long du rayon — est précisément ce qui engendre cette contrainte : la recherche passe de 2D (toute l'image) à 1D (une ligne).

### La formule

La **matrice fondamentale F** encode cette contrainte :

```
x'ᵀ · F · x  =  0          pour tout couple de points correspondants x ↔ x'
```

Le produit `F · x` calcule directement l'équation de la ligne épipolaire dans l'image droite. F décrit toute la géométrie relative des deux vues à partir de simples correspondances de pixels, **sans connaître K** — utile quand les caméras ne sont pas calibrées. Elle a 7 degrés de liberté ; 8 correspondances suffisent (algorithme des 8 points).

Quand K est connue, on passe à la **matrice essentielle E**, qui contient davantage :

```
E  =  K'ᵀ · F · K  =  [t]ₓ · R
```

E se décompose en la rotation R et la translation t entre les deux vues — exactement la **pose relative** des caméras, point de départ de toute reconstruction 3D, de tout SLAM visuel, de toute odométrie. L'algorithme de Nistér (2004) calcule E avec seulement 5 correspondances. ∎

### Différence d'implémentation — la normalisation de Hartley

Centrer et mettre à l'échelle les coordonnées avant le calcul (normalisation de Hartley) est indispensable : sur des coordonnées pixel brutes (0–1920), le système devient numériquement instable et les résultats inexploitables.

---

## 8.6 — Stéréovision : retrouver la profondeur perdue

> *Le décalage entre deux vues mesure la distance, comme deux yeux jugent le relief*

### L'intention

Avec une paire de caméras, on veut mesurer directement la distance à un obstacle — récupérer la profondeur que la projection avait effacée.

### La forme recherchée

Un même point du monde apparaît à deux endroits différents dans les deux images : ce décalage horizontal, la **disparité**, est d'autant plus grand que l'objet est proche. C'est le principe de la vision binoculaire — deux yeux jugent le relief par le léger écart entre leurs deux images. La profondeur est l'inverse de la disparité.

### La formule

```
Z  =  f · B / d
```

`f` : focale en pixels. `B` : distance entre les deux caméras (*baseline*). `d` : disparité, le décalage horizontal en pixels du même point entre image gauche et droite. La relation inverse `Z ∝ 1/d` a trois conséquences à connaître :

**1. Proche = grande disparité, fiable ; loin = faible disparité, incertain.** Un objet à 50 cm présente une forte disparité, mesurable avec précision. À 30 m, la disparité est si faible qu'une erreur d'un pixel entraîne une incertitude de plusieurs mètres sur Z. La stéréovision est l'outil de la courte portée ; le LiDAR prend le relais au-delà.

**2. L'erreur sur Z croît comme Z².** Erreur de ±1 px sur d à 2,4 m : incertitude de ±0,25 m. Même erreur à 24 m : incertitude de ±6 m.

**3. La baseline est un arbitrage de conception.** Grande baseline → grandes disparités → meilleure précision en profondeur, mais recouvrement réduit entre les deux images et appariement plus difficile pour les objets proches. Chaque application a son B optimal. ∎

### Exemple

f = 800 px, B = 12 cm, disparité d = 40 px :

```
Z = 800 × 0,12 / 40  =  2,4 m
```

Le vrai défi est de **mesurer la disparité** : trouver pour chaque pixel gauche son homologue exact à droite. La rectification (alignement des lignes épipolaires à l'horizontale) ramène la recherche sur une seule ligne. Les ennemis : zones sans texture (ciel, murs unis), occlusions, reflets spéculaires. L'algorithme SGBM (*Semi-Global Matching*) régularise la carte de disparité en imposant une cohérence spatiale entre pixels voisins.

### Différence d'implémentation — la disparité en 1/16 de pixel

`cv2.StereoSGBM_create` renvoie la disparité en unités de 1/16 de pixel (entier × 16). Diviser par 16,0 avant d'appliquer Z = fB/d ; oublier ce facteur produit des profondeurs 16 fois trop petites.

### Dans VNStudio

Canvas : `Camera Left` + `Camera Right` → `Stereo Rectify` → `StereoSGBM` → `Depth Map` → `Colorize`. La carte de profondeur s'affiche en fausses couleurs ; l'inspecteur donne les valeurs min/max/médiane en mètres.

---

## 8.7 — Distorsion : corriger ce que l'objectif déforme

> *Un miroir déformant qui laisse le centre intact et tord les bords*

![Distorsion radiale en barillet et en coussinet](../figures/fig_ch8_obs2_radial_distortion.pdf)

### L'intention

Un objectif réel n'est pas parfait : les lignes droites de la scène arrivent légèrement courbées dans l'image, surtout en périphérie. En métrologie ou en cartographie, cette déformation biaise toutes les mesures ; en vision, elle fausse la détection de coins et la précision des homographies. Il faut la corriger avant tout le reste.

### La forme recherchée

La déformation se concentre vers les bords et épargne le centre, comme un **miroir déformant** qui laisse le visage intact au milieu et le tord sur les côtés. Elle prend deux formes :

- **Barillet** (k₁ < 0) : l'image gonfle vers les bords, un horizon droit apparaît bombé. Typique des grands-angles et des caméras de surveillance.
- **Coussinet** (k₁ > 0) : l'image se resserre vers les bords. Plus rare ; courant sur les téléobjectifs.

### La formule

`(x, y)` désignent les coordonnées *idéales* (sans distorsion), `r = √(x²+y²)` la distance au centre. Les coordonnées réellement mesurées valent :

```
x_mesuré  =  x · (1 + k₁r² + k₂r⁴)
y_mesuré  =  y · (1 + k₁r² + k₂r⁴)
```

Le facteur `(1 + k₁r² + k₂r⁴)` vaut 1 au centre (r = 0) — rien n'y bouge — et s'écarte de 1 à mesure qu'on s'éloigne, exactement comme le miroir déformant. Les coefficients k₁, k₂ sont estimés lors de la calibration (§8.3). ∎

### Comment juger le modèle — l'erreur de reprojection

Pour savoir si le modèle complet (K + distorsion) est bon, on prend un point 3D de position connue, on calcule où le modèle prédit sa projection, et on mesure l'écart en pixels avec l'endroit où il apparaît vraiment :

```
erreur  =  ‖ point_mesuré − point_prédit_par_le_modèle ‖   (en pixels)
```

C'est la métrique de référence de tout le chapitre — calibration, reconstruction, bundle adjustment — exprimée dans l'unité qui compte, le pixel.

| RMS | Interprétation |
|---|---|
| < 0,5 px | Bonne calibration, usage général |
| < 0,1 px | Métrologie, chirurgie, cartographie précise |
| > 1,0 px | Poses insuffisamment diversifiées, ou mauvaise détection des coins |

### Exemple

Le modèle prédit le coin d'un damier en (320,0 ; 240,0), détecté à (320,8 ; 239,4) :

```
erreur²  =  0,8² + 0,6²  =  0,64 + 0,36  =  1,00 px²     →  RMS = 1,0 px sur ce point
```

### Paramètres opérationnels (VNStudio / Python)

Dans le nœud `Undistort` (ou via `cv2.undistort` en Python), la correction géométrique repose sur les paramètres opérationnels suivants :

*   **Matrice de la caméra (K)** :
    *   Dans VNStudio, ce paramètre se configure via le fichier de calibration de la caméra ou les champs **Camera Matrix (K)** ; en Python (OpenCV), il correspond à l'argument `cameraMatrix` dans la fonction `cv2.undistort`.
    *   Une matrice 3×3 contenant les paramètres internes de la caméra : la focale en pixels (`fx`, `fy`) et le point principal (`cx`, `cy`), qui désigne l'intersection de l'axe optique avec le capteur. Ces valeurs sont calculées lors de la phase de calibration en filmant une mire (comme un damier).
*   **Coefficients de distorsion (D)** :
    *   Dans VNStudio, ces valeurs correspondent aux champs **Distortion Coefficients (D)** ; en Python (OpenCV), elles correspondent à l'argument `distCoeffs` dans la fonction `cv2.undistort`.
    *   Un vecteur de 4, 5 ou 8 valeurs. Les coefficients de distorsion radiale (`k1`, `k2`, `k3`) corrigent l'effet « barillet » (bords bombés vers l'extérieur) ou « coussinet » (bords rentrants). Les coefficients de distorsion tangentielle (`p1`, `p2`) corrigent le défaut d'alignement physique entre le capteur et la lentille lors de l'assemblage de l'objectif.
*   **Seuil de reprojection RANSAC (dans `cv2.findHomography`)** :
    *   Dans VNStudio, ce paramètre correspond au champ **RANSAC Threshold** ; en Python (OpenCV), il correspond à l'argument `ransacReprojThreshold` dans la fonction `cv2.findHomography`.
    *   Lors du calcul d'une homographie entre deux vues, le paramètre `ransacReprojThreshold` (généralement réglé entre 1 et 5 pixels) définit l'écart maximal toléré pour qu'une correspondance de points soit considérée comme valide (inlier) et participe à l'estimation de la géométrie de projection.

### Dans VNStudio

Dans votre canvas :
`Camera Source` ──> `Undistort` ──> `Output Display`.

Le nœud `Undistort` prend en entrée l'image déformée et lui applique la matrice de calibration préalablement estimée. Il se place toujours en début de pipeline et précalcule les cartes de remapping au chargement des paramètres. La correction s'applique ensuite en temps réel sans coût supplémentaire par image, redressant instantanément les lignes courbes de l'objectif grand angle en lignes droites parfaites, particulièrement près des bords.

**Exercice de dépannage :** L'exercice consiste à estimer une homographie entre deux images à l'aide d'un nœud **Find Homography (RANSAC)**. Introduire volontairement un point d'appariement faux (un outlier reliant deux zones n'ayant aucun rapport géométrique) et désactiver RANSAC en sélectionnant la méthode des moindres carrés standard (méthode `0` au lieu de `RANSAC`). Le lecteur observe que l'image projetée se distord de manière aberrante et s'étire à l'infini, démontrant comment un seul outlier suffit à détruire l'estimation géométrique en moindres carrés.

---

## Tableau récapitulatif

| Outil | Ce qu'il encode | Ce qui manque | Usage principal |
|---|---|---|---|
| Coordonnées homogènes | Projection linéarisée ; points à l'infini | Ne récupère pas la profondeur | Base de toute la géométrie projective |
| Modèle sténopé K[R\|t] | Chemin complet monde → pixel | Profondeur Z perdue (rayon ambigu) | Rendu, RA, simulation |
| Calibration (Zhang) | K + distorsion | Nécessite une mire, poses diversifiées | Toute mesure métrique dans l'image |
| Homographie H | Correspondance pixel à pixel (plan ou rotation pure) | Invalide si scène non plane + translation | Panoramas, vue de dessus, RA sur plan |
| Matrice fondamentale F | Géométrie épipolaire sans calibration | Ne donne pas R et t | Appariement guidé, vérification |
| Matrice essentielle E | Pose relative R, t (avec calibration) | Translation à échelle inconnue | SLAM, reconstruction, odométrie |
| Stéréo Z = fB/d | Profondeur métrique depuis deux vues | Imprécis loin ; zones sans texture | Robotique courte portée, chirurgie |
| Distorsion k₁, k₂ + reprojection | Écart du modèle réel au modèle idéal | Ne corrige pas le flou ni le bougé | Calibration précise, métrologie |

---

## Encadré final — défaire ce qu'une caméra a fait

La caméra est l'entrée de tout pipeline de vision, et elle impose d'emblée une contrainte : elle a aplati un espace à trois dimensions sur un plan, en sacrifiant la profondeur. Tant qu'on ne comprend pas comment cette perte s'est produite, on ne peut ni mesurer, ni recaler, ni reconstruire correctement.

Les outils du chapitre sont les réponses successives à cette perte. La calibration donne au modèle ses paramètres exacts. L'homographie exploite les cas où la profondeur ne pose pas de problème (les surfaces planes). La géométrie épipolaire convertit l'incertitude de profondeur en une contrainte de ligne. La stéréovision récupère la profondeur en croisant deux vues. La correction de distorsion retire les artefacts de l'optique avant que le reste du pipeline ne les amplifie.

On retrouve la logique des chapitres 5 et 3 : un filtre encode un a priori sur ce qu'on s'autorise à ignorer dans le signal, une distance encode ce qui compte et ce qui ne compte pas. Ici, c'est la caméra qui encode sa perte. Nommer précisément ce qui a été sacrifié est, à chaque fois, la première étape pour le compenser. Le chapitre 9 enchaînera sur le mouvement, où deux vues décalées non plus dans l'espace mais dans le temps poseront la même question d'information manquante.

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch8_couverture` | chapeau | Illustration humoristique : personnage avec mètre alignant une foule sur une droite | JPG/PNG |
| `fig_ch8_obs1_homogeneous` | 8.1 | Déjà existant (PDF) : correspondance coordonnées cartésiennes ↔ homogènes | — |
| `fig_ch8_01_projection_rayon` | 8.2 | Schéma : un point 3D → rayon → pixel ; deux objets différents sur le même rayon | SVG |
| `fig_ch8_03_stenope` | 8.2 | Schéma du modèle sténopé : centre optique, plan image, triangles semblables | SVG |
| `fig_ch8_04_calibration_poses` | 8.3 | 6 vues de damier sous angles variés → qualité de calibration | SVG |
| `fig_ch8_05_homographie` | 8.4 | Vue de dessus d'entrepôt avant/après redressement par homographie | SVG |
| `fig_ch8_06_epipolaire` | 8.5 | Schéma : deux caméras, un point 3D, lignes épipolaires dans chaque image | SVG |
| `fig_ch8_07_disparite_profondeur` | 8.6 | Courbe Z = fB/d : profondeur en fonction de la disparité, avec zone d'incertitude | SVG |
| `fig_ch8_obs2_radial_distortion` | 8.7 | Déjà existant (PDF) : distorsion en barillet et en coussinet | — |
| `fig_ch8_09_reprojection` | 8.7 | Schéma : point 3D → projection modèle → écart avec point détecté | SVG |
