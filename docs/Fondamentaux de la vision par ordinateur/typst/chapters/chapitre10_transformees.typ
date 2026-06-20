#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = block(above: 2em, below: 2em, width: 100%)[
  #block(width: 100%, inset: (x: 16pt, y: 14pt), radius: 6pt,
    fill: rgb("#fdf3f5"), stroke: 1pt + rgb("#d0a0aa"))[
    #grid(columns: (1fr, auto), column-gutter: 14pt, align: horizon,
      align(left)[
        #text(size: 0.78em, weight: "bold", fill: rgb("#c1002a"), font: "Roboto")[▪ IMAGE]
        #v(0.4em)
        #text(size: 0.9em, fill: rgb("#334155"), font: "Roboto")[#raw(id)]
      ],
      box(width: 42pt, height: 34pt, radius: 3pt, fill: rgb("#fff0f2"), stroke: 1pt + rgb("#c1002a"), clip: true)[
        #align(center)[
          #v(5pt)
          #circle(radius: 4pt, fill: rgb("#c1002a").lighten(35%), stroke: none)
          #v(2pt)
          #polygon(fill: rgb("#c1002a").lighten(55%), stroke: none,
            (0pt, 9pt), (13pt, 0pt), (26pt, 9pt))
          #v(2pt)
        ]
      ]
    )
  ]
]

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let figcap(path, cap) = block(above: 1em, below: 1.4em, width: 100%)[#text(weight: "bold", size: 0.95em, fill: rgb("#7a1330"))[#cap]#v(0.35em)#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[
  #show heading: it => block(above: 0.5em, below: 0em)[
    #text(font: "Roboto", weight: "regular", size: 0.95em)[#it.body]
  ]
  #set heading(numbering: none)
  #body
]


#chapter(title: [Les transformées], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap10.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Une transformée ne change pas l'image, seulement le système de coordonnées où on la lit. Le bon repère rend trivial ce qui semblait laborieux : effacer une rayure devient effacer deux coefficients.]

Depuis le début du livre, les images ont été manipulées dans leur forme naturelle : un tableau de pixels portant chacun une intensité. Ce point de vue est le plus direct, pas toujours le plus efficace. Filtrer une rayure périodique pixel par pixel est laborieux ; vue autrement, l'opération se réduit à effacer deux nombres. Détecter des droites dans un nuage de contours bruités est difficile ; vues autrement, elles se révèlent comme des pics nets. Compresser une image est impossible directement dans les pixels ; vue autrement, quelques nombres suffisent.

Le fil du chapitre tient en une phrase : *changer de base, c'est choisir où le problème devient simple.* Une « base » est un système de coordonnées : une façon de décrire la même chose avec des axes différents. Une transformée ne modifie pas l'image — elle la réexprime dans une nouvelle base, choisie pour que la tâche (filtrer, détecter, compresser, mesurer) y devienne triviale. L'information est la même ; seul le cadre change. Comme le choix d'une distance (chapitre 3) ou d'un filtre (chapitre 5), ce choix encode une hypothèse sur ce qui compte.

Le chapitre prolonge le chapitre 5 : il révèle _pourquoi_ les filtres spatiaux agissent sur les fréquences. La transformée de distance (§10.5) reparaîtra au chapitre 12 sur la segmentation.

=== Un peu de vocabulaire avant de commencer

- *Changement de base* : La réécriture d'une information dans un nouveau repère ou système d'axes sans en altérer le contenu (ex. : décrire une image par ses fréquences plutôt que par ses pixels).
- *Transformée* : L'opérateur qui convertit les données d'un espace à un autre (ex. : la transformée de Fourier passe de l'espace spatial à l'espace fréquentiel).
- *Fréquences spatiales* : La vitesse à laquelle l'intensité varie dans l'espace. Les variations lentes forment les *basses fréquences*, les variations rapides et le bruit forment les *hautes fréquences*.

---

// ============================================================

== La transformée de Fourier (DFT) : décomposer en ondes

#subtitle[L'accordeur qui décompose une note en ses fréquences pures]

#figfull("/illustrations/chap10.1.png")

