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


#chapter(title: [Le pochoir glissant : filtrage et convolution], toc: false)[

#figtodo("chap5", [Illustration de couverture du chapitre 5])

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Le même geste — un petit pochoir promené sur l'image — lisse, accentue ou détecte selon les nombres qu'on y inscrit. Choisir le pochoir, c'est déjà parier sur ce qu'est le signal.]

Chaque pixel d'une image n'existe pas isolément : il est entouré de voisins qui partagent son contexte. Le filtrage exploite ce voisinage — il remplace chaque pixel par une combinaison pondérée de ses proches. Avec le bon choix de pondération, la même mécanique lisse le bruit d'une radiographie, accentue les nervures d'une feuille en microscopie, détecte les craquelures d'une pièce industrielle ou repère les orientations dominantes d'une empreinte digitale.

Le fil du chapitre tient en une phrase : *un filtre est un a priori sur le signal.* Un _a priori_, c'est ce qu'on suppose vrai avant même de regarder. Choisir un filtre, c'est donc déclarer ce qu'on croit savoir du signal d'avance. Le filtre gaussien suppose qu'il varie doucement, sans saut brusque entre voisins. Le bilatéral suppose qu'il est lisse _par morceaux_, avec des sauts francs aux contours mais une régularité à l'intérieur des régions. Le Gabor suppose qu'il contient des ondulations à une certaine fréquence et orientation. Cette hypothèse est inscrite dans les nombres du filtre ; elle décide de ce qu'il voit et de ce qu'il rate. Un filtre mal choisi n'est pas seulement décevant : il impose une hypothèse fausse sur la nature des données, et les dégrade.

Le chapitre construit la convolution depuis ses propriétés, puis dérive les filtres essentiels en montrant à chaque fois quelle hypothèse leur forme encode. Il prolonge le chapitre 3 — la pondération d'un filtre est une façon de mesurer la proximité pertinente entre pixels — et prépare le chapitre 6, où le choix du filtre de dérivation conditionnera la qualité des détecteurs de bords.

=== Un peu de vocabulaire avant de commencer

- *Pixel et voisinage* : Un pixel `I(x, y)` est le point élémentaire de l'image. Son *voisinage* désigne l'ensemble des pixels qui l'entourent directement (par exemple dans une grille de 3×3 ou 5×5 pixels centrée sur lui).
- *Noyau (kernel)* : Une petite grille de nombres (comme un pochoir) qui définit les coefficients de pondération appliqués à chaque voisin.
- \*\*Convolution (notée \*)\*\* : L'action de faire glisser le noyau sur chaque pixel de l'image pour additionner les valeurs pondérées de son voisinage.

---

// ============================================================

== La convolution 2D : le pochoir promené partout pareil

#subtitle[Une petite grille de nombres, posée sur chaque pixel à son tour]

#figfull("/figures/fig_ch5_obs3_conv_vs_corr.pdf")

=== L'intention
On veut une opération qui exploite le voisinage de chaque pixel, mais une opération *uniforme* : le même traitement partout, réglé une seule fois, applicable à l'image entière.

=== La forme recherchée
L'image est celle d'un pochoir qui glisse sur une feuille. Le pochoir — appelé *noyau* (_kernel_) — est une petite grille de nombres. On le pose centré sur un pixel, on multiplie chaque case du pochoir par l'intensité qu'elle recouvre, on additionne le tout : c'est la nouvelle valeur du pixel central. On glisse d'un pas, on recommence, jusqu'à couvrir toute l'image. Cette opération s'appelle la *convolution*. Le même pochoir s'applique partout de façon identique — la rivière d'une image satellite reçoit exactement le traitement de la forêt voisine.

#info-box(title: "La formule")[
```
(I * K)(x, y) = Σᵢ Σⱼ I(x − i, y − j) · K(i, j)
```
]

`I` désigne l'image, `K` le noyau, l'astérisque `*` note la convolution, et le double `Σ` (sigma) additionne les calculs sur toutes les cases du pochoir.

