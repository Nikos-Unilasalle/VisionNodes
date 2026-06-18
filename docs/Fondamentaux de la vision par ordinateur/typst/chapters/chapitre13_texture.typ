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


#chapter(title: [La texture], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap13.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Deux régions peuvent peser le même histogramme — même moyenne, même variance — et n'avoir rien à voir : l'une lisse, l'autre rugueuse. La texture n'est pas dans la valeur des pixels, mais dans la façon dont ils se suivent.]

La texture est ce que l'histogramme ne voit pas. Deux régions peuvent avoir exactement la même distribution de niveaux de gris — même moyenne, même variance, même entropie — et pourtant l'une est lisse et l'autre rugueuse, l'une rayée et l'autre tachetée. La différence n'est pas dans la valeur des pixels, mais dans leur *arrangement spatial*. Ce chapitre construit les descripteurs de texture dans l'ordre où ils répondent à une question de plus en plus fine : la statistique d'un pixel seul (premier ordre), la cooccurrence de paires (GLCM), le micro-motif local (LBP), la réponse fréquentielle orientée (bancs de filtres).

Le fil du chapitre tient en une phrase : *décrire une texture, c'est choisir une relation de voisinage et une échelle, puis résumer la statistique de cette relation.* Un pixel seul n'a pas de texture ; elle vit dans le rapport entre pixels. Tout descripteur fixe donc trois choses — _quelle relation_ (des paires à un décalage, un centre contre sa couronne, une bande de fréquence), _à quelle échelle_ (le décalage d, le rayon R, la longueur d'onde λ), _quel résumé_ (un histogramme, cinq nombres, une énergie) — et chacun de ces choix jette la position individuelle pour ne garder qu'une statistique.

La texture est un carrefour du livre. Les statistiques du premier ordre sont les moments de l'histogramme (chapitre 2). Le filtre de Gabor du §13.5 est le filtre orienté du chapitre 5 transposé à l'analyse de texture. Le tenseur de structure (chapitre 6) mesurait déjà l'orientation locale ; LBP et Gabor lui ajoutent, l'un la forme du micro-motif, l'autre la sélectivité d'échelle. Comparer deux textures revient à comparer deux histogrammes ou deux vecteurs selon les distances du chapitre 3. Et le couple _information gardée / invariance gagnée_ prolonge le fil du chapitre 1 — appliqué non plus à une silhouette, mais à un motif statistique.

=== Un peu de vocabulaire avant de commencer

- *Texture* : L'arrangement spatial répétitif ou aléatoire des intensités, décrivant l'aspect de surface (rugueux, lisse, rayé) plutôt qu'une silhouette globale.
- *Matrice de co-occurrence (GLCM)* : Un tableau statistique comptant combien de fois des couples de pixels ayant des intensités données se trouvent à une distance et orientation fixées.
- *Entropie* : Une mesure du désordre ou de la complexité statistique d'une répartition d'intensités.

---

// ============================================================

== Statistiques du premier ordre : la texture que l'histogramme rate

#subtitle[Vider l'image dans un sac, secouer, compter les billes — sans noter d'où elles venaient]

=== L'intention
Avant tout outil sophistiqué, on tente le plus simple : décrire une région par la statistique de ses niveaux de gris — sa clarté moyenne, l'amplitude de ses variations, son désordre. On verra que cette description, juste mais aveugle, échoue sur la texture, et c'est cet échec qui motive tout le reste du chapitre.

=== La forme recherchée
On part de l'*histogramme normalisé* p(g) : pour chaque niveau de gris g, la proportion de pixels qui le portent. L'image utile est celle d'un sac de billes de couleur : on vide l'image pixel par pixel dans le sac, on secoue, et on compte combien de billes portent chaque nuance. Le sac dit _combien_, jamais _où_ — construire l'histogramme *jette toute information de position*. Sur cette distribution, on calcule des résumés : sa moyenne (la clarté), sa dispersion (le contraste), son désordre (l'entropie). Ce sont les moments de l'histogramme du chapitre 2, appliqués aux intensités.

