#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = figure(
  block(width: 100%, inset: 14pt, radius: 6pt,
    fill: luma(246), stroke: (dash: "dashed", thickness: 0.8pt, paint: luma(170)))[
    #align(center)[#text(fill: luma(110), style: "italic", size: 0.9em)[
      Figure à créer — #raw(id)\
      #desc
    ]]
  ]
)

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[#body]


#chapter(title: [Tester une forme, pas pondérer : la morphologie mathématique], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap11.png", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Pas de moyenne, pas de coefficients : une question géométrique. Cette sonde tient-elle ici ? La réponse, oui ou non, façonne l'image. Tout le travail est dans le choix de la sonde.]

Tous les filtres du chapitre 5 partagent une même grammaire : pondérer les valeurs voisines et les additionner. La morphologie mathématique en change radicalement. Elle ne calcule pas de moyenne ; elle pose une question géométrique — _cette forme tient-elle ici ?_ — et répond par un minimum ou un maximum. L'outil central n'est plus un pochoir de nombres mais un *élément structurant* : une forme-sonde, choisie par le praticien, qu'on promène pixel par pixel. Partout où la sonde s'insère, on lit une réponse ; partout où elle bute, l'autre.

Le fil du chapitre tient en une phrase : *la morphologie remplace la pondération par le test de forme.* Là où la convolution combine des valeurs par addition, la morphologie ne raisonne que par *comparaison* (plus grand, plus petit, tient ou ne tient pas). Tester si une forme tient, c'est déclarer quelle géométrie compte ; choisir une sonde, c'est encoder une hypothèse sur l'échelle et la direction des structures pertinentes.

La morphologie prolonge le filtrage (chapitre 5) en version non linéaire : là où le gaussien pondère pour lisser, l'ouverture sélectionne par la forme pour nettoyer. Le gradient morphologique (§11.3) mesure le même phénomène que Sobel (chapitre 6) mais par minimum/maximum. Le squelette (§11.5) coïncide avec les crêtes de la transformée de distance (chapitre 10). Et la morphologie est l'outil canonique de nettoyage des masques produits par le seuillage (chapitre 12) ou la segmentation : combler les trous, séparer les jonctions, retirer le bruit.

=== Un peu de vocabulaire avant de commencer

- *Élément structurant (B)* : Une petite forme géométrique de référence (disque, carré, ligne) que l'on promène sur l'image pour tester la géométrie locale.
- *Érosion* : L'opération qui réduit l'objet en ne gardant que les points où l'élément structurant rentre entièrement à l'intérieur.
- *Dilatation* : L'opération qui agrandit l'objet en ajoutant tous les points touchés par l'élément structurant lorsqu'il frôle le contour.

---

// ============================================================

== Érosion et dilatation : le tampon-sonde

#subtitle[Le tampon tient-il dans la forme ? la forme touche-t-elle le tampon ?]

#figfull("/figures/fig_ch11_obs1_erosion.svg")

=== L'intention
On veut rétrécir ou épaissir des formes selon un critère purement géométrique : retirer ce qui est plus fin qu'une sonde donnée, ou combler ce qui est plus étroit qu'elle.

=== La forme recherchée
Pour vous représenter ces deux opérations fondamentales de façon physique et mécanique :
+ *L'érosion comme une brosse abrasive* : Imaginez que vous passez une brosse rotative abrasive d'une forme donnée (la sonde) le long de la silhouette de votre objet. Partout où la brosse déborde ne serait-ce qu'un peu à l'extérieur de la forme, elle rabote et détruit le pixel central. L'érosion est donc un grignotage systématique : elle rétrécit l'objet, coupe les ponts fins et fait disparaître tous les détails plus petits que la brosse.
+ *La dilatation comme une buse de peinture* : C'est l'opération inverse. Imaginez que vous promenez une buse de projection de peinture (de la forme de votre sonde) sur le contour de l'objet. Partout où le centre de la buse frôle la forme, elle projette de la matière tout autour. La dilatation est une expansion géométrique : elle épaissit l'objet, fusionne les parties proches et comble les trous et crevasses étroits.

Pour une image en niveaux de gris, « raboter » (érosion) revient à prendre la valeur minimale du voisinage sous la sonde. « Projeter de la matière » (dilatation) revient à prendre la valeur maximale. L'érosion tire tout vers le bas (assombrit), tandis que la dilatation pousse tout vers le haut (éclaircit).

#info-box(title: "La formule")[
```
érosion    : (I ⊖ B)(x) = minimum des valeurs de I sous la sonde B posée en x
dilatation : (I ⊕ B)(x) = maximum des valeurs de I sous la sonde B posée en x
```
]