Pour comprendre cette formule géométriquement, attardons-nous sur le signe moins : `x − i` et `y − j`.
+ *L'inversion du pochoir* : Au lieu de poser le pochoir tel quel, les indices négatifs nous obligent mathématiquement à le faire pivoter de 180° (c'est-à-dire le retourner de gauche à droite et de haut en bas) avant d'effectuer les multiplications. C'est l'étape de retournement qui distingue la convolution stricte de la simple corrélation croisée.
+ *Pourquoi cette contrainte ?* Ce retournement garantit que la convolution respecte une propriété mathématique cruciale : l'*associativité*. Grâce à cela, appliquer un filtre A puis un filtre B donne exactement le même résultat qu'appliquer d'abord le filtre B puis le filtre A. De même, on peut fusionner les deux filtres en un seul et l'appliquer en une unique passe. Sans ce retournement, l'ordre d'enchaînement modifierait le résultat, brisant la cohérence géométrique des pipelines de traitement.

Cette uniformité — le filtre ne dépend pas de l'endroit, on dit qu'il est *invariant par translation* — fait la force et la limite de la convolution. Sa force : un filtre réglé une fois s'applique à toute l'image sans recalibrage. Sa limite : si le signal a une structure différente selon la région (fond uniforme contre bord texturé), un seul noyau ne s'y adapte pas — d'où les filtres adaptatifs comme le bilatéral (§5.4).

Deux propriétés méritent d'être nommées. La convolution est *linéaire* (doubler l'image double le résultat). Et elle est *associative* : enchaîner deux filtres revient à appliquer un seul noyau combiné, calculé une fois pour toutes — ce qui économise un passage complet sur l'image quand on lisse puis on dérive. Linéarité et invariance par translation se révèlent caractériser _entièrement_ ce genre de filtres : tout traitement à la fois uniforme et linéaire _est_ nécessairement une convolution. Ce n'est pas une convention, mais un fait mathématique — la convolution est le seul outil de cette famille. ∎

=== La séparabilité : diviser pour régner
Certains noyaux 2D peuvent se décomposer en deux passes 1D : d'abord sur les lignes, puis sur les colonnes. On dit qu'ils sont *séparables*. Le gain est énorme. Pour un pochoir de 21 × 21, la version directe demande 441 multiplications par pixel ; la version séparée, 42 — un facteur 10, décisif pour un traitement exécuté à 30 images par seconde. Le filtre gaussien (§5.2) a cette propriété, ce qui explique pourquoi un flou même large reste rapide sur une image en haute définition.

=== Gestion des bords
Au bord de l'image, le pochoir déborde là où il n'y a pas de pixels. Quatre conventions usuelles comblent ce vide : étendre par des zéros (crée des bandes sombres artificielles), répéter en miroir les pixels du bord (le plus neutre, défaut le plus sûr pour le lissage), prolonger le pixel de bord en ligne droite, ou traiter l'image comme périodique (rarement pertinent sur des images naturelles). Le choix affecte les quelques pixels de bordure ; une analyse sérieuse des bords documente donc la convention employée.

#info-box(title: "Subtilité — convolution ou corrélation, et le type de données")[
Beaucoup de bibliothèques calculent en réalité une *corrélation* — la convolution sans une étape de retournement du noyau. Sans effet pour un pochoir symétrique (gaussien, moyenneur), mais pour un pochoir asymétrique (les dérivateurs du chapitre 6), cela inverse le signe : un gradient sort « à l'envers ». Autre point : travailler en nombres entiers sans marge fait saturer et tronque silencieusement les valeurs, surtout avec les noyaux à coefficients négatifs (LoG, DoG) ; on calcule alors en nombres à virgule.
]

#canvas[
Canvas : `Image Source` → `Convolution` → `Output Display`. Le nœud `Convolution` prend un noyau au choix (un moyenneur 5×5 incarne l'a priori « localement constant ») et expose la convention de bord. Pour les noyaux directionnels, une option de retournement garantit le comportement de convolution stricte.

---
]

// ============================================================

== Le noyau gaussien : l'hypothèse de douceur

#subtitle[Un spot lumineux flou centré sur chaque pixel]

#figfull("/illustrations/chap5.2.png")

=== L'intention
On veut atténuer le bruit en supposant que le signal est *localement lisse* : la valeur d'un pixel devrait ressembler à celle de ses voisins, et cette ressemblance décroître progressivement avec la distance.

=== La forme recherchée
La pondération doit valoir beaucoup au centre et fondre doucement vers les bords — une *cloche*. L'image utile est celle d'un spot lumineux flou centré sur chaque pixel : les zones les plus intensément éclairées (le centre) pèsent le plus dans la moyenne. Plus on élargit le spot, plus le voisinage pris en compte est étendu, plus l'image résulte floue.