#figfull("/figures/fig_ch10_obs1_fft_filter.svg")

=== L'intention
On voudrait savoir de quelles ondulations une image est faite — ses variations lentes, ses détails fins, ses motifs périodiques — pour agir sur l'une sans toucher aux autres.

=== La forme recherchée
L'image utile est celle d'un accordeur de musique. Quand un musicien joue une note complexe, l'accordeur la décompose en fréquences : une fondamentale forte, des harmoniques plus faibles. La *transformée de Fourier* fait de même pour une image : elle la décompose en une somme d'ondulations régulières (des sinusoïdes), chacune d'une fréquence, d'une orientation et d'une position données. Les *basses fréquences* sont les variations lentes — les grandes plages uniformes, l'éclairage général ; les *hautes fréquences* sont les contours nets, les détails fins, le bruit du capteur.

On peut voir cette décomposition comme un changement de base : au lieu de décrire l'image pixel par pixel, on la décrit ondulation par ondulation. Ces ondulations forment un système d'axes complet, exactement comme les trois axes de l'espace décrivent un point. L'image et sa transformée contiennent la même information — dans la base des pixels, les fréquences sont invisibles ; dans la base de Fourier, elles sautent aux yeux. Chaque ondulation est décrite par deux nombres : son *amplitude* (quelle énergie à cette fréquence) et sa *phase* (où elle est positionnée). Détail contre-intuitif mais important : c'est la *phase* qui porte l'essentiel de la structure visible — c'est elle qui dit _où_ sont les contours.

#info-box(title: "La formule")[
```
F(u, v) = somme sur tous les pixels de  I(x,y) · (ondulation de fréquence u, v)
```
]

Pour vous représenter cette formule physiquement :
+ *L'image mentale des vagues* : Une « ondulation de fréquence `(u, v)` » est un motif géométrique de vagues régulières (une sinusoïde bidimensionnelle) dessinées sur l'image. L'indice `u` représente le nombre de vagues horizontales (de gauche à droite), tandis que `v` représente le nombre de vagues verticales (de haut en bas).
+ *Le produit scalaire comme résonance* : Multiplier l'image d'origine `I(x, y)` pixel par pixel par ce motif de vagues et additionner les résultats (la somme) revient à calculer leur produit scalaire (§3.3). Si les structures de l'image s'alignent avec le rythme et l'orientation de ces vagues, la somme explose (résonance) et `F(u, v)` prend une valeur très forte. Si l'image n'a rien à voir avec ce motif, les parties claires et sombres s'annulent dans la somme, et `F(u, v)` vaut zéro.

On calcule cette décomposition pour toutes les fréquences possibles grâce à la *FFT* (transformée de Fourier rapide), un algorithme extrêmement optimisé capable de traiter une image haute définition en temps réel. ∎

#question-box(title: "Exemple")[
Une image de rayures verticales espacées de 10 pixels a une transformée presque entièrement vide, *sauf deux pics* symétriques à la fréquence correspondant à cet espacement. Toute la structure « rayures » tient dans deux nombres. Pour les effacer — sur une radiographie, un scan de document —, on annule ces deux nombres puis on revient dans l'espace des pixels : les rayures ont disparu sans toucher au reste. Trivial dans la base de Fourier, laborieux dans les pixels.
]

#warning-box(title: "Piège — l'image est supposée se répéter")[
La transformée suppose que l'image se répète à l'infini dans toutes les directions, bord droit collé au bord gauche. Si ces bords diffèrent (presque toujours), la jointure crée une fausse discontinuité brutale qui pollue le spectre — une *fuite spectrale*. Le remède atténue doucement les bords vers zéro avant le calcul (une « fenêtre d'apodisation »).
]

#canvas[
Canvas : `Image File` → `Grayscale` → `FFT Analysis` → `Display`. Le nœud affiche le spectre d'amplitude (les pics de fréquence) ; son paramètre *Filter Type* permet d'annuler des fréquences précises (les deux pics d'une rayure) et le port *Filtered* renvoie l'image nettoyée.

---
]

// ============================================================

== Le théorème de convolution : le pont avec le chapitre 5