B est l'élément structurant (la sonde). Le passage du noir et blanc aux niveaux de gris remplace simplement « tous les points dedans » par un minimum, et « au moins un point » par un maximum : l'ordre remplace l'appartenance. Les deux opérations sont *duales* — éroder l'objet revient à dilater le fond, et inversement. Comprendre l'érosion suffit à déduire la dilatation, et toute la suite se décline en paires symétriques.

L'érosion rétrécit le clair, supprime les détails plus fins que la sonde, déconnecte les ponts minces ; la dilatation épaissit, comble, fusionne. L'angle mort majeur : *ces opérations perdent de l'information.* Un détail plus étroit que la sonde, une fois effacé, est perdu pour de bon. Éroder puis dilater ne reconstruit pas l'image d'origine — c'est l'ouverture (§11.2), structurellement plus petite. La sonde décide ce qui est « trop fin pour survivre ». ∎

#question-box(title: "Exemple chiffré")[
Signal `[3, 1, 4, 1, 5, 9, 2, 6]`, sonde plate de largeur 3 (le pixel et ses deux voisins) :

```
érosion   (minimum glissant) : [1, 1, 1, 1, 1, 2, 2, 2]
dilatation (maximum glissant): [3, 4, 4, 5, 9, 9, 9, 6]
```

Au pic isolé (la valeur 9) : son voisinage est {5, 9, 2}, dont le minimum est 2 et le maximum 9. L'érosion ramène le pic à 2 (il disparaît), la dilatation le propage à ses voisins. On a toujours érosion ≤ image ≤ dilatation, point par point.
]

#warning-box(title: "Piège — conventions d'objet et de bord")[
Trois points donnent un résultat faux et silencieux s'ils sont négligés. *Quel est l'objet ?* « Éroder » rétrécit les pixels allumés ; sur un masque inversé (objet sombre sur fond clair), l'érosion élargit l'objet. *Le bord de l'image* : l'érosion a besoin de valeurs au-delà du bord ; selon ce qu'on suppose dehors (du fond ou un prolongement), le résultat change sur la bordure. *Sonde asymétrique* : certaines bibliothèques retournent la sonde, d'autres non — sans effet pour un disque ou une croix symétriques, mais source d'erreur pour une sonde dissymétrique.
]

#canvas[
Canvas : `Mask` → `Erode` et `Mask` → `Dilate` → `Output Display`. Les deux nœuds exposent la forme et la taille de la sonde (disque, carré, croix, segment) ; l'inspecteur compte les pixels retirés par l'érosion ou ajoutés par la dilatation.

---
]

// ============================================================

== Ouverture et fermeture : la sonde qui roule

#subtitle[Tout ce que la sonde peut atteindre survit ; le reste disparaît]

=== L'intention
On veut nettoyer un masque selon la taille : retirer les petits objets clairs (ou reboucher les petits trous sombres) sans rétrécir durablement les structures qu'on garde.