#info-box(title: "La formule")[
```
À partir de l'histogramme normalisé p(g), g = 0..L−1 :
  moyenne    μ  = Σ_g g·p(g)
  variance   σ² = Σ_g (g−μ)²·p(g)
  asymétrie  γ  = Σ_g (g−μ)³·p(g) / σ³
  uniformité U  = Σ_g p(g)²
  entropie   H  = −Σ_g p(g)·log p(g)
```
]

La variance mesure l'amplitude des fluctuations de niveau : un fond uniforme a σ² ≈ 0, une texture contrastée un σ² élevé. L'uniformité U vaut 1 pour une zone d'un seul niveau et décroît quand l'histogramme s'étale. L'entropie H compte les bits nécessaires pour coder un pixel tiré au hasard : maximale quand tous les niveaux sont équiprobables. ∎

=== Son angle mort est définitionnel
Par construction, ces descripteurs ignorent l'arrangement spatial : ils résument la relation la plus pauvre possible, un pixel seul, sans voisin. Une zone lisse et une zone poivre-et-sel qui partagent le même histogramme leur sont rigoureusement indiscernables. Ce n'est pas un défaut accidentel mais le vide exact que les sections suivantes comblent, en réintroduisant la géométrie qu'on vient de jeter.

#question-box(title: "Exemple chiffré")[
Deux patchs 1×4 de même histogramme `{0, 1, 2, 3}` (chaque niveau une fois) :

```
A = [0, 1, 2, 3]   (rampe lisse — les valeurs montent progressivement)
B = [0, 3, 1, 2]   (alternance abrupte — les valeurs sautent)

μ_A = μ_B = 1,5
σ²_A = σ²_B = (1,5² + 0,5² + 0,5² + 1,5²)/4 = 1,25
H_A = H_B,  U_A = U_B   …   identiques sur TOUS les descripteurs d'ordre 1
```

Aucune statistique du premier ordre ne sépare A de B : même moyenne, même variance, même entropie. Pourtant A monte doucement (voisins proches qui se ressemblent) et B saute brutalement (voisins proches qui diffèrent). Il faut regarder les *paires de pixels* — c'est la GLCM du §13.2.
]

#info-box(title: "Subtilité — l'espace gamma et la quantification")[
Moyenne et variance calculées sur des valeurs encodées en gamma (ce qu'on lit directement dans un JPEG ou un PNG, chapitre 7) ne sont pas celles du signal lumineux physique. Pour une vraie mesure de rugosité radiométrique — comparer la réflectance de matériaux en télédétection —, on linéarise l'image avant le calcul. Autre arbitrage : réduire le nombre de niveaux de 256 à 16 stabilise les estimateurs sur de petits patchs mais lisse le contraste — le même compromis reviendra, amplifié, dans la GLCM.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `First Order Stats` → `Inspector`. Le nœud sort moyenne, variance, uniformité et entropie sur la région. Brancher les deux patchs A et B sur deux branches montre les sorties identiques — la démonstration en acte de l'angle mort du premier ordre.

---
]

// ============================================================

== Matrice de cooccurrence (GLCM) : la statistique des paires

#subtitle[Compter non plus les billes, mais les paires de billes voisines]

#figfull("/figures/fig_ch13_obs1_glcm.svg")

#figfull("/figures/fig_ch13_obs1_glcm.svg")

=== L'intention
Le premier ordre a échoué faute de regarder les voisinages. On veut la pièce manquante : non plus la distribution d'un pixel isolé, mais celle d'une *paire* de pixels liés par une relation géométrique fixée. Là se cache l'information que A et B (§13.1) ne livraient pas.

=== La forme recherchée
L'image utile prolonge celle du sac de billes : au lieu de compter combien de billes portent chaque couleur, on compte combien de _paires de billes voisines_ portent telle et telle couleur. On choisit la relation — un décalage `d` (l'échelle) et une orientation `θ` (la direction) — et on dénombre toutes les paires de l'image qui la réalisent. Le résultat est la *matrice de cooccurrence* (GLCM) : un tableau L×L où la case (i, j) compte combien de fois un pixel de niveau i a, au décalage (d, θ), un voisin de niveau j. Si les voisins se ressemblent souvent (texture lisse), la masse se concentre sur la *diagonale* ; s'ils diffèrent souvent (texture contrastée), elle s'en écarte.

