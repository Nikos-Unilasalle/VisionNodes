# Chapitre — Descripteurs de forme : dérivations et exemples

Une fois qu'un objet a été isolé dans une image — sa silhouette découpée du fond, comme on découperait une forme aux ciseaux dans une feuille — comment le décrire avec des nombres plutôt qu'avec des mots 1 ? On voudrait dire « cet objet est rond », « celui-là est allongé », « celui-ci a un bord déchiqueté », mais le faire de façon que la machine puisse trier, comparer et classer des milliers d'objets sans jamais les regarder 1\. C'est le rôle d'un descripteur de forme : un nombre, ou une poignée de nombres, qui résume une silhouette selon un aspect précis 1\.  
Ce chapitre construit les descripteurs géométriques essentiels. Le fil conducteur tient en une phrase : **chaque descripteur choisit ce qu'il voit et ce qu'il oublie** 2\. La circularité repère un bord rugueux mais ignore l'orientation ; la rectangularité voit comment les coins sont remplis mais ignore l'allongement 2\. Comprendre un descripteur, c'est d'abord connaître son angle mort 2\.  
Quelques mots de vocabulaire avant de commencer. Une **région** désigne l'ensemble des pixels appartenant à un objet, fournis sous forme de **masque binaire** : une image où chaque pixel vaut 255 (ou 1\) s'il fait partie de l'objet et 0 sinon 3\. On notera **A** l'aire de la région — son nombre de pixels — et **P** son périmètre, la longueur de son contour 3\.

#### 1.1 Circularité (compacité)