=== La forme recherchée
Pour vous représenter l'ouverture et la fermeture :
+ *L'ouverture comme un aspirateur à tamis* : Faire une ouverture, c'est comme passer l'aspirateur muni d'un embout d'une certaine taille (la sonde) sur une plage de sable jonchée de débris. Les petites poussières et les brindilles fines (les bruits « sel » plus étroits que l'embout) sont instantanément aspirées et disparaissent. En revanche, les gros galets et les objets plus larges que l'embout ne peuvent pas entrer : ils sont préservés et conservent leur forme globale d'origine (grâce à la dilatation qui succède à l'érosion).
+ *La fermeture comme une truelle de maçon* : La fermeture est l'exact opposé. C'est le geste du maçon qui étale du ciment avec sa truelle sur une surface. Les crevasses étroites, les petites bulles d'air et les pores (les bruits « poivre ») sont rebouchés et lissés, tandis que le relief général et les grands blocs restent inchangés.

Choisir une sonde de 5 pixels, c'est déclarer que tout motif plus étroit que 5 pixels est un parasite à éliminer. Choisir une sonde en forme de trait horizontal, c'est décider que seules les structures allongées horizontalement méritent de survivre.

#info-box(title: "La formule")[
```
ouverture : I ∘ B = (I ⊖ B) ⊕ B     (éroder puis dilater → supprime les petits objets clairs)
fermeture : I • B = (I ⊕ B) ⊖ B     (dilater puis éroder → rebouche les petits trous sombres)
```
]

Une ouverture, c'est une érosion suivie d'une dilatation par la même sonde : l'érosion efface ce qui est trop fin, la dilatation rend leur taille à ce qui a survécu. Ces opérations ont une propriété utile : elles sont *idempotentes* — réappliquer une ouverture ne change plus rien. Conséquence pratique souvent ignorée : itérer une ouverture est inutile ; pour nettoyer davantage, on agrandit la sonde, on ne répète pas l'opération. Et l'ordre est garanti : l'ouverture ne peut qu'abaisser (I ∘ B ≤ I), la fermeture qu'élever (I • B ≥ I). Une ouverture qui produirait des pixels plus clairs que l'original trahirait un bogue.

En ouvrant avec des sondes de taille croissante et en mesurant l'aire perdue à chaque pas, on obtient une *granulométrie* — un tamisage virtuel qui donne la distribution des tailles d'objets, prolongeant le diamètre équivalent du chapitre 1. ∎

#question-box(title: "Exemple chiffré")[
Signal `[3, 1, 4, 1, 5, 9, 2, 6]`, sonde plate de largeur 3 :

```
ouverture (éroder puis dilater) = [1, 1, 1, 1, 2, 2, 2, 2]   ≤ image  ✓
fermeture (dilater puis éroder) = [3, 3, 4, 4, 5, 9, 6, 6]   ≥ image  ✓
```

L'ouverture a rasé le pic isolé 9 (plus étroit que la sonde) ; la fermeture a rebouché les vallées étroites 1 (remontées à 3 et 4). Littéralement : retrait des petits objets clairs, comblement des petits trous sombres.
]

#info-box(title: "Réglage — l'ordre et la forme de la sonde")[
Sur un masque de cellules en microscopie, ouvrir d'abord (retirer le bruit blanc) puis fermer (reboucher les trous des noyaux) est l'ordre habituel ; l'inverser peut créer de faux objets. Une ouverture par un segment horizontal ne conserve que les structures horizontales — utile pour isoler les lignes d'un tableau numérisé ou les traits d'un texte.
]

#canvas[
Canvas : `Mask` → `Morph Open` et `Mask` → `Morph Close` → `Output Display`. Les nœuds exposent forme et taille de la sonde ; l'inspecteur indique les pixels supprimés par l'ouverture et ajoutés par la fermeture.

---
]

// ============================================================

== Gradient morphologique : le contraste sans dérivée

#subtitle[La différence entre ce que la fenêtre a de plus haut et de plus bas]

#figfull("/figures/fig_ch11_obs2_morph_gradient.svg")

=== L'intention
On veut détecter les contours — les sauts d'intensité — sans calculer de dérivée, par une mesure de contraste local robuste.

=== La forme recherchée
Dans une zone plate, le maximum et le minimum du voisinage sont égaux : leur différence est nulle. Près d'une transition sombre/clair, la dilatation capte la valeur haute et l'érosion la valeur basse : leur différence révèle l'amplitude du saut. Le *gradient morphologique* mesure ainsi le contraste local, sans aucune dérivée. Comparé à Sobel (chapitre 6), qui donne magnitude _et_ orientation, il ne donne que la magnitude — et traite toutes les directions également si la sonde est un disque.