#subtitle[Faire glisser un noyau, ou multiplier deux spectres — le même geste]

#figfull("/nvlle illu/A_humorous,_highly_stylized_line-art_202606191401.jpeg")

=== L'intention
Au chapitre 5, on affirmait que les filtres agissent sur les fréquences sans le prouver. On veut maintenant le lien exact entre la convolution spatiale (faire glisser un pochoir) et le domaine des fréquences.

#info-box(title: "La forme recherchée et la formule")[
```
transformée de (image filtrée) = transformée de l'image × transformée du filtre
```
]

Le théorème dit ceci : faire glisser un pochoir sur l'image (la convolution du chapitre 5) revient exactement à *multiplier*, fréquence par fréquence, le spectre de l'image par le spectre du filtre. Convoluer dans l'espace — lent pour de grands pochoirs — et multiplier deux spectres — instantané — sont deux façons de faire la même chose. La convolution, en apparence spatiale, est donc en réalité un filtrage des fréquences. ∎

=== Ce que cela révèle sur le chapitre 5
Ce résultat explique enfin pourquoi les filtres du chapitre 5 agissent sur les fréquences :

```
filtre spatial          ce qu'il fait aux fréquences
gaussien (lissage)  →   laisse passer les basses, coupe les hautes  (passe-bas)
Sobel / Laplacien   →   coupe les basses, laisse passer les hautes  (passe-haut)
DoG / Gabor         →   ne laisse passer qu'une bande              (passe-bande)
```

Un flou gaussien atténue les hautes fréquences : c'est un *passe-bas*. Un dérivateur les exalte : c'est un *passe-haut*. Concevoir un filtre revient alors à dessiner quelles fréquences il laisse passer — souvent plus intuitif que de choisir des nombres dans un pochoir. Conséquence pratique : pour un très grand pochoir, passer par les fréquences (transformer, multiplier, retransformer) est bien plus rapide que de le faire glisser pixel par pixel.

#canvas[
Canvas : `Image File` → `FFT Analysis` → `Display` (paramètre *Filter Type* = Low-pass). Le nœud applique un masque de fréquences (passe-bas, passe-haut ou passe-bande) directement dans le domaine de Fourier ; comparer son résultat à un `Blur` (mode Gaussien) montre que les deux donnent le même flou.

---
]

// ============================================================

== La transformée en cosinus (DCT)

#subtitle[Replier le tissu comme un miroir pour éviter la couture visible]

#figfull("/illustrations/chap10.3.png")

=== L'intention
Pour stocker ou transmettre une image, on voudrait concentrer son contenu dans le moins de nombres possible — quitte à jeter ce qui se voit le moins.

=== La forme recherchée
La DCT (_transformée en cosinus discrète_) est une cousine de Fourier qui n'utilise que des cosinus, sans la partie « position » complexe — ses nombres sont donc deux fois plus légers. Surtout, elle résout élégamment le problème de frontière de Fourier.

Pour le comprendre, imaginez des carreaux de faïence avec lesquels on pave un mur infini :
+ *La répétition selon Fourier* : Fourier colle le bord droit de l'image directement contre son bord gauche pour la répéter. Si l'image est très claire à droite et très sombre à gauche, la couture entre les deux carreaux forme une ligne verticale brutale de fort contraste. La transformée de Fourier, qui suppose cette périodicité, voit cette « couture » comme une haute fréquence verticale artificielle très intense, qui pollue tout le spectre.
+ *Le pliage en miroir de la DCT* : La DCT résout cela en inversant un carreau sur deux, comme dans un miroir (le reflet de droite fait face au carreau suivant). La transition de clarté aux coutures se fait désormais de façon parfaitement symétrique et continue : aucun bord brusque n'est créé artificiellement. Le spectre fréquentiel s'en trouve grandement nettoyé de ses hautes fréquences parasites.

Sa propriété reine est la *compaction d'énergie* : pour les images naturelles, qui varient doucement, la DCT concentre presque toute l'information dans quelques nombres de basse fréquence, les autres étant proches de zéro. Ce n'est pas magique : les pixels voisins se ressemblent, et cette redondance se traduit par peu de nombres non nuls. Jeter les quasi-nuls ne change presque rien à l'image — c'est le fondement de toute compression avec perte.

