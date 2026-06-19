# Chapitre 1 — Décrire une forme avec des nombres

![Un inspecteur des douanes tamponne des créatures de toutes formes sur un tapis roulant, une fiche chiffrée à la main](../figures/fig_ch1_couverture.jpg)
*Trier des milliers de formes sans jamais les regarder une à une : il faut d'abord les réduire à quelques nombres bien choisis. Chaque nombre voit une chose et en ignore une autre.*

---

Un pipeline de vision par ordinateur commence presque toujours par découper les objets du fond — la silhouette d'une cellule, d'une pièce mécanique, d'un caractère imprimé, isolée comme on découperait une forme aux ciseaux dans une feuille. Vient ensuite la vraie question : comment trier, comparer et classer ces objets par milliers, sans qu'un humain les regarde un par un ? Une machine ne sait pas dire « cet objet est rond » ou « celui-là est allongé ». Il faut lui donner des nombres.

C'est le rôle d'un **descripteur de forme** : un nombre, ou une petite poignée de nombres, qui résume une silhouette selon un aspect précis. Rond, étiré, troué, dentelé — chaque trait géométrique a son descripteur.

Le fil de ce chapitre tient en une phrase : **chaque descripteur choisit ce qu'il voit et ce qu'il oublie**. La circularité repère un bord rugueux mais ignore l'orientation. La rectangularité voit comment les coins sont remplis mais reste aveugle à l'allongement. Comprendre un descripteur, c'est d'abord connaître son angle mort — ce qu'il refuse de voir.

Deux mots de vocabulaire avant de commencer. Une **région** désigne l'ensemble des pixels d'un objet, livrés sous forme de **masque binaire** : une image où chaque pixel vaut 1 s'il appartient à l'objet, 0 sinon. On note **A** l'aire de la région (son nombre de pixels) et **P** son périmètre (la longueur de son contour).

> La plupart des descripteurs de ce chapitre sont des **rapports** de deux grandeurs. C'est un choix : un rapport efface la taille absolue et ne garde qu'une proportion, ce qui rend la mesure insensible à l'échelle. Voir la forme `a/b`, annexe C.

---

## 1.1 — Circularité : à quel point est-ce rond ?

> *Le ballon de baudruche qui cherche la forme la plus économe*

![fig_ch1_obs1](../figures/fig_ch1_obs1_circ_roundness.pdf)

### L'intention

On veut séparer automatiquement les objets ronds des objets allongés ou déchiquetés. En reconnaissance de caractères, distinguer un « O » d'un « I ». En biologie, repérer les cellules saines (rondes) parmi des débris. Il nous faut un nombre qui vaut son maximum pour un cercle parfait, et qui chute dès que la forme s'éloigne du disque.

### La forme recherchée

Le cercle a une propriété remarquable : pour une longueur de contour donnée, c'est lui qui enferme le plus de surface. Un ballon de baudruche qu'on gonfle prend spontanément une forme ronde, parce que c'est la façon la plus économe de contenir l'air avec la peau de plastique disponible. Cette propriété s'appelle l'**inégalité isopérimétrique**.

On cherche donc un nombre qui compare l'aire à la longueur du contour, et qu'on cale pour qu'il vaille exactement **1 au cercle** et moins partout ailleurs.

### La formule

```
C = 4 · π · A / P²
```

Le facteur `4π` n'a rien d'arbitraire : il est choisi précisément pour que le disque tombe sur 1. Pour un cercle de rayon r, on a `A = πr²` et `P = 2πr`, et la formule donne `4π · πr² / (2πr)² = 1`. Toute autre forme, plus étirée ou plus froissée, a relativement trop de contour pour son aire, et C descend vers 0. ∎

### Ce qu'elle mesure, et son angle mort

La circularité baisse pour **deux raisons** que rien ne permet de distinguer : la forme s'allonge, ou son bord se dentelle. Une forme lisse mais en cigare, et un disque parfait au bord en lame de scie, peuvent décrocher la même valeur. La circularité mêle ces deux causes en un seul nombre — c'est son angle mort. (La rondeur, §1.9, séparera les deux.)