#info-box(title: "La formule")[
```
∇_m I = (I ⊕ B) − (I ⊖ B)        (dilatation moins érosion)
```
]

C'est tout : la valeur la plus haute du voisinage moins la plus basse. Sur une zone constante, les deux sont égales, le gradient est nul. Près d'une marche, la magnitude est exacte, mais la *largeur* du contour détecté est imposée par la sonde, pas par l'image : une grande sonde donne des bords épais. Le gradient morphologique est *plus robuste au bruit aléatoire* que Sobel (minimum et maximum sont moins sensibles que la dérivée) mais *plus sensible aux pixels aberrants* (un seul pixel très brillant gonfle le maximum). ∎

#question-box(title: "Exemple chiffré")[
Marche d'intensité `[10, 10, 10, 50, 50, 50]`, sonde plate de largeur 3 :

```
dilatation = [10, 10, 50, 50, 50, 50]
érosion    = [10, 10, 10, 10, 50, 50]
gradient   = [ 0,  0, 40, 40,  0,  0]
```

Le contour de hauteur 40 (= 50 − 10) est détecté, mais étalé sur 2 pixels (largeur de la sonde moins un). La valeur est juste, la largeur est un artefact de la sonde.
]

#info-box(title: "Réglage — finesse et bruit impulsionnel")[
Pour un watershed par marqueurs (chapitre 12), on veut un gradient fin : une petite sonde 3×3 évite les faux bassins. Si l'image est piquée d'impulsions (bruit sel-et-poivre), un filtrage médian préalable (chapitre 5) empêche un pixel aberrant de gonfler le gradient.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `Morph Gradient` → `Output Display`. Le nœud sort la carte de contraste local ; réduire la taille de la sonde montre les contours s'affiner.

---
]

// ============================================================

== Top-hat et black-hat : isoler les détails du fond

#subtitle[Estimer le fond par une grande sonde, puis le soustraire]

=== L'intention
Isoler de petits objets d'intérêt (comme des cellules claires ou des caractères imprimés sombres) lorsqu'ils sont posés sur un fond dont la luminosité varie de façon inégale ou progressive. Dans ces conditions, un seuil global est inutilisable : un seuil réglé pour le côté clair de l'image efface tout du côté sombre, et inversement.

=== La forme recherchée
Puisqu'on ne peut pas utiliser de seuil direct, on va chercher à gommer les variations de lumière en estimant la forme générale du fond pour la soustraire. L'image de référence est celle d'un menuisier qui rabote une planche de bois irrégulière :
+ *L'estimation du fond* : On utilise l'ouverture morphologique (§11.2). En choisissant une sonde plus grande que les objets à détecter, la sonde ne peut pas entrer dans les détails fins. L'ouverture agit donc comme un rabot géométrique : elle efface complètement les petits objets clairs et ne conserve que la surface lisse et ondulée du fond.
+ *La soustraction* : En soustrayant ce fond estimé de l'image originale, on annule toutes les variations lentes d'éclairage. Il ne reste que les « copeaux » du rabotage, c'est-à-dire les petits détails saillants et clairs qui ont été nettoyés de leur fond.

Le *top-hat* réalise cette opération pour les détails plus clairs que le fond. Le *black-hat* effectue l'opération duale pour les détails sombres (en utilisant la fermeture pour estimer le fond et en soustrayant l'image originale).

#info-box(title: "La formule")[
```
top-hat(I, B)   = I − (I ∘ B)
black-hat(I, B) = (I • B) − I
```
]