#info-box(title: "La formule")[
```
P(i, j | d, θ) = nombre de paires de pixels distantes de (d, θ)
                 dont l'un vaut i et l'autre j,   puis normalisation Σ P = 1
```
]

Après normalisation, `P(i, j)` est la probabilité qu'un pixel de niveau i ait, au décalage (d, θ), un voisin de niveau j — l'estimateur empirique de la loi jointe du couple (pixel, voisin). On rend en général la matrice *symétrique* (compter (i, j) et (j, i)) pour ne pas privilégier un sens de parcours. ∎

=== Ce qu'elle mesure, et son angle mort
La GLCM encode la co-variation locale : sur la diagonale, les paires de niveaux semblables (zones lisses) ; loin d'elle, les transitions brusques (bords, rugosité). Trois angles morts. Elle dépend du couple (d, θ) : une texture rayée verticalement est invisible si on n'interroge que θ = 0°. Elle explose en taille (L×L) et se vide si L est grand — d'où la quantification quasi obligatoire à 8–32 niveaux. Et elle n'est pas invariante en rotation, sauf à moyenner sur plusieurs θ.

#question-box(title: "Exemple chiffré")[
Image-jouet 3×3 à trois niveaux, décalage horizontal `d = 1, θ = 0°`, matrice symétrique :

```
img =  0 0 1
       0 1 2
       1 2 2

Paires horizontales adjacentes : (0,0) (0,1) | (0,1) (1,2) | (1,2) (2,2)
→ 6 paires, comptées dans les deux sens = 12 cooccurrences
```

GLCM symétrique normalisée (÷12) :

```
[ 1/6  1/6   0  ]
[ 1/6   0   1/6 ]      (6 cases à 1/6 ≈ 0,167)
[  0   1/6  1/6 ]
```

Les six paires se rangent le long de la diagonale et juste à côté : niveaux voisins majoritairement proches (0-0, 1-2, 2-2) ou distants d'un cran (0-1) — la signature d'une texture à transitions douces. On en extrait les scalaires d'Haralick au §13.3.
]

#info-box(title: "Réglage — quantifier, symétriser, moyenner les angles")[
Quantifier d'abord (passer de 256 à 16 ou 32 niveaux) : sinon la matrice 256×256 est creuse et statistiquement non fiable sur tout patch raisonnable — trop peu de niveaux écrase le contraste utile, trop de niveaux vide la matrice. Symétrie et normalisation sont presque toujours souhaitées : sans normalisation, les descripteurs ne se comparent pas entre patchs de tailles différentes. Le couple (d, θ) est un choix, pas un réglage neutre : pour l'invariance directionnelle, on calcule sur θ ∈ {0°, 45°, 90°, 135°} et on moyenne. Enfin, les paires qui débordent de l'image ne sont pas comptées — sur un petit patch, l'effet de bord est substantiel.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `GLCM` (ou via les fonctions de `skimage.feature.graycomatrix` en Python), le calcul de la cooccurrence dépend des réglages de déplacement et d'échelle :

- *Distances de décalage (`distances`)* :
- Dans VNStudio, ce paramètre correspond au champ *Displacement Steps* ; en Python (scikit-image), il correspond à l'argument `distances` de la fonction `skimage.feature.graycomatrix`.
- Une liste de pas en pixels (ex. : `[1, 3, 5]`) définissant la distance séparant les deux pixels comparés. Un pas de `1` pixel capture la texture à haute fréquence (la micro-rugosité), tandis qu'un pas plus grand (ex. : `5` ou `10`) est nécessaire pour analyser des motifs texturés de plus grande échelle (des rayures larges ou des mailles).
- *Directions angulaires (`angles`)* :
- Dans VNStudio, ce paramètre correspond au champ *Directions (Angles)* ; en Python (scikit-image), il correspond à l'argument `angles` de la fonction `skimage.feature.graycomatrix`.
- Une liste d'orientations en radians (généralement `[0, pi/4, pi/2, 3*pi/4]`, correspondant à 0°, 45°, 90° et 135°). Si les textures de vos images ont une direction préférentielle (ex. : des lignes horizontales), la GLCM présentera des variations fortes selon l'angle choisi. Rendre le descripteur invariant à la rotation demande de calculer la GLCM sur les quatre directions et de faire la moyenne des matrices obtenues.
- *Niveaux de gris quantifiés (`levels`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Quantization Levels* ; en Python (scikit-image), il correspond à l'argument `levels` de la fonction `skimage.feature.graycomatrix`.
- Le nombre d'intensités distinctes pris en compte. Calculer une GLCM sur 256 niveaux produit une matrice géante de 256×256 cases (65 536 valeurs), lente à traiter et très bruitée. On quantifie généralement l'image sur 16 ou 32 niveaux avant le calcul, réduisant la matrice à une taille compacte (ex. : 32×32) et beaucoup plus stable.
]