Elle reste en revanche insensible à la translation, à la rotation et à l'échelle : un cercle est un cercle, où qu'il soit, quelle que soit sa taille.

### Exemple

Un « O » bien formé donne environ `C ≈ 0,9`. Un « I » modélisé par une barre de 40 px de haut sur 4 de large : `C = 4π · 160 / 88² ≈ 0,26`. Un simple seuil à 0,5 sépare d'emblée les caractères ronds des caractères linéaires.

### Le périmètre en escalier : pourquoi la géométrie discrète fausse la mesure

Sur une grille de pixels, l'affichage d'un cercle ressemble à un escalier. Mesurer la longueur de ce contour en sommant simplement les bords des pixels introduit une erreur systématique majeure. En effet, si l'on parcourt une diagonale en escalier (droite-haut, droite-haut), le trajet mesuré est la somme des pas horizontaux et verticaux (longueur 2), alors que la diagonale réelle mesure la racine carrée de 2, soit environ 1,414. L'erreur est de plus de 40 %. 

Même en augmentant la résolution de l'image à l'infini (en rendant les pixels infiniment petits), l'escalier se resserre mais sa longueur totale ne converge jamais vers le périmètre du cercle réel : elle reste surestimée d'environ 27 %. C'est le paradoxe géométrique du périmètre discret. Si l'on calcule la circularité avec ce périmètre naïf, le cercle parfait obtient un score de `C ≈ 0,79` au lieu de 1,0. Pour corriger cela, on utilise des algorithmes d'estimation de périmètre (comme la formule de Freeman ou des approximations polygonales) qui lissent les marches d'escalier en mesurant des diagonales.

### Paramètres opérationnels (VNStudio / Python)

Dans le nœud `Find Contours` (ou en Python via `cv2.findContours`), le lecteur configure les paramètres opérationnels critiques suivants :

*   **Mode de récupération des contours (`mode`)** :
    *   Dans VNStudio, ce paramètre correspond au menu déroulant **Retrieval Mode** ; en Python (OpenCV), il se nomme `mode` dans `cv2.findContours`.
    *   `cv2.RETR_EXTERNAL` : Ne trouve que les contours extérieurs de chaque objet. C'est le mode le plus robuste pour calculer des descripteurs de forme globaux, car il ignore tous les trous internes.
    *   `cv2.RETR_LIST` : Extrait tous les contours (extérieurs et intérieurs) de manière plate, sans aucune hiérarchie.
    *   `cv2.RETR_TREE` : Reconstruit l'arbre complet des contours imbriqués les uns dans les autres (les trous dans les objets, et les sous-objets dans les trous). Indispensable si l'on cherche à analyser la structure imbriquée des silhouettes.
*   **Méthode d'approximation (`method`)** :
    *   Dans VNStudio, ce paramètre correspond au champ **Contour Approximation** ; en Python (OpenCV), il se nomme `method` dans `cv2.findContours`.
    *   `cv2.CHAIN_APPROX_NONE` : Conserve la liste brute de tous les pixels du contour. Très précis mais extrêmement lourd en mémoire.
    *   `cv2.CHAIN_APPROX_SIMPLE` : Compresse les segments horizontaux, verticaux et diagonaux en ne conservant que leurs extrémités. Par exemple, un contour rectangulaire n'est stocké que par ses 4 sommets au lieu de centaines de pixels. C'est le choix recommandé pour optimiser les performances.
*   **Tolérance d'approximation (`epsilon` ou approximation polygonale)** :
    *   Dans VNStudio, ce paramètre correspond au curseur **Simplification (Epsilon)** ; en Python (OpenCV), c'est la valeur `epsilon` passée à la fonction `cv2.approxPolyDP`.
    *   Ce paramètre (exprimé en pixels ou en pourcentage du périmètre) règle la simplification de Douglas-Peucker. Une valeur de `0` conserve le contour pixelisé exact. Augmenter `epsilon` lisse le contour en éliminant les petites variations. Une valeur trop élevée transformera un cercle en simple triangle ou carré.