=== JPEG : la DCT en action
```
1. Découper l'image en blocs de 8×8 pixels
2. DCT de chaque bloc  → énergie concentrée dans le coin basse fréquence
3. Quantification      → arrondir grossièrement les hautes fréquences peu visibles
4. Compression         → les nombreux zéros se compressent très bien
```

La quantification est la seule étape destructive, et elle exploite la perception : l'œil tolère mal les erreurs dans les zones lisses (basses fréquences) mais bien dans les détails fins (hautes fréquences). Poussée trop loin, elle produit les fameux *artefacts en blocs* : les frontières des carrés de 8×8 deviennent visibles, révélant l'unité de calcul que le changement de base avait réussi à faire oublier.

#question-box(title: "Exemple")[
Un bloc 8×8 pris dans un ciel uniforme : après DCT, un seul nombre (la moyenne du bloc) concentre presque toute l'énergie, les 63 autres sont proches de zéro. On stocke un nombre au lieu de 64. Un bloc pris dans du feuillage serré étale son énergie sur des dizaines de nombres : il se compresse moins bien. La DCT n'améliore pas l'image, elle rend visible la compressibilité déjà présente.
]

#canvas[
Canvas : `Image File` → `Grayscale` → `DCT Analysis` → `Display`. Le nœud découpe en blocs 8×8, montre la concentration d'énergie de chaque bloc, et permet de ne garder que les N plus grands nombres pour visualiser la perte de compression.

---
]

// ============================================================

== La transformée de Hough : voter pour des formes

#subtitle[Un vote à bulletin secret : les vrais alignements s'accumulent, le bruit se disperse]

#figfull("/illustrations/chap10.4.png")

#figfull("/figures/fig_ch10_obs3_hough.svg")

=== L'intention
On veut détecter des formes géométriques précises — droites, cercles — dans un nuage de contours bruités et parfois interrompus, là où une recherche directe d'alignements serait fragile.

=== La forme recherchée
Hough change l'image vers un *espace de paramètres* : un espace dont les axes ne sont plus la position, mais les caractéristiques de la forme cherchée. Pour une droite, deux paramètres suffisent (sa distance à l'origine et son inclinaison), donc chaque droite possible est un point de cet espace. L'image utile est celle d'un vote à bulletin secret. Chaque pixel de contour ignore à quelle droite globale il appartient, mais il peut *voter* pour toutes les droites qui pourraient passer par lui. Une vraie droite rassemble de nombreux pixels qui votent tous pour les mêmes paramètres : leurs votes s'accumulent en un même point de l'espace de Hough, formant un *pic*. Le bruit vote de façon dispersée et ne forme aucun pic.

Un point de l'image vote pour toutes les droites passant par lui, ce qui dessine une courbe dans l'espace des paramètres. La dualité :

#info-box(title: "La formule — la dualité point/courbe")[
```
un POINT dans l'image    →   une COURBE dans l'espace des paramètres
une DROITE dans l'image  →   un POINT dans l'espace des paramètres (un pic de votes)
```
]