#canvas[
Dans votre canvas :
`Image Source` ──> `Grayscale` ──> `GLCM` ──> `Inspector`.

Le nœud `GLCM` quantifie en interne l'image d'entrée et calcule la matrice statistique. L'inspecteur affiche des résumés numériques (contraste, corrélation, homogénéité, énergie, entropie) calculés d'après les formules ci-dessus, et transmet la matrice au nœud `Haralick Features` du §13.3.

*Exercice de dépannage (échec contrôlé) :* L'exercice consiste à charger une image d'une texture striée verticalement présentant une période d'alternance de 4 pixels. Brancher cette image à un nœud *GLCM* et régler la distance de décalage horizontale sur 4 pixels. Le lecteur constate dans l'inspecteur que le contraste d'Haralick chute à une valeur proche de 0 (la texture paraît lisse car on compare des pixels en phase). Régler ensuite le décalage sur 2 pixels. Le lecteur observe le contraste remonter à sa valeur maximale, illustrant comment le choix du pas peut éteindre ou allumer la sensibilité de la GLCM en fonction de la périodicité du motif.

---
]

// ============================================================

== Descripteurs d'Haralick : compresser la matrice en cinq nombres

#subtitle[Cinq questions posées à la matrice pour la résumer en cinq nombres]

=== L'intention
Une GLCM 16×16 contient 256 nombres : illisible et redondante. On veut la résumer en une poignée de scalaires, chacun isolant un aspect géométrique précis — l'amplitude des sauts, la régularité, le désordre, la prévisibilité du voisin.

=== La forme recherchée
Chaque descripteur d'Haralick est une *somme pondérée* de la matrice par un noyau qui souligne un trait. Vue comme un relief, la GLCM porte sa masse plus ou moins loin de son sillon diagonal :

- le *contraste* pèse par (i−j)² : il grandit quand la masse s'éloigne de la diagonale — l'amplitude des sauts locaux ;
- l'*énergie* (Σ P², dite _Angular Second Moment_) est maximale quand la masse se concentre sur peu de cases — une texture régulière et prévisible, comme un quadrillage de tissu, « vote » toujours pour les mêmes paires. C'est l'inverse conceptuel de l'entropie ;
- l'*homogénéité* pèse par 1/(1+|i−j|) : elle récompense les paires proches de la diagonale — l'opposé souple du contraste ;
- l'*entropie* est celle de Shannon, appliquée à la loi jointe : combien de bits pour coder une paire tirée au hasard. Une texture aléatoire (sable, bruit) étale la masse et la maximise ;
- la *corrélation* dit dans quelle mesure on peut _prédire_ le voisin connaissant le pixel central. Sur des stries régulières, elle frôle 1 dans la direction des stries.

#info-box(title: "La formule")[
```
Contraste    = Σᵢⱼ (i−j)²·P(i,j)
Énergie/ASM  = Σᵢⱼ P(i,j)²
Homogénéité  = Σᵢⱼ P(i,j) / (1 + |i−j|)
Entropie     = −Σᵢⱼ P(i,j)·log P(i,j)
Corrélation  = Σᵢⱼ (i−μᵢ)(j−μⱼ)·P(i,j) / (σᵢ·σⱼ)
```
]

μᵢ, σᵢ sont la moyenne et l'écart-type des marges de la GLCM. Les cinq scalaires héritent du choix de (d, θ) ; ils sont le résumé compact de la statistique de la paire. ∎