### Dans VNStudio

Dans votre canvas :
`Image Source` ──> `Threshold` ──> `Find Contours` ──> `Shape Descriptors` ──> `Output Display`.

Le nœud `Find Contours` applique les paramètres ci-dessus. Le nœud `Shape Descriptors` lit les coordonnées des contours simplifiés pour en extraire l'aire, le périmètre corrigé et la circularité dans l'inspecteur, permettant de router automatiquement les objets selon les critères dimensionnels choisis.

**Exercice de dépannage :** L'exercice consiste à connecter une image d'un disque parfait au nœud `Find Contours` et à régler le paramètre **Simplification (Epsilon)** sur une valeur très élevée (ex. : 20 pixels). Le lecteur constate dans l'inspecteur la valeur de la circularité : elle s'effondre de 1.0 à environ 0.65, car le cercle parfait s'est transformé en un simple polygone grossier. Cela illustre comment une approximation trop agressive détruit la signature géométrique d'une forme.

---

## 1.2 — Élongation : trapu ou étiré ?

> *Le plus petit carton dans lequel l'objet rentre, quitte à pencher la tête*

### L'intention

En microscopie, on veut séparer d'un coup d'œil les bactéries rondes des bâtonnets et des longues fibres. Une mesure grossière mais immédiate de l'allongement suffit.

### La forme recherchée

On enferme l'objet dans le plus petit rectangle possible, puis on regarde le rapport de ses deux côtés. Détail décisif : ce rectangle doit pouvoir **pivoter** librement pour épouser la forme au plus près. Un crayon posé en diagonale, enfermé dans une boîte strictement horizontale, donnerait une boîte presque carrée et une mesure trompeuse. En autorisant la boîte à pencher la tête, on rend la mesure indépendante de l'orientation.

### La formule

```
E = L_max / L_min
```

où `L_max` et `L_min` sont la longueur et la largeur de la **boîte englobante orientée**. Un rapport, là encore : il efface la taille et ne garde que la proportion. ∎

### Ce qu'elle mesure, et son angle mort

L'élongation dit si la forme générale est trapue ou étirée, rien de plus. Son angle mort est béant : elle ignore tout ce qui se passe *à l'intérieur* de la boîte. Une équerre en « L » et une barre en diagonale peuvent partager la même boîte orientée, donc la même élongation, alors que leur matière est répartie de façons radicalement différentes.

### Exemple

Un globule rouge : `E ≈ 1,0`. Une bactérie en bâtonnet : `E ≈ 5 à 8`. Une fibre : souvent `E > 20`.

### Subtilité d'implémentation

`cv2.minAreaRect` renvoie les deux dimensions de la boîte dans un ordre quelconque. Un tri explicite du max et du min est nécessaire avant de calculer le rapport, sans quoi l'élongation peut sortir inversée.

### Dans VNStudio

Canvas : `Find Contours` → `Min Area Rect` → `Shape Descriptors`. La boîte orientée est dessinée en surimpression sur l'objet, ce qui rend l'inclinaison visible directement.

---

## 1.3 — Excentricité : l'allongement vu par la masse

> *Un nuage de points, et la direction où il s'étire le plus*

### L'intention

L'élongation se laisse berner par un seul pixel de bruit, qui suffit à élargir la boîte englobante. On veut la même information — l'allongement — mais mesurée sur la répartition de *tous* les pixels, pour qu'un point aberrant ne pèse presque rien.

### La forme recherchée

L'image mentale utile est celle d'un **nuage de points** : une silhouette numérique n'est qu'un amas de pixels. On cherche la direction dans laquelle ce nuage est le plus étalé, et la direction perpendiculaire où il l'est le moins. Un nuage parfaitement circulaire s'étale pareil dans toutes les directions ; un nuage en fin pinceau s'étire dans une seule.