#info-box(title: "La formule")[
```
G(x, y) = (1 / 2πσ²) · exp(−(x² + y²) / 2σ²)
```
]

Le seul réglage qui compte est σ (« sigma »), la largeur de la cloche : il fixe l'étendue du voisinage. Un petit σ encode un a priori de lisseur très local ; un grand σ, un signal supposé uniforme sur de grandes zones. Au-delà d'environ trois fois σ de distance, la pondération devient négligeable. ∎

=== Pourquoi la gaussienne et pas une autre cloche ?
Ce n'est pas un choix esthétique. La gaussienne est l'*unique* cloche qui réunit plusieurs bonnes propriétés à la fois. D'abord, elle *ne crée jamais de structure* : élargir le flou ne fait jamais apparaître de nouveau détail qui n'existait pas — un moyenneur en boîte, lui, peut créer de fausses ondulations. C'est le fondement de la « pyramide d'échelle », cette suite de versions de plus en plus floues d'une image, sur laquelle on cherche les structures à différentes tailles. Ensuite, elle est *séparable* (§5.1), donc rapide. Enfin, elle a la propriété d'*auto-similarité* : flouter deux fois de suite équivaut à flouter une seule fois un peu plus fort, ce qui rend ces pyramides prévisibles et stables. Ces qualités font de la gaussienne le filtre de lissage de référence.

#question-box(title: "Exemple chiffré")[
Un petit noyau gaussien 3×3, avec les coefficients entiers couramment utilisés :

```
     [ 1  2  1 ]
1/16 · [ 2  4  2 ]
     [ 1  2  1 ]
```

La somme des coefficients vaut 16, d'où la division par 16. Un filtre de lissage doit préserver la luminosité moyenne (ses coefficients somment à 1 une fois normalisés) ; sans cela, chaque passage assombrirait ou éclaircirait l'image. Le centre pèse 25 %, les quatre voisins directs 12,5 % chacun, les diagonales 6,25 % — une cloche en miniature.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `Gaussian Blur` (ou via `cv2.GaussianBlur` en Python), le comportement du lissage est contrôlé par les paramètres opérationnels suivants :

- *Taille du noyau (`ksize`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Kernel Size* ; en Python (OpenCV), il se nomme `ksize` dans `cv2.GaussianBlur`.
- Spécifie la largeur et la hauteur de la grille du noyau (ex. : 3×3, 5×5, 7×7). Cette taille doit obligatoirement être représentée par des nombres impairs pour que le noyau possède un pixel central bien défini. Plus la grille est grande, plus le lissage est large, mais plus le coût de calcul augmente.
- *Écart-type du lissage (`sigmaX`, `sigmaY`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Sigma* ; en Python (OpenCV), il se nomme `sigmaX` (et optionnellement `sigmaY`) dans `cv2.GaussianBlur`.
- Contrôle la largeur réelle de la cloche gaussienne (le degré de flou). Si vous réglez `sigma` sur `0` en Python, OpenCV calcule automatiquement l'écart-type idéal à partir de la taille du noyau. Si vous réglez `sigma` manuellement, veillez à ce que la taille du noyau soit au moins égale à *6 fois le sigma* (c'est-à-dire `ksize ≈ 6 * sigma`). Si le noyau est trop petit par rapport à `sigma`, la cloche gaussienne est tronquée brusquement sur les bords du pochoir, ce qui génère des artefacts visibles (des bandes d'intensité artificielles sur l'image).
- *Gestion des bordures (`borderType`)* :
- Dans VNStudio, ce paramètre correspond au menu déroulant *Border Type* ; en Python (OpenCV), il correspond à l'argument `borderType` dans `cv2.filter2D`.
- Définit comment OpenCV traite les pixels hors-limite lorsque le pochoir déborde des bords de l'image. Le mode par défaut `cv2.BORDER_DEFAULT` (ou `BORDER_REFLECT_101`) recopie l'image par symétrie au niveau des bords, évitant ainsi de créer des bandes noires artificielles qui fausseraient le calcul des moyennes.
]

#canvas[
Dans votre canvas :
`Image Source` ──> `Grayscale` ──> `Gaussian Blur` ──> `Output Display`.

Le nœud `Gaussian Blur` expose les curseurs `Kernel Size` (taille de grille) et `Sigma` dans l'inspecteur, permettant d'observer en direct le lissage du bruit et la disparition des détails les plus fins au fur et à mesure que la cloche s'élargit.