#question-box(title: "Exemple chiffré")[
Sur la GLCM normalisée du §13.2 (six cases à 1/6) :

```
Énergie   = 6 · (1/6)²              = 1/6        ≈ 0,167
Contraste = 4 cases hors-diag à |i−j|=1 = 4·(1/6) ≈ 0,667
Homogén.  = 2·(1/6)/1 + 4·(1/6)/2  = 2/3        ≈ 0,667
Entropie  = −6·(1/6)·ln(1/6) = ln 6              ≈ 1,79 nats
Corrél.   = (1/3) / (2/3)                        = 0,5
```

Contraste modéré et corrélation positive (0,5) confirment des transitions douces et ordonnées — exactement ce que la disposition de la GLCM montrait. Les cinq nombres redisent, sous forme compacte et comparable, ce que la matrice exprimait en clair.
]

#info-box(title: "Différence d'implémentation — des noms qui trompent")[
Trois conventions divergentes, chacune source de résultats faux et silencieux. D'abord, `'energy'` de scikit-image n'est pas l'ASM : `graycoprops(glcm, 'ASM')` rend Σ P² (notre énergie ≈ 0,167), mais `graycoprops(glcm, 'energy')` rend √ASM (≈ 0,408) — deux noms, deux valeurs. Ensuite, deux « homogénéités » coexistent : l'_Inverse Difference_ en 1/(1+|i−j|), et l'_Inverse Difference Moment_ en 1/(1+(i−j)²), que renvoie `'homogeneity'` ; elles coïncident tant que |i−j| ≤ 1, divergent dès |i−j| = 2. Enfin, la base du logarithme de l'entropie change la valeur d'un facteur ln 2 ≈ 0,693 (nats avec ln, bits avec log₂). Ne jamais comparer des valeurs issues de conventions différentes.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `GLCM` → `Haralick Features` → `Inspector`. Le nœud `Haralick Features` lit la matrice du §13.2 et sort les cinq scalaires, moyennés sur les quatre orientations pour l'invariance directionnelle ; l'inspecteur les affiche côte à côte.

---
]

// ============================================================

== Local Binary Pattern (LBP) : le micro-motif local

#subtitle[Demander à chaque voisin : es-tu plus clair que moi ? oui/non, et lire le mot binaire]

#figfull("/figures/fig_ch13_obs2_lbp.svg")

#figfull("/figures/fig_ch13_obs2_lbp.svg")

=== L'intention
La GLCM compte des paires. On veut maintenant décrire chaque pixel par la *forme* de son voisinage immédiat — bord, coin, point, zone plate — et résumer la région par la fréquence de ces formes. On vise au passage une robustesse à l'éclairage que les niveaux bruts n'offrent pas.

=== La forme recherchée
Pour comprendre comment capter la forme locale, on imagine un randonneur debout sur le pixel central, dont l'altitude correspond à l'intensité lumineuse de ce pixel. Autour de lui, disposés sur un cercle de rayon R, se trouvent P points d'observation (les pixels voisins). Le randonneur tourne sur lui-même et examine chaque point de sa couronne, l'un après l'autre, dans un ordre fixe (par exemple en partant du voisin de droite et en tournant dans le sens inverse des aiguilles d'une montre).

Pour chaque point d'observation, la question posée est binaire : « Ce point est-il situé plus haut (plus clair) ou plus bas (plus sombre) que le sol sous mes pieds ? »
- Si le point observé est plus haut ou à la même hauteur, le randonneur plante un drapeau « 1 » ;
- S'il est plus bas, il plante un drapeau « 0 ».

En faisant un tour complet, il obtient ainsi une couronne de P drapeaux (par exemple 8 drapeaux). Cette suite circulaire de 1 et de 0 forme un mot binaire de P bits. Ce mot encode précisément le micro-relief ou la forme géométrique du terrain autour de sa position :
- Un plateau parfaitement plat donnera une couronne uniforme (`00000000` ou `11111111`) ;
- Un flanc de colline franc donnera une moitié de 1 et une moitié de 0 (`00001111`) ;
- Un col ou un petit ravin dessinera d'autres motifs binaires caractéristiques.