L'outil mathématique qui analyse ce nuage en sort deux nombres, `λ₁` et `λ₂`. Inutile de maîtriser l'algèbre matricielle qui les calcule : visuellement, **`λ₁` mesure l'envergure du nuage dans sa direction la plus longue, et `λ₂` dans sa direction la plus courte**. Ce sont les deux « rayons » d'une ellipse qui résumerait le nuage.

### La formule

```
e = √(1 − λ₂ / λ₁)
```

Le rapport `λ₂/λ₁` compare les deux envergures. S'il vaut 1 (nuage rond), e tombe à 0. S'il tend vers 0 (nuage en aiguille), e tend vers 1. L'excentricité varie donc entre 0 (cercle) et 1 (segment). ∎

### Différence avec l'élongation

Pourquoi deux outils pour mesurer l'allongement ? Parce qu'ils ne regardent pas la même chose. Une forme en croix a une boîte englobante carrée — élongation 1, l'air trapu — mais l'excentricité, en pesant la répartition réelle des pixels des deux barres, en révèle la vraie géométrie. Et surtout, l'excentricité est **stable** : un pixel de bruit isolé change la boîte de l'élongation, mais ne déplace presque pas la masse globale.

### Exemple

Un nuage deux fois et demie plus étalé en longueur (`λ₁ = 2500`) qu'en largeur (`λ₂ = 400`) : `e = √(1 − 400/2500) = √0,84 ≈ 0,916`.

### Dans VNStudio

Canvas : `Find Contours` → `Region Properties`. Le nœud calcule l'ellipse d'inertie et l'affiche par-dessus l'objet ; l'inspecteur donne l'excentricité et l'orientation.

---

## 1.4 — Solidité : la forme est-elle pleine ?

> *La pellicule plastique tendue qui ignore les creux*

![fig_ch1_obs2](../figures/fig_ch1_obs2_solidity_convexity.pdf)

### L'intention

Quand deux cellules se touchent, le traitement d'image les fond parfois en une seule forme en « 8 ». On veut détecter ces fusions accidentelles — repérer qu'une forme a un creux profond, là où on attendait un objet plein.

### La forme recherchée

Le concept clé est l'**enveloppe convexe** : la pellicule qu'on tendrait autour de l'objet. Elle s'appuie sur toutes les parties saillantes et passe au-dessus des creux sans jamais y entrer, comme un film plastique tiré sur un objet bosselé. Là où l'objet a un renfoncement, le film reste tendu droit par-dessus, emprisonnant un vide.

On compare alors la surface réelle de l'objet à la surface enfermée sous cette enveloppe. Sans creux, les deux coïncident. Avec un grand renfoncement, l'enveloppe couvre beaucoup de vide en plus.

### La formule

```
S = A / A_convexe
```

Sans aucune cavité, l'objet touche son enveloppe convexe partout et `S = 1`. Plus les creux sont profonds, plus S s'effondre. ∎

### Ce qu'elle détecte le mieux

C'est le descripteur des fusions d'objets. Deux cellules collées en « 8 » : l'enveloppe convexe recouvre le creux central, ce vide fait chuter la solidité autour de 0,85, bien en dessous de ce qu'on attend d'une cellule isolée. Son angle mort : la rugosité fine du bord, qui retire très peu de surface et la laisse donc presque insensible.

### Exemple

Une forme à deux lobes : aire `A = 3100 px²`, enveloppe convexe `A_convexe = 3720 px²`. Solidité `S = 3100 / 3720 ≈ 0,83`.

### Différence d'implémentation

Les trous entièrement internes — l'intérieur d'un anneau, par exemple — sont comptés dans la surface ou non selon la bibliothèque. Le résultat de la solidité en dépend, et la convention employée doit être vérifiée avant d'interpréter les valeurs.

### Dans VNStudio

Canvas : `Find Contours` → `Convex Hull` → `Shape Descriptors`. L'enveloppe convexe se superpose en pointillés sur l'objet, et le creux comblé saute aux yeux.

---

## 1.5 — Convexité : la même enveloppe, vue par le périmètre

> *Le chemin direct par-dessus les creux, contre le contour qui épouse tout*

### L'intention

