# Chapitre — Descripteurs de forme : dérivations et exemples

Une fois qu'un objet a été isolé dans une image — sa silhouette découpée du fond, comme on découperait une forme aux ciseaux dans une feuille — comment le décrire avec des nombres plutôt qu'avec des mots ? On voudrait dire « cet objet est rond », « celui-là est allongé », « celui-ci a un bord déchiqueté », mais le faire de façon que la machine puisse trier, comparer et classer des milliers d'objets sans jamais les regarder. C'est le rôle d'un descripteur de forme : un nombre, ou une poignée de nombres, qui résume une silhouette selon un certain aspect — sa rondeur, son élongation, sa rugosité.

Ce chapitre construit les descripteurs géométriques essentiels. Pour chacun, on cherchera à comprendre ce qu'il mesure vraiment, ce qu'il laisse échapper, et comment les combiner.

Le fil conducteur tient en une phrase : **chaque descripteur choisit ce qu'il voit et ce qu'il oublie**. La circularité repère un bord rugueux mais ignore l'orientation ; la rectangularité voit comment les coins sont remplis mais ignore l'allongement. Comprendre un descripteur, c'est d'abord connaître son angle mort. C'est précisément pour cela qu'on ne s'appuie jamais sur un seul.

Quelques mots de vocabulaire avant de commencer. Une **région** désigne ici l'ensemble des pixels appartenant à un objet, fournis sous forme de **masque binaire** : une image où chaque pixel vaut 1 s'il fait partie de l'objet et 0 sinon. On notera **A** l'aire de la région — son nombre de pixels — et **P** son périmètre, la longueur de son contour. Ces deux quantités, l'aire et le périmètre, suffisent déjà à construire le premier descripteur.

---

## 1.1 Circularité (compacité)

### Définition
```
C = 4π·A / P²
```

### L'idée

La circularité répond à une question simple : à quel point cette forme ressemble-t-elle à un disque ? Elle compare l'aire d'un objet à la longueur de son contour. L'intuition à retenir est qu'un cercle est la forme la plus « économe » qui soit : pour une certaine quantité de contour, c'est lui qui enferme le plus de surface. Un ballon de baudruche gonflé prend spontanément une forme ronde, parce que c'est la façon la plus efficace de contenir l'air avec la peau disponible — la nature « préfère » le cercle pour cette raison.

Cette propriété porte un nom, l'**inégalité isopérimétrique** : à périmètre fixé, aucune forme plane n'enferme plus d'aire que le cercle. Il n'est pas nécessaire de la démontrer ici ; il suffit de retenir sa conséquence directe. La formule est construite pour que **C vaille exactement 1 pour un cercle parfait**, et moins de 1 pour tout le reste. Plus une forme s'allonge ou se déchire, plus C descend vers 0.

On peut le vérifier sur le cercle lui-même. Pour un cercle de rayon r, l'aire vaut A = πr² et le périmètre P = 2πr. En remplaçant :

```
C = 4π·(πr²) / (2πr)² = 4π²r² / 4π²r² = 1
```

Tout se simplifie et il reste 1. ∎ Le facteur 4π dans la définition n'est pas magique : il est calibré exactement pour produire ce résultat.

### Ce qu'elle mesure (et son angle mort)

La circularité chute pour deux raisons distinctes : quand le contour s'allonge, et quand il se dentelle. Son défaut est de ne pas distinguer les deux. Une ellipse lisse et un disque au bord très découpé peuvent obtenir la même valeur de C, alors que ce sont des objets très différents. La circularité signale qu'« il se passe quelque chose », sans dire quoi.