En traduisant ce mot binaire en un nombre entier (en posant par exemple que le premier drapeau vaut 1, le deuxième 2, le troisième 4, le quatrième 8, et ainsi de suite jusqu'à 2^(P-1)), chaque relief possible reçoit une étiquette numérique unique. L'image entière est ainsi convertie en une carte d'étiquettes de micro-reliefs. C'est l'*histogramme* de ces étiquettes — c'est-à-dire le décompte de la fréquence de chaque type de relief sur toute la zone — qui sert de descripteur de texture.

Ce seuillage relatif par rapport à l'altitude du centre offre une invariance précieuse : le code obtenu ne dépend d'aucune transformation monotone des niveaux de gris. Si on ajoute une constante d'éclairage (le soleil se lève), si on multiplie par un gain (on augmente l'exposition), ou si on applique une compression gamma, les relations d'altitude relative restent inchangées : ce qui était plus haut reste plus haut. L'invariance à l'illumination découle du choix même de cette relation (le signe d'une différence d'altitude), et non de sa valeur numérique absolue.

#info-box(title: "La formule")[
```
LBP_{P,R}(c) = Σ_{p=0}^{P−1} s(g_p − g_c) · 2^p,    s(x) = 1 si x ≥ 0, sinon 0
```
]

g_c est le niveau du centre, g_p celui de chaque voisin sur le cercle (P points, rayon R). LBP choisit la relation centre/couronne, l'échelle R, et produit comme résumé l'histogramme des codes. ∎

=== Ce qu'elle mesure, et son angle mort
LBP capte les micro-structures à l'échelle R. Deux variantes comptent. Le *LBP uniforme* ne garde distinctement que les motifs à au plus 2 transitions 0↔1 dans le code circulaire (les motifs « propres » : coins, bords, arcs) et regroupe tous les autres, bruités, dans une seule case fourre-tout — ce qui réduit la dimension et la sensibilité au bruit. Le *LBP rotation-invariant* prend la plus petite rotation circulaire du code, pour ne pas distinguer `00001111` de `00111100`. Angles morts : LBP est mono-échelle (un seul R à la fois ; on empile plusieurs R pour le multi-échelle), fragile au bruit quand g_p ≈ g_c (un grain peut basculer le signe), et il jette l'*amplitude* des différences pour n'en garder que le signe — perdant l'information de contraste absolu.

#question-box(title: "Exemple chiffré")[
Voisinage 3×3 (P = 8, R = 1), centre g_c = 50, voisins parcourus depuis le coin haut-gauche en sens horaire :

```
60 20 90        g_p :  60  20  90  10  80  70  30  40
40 50 10        s   :   1   0   1   0   1   1   0   0   (g_p ≥ 50 ?)
30 70 80
                LBP = 1 + 4 + 16 + 32 = 53
```

Le code circulaire `1 0 1 0 1 1 0 0` présente *6 transitions* 0↔1 (en bouclant). Il n'est pas uniforme (seuil : ≤ 2 transitions) : il tombe dans la case fourre-tout — typique d'un voisinage irrégulier ou bruité. Un bord franc, lui, donnerait un `00001111` à 2 transitions exactes, uniforme et clairement identifiable.
]

#info-box(title: "Différence d'implémentation — l'ordre des voisins, et la bonne distance")[
L'ordre des voisins est une convention : scikit-image démarre au voisin de droite et tourne dans le sens trigonométrique, l'exemple ci-dessus part du coin haut-gauche en sens horaire. L'entier produit diffère donc d'une bibliothèque à l'autre, mais l'histogramme (le vrai descripteur) reste équivalent à une permutation des cases près — on ne compare jamais des codes LBP bruts entre deux bibliothèques. Pour P = 8, R = 1, les voisins tombent sur la grille ; pour R fractionnaire ou P ≠ 8, les positions hors grille sont interpolées. Enfin, l'histogramme LBP se compare en χ² ou Bhattacharyya (chapitre 3), *pas* en euclidien : les cases sont des catégories nominales (des codes de motifs), pas une échelle ordonnée.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `LBP` → `Inspector`. Le nœud expose P, R et la variante (uniforme, rotation-invariant) ; il sort l'histogramme des codes comme vecteur descripteur, à comparer ensuite via le nœud `Histogram Distance` (chapitre 3) en mode χ².