On veut maintenant distinguer un objet simplement abîmé en surface (un galet ébréché, au bord rugueux mais à la forme intacte) d'un objet vraiment déformé. La solidité, qui regarde les surfaces, n'y est pas sensible. Il faut regarder le contour.

### La forme recherchée

On reprend l'**enveloppe convexe** du §1.4, mais on compare cette fois les **périmètres** plutôt que les aires. L'enveloppe, qui va au plus direct par-dessus les creux, a toujours un contour plus court que la silhouette réelle, laquelle doit épouser tous les détours. Une multitude de minuscules dentelures rallonge énormément le contour réel sans presque rien retirer à la surface sous l'enveloppe — c'est exactement ce que la convexité capte et que la solidité manque. ∎

### La formule

```
Cv = P_convexe / P
```

### Le binôme avec la solidité

Les deux descripteurs travaillent en équipe, et c'est leur combinaison qui informe :

- Un contour très granuleux mais sans gros renfoncement : **convexité basse, solidité haute** → un bord abîmé, une structure saine.
- Un croissant de lune parfaitement lisse : **convexité haute, solidité basse** → un bord net, mais une grande concavité de masse.

### Exemple

Un galet ébréché : contour réel tortueux `P = 380 px`, enveloppe directe `P_convexe = 322 px`. Convexité `Cv = 322 / 380 ≈ 0,84`. Couplée à une solidité élevée, cette valeur dit à la machine : surface détériorée, structure intacte.

### Dans VNStudio

Canvas : `Find Contours` → `Convex Hull` → `Shape Descriptors`. Mêmes nœuds qu'en 1.4 ; il suffit de lire la sortie convexité au lieu de la solidité, les deux venant de la même enveloppe.

---

## 1.6 — Étendue : remplir une boîte qui ne tourne pas

> *Le rectangle rigide, aligné sur l'image, qui assume sa naïveté*

![fig_ch1_obs3](../figures/fig_ch1_obs3_extent_rect.pdf)

### L'intention

Sur une chaîne de tri où les composants arrivent toujours dans la même orientation, on veut une mesure de remplissage instantanée, sans le coût d'extraire et d'analyser des contours complexes.

### La forme recherchée

On enferme l'objet dans sa boîte englobante **strictement alignée** sur l'image — aucune rotation permise — et on regarde quelle fraction de cette boîte il occupe. C'est rapide, parce qu'il suffit des coordonnées extrêmes de l'objet. ∎

### La formule

```
Ext = A / (W_boîte · H_boîte)
```

### Sa force et sa faiblesse assumées

Un rectangle posé à plat remplit sa boîte à presque 100 % (`Ext ≈ 0,95`). Inclinez-le à 45° : la boîte horizontale-verticale qui le contient devient bien plus grande, à moitié vide (`Ext ≈ 0,5`). L'étendue change donc radicalement si l'objet tourne — elle n'est invariante ni à la rotation. Elle ne vaut que là où l'orientation est fixe et connue : tri de composants alignés, lecture de caractères sur une même ligne.

### Dans VNStudio

Canvas : `Find Contours` → `Bounding Rect` → `Shape Descriptors`. La boîte droite s'affiche sur l'objet ; on voit immédiatement l'espace vide se creuser dès qu'une pièce arrive de travers.

---

## 1.7 — Diamètre équivalent : convertir une aire en taille

> *Refondre l'objet en un disque, et mesurer ce disque*

### L'intention

En granulométrie — classer des grains de métal, des cellules, du sable par taille — on veut transformer une aire en pixels en une longueur physique unique, comparable et convertible en micromètres.

### La forme recherchée

L'idée : si on refondait la matière de l'objet en un disque parfait de même surface, quel serait son diamètre ? On part de la formule de l'aire du disque et on isole le diamètre. Une aire (en pixels carrés) devient ainsi une longueur (en pixels), qu'on convertit ensuite en taille réelle dès qu'on connaît le calibrage de la caméra. ∎

### La formule

```
D_eq = √(4 · A / π)
```