*Exercice de dépannage (échec contrôlé) :* L'exercice consiste à appliquer un flou avec un *Kernel Size* très large (ex. : 21x21) sur une image claire, en réglant le paramètre *Border Type* sur *Constant (0)* (ce qui remplit le hors-bord de noir). Le lecteur observe sur l'image de sortie un halo sombre artificiel qui bave depuis les bordures vers l'intérieur de l'image. Cela illustre comment un mauvais choix de gestion des bords corrompt l'intensité des pixels périphériques lors des calculs de moyenne locale.

---
]

// ============================================================

== DoG et LoG : voir ce qui change

#subtitle[Le chapeau mexicain qui s'allume sur les taches et les bords]

#figfull("/figures/fig_ch5_obs1_dog_bandpass.pdf")

=== L'intention
Après les filtres qui voient ce qui est lisse, on veut détecter ce qui _change_ — contours, taches, petits blobs. Mais mesurer un changement (dériver) amplifie le bruit ; il faut donc lisser avant.

=== La forme recherchée
La logique procède en deux temps. D'abord, on lisse avec un gaussien, ce qui efface le bruit fin qui rendrait toute mesure de variation instable — l'a priori reste que le signal utile est plus lisse que le bruit. Ensuite, on regarde la *courbure* de l'intensité : à quel point elle s'incurve. Sur une crête lumineuse, l'intensité culmine puis redescend, courbure forte ; à une transition franche (un bord), la courbure change de signe et passe par zéro. Détecter un contour revient à chercher ces *passages par zéro*.

Le filtre qui réalise les deux temps d'un coup a la forme d'un *chapeau mexicain* : positif au centre (il s'allume sur une tache claire entourée de sombre), négatif en couronne autour. On le nomme LoG (_Laplacian of Gaussian_, le laplacien d'une gaussienne — le laplacien étant l'outil mathématique standard qui mesure la courbure).

#info-box(title: "La formule")[
```
LoG(x,y) = ((x² + y² − 2σ²) / σ⁴) · G(x,y)
DoG = G_σ1 − G_σ2     (avec σ1 < σ2, typiquement σ2 / σ1 ≈ 1.6)
```
]

Le *DoG* (_Difference of Gaussians_, différence de deux gaussiennes) approxime le LoG par un raccourci économique : on floute l'image deux fois, à deux degrés, et on soustrait. Il se comporte comme un filtre *passe-bande* : il efface à la fois les très grandes structures (lissées par le flou large) et le bruit fin (lissé par le flou serré), ne laissant passer que les détails d'une taille proche de σ.

C'est la brique du détecteur de points SIFT : en calculant la DoG à plusieurs σ, on repère des blobs *et leur taille* — le même point d'intérêt se retrouve dans une image zoomée ou tournée. En microscopie, cela mesure automatiquement le diamètre de centaines de vésicules en une passe. ∎

#question-box(title: "Exemple chiffré")[
Au centre exact d'un blob clair sur fond sombre, la formule du LoG se simplifie : le terme entre parenthèses devient −2σ², et la réponse vaut −2/σ² × G(0,0), *fortement négative*. La courbure de l'intensité y est maximale. Chercher les minima (les valeurs les plus négatives) de la réponse localise les centres de blobs clairs ; pour des blobs sombres, on cherche les maxima.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `Laplacian of Gaussian` → `Output Display`. Le nœud calcule en nombres à virgule (indispensable : la réponse a deux signes, et un calcul en entiers effacerait la moitié négative) et propose une variante DoG plus rapide pour le même effet.

---
]

// ============================================================

== Le filtre bilatéral : lisser sans franchir les bords

#subtitle[Ne moyenner deux pixels que s'ils sont proches en place ET en valeur]

#figfull("/illustrations/chap5.4.png")

=== L'intention
Le gaussien lisse partout indistinctement, y compris à travers les contours — cohérent avec son a priori de signal globalement lisse, mais cet a priori est faux aux frontières. Une radiographie, une image satellite, un portrait : tous ont des zones intérieures uniformes séparées par des bords nets. On veut lisser l'intérieur des régions sans franchir leurs bords.