**Définition**  
`C = (4 * π * A) / P²`  
**L'idée et dérivation**La circularité répond à une question simple : à quel point cette forme ressemble-t-elle à un disque 4 ? Elle compare l'aire d'un objet à la longueur de son contour 4\. L'intuition visuelle à retenir est qu'un cercle est la forme la plus « économe » qui soit : pour une quantité de contour donnée, c'est lui qui enferme le plus de surface 4\. Un ballon de baudruche gonflé prend spontanément une forme ronde, car c'est la façon la plus efficace de contenir l'air avec la surface de plastique disponible 4\.  
Cette propriété géométrique s'appelle l'inégalité isopérimétrique 5\. La formule est spécifiquement construite pour que **C vaille exactement 1 pour un cercle parfait**, et moins de 1 pour toute autre forme 5\. En effet, pour un cercle de rayon r, l'aire vaut A \= πr² et le périmètre P \= 2πr 5\. En remplaçant dans la formule, on obtient (4 \* π \* πr²) / (4π²r²), ce qui se simplifie pour donner exactement 1 5, 6\. Plus une forme s'étire ou se froisse, plus la valeur de C chute vers 0 5\.  
**Ce qu'elle mesure (et son angle mort)**La circularité diminue pour deux raisons distinctes : quand la forme s'allonge, et quand son contour se dentelle 6\. Son angle mort réside dans son incapacité à faire la différence entre les deux 6\. Une forme lisse mais allongée (comme un cigare) et un disque parfait mais au bord très découpé (comme une scie circulaire) peuvent obtenir la même valeur 6\. Elle possède cependant trois invariances fondamentales : elle est insensible à la translation, à la rotation et au changement d'échelle 7\.  
**Exemple numérique**Dans un système de reconnaissance de texte, un « O » bien formé donne environ C ≈ 0,9 8\. Comparons avec un « I », modélisé par une barre de 40 pixels de haut et 4 de large : C \= (4 \* π \* 160\) / 88² ≈ 0,26 8\. Ce simple seuillage sépare d'emblée les caractères ronds des caractères linéaires 8\.  
**Piège d'implémentation**Sur une grille de pixels, le périmètre est systématiquement surestimé si on le mesure de façon naïve 9\. La raison est purement visuelle : le bord d'un cercle sur un écran d'ordinateur est fait de petites marches d'escalier (les pixels) 9\. Le chemin en escalier est toujours plus long que la courbe lisse qu'il tente de dessiner 9\. Pour un cercle discret, cette erreur gonfle le périmètre mesuré d'environ 27 %, ce qui écrase la circularité et donne C ≈ 0,79 au lieu de 1 9, 10\. Il faut donc toujours préciser la méthode de calcul du périmètre utilisée pour garantir des résultats reproductibles 10\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `A = cv2.contourArea(cnt)`  
    `P = cv2.arcLength(cnt, True)`  
    `C = (4 * np.pi * A) / (P * P) if P > 0 else 0.0`  
    `out_a = {"Aire": float(A), "Perimetre": float(P), "Circularite": float(C)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.2 Élongation (rapport d'aspect)

**Définition**  
`E = L_max / L_min`  
où L\_max et L\_min sont la longueur et la largeur de la **boîte englobante orientée** 11\.  
**L'idée et invariances**L'élongation évalue de manière rudimentaire à quel point un objet est étiré. On enferme l'objet dans le plus petit rectangle possible 11\. Le point crucial est d'autoriser ce rectangle à **pivoter** librement pour épouser la forme au plus près 11\. Si le rectangle restait strictement horizontal et vertical, un crayon posé en diagonale nécessiterait une grande boîte presque carrée, faussant complètement la mesure 11\. En permettant la rotation de la boîte, l'élongation devient invariante à l'orientation de l'objet 11\.  
**Ce qu'elle mesure (et son angle mort)**Ce descripteur indique si la forme globale est trapue ou allongée. Toutefois, son angle mort est béant : l'élongation ignore totalement ce qui se passe à l'intérieur de la boîte 12\. Une équerre (en forme de « L ») et une barre en diagonale peuvent partager exactement la même boîte orientée, et donc la même élongation, alors que leurs répartitions de matière sont complètement différentes 12\.  
**Exemple numérique**Un globule rouge, de forme ronde, présente une élongation E ≈ 1,0 12\. Une bactérie en forme de bâtonnet donne E ≈ 5 à 8, et une fibre dépasse souvent E \> 20 12\.  
**Piège d'implémentation**La fonction cv2.minAreaRect renvoie les deux dimensions de la boîte sans garantir un ordre précis 13\. Il est impératif de trier manuellement le résultat pour obtenir le maximum et le minimum 13\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `rect = cv2.minAreaRect(cnt)`  
    `# rect[14] contient les dimensions de la boîte (largeur, hauteur)`  
    `L_max = max(rect[14])`  
    `L_min = min(rect[14])`  
    `E = L_max / L_min if L_min > 0 else 0.0`  
    `out_a = {"Elongation": float(E)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.3 Excentricité

**Définition**  
`e = √(1 - (λ₂ / λ₁))`  
**L'idée**L'excentricité mesure également l'allongement, mais d'une façon beaucoup plus fine que l'élongation 15\. Au lieu de se limiter aux bords extérieurs extrêmes, elle prend en compte la position de chaque pixel de l'objet 15\.  
L'image mentale utile pour comprendre cette notion est celle d'un nuage de points 15\. Une silhouette numérique est simplement un amas de pixels. On peut chercher à observer dans quelle direction ce nuage est le plus étalé, et dans quelle direction perpendiculaire il l'est le moins 15\. Si le nuage est parfaitement circulaire, il s'étale de façon égale partout : son excentricité est nulle 15\. S'il s'allonge en un fin pinceau, son excentricité tend vers 1 15\.  
L'outil mathématique qui analyse ce nuage extrait deux nombres fondamentaux, notés **λ₁** et **λ₂**. Il n'est pas nécessaire de maîtriser l'algèbre matricielle (la « matrice de covariance ») qui les calcule pour les comprendre 16\. Visuellement, c'est très simple : **λ₁ quantifie l'envergure du nuage dans sa direction la plus longue, et λ₂ l'envergure dans sa direction la plus courte** 16\. La formule compare simplement ces deux étalements.  
**Différence avec l'élongation**Pourquoi avoir deux outils pour mesurer l'allongement ? Parce qu'une forme en croix possède une boîte englobante carrée, lui donnant une élongation de 1 (elle semble trapue). Pourtant, l'excentricité, en pesant la répartition réelle de tous les pixels (les deux barres de la croix), dévoilera une autre géométrie 17\. De plus, l'excentricité est beaucoup plus stable : un pixel de bruit isolé modifiera la taille de la boîte englobante de l'élongation, mais aura très peu d'impact sur la masse globale évaluée par l'excentricité 17\.  
**Exemple numérique**Pour un nuage de pixels qui est deux fois et demie plus étalé dans le sens de la longueur (λ₁ \= 2500\) que dans la largeur (λ₂ \= 400), l'excentricité donne e \= √(1 \- 400/2500) \= √(1 \- 0.16) ≈ 0,916 18\.  
**Code Python**  
`from skimage.measure import regionprops`

`props = regionprops((a > 0).astype(int))`

`if props:`  
    `main_region = max(props, key=lambda r: r.area)`  
    `out_a = {"Excentricite": float(main_region.eccentricity)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.4 Solidité

**Définition**  
`S = A / A_convexe`  
**L'idée**La solidité permet de savoir à quel point une forme est « pleine », c'est-à-dire dépourvue de creux ou d'échancrures 18\. Elle repose sur le concept d'enveloppe convexe. L'analogie la plus juste est celle d'une **pellicule plastique tendue autour de l'objet** 18\. Le film plastique va s'appuyer sur les parties saillantes de l'objet, mais sera tendu au-dessus des creux intérieurs, sans jamais y pénétrer 18\.  
La solidité consiste simplement à comparer la surface réelle de l'objet (A) à la surface totale enfermée sous ce film plastique (A\_convexe) 19\. S'il n'y a aucun creux, l'objet touche le plastique partout et la solidité vaut 1 19\. Plus il y a de cavités profondes, plus la valeur de S s'effondre 19\.  
**Ce qu'elle détecte le mieux**C'est le descripteur idéal pour identifier des fusions accidentelles d'objets 19\. Par exemple, si le traitement d'image lie deux cellules distinctes, la forme générée ressemble à un « 8 » 19\. Le film plastique va recouvrir le creux central entre les deux cellules, créant un grand vide et faisant chuter la solidité autour de 0,85, bien en dessous de la valeur attendue pour une cellule saine 19\.  
**Exemple numérique**Une forme avec deux lobes distincts a une aire de A \= 3100 px², mais l'aire de son enveloppe plastique couvre 3720 px² 20\. La solidité est de S \= 3100 / 3720 ≈ 0,83 20\.  
**Piège d'implémentation**Il faut être très vigilant avec les trous situés complètement à l'intérieur de l'objet (comme l'intérieur d'un anneau) 20\. Selon la bibliothèque de code choisie, ce trou intérieur peut être considéré comme faisant partie de la surface ou non 20\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `A = cv2.contourArea(cnt)`  
    `hull = cv2.convexHull(cnt)`  
    `A_hull = cv2.contourArea(hull)`  
    `S = A / A_hull if A_hull > 0 else 0.0`  
    `out_a = {"Solidite": float(S)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.5 Convexité

**Définition**  
`Cv = P_convexe / P`  
**L'idée et la complémentarité avec la solidité**La convexité utilise la même pellicule plastique que la solidité, mais au lieu de comparer les surfaces, elle compare les **périmètres** 21\. Le film plastique, en allant au plus direct par-dessus les creux, aura toujours un périmètre plus court que le contour réel de la forme qui doit épouser tous les détours 21\.  
La convexité est particulièrement sensible à la **rugosité fine du bord** de l'objet 22\. De très nombreuses et minuscules dentelures augmentent de manière drastique la longueur du contour réel, sans pour autant retirer beaucoup de surface sous le film plastique 22\.  
Les deux descripteurs travaillent donc en équipe :

* Un contour extrêmement granuleux mais sans gros renfoncement aura une **convexité basse** et une **solidité haute** 22\.  
* Un croissant de lune parfaitement lisse, à l'inverse, possèdera une **convexité haute** mais une **solidité très basse** 22\.

**Exemple numérique**Un objet avec des bords rugueux, comme un galet ébréché, possède un contour tortueux de P \= 380 px, tandis que son enveloppe plastique fait un trajet direct de P\_convexe \= 322 px 23\. La convexité est de Cv \= 322 / 380 ≈ 0,84 23\. Couplée à une solidité élevée, cette valeur permet à une machine de diagnostiquer une simple détérioration de la surface plutôt qu'une déformation de la structure de l'objet 23\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `P = cv2.arcLength(cnt, True)`  
    `hull = cv2.convexHull(cnt)`  
    `P_hull = cv2.arcLength(hull, True)`  
    `Cv = P_hull / P if P > 0 else 0.0`  
    `out_a = {"Convexite": float(Cv)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.6 Étendue (extent)

**Définition**  
`Ext = A / (W_bbox_droite * H_bbox_droite)`  
**L'idée et sa limite**L'étendue calcule le pourcentage de remplissage de la boîte englobante de l'objet, à condition que cette boîte soit **strictement alignée horizontalement et verticalement** avec l'image (aucune rotation n'est permise) 24\. Ce descripteur est extrêmement rapide à calculer puisqu'il ne nécessite pas d'extraire les contours complexes 24\.  
Son immense faiblesse, totalement assumée, est qu'elle change drastiquement si l'objet tourne sur lui-même 24\. Un rectangle parfait, posé à plat, remplit sa boîte à 100% (Ext ≈ 0,95) 24\. Mais inclinez ce même rectangle à 45 degrés, et la boîte verticale/horizontale nécessaire pour le contenir devient beaucoup plus vaste, laissant la moitié de l'espace vide (Ext ≈ 0,5) 24\.  
L'étendue n'est donc utile que dans les domaines où l'on sait que les objets ont toujours la **même orientation par rapport à la caméra**, comme le tri de composants électroniques ou la lecture de caractères alignés sur une ligne 25\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `A = cv2.contourArea(cnt)`  
    `x, y, w, h = cv2.boundingRect(cnt)`  
    `A_box = w * h`  
    `Ext = A / A_box if A_box > 0 else 0.0`  
    `out_a = {"Etendue": float(Ext)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.7 Diamètre équivalent

**Définition**  
`D_eq = √((4 * A) / π)`  
**L'idée**Ce concept répond à une question simple : si on fondait la matière de cet objet pour en faire un disque parfait de même superficie, quel serait le diamètre de ce disque 26 ? Les mathématiques isolent le diamètre à partir de la formule classique de l'aire du disque 26\.  
Cela permet de convertir une aire mesurée en pixels carrés en une simple longueur de diamètre 26\. Il est ensuite très aisé de faire correspondre cette valeur avec une taille physique réelle (en micromètres, centimètres, etc.) si l'on connaît le calibrage de l'appareil de capture 26\. C'est ce descripteur qui permet de dresser les courbes granulométriques utilisées pour classer la taille des cellules ou des grains d'un métal 27\.  
**Exemple numérique**Un grain de sable mesuré à 3100 px² sous un microscope réglé à 0,5 micromètre par pixel possède un diamètre équivalent de √((4 \* 3100\) / π) ≈ 62,8 px 28\. En le multipliant par le réglage du microscope, on obtient une taille physique concrète d'environ 31 micromètres de diamètre 28\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `A = cv2.contourArea(cnt)`  
    `D_eq = np.sqrt((4 * A) / np.pi)`  
    `out_a = {"Diametre_Eq": float(D_eq)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.8 Rectangularité

**Définition**  
`R = A / A_minRect`  
**L'idée**Contrairement à l'étendue qui utilisait une boîte fixe, la rectangularité utilise la boîte orientée (celle qui est libre de tourner pour s'ajuster au plus près) 28\. Elle calcule quel pourcentage de cette boîte ajustée est effectivement rempli par l'objet 28\. C'est un excellent outil pour reconnaître les formes manufacturées (cartes, composants, bâtiments) 29\.  
**Angle mort**La rectangularité possède une particularité amusante : elle est totalement aveugle à l'allongement de la forme 29\. Prenez n'importe quelle forme géométrique ovale (une ellipse). Qu'il s'agisse d'un ovale très arrondi ou d'un ovale extrêmement étiré semblable à un lacet de chaussure, la proportion d'espace occupée à l'intérieur de sa boîte ajustée restera immuablement de π/4 ≈ 0,785 29\. La rectangularité ne voit que l'occupation des « coins », ignorant complètement les proportions générales de la forme 29\.  
**Exemple numérique**Un composant d'usine rectangulaire (A \= 4800 px²) s'inscrivant dans une boîte ajustée de 122 × 42 pixels (5124 px²) décroche une rectangularité de R ≈ 0,93 29\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `A = cv2.contourArea(cnt)`  
    `rect = cv2.minAreaRect(cnt)`  
    `w, h = rect[14]`  
    `A_rect = w * h`  
    `R = A / A_rect if A_rect > 0 else 0.0`  
    `out_a = {"Rectangularite": float(R)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### 1.9 Rondeur (roundness)

**Définition**  
`Rd = (4 * A) / (π * L_max²)`  
où L\_max est la plus grande dimension de l'objet, mesurée de bout en bout 30\.  
**L'idée**La rondeur est une évolution de la circularité vue au début du chapitre 30\. La circularité, nous l'avons dit, a le défaut d'être trompée par un bord très dentelé. La rondeur contourne ce problème en supprimant le périmètre de l'équation, et en le remplaçant par l'axe le plus long de la forme (L\_max) 30\. Cette mesure d'extrémité à extrémité ne se soucie pas des petits détails et des aspérités du contour 30\.  
Grâce à cela, un disque parfait mais dentelé conservera une rondeur élevée de Rd ≈ 0,95, captant sa **forme d'ensemble**, tandis que sa circularité s'effondrera 30, 31\.  
**Exemple numérique**Une particule abrasive a une aire A \= 3100 px² et son grand axe est de L\_max \= 68 px 31.Sa rondeur est élevée : Rd \= (4 \* 3100\) / (π \* 68²) ≈ 0,85, car sa forme globale est compacte 31\. En revanche, sa circularité classique n'est que de C ≈ 0,55 à cause de son bord déchiqueté 31\. En soustrayant ces deux valeurs (0,85 \- 0,55 \= 0,30), on obtient une mesure mathématique pure de l'état de rugosité du bord, libérée de la forme globale 31\.  
**Code Python**  
`cnts, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)`

`if cnts:`  
    `cnt = max(cnts, key=cv2.contourArea)`  
    `A = cv2.contourArea(cnt)`  
    `rect = cv2.minAreaRect(cnt)`  
    `L_max = max(rect[14])`  
    `Rd = (4 * A) / (np.pi * L_max * L_max) if L_max > 0 else 0.0`  
    `out_a = {"Rondeur": float(Rd)}`  
`else:`  
    `out_a = {"Erreur": "Aucun objet détecté"}`

#### Tableau récapitulatif — ce que chaque descripteur voit et ignore

Descripteur,Voit surtout,Angle mort,Invariances (T/R/E)  
Circularité C,rugosité \+ élongation (mêlées),ne sépare pas les deux causes,"T, R, E"  
Élongation E,allongement,l'intérieur de la boîte,"T, R, E"  
Excentricité e,allongement (par la masse),rugosité du bord,"T, R, E"  
Solidité S,"concavités, fusions d'objets",rugosité fine du bord,"T, R, E"  
Convexité Cv,rugosité du contour,concavités de masse,"T, R, E"  
Étendue Ext,remplissage (orienté),dépend de l'orientation,"T, E (pas R)"  
Diamètre éq. D\_eq,taille absolue,la forme,"T, R (pas E)"  
Rectangularité R,remplissage des coins,l'élongation,"T, R, E"  
Rondeur Rd,forme d'ensemble,l'état du bord,"T, R, E"  
*(T \= translation, R \= rotation, E \= échelle)* 32.Aucun descripteur ne suffit seul, mais en piochant intelligemment parmi eux, vous pouvez construire une combinaison presque parfaite 32\.

#### Encadré final — une invariance est une information qu'on accepte de perdre

Vous remarquerez que certains descripteurs de ce chapitre ne sont pas parfaits, ou dépendent de l'échelle et de l'orientation. Ce n'est pas un oubli ou une faiblesse mathématique, ce sont des choix délibérés 33\.  
Rendre un outil mathématique invariant à une transformation le rend en réalité **aveugle** à cette transformation 33\. Utiliser la circularité, qui ignore la taille de l'objet, c'est signer un contrat mathématique stipulant que la dimension n'a aucune pertinence pour votre projet 33\. Refuser d'utiliser le diamètre équivalent parce qu'il change avec la taille, c'est oublier qu'il a été conçu pour ça 33\. La question essentielle n'est donc pas de trouver un descripteur parfait, mais de se demander : **« À quelles transformations dois-je être aveugle pour ce que j'essaie de résoudre ? »** 33\.  
Choisir ses descripteurs, c'est comme régler l'objectif d'une caméra : on décide de ce qui mérite d'être net, et de ce qu'on laisse volontairement dans le flou 34\.  