---
]

// ============================================================

== Bancs de filtres et énergie de Gabor : la texture comme spectre orienté

#subtitle[Un peigne accordé à une fréquence et une direction, qui vibre fort sur la bonne trame]

#figfull("/figures/fig_ch13_obs3_gabor.svg")

#figfull("/figures/fig_ch13_obs3_gabor.svg")

=== L'intention
Une texture est une répétition : les stries d'un tissu, les alvéoles d'une éponge, les grains d'une roche. Toute répétition a une échelle (une période) et souvent une direction privilégiée. On veut mesurer _combien d'énergie_ la texture place à chaque fréquence et dans chaque direction — mais *localement*, sans perdre où elle se trouve.

=== La forme recherchée
La transformée de Fourier globale (chapitre 10) dit quelles fréquences sont présentes dans toute l'image, pas où. Le filtre de Gabor est le compromis : une sinusoïde de longueur d'onde λ et d'orientation θ, *fenêtrée* par une gaussienne. C'est le « peigne » du chapitre 5 — un peigne à dents régulières, incliné, dont l'empreinte s'estompe vers les bords de la fenêtre. Passé sur l'image, il répond fort là où elle ressemble _localement_ à une sinusoïde de sa fréquence et de sa direction. On le décline en *banc* (plusieurs λ × plusieurs θ) et on mesure l'énergie de réponse à chaque combinaison : le vecteur de ces énergies est la signature fréquence-orientation de la texture. C'est le pendant orienté du tenseur de structure (chapitre 6), augmenté de la sélectivité d'échelle via λ.

#info-box(title: "La formule")[
```
g(x,y) = exp(−(x'² + γ²y'²) / 2σ²) · cos(2πx'/λ + ψ)
         avec x' =  x·cosθ + y·sinθ ,  y' = −x·sinθ + y·cosθ

Énergie de texture en (λ, θ) :  E(λ,θ) = ‖ I * g_{λ,θ} ‖²   (sur la fenêtre analysée)
```
]

Le premier facteur est l'enveloppe (la fenêtre gaussienne), le second l'ondulation (le cosinus). λ est l'espacement des dents du peigne (l'échelle), θ son inclinaison (la direction). Le banc choisit la relation à une sinusoïde (λ, θ), λ comme échelle, et l'énergie locale comme résumé. ∎

=== Ce qu'elle mesure, et son angle mort
Le banc répond fort là où la texture possède une périodicité à la fréquence et à l'orientation du filtre. Une trame régulière (tissu, grille, mire) allume un pic net ; une texture aléatoire (sable, bruit blanc) étale l'énergie uniformément. Angles morts : le pas d'échantillonnage (λ, θ) fixe la résolution — un motif de période intermédiaire entre deux bandes λ est mal vu ; le banc est coûteux (autant de convolutions que de filtres) ; et l'énergie seule ignore la *phase*, si bien que deux textures de même spectre mais d'agencement différent peuvent se confondre — l'angle mort du §13.1, transposé au domaine fréquentiel.

#question-box(title: "Exemple chiffré")[
Mire sinusoïdale verticale de *période 4 pixels* → fréquence 1/4 cycle/pixel, orientation 0° :

```
Banc de Gabor, θ = 0°, longueurs d'onde λ ∈ {2, 4, 8} px :
  λ = 4  →  fréquence 1/4 = celle de la mire  → RÉSONANCE, énergie maximale
  λ = 2  →  fréquence 1/2 (trop haute)        → réponse faible
  λ = 8  →  fréquence 1/8 (trop basse)        → réponse faible

Même mire interrogée à λ = 4 mais θ = 90° :
  la sinusoïde est constante le long de la verticale → énergie ≈ 0
```

Le pic tombe sur le filtre dont λ et θ coïncident avec la mire (λ = 4, θ = 0°). Le banc localise la texture dans le plan (échelle, orientation) : sa signature fréquence-direction.
]