### Exemple

Un grain de sable à `A = 3100 px²` sous un microscope réglé à 0,5 µm/pixel : `D_eq = √(4 · 3100 / π) ≈ 62,8 px`, soit environ **31 µm** de diamètre réel. C'est ce descripteur qui dresse les courbes granulométriques.

Contrairement aux précédents, le diamètre équivalent **dépend de l'échelle** — c'est tout son intérêt. Il mesure une taille absolue, là où les rapports l'effaçaient.

### Dans VNStudio

Canvas : `Find Contours` → `Shape Descriptors` (sortie diamètre équivalent) → `Scale Calibration`. Le nœud de calibrage convertit les pixels en unité physique si la résolution est renseignée.

---

## 1.8 — Rectangularité : remplir une boîte qui, elle, tourne

> *Le carton ajusté au plus près, et la part de vide qui reste*

### L'intention

On veut reconnaître les formes manufacturées — cartes, composants, bâtiments vus du ciel — qui remplissent bien un rectangle, quelle que soit leur inclinaison.

### La forme recherchée

Comme l'étendue (§1.6), on mesure un taux de remplissage de boîte. Mais cette fois la boîte est **orientée** : elle pivote pour s'ajuster au plus près de l'objet, comme en 1.2. On regarde quelle fraction de cette boîte ajustée l'objet occupe vraiment. ∎

### La formule

```
R = A / A_minRect
```

### Son angle mort surprenant

La rectangularité est totalement aveugle à l'allongement. Prenez n'importe quelle ellipse — un ovale presque rond ou un ovale étiré comme un lacet : elle remplit toujours sa boîte ajustée à la même proportion, `π/4 ≈ 0,785`. La rectangularité ne lit que l'occupation des **coins**, pas les proportions d'ensemble. Un descripteur qui vaut 0,785 signale donc « bords arrondis, coins vides », sans rien dire de la forme générale.

### Exemple

Un composant rectangulaire `A = 4800 px²` dans une boîte ajustée de 122 × 42 px (5124 px²) : `R = 4800 / 5124 ≈ 0,93` — une forme franchement rectangulaire.

### Dans VNStudio

Canvas : `Find Contours` → `Min Area Rect` → `Shape Descriptors`. La boîte orientée s'affiche par-dessus l'objet ; coins vides ou remplis se lisent au premier regard.

---

## 1.9 — Rondeur : la forme d'ensemble, sans le bruit du bord

> *La circularité débarrassée de ce qui la trompait*

![fig_ch1_obs1](../figures/fig_ch1_obs1_circ_roundness.pdf)

### L'intention

La circularité (§1.1) avait un défaut : un bord dentelé la faisait chuter, même quand la forme globale restait bien ronde. On veut mesurer la rondeur **d'ensemble**, en ignorant les aspérités du contour.

### La forme recherchée

Le problème venait du périmètre, qui explose au moindre détail du bord. On le retire de l'équation et on le remplace par le **grand axe** de la forme — sa plus grande dimension, mesurée d'une extrémité à l'autre. Cette mesure de bout en bout se moque des petites dentelures : elle ne voit que l'enveloppe globale. ∎

### La formule

```
Rd = 4 · A / (π · L_max²)
```

### Ce que l'écart avec la circularité révèle

Un disque dentelé garde une rondeur élevée (`Rd ≈ 0,95`) tandis que sa circularité s'effondre. C'est tout l'intérêt de garder les deux : leur **différence** isole la rugosité du bord, débarrassée de la forme d'ensemble.

### Exemple

Une particule abrasive : `A = 3100 px²`, grand axe `L_max = 68 px`. Rondeur `Rd = 4 · 3100 / (π · 68²) ≈ 0,85` — forme globalement compacte. Mais sa circularité ne vaut que `C ≈ 0,55`, à cause du bord déchiqueté. La soustraction `0,85 − 0,55 = 0,30` donne une mesure pure de l'état du bord, indépendante de la silhouette.

### Dans VNStudio