Ici, `I` représente l'image d'entrée et `B` la sonde (l'élément structurant).

Pour comprendre pourquoi le top-hat fonctionne, décomposons son comportement pixel par pixel :
- Puisque l'ouverture `I ∘ B` est mathématiquement inférieure ou égale à l'image originale `I` en chaque point (l'érosion rabote toujours les pics), le résultat `I − (I ∘ B)` est toujours positif ou nul.
- Sur les zones plates ou les pentes douces qui représentent le fond, l'ouverture épouse parfaitement l'intensité d'origine : la soustraction donne un résultat très proche de zéro (le fond est neutralisé et devient noir).
- Sur un pic clair plus petit que la sonde, l'ouverture gomme le pic et renvoie l'intensité du fond environnant. La soustraction donne alors la hauteur exacte du pic par rapport à son fond local.

La condition essentielle de réussite repose sur une *fenêtre d'échelle* : la sonde doit être strictement plus grande que les objets d'intérêt pour pouvoir les effacer, mais plus petite que la distance sur laquelle le fond varie. Si les variations d'éclairage se produisent à la même échelle de taille que vos objets, aucune sonde ne pourra les séparer géométriquement. ∎

#question-box(title: "Exemple chiffré")[
Imaginons une ligne de pixels représentant une rampe d'éclairage avec un pic clair localisé à l'indice 4 (le détail à détecter, d'intensité 48) :

```
Image d'origine I        = [10, 12, 14, 16, 48, 20]
```

Si l'on applique une ouverture avec une sonde plate de taille 3, la sonde est trop large pour entrer dans le pic isolé à l'indice 4. Elle renvoie donc le fond lissé :

```
Ouverture (I ∘ B)        = [10, 12, 14, 16, 16, 16]
```

En soustrayant l'ouverture de l'image d'origine, on isole parfaitement le pic :

```
Top-hat (I − (I ∘ B))    = [ 0,  0,  0,  0, 32,  4]
```

La rampe d'éclairage (le gradient de 10 à 20) a complètement disparu. Le pic à l'indice 4 ressort avec une intensité nette de 32 (sa hauteur relative par rapport au fond local qui valait 16). La valeur 4 à l'extrémité est un artefact de bordure inévitable, dû au fait que la sonde déborde de l'image lors du calcul de l'ouverture.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans VNStudio (nœud `Top Hat` / `Black Hat`) ou en Python (`cv2.morphologyEx` avec `cv2.MORPH_TOPHAT` ou `cv2.MORPH_BLACKHAT`), les réglages suivants déterminent la qualité du résultat :

- *Type d'élément structurant (`shape`)* :
- Dans VNStudio, ce paramètre correspond au menu déroulant *Structuring Element Shape* ; en Python (OpenCV), il se nomme `shape` (ex. `cv2.MORPH_ELLIPSE`) dans la fonction `cv2.getStructuringElement`.
- `cv2.MORPH_RECT` (Rectangle) : À utiliser pour les objets rectangulaires (ex. : codes-barres, caractères d'imprimerie).
- `cv2.MORPH_ELLIPSE` (Ellipse) : Le choix le plus robuste pour les objets naturels ou circulaires (ex. : cellules, grains). Il évite de créer des artefacts anguleux dans les coins des objets isolés.
- `cv2.MORPH_CROSS` (Croix) : Utile pour isoler des lignes fines orthogonales ou réduire le temps de calcul.
- *Taille de la sonde (`kernel size` ou `ksize`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Structuring Element Size* ; en Python (OpenCV), il se nomme `ksize` dans `cv2.getStructuringElement`.
- Ce paramètre (ex. : 15×15) est le plus sensible. La règle d'or est de mesurer l'épaisseur moyenne de vos objets en pixels. La taille de la sonde doit être choisie environ *1,5 à 2 fois supérieure* à cette épaisseur. Si vos objets font 10 pixels de large, configurez une sonde de 15×15 ou 21×21. Une sonde trop petite détruira vos objets lors de la soustraction ; une sonde trop grande ralentira inutilement le calcul et augmentera la taille des artefacts de bordure.
- *Nombre d'itérations (`iterations`)* :
- Dans VNStudio, ce paramètre correspond au champ *Iterations* ; en Python (OpenCV), il correspond à l'argument `iterations` de `cv2.morphologyEx`.
- Répéter l'opération. Pour le top-hat, faire 2 itérations avec une sonde 3×3 équivaut à utiliser une sonde de 5×5. Il est généralement préférable de régler directement la taille de la sonde plutôt que de multiplier les itérations, pour des raisons de clarté.
- *Gestion des bordures (`borderType`)* :
- Dans VNStudio, ce paramètre correspond au menu déroulant *Border Type* ; en Python (OpenCV), il correspond à l'argument `borderType` dans `cv2.morphologyEx`.
- Définit comment OpenCV estime les pixels manquants lorsque la sonde dépasse des bords de l'image (ex. : `cv2.BORDER_CONSTANT` qui suppose un fond noir, ou `cv2.BORDER_REPLICATE` qui duplique la dernière ligne). C'est ce paramètre qui contrôle l'intensité des artefacts de bord observés aux extrémités de l'image.

*Exercice de dépannage (échec contrôlé) :* L'exercice consiste à charger une image binaire contenant des trous noirs circulaires de 10 pixels de diamètre au sein d'une forme blanche. Tenter de combler ces trous en appliquant une fermeture morphologique (nœud *Closing*). Régler le paramètre *Structuring Element Size* sur 5 pixels. Le lecteur observe dans l'inspecteur que les trous restent ouverts et inchangés. Régler ensuite la taille de l'élément à 15 pixels. Le lecteur constate que tous les trous disparaissent instantanément. Cet échec contrôlé démontre que la taille du noyau doit être strictement supérieure à l'épaisseur du défaut à combler pour que l'opération réussisse.
]

#canvas[
Dans votre canvas :
`Image Source` ──> `Grayscale` ──> `Top Hat` (ou `Black Hat`) ──> `Adaptive Threshold` (ou `Threshold` simple) ──> `Output Display`.

Le nœud `Top Hat` applique les paramètres ci-dessus. En réglant le curseur `Sonde` à une valeur supérieure à la largeur des détails recherchés, vous verrez l'image de fond devenir instantanément noire et homogène, rendant le seuillage qui suit extrêmement simple et stable.

---
]

// ============================================================

== Tout-ou-rien et squelette

#subtitle[Deux sondes : la forme qui doit être là, et celle qui doit être absente]

#figfull("/figures/fig_ch11_obs3_skeleton.svg")

=== L'intention
Les opérateurs précédents _transforment_ l'image. On veut ici *détecter* une configuration géométrique exacte (un coin, une extrémité de trait, un pixel isolé), puis réduire une forme à son axe central.

=== La forme recherchée
La transformée *tout-ou-rien* (_hit-or-miss_) utilise *deux sondes disjointes* : la première décrit la forme que l'objet doit avoir, la seconde celle que le fond doit avoir autour. Un pixel survit seulement si la première tient dans l'objet _et_ la seconde tient dans le fond. C'est le test de forme poussé à sa précision maximale : on déclare à la fois ce qui doit être présent et ce qui doit être absent.

Le *squelette* réduit une forme à son *axe central* — le lieu des centres des plus grands disques qu'on peut inscrire dans la forme. Prenez un « B » imprimé : son squelette trace une colonne verticale et deux branches (les panses). Toute la topologie — les connexions, les branches, la longueur — tient dans ce tracé d'un pixel d'épaisseur. Ce squelette coïncide exactement avec les *crêtes de la transformée de distance* (chapitre 10) : éroder une forme par un disque de rayon r revient à seuiller sa carte de distance à r. Morphologie et transformée de distance décrivent la même réalité — l'épaisseur et la centralité d'une forme — l'une par sondes successives, l'autre par carte de distances.

La transformée tout-ou-rien est précise au pixel près (motifs réguliers : texte, circuits) mais fragile au bruit — un pixel manquant annule la détection. Le squelette est topologiquement riche mais *instable* : une petite bosse du contour crée une branche parasite (une « barbe »). Les deux supposent un masque propre, d'où un nettoyage préalable par ouverture ou fermeture.

#question-box(title: "Exemple chiffré")[
Détecter les *pixels isolés* : première sonde = un pixel central allumé, seconde sonde = ses huit voisins, tous censés appartenir au fond. Un pixel d'objet entouré uniquement de fond satisfait les deux conditions ; tout pixel ayant un voisin allumé est rejeté. On obtient ainsi la carte des pixels solitaires — pour compter ou retirer le bruit « poivre » d'un masque, complément du bruit « sel » que l'ouverture retire.
]

#canvas[
Canvas : `Mask` → `Skeleton` → `Output Display` pour l'axe médian ; `Mask` → `Hit or Miss` → `Output Display` avec la sonde « pixel isolé » pour détecter les points solitaires. L'inspecteur donne la longueur du squelette et l'épaisseur maximale de la forme.

---
]

// ============================================================

== Tableau récapitulatif — chaque opérateur est un choix de sonde

#table(
  columns: 5,
  table.header(
    [*Opérateur*], [*Test de forme*], [*Effet géométrique*], [*Angle mort*], [*Usage type*]
  ),
  [Érosion], [minimum local], [rétrécit le clair, perd les détails fins], [perte irréversible], [séparer des objets proches, nettoyage],
  [Dilatation], [maximum local], [épaissit le clair, comble les lacunes fines], [fusionne des objets proches], [reconnexion, marqueurs watershed],
  [Ouverture], [sonde qui roule dedans], [supprime les objets clairs trop fins], [sonde mal calibrée efface le signal], [retrait de bruit, granulométrie],
  [Fermeture], [sonde qui roule dehors], [bouche les trous sombres trop étroits], [sonde mal calibrée noie les détails], [colmatage de masques (vaisseaux, fissures)],
  [Gradient], [écart max − min local], [contour isotrope, magnitude seule], [épaisseur imposée par la sonde], [pré-watershed, bords robustes],
  [Top-hat], [image − ouverture], [détails clairs sur fond quelconque], [la sonde doit encadrer l'échelle], [OCR sur fond inégal, microscopie],
  [Black-hat], [fermeture − image], [détails sombres sur fond quelconque], [idem top-hat], [défauts sombres, télédétection],
  [Tout-ou-rien], [deux sondes (objet + fond)], [détecte un motif exact], [fragile au bruit], [coins, extrémités, pixels isolés],
  [Squelette], [crêtes de la carte de distance], [axe central, topologie préservée], [barbes sur les contours rugueux], [signature de forme, épaisseur],
)

---

// ============================================================

== le difficile, c'est de choisir la sonde

La morphologie pousse à sa forme la plus géométrique l'idée qui traverse le livre :

```
chapitre 3  (distances)   : une métrique             → ce qui rend deux choses proches
chapitre 5  (filtrage)    : un noyau                 → un a priori sur la régularité du signal
chapitre 6  (gradients)   : une dérivée              → ce qui constitue une transition
chapitre 10 (transformées): une base                 → le domaine où le problème devient simple
chapitre 11 (morphologie) : un élément structurant   → la forme et l'échelle qui comptent
```

On ne pondère pas, on ne projette pas : on teste si une forme tient. Les opérateurs eux-mêmes — un minimum, un maximum, une différence — sont triviaux à calculer. Le difficile, c'est de choisir la sonde : déclarer, avant de toucher à l'image, quelle géométrie mérite d'être vue et à quelle échelle. Un disque pour rester sans direction privilégiée, un segment orienté pour ne garder qu'une direction, une grande sonde pour estimer un fond lent, deux sondes pour reconnaître un motif exact. Une fois la sonde bien posée, le résultat est presque acquis.

Cela fixe aussi la place de la morphologie dans les pipelines modernes : les réseaux profonds apprennent _quoi_ segmenter mais n'offrent aucune garantie de forme sur leurs masques, là où la morphologie impose _quelle géométrie_ le masque doit respecter — combler les trous, séparer les jonctions, nettoyer le bruit. Le réseau repère l'objet, la morphologie lui donne une forme propre. Le chapitre 12 s'appuiera directement sur ces opérateurs pour nettoyer les masques de seuillage et préparer le watershed.

---

]