#info-box(title: "Réglage — normaliser, lier σ et λ, prendre la magnitude")[
Normaliser les noyaux (somme nulle pour la composante cosinus, énergie unité) rend les énergies comparables entre échelles. σ et λ sont liés : fixer leur rapport constant (σ ≈ 0,56 λ pour environ une octave de largeur de bande) garde une sélectivité homogène d'une échelle à l'autre. On utilise toujours la *magnitude* des deux phases (ψ = 0 et ψ = π/2, soit les parties réelle et imaginaire du filtre complexe) : la magnitude est insensible à la position du motif sous le filtre, alors qu'une seule phase oscille avec elle. Enfin, λ proche de 2 px touche la limite de Nyquist (chapitre 10) : les réponses aux plus hautes fréquences sont peu fiables.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `Gabor Bank` → `Inspector`. Le nœud `Gabor Bank` (déjà rencontré au chapitre 5) applique plusieurs λ et θ et sort le vecteur d'énergies — la signature fréquence-orientation ; l'inspecteur la présente comme une petite carte (échelle × orientation) où le pic de résonance saute aux yeux.

---
]

// ============================================================

== Tableau récapitulatif — quelle relation, quelle échelle, quel résumé

#table(
  columns: 6,
  table.header(
    [*Descripteur*], [*Relation interrogée*], [*Échelle*], [*Résumé produit*], [*Invariances*], [*Angle mort principal*]
  ),
  [1er ordre], [aucune (pixel seul)], [—], [μ, σ², H (scalaires)], [translation, rotation (totales)], [ignore tout arrangement spatial],
  [GLCM / Haralick], [paires à (d, θ)], [décalage d], [5 scalaires × (d, θ)], [translation ; rotation si moyenné sur θ], [dépend de (d, θ) ; coûteuse en L],
  [LBP], [centre vs couronne de P points], [rayon R], [histogramme de codes], [niveaux monotones ; rotation (variante)], [bruit près du seuil ; jette l'amplitude],
  [Gabor / banc], [corrélation à une sinusoïde (λ, θ)], [longueur d'onde λ], [énergies en (λ, θ)], [translation (via magnitude)], [ignore la phase ; coûteux],
)

_État de l'art :_ ces familles précèdent l'apprentissage profond, qui domine aujourd'hui la classification de textures (réseaux convolutifs, _bilinear pooling_ héritier de la cooccurrence, _scattering transforms_ cousins du banc de Gabor). Les méthodes classiques gardent leur créneau — sans données d'entraînement, interprétables, légères, robustes sur des problèmes contraints (microscopie, télédétection, contrôle industriel) — et survivent à l'intérieur des pipelines modernes : un LBP en couche d'entrée fixe, une matrice de Gram (cooccurrence de canaux profonds) au cœur du transfert de style neural.

---

// ============================================================

== la texture est une relation, pas une valeur

Le chapitre raconte une seule histoire, déclinée quatre fois : un pixel n'a pas de texture, seule une relation entre pixels en a une. Chaque section a construit cette relation un peu plus finement.

```
1er ordre : relation « aucune »          — résume la distribution d'UN pixel (et échoue)
GLCM      : relation « paire à (d,θ) »   — résume la loi jointe de DEUX pixels liés
LBP       : relation « centre/couronne » — résume le SIGNE des différences au voisinage
Gabor     : relation « sinusoïde (λ,θ) » — résume l'ÉNERGIE par fréquence et direction
```

D'un bout à l'autre, le même mouvement : on ajoute la géométrie que le premier ordre avait jetée (la position du voisin, la forme du motif, sa fréquence), puis on la re-jette partiellement sous forme de statistique. Et l'invariance récoltée est exactement l'information délibérément perdue : LBP achète l'invariance à l'éclairage en ne gardant que le signe des différences, Gabor l'invariance de position en ne gardant que la magnitude, la GLCM l'invariance directionnelle en moyennant sur les angles.

C'est le fil du chapitre 1 transposé du contour au motif : un descripteur garde une chose et en jette une autre. Comme une distance déclare ce qui rapproche deux points (chapitre 3) et un filtre encode un a priori sur le signal (chapitre 5), décrire une texture revient à choisir le couple relation-échelle où la régularité cherchée devient visible. Le chapitre 14 quittera la description pour la mesure de la qualité d'une image, où la même entropie de Shannon reparaîtra, cette fois comme juge de l'information.

---

]