Canvas : `Find Contours` → `Shape Descriptors`. Les sorties circularité et rondeur sont disponibles côte à côte ; un nœud `Math` peut calculer leur différence pour isoler la rugosité.

---

## Tableau récapitulatif — ce que chaque descripteur voit et ignore

| Descripteur | Voit surtout | Angle mort | Invariances (T / R / E) |
|---|---|---|---|
| Circularité C | rugosité + élongation (mêlées) | ne sépare pas les deux causes | T, R, E |
| Élongation E | allongement | l'intérieur de la boîte | T, R, E |
| Excentricité e | allongement (par la masse) | rugosité du bord | T, R, E |
| Solidité S | concavités, fusions d'objets | rugosité fine du bord | T, R, E |
| Convexité Cv | rugosité du contour | concavités de masse | T, R, E |
| Étendue Ext | remplissage (boîte droite) | dépend de l'orientation | T, E (pas R) |
| Diamètre éq. D_eq | taille absolue | la forme | T, R (pas E) |
| Rectangularité R | remplissage des coins | l'élongation | T, R, E |
| Rondeur Rd | forme d'ensemble | l'état du bord | T, R, E |

*(T = translation, R = rotation, E = échelle.)* Aucun descripteur ne suffit seul. C'est en les combinant — l'un pour l'allongement, l'autre pour le bord, un troisième pour les fusions — qu'on cerne une forme presque parfaitement.

---

## Encadré final — une invariance est une information qu'on accepte de perdre

Une invariance rend un descripteur aveugle à une transformation. C'est utile quand cette transformation ne porte aucune information pour la tâche, coûteux quand elle en porte. La circularité ignore la taille : l'utiliser, c'est déclarer que la dimension n'a aucune importance pour le problème posé. Refuser le diamètre équivalent parce qu'il varie avec la taille, c'est oublier qu'il a été conçu exactement pour ça. La bonne question de conception n'est donc pas « ce descripteur est-il invariant ? » mais « à quoi dois-je être aveugle pour cette tâche ? ».

On retrouvera cette question à chaque chapitre, sous d'autres noms. Un filtre garde une fréquence et en jette une autre ; une distance déclare ce qui se ressemble ; une caméra projette et sacrifie la profondeur. Un descripteur garde une chose et en jette une autre — choisir ses descripteurs, c'est dire ce qui, dans une forme, compte pour le problème qu'on traite.

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch1_couverture` | chapeau | Illustration humoristique : inspecteur tamponnant des créatures de formes variées sur un tapis roulant, fiche chiffrée en main | JPG/PNG |
| `fig_ch1_obs1_circ_roundness` | 1.1 / 1.9 | Déjà existant (PDF) : disque lisse vs disque dentelé, circularité vs rondeur | — |
| `fig_ch1_01_isoperimetrique` | 1.1 | Schéma : même périmètre, aires croissantes du segment au cercle ; courbe de C qui monte vers 1 | SVG |
| `fig_ch1_02_box_oriented` | 1.2 | Crayon en diagonale : boîte droite (grande, fausse) vs boîte orientée (ajustée) | SVG |
| `fig_ch1_03_nuage_points` | 1.3 | Nuage de pixels avec ses deux axes λ₁, λ₂ ; cercle (e=0) vs aiguille (e→1) | SVG |
| `fig_ch1_obs2_solidity_convexity` | 1.4 / 1.5 | Déjà existant (PDF) : forme en « 8 » et son enveloppe convexe | — |
| `fig_ch1_obs3_extent_rect` | 1.6 / 1.8 | Déjà existant (PDF) : boîte droite vs boîte orientée, taux de remplissage | — |
| `fig_ch1_04_diametre_eq` | 1.7 | Objet irrégulier « refondu » en disque de même aire | SVG |
| `fig_ch1_05_rect_ellipse` | 1.8 | Plusieurs ellipses d'allongements variés, toutes à R = π/4 dans leur boîte | SVG |
| `fig_ch1_pipeline` | global | Déjà existant (PDF + .vn) : pipeline complet de descripteurs dans VNStudio | — |