En revanche, elle possède trois qualités précieuses, qu'on appelle des **invariances**. Une invariance, c'est une transformation qui ne change pas la valeur du descripteur. La circularité est invariante par translation (déplacer l'objet ne change rien), par rotation (le tourner ne change rien) et par changement d'échelle (l'agrandir ou le réduire ne change rien). Ces trois insensibilités en font un excellent outil de premier tri : la valeur ne dépend que de la *forme*, jamais de la position, de l'orientation ou de la taille.

### Exemple numérique

Prenons deux caractères dans une tâche de reconnaissance de texte. Un « O » bien formé, dont le contour est presque circulaire, donne environ C ≈ 0,9. Comparons avec un « I », modélisé par une barre verticale de 40 pixels de haut et 4 de large :

```
A = 40 × 4 = 160 px²
P = 2 × (40 + 4) = 88 px
C = 4π × 160 / 88² ≈ 2011 / 7744 ≈ 0,26
```

L'écart est net : 0,9 pour le « O » contre 0,26 pour le « I ». Un simple seuil sur la circularité sépare déjà les caractères ronds des caractères linéaires — un premier tri exploité en reconnaissance optique de caractères.

### Piège d'implémentation : le périmètre est traître à mesurer

Voici un problème qui surprend tout débutant. Sur une grille de pixels, le périmètre est **systématiquement surestimé** si on le mesure naïvement. La raison est géométrique : le bord d'un cercle dessiné sur du papier quadrillé avance en petites marches d'escalier, et la longueur de l'escalier dépasse toujours celle de la pente lisse qu'il imite. Pour un cercle discret de rayon 100, compter les arêtes des pixels donne un périmètre d'environ 800 au lieu de la valeur attendue 628 — une erreur de +27 %.

Cette surestimation gonfle P², donc écrase C. Conséquence concrète : un disque parfait peut afficher C ≈ 0,79 au lieu de 1, simplement à cause de la méthode de mesure. La règle pratique est de toujours préciser **comment** le périmètre a été estimé lorsqu'on publie un seuil de circularité, car les valeurs ne sont pas transposables d'une méthode à l'autre. C'est la première cause de seuils irreproductibles d'une étude à l'autre.

### Code
```python
import cv2
import numpy as np

def circularity(mask):
    # findContours extrait le contour de l'objet à partir du masque binaire.
    # RETR_EXTERNAL : on ne garde que le contour extérieur (pas les trous).
    cnts, _ = cv2.findContours(mask.astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # S'il y a plusieurs contours, on prend le plus grand (l'objet principal).
    c = max(cnts, key=cv2.contourArea)
    p = cv2.arcLength(c, True)          # longueur du contour (le True = fermé)
    # Le 'if p else 0.0' évite une division par zéro si le contour est vide.
    return 4 * np.pi * cv2.contourArea(c) / p**2 if p else 0.0
```

---

## 1.2 Élongation (rapport d'aspect)

### Définition
```
E = L_max / L_min ≥ 1
```
où L_max et L_min sont la longueur et la largeur de la **boîte englobante orientée** — le plus petit rectangle qui contient l'objet, libre de se pencher dans n'importe quel sens pour épouser au mieux la forme.

### L'idée

L'élongation mesure à quel point un objet est allongé : c'est le rapport entre sa longueur et sa largeur. Une pièce de monnaie donne E ≈ 1 (aussi large que longue) ; un crayon donne un E très grand.

Le point délicat est le choix de la boîte. On pourrait prendre le rectangle aligné sur les bords de l'image, mais il aurait un défaut : un crayon posé en diagonale rentrerait dans une grande boîte presque carrée, et son élongation paraîtrait faible à tort. En autorisant la boîte à **pivoter** pour s'ajuster au plus serré, on obtient un descripteur qui ne dépend plus de l'orientation de l'objet. L'élongation devient ainsi invariante par rotation, en plus de l'être par translation et par échelle.

### Exemple numérique

L'élongation sépare d'emblée les grandes familles morphologiques. Un globule rouge sain, en forme de disque, donne E ≈ 1,0. Un bacille — une bactérie en bâtonnet — donne E ≈ 5 à 8. Une fibre ou une fissure dépasse E > 20. En analyse d'images biologiques comme en étude de matériaux, un seuil unique sur E distingue déjà les ronds, les bâtonnets et les filaments.

### Angle mort et piège

L'élongation ne regarde que les dimensions de la boîte ; elle ignore totalement ce qui se passe **à l'intérieur**. Une forme en « L » et une simple diagonale pleine peuvent occuper la même boîte orientée et recevoir la même élongation, alors qu'elles n'ont rien à voir.

Côté code, un piège classique : la fonction `cv2.minAreaRect` renvoie la largeur et la hauteur dans un ordre qui n'est pas garanti — parfois la grande dimension en premier, parfois l'inverse. Il faut donc toujours prendre soi-même le maximum et le minimum, plutôt que de supposer l'ordre. Le descripteur devient aussi instable pour les très petits objets (sous ~5 px), où chaque pixel pèse trop lourd.

### Code
```python
def elongation(mask):
    cnts, _ = cv2.findContours(mask.astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # minAreaRect renvoie le rectangle orienté minimal : centre, (w, h), angle.
    (_, _), (w, h), _ = cv2.minAreaRect(max(cnts, key=cv2.contourArea))
    # On force max/min nous-mêmes : l'ordre de w et h n'est pas fiable.
    return max(w, h) / min(w, h) if min(w, h) else float('inf')
```

---

## 1.3 Excentricité

### Définition
```
e = √(1 − b²/a²) ,  0 ≤ e < 1
```
où a et b sont le grand et le petit demi-axe de l'**ellipse équivalente** : l'ellipse qui « ressemble » le plus à la région, au sens où elle a la même répartition de masse (voir le chapitre Moments).

### L'idée

L'excentricité mesure elle aussi l'allongement, mais d'une façon plus subtile que l'élongation. Au lieu de se contenter d'une boîte englobante, elle prend en compte **la façon dont les pixels sont répartis** dans la forme.

L'image mentale utile est celle d'un nuage de points. Une silhouette, c'est une nuée de pixels ; on peut chercher dans quelle direction ce nuage est le plus étalé, et dans quelle direction il l'est le moins. Si le nuage est aussi étalé dans toutes les directions, il est rond : excentricité nulle. S'il s'étire fortement dans une direction, l'excentricité grimpe vers 1. Le mot vient de l'astronomie : l'orbite d'une planète a une excentricité de 0 si elle est circulaire et s'approche de 1 à mesure qu'elle s'allonge en ovale.

Pour trouver ces deux directions — la plus étalée et la moins étalée — on s'appuie sur une opération mathématique standard appliquée au nuage de pixels. Elle fournit deux nombres, λ₁ et λ₂, qui mesurent l'étalement le long de chacune des deux directions principales (λ₁ étant le plus grand). Il n'est pas indispensable de savoir les calculer à la main ; il faut surtout retenir ce qu'ils représentent : **λ₁, c'est combien la forme s'étale dans sa direction la plus longue ; λ₂, dans sa direction la plus courte**. L'excentricité se déduit alors de leur rapport, e = √(1 − λ₂/λ₁). Quand les deux étalements sont égaux (forme ronde), le rapport vaut 1 et e tombe à 0 ; quand λ₂ devient minuscule face à λ₁ (forme en aiguille), le rapport tend vers 0 et e tend vers 1.

### Différence avec l'élongation

Pourquoi deux descripteurs pour la même idée d'allongement ? Parce qu'ils ne « pèsent » pas la forme de la même manière. L'élongation ne regarde que la boîte ; l'excentricité tient compte de **tous les pixels**. Une forme en croix a une boîte carrée — donc une élongation de 1, qui suggère à tort qu'elle est trapue — mais son excentricité reflète la vraie répartition de sa matière. L'excentricité est aussi plus robuste au bruit : comme elle intègre toute la surface, quelques pixels parasites sur le bord ne la perturbent guère, là où l'élongation, qui dépend des points extrêmes, peut basculer pour un seul pixel mal placé.

### Exemple numérique

Considérons une région deux fois et demie plus étalée dans une direction que dans l'autre : disons λ₁ = 2500 et λ₂ = 400. Alors :

```
e = √(1 − 400/2500) = √0,84 ≈ 0,917
```

Une valeur élevée, cohérente avec une forme nettement allongée — le rapport des longueurs vaut ici √(2500/400) = 2,5.

### Code
```python
from skimage.measure import regionprops, label

# label() numérote les objets distincts du masque ; regionprops calcule
# leurs propriétés. On prend le premier objet et sa propriété 'eccentricity'.
e = regionprops(label(mask))[0].eccentricity
```

---

## 1.4 Solidité

### Définition
```
S = A / A_enveloppe_convexe ,  0 < S ≤ 1
```

### L'idée

La solidité mesure à quel point une forme est « pleine », sans creux ni échancrure. Elle repose sur la notion d'**enveloppe convexe** : c'est la plus petite forme sans creux qui contient l'objet. L'image juste est celle d'un élastique tendu autour de la silhouette : il épouse les parties saillantes mais saute par-dessus les renfoncements, comme la pellicule plastique tendue sur un plat ignore le relief en dessous.

La solidité compare l'aire réelle de l'objet à l'aire de cet élastique. Si la forme n'a aucun creux, l'élastique colle partout et S = 1. Plus la forme a d'échancrures profondes, plus l'élastique laisse de vide en dessous, plus S diminue.

### Ce qu'elle détecte le mieux : les fusions et les appendices

La solidité est l'outil de référence pour repérer deux objets que la segmentation a collés à tort. Deux cellules accolées, segmentées comme une seule, forment un « 8 » : l'élastique tendu autour englobe les deux lobes *et* le creux entre eux, si bien que S tombe autour de 0,85 — nettement sous le S ≈ 0,97 d'une cellule isolée bien ronde. De la même façon, une étoile de mer aux bras écartés ou une feuille dentelée ont une solidité basse, révélatrice de leurs grandes échancrures. Comme la fusion d'objets est un mode d'erreur fréquent de toute segmentation, un seul nombre suffit à le diagnostiquer.

### Exemple numérique

Une forme à deux lobes a une aire A = 3100 px², mais son enveloppe convexe (l'élastique) couvre 3720 px² :

```
S = 3100 / 3720 ≈ 0,833
```

À comparer au S ≈ 0,98 d'un objet plein et convexe. L'écart se voit immédiatement.

### Piège

Attention aux trous internes (un objet en forme d'anneau, par exemple). Selon l'outil, le trou est compté ou non dans l'aire : `cv2.contourArea` mesuré sur le contour extérieur ignore le trou, tandis que `regionprops` compte les pixels réellement allumés. Les deux conventions donnent des solidités différentes pour le même objet. Il faut en choisir une et s'y tenir.

### Code
```python
def solidity(mask):
    cnts, _ = cv2.findContours(mask.astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    # convexHull calcule l'enveloppe convexe (l'« élastique ») du contour.
    ah = cv2.contourArea(cv2.convexHull(c))
    return cv2.contourArea(c) / ah if ah else 0.0
```

---

## 1.5 Convexité

### Définition
```
Cv = P_enveloppe_convexe / P ,  0 < Cv ≤ 1
```

### L'idée et la complémentarité avec la solidité

La convexité reprend l'enveloppe convexe — l'élastique du paragraphe précédent — mais compare les **périmètres** au lieu des aires. L'élastique tendu autour d'une forme a toujours un contour plus court que la forme elle-même, parce qu'il coupe au plus court par-dessus chaque renfoncement et chaque dentelure. Le rapport des deux périmètres mesure donc à quel point le vrai contour fait des détours par rapport au trajet le plus direct.

La différence avec la solidité est importante et vaut la peine d'être saisie. La solidité, qui compare des aires, réagit aux **grandes échancrures** qui retirent beaucoup de surface. La convexité, qui compare des périmètres, réagit à la **rugosité fine du bord** : une multitude de petites dentelures rallonge énormément le contour sans pour autant retirer beaucoup d'aire. D'où deux situations contrastées :

- un contour finement dentelé, mais sans grand creux : convexité basse, solidité haute ;
- une forme en croissant lisse : convexité plutôt haute, solidité basse.

Les deux descripteurs sont complémentaires. On les utilise souvent ensemble pour distinguer « le bord est rugueux » de « la forme est creusée ».

### Exemple numérique

Une particule au bord granuleux a un contour réel P = 380 px (allongé par les aspérités), tandis que son enveloppe convexe ne mesure que P_hull = 322 px :

```
Cv = 322 / 380 ≈ 0,847
```

Sa solidité, elle, reste élevée (S ≈ 0,96) : la matière est compacte, c'est seulement le bord qui est irrégulier. Ce couple de valeurs — convexité basse, solidité haute — est typique d'une surface rugueuse, utile par exemple en contrôle qualité pour distinguer une pièce simplement ébréchée d'une pièce franchement déformée.

### Code
```python
def convexity(mask):
    cnts, _ = cv2.findContours(mask.astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    # Périmètre de l'enveloppe convexe divisé par le périmètre réel.
    return cv2.arcLength(cv2.convexHull(c), True) / cv2.arcLength(c, True)
```

---

## 1.6 Étendue (extent)

### Définition
```
Ext = A / (w_bbox × h_bbox)
```
où la boîte englobante est cette fois **alignée sur les axes** de l'image (elle ne pivote pas).

### L'idée et une limite assumée

L'étendue mesure quelle fraction de sa boîte rectangulaire un objet remplit réellement. C'est le descripteur le moins coûteux de tous : pas besoin d'extraire de contour, il suffit de connaître l'aire et les dimensions de la boîte.

Son défaut est qu'il dépend de l'orientation, justement parce que la boîte ne pivote pas. Un rectangle posé bien à plat remplit sa boîte à ras bord, Ext ≈ 0,95. Le même rectangle incliné à 45° flotte dans une boîte devenue presque carrée et à moitié vide, Ext ≈ 0,5. C'est un problème — mais seulement si l'orientation des objets peut varier librement.

### Quand sa faiblesse devient une force

Lorsque les objets ont une **orientation connue et stable**, ce défaut disparaît et l'étendue devient un classifieur quasi gratuit. C'est le cas des caractères imprimés (alignés horizontalement sur la ligne), des composants posés sur un circuit imprimé, ou des cellules disposées sur une lame orientée. L'étendue est l'exemple type du descripteur théoriquement faible mais contextuellement fort : une connaissance du domaine — ici, « les objets sont droits » — rachète son manque d'invariance. Avant de rejeter un descripteur pour ses limites, il vaut toujours la peine de se demander si le contexte ne les annule pas.

### Code
```python
def extent(mask):
    ys, xs = np.nonzero(mask)            # coordonnées des pixels allumés
    # Aire de la boîte alignée sur les axes (+1 car les bornes sont incluses).
    bb = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
    return mask.sum() / bb               # mask.sum() = nombre de pixels = aire
```

---

## 1.7 Diamètre équivalent

### Définition
```
D_eq = √(4A/π)
```

### L'idée

Ce descripteur répond à la question : si je transformais mon objet en un disque de même aire, quel serait le diamètre de ce disque ? On part de la formule de l'aire d'un disque, A = π(D/2)², et on la retourne pour isoler D. Le résultat est le diamètre équivalent.

Mathématiquement, c'est presque trivial. Mais il rend un service précieux : il convertit une **aire** (en pixels carrés) en une **longueur** (en pixels), ce qui la rend directement comparable aux dimensions physiques une fois la caméra calibrée. Dire « cet objet fait 3100 px² » parle peu ; dire « il fait 63 px de diamètre, soit 31 micromètres » parle tout de suite.

### Application : la granulométrie

Pris isolément, le diamètre équivalent décrit un objet. Mais calculé sur toute une population d'objets, son histogramme devient une **courbe granulométrique** : la distribution des tailles de l'échantillon. C'est un outil de tous les jours en science des matériaux (taille des grains d'un métal), en pharmacie (calibre des particules d'un médicament), en biologie (taille des cellules) ou dans le traitement des minerais. Un seul nombre par objet, mais sa distribution caractérise l'échantillon entier.

### Exemple numérique

Pour un objet de 3100 px² :

```
D_eq = √(4 × 3100 / π) ≈ 62,8 px
```

Avec une caméra calibrée à 0,5 micromètre par pixel, cela fait environ 31 micromètres.

### Code
```python
# 'areas' peut être un tableau NumPy contenant l'aire de chaque objet :
# le calcul s'applique alors à toute la population d'un coup (vectorisé).
d_eq = np.sqrt(4 * areas / np.pi)
```

---

## 1.8 Rectangularité

### Définition
```
R = A / A_minRect ,  0 < R ≤ 1
```
où A_minRect est l'aire du **rectangle orienté d'aire minimale** (la boîte qui pivote pour épouser l'objet, déjà rencontrée pour l'élongation).

### L'idée

La rectangularité mesure à quel point un objet remplit son plus petit rectangle ajusté. Comme la boîte a le droit de pivoter, le descripteur est invariant par rotation. Un vrai rectangle remplit parfaitement sa boîte, R = 1. Une forme aux contours arrondis ou irréguliers laisse des coins vides et fait baisser R.

C'est le descripteur naturel pour repérer les objets manufacturés rectangulaires — cartes, composants électroniques, bâtiments vus du ciel, qui donnent R > 0,9 — et les séparer des formes organiques ou irrégulières, qui restent sous R < 0,75.

### Exemple numérique

Un composant électronique rectangulaire d'aire A = 4800 px² entre dans une boîte orientée de 122 × 42 = 5124 px² :

```
R = 4800 / 5124 ≈ 0,937
```

Très proche de 1, comme attendu. Un galet ou une cellule donnerait plutôt R ≈ 0,76.

### Angle mort

La rectangularité a une cécité instructive : pour **n'importe quelle ellipse**, qu'elle soit presque ronde ou très allongée, R vaut toujours π/4 ≈ 0,785. La raison est que l'aire d'une ellipse est toujours la même fraction de la boîte qui l'entoure, quelle que soit sa forme. Autrement dit, R ne « voit » pas du tout l'allongement : il ne renseigne que sur la façon de remplir les coins. C'est exactement pourquoi on le combine avec l'élongation et la solidité, qui voient ce qu'il ignore.

### Code
```python
def rectangularity(mask):
    cnts, _ = cv2.findContours(mask.astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    (_, _), (w, h), _ = cv2.minAreaRect(c)   # rectangle orienté minimal
    return cv2.contourArea(c) / (w * h) if w * h else 0.0
```

---

## 1.9 Rondeur (roundness)

### Définition
```
Rd = 4A / (π·L_max²)
```
où L_max est le grand axe de l'objet — sa plus grande longueur d'un bord à l'autre.

### L'idée : une circularité qui se moque du bord

La rondeur ressemble à la circularité, mais elle corrige son principal défaut. Rappelons que la circularité C utilise le périmètre P, lequel s'allonge dès que le bord se dentelle : un disque au bord déchiqueté peut voir sa circularité chuter à 0,6 alors qu'il reste globalement rond. La rondeur remplace le périmètre par le grand axe L_max, une mesure de « bout à bout » qui ne se laisse pas troubler par les petites dentelures. Le même disque déchiqueté garde une rondeur Rd ≈ 0,95.

Cette différence rend les deux descripteurs complémentaires et permet une décomposition élégante. La rondeur capte la **forme d'ensemble**, en ignorant le bord. L'écart entre la circularité et la rondeur capte, lui, **l'état du bord** :

```
forme d'ensemble  → Rd       (insensible aux dentelures)
état du bord      → l'écart entre Rd et C
```

### Exemple numérique

Une particule abrasive a une aire A = 3100 px² et un grand axe L_max = 68 px :

```
Rd = 4 × 3100 / (π × 68²) ≈ 0,854
```

Sa rondeur reste donc élevée — la forme d'ensemble est assez compacte. Mais sa circularité, pénalisée par un bord très découpé, ne vaut que C ≈ 0,55. L'écart entre les deux, environ 0,30, **quantifie à lui seul la rugosité du contour**, indépendamment de la forme générale. C'est un indicateur précieux pour distinguer, par exemple, un grain anguleux fraîchement concassé d'un grain roulé et poli par l'érosion — un problème courant en sédimentologie comme dans le contrôle des abrasifs.

### Code
```python
p = regionprops(label(mask))[0]
roundness = 4 * p.area / (np.pi * p.major_axis_length**2)
```

---

## Tableau récapitulatif — ce que chaque descripteur voit et ignore

| Descripteur | Voit surtout | Angle mort | Invariances (T/R/E) |
|---|---|---|---|
| Circularité C | rugosité + élongation (mêlées) | ne sépare pas les deux causes | T, R, E |
| Élongation E | allongement | l'intérieur de la boîte | T, R, E |
| Excentricité e | allongement (par la masse) | rugosité du bord | T, R, E |
| Solidité S | concavités, fusions d'objets | rugosité fine du bord | T, R, E |
| Convexité Cv | rugosité du contour | concavités de masse | T, R, E |
| Étendue Ext | remplissage (orienté) | dépend de l'orientation | T, E (pas R) |
| Diamètre éq. D_eq | taille absolue | la forme | T, R (pas E) |
| Rectangularité R | remplissage des coins | l'élongation | T, R, E |
| Rondeur Rd | forme d'ensemble | l'état du bord | T, R, E |

(T = translation, R = rotation, E = échelle.)

Aucun descripteur ne suffit seul, mais ensemble ils se complètent presque parfaitement. Un classifieur de formes robuste combine en général un descripteur de **forme globale** (rondeur ou excentricité), un de **concavité** (solidité), un de **rugosité** (convexité, ou l'écart entre rondeur et circularité), et au besoin la **taille** (diamètre équivalent). Avec cette poignée de nombres, une silhouette est décrite de façon quasi complète, et un arbre de décision simple atteint souvent plus de 90 % de précision — sans le moindre apprentissage automatique.

---

## Encadré — une invariance est une information qu'on accepte de perdre

Deux descripteurs de ce chapitre ne sont pas pleinement invariants, et ce n'est pas un oubli :

```
Étendue           → non invariante par rotation : elle EXPLOITE l'orientation connue
Diamètre équiv.   → non invariant par l'échelle : il PORTE l'information de taille
```

Ce sont des choix délibérés. Une invariance rend un descripteur insensible à une transformation — mais le rendre insensible, c'est aussi le rendre **aveugle** à l'information que cette transformation porte. Rendre la circularité invariante par l'échelle revient à décider que la taille ne compte pas pour le problème. Garder le diamètre équivalent dépendant de l'échelle revient à décider, au contraire, qu'elle compte. La bonne question de conception n'est donc jamais « ce descripteur est-il invariant ? », mais « **à quelles transformations dois-je être aveugle pour la tâche que je traite ?** ».

C'est la même leçon qui reviendra tout au long de l'ouvrage. De même qu'une distance encode une hypothèse sur ce qui se ressemble, qu'un filtre encode un a priori sur le signal, un descripteur encode un **point de vue** : il décide de ce qui mérite d'être vu et de ce qui peut être ignoré. Choisir ses descripteurs, c'est déclarer ce qui, dans une forme, fait sens pour le problème qu'on cherche à résoudre.