Plusieurs points alignés produisent des courbes qui *se croisent toutes au même endroit* : les paramètres de leur droite commune. On compte les votes dans une grille (l'*accumulateur*) et on cherche les pics. Pour les cercles, même principe avec trois paramètres (centre et rayon). La force de Hough est sa *robustesse aux occlusions et au bruit* : une droite partiellement masquée accumule moins de votes mais reste détectable, et le bruit ne forme aucun pic. Sa faiblesse : le coût de l'accumulateur, surtout pour les cercles, et la sensibilité à la finesse de la grille. ∎

#question-box(title: "Exemple")[
Trois pixels alignés horizontalement à hauteur 5 : ils votent tous, entre autres, pour « la droite horizontale à hauteur 5 ». Cette case de l'accumulateur reçoit trois votes, toutes les autres au plus un. Le pic est sans ambiguïté : la droite est détectée.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `Hough Lines` (ou via `cv2.HoughLines` et `cv2.HoughLinesP` en Python), la détection de droites est contrôlée par les paramètres opérationnels suivants :

- *Résolution de l'accumulateur (`rho`, `theta`)* :
- Dans VNStudio, ce paramètre correspond au champ *Distance Resolution (Rho)* ; en Python (OpenCV), il correspond à l'argument `rho` dans `cv2.HoughLines`.
- Dans VNStudio, ce paramètre correspond au champ *Angular Resolution (Theta)* ; en Python (OpenCV), il correspond à l'argument `theta` dans `cv2.HoughLines`.
- `theta` spécifie la résolution en radians pour la direction (généralement réglé à `pi/180`, soit 1 degré). Réduire cette valeur augmente la précision angulaire, mais disperse les votes de contours flous sur plusieurs cases voisines.
- *Seuil de votes (`threshold`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Votes Threshold* ; en Python (OpenCV), il correspond à l'argument `threshold` dans `cv2.HoughLines`.
- Le nombre minimal d'intersections de sinusoïdes dans une case pour qu'une droite soit validée. Un seuil trop bas génère de nombreuses fausses droites dues à des alignements fortuits de pixels de bruit. Un seuil trop élevé ne détecte que les très longues droites parfaites.
- *Longueur minimale de segment (`minLineLength`) et Écart maximal (`maxLineGap`)* (Hough probabiliste) :
- Dans VNStudio, ces valeurs correspondent aux champs *Minimum Line Length* et *Maximum Line Gap* ; en Python (OpenCV), elles correspondent aux arguments `minLineLength` et `maxLineGap` dans `cv2.HoughLinesP`.
- `minLineLength` (en pixels) élimine les segments trop courts.
- `maxLineGap` (en pixels) permet de relier deux segments colinéaires séparés par un trou (ex. : une ligne blanche discontinue sur la route).
]

#canvas[
Dans votre canvas :
`Image File` ──> `Grayscale` ──> `Canny Edge` ──> `Hough Lines` ──> `Display`.

Le nœud `Hough Lines` prend la carte de contours binaires produite par Canny et accumule les votes. En modifiant le curseur `Votes Threshold` (seuil de votes) dans l'inspecteur, vous déterminez le niveau de sélectivité nécessaire pour filtrer les lignes dominantes de la scène. Un nœud `Hough Circles` fait de même pour les cercles, et l'inspecteur compte les formes trouvées.

*Exercice de dépannage :* L'exercice consiste à charger une image bruitée et à régler le curseur *Votes Threshold* sur une valeur extrêmement basse (ex. : 10 votes) dans le nœud *Hough Lines*. Le lecteur observe à l'écran une quantité géante de lignes parasites traversant l'image de part en part. Cela montre comment des alignements fortuits de pixels de bruit s'accumulent au-dessus du seuil de tolérance, démontrant l'importance d'adapter ce seuil à la taille physique des objets recherchés.

---
]

// ============================================================

== La transformée de distance : mesurer une forme de l'intérieur

#subtitle[Du masque présence/absence à une carte de relief]

#figfull("/illustrations/chap10.5.png")

#figfull("/figures/fig_ch10_obs2_distance_transform.svg")

=== L'intention
Une forme binaire ne dit que « appartient / n'appartient pas ». On voudrait savoir, pour chaque pixel intérieur, _à quelle profondeur_ il appartient — pour en extraire l'axe, l'épaisseur, le point le plus intérieur.

=== La forme recherchée
On transforme le masque en *carte de relief* : le bord est au niveau de la mer, et l'intérieur monte en altitude à mesure qu'il s'éloigne du bord. Pour chaque pixel de la forme, la valeur est sa distance au pixel de fond le plus proche. Cette carte révèle deux choses. Ses *crêtes* — les pixels localement les plus éloignés de tout bord — forment le *squelette* (l'axe central) : le tracé d'une lettre, l'axe d'un os ou d'un vaisseau. Et son *point le plus haut* donne à la fois le point le plus intérieur de la forme et le rayon du plus grand disque qu'on peut y loger sans toucher le bord.

#info-box(title: "La formule")[
```
DT(p) = distance du pixel p au pixel de fond le plus proche
```
]