=== La forme recherchée
L'a priori devient : le signal est *lisse par morceaux* — régulier dans chaque région, avec des transitions brusques aux contours. On ajoute donc au poids de proximité spatiale du gaussien un second poids, en intensité : deux pixels ne se moyennent que s'ils sont à la fois *proches dans l'espace* ET *proches en valeur*. Un pixel de l'autre côté d'un contour fort a une grande différence d'intensité : son poids tombe à presque zéro, il ne contribue pas, le contour est préservé.

#info-box(title: "La formule")[
```
BF[I](p) = (1/W_p) · Σ_{q∈Ω}  G_σs(‖p − q‖) · G_σr(|I(p) − I(q)|) · I(q)
```
]

Le détail importe peu ; l'essentiel est qu'il y a *deux cloches gaussiennes multipliées*. La première, G_σs, pèse la distance spatiale (comme au §5.2). La seconde, G_σr, pèse la différence d'intensité : elle s'effondre dès que deux pixels n'ont pas la même clarté. Le produit des deux fait qu'un voisin ne compte que s'il est proche _et_ de teinte semblable. Conséquence importante : ce filtre *n'est pas une convolution*, car son poids dépend du contenu de l'image, pas seulement de la position. C'est un filtre *adaptatif* — plus lent, mais qui respecte les bords.

Deux réglages indépendants. σs (spatial) fixe la taille du voisinage ; σr (intensité) fixe la tolérance aux différences de teinte. Un petit σr ne moyenne que des teintes presque identiques (contours bien gardés, lissage faible) ; un grand σr rend le filtre indifférent aux différences et le ramène à un simple gaussien. ∎

#question-box(title: "Exemple chiffré")[
Pixel p sur un contour, d'intensité 200. À gauche, voisins à 195 (même côté) ; à droite, voisins à 50 (autre côté). Avec une tolérance σr = 30 :

```
poids du voisin à 195 : très proche en teinte → contribue fortement
poids du voisin à 50  : très différent        → contribution quasi nulle
```

Le pixel se moyenne donc uniquement avec ses voisins du même côté du contour. Le bord reste net. Cet a priori sert au débruitage préservant les contours (scanner, IRM), au lissage de peau en retouche, à l'effet « cartoon », au filtrage de cartes de profondeur en robotique.
]

#info-box(title: "Réglage — l'unité de la tolérance")[
Le filtre est sensible à l'échelle des valeurs : une tolérance réglée pour des pixels de 0 à 255 n'a pas le même sens sur une image ramenée entre 0 et 1. L'oublier produit un filtre soit transparent (tolérance trop grande), soit inopérant (trop petite) : on vérifie toujours σr par rapport à la plage réelle des données.
]

#canvas[
Canvas : `Image Source` → `Bilateral Filter` → `Output Display`. Le nœud expose les deux rayons (spatial et intensité) ; baisser le rayon d'intensité montre les contours se figer pendant que l'intérieur des régions se lisse.

---
]

// ============================================================

== Le filtre de Gabor : chercher une ondulation orientée

#subtitle[Un peigne à dents régulières, incliné, dont l'empreinte s'estompe vers les bords]

#figfull("/figures/fig_ch5_obs2_gabor.pdf")

=== L'intention
Certains signaux sont des *ondulations* localisées et orientées : une strie sur un tissu, une nervure de feuille, un sillon d'empreinte digitale. On veut un filtre qui réponde fortement là où l'image ondule à une fréquence donnée, dans une direction donnée.

=== La forme recherchée
Le filtre est le produit de deux choses qu'on visualise séparément. Une *enveloppe gaussienne* délimite une petite fenêtre autour du pixel — on ne cherche la strie qu'à proximité, pas dans toute l'image. Une *ondulation* (une sinusoïde, la courbe régulière qui monte et descend) oscille à une certaine fréquence le long d'une direction donnée. L'image juste est celle d'un *peigne à dents régulières*, incliné à l'angle voulu, dont l'empreinte s'estompe vers les bords de la fenêtre : passer ce peigne sur l'image mesure à quel point elle « vibre » à la fréquence du peigne, dans sa direction.

#info-box(title: "La formule")[
```
g(x,y) = exp(−(x'² + γ²y'²) / 2σ²) · cos(2π x'/λ + ψ)
```
]