On peut choisir la distance (euclidienne, Manhattan… chapitre 3). Un algorithme rapide la calcule en deux passages sur l'image. Elle sert au *watershed* (le relief où l'eau monte sépare des objets accolés, chapitre 12), à la *squelettisation* (réduire une forme à son axe : chiffres manuscrits, réseaux vasculaires) et à la *navigation* (distance à l'obstacle le plus proche en tout point). ∎

#question-box(title: "Exemple")[
Un disque binaire de rayon 10 pixels : la carte vaut 0 sur le bord, croît vers le centre, et atteint exactement 10 au centre — le rayon. Le point le plus haut donne d'un coup le centre et le rayon, sans calculer ni contour ni centre de gravité. Pour un rectangle, la carte forme une arête centrale dont la hauteur donne le demi-côté.
]

#canvas[
Canvas : `Image File` → `Threshold` → `Distance Transform` → `Display`. Le nœud sort la carte de relief en fausses couleurs et l'inspecteur indique le point le plus intérieur et le rayon maximal inscrit — directement exploitables pour placer un marqueur ou amorcer un watershed.

---
]

// ============================================================

== Tableau récapitulatif — quelle transformée pour quel but ?

#table(
  columns: 5,
  table.header(
    [*Transformée*], [*Nouvelle base*], [*Ce qu'elle révèle*], [*Angle mort*], [*Usage type*]
  ),
  [Fourier (FFT)], [fréquences (ondulations)], [périodicité, amplitude et phase, fréquences parasites], [la position (un nombre est global)], [filtrage fréquentiel, recalage, texture],
  [DCT], [fréquences (cosinus)], [compaction d'énergie pour signaux corrélés], [discontinuités (artefacts blocs)], [compression JPEG, blocs compacts],
  [Hough], [paramètres de forme (distance, angle, rayon)], [formes géométriques par accumulation de votes], [formes non paramétriques, coût élevé], [droites, cercles, contours occultés],
  [Distance], [carte de proximité], [épaisseur, squelette, rayon inscrit, intérieur], [bruit de bord (carte = 0 sur tout le contour)], [watershed, squelette, navigation],
)

---

// ============================================================

== reconnaître la base où la question devient facile

Un problème difficile dans un domaine peut devenir trivial dans un autre :

```
Filtrer une fréquence parasite      → impossible à l'œil dans l'espace pixel,
                                       deux nombres à annuler dans Fourier.
Compresser une image naturelle      → 64 pixels difficiles à tronquer,
                                       quelques nombres DCT quasi nuls faciles à jeter.
Trouver des droites dans le bruit   → chercher des alignements (dur),
                                       chercher des pics de votes (facile).
Trouver le point le plus profond    → géométrie complexe dans les pixels,
  d'une forme                          un sommet dans la carte de distance.
```

Aucune transformée n'ajoute d'information : l'image reste la même, seul le système de coordonnées change. Chacune *réorganise* l'information pour qu'une question précise trouve sa réponse dans une opération simple — annuler un nombre, lire un sommet, repérer un pic. La compétence consiste à reconnaître, face à un problème, dans quelle base il devient facile.

Choisir un descripteur (chapitre 1), une distance (chapitre 3) ou un filtre (chapitre 5), c'était déjà décider ce qui mérite d'être vu ; choisir une base, c'est décider dans quel espace une propriété — fréquence, compacité, paramètre géométrique, profondeur — devient lisible. Le chapitre 12 s'appuiera sur la transformée de distance pour séparer des objets accolés par watershed.

---

// EXERCICES — CHAPITRE 10
// ============================================================

#pagebreak()
== Exercices pratiques

=== Exercice 1 · Effacer un motif de tissu sans toucher au reste

#figtodo("ex_ch10_tissu_carreaux", [Tissu à carreaux réguliers photographié à plat : motif périodique de lignes bleu])

*Ce que vous voyez.* Un motif parfaitement périodique. La mission : passer dans l'espace des fréquences pour repérer la signature du quadrillage, puis le faire disparaître à volonté.

*Pipeline VNStudio*
`Image File` → `FFT Analysis` → `Display`

Le nœud affiche le spectre de fréquences et permet d'appliquer un filtre passe-bas ou passe-haut avant de reconstruire l'image.



*Questions*

+ Observez le spectre : voyez-vous des points brillants bien nets, ou une tache diffuse ? Que disent ces points sur la régularité du tissu ? Repérez ceux qui correspondent aux lignes horizontales et ceux des verticales.

+ Appliquez un filtre passe-bas. Le quadrillage survit-il dans l'image reconstruite, ou s'efface-t-il ? Qu'a-t-on retiré au juste ?

+ Appliquez un filtre passe-haut. L'image reconstruite ne garde-t-elle que les contours du motif ? Pourquoi le fond uni a-t-il disparu ?

+ *Défi.* Passez la FFT sur un visage au lieu du tissu. Le spectre montre-t-il des points nets comme le tissu, ou une tache continue qui s'éteint depuis le centre ? Qu'est-ce que cela révèle sur la différence entre un motif fabriqué et une image naturelle ?


=== Exercice 2 · Retrouver les routes d'un carrefour par le vote

#figtodo("ex_ch10_carrefour", [Vue aérienne d'un carrefour en étoile : cinq routes rectilignes convergent vers ])

*Ce que vous voyez.* Plusieurs droites bien marquées dans la scène. La mission : les faire retrouver automatiquement, sans dire au système où elles sont.

*Pipeline VNStudio*
`Image File` → `Canny Edge` → `Hough Lines` → `Display`

Le nœud trace les droites détectées sur l'image et expose un seuil de vote qui décide combien de lignes ressortent.



*Questions*

+ Lancez le pipeline. Les cinq routes sont-elles toutes tracées ? Leur direction colle-t-elle à ce que vous voyez ?

+ Le rond-point central est un cercle. Le détecteur de droites trace-t-il une ligne dessus ? Pourquoi un bord qui tourne en rond ne réunit-il pas assez de votes pour une seule direction ?

+ Baissez le seuil de vote. Combien de fausses lignes apparaissent en plus ? D'où viennent-elles dans la scène (marquages, trottoirs, ombres) ?

+ *Défi.* Passez le détecteur sur une feuille de papier millimétré : il devrait ne trouver que deux familles de lignes (horizontales et verticales). Vérifiez. Faites ensuite pivoter la feuille de 15° et observez les deux familles tourner d'autant. Le détecteur suit-il la rotation ?


=== Exercice 3 · Trouver le cœur d'une forme pour préparer une découpe

#figtodo("ex_ch10_etoile_masque", [Masque binaire d'une étoile à cinq branches : fond noir, étoile blanche, branche])

*Ce que vous voyez.* Une forme à bras fins et centre épais. La mission : mesurer « l'épaisseur intérieure » en chaque point pour trouver les cœurs des régions, étape clé avant de séparer des objets collés.

*Pipeline VNStudio*
`Image File` → `Threshold (Advanced)` → `Distance Transform` → `Apply Colormap` → `Display`

La carte colore chaque pixel selon son éloignement du bord le plus proche : froid près des bords, chaud au cœur.



*Questions*

+ Sur la carte colorée, où se trouve le point le plus « chaud » de l'étoile : au centre du pentagone ou au bout d'une branche ? Pourquoi ?

+ Comparez la couleur au cœur d'une branche fine et au cœur du pentagone. Laquelle est la plus chaude ? Que dit cette couleur sur l'épaisseur locale de la forme ?

+ Cette carte sert de relief pour séparer des objets collés : on plante un germe à chaque sommet chaud. Combien de sommets chauds distincts comptez-vous sur l'étoile ? Un par branche plus un au centre, ou un seul ?

+ *Défi.* Collez deux étoiles par le bout d'une branche et relancez la carte. Y a-t-il toujours deux cœurs bien séparés ? Branchez un `Watershed` qui part de ces cœurs et vérifiez qu'il recoupe les deux étoiles à l'endroit du collage.



#v(2em)
#align(center)[
  #image("/QR Code.png", width: 60pt)
  #v(4pt)
  #text(size: 0.8em, style: "italic", fill: rgb("#64748b"))[Télécharger les images de référence]
]

]