Le premier facteur est l'enveloppe (la fenêtre gaussienne), le second l'ondulation (le cosinus). Les réglages : λ (« lambda ») est la longueur d'onde, c'est-à-dire l'espacement des dents du peigne, donc la taille de la texture cherchée ; θ (caché dans les coordonnées x', y') est l'orientation ; σ la taille de la fenêtre. Ce filtre a une qualité remarquable, partagée avec la gaussienne : il localise au mieux à la fois _où_ est la strie et _quelle_ est sa période. Cette qualité a une trace biologique frappante — les neurones du cortex visuel des mammifères réagissent comme des filtres de Gabor : l'évolution a sélectionné ce filtre pour analyser les textures. ∎

=== Le banc de filtres
Un seul Gabor ne capte qu'une fréquence et une orientation. En pratique on construit un *banc* : plusieurs longueurs d'onde × plusieurs orientations (souvent 0°, 45°, 90°, 135°). La réponse de l'image à tout le banc forme une signature de texture riche. C'est ainsi qu'on reconnaît un iris dans un passeport biométrique, ou qu'on distingue les types de couvert végétal sur une image satellite.

#question-box(title: "Exemple chiffré")[
Pour détecter des stries verticales espacées de 8 pixels : on règle la longueur d'onde sur 8 et l'orientation pour que l'ondulation varie horizontalement (ce qui détecte des stries verticales). Une zone à cette périodicité exacte produit une réponse maximale ; une zone lisse ou striée autrement, une réponse quasi nulle. En balayant les orientations, on obtient en chaque pixel l'orientation dominante de la texture.
]

#info-box(title: "Réglage — normaliser les filtres du banc")[
Les noyaux de Gabor n'ont pas tous la même « énergie » selon leurs réglages. Dans un banc comparatif, on normalise chaque noyau pour que les réponses soient comparables d'une orientation à l'autre ; sans cela, les orientations associées aux noyaux les plus énergétiques l'emportent artificiellement.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `Gabor Bank` → `Output Display`. Le nœud `Gabor Bank` applique plusieurs orientations et longueurs d'onde et sort la réponse maximale en chaque pixel, ce qui fait ressortir les textures orientées comme une carte d'intensité.

---
]

// ============================================================

== Tableau récapitulatif — le filtre comme a priori sur le signal

#table(
  columns: 5,
  table.header(
    [*Filtre*], [*Linéaire ?*], [*Séparable ?*], [*A priori sur le signal*], [*Usage type*]
  ),
  [Gaussien], [oui], [oui], [localement lisse, variation douce], [débruitage, pyramide d'échelle],
  [Moyenneur (boîte)], [oui], [oui], [localement constant], [lissage rapide, grossier],
  [LoG], [oui], [non], [contours = passages par zéro de la courbure], [détection de contours, blobs],
  [DoG], [oui], [~oui (2 gaussiens)], [structures à une bande de taille], [blobs, SIFT, multi-échelle],
  [Bilatéral], [*non*], [non], [lisse par morceaux (sauts aux contours)], [débruitage préservant les bords],
  [Gabor], [oui], [non], [ondulations orientées à une fréquence], [texture, biométrie, cortex visuel],
)

---

// ============================================================

== quand l'hypothèse est fausse, le filtre dégrade

Chaque filtre du chapitre porte une déclaration sur le signal, inscrite dans ses nombres et appliquée aveuglément à chaque pixel. Quand l'a priori est vrai — signal effectivement lisse (gaussien), effectivement à sauts nets (bilatéral), effectivement strié à telle fréquence (Gabor) — le filtre excelle. Quand il est faux, il dégrade le signal précisément là où on voulait l'améliorer : le gaussien dit « les variations brusques sont du bruit » et efface alors les contours qu'on voulait garder.

Le chapitre 3 mesurait la proximité pertinente entre objets ; un filtre fait de même entre pixels — le gaussien mesure une proximité spatiale, le bilatéral une proximité conjointe place-intensité, le Gabor une ressemblance d'ondulation. Un descripteur du chapitre 1, une distance du chapitre 3, un filtre ici : chacun encode une hypothèse sur ce qui compte, et reconnaître laquelle on impose explique pourquoi un résultat déçoit quand les données ne respectent pas l'hypothèse.

Le chapitre 6 enchaînera directement : tout détecteur de contour est un filtre de dérivation, et son comportement face au bruit dépend de l'a priori de lisseur qu'il porte en amont. Le chapitre 10 reprendra l'idée dans le domaine des fréquences, où l'on verra qu'un noyau de lissage est un « passe-bas », un noyau de dérivation un « passe-haut », un Gabor un « passe-bande orienté ».

---

]
